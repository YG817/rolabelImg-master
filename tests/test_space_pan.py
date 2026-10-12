from unittest.mock import patch
import pytest
from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent
from PyQt5.QtGui import QImage, QPixmap, QMouseEvent, QKeyEvent, QFocusEvent
from PyQt5.QtWidgets import QApplication, QAction
from PyQt5.QtTest import QTest
from shape import Shape


def prepare(window, drawing=False, locked=False):
    window.image = QImage(2400, 1800, QImage.Format_RGB32)
    window.image.fill(Qt.white)
    canvas = window.canvas
    canvas.loadPixmap(QPixmap.fromImage(window.image))
    window.toggleActions(True)
    window.filePath = 'space-pan.png'
    window.setZoom(100)
    QApplication.processEvents()
    shape = Shape('Bridge')
    shape.points = [QPointF(600, 600), QPointF(800, 600), QPointF(800, 800), QPointF(600, 800)]
    shape.close()
    shape.locked = locked
    canvas.shapes = [shape]
    window.addLabel(shape)
    canvas.setEditing(not drawing)
    canvas.selectShape(shape)
    for bar in window.scrollBars.values():
        bar.setValue(300)
    canvas.setFocus()
    return canvas, shape


def mouse(canvas, kind, global_pos, changed=Qt.NoButton, held=Qt.NoButton):
    QApplication.sendEvent(canvas, QMouseEvent(kind, QPointF(canvas.mapFromGlobal(global_pos)),
                                              QPointF(global_pos), changed, held, Qt.NoModifier))


@pytest.mark.parametrize('drawing,locked', [(False, False), (False, True), (True, False), (True, True)])
def test_hold_space_pans_over_boxes_and_restores_mode(window, drawing, locked):
    canvas, shape = prepare(window, drawing, locked)
    points = list(shape.points)
    original_mode = canvas.mode
    position = ((QPointF(700, 700) + canvas.offsetToCenter()) * canvas.scale).toPoint()
    global_pos = canvas.mapToGlobal(position)
    with patch.object(window, 'saveFile') as save:
        QTest.keyPress(canvas, Qt.Key_Space)
        assert canvas._spacePanHeld
        assert canvas.cursor().shape() == Qt.OpenHandCursor
        mouse(canvas, QEvent.MouseButtonPress, global_pos, Qt.LeftButton, Qt.LeftButton)
        assert canvas.cursor().shape() == Qt.ClosedHandCursor
        mouse(canvas, QEvent.MouseMove, global_pos + QPoint(50, 30), held=Qt.LeftButton)
        mouse(canvas, QEvent.MouseButtonRelease, global_pos + QPoint(50, 30), Qt.LeftButton)
        assert canvas.cursor().shape() == Qt.OpenHandCursor
        QTest.keyRelease(canvas, Qt.Key_Space)
        save.assert_not_called()
    assert window.scrollBars[Qt.Horizontal].value() == 250
    assert window.scrollBars[Qt.Vertical].value() == 270
    assert shape.points == points and canvas.selectedShape is shape
    assert len(canvas.shapes) == 1 and canvas.current is None
    assert not window.dirty and not canvas.verified
    assert canvas.mode == original_mode and not canvas._spacePanHeld
    assert canvas._cursor == (Qt.CrossCursor if drawing else Qt.ArrowCursor)


def test_releasing_space_before_mouse_cannot_draw_or_edit(window):
    canvas, shape = prepare(window, drawing=True)
    points = list(shape.points)
    start = canvas.mapToGlobal(((QPointF(700, 700) + canvas.offsetToCenter()) * canvas.scale).toPoint())
    QTest.keyPress(canvas, Qt.Key_Space)
    mouse(canvas, QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
    QTest.keyRelease(canvas, Qt.Key_Space)
    mouse(canvas, QEvent.MouseMove, start + QPoint(20, 10), held=Qt.LeftButton)
    mouse(canvas, QEvent.MouseButtonRelease, start + QPoint(20, 10), Qt.LeftButton)
    assert not canvas._spacePanHeld and not canvas._spacePanSuppressMouse
    assert shape.points == points and canvas.current is None and not window.dirty
    # A new mouse press resumes normal box editing.
    local = (QPointF(700, 700) + canvas.offsetToCenter()) * canvas.scale
    mouse(canvas, QEvent.MouseButtonPress, canvas.mapToGlobal(local.toPoint()), Qt.LeftButton, Qt.LeftButton)
    assert canvas._editingGesture
    mouse(canvas, QEvent.MouseButtonRelease, canvas.mapToGlobal(local.toPoint()), Qt.LeftButton)


def test_space_repeat_focus_loss_and_list_focus(window):
    canvas, shape = prepare(window)
    window.labelList.setFocus()
    QTest.keyPress(window.labelList, Qt.Key_Space)
    assert canvas.hasFocus() and canvas._spacePanHeld
    for kind in (QEvent.KeyRelease, QEvent.KeyPress):
        QApplication.sendEvent(canvas, QKeyEvent(kind, Qt.Key_Space, Qt.NoModifier, ' ', True))
        assert canvas._spacePanHeld
    QApplication.sendEvent(canvas, QFocusEvent(QEvent.FocusOut))
    assert not canvas._spacePanHeld and canvas._panButton == Qt.NoButton
    canvas.resetState()
    assert not canvas._spacePanHeld


def test_space_is_text_in_input_and_no_longer_save_shortcut(window):
    canvas, shape = prepare(window)
    assert all(action.shortcut().toString() != 'Space' for action in window.findChildren(QAction))
    window.centerCoordinates.setReadOnly(False)
    window.centerCoordinates.setFocus()
    QTest.keyClicks(window.centerCoordinates, 'a b')
    assert window.centerCoordinates.text() == 'a b'
    assert not canvas._spacePanHeld and not window.dirty
    window.centerCoordinates.setReadOnly(True)
    QTest.keyPress(window.centerCoordinates, Qt.Key_Space)
    assert canvas._spacePanHeld
    QTest.keyRelease(canvas, Qt.Key_Space)


def test_space_pan_over_rotated_handle_preserves_box(window):
    canvas, shape = prepare(window, drawing=True)
    shape.isRotated = True
    points = list(shape.points)
    handle = canvas.rotationHandle(shape)
    start = canvas.mapToGlobal(((handle + canvas.offsetToCenter()) * canvas.scale).toPoint())
    QTest.keyPress(canvas, Qt.Key_Space)
    mouse(canvas, QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
    mouse(canvas, QEvent.MouseMove, start + QPoint(35, 25), held=Qt.LeftButton)
    mouse(canvas, QEvent.MouseButtonRelease, start + QPoint(35, 25), Qt.LeftButton)
    QTest.keyRelease(canvas, Qt.Key_Space)
    assert shape.points == points and not window.dirty
    assert window.scrollBars[Qt.Horizontal].value() == 265


def test_pressing_space_during_box_drag_stops_geometry_edits(window):
    canvas, shape = prepare(window)
    start = canvas.mapToGlobal(((QPointF(700, 700) + canvas.offsetToCenter()) * canvas.scale).toPoint())
    mouse(canvas, QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
    assert canvas._editingGesture
    QTest.keyPress(canvas, Qt.Key_Space)
    points = list(shape.points)
    mouse(canvas, QEvent.MouseMove, start + QPoint(20, 15), held=Qt.LeftButton)
    mouse(canvas, QEvent.MouseButtonRelease, start + QPoint(20, 15), Qt.LeftButton)
    QTest.keyRelease(canvas, Qt.Key_Space)
    assert shape.points == points and not window.dirty
    assert window.scrollBars[Qt.Horizontal].value() == 280
