"""Exercise the real expanded controls, not just their closed-state styling."""
from pathlib import Path
import time
import pytest
from PyQt5.QtCore import QPoint, Qt, QSettings
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest, QSignalSpy
from batch_edit_dialog import BatchEditDialog
from conftest import wait_until
import update_checker


def enable_offscreen_fonts():
    # The Windows offscreen plugin does not enumerate installed fonts itself.
    if not QFontDatabase().families():
        for path in ('C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/msyh.ttc'):
            if Path(path).is_file():
                QFontDatabase.addApplicationFont(path)


@pytest.mark.parametrize('font_size', [13, 20])
def test_edit_menu_long_action_has_separate_shortcut_and_is_clickable(window, font_size):
    enable_offscreen_fonts()
    menu = window.menus.edit
    menu.setStyleSheet(menu.styleSheet().replace('13px', '%dpx' % font_size))
    action = next(a for a in menu.actions() if a.text() == '选择下一个重叠框')
    spy = QSignalSpy(action.triggered)
    menu.popup(window.mapToGlobal(QPoint(30, 50)))
    QApplication.processEvents()
    label, shortcut = menu.textRects(action)
    assert menu.fontMetrics().horizontalAdvance(action.text()) <= label.width()
    assert menu.fontMetrics().horizontalAdvance('Alt+Q') <= shortcut.width()
    assert shortcut.left() - label.right() >= 20
    QTest.mouseClick(menu, Qt.LeftButton, pos=menu.actionGeometry(action).center())
    assert len(spy) == 1 and not menu.isVisible()


def test_expanded_category_dropdown_has_usable_rows_and_selects_item(window):
    enable_offscreen_fonts()
    for name in ('Bridge', 'CargoShip', 'OilTank'):
        window.labelStore.ensure(name)
    dialog = BatchEditDialog(window, 2, 0, [e['name'] for e in window.labelStore.entries])
    dialog.show()
    combo = dialog.category
    combo.showPopup()
    QApplication.processEvents()
    index = combo.model().index(1, 0)
    rect = combo.view().visualRect(index)
    assert rect.height() >= 36
    assert combo.itemData(1, Qt.UserRole + 2)
    QTest.mouseClick(combo.view().viewport(), Qt.LeftButton, pos=rect.center())
    assert combo.currentText() == 'CargoShip'
    assert not combo.view().window().isVisible()
    combo.setFocus()
    QTest.keyClick(combo, Qt.Key_Down)
    assert combo.currentText() == 'OilTank'
    dialog.close()


def test_update_preferences_show_checking_result_and_retry(window, monkeypatch):
    monkeypatch.setattr(update_checker, 'fetch_latest', lambda: (time.sleep(0.1) or None))
    window.updater.show_settings()
    dialog = window.updater.settingsDialog
    dialog.checkButton.click()
    assert not dialog.checkButton.isEnabled()
    assert '检查' in dialog.checkButton.text()
    wait_until(lambda: window.updater.worker is None)
    assert dialog.checkButton.isEnabled() and '未发现更高' in dialog.status.text()
    def fail():
        raise ValueError('无法连接 GitHub')
    monkeypatch.setattr(update_checker, 'fetch_latest', fail)
    dialog.checkButton.click()
    wait_until(lambda: window.updater.worker is None)
    assert dialog.checkButton.isEnabled() and '无法连接' in dialog.status.text()
    dialog.enabled.setChecked(False)
    dialog.close()
    window.updater.show_settings()
    assert window.updater.settingsDialog is dialog
    assert not dialog.enabled.isChecked()
    assert not QSettings().value('updates/enabled', True, type=bool)
    assert not dialog.windowFlags() & Qt.WindowContextHelpButtonHint
    dialog.close()
