import os
import sys
import tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'libs'))
import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QSettings, QStandardPaths, QCoreApplication, QEvent
from PyQt5.QtTest import QTest
from PyQt5.QtGui import QFontDatabase

@pytest.fixture(scope='session')
def app():
    application = QApplication.instance() or QApplication([])
    # Windows' offscreen plugin does not enumerate system fonts. Use installed
    # fonts so geometry assertions exercise real text instead of empty glyphs.
    if not QFontDatabase().families():
        for path in ('C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/msyh.ttc'):
            if Path(path).is_file():
                QFontDatabase.addApplicationFont(path)
    application.setApplicationName('roLabelImg-regression')
    application.setQuitOnLastWindowClosed(False)
    QStandardPaths.setTestModeEnabled(True)
    with tempfile.TemporaryDirectory() as directory:
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, directory)
        yield application

@pytest.fixture
def window(app, tmp_path, monkeypatch):
    import roLabelImg
    from label_store import LabelStore
    monkeypatch.setattr(roLabelImg, 'LabelStore', lambda: LabelStore(str(tmp_path / 'labels.json')))
    QSettings().clear()
    win = roLabelImg.MainWindow()
    win.show()
    app.processEvents()
    try:
        yield win
    finally:
        win.dirty = False
        win.close()
        wait_until(lambda: not win._workers)
        win.close()
        win.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

def wait_until(predicate, timeout=10000):
    import time
    start = time.monotonic()
    while not predicate():
        if time.monotonic() - start > timeout / 1000:
            raise AssertionError('Timed out')
        QTest.qWait(10)
