"""A failed version query must not take away a known installer."""
import hashlib
import io
import json
import time
from pathlib import Path
from urllib.error import HTTPError
import pytest
from PyQt5.QtCore import QSettings
from conftest import wait_until
from app_version import APP_VERSION, GITHUB_OWNER, GITHUB_REPO, LATEST_RELEASE_API, LATEST_UPDATE_MANIFEST, installer_name
from test_release_updates import release
from test_update_download import DATA, info
from update_manifest import write_update_manifest
import update_checker
import update_download


class JsonResponse(io.BytesIO):
    def __init__(self, data):
        super().__init__(json.dumps(data).encode())
    def geturl(self):
        return 'https://release-assets.githubusercontent.com/update.json'


def manifest():
    data = release('2.0.3')
    data.update(schema_version=1, repository=f'{GITHUB_OWNER}/{GITHUB_REPO}')
    data['assets'][0]['digest'] = 'sha256:' + 'a' * 64
    return data


def test_manifest_query_does_not_call_rest_api(monkeypatch):
    calls = []
    def fetch(request, **kwargs):
        calls.append(request.full_url)
        return JsonResponse(manifest())
    monkeypatch.setattr(update_checker, 'urlopen', fetch)
    assert update_checker.fetch_latest()['version'] == '2.0.3'
    assert calls == [LATEST_UPDATE_MANIFEST]


def test_old_release_without_manifest_falls_back_once(monkeypatch):
    calls = []
    def fetch(request, **kwargs):
        calls.append(request.full_url)
        if request.full_url == LATEST_UPDATE_MANIFEST:
            raise HTTPError(request.full_url, 404, 'missing asset', {}, None)
        return JsonResponse(release('2.0.3'))
    monkeypatch.setattr(update_checker, 'urlopen', fetch)
    assert update_checker.fetch_latest()['version'] == '2.0.3'
    assert calls == [LATEST_UPDATE_MANIFEST, LATEST_RELEASE_API]


@pytest.mark.parametrize('headers,body,limited', [
    ({}, {'message': 'Forbidden'}, False),
    ({'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': str(time.time() + 200)}, {}, True),
    ({'Retry-After': '120'}, {'message': 'You have exceeded a secondary rate limit.'}, True),
])
def test_access_denied_is_distinguished_from_rate_limit(monkeypatch, headers, body, limited):
    def fail(*args, **kwargs):
        raise HTTPError(LATEST_RELEASE_API, 403, 'test', headers, io.BytesIO(json.dumps(body).encode()))
    monkeypatch.setattr(update_checker, 'urlopen', fail)
    with pytest.raises(ValueError) as error:
        update_checker.fetch_latest(LATEST_RELEASE_API)
    assert isinstance(error.value, update_checker.UpdateRateLimit) is limited
    if not limited:
        assert '拒绝访问' in str(error.value)


def test_limited_check_preserves_cached_update_and_obeys_cooldown(window, monkeypatch):
    available = update_checker.release_information(manifest())
    calls, shown = [], []
    monkeypatch.setattr(window.updater, 'show_update', shown.append)
    monkeypatch.setattr(update_checker, 'fetch_latest', lambda: available)
    window.updater.check(True)
    wait_until(lambda: window.updater.worker is None)
    assert update_checker.load_cached_release()['version'] == '2.0.3'
    def limited():
        calls.append(1)
        raise update_checker.UpdateRateLimit(time.time() + 600)
    monkeypatch.setattr(update_checker, 'fetch_latest', limited)
    window.updater.check(True)
    wait_until(lambda: window.updater.worker is None)
    assert len(calls) == 1 and shown[-1]['from_cache']
    for _ in range(3):
        window.updater.check(True)
    assert len(calls) == 1 and window.updater.worker is None
    assert float(QSettings().value('updates/retryAt')) > time.time()
    window.updater.show_settings()
    assert window.updater.settingsDialog.cachedPanel.isVisible()
    window.updater.settingsDialog.close()


def test_cached_update_can_be_opened_without_network_after_controller_recreation(window, monkeypatch):
    update_checker.save_cached_release(update_checker.release_information(manifest()))
    QSettings().sync()
    controller = update_checker.UpdateController(window)
    shown = []
    monkeypatch.setattr(controller, 'show_update', shown.append)
    monkeypatch.setattr(update_checker, 'fetch_latest', lambda: pytest.fail('Unexpected version query'))
    controller.show_cached_update()
    assert shown[0]['from_cache'] and shown[0]['version'] == '2.0.3'


def test_wrong_repository_or_installed_cache_is_not_used(window):
    available = update_checker.release_information(manifest())
    update_checker.save_cached_release(available)
    raw = json.loads(QSettings().value('updates/availableRelease'))
    raw['repository'] = 'another/repo'
    QSettings().setValue('updates/availableRelease', json.dumps(raw))
    assert update_checker.load_cached_release() is None
    raw['repository'] = f'{GITHUB_OWNER}/{GITHUB_REPO}'
    raw['info']['version'] = APP_VERSION
    QSettings().setValue('updates/availableRelease', json.dumps(raw))
    assert update_checker.load_cached_release() is None


def test_downloaded_verified_installer_is_reused_offline(window, tmp_path, monkeypatch):
    target = tmp_path / installer_name('2.0.2')
    target.write_bytes(DATA)
    monkeypatch.setattr(update_download, 'urlopen', lambda *a, **k: pytest.fail('Should reuse local verified installer'))
    worker = update_download.InstallerDownload(info(), tmp_path, window)
    results = []
    worker.result.connect(lambda *a: results.append(a))
    worker.start()
    wait_until(lambda: worker.isFinished())
    wait_until(lambda: bool(results))
    assert results[0] == (str(target), hashlib.sha256(DATA).hexdigest())


def test_corrupt_local_installer_is_not_reused(window, tmp_path, monkeypatch):
    target = tmp_path / installer_name('2.0.2')
    corrupted = b'MZ' + b'X' * (len(DATA) - 2)
    target.write_bytes(corrupted)
    def fail(*args, **kwargs):
        raise OSError('offline')
    monkeypatch.setattr(update_download, 'urlopen', fail)
    worker = update_download.InstallerDownload(info(), tmp_path, window)
    errors, results = [], []
    worker.failed.connect(errors.append)
    worker.result.connect(lambda *a: results.append(a))
    worker.start()
    wait_until(lambda: worker.isFinished())
    wait_until(lambda: bool(errors))
    assert not results and target.read_bytes() == corrupted


def test_generated_manifest_matches_binary_and_notes(tmp_path, monkeypatch):
    path = tmp_path / installer_name('2.0.3')
    path.write_bytes(DATA)
    generated = write_update_manifest(tmp_path, '2.0.3', '## 更新日志\n- 测试')
    data = json.loads(generated.read_text(encoding='utf-8'))
    assert data['assets'][0]['digest'] == 'sha256:' + hashlib.sha256(DATA).hexdigest()
    assert data['assets'][0]['size'] == len(DATA)
    monkeypatch.setattr(update_checker, 'urlopen', lambda *a, **k: JsonResponse(data))
    checked = update_checker.fetch_manifest()
    assert checked['version'] == '2.0.3' and '更新日志' in checked['notes']
