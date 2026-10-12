"""GitHub update checks, release notes and asynchronous installer downloads."""
import json
import re
import time
import math
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from PyQt5.QtCore import QObject, QSettings, QTimer, Qt, QThread, pyqtSignal, QStandardPaths
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextBrowser,
                            QCheckBox, QDialogButtonBox, QApplication, QProgressBar)
from app_version import (APP_VERSION, GITHUB_OWNER, GITHUB_REPO, LATEST_RELEASE_API,
                         LATEST_UPDATE_MANIFEST, installer_name)
from ui_theme import ModernDialog as QDialog, ui_label, panel, set_role
try:
    from .browser_launcher import BrowserLauncher
    from .update_download import InstallerDownload, launch_installer_after_exit
    from .update_download import validate_response_url, validate_download
except ImportError:
    from browser_launcher import BrowserLauncher
    from update_download import InstallerDownload, launch_installer_after_exit
    from update_download import validate_response_url, validate_download


def version_tuple(text):
    match = re.fullmatch(r'v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', text)
    if not match:
        raise ValueError('正式版本必须使用 v主版本.次版本.修订号，例如 v2.0.1')
    return tuple(map(int, match.groups()))


def release_information(data, current=APP_VERSION):
    """Reject incomplete releases and URLs outside the configured repository."""
    if not isinstance(data, dict):
        raise ValueError('版本信息格式错误')
    if data.get('draft') or data.get('prerelease'):
        return None
    tag = data.get('tag_name', '')
    remote = version_tuple(tag)
    if remote <= version_tuple(current):
        return None
    version = '.'.join(map(str, remote))
    expected = installer_name(version)
    prefix = f'/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/{tag}/'
    for asset in data.get('assets', []):
        if asset.get('name') != expected or asset.get('state') != 'uploaded' or asset.get('size', 0) <= 0:
            continue
        url = asset.get('browser_download_url', '')
        parsed = urlparse(url)
        if (parsed.scheme == 'https' and parsed.netloc == 'github.com'
                and parsed.path == prefix + expected and not parsed.query and not parsed.fragment):
            digest = asset.get('digest')
            if digest is not None and not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
                raise ValueError('安装包校验值格式错误')
            return dict(version=version, url=url, notes=str(data.get('body') or '')[:16000],
                        size=asset['size'], sha256=digest[7:] if digest else None,
                        release_url=f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/tag/{tag}')
    raise ValueError('新版本尚未提供匹配的 Windows x64 安装包，请稍后检查')


class UpdateRateLimit(ValueError):
    def __init__(self, retry_at):
        self.retry_at = retry_at
        super().__init__('更新查询暂时受限，已暂停重复查询；建议 %s 后重试。' %
                         datetime.fromtimestamp(retry_at).strftime('%H:%M:%S'))


def rate_limit_error(exc):
    headers = {key.lower(): value for key, value in (exc.headers or {}).items()}
    try:
        message = exc.read(4096).decode('utf-8', errors='replace').lower()
    except Exception:
        message = ''
    if not (exc.code == 429 or headers.get('x-ratelimit-remaining') == '0' or 'rate limit' in message):
        return None
    now = time.time()
    retry_at = now + 60
    for key, relative in (('retry-after', True), ('x-ratelimit-reset', False)):
        if key == 'x-ratelimit-reset' and headers.get('x-ratelimit-remaining') != '0':
            continue
        try:
            value = float(headers.get(key, ''))
            if math.isfinite(value):
                retry_at = max(retry_at, now + value if relative else value)
        except (ValueError, TypeError):
            pass
    # Invalid proxy headers must not make datetime formatting overflow.
    retry_at = min(retry_at, now + 7 * 86400)
    return UpdateRateLimit(retry_at)


def fetch_manifest(current=APP_VERSION):
    request = Request(LATEST_UPDATE_MANIFEST, headers={'User-Agent': 'roLabelImg/' + APP_VERSION,
                                                      'Accept': 'application/json'})
    with urlopen(request, timeout=10) as response:
        validate_response_url(response.geturl())
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('版本信息过大')
    data = json.loads(raw)
    if (not isinstance(data, dict) or data.get('schema_version') != 1
            or data.get('repository') != f'{GITHUB_OWNER}/{GITHUB_REPO}'):
        raise ValueError('更新说明的格式或来源无效')
    info = release_information(data, current)
    if info:
        validate_download(info)
        if not info['sha256']:
            raise ValueError('更新说明缺少安装包校验值')
    return info


def fetch_latest(url=None):
    if url is None:
        try:
            return fetch_manifest()
        except HTTPError as exc:
            if exc.code in (403, 429):
                limited = rate_limit_error(exc)
                if limited:
                    raise limited from exc
            # Older releases do not have update.json; retain the API fallback.
        except (URLError, TimeoutError, OSError):
            pass
    url = url or LATEST_RELEASE_API
    request = Request(url, headers={'Accept': 'application/vnd.github+json',
        'User-Agent': 'roLabelImg/' + APP_VERSION, 'X-GitHub-Api-Version': '2026-03-10'})
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('版本信息过大')
        info = release_information(json.loads(raw))
        if info:
            validate_download(info)
        return info
    except HTTPError as exc:
        if exc.code == 404:
            raise ValueError('发布仓库尚无可访问的正式版本，请确认仓库公开且已发布 Release') from exc
        if exc.code in (403, 429):
            limited = rate_limit_error(exc)
            if limited:
                raise limited from exc
            raise ValueError('GitHub 拒绝访问（HTTP 403），请检查网络或访问权限。') from exc
        raise ValueError('GitHub 返回错误 HTTP %s' % exc.code) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError('无法连接 GitHub，或请求超时。可稍后手动检查更新。') from exc


class ReleaseWorker(QThread):
    result = pyqtSignal(object)
    failed = pyqtSignal(str)
    limited = pyqtSignal(object)

    def run(self):
        try:
            info = fetch_latest()
            if not self.isInterruptionRequested():
                self.result.emit(info)
        except UpdateRateLimit as exc:
            if not self.isInterruptionRequested():
                self.limited.emit(exc)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))


def load_cached_release():
    try:
        raw = QSettings().value('updates/availableRelease', '')
        if not isinstance(raw, str) or len(raw) > 1024 * 1024:
            return None
        cache = json.loads(raw)
        if cache.get('repository') != f'{GITHUB_OWNER}/{GITHUB_REPO}':
            return None
        original = cache['info']
        validate_download(original)
        version = original['version']
        if version_tuple(version) <= version_tuple(APP_VERSION):
            return None
        checked_at = float(cache['checked_at'])
        if not math.isfinite(checked_at) or checked_at <= 0:
            return None
        datetime.fromtimestamp(checked_at)
        return dict(version=version, url=original['url'], size=original['size'],
                    sha256=original.get('sha256'), notes=str(original.get('notes') or '')[:16000],
                    release_url=f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/tag/v{version}',
                    from_cache=True, checked_at=checked_at)
    except (ValueError, TypeError, KeyError, AttributeError, OSError, OverflowError):
        return None


def save_cached_release(info):
    validate_download(info)
    if version_tuple(info['version']) > version_tuple(APP_VERSION):
        QSettings().setValue('updates/availableRelease', json.dumps(dict(
            repository=f'{GITHUB_OWNER}/{GITHUB_REPO}', checked_at=time.time(), info=info), ensure_ascii=False))


def release_notes_html(notes):
    """Render common changelog headings/lists without loading external content."""
    lines = []
    for line in (notes or '此版本未提供更新说明。').splitlines():
        text = escape(line.strip())
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
        if line.startswith('#'):
            text = re.sub(r'^#+\s*', '', text)
            lines.append('<h3>%s</h3>' % text)
        elif line.lstrip().startswith(('- ', '* ')):
            lines.append('<p style="margin: 8px 0 8px 12px;">• %s</p>' % text[2:])
        elif text:
            lines.append('<p>%s</p>' % text)
    return ('<html><body style="font-family: Microsoft YaHei UI; color: #273449; font-size: 14px;">'
            + ''.join(lines) + '</body></html>')


class UpdateDialog(QDialog):
    def __init__(self, controller, info):
        super().__init__(controller.window)
        self.controller = controller
        self.info = info
        self.worker = None
        self.installer = None
        self.digest = None
        self.setWindowTitle('软件更新')
        self.resize(720, 570)
        self.setMinimumSize(520, 400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(14)
        header = QHBoxLayout()
        title = ui_label('新版本 v%s' % info['version'], 'dialogTitle')
        header.addWidget(title, 1)
        release = QPushButton('前往发布页')
        release.clicked.connect(lambda: controller.open_download(info.get('release_url') or
                                f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/tag/v{info["version"]}'))
        header.addWidget(release)
        layout.addLayout(header)
        layout.addWidget(ui_label('当前版本 %s · 下载完成后，可保存标注并退出软件安装更新' % APP_VERSION))
        if info.get('from_cache'):
            checked = datetime.fromtimestamp(info['checked_at']).strftime('%m-%d %H:%M')
            layout.addWidget(ui_label('来自 %s 的成功检查记录；可直接下载，尚未确认是否有更高版本。' % checked))
        self.notes = QTextBrowser(self)
        self.notes.setObjectName('updateNotes')
        self.notes.setOpenLinks(False)
        self.notes.setHtml(release_notes_html(info.get('notes')))
        self.notes.setStyleSheet('QTextBrowser { background: white; border: 1px solid #dfe5ee; '
                                'border-radius: 8px; padding: 14px; }')
        layout.addWidget(self.notes, 1)
        self.status = QLabel('点击“下载更新”，在软件内下载安装包')
        self.status.setWordWrap(True)
        self.status.setStyleSheet('color: #65758b;')
        layout.addWidget(self.status)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setStyleSheet('QProgressBar { border: none; border-radius: 4px; background: #e5ecf7; '
                                   'height: 12px; text-align: center; } '
                                   'QProgressBar::chunk { background: #3478e5; border-radius: 4px; }')
        layout.addWidget(self.progress)
        buttons = QHBoxLayout()
        copy = QPushButton('复制下载链接')
        copy.clicked.connect(lambda: QApplication.clipboard().setText(info['url']))
        buttons.addWidget(copy)
        buttons.addStretch()
        self.cancelButton = QPushButton('关闭')
        self.cancelButton.clicked.connect(self.close)
        buttons.addWidget(self.cancelButton)
        self.downloadButton = QPushButton('下载更新')
        self.downloadButton.setObjectName('downloadUpdate')
        set_role(self.downloadButton, 'primary')
        self.downloadButton.clicked.connect(self.primaryAction)
        buttons.addWidget(self.downloadButton)
        layout.addLayout(buttons)

    def primaryAction(self):
        if self.worker:
            self.worker.requestInterruption()
            self.downloadButton.setEnabled(False)
            self.status.setText('正在取消下载…')
        elif self.installer:
            self.controller.pending_installer = (self.installer, self.digest)
            self.controller.window.close()
        else:
            directory = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)) / 'updates'
            self.worker = InstallerDownload(self.info, directory, self.controller.window)
            self.controller.window._workers.add(self.worker)
            self.worker.progress.connect(self.downloadProgress)
            self.worker.phase.connect(self.status.setText)
            self.worker.result.connect(self.downloaded)
            self.worker.failed.connect(self.downloadFailed)
            self.worker.cancelled.connect(self.downloadCancelled)
            self.worker.finished.connect(self.downloadFinished)
            self.worker.finished.connect(self.controller.window.workerFinished)
            self.downloadButton.setText('取消下载')
            self.progress.setValue(0)
            self.status.setText('正在连接 GitHub…')
            self.worker.start()

    def downloadProgress(self, downloaded, total, speed):
        self.progress.setValue(int(downloaded * 100 / total))
        self.status.setText('%.1f / %.1f MB · %.1f MB/s' % (downloaded / 1024**2, total / 1024**2, speed / 1024**2))

    def downloaded(self, path, digest):
        self.installer, self.digest = path, digest
        self.progress.setValue(100)
        self.status.setText('安装包已就绪%s。点击“退出并安装”后先处理未保存标注，再启动安装向导。' %
                            ('，SHA-256 校验通过' if self.info.get('sha256') else '，文件大小已核对'))
        self.status.setToolTip(path)

    def downloadFailed(self, message):
        self.status.setText(message + '；可重试，或前往发布页手动下载。')

    def downloadCancelled(self):
        self.progress.setValue(0)
        self.status.setText('已取消下载，临时文件已清理；可重新下载。')

    def downloadFinished(self):
        self.worker = None
        self.downloadButton.setEnabled(True)
        self.downloadButton.setText('退出并安装' if self.installer else '下载更新')

    def closeEvent(self, event):
        if self.worker:
            self.worker.requestInterruption()
        # Keep this dialog alive while queued worker signals are delivered.
        super().closeEvent(event)


class UpdateSettingsDialog(QDialog):
    def __init__(self, controller):
        super().__init__(controller.window)
        self.setWindowTitle('版本与更新')
        self.resize(500, 350)
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(16)
        header = QHBoxLayout()
        header.addWidget(ui_label('roLabelImg', 'dialogTitle'), 1)
        header.addWidget(ui_label('v' + APP_VERSION, 'badge'))
        layout.addLayout(header)
        layout.addWidget(ui_label('Windows x64 · 遥感影像标注'))
        preferences, fields = panel()
        fields.setContentsMargins(16, 16, 16, 16)
        fields.addWidget(ui_label('更新设置', 'sectionTitle'))
        self.enabled = QCheckBox('启动时自动检查新版本', preferences)
        self.enabled.setChecked(QSettings().value('updates/enabled', True, type=bool))
        self.enabled.toggled.connect(lambda value: QSettings().setValue('updates/enabled', value))
        fields.addWidget(self.enabled)
        fields.addWidget(ui_label('自动检查最多每天一次，手动检查不受此间隔限制。'))
        layout.addWidget(preferences)
        self.cachedPanel, cachedLayout = panel()
        self.cachedLabel = ui_label('', 'sectionTitle')
        cachedLayout.addWidget(self.cachedLabel)
        cachedLayout.addWidget(ui_label('保留上次成功检查的信息，查询受限时仍可下载安装。'))
        cachedButton = QPushButton('查看日志并更新')
        set_role(cachedButton, 'primary')
        cachedButton.clicked.connect(controller.show_cached_update)
        cachedLayout.addWidget(cachedButton)
        layout.addWidget(self.cachedPanel)
        self.refreshCache()
        self.status = ui_label('点击“检查更新”，查看最新版本与更新日志。')
        self.status.setObjectName('updateCheckStatus')
        layout.addWidget(self.status)
        layout.addStretch()
        footer = QHBoxLayout()
        release = QPushButton('发布页')
        release.clicked.connect(lambda: controller.open_download(
            f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest'))
        footer.addWidget(release)
        footer.addStretch()
        close = QPushButton('关闭')
        close.clicked.connect(self.close)
        footer.addWidget(close)
        self.checkButton = QPushButton('检查更新')
        set_role(self.checkButton, 'primary')
        self.checkButton.clicked.connect(lambda: controller.check(True))
        footer.addWidget(self.checkButton)
        layout.addLayout(footer)

    def setBusy(self, busy):
        self.checkButton.setEnabled(not busy)
        self.checkButton.setText('正在检查…' if busy else '检查更新')

    def refreshCache(self):
        info = load_cached_release()
        self.cachedPanel.setVisible(info is not None)
        if info:
            self.cachedLabel.setText('已发现新版本 v%s' % info['version'])
        if hasattr(self, 'checkButton'):
            set_role(self.checkButton, 'quiet' if info else 'primary')


class UpdateController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.worker = None
        self.manual = False
        self.cancelled = False
        self.dialog = None
        self.settingsDialog = None
        self.pending_installer = None
        self.startup = QTimer(self)
        self.startup.setSingleShot(True)
        self.startup.timeout.connect(self.check)

    def schedule(self):
        self.startup.start(5000)

    def check(self, manual=False):
        if self.worker is not None or self.window._closePending:
            return
        settings = QSettings()
        try:
            retry_at = float(settings.value('updates/retryAt', 0))
        except (ValueError, TypeError):
            retry_at = 0
        if math.isfinite(retry_at) and time.time() < retry_at <= time.time() + 7 * 86400:
            if manual:
                self.failed(str(UpdateRateLimit(retry_at)))
            return
        if not manual:
            enabled = settings.value('updates/enabled', True, type=bool)
            try:
                last = float(settings.value('updates/lastCheck', 0))
            except (ValueError, TypeError):
                last = 0
            if not enabled or time.time() - last < 86400:
                return
        self.manual, self.cancelled = manual, False
        settings.setValue('updates/lastCheck', time.time())
        self.worker = ReleaseWorker(self.window)
        self.window._workers.add(self.worker)
        self.worker.result.connect(self.finished)
        self.worker.failed.connect(self.failed)
        self.worker.limited.connect(self.rateLimited)
        self.worker.finished.connect(self.clear_worker)
        self.worker.finished.connect(self.window.workerFinished)
        self.worker.start()
        if manual:
            self.window.status('正在检查新版本…')
        if self.settingsDialog:
            self.settingsDialog.setBusy(True)
            self.settingsDialog.status.setText('正在连接 GitHub，检查最新正式版本…')

    def clear_worker(self):
        self.worker = None
        if self.settingsDialog:
            self.settingsDialog.setBusy(False)

    def cancel(self):
        self.cancelled = True
        self.startup.stop()
        if self.worker:
            self.worker.requestInterruption()
        if self.dialog and self.dialog.worker:
            self.dialog.worker.requestInterruption()

    def failed(self, message):
        if not self.cancelled and not self.window._closePending:
            if self.settingsDialog:
                self.settingsDialog.status.setText(message)
                self.settingsDialog.refreshCache()
            if self.manual:
                self.window.status(message, 15000)
                self.show_cached_update()

    def rateLimited(self, error):
        settings = QSettings()
        try:
            previous = float(settings.value('updates/rateLimitBackoff', 0))
        except (ValueError, TypeError):
            previous = 0
        delay = min(3600, max(60, previous * 2 if math.isfinite(previous) else 60))
        error = UpdateRateLimit(max(error.retry_at, time.time() + delay))
        settings.setValue('updates/rateLimitBackoff', delay)
        settings.setValue('updates/retryAt', error.retry_at)
        self.failed(str(error))

    def finished(self, info):
        if self.cancelled or self.window._closePending:
            return
        if info:
            save_cached_release(info)
            QSettings().remove('updates/retryAt')
            QSettings().remove('updates/rateLimitBackoff')
            if self.settingsDialog:
                self.settingsDialog.refreshCache()
                self.settingsDialog.status.setText('发现新版本 %s，可查看日志并下载更新。' % info['version'])
            self.show_update(info)
        else:
            QSettings().remove('updates/availableRelease')
            QSettings().remove('updates/retryAt')
            QSettings().remove('updates/rateLimitBackoff')
            if self.settingsDialog:
                self.settingsDialog.refreshCache()
                self.settingsDialog.status.setText('当前版本 %s，未发现更高的正式版本。' % APP_VERSION)
            if self.manual:
                self.window.status('当前版本 %s，未发现更高的正式版本' % APP_VERSION, 10000)

    def show_cached_update(self):
        info = load_cached_release()
        if info:
            self.show_update(info)

    def open_download(self, url):
        worker = BrowserLauncher(url, self.window)
        self.window._workers.add(worker)
        worker.failed.connect(lambda message: self.window.status(message + '；可复制下载链接。', 15000))
        worker.finished.connect(self.window.workerFinished)
        worker.start()

    def show_update(self, info):
        if self.dialog and (self.dialog.worker or self.dialog.info['version'] == info['version']):
            self.dialog.show()
            self.dialog.raise_()
            self.dialog.activateWindow()
            return
        if self.dialog:
            self.dialog.close()
            self.dialog.deleteLater()
        self.dialog = UpdateDialog(self, info)
        self.dialog.show()

    def launch_pending_installer(self):
        if not self.pending_installer:
            return False
        launch_installer_after_exit(*self.pending_installer)
        self.pending_installer = None
        return True

    def show_settings(self):
        if self.settingsDialog is None:
            self.settingsDialog = UpdateSettingsDialog(self)
        self.settingsDialog.enabled.setChecked(QSettings().value('updates/enabled', True, type=bool))
        self.settingsDialog.refreshCache()
        self.settingsDialog.setBusy(self.worker is not None)
        self.settingsDialog.show()
        self.settingsDialog.raise_()
        self.settingsDialog.activateWindow()
