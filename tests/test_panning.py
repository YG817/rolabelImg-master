import pytest
from PyQt5.QtCore import QPoint, QPointF, Qt, QEvent
from PyQt5.QtGui import QImage, QPixmap, QMouseEvent, QFocusEvent
from PyQt5.QtWidgets import QApplication
from shape import Shape


@pytest.mark.parametrize('button,modifiers,drawing', [
    (Qt.MiddleButton, Qt.NoModifier, False),
    (Qt.LeftButton, Qt.AltModifier, False),
    (Qt.LeftButton, Qt.NoModifier, False),
    (Qt.MiddleButton, Qt.NoModifier, True),
    (Qt.LeftButton, Qt.AltModifier, True),
])
def test_pan_preserves_annotations(window, button, modifiers, drawing):
    window.image = QImage(2400, 1800, QImage.Format_RGB32)
    window.image.fill(Qt.white)
    canvas = window.canvas
    canvas.loadPixmap(QPixmap.fromImage(window.image))
    window.setZoom(100)
    window.paintCanvas()
    QApplication.processEvents()
    for bar in window.scrollBars.values():
        bar.setValue(300)
    shape = Shape('test')
    shape.points = [QPointF(600, 600), QPointF(800, 600), QPointF(800, 800), QPointF(600, 800)]
    shape.close()
    canvas.shapes = [shape]
    window.addLabel(shape)
    canvas.selectShape(shape)
    canvas.setEditing(not drawing)
    before = list(shape.points)
    position = QPoint(1000, 1000) if button == Qt.LeftButton and not modifiers else QPoint(700, 700)
    global_pos = canvas.mapToGlobal(position)

    def event(kind, point, changed, held):
        return QMouseEvent(kind, QPointF(canvas.mapFromGlobal(point)), QPointF(point), changed, held, modifiers)

    QApplication.sendEvent(canvas, event(QEvent.MouseButtonPress, global_pos, button, button))
    assert canvas._panButton == button
    for i in (1, 2):
        QApplication.sendEvent(canvas, event(QEvent.MouseMove, global_pos + QPoint(25*i, 15*i), Qt.NoButton, button))
    assert window.scrollBars[Qt.Horizontal].value() == 250
    assert window.scrollBars[Qt.Vertical].value() == 270
    QApplication.sendEvent(canvas, event(QEvent.MouseButtonRelease, global_pos + QPoint(50, 30), button, Qt.NoButton))
    assert canvas._panButton == Qt.NoButton
    assert shape.points == before
    assert len(canvas.shapes) == 1 and canvas.current is None
    assert not window.dirty


def test_pan_clamps_and_cancels_on_focus_loss(window):
    for bar in window.scrollBars.values():
        bar.setRange(0, 100)
        bar.setValue(50)
    window.panImage(1000, -1000)
    assert window.scrollBars[Qt.Horizontal].value() == 0
    assert window.scrollBars[Qt.Vertical].value() == 100
    window.canvas._panButton = Qt.MiddleButton
    window.canvas._panGlobalPos = QPoint(20, 20)
    window.canvas.focusOutEvent(QFocusEvent(QEvent.FocusOut))
    assert window.canvas._panButton == Qt.NoButton
    assert window.canvas._panGlobalPos is None
