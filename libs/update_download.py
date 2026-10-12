"""Stream Windows release assets without blocking the GUI."""
import base64
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PyQt5.QtCore import QThread, pyqtSignal
from app_version import APP_VERSION, GITHUB_OWNER, GITHUB_REPO, installer_name


class DownloadCancelled(Exception):
    pass


def validate_download(info):
    version = info['version']
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version):
        raise ValueError('更新版本号无效')
    name = installer_name(version)
    expected = f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/v{version}/{name}'
    if info['url'] != expected:
        raise ValueError('安装包下载地址不属于配置的发布仓库')
    size = info.get('size', 0)
    if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= 2 * 1024**3:
        raise ValueError('安装包大小无效，请重新检查更新')
    digest = info.get('sha256')
    if digest is not None and not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('安装包校验值无效')
    return name, size, digest


def validate_response_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in (
            'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'):
        raise ValueError('下载重定向到非 GitHub 地址，已停止下载')


class InstallerDownload(QThread):
    progress = pyqtSignal(object, object, float)
    result = pyqtSignal(str, str)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    phase = pyqtSignal(str)

    def __init__(self, info, directory, parent=None):
        super().__init__(parent)
        self.info = dict(info)
        self.directory = Path(directory)

    def check_cancelled(self):
        if self.isInterruptionRequested():
            raise DownloadCancelled()

    def run(self):
        temporary = None
        try:
            name, total, expected_digest = validate_download(self.info)
            self.check_cancelled()
            self.directory.mkdir(parents=True, exist_ok=True)
            destination = self.directory / name
            if expected_digest and destination.is_file() and destination.stat().st_size == total:
                self.phase.emit('正在核验已下载的安装包…')
                existing_digest = hashlib.sha256()
                with destination.open('rb') as stream:
                    header = stream.read(2)
                    stream.seek(0)
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        self.check_cancelled()
                        existing_digest.update(chunk)
                self.check_cancelled()
                if header == b'MZ' and existing_digest.hexdigest() == expected_digest:
                    self.progress.emit(total, total, 0)
                    self.result.emit(str(destination), expected_digest)
                    return
            self.phase.emit('正在连接 GitHub，下载安装包…')
            fd, temporary = tempfile.mkstemp(prefix=name + '.', suffix='.part', dir=self.directory)
            digest = hashlib.sha256()
            downloaded = 0
            started = last_progress = time.monotonic()
            self.progress.emit(0, total, 0)
            with os.fdopen(fd, 'wb') as output:
                request = Request(self.info['url'], headers={'User-Agent': 'roLabelImg/' + APP_VERSION,
                                                             'Accept': 'application/octet-stream'})
                with urlopen(request, timeout=10) as response:
                    validate_response_url(response.geturl())
                    length = response.headers.get('Content-Length')
                    if length is not None and int(length) != total:
                        raise ValueError('下载大小与发布信息不一致，请重新检查更新')
                    while True:
                        self.check_cancelled()
                        chunk = response.read(128 * 1024)
                        if not chunk:
                            break
                        downloaded += len(chunk)
                        if downloaded > total:
                            raise ValueError('安装包大小超出发布信息，已停止下载')
                        output.write(chunk)
                        digest.update(chunk)
                        now = time.monotonic()
                        if now - last_progress >= 0.1 or downloaded == total:
                            self.progress.emit(downloaded, total, downloaded / max(now - started, 0.001))
                            last_progress = now
                output.flush()
                os.fsync(output.fileno())
            self.check_cancelled()
            if downloaded != total:
                raise ValueError('安装包下载不完整，请重试')
            actual_digest = digest.hexdigest()
            if expected_digest and actual_digest != expected_digest:
                raise ValueError('安装包 SHA-256 校验失败，请重新下载')
            with open(temporary, 'rb') as stream:
                if stream.read(2) != b'MZ':
                    raise ValueError('下载内容不是 Windows 安装程序，请重试')
            os.replace(temporary, destination)
            temporary = None
            self.progress.emit(total, total, downloaded / max(time.monotonic() - started, 0.001))
            self.result.emit(str(destination), actual_digest)
        except DownloadCancelled:
            self.cancelled.emit()
        except Exception as exc:
            if self.isInterruptionRequested():
                self.cancelled.emit()
            else:
                self.failed.emit('下载失败：%s' % exc)
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass


def launch_installer_after_exit(path, digest):
    """A hidden helper waits for this process to exit before opening Setup."""
    if os.name != 'nt':
        raise OSError('安装更新仅支持 Windows')
    path = Path(path).resolve(strict=True)
    if not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('安装包校验值无效')
    # Literal PowerShell strings escape apostrophes without shell interpolation.
    literal = str(path).replace("'", "''")
    script = (f'Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue; '
              f"if ((Get-FileHash -LiteralPath '{literal}' -Algorithm SHA256).Hash -ne '{digest}') {{ exit 1 }}; "
              f"Start-Process -FilePath '{literal}'")
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    subprocess.Popen([str(powershell), '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden',
                      '-EncodedCommand', encoded], creationflags=subprocess.CREATE_NO_WINDOW,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
