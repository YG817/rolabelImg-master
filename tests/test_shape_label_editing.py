"""Right double clicks relabel exactly one box without starting a drag or drawing."""
import math
import pytest
from PyQt5.QtCore import QPointF, QEvent, Qt, QTimer
from PyQt5.QtWidgets import QApplication, QDialogButtonBox
from PyQt5.QtGui import QColor
from shape_label_dialog import ShapeLabelDialog
from test_interactive_editing import prepare, add, mouse


def right_double_click(canvas, point):
    mouse(canvas, QEvent.MouseButtonPress, point, Qt.RightButton, Qt.RightButton)
    mouse(canvas, QEvent.MouseButtonRelease, point, Qt.RightButton, Qt.NoButton)
    mouse(canvas, QEvent.MouseButtonDblClick, point, Qt.RightButton, Qt.RightButton)
    mouse(canvas, QEvent.MouseButtonRelease, point, Qt.RightButton, Qt.NoButton)


@pytest.mark.parametrize('mode', ['edit', 'normal', 'rotated', 'region'])
@pytest.mark.parametrize('rotated', [False, True])
def test_right_double_click_edits_one_box_and_preserves_tool(window, monkeypatch, mode, rotated):
    prepare(window)
    first = add(window, [(100, 100), (200, 100), (200, 200), (100, 200)], rotated)
    other = add(window, [(400, 100), (500, 100), (500, 200), (400, 200)])
    window.labelStore.ensure('OilTank')
    window.refreshLabelLibrary()
    if mode in ('normal', 'rotated'):
        window.categoryGrid.setCurrentCell(0, 0)
        (window.actions.create if mode == 'normal' else window.actions.createRo).trigger()
    elif mode == 'region':
        window.actions.selectRegion.trigger()
    before_mode = window.canvas.mode
    before_tool = window._activeDraw
    before_category = window.selectedCategory()
    before_points = [QPointF(p) for p in first.points]
    window.selectRegionAnnotations([first, other])
    calls = []
    def choose(shape, editing=False):
        calls.append((shape, editing))
        return 'OilTank'
    monkeypatch.setattr(window, 'chooseShapeLabel', choose)
    # Any context menu would block the double click, so make it a test failure.
    for menu in window.canvas.menus:
        monkeypatch.setattr(menu, 'exec_', lambda *args: pytest.fail('Unexpected context menu'))
    right_double_click(window.canvas, QPointF(150, 150))
    assert calls == [(first, True)]
    assert first.label == 'OilTank' and other.label == 'Bridge'
    assert first.points == before_points and first.isRotated == rotated
    entry = next(e for e in window.labelStore.entries if e['name'] == 'OilTank')
    assert first.line_color.name() == QColor(entry['color']).name()
    assert window.shapesToItems[first].text() == 'OilTank'
    assert window._annotationCounts == {'OilTank': 1, 'Bridge': 1}
    assert len(window._undoStack) == 1 and window.dirty
    assert len(window.labelList.selectedItems()) == 1
    assert window.canvas.mode == before_mode and window._activeDraw == before_tool
    assert window.selectedCategory() == before_category
    assert window.canvas.current is None and len(window.canvas.shapes) == 2
    assert not window.canvas._editingGesture and not window.canvas._rotatingGesture
    window.undoAnnotation()
    assert [s.label for s in window.canvas.shapes] == ['Bridge', 'Bridge']
    assert window.canvas.shapes[0].points == before_points
    window.redoAnnotation()
    assert [s.label for s in window.canvas.shapes] == ['OilTank', 'Bridge']


@pytest.mark.parametrize('result', ['existing', 'new', 'cancel', 'unchanged'])
def test_actual_single_label_popup(window, result):
    prepare(window)
    shape = add(window, [(100, 100), (200, 100), (200, 200), (100, 200)])
    window.labelStore.ensure('OilTank')
    observed = []
    def answer():
        dialog = QApplication.activePopupWidget()
        if not isinstance(dialog, ShapeLabelDialog):
            observed.append('wrong dialog')
            if dialog:
                dialog.close()
            return
        observed.append((dialog.windowTitle(), dialog.category.currentText()))
        if result == 'cancel':
            dialog.reject()
            return
        if result == 'new':
            dialog.category.setEditText('NewTarget')
        elif result == 'existing':
            dialog.category.setCurrentText('OilTank')
        dialog.buttons.button(QDialogButtonBox.Ok).click()
    QTimer.singleShot(30, answer)
    right_double_click(window.canvas, QPointF(150, 150))
    assert observed == [('更改标签', 'Bridge')]
    if result in ('cancel', 'unchanged'):
        assert shape.label == 'Bridge' and not window.dirty and not window._undoStack
    else:
        expected = 'NewTarget' if result == 'new' else 'OilTank'
        assert shape.label == expected and any(e['name'] == expected for e in window.labelStore.entries)
        assert len(window._undoStack) == 1
        if result == 'new':
            from label_store import LabelStore
            assert any(e['name'] == expected for e in LabelStore(window.labelStore.path).entries)


def test_tiny_box_corner_can_be_relabeled(window, monkeypatch):
    prepare(window)
    shape = add(window, [(100, 100), (101, 100), (101, 101), (100, 101)], True)
    monkeypatch.setattr(window, 'chooseShapeLabel', lambda shape, editing=False: 'TinyTarget')
    right_double_click(window.canvas, QPointF(105, 104))
    assert shape.label == 'TinyTarget' and shape.isRotated


def test_locked_box_consumes_click_without_popup_or_edit(window, monkeypatch):
    prepare(window)
    shape = add(window, [(100, 100), (200, 100), (200, 200), (100, 200)])
    shape.locked = True
    monkeypatch.setattr(window, 'chooseShapeLabel', lambda *args, **kwargs: pytest.fail('Locked label editor'))
    for menu in window.canvas.menus:
        monkeypatch.setattr(menu, 'exec_', lambda *args: pytest.fail('Unexpected context menu'))
    right_double_click(window.canvas, QPointF(150, 150))
    assert shape.label == 'Bridge' and not window.dirty and not window._undoStack


def test_hidden_blank_and_unfinished_box_do_not_relabel(window, monkeypatch):
    prepare(window)
    shape = add(window, [(100, 100), (200, 100), (200, 200), (100, 200)])
    window.canvas.setShapeVisible(shape, False)
    monkeypatch.setattr(window, 'chooseShapeLabel', lambda *args, **kwargs: pytest.fail('Unexpected editor'))
    for point in (QPointF(150, 150), QPointF(800, 800)):
        mouse(window.canvas, QEvent.MouseButtonDblClick, point, Qt.RightButton, Qt.RightButton)
        mouse(window.canvas, QEvent.MouseButtonRelease, point, Qt.RightButton, Qt.NoButton)
    window.actions.create.trigger()
    mouse(window.canvas, QEvent.MouseButtonPress, QPointF(400, 400), Qt.LeftButton, Qt.LeftButton)
    assert window.canvas.current is not None
    mouse(window.canvas, QEvent.MouseButtonDblClick, QPointF(450, 450), Qt.RightButton, Qt.RightButton)
    mouse(window.canvas, QEvent.MouseButtonRelease, QPointF(450, 450), Qt.RightButton, Qt.NoButton)
    assert window.canvas.current is not None and len(window.canvas.shapes) == 1
    assert not window.dirty and not window._undoStack


def test_right_drag_corner_still_rotates_and_creates_one_undo(window):
    prepare(window)
    shape = add(window, [(100, 100), (200, 100), (200, 200), (100, 200)], True)
    mouse(window.canvas, QEvent.MouseButtonPress, QPointF(100, 100), Qt.RightButton, Qt.RightButton)
    mouse(window.canvas, QEvent.MouseMove, QPointF(220, 150), Qt.NoButton, Qt.RightButton)
    mouse(window.canvas, QEvent.MouseButtonRelease, QPointF(220, 150), Qt.RightButton, Qt.NoButton)
    assert not math.isclose(shape.direction, 0) and len(window._undoStack) == 1
    assert not window.canvas._editingGesture and not window.canvas._rotatingGesture


def test_label_confirm_rejects_blank_text(window):
    dialog = ShapeLabelDialog(window, window.labelStore.entries, 'Bridge')
    dialog.category.setEditText('   ')
    assert not dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()
    dialog.accept()
    assert dialog.result() != dialog.Accepted
    dialog.category.setEditText('NewClass')
    assert dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()


def test_real_dropdown_selection_and_escape_cancel(window):
    from PyQt5.QtTest import QTest
    from test_popup_controls import enable_offscreen_fonts
    enable_offscreen_fonts()
    prepare(window)
    shape = add(window, [(100, 100), (200, 100), (200, 200), (100, 200)])
    window.labelStore.ensure('OilTank')
    observed = []
    def choose_from_dropdown():
        dialog = QApplication.activePopupWidget()
        dialog.category.showPopup()
        QApplication.processEvents()
        view = dialog.category.view()
        index = dialog.category.model().index(dialog.category.findText('OilTank'), 0)
        view.scrollTo(index)
        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.visualRect(index).center())
        observed.append(dialog.category.currentText())
        dialog.buttons.button(QDialogButtonBox.Ok).click()
    QTimer.singleShot(30, choose_from_dropdown)
    right_double_click(window.canvas, QPointF(150, 150))
    assert observed == ['OilTank'] and shape.label == 'OilTank'
    def cancel_with_escape():
        dialog = QApplication.activePopupWidget()
        dialog.category.setEditText('ShouldNotBeAdded')
        QTest.keyClick(dialog.category, Qt.Key_Escape)
    QTimer.singleShot(30, cancel_with_escape)
    right_double_click(window.canvas, QPointF(150, 150))
    assert shape.label == 'OilTank' and len(window._undoStack) == 1
    assert not any(e['name'] == 'ShouldNotBeAdded' for e in window.labelStore.entries)
