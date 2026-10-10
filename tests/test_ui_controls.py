import pytest
from PyQt5.QtCore import QPoint, QPointF, Qt
from PyQt5.QtGui import QImage, QWheelEvent
from PyQt5.QtWidgets import QApplication, QTextBrowser, QAction


def prepare_image(window):
    window.image = QImage(640, 480, QImage.Format_RGB32)
    window.image.fill(Qt.white)
    from PyQt5.QtGui import QPixmap
    window.canvas.loadPixmap(QPixmap.fromImage(window.image))
    window.toggleActions(True)
    window.setZoom(100)


def test_ctrl_wheel_relative_steps_and_bounds(window):
    prepare_image(window)
    event = QWheelEvent(QPointF(100, 100), QPointF(100, 100), QPoint(), QPoint(0, 120),
                        Qt.NoButton, Qt.ControlModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(window.canvas, event)
    assert window.zoomWidget.value() == 115
    window.zoomRequest(-120)
    assert window.zoomWidget.value() == 100
    window.zoomRequest(60)
    assert window.zoomWidget.value() == pytest.approx(100 * 1.15 ** 0.5, abs=0.01)
    window.setZoom(500)
    window.zoomRequest(120)
    assert window.zoomWidget.value() == 500
    window.setZoom(0.01)
    window.zoomRequest(-120)
    assert window.zoomWidget.value() == pytest.approx(0.01)


def test_zoom_toolbar_and_help(window):
    prepare_image(window)
    window.actions.zoomIn.trigger()
    assert window.zoomWidget.value() == 115
    window.actions.zoomOut.trigger()
    assert window.zoomWidget.value() == 100
    window.guideAction.trigger()
    assert window._guideDialog.isVisible()
    assert 'Ctrl+Shift+P' in '\n'.join(b.toPlainText() for b in window._guideDialog.findChildren(QTextBrowser))
    assert not window._guideDialog.isModal()
    window._guideDialog.close()


def test_no_duplicate_shortcuts(window):
    shortcuts = [a.shortcut().toString() for a in window.findChildren(QAction) if not a.shortcut().isEmpty()]
    assert len(shortcuts) == len(set(shortcuts))
