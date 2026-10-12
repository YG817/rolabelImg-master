"""Resize one side of either box type, preserving its opposite side and orientation."""
import math
import pytest
from PyQt5.QtCore import QPointF, Qt, QEvent
from PyQt5.QtWidgets import QApplication
from test_interactive_editing import prepare, add, drag, mouse
from box_geometry import validate_box


@pytest.mark.parametrize('angle', [0, 35, 90, 180, 270])
@pytest.mark.parametrize('edge', range(4))
def test_each_edge_moves_perpendicularly_and_keeps_opposite_side(window, angle, edge):
    prepare(window)
    shape = add(window, [(500, 500), (800, 500), (800, 700), (500, 700)], angle != 0)
    shape.rotate(math.radians(angle))
    direction = shape.direction
    before = [QPointF(point) for point in shape.points]
    midpoint = (before[edge] + before[(edge + 1) % 4]) / 2
    vector = before[(edge + 1) % 4] - before[edge]
    length = math.hypot(vector.x(), vector.y())
    normal = QPointF(-vector.y() / length, vector.x() / length)
    window.categoryGrid.setCurrentCell(0, 0)
    mouse(window.canvas, QEvent.MouseMove, midpoint, Qt.NoButton, Qt.NoButton)
    assert window.canvas.hEdge == edge and window.canvas.hShape is shape
    # Tangential pointer motion must not translate or shear the edge.
    drag(window.canvas, midpoint, midpoint + normal * -40 + vector / length * 20)
    for i in range(4):
        expected = before[i] - normal * 40 if i in (edge, (edge + 1) % 4) else before[i]
        assert math.hypot(shape[i].x() - expected.x(), shape[i].y() - expected.y()) < 1e-7
    assert shape.direction == direction and shape.isRotated == (angle != 0)
    assert window.canvas.drawing() and window.canvas.current is None
    assert len(window._undoStack) == 1 and window.dirty
    assert window._annotationCounts == {'Bridge': 1}
    validate_box([(p.x(), p.y()) for p in shape.points])
    window.undoAnnotation()
    assert window.canvas.shapes[0].points == before
    window.redoAnnotation()
    assert window.canvas.shapes[0].points != before


def test_reverse_winding_outside_tolerance_and_edge_boundary_clamping(window):
    prepare(window)
    shape = add(window, [(100, 100), (100, 300), (400, 300), (400, 100)])
    # Eight pixels outside a side remains a resize hit rather than empty-space pan.
    drag(window.canvas, QPointF(92, 200), QPointF(-100, 200))
    assert shape[0].x() == shape[1].x() == 0
    assert shape[2] == QPointF(400, 300) and shape[3] == QPointF(400, 100)
    # Shrinking through the opposite side must not invert or collapse the box.
    drag(window.canvas, QPointF(0, 200), QPointF(600, 200))
    assert 0 < 400 - shape[0].x() < 1e-5
    validate_box([(p.x(), p.y()) for p in shape.points])


def test_locked_hidden_and_corner_regions_keep_their_original_behavior(window):
    prepare(window)
    shape = add(window, [(100, 100), (400, 100), (400, 300), (100, 300)])
    shape.locked = True
    assert window.canvas.edgeAt(QPointF(250, 100)) == (None, None)
    before = list(shape.points)
    drag(window.canvas, QPointF(250, 100), QPointF(250, 70))
    assert shape.points == before and not window.dirty
    shape.locked = False
    window.canvas.setShapeVisible(shape, False)
    assert window.canvas.edgeAt(QPointF(250, 100)) == (None, None)
    window.canvas.setShapeVisible(shape, True)
    drag(window.canvas, QPointF(100, 100), QPointF(80, 80))
    assert shape[0] == QPointF(80, 80) and shape[2] == QPointF(400, 300)
    assert window.canvas._edgeGesture is None


def test_tangential_drag_does_not_create_a_change_or_undo_entry(window):
    prepare(window)
    shape = add(window, [(100, 100), (400, 100), (400, 300), (100, 300)])
    before = list(shape.points)
    drag(window.canvas, QPointF(250, 100), QPointF(270, 100))
    assert shape.points == before and not window.dirty and not window._undoStack


@pytest.mark.parametrize('scale', [0.1, 0.5, 2])
def test_edge_hit_region_keeps_screen_pixel_tolerance(window, scale):
    prepare(window)
    shape = add(window, [(400, 400), (1800, 400), (1800, 1500), (400, 1500)])
    window.canvas.scale = scale
    midpoint = QPointF(1100, 400)
    assert window.canvas.edgeAt(midpoint + QPointF(0, 9 / scale)) == (shape, 0)
    assert window.canvas.edgeAt(midpoint + QPointF(0, 11 / scale)) == (None, None)


def test_right_double_click_near_edge_still_changes_single_label(window, monkeypatch):
    from test_shape_label_editing import right_double_click
    prepare(window)
    shape = add(window, [(100, 100), (400, 100), (400, 300), (100, 300)])
    monkeypatch.setattr(window, 'chooseShapeLabel', lambda shape, editing=False: 'OilTank')
    right_double_click(window.canvas, QPointF(250, 92))
    assert shape.label == 'OilTank' and shape[0] == QPointF(100, 100)
