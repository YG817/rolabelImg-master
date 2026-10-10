"""Real mouse gestures covering drawing, editing, deletion, undo and zoom anchors."""
import math
import pytest
from PyQt5.QtCore import QPoint, QPointF, Qt, QEvent, QTimer
from PyQt5.QtGui import QImage, QPixmap, QMouseEvent, QColor
from PyQt5.QtWidgets import QApplication, QDialog, QComboBox
from PyQt5.QtTest import QTest
from shape import Shape


def prepare(window):
    window.image = QImage(2400, 1800, QImage.Format_RGB32)
    window.image.fill(Qt.white)
    window.canvas.loadPixmap(QPixmap.fromImage(window.image))
    window.filePath = 'test.png'
    window.toggleActions(True)
    window.setZoom(100)
    QApplication.processEvents()


def add(window, points, rotated=False):
    shape = Shape('Bridge')
    shape.points = [QPointF(*p) for p in points]
    shape.isRotated = rotated
    shape.close()
    window.canvas.shapes.append(shape)
    window.addLabel(shape)
    return shape


def mouse(canvas, kind, point, button, buttons):
    local = (point + canvas.offsetToCenter()) * canvas.scale
    event = QMouseEvent(kind, local, QPointF(canvas.mapToGlobal(local.toPoint())),
                        button, buttons, Qt.NoModifier)
    QApplication.sendEvent(canvas, event)


def drag(canvas, start, end):
    mouse(canvas, QEvent.MouseMove, start, Qt.NoButton, Qt.NoButton)
    mouse(canvas, QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
    mouse(canvas, QEvent.MouseMove, end, Qt.NoButton, Qt.LeftButton)
    mouse(canvas, QEvent.MouseButtonRelease, end, Qt.LeftButton, Qt.NoButton)


def test_edit_existing_boxes_during_continuous_drawing(window):
    prepare(window)
    canvas = window.canvas
    shape = add(window, [(100, 100), (200, 100), (200, 200), (100, 200)], True)
    window.categoryGrid.setCurrentCell(0, 0)
    assert canvas.drawing() and canvas.canDrawRotatedRect
    drag(canvas, QPointF(100, 100), QPointF(80, 80))
    assert shape[0] == QPointF(80, 80)
    assert len(canvas.shapes) == 1 and canvas.current is None
    before = [QPointF(p) for p in shape.points]
    drag(canvas, QPointF(140, 140), QPointF(160, 170))
    assert shape[0] == before[0] + QPointF(20, 30)
    handle = canvas.rotationHandle(shape)
    target = shape.center + QPointF(80, 0)
    drag(canvas, handle, target)
    assert not math.isclose(shape.direction, 0)
    assert canvas.drawing() and len(canvas.shapes) == 1
    window.undoAnnotation()
    assert window.canvas.shapes[0].direction == 0
    window.undoAnnotation()
    assert window.canvas.shapes[0][0] == QPointF(80, 80)
    window.undoAnnotation()
    assert window.canvas.shapes[0][0] == QPointF(100, 100)


def test_tiny_box_selection_multi_delete_and_undo(window):
    prepare(window)
    canvas = window.canvas
    tiny = add(window, [(100, 100), (101, 100), (101, 101), (100, 101)])
    other = add(window, [(250, 250), (350, 250), (350, 350), (250, 350)])
    window.categoryGrid.setCurrentCell(0, 0)
    mouse(canvas, QEvent.MouseButtonPress, QPointF(105, 104), Qt.LeftButton, Qt.LeftButton)
    mouse(canvas, QEvent.MouseButtonRelease, QPointF(105, 104), Qt.LeftButton, Qt.NoButton)
    assert canvas.selectedShape is tiny
    assert window.deleteSelectedButton.isEnabled()
    window.deleteSelectedButton.click()
    assert canvas.shapes == [other]
    window.undoAnnotation()
    assert len(canvas.shapes) == 2
    window.labelList.item(0).setSelected(True)
    window.labelList.item(1).setSelected(True)
    assert len(window.labelList.selectedItems()) == 2
    window.deleteSelectedButton.click()
    assert not canvas.shapes and window.labelList.count() == 0
    window.undoAnnotation()
    assert len(canvas.shapes) == 2 and window.labelList.count() == 2


def test_category_toggle_and_post_draw_label_popup(window, monkeypatch):
    prepare(window)
    window.labelStore.ensure('Bridge')
    window.refreshLabelLibrary()
    grid = window.categoryGrid
    point = grid.visualItemRect(grid.item(0, 0)).center()
    QTest.mouseClick(grid.viewport(), Qt.LeftButton, pos=point)
    assert window.selectedCategory()['name'] == 'Bridge'
    assert window._activeDraw == 'rotated'
    QTest.mouseClick(grid.viewport(), Qt.LeftButton, pos=point)
    assert window.selectedCategory() is None and window.canvas.editing()
    window.actions.create.trigger()
    monkeypatch.setattr(window, 'chooseShapeLabel', lambda shape: 'NewClass')
    drag(window.canvas, QPointF(200, 200), QPointF(300, 300))
    assert window.canvas.shapes[-1].label == 'NewClass'
    assert window.selectedCategory() is None and window.canvas.drawing()
    assert not window.canvas.shapes[-1].isRotated
    monkeypatch.setattr(window, 'chooseShapeLabel', lambda shape: None)
    drag(window.canvas, QPointF(400, 400), QPointF(500, 500))
    assert len(window.canvas.shapes) == 1
    window.canvas.setFocus()
    QTest.keyClick(window.canvas, Qt.Key_Z, Qt.ControlModifier)
    assert not window.canvas.shapes


def test_popup_accepts_typed_label(window):
    prepare(window)
    shape = add(window, [(100, 100), (200, 100), (200, 200), (100, 200)])
    def accept():
        dialog = QApplication.activeModalWidget() or QApplication.activePopupWidget()
        assert isinstance(dialog, QDialog)
        dialog.findChild(QComboBox).setEditText('NewLabel')
        dialog.accept()
    QTimer.singleShot(50, accept)
    assert window.chooseShapeLabel(shape) == 'NewLabel'


def test_rotation_handle_does_not_fill_following_boxes_white(window):
    prepare(window)
    background = QColor(35, 45, 55)
    window.image.fill(background)
    window.canvas.loadPixmap(QPixmap.fromImage(window.image))
    first = add(window, [(50, 50), (450, 50), (450, 450), (50, 450)], True)
    second = add(window, [(700, 50), (1100, 50), (1100, 450), (700, 450)], True)
    window.canvas.selectShape(first)
    window.setFitWindow()
    QApplication.processEvents()
    for _ in range(2):
        rendered = window.canvas.grab().toImage()
        point = ((QPointF(800, 150) + window.canvas.offsetToCenter()) * window.canvas.scale).toPoint()
        assert rendered.pixelColor(point) == background
    window.canvas.selectShape(second)
    rendered = window.canvas.grab().toImage()
    point = ((QPointF(150, 150) + window.canvas.offsetToCenter()) * window.canvas.scale).toPoint()
    assert rendered.pixelColor(point) == background


@pytest.mark.parametrize('initial,target', [(100, 101), (100, 70), (10, 11), (20, 40)])
def test_zoom_keeps_pointer_image_coordinate(window, initial, target):
    prepare(window)
    window.setZoom(initial)
    QApplication.processEvents()
    viewport = window.centralWidget().viewport()
    anchor = QPoint(180, 160)
    window.canvas.zoomAnchor = viewport.mapToGlobal(anchor)
    before = window.canvas.transformPos(window.canvas.mapFromGlobal(window.canvas.zoomAnchor))
    window.setZoom(target)
    QApplication.processEvents()
    after = window.canvas.transformPos(window.canvas.mapFromGlobal(window.canvas.zoomAnchor))
    assert abs(after.x() - before.x()) * window.canvas.scale < 1.1
    assert abs(after.y() - before.y()) * window.canvas.scale < 1.1
    window.canvas.zoomAnchor = None
