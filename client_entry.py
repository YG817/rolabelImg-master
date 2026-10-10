"""Windows executable entry with persistent diagnostics and a frozen smoke test."""
import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'libs'))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test':
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from release_smoke import smoke_test
        return smoke_test(Path(sys.argv[2]), ROOT)
    log_dir = Path(os.environ.get('APPDATA', str(Path.home()))) / 'roLabelImg' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(
        log_dir / 'client.log', maxBytes=2 * 1024 * 1024, backupCount=3, encoding='utf-8')])
    def exception_handler(kind, value, trace):
        logging.error('Unhandled exception', exc_info=(kind, value, trace))
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.critical(None, '程序错误', '发生错误，请查看日志：\n%s' % (log_dir / 'client.log'))
    sys.excepthook = exception_handler
    mutex = None
    if os.name == 'nt' and getattr(sys, 'frozen', False):
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        mutex = kernel32.CreateMutexW(None, False, 'Local\\roLabelImg-running')
    try:
        import roLabelImg
        return roLabelImg.main(sys.argv)
    except Exception:
        logging.exception('Startup failed')
        from PyQt5.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, '启动失败', '请查看日志：\n%s' % (log_dir / 'client.log'))
        return 1
    finally:
        if mutex:
            kernel32.CloseHandle(mutex)


if __name__ == '__main__':
    sys.exit(main())
