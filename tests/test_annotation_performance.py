"""Index correctness and bounded work with large annotation sets, without timing limits."""
import math
import random
from unittest.mock import patch
from PyQt5.QtCore import QPointF, QRectF, QSize, Qt, QEvent
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication
from shape import Shape
from canvas import Canvas
from test_interactive_editing import add, drag, mouse
from test_workspace_navigation import prepare


def box(x, y, width=40, height=30):
    shape = Shape('Bridge')
    shape.points = [QPointF(x, y), QPointF(x + width, y), QPointF(x + width, y + height), QPointF(x, y + height)]
    shape.isRotated = False
    shape.close()
    return shape


def test_index_matches_linear_bounds_before_and_after_mutations(app):
    randomizer = random.Random(42)
    canvas = Canvas()
    canvas.shapes = [box(randomizer.randrange(5000), randomizer.randrange(5000)) for _ in range(500)]
    def compare():
        for _ in range(80):
            rect = QRectF(randomizer.randrange(5000), randomizer.randrange(5000), 500, 400)
            assert canvas._shapeIndex.query(rect) == [s for s in canvas.shapes if s.boundingRect().intersects(rect)]
    compare()
    canvas.shapes[0].moveBy(QPointF(1000, 200))
    canvas.shapes[1].rotate(math.pi / 4)
    canvas.shapes[2].points = box(1800, 1900).points
    canvas.shapes[3].points[0] = QPointF(2100, 2200)
    compare()
    canvas.shapes.append(box(1500, 1400))
    canvas.shapes.pop(6)
    canvas.shapes[8:10] = [box(4200, 4300)]
    canvas.shapes.reverse()
    compare()
    canvas.shapes = [box(10, 20)]
    assert canvas._shapeIndex.query(QRectF(0, 0, 100, 100)) == list(canvas.shapes)
    canvas.shapes.clear()
    assert not canvas._shapeIndex.query(QRectF(0, 0, 5000, 5000))


def test_giant_boxes_do_not_allocate_unbounded_grid_cells(app):
    canvas = Canvas()
    giant = box(-1e9, -1e9, 2e9, 2e9)
    tiny = box(10, 10)
    canvas.shapes = [giant, tiny]
    assert canvas._shapeIndex.query(QRectF(0, 0, 100, 100)) == [giant, tiny]
    assert len(canvas._shapeIndex._buckets) <= 4
    assert canvas._shapeIndex.query(QRectF(-1e10, -1e10, 2e10, 2e10)) == [giant, tiny]


def test_sparse_ten_thousand_boxes_only_pick_near_pointer(app, monkeypatch):
    canvas = Canvas()
    canvas.shapes = [box(col * 120, row * 120) for row in range(100) for col in range(100)]
    canvas._shapeIndex.synchronize()
    calls = []
    original = Shape.nearestVertex
    def count(shape, point, epsilon):
        calls.append(shape)
        return original(shape, point, epsilon)
    monkeypatch.setattr(Shape, 'nearestVertex', count)
    for _ in range(100):
        mouse(canvas, QEvent.MouseMove, QPointF(60, 60), Qt.NoButton, Qt.NoButton)
    assert len(calls) <= 400
    assert len(canvas.hitShapes(QPointF(60, 60))) <= 4
    assert len(canvas.shapes) == 10000


def test_point_pick_after_move_delete_replacement_and_visibility_changes(app):
    canvas = Canvas()
    shape = box(100, 100, 200, 100)
    other = box(600, 100, 200, 100)
    canvas.shapes = [shape, other]
    assert canvas.edgeAt(QPointF(200, 100)) == (shape, 0)
    shape.moveBy(QPointF(1000, 0))
    shape.close()
    assert canvas.edgeAt(QPointF(200, 100)) == (None, None)
    assert canvas.edgeAt(QPointF(1200, 100)) == (shape, 0)
    canvas.setShapeVisible(shape, False)
    assert canvas.edgeAt(QPointF(1200, 100)) == (None, None)
    canvas.setShapeVisible(shape, True)
    canvas.shapes.remove(shape)
    assert canvas.edgeAt(QPointF(1200, 100)) == (None, None)
    restored = shape.copy()
    canvas.shapes = [restored]
    assert canvas.edgeAt(QPointF(1200, 100)) == (restored, 0)
    restored.label = 'A much longer new category'
    canvas._shapeIndex.synchronize()
    assert canvas._shapeIndex.maxLabelLength == len(restored.label)


def test_geometry_drag_does_not_recount_or_restyle_whole_list(window):
    prepare(window, (2400, 1800))
    shape = add(window, [(100, 100), (400, 100), (400, 300), (100, 300)])
    with patch.object(window, 'updateAnnotationStats') as recount, patch.object(window.saveStatus, 'setStyleSheet') as restyle:
        drag(window.canvas, QPointF(250, 100), QPointF(250, 70))
        drag(window.canvas, QPointF(250, 200), QPointF(260, 210))
        recount.assert_not_called()
        assert restyle.call_count == 1
    assert window._annotationCounts == {'Bridge': 1} and window.dirty
    assert shape.label == 'Bridge'


def test_paint_does_not_visit_thousands_of_offscreen_boxes(window, monkeypatch):
    prepare(window, (400, 320))
    window.canvas.loadPixmap(QPixmap.fromImage(window.image), QSize(20000, 16000))
    window.setZoom(100)
    shapes = [box(col * 180, row * 150) for row in range(100) for col in range(100)]
    window.canvas.shapes = shapes
    window.centerOnImagePoint(QPointF(250, 250))
    QApplication.processEvents()
    painted = []
    original = Shape.paint
    def paint(shape, painter):
        painted.append(shape)
        return original(shape, painter)
    monkeypatch.setattr(Shape, 'paint', paint)
    window.canvas.update()
    QApplication.processEvents()
    assert painted and len(painted) < 200
    assert len(shapes) == 10000
