import pytest
from PyQt5.QtCore import Qt, QPoint, QPointF
from PyQt5.QtGui import QImage, QPixmap, QWheelEvent
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
from view_layout import ResponsiveRow


def prepare(window, size=(120, 80)):
    window.image = QImage(*size, QImage.Format_RGB32)
    window.image.fill(Qt.white)
    window.canvas.loadPixmap(QPixmap.fromImage(window.image))
    window.filePath = 'navigation.png'
    window.toggleActions(True)
    window.setZoom(100)
    window.centerOnImagePoint(QPointF(size[0] / 2, size[1] / 2))
    QApplication.processEvents()


@pytest.mark.parametrize('size,zoom', [((120, 80), 20), ((2400, 1800), 150)])
def test_both_scrollbars_move_small_and_large_images_at_all_edges(window, size, zoom):
    prepare(window, size)
    window.setZoom(zoom)
    QApplication.processEvents()
    viewport = window.centralWidget().viewport()
    for orientation in (Qt.Horizontal, Qt.Vertical):
        bar = window.scrollBars[orientation]
        assert bar.isVisible() and bar.maximum() > 0
        positions = []
        for value in (bar.minimum(), bar.maximum()):
            bar.setValue(value)
            origin = window.canvas.transformPos(QPointF(window.canvas.mapFrom(viewport, QPoint())))
            positions.append(origin.x() if orientation == Qt.Horizontal else origin.y())
        assert positions[0] < 0
        assert positions[1] >= (size[0] if orientation == Qt.Horizontal else size[1])
        bar.setValue(bar.maximum() // 2)
        before = bar.value()
        window.scrollRequest(120, orientation)
        assert bar.value() < before
    assert window.canvas.viewOffset.isNull()


def test_shift_wheel_scrolls_horizontally(window):
    prepare(window)
    horizontal = window.scrollBars[Qt.Horizontal]
    vertical = window.scrollBars[Qt.Vertical]
    before = horizontal.value(), vertical.value()
    event = QWheelEvent(QPointF(100, 100), QPointF(100, 100), QPoint(), QPoint(0, 120),
                        Qt.NoButton, Qt.ShiftModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(window.canvas, event)
    assert horizontal.value() < before[0]
    assert vertical.value() == before[1]


def test_inspection_restore_original_and_fit_preserve_annotations(window):
    prepare(window, (2400, 1800))
    window.showInspection()
    dialog = window._inspectionDialog
    dialog.selectRegion(4)
    QApplication.processEvents()
    dialog.originalSizeButton.click()
    QApplication.processEvents()
    assert window.zoomWidget.value() == 100
    viewport = window.centralWidget().viewport()
    center = window.canvas.transformPos(QPointF(window.canvas.mapFrom(viewport, viewport.rect().center())))
    assert center.x() == pytest.approx(1200, abs=1)
    assert center.y() == pytest.approx(900, abs=1)
    dialog.fitButton.click()
    QApplication.processEvents()
    assert window.canvas.imageSize.width() * window.canvas.scale <= viewport.width() + 1
    assert window.canvas.imageSize.height() * window.canvas.scale <= viewport.height() + 1
    assert not window.dirty and not dialog.overview.completed
    dialog.close()


def test_narrow_docks_reflow_and_resizing_updates_workspace(window):
    prepare(window)
    window.labelStore.ensure('first')
    window.labelStore.ensure('second')
    window.refreshLabelLibrary()
    window.resizeDocks([window.dock], [500], Qt.Horizontal)
    QApplication.processEvents()
    assert window.categoryGrid.columnCount() == 2
    window.categoryGrid.setCurrentCell(0, 1)
    selected = window.selectedCategory()['id']
    window.resizeDocks([window.dock], [200], Qt.Horizontal)
    QApplication.processEvents()
    assert window.dock.width() < 290
    assert window.filedock.width() < 290
    assert window.categoryGrid.columnCount() == 1
    assert window.selectedCategory()['id'] == selected
    for row in window.dock.findChildren(ResponsiveRow):
        assert row.width() <= window.dock.width()
    assert window.canvas.viewportSize == window.centralWidget().viewport().size()


def test_resizing_dock_preserves_manual_view_center(window):
    prepare(window, (2400, 1800))
    window.centerOnImagePoint(QPointF(900, 700))
    QApplication.processEvents()
    window.resizeDocks([window.dock], [200], Qt.Horizontal)
    QTest.qWait(20)
    viewport = window.centralWidget().viewport()
    center = window.canvas.transformPos(QPointF(window.canvas.mapFrom(viewport, viewport.rect().center())))
    assert center.x() == pytest.approx(900, abs=2)
    assert center.y() == pytest.approx(700, abs=2)
