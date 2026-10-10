"""GitHub release metadata checks; downloads and installation remain manual."""
import json
import re
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from PyQt5.QtCore import QObject, QSettings, QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, QTextBrowser,
                            QLineEdit, QCheckBox, QDialogButtonBox, QApplication)
from app_version import APP_VERSION, GITHUB_OWNER, GITHUB_REPO, LATEST_RELEASE_API, installer_name
try:
    from .browser_launcher import BrowserLauncher
except ImportError:
    from browser_launcher import BrowserLauncher


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
            return dict(version=version, url=url, notes=str(data.get('body') or '')[:16000])
    raise ValueError('新版本尚未提供匹配的 Windows x64 安装包，请稍后检查')


def fetch_latest(url=LATEST_RELEASE_API):
    request = Request(url, headers={'Accept': 'application/vnd.github+json',
        'User-Agent': 'roLabelImg/' + APP_VERSION, 'X-GitHub-Api-Version': '2026-03-10'})
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('版本信息过大')
        return release_information(json.loads(raw))
    except HTTPError as exc:
        if exc.code == 404:
            raise ValueError('发布仓库尚无可访问的正式版本，请确认仓库公开且已发布 Release') from exc
        if exc.code in (403, 429):
            raise ValueError('GitHub 检查次数受限，请稍后重试') from exc
        raise ValueError('GitHub 返回错误 HTTP %s' % exc.code) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError('无法连接 GitHub，或请求超时。可稍后手动检查更新。') from exc


class ReleaseWorker(QThread):
    result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def run(self):
        try:
            info = fetch_latest()
            if not self.isInterruptionRequested():
                self.result.emit(info)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))


class UpdateController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.worker = None
        self.manual = False
        self.cancelled = False
        self.startup = QTimer(self)
        self.startup.setSingleShot(True)
        self.startup.timeout.connect(self.check)

    def schedule(self):
        self.startup.start(5000)

    def check(self, manual=False):
        if self.worker is not None or self.window._closePending:
            return
        settings = QSettings()
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
        self.worker.finished.connect(self.clear_worker)
        self.worker.finished.connect(self.window.workerFinished)
        self.worker.start()
        if manual:
            self.window.status('正在检查新版本…')

    def clear_worker(self):
        self.worker = None

    def cancel(self):
        self.cancelled = True
        self.startup.stop()
        if self.worker:
            self.worker.requestInterruption()

    def failed(self, message):
        if self.manual and not self.cancelled and not self.window._closePending:
            self.window.status(message, 15000)

    def finished(self, info):
        if self.cancelled or self.window._closePending:
            return
        if info:
            self.show_update(info)
        elif self.manual:
            self.window.status('当前版本 %s，未发现更高的正式版本' % APP_VERSION, 10000)

    def open_download(self, url):
        worker = BrowserLauncher(url, self.window)
        self.window._workers.add(worker)
        worker.failed.connect(lambda message: self.window.status(message + '；可复制下载链接。', 15000))
        worker.finished.connect(self.window.workerFinished)
        worker.start()

    def show_update(self, info):
        dialog = QDialog(self.window)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.setWindowTitle('发现新版本')
        dialog.resize(560, 410)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('当前 %s → 最新 %s' % (APP_VERSION, info['version'])))
        layout.addWidget(QLabel('先保存标注，下载完成后退出软件，再运行安装包升级。'))
        notes = QTextBrowser(dialog)
        notes.setPlainText(info['notes'] or '此版本未提供更新说明。')
        layout.addWidget(notes)
        link = QLineEdit(info['url'], dialog)
        link.setReadOnly(True)
        layout.addWidget(link)
        download = QPushButton('打开浏览器下载安装包', dialog)
        download.clicked.connect(lambda: self.open_download(info['url']))
        layout.addWidget(download)
        copy = QPushButton('复制下载链接', dialog)
        copy.clicked.connect(lambda: QApplication.clipboard().setText(info['url']))
        layout.addWidget(copy)
        close = QDialogButtonBox(QDialogButtonBox.Close, parent=dialog)
        close.rejected.connect(dialog.close)
        layout.addWidget(close)
        dialog.show()

    def show_settings(self):
        dialog = QDialog(self.window)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.setWindowTitle('版本与更新')
        dialog.resize(420, 190)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('roLabelImg %s · Windows x64' % APP_VERSION))
        enabled = QCheckBox('启动时检查更新（最多每天一次）', dialog)
        enabled.setChecked(QSettings().value('updates/enabled', True, type=bool))
        enabled.toggled.connect(lambda value: QSettings().setValue('updates/enabled', value))
        layout.addWidget(enabled)
        button = QPushButton('检查更新', dialog)
        button.clicked.connect(lambda: self.check(True))
        layout.addWidget(button)
        layout.addWidget(QLabel('更新由用户通过浏览器下载并运行安装包。'))
        close = QDialogButtonBox(QDialogButtonBox.Close, parent=dialog)
        close.rejected.connect(dialog.close)
        layout.addWidget(close)
        dialog.show()
