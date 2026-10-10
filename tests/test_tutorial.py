import time
import pytest
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QDialog, QLineEdit
from conftest import wait_until


@pytest.mark.parametrize('result', [True, False, OSError('browser unavailable')])
def test_tutorial_async_and_failure_recovery(window, monkeypatch, result):
    from browser_launcher import QDesktopServices
    calls, beats = [], []

    def open_url(url):
        calls.append(url.toString())
        time.sleep(0.15)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(QDesktopServices, 'openUrl', open_url)
    timer = QTimer()
    timer.timeout.connect(lambda: beats.append(1))
    timer.start(10)
    window.tutorialAction.trigger()
    worker = window._tutorialWorker
    window.tutorial()
    assert window._tutorialWorker is worker
    assert not window.tutorialAction.isEnabled()
    wait_until(lambda: window._tutorialWorker is None)
    timer.stop()
    assert len(beats) >= 3
    assert calls == [window.screencast]
    assert window.tutorialAction.isEnabled()
    notices = window.findChildren(QDialog, 'tutorialError')
    if result is True:
        assert not notices
    else:
        assert len(notices) == 1
        assert not notices[0].isModal()
        assert window.screencast == notices[0].findChild(QLineEdit).text()
        notices[0].close()


def test_close_during_browser_launch(window, monkeypatch):
    from browser_launcher import QDesktopServices
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: (time.sleep(0.1) or False))
    window.tutorial()
    window.close()
    wait_until(lambda: not window._workers)
    assert not window.isVisible()
    assert not window.findChildren(QDialog, 'tutorialError')
