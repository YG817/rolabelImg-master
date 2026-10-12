"""Download progress, integrity, cancellation and installation handoff."""
import base64
import hashlib
import io
from pathlib import Path
import time
import pytest
from PyQt5.QtCore import QTimer, QStandardPaths
from app_version import installer_name
from conftest import wait_until
from test_release_updates import release
import update_checker
import update_download


DATA = b'MZ' + b'installer data' * 50000


def info():
    data = release('2.0.2')
    data['assets'][0]['size'] = len(DATA)
    data['assets'][0]['digest'] = 'sha256:' + hashlib.sha256(DATA).hexdigest()
    data['body'] = '## 新增功能\n- 软件内下载更新\n\n## 修复问题\n- 删除 JSON 后可以重新保存\n<b>literal</b>'
    return update_checker.release_information(data, '2.0.1')


class Response(io.BytesIO):
    def __init__(self, data=DATA, delay=0, url=None, length=None):
        super().__init__(data)
        self.delay = delay
        self.url = url or info()['url']
        self.headers = {} if length is None else {'Content-Length': str(length)}

    def geturl(self):
        return self.url

    def read(self, size=-1):
        if self.delay:
            time.sleep(self.delay)
        return super().read(size)


def test_async_download_is_responsive_and_verifies_digest(window, tmp_path, monkeypatch):
    monkeypatch.setattr(update_download, 'urlopen', lambda *a, **k: Response(delay=0.03, length=len(DATA)))
    worker = update_download.InstallerDownload(info(), tmp_path, window)
    result, progress, beats = [], [], []
    worker.result.connect(lambda *args: result.append(args))
    worker.progress.connect(lambda *args: progress.append(args))
    timer = QTimer(window)
    timer.timeout.connect(lambda: beats.append(1))
    timer.start(5)
    worker.start()
    wait_until(lambda: worker.isFinished())
    wait_until(lambda: len(result) == 1)
    timer.stop()
    assert len(beats) >= 5
    assert progress[0][0] == 0 and progress[-1][0] == len(DATA)
    assert Path(result[0][0]).read_bytes() == DATA
    assert result[0][1] == hashlib.sha256(DATA).hexdigest()
    assert not list(tmp_path.glob('*.part'))


@pytest.mark.parametrize('response,expected', [
    (lambda: Response(b'MZshort'), '不完整'),
    (lambda: Response(DATA + b'excess'), '超出'),
    (lambda: Response(DATA.replace(b'data', b'DATA')), 'SHA-256'),
    (lambda: Response(b'xx' + DATA[2:]), 'SHA-256'),
    (lambda: Response(length=3), '大小'),
    (lambda: Response(url='https://evil.example/setup.exe'), '非 GitHub'),
])
def test_corrupted_or_redirected_download_never_replaces_existing(window, tmp_path, monkeypatch, response, expected):
    target = tmp_path / installer_name('2.0.2')
    target.write_bytes(b'previous valid installer')
    monkeypatch.setattr(update_download, 'urlopen', lambda *a, **k: response())
    worker = update_download.InstallerDownload(info(), tmp_path, window)
    errors, results = [], []
    worker.failed.connect(errors.append)
    worker.result.connect(lambda *a: results.append(a))
    worker.start()
    wait_until(lambda: worker.isFinished())
    wait_until(lambda: bool(errors))
    assert expected in errors[0]
    assert not results and target.read_bytes() == b'previous valid installer'
    assert not list(tmp_path.glob('*.part'))


def test_cancel_download_then_retry_with_changelog(window, tmp_path, monkeypatch):
    monkeypatch.setattr(QStandardPaths, 'writableLocation', lambda *a: str(tmp_path))
    monkeypatch.setattr(update_download, 'urlopen', lambda *a, **k: Response(delay=0.04))
    window.updater.show_update(info())
    dialog = window.updater.dialog
    assert not dialog.isModal()
    assert '新增功能' in dialog.notes.toPlainText() and '<b>literal</b>' in dialog.notes.toPlainText()
    dialog.downloadButton.click()
    QTimer.singleShot(50, dialog.primaryAction)
    wait_until(lambda: dialog.worker is None)
    assert not dialog.installer and '已取消' in dialog.status.text()
    assert not list((tmp_path / 'updates').glob('*.part'))
    dialog.downloadButton.click()
    wait_until(lambda: dialog.worker is None)
    assert Path(dialog.installer).read_bytes() == DATA
    assert dialog.progress.value() == 100 and dialog.downloadButton.text() == '退出并安装'
    assert 'SHA-256' in dialog.status.text()


def test_switch_image_does_not_cancel_update_and_close_does(window, tmp_path, monkeypatch):
    monkeypatch.setattr(QStandardPaths, 'writableLocation', lambda *a: str(tmp_path))
    monkeypatch.setattr(update_download, 'urlopen', lambda *a, **k: Response(delay=0.1))
    window.updater.show_update(info())
    dialog = window.updater.dialog
    dialog.downloadButton.click()
    worker = dialog.worker
    window.resetState()
    assert not worker.isInterruptionRequested()
    window.close()
    wait_until(lambda: not window._workers)
    assert not window.isVisible()
    assert not list((tmp_path / 'updates').glob('*.part'))


def test_cancel_unsaved_close_prevents_installer_launch(window, monkeypatch):
    window.updater.show_update(info())
    dialog = window.updater.dialog
    dialog.installer, dialog.digest = 'not-used.exe', '0' * 64
    calls = []
    monkeypatch.setattr(window, 'mayContinue', lambda: False)
    monkeypatch.setattr(update_checker, 'launch_installer_after_exit', lambda *a: calls.append(a))
    dialog.primaryAction()
    assert window.isVisible() and not calls
    assert window.updater.pending_installer is None


def test_install_handoff_occurs_after_close_approval(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window, 'mayContinue', lambda: True)
    monkeypatch.setattr(update_checker, 'launch_installer_after_exit', lambda *a: calls.append(a))
    window.updater.pending_installer = ('verified.exe', '1' * 64)
    window.close()
    assert calls == [('verified.exe', '1' * 64)]
    assert not window.isVisible()


def test_windows_helper_is_hidden_waits_for_exit_and_escapes_paths(tmp_path, monkeypatch):
    path = tmp_path / "中文 It's setup.exe"
    path.write_bytes(b'MZtest')
    calls = []
    monkeypatch.setattr(update_download.subprocess, 'Popen', lambda *a, **k: calls.append((a, k)))
    update_download.launch_installer_after_exit(path, 'a' * 64)
    args, kwargs = calls[0][0][0], calls[0][1]
    script = base64.b64decode(args[-1]).decode('utf-16le')
    assert "It''s setup.exe" in script
    assert 'Wait-Process -Id' in script and 'Get-FileHash -LiteralPath' in script
    assert 'Start-Process -FilePath' in script
    assert args[args.index('-WindowStyle') + 1] == 'Hidden'
    assert kwargs['creationflags'] == update_download.subprocess.CREATE_NO_WINDOW


def test_download_network_failure_can_be_retried(window, tmp_path, monkeypatch):
    monkeypatch.setattr(QStandardPaths, 'writableLocation', lambda *a: str(tmp_path))
    def fail(*args, **kwargs):
        raise TimeoutError('connection timed out')
    monkeypatch.setattr(update_download, 'urlopen', fail)
    window.updater.show_update(info())
    dialog = window.updater.dialog
    dialog.downloadButton.click()
    wait_until(lambda: dialog.worker is None)
    assert '下载失败' in dialog.status.text()
    assert dialog.downloadButton.isEnabled() and dialog.downloadButton.text() == '下载更新'
    assert not list((tmp_path / 'updates').glob('*.part'))
    monkeypatch.setattr(update_download, 'urlopen', lambda *a, **k: Response())
    dialog.downloadButton.click()
    wait_until(lambda: dialog.worker is None)
    assert dialog.installer and dialog.progress.value() == 100
