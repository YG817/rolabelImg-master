def test_startup(window):
    assert window.formatCombo.currentIndex() == 0
    assert not window.usingPascalVocFormat


def test_reopening_windows_keeps_global_style_alive(window, app):
    """Window styles and popups must survive closing/reopening another window."""
    from PyQt5 import sip
    from PyQt5.QtCore import QCoreApplication, QEvent
    from PyQt5.QtGui import QPalette
    import roLabelImg

    style = app.style()
    assert app.palette().color(QPalette.Highlight).name() == '#346bd1'
    window.guideAction.trigger()
    for _ in range(6):
        reopened = roLabelImg.MainWindow()
        try:
            reopened.show()
            app.processEvents()
            assert not sip.isdeleted(style)
            assert app.style() is style
            assert window._guideDialog.isVisible()
            assert reopened.styleSheet() == window.styleSheet()
        finally:
            reopened.dirty = False
            reopened.close()
            reopened.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        assert sip.isdeleted(reopened)
    window._guideDialog.close()


def test_deleting_window_cancels_pending_callbacks(window, app):
    from PyQt5 import sip
    from PyQt5.QtCore import QCoreApplication, QEvent, QPointF
    import roLabelImg

    reopened = roLabelImg.MainWindow()
    calls = []
    reopened.queueEvent(lambda: calls.append('called'))
    reopened.centerOnImagePoint(QPointF(10, 10))
    reopened.close()
    reopened.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    assert sip.isdeleted(reopened)
    assert calls == []
