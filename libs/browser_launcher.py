"""Launch the system browser without blocking Qt's GUI thread."""
from PyQt5.QtCore import QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices


class BrowserLauncher(QThread):
    failed = pyqtSignal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            if not QDesktopServices.openUrl(QUrl(self.url)):
                self.failed.emit('系统未能打开默认浏览器。')
        except Exception as exc:
            self.failed.emit('启动浏览器失败：%s' % exc)
