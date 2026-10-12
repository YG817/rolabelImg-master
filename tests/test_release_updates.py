import json
import time
from urllib.error import HTTPError
import pytest
from PyQt5.QtCore import QSettings, QTimer
from PyQt5.QtWidgets import QDialog, QCheckBox
from conftest import wait_until
from app_version import GITHUB_OWNER, GITHUB_REPO, installer_name
import update_checker


def release(version='2.0.1'):
    tag = 'v' + version
    name = installer_name(version)
    return {'tag_name': tag, 'draft': False, 'prerelease': False, 'body': '<b>plain notes</b>',
            'assets': [{'name': name, 'state': 'uploaded', 'size': 123,
                'browser_download_url': f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/{tag}/{name}'}]}


def test_numeric_version_comparison_and_stable_channel():
    assert update_checker.version_tuple('v2.10.0') > update_checker.version_tuple('2.9.0')
    assert update_checker.release_information(release(), '2.0.0')['version'] == '2.0.1'
    assert update_checker.release_information(release(), '2.0.1') is None
    assert update_checker.release_information(release(), '3.0.0') is None
    for field in ('draft', 'prerelease'):
        data = release()
        data[field] = True
        assert update_checker.release_information(data, '2.0.0') is None
    for value in ('v2.0', 'latest', '2.0.1-rc.1', '2.01.0'):
        with pytest.raises(ValueError):
            update_checker.version_tuple(value)


@pytest.mark.parametrize('url', ['http://github.com/file.exe', 'https://evil.example/file.exe',
                              'https://github.com/another/repo/releases/download/v2.0.1/setup.exe'])
def test_download_validation(url):
    data = release()
    data['assets'][0]['browser_download_url'] = url
    with pytest.raises(ValueError):
        update_checker.release_information(data, '2.0.0')


def test_missing_installer_rejected():
    data = release()
    data['assets'] = []
    with pytest.raises(ValueError):
        update_checker.release_information(data, '2.0.0')


def test_http_errors_and_size_limit(monkeypatch):
    for status in (404, 403, 429, 500):
        def fail(*args, **kwargs):
            raise HTTPError('https://api.github.com', status, 'test', {}, None)
        monkeypatch.setattr(update_checker, 'urlopen', fail)
        with pytest.raises(ValueError):
            update_checker.fetch_latest()
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def geturl(self): return 'https://release-assets.githubusercontent.com/metadata'
        def read(self, size): return b' ' * size
    monkeypatch.setattr(update_checker, 'urlopen', lambda *a, **k: Response())
    with pytest.raises(ValueError, match='过大'):
        update_checker.fetch_latest()


def test_update_check_is_async_and_cache_can_be_bypassed(window, monkeypatch):
    beats, calls, updates = [], [], []
    def fetch():
        calls.append(1)
        time.sleep(0.15)
        return update_checker.release_information(release(), '2.0.0')
    monkeypatch.setattr(update_checker, 'fetch_latest', fetch)
    monkeypatch.setattr(window.updater, 'show_update', updates.append)
    timer = QTimer()
    timer.timeout.connect(lambda: beats.append(1))
    timer.start(10)
    window.updater.check(True)
    first = window.updater.worker
    window.updater.check(True)
    assert window.updater.worker is first
    wait_until(lambda: window.updater.worker is None)
    assert len(beats) >= 3 and len(calls) == 1 and len(updates) == 1
    window.updater.check()
    assert window.updater.worker is None
    window.updater.check(True)
    wait_until(lambda: window.updater.worker is None)
    assert len(calls) == 2
    timer.stop()


def test_preferences_and_close_during_check(window, monkeypatch):
    window.updateAction.trigger()
    dialog = next(d for d in window.findChildren(QDialog) if d.windowTitle() == '版本与更新')
    dialog.findChild(QCheckBox).setChecked(False)
    assert not QSettings().value('updates/enabled', True, type=bool)
    dialog.close()
    window.updater.check()
    assert window.updater.worker is None
    monkeypatch.setattr(update_checker, 'fetch_latest', lambda: (time.sleep(0.15) or None))
    window.updater.check(True)
    window.close()
    wait_until(lambda: not window._workers)
    assert not window.isVisible()
