from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QFileDialog, QTabWidget
from conftest import wait_until


def make_image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(80, 60, QImage.Format_RGB32)
    image.fill(Qt.gray)
    assert image.save(str(path))
    return str(path)


def test_single_image_list_and_title(window, tmp_path):
    path = make_image(tmp_path / 'scene.png')
    window.loadFile(path)
    wait_until(lambda: window.filePath == path and not window._loading)
    assert window.fileListWidget.count() == 1
    item = window.fileListWidget.currentItem()
    assert item.text() == 'scene.png'
    assert item.data(Qt.UserRole) == path and item.toolTip() == path
    assert window.windowTitle() == 'roLabelImg'


def test_folder_list_relative_paths_navigation_and_cancel(window, tmp_path, monkeypatch):
    folder = tmp_path / 'images'
    first = make_image(folder / 'a' / 'same.png')
    second = make_image(folder / 'b' / 'same.png')
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a, **k: str(folder))
    window.openDir()
    wait_until(lambda: window.filePath == first and not window._loading)
    assert window.fileListWidget.count() == 2
    assert window.fileListWidget.item(0).text() != window.fileListWidget.item(1).text()
    window.fileitemDoubleClicked(window.fileListWidget.item(1))
    wait_until(lambda: window.filePath == second and not window._loading)
    assert window.fileListWidget.currentRow() == 1
    window.openPrevImg()
    wait_until(lambda: window.filePath == first and not window._loading)
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a, **k: '')
    window.openDir()
    assert window.mImgList == [first, second] and window.filePath == first
    outside = make_image(tmp_path / 'outside.png')
    window.loadFile(outside)
    wait_until(lambda: window.filePath == outside and not window._loading)
    assert window.mImgList == [outside]
    assert window.fileListWidget.currentItem().text() == 'outside.png'


def test_direct_quick_guide_action(window):
    actions = window.menuBar().actions()
    assert window.guideAction in actions
    assert window.guideAction.text() == '❔ 操作说明'
    assert window.menus.help.menuAction() not in actions
    window.guideAction.trigger()
    tabs = window._guideDialog.findChild(QTabWidget)
    assert [tabs.tabText(i) for i in range(tabs.count())] == ['标注与编辑', '影像与视图', '文件与保存']
    assert not window._guideDialog.isModal()
    window._guideDialog.close()
