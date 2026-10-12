"""Empty image zoom and real divider gestures must keep the workspace usable."""
import sys
import pytest
from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent, QCoreApplication
from PyQt5.QtGui import QWheelEvent, QMouseEvent, QHoverEvent
from PyQt5.QtWidgets import QApplication, QToolButton
from PyQt5.QtTest import QTest, QSignalSpy
from conftest import wait_until
from test_workspace_navigation import prepare
from test_popup_controls import enable_offscreen_fonts


@pytest.mark.parametrize('state', ['startup', 'closed', 'loading'])
def test_ctrl_wheel_without_image_never_raises_or_changes_zoom(window, monkeypatch, state):
    errors = []
    monkeypatch.setattr(sys, 'excepthook', lambda *args: errors.append(args))
    if state == 'closed':
        prepare(window)
        window.resetState()
    elif state == 'loading':
        window.resetState()
        window._loading = True
    before = window.zoomWidget.value()
    spy = QSignalSpy(window.canvas.zoomRequest)
    for delta in (120, -120, 360, -360, 15):
        event = QWheelEvent(QPointF(100, 100), QPointF(window.canvas.mapToGlobal(QPoint(100, 100))),
                            QPoint(), QPoint(0, delta), Qt.NoButton, Qt.ControlModifier,
                            Qt.NoScrollPhase, False)
        QApplication.sendEvent(window.canvas, event)
        window.zoomRequest(delta)
    window.setZoom(200)
    window.setFitWindow()
    window.setFitWidth()
    window.adjustScale()
    window.paintCanvas()
    QApplication.processEvents()
    assert window.zoomWidget.value() == before and not errors and not spy
    assert window.isVisible() and window.image.isNull() and window.canvas.zoomAnchor is None
    # A queued/programmatic valueChanged after closing also cannot crash.
    window.zoomWidget.setValue(before + 1)
    QApplication.processEvents()
    assert not errors
    window._loading = False


def test_ctrl_wheel_still_zooms_loaded_image(window):
    prepare(window, (2400, 1800))
    global_pos = window.centralWidget().viewport().mapToGlobal(QPoint(140, 120))
    anchor = window.canvas.mapFromGlobal(global_pos)
    before = window.canvas.transformPos(anchor)
    event = QWheelEvent(QPointF(anchor), QPointF(global_pos), QPoint(), QPoint(0, 120),
                        Qt.NoButton, Qt.ControlModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(window.canvas, event)
    QApplication.processEvents()
    assert window.zoomWidget.value() == pytest.approx(115)
    after = window.canvas.transformPos(window.canvas.mapFromGlobal(global_pos))
    assert abs(after.x() - before.x()) * window.canvas.scale < 1.1
    assert abs(after.y() - before.y()) * window.canvas.scale < 1.1


def drag_widget(widget, start, end):
    QApplication.sendEvent(widget, QHoverEvent(QEvent.HoverMove, QPointF(start), QPointF(start - QPoint(1, 0))))
    QTest.mouseMove(widget, start)
    QTest.mousePress(widget, Qt.LeftButton, pos=start)
    event = QMouseEvent(QEvent.MouseMove, QPointF(end), QPointF(widget.mapToGlobal(end)),
                        Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, event)
    # Dock resizing applies the pointer movement through a zero-delay Qt timer.
    QApplication.processEvents()
    QTest.mouseRelease(widget, Qt.LeftButton, pos=end)
    QApplication.processEvents()


def test_tool_dock_real_drag_collapses_to_icons_and_expands(window):
    enable_offscreen_fonts()
    prepare(window, (2400, 1800))
    window.resizeDocks([window.toolsDock], [150], Qt.Horizontal)
    QApplication.processEvents()
    before = window.toolsDock.width()
    # QMainWindow owns the resize strip immediately beside the dock.
    edge = window.toolsDock.geometry().right() + 4
    point = QPoint(edge, window.toolsDock.geometry().center().y())
    drag_widget(window, point, point - QPoint(90, 0))
    assert 58 <= window.toolsDock.width() < before
    assert window.tools._compact and not window.zoomWidget.isVisible()
    buttons = [b for b in window.tools.findChildren(QToolButton) if b.defaultAction()]
    assert buttons and all(b.toolButtonStyle() == Qt.ToolButtonIconOnly for b in buttons)
    assert all(b.toolTip() for b in buttons)
    # Open remains clickable while it has no text.
    window.actions.open.triggered.disconnect()
    spy = QSignalSpy(window.actions.open.triggered)
    QTest.mouseClick(next(b for b in buttons if b.defaultAction() is window.actions.open), Qt.LeftButton)
    assert len(spy) == 1
    edge = window.toolsDock.geometry().right() + 4
    point = QPoint(edge, window.toolsDock.geometry().center().y())
    drag_widget(window, point, point + QPoint(100, 0))
    assert window.toolsDock.width() >= 112
    assert not window.tools._compact and window.zoomWidget.isVisible()
    assert all(b.toolButtonStyle() == Qt.ToolButtonTextBesideIcon for b in buttons)


@pytest.mark.parametrize('index', [1, 2])
def test_right_section_handles_resize_without_losing_controls(window, index):
    splitter = window.rightSplitter
    splitter.setSizes([220, 260, 160])
    QApplication.processEvents()
    before = splitter.sizes()
    handle = splitter.handle(index)
    drag_widget(handle, handle.rect().center(), handle.rect().center() + QPoint(0, 35))
    after = splitter.sizes()
    assert after[index - 1] > before[index - 1]
    assert after[index] < before[index]
    assert all(size >= 72 for size in after)
    assert window.categoryGrid.isVisible() and window.labelList.isVisible()
    assert window.formatCombo.isVisible() and window.centerCoordinates.isVisible()
    assert window.annotationCountLabel.isVisible()
    assert window.fileListWidget.isVisible()


def test_navigation_keeps_icons_and_text_and_actions_clickable(window):
    enable_offscreen_fonts()
    bar = window.menuBar()
    QApplication.processEvents()
    assert [a.text() for a in bar.actions()] == ['文件', '编辑', '视图', '操作说明', '版本与更新']
    for action in bar.actions():
        assert not action.icon().isNull()
        assert bar.actionGeometry(action).width() >= bar.fontMetrics().horizontalAdvance(action.text()) + 44
    QTest.mouseClick(bar, Qt.LeftButton, pos=bar.actionGeometry(window.menus.file.menuAction()).center())
    assert window.menus.file.isVisible()
    window.menus.file.close()
    QTest.mouseClick(bar, Qt.LeftButton, pos=bar.actionGeometry(window.guideAction).center())
    assert window._guideDialog.isVisible()
    window._guideDialog.close()
    QTest.mouseClick(bar, Qt.LeftButton, pos=bar.actionGeometry(window.updateAction).center())
    assert window.updater.settingsDialog.isVisible()
    window.updater.settingsDialog.close()


def test_image_list_boundary_can_be_dragged_vertically(window):
    before = window.filedock.height()
    edge = window.filedock.geometry().top() - 4
    point = QPoint(window.filedock.geometry().center().x(), edge)
    drag_widget(window, point, point - QPoint(0, 35))
    assert window.filedock.height() > before
    assert all(size >= 72 for size in window.rightSplitter.sizes())
    assert window.fileListWidget.isVisible() and window.annotationCountLabel.isVisible()


def test_layout_sizes_survive_restart(window):
    window.resizeDocks([window.toolsDock], [68], Qt.Horizontal)
    window.resizeDocks([window.dock, window.filedock], [500, 180], Qt.Vertical)
    window.rightSplitter.setSizes([200, 280, 100])
    QApplication.processEvents()
    width = window.toolsDock.width()
    sizes = window.rightSplitter.sizes()
    file_height = window.filedock.height()
    window.close()
    restarted = type(window)()
    try:
        restarted.show()
        QApplication.processEvents()
        assert abs(restarted.toolsDock.width() - width) <= 2
        assert restarted.tools._compact
        restored = restarted.rightSplitter.sizes()
        assert all(abs(a / sum(sizes) - b / sum(restored)) < 0.03 for a, b in zip(sizes, restored))
        assert abs(restarted.filedock.height() - file_height) <= 4
    finally:
        restarted.dirty = False
        restarted.close()
        wait_until(lambda: not restarted._workers)
        restarted.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.mark.parametrize('width', [420, 240])
@pytest.mark.parametrize('section', [0, 1, 2])
def test_vertical_section_resize_keeps_controls_at_top_and_grows_content(window, section, width):
    from PyQt5.QtWidgets import QLabel
    from view_layout import ResponsiveRow
    window.resize(1280, 1250)
    window.resizeDocks([window.dock], [width], Qt.Horizontal)
    window.resizeDocks([window.dock, window.filedock], [1050, 100], Qt.Vertical)
    QApplication.processEvents()
    area = window.rightSplitter.widget(section)
    panel = area.widget()
    controls = panel.findChildren(ResponsiveRow) + [w for w in panel.findChildren(QLabel)
                                                   if isinstance(w.parentWidget(), type(panel))]
    assert controls
    def snapshot():
        return [(w.mapTo(panel, QPoint()).y(), w.height()) for w in controls]
    heights = [260, 260, 260]
    heights[section] = 220
    window.rightSplitter.setSizes(heights)
    QApplication.processEvents()
    first = snapshot()
    first_columns = window.categoryGrid.columnCount()
    content = window.categoryGrid if section == 0 else window.labelList if section == 1 else None
    before_content = content.height() if content is not None else None
    before_height = panel.height()
    heights[section] = 600
    window.rightSplitter.setSizes(heights)
    QApplication.processEvents()
    assert panel.height() > before_height
    assert snapshot() == first
    assert window.categoryGrid.columnCount() == first_columns
    assert min(y for y, height in first) <= 14
    if content is not None:
        assert content.height() > before_content
    else:
        # Extra export-space stays below the coordinate controls.
        last_row = panel.findChildren(ResponsiveRow)[-1]
        assert last_row.geometry().bottom() < panel.height() - 100


@pytest.mark.parametrize('font_size', [13, 20])
def test_tool_width_stops_at_full_content_and_does_not_clip_labels(window, font_size):
    window.tools.setStyleSheet('QToolButton { font-size: %dpx; }' % font_size)
    window.constrainToolsWidth()
    cap = window.toolsDock.maximumWidth()
    window.resizeDocks([window.toolsDock], [cap + 200], Qt.Horizontal)
    QApplication.processEvents()
    assert window.toolsDock.width() == cap and not window.tools._compact
    assert cap == window.tools._expandedWidth
    buttons = window.tools.activeButtons()
    assert all(button.sizeHint().width() <= window.tools.width() for button in buttons)
    assert all(button.geometry().right() < window.tools.width() for button in buttons if button.isVisible())
    # Growing the window does not reintroduce a blank strip beside the tools.
    window.resize(1600, 1000)
    QApplication.processEvents()
    assert window.toolsDock.width() <= cap


def test_saved_oversized_tool_width_is_clamped_on_startup(window):
    window.settings['window/toolsWidth'] = 260
    restarted = type(window)()
    try:
        restarted.show()
        QApplication.processEvents()
        assert restarted.toolsDock.width() == restarted.toolsDock.maximumWidth()
        assert restarted.toolsDock.width() < 260
        assert not restarted.tools._compact
    finally:
        restarted.dirty = False
        restarted.close()
        wait_until(lambda: not restarted._workers)
        restarted.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
