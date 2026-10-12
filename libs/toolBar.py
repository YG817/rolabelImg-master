try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *


class ToolBar(QToolBar):

    def __init__(self, title):
        super(ToolBar, self).__init__(title)
        layout = self.layout()
        m = (0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setContentsMargins(*m)
        self.setContentsMargins(*m)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.layout().setSizeConstraint(QLayout.SetNoConstraint)
        self.setMinimumWidth(0)
        self._compact = False
        self._expandedWidth = 130

    def addAction(self, action):
        if isinstance(action, QWidgetAction):
            widget = action.defaultWidget()
            if widget:
                widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
                action.setVisible(not self._compact)
            return super(ToolBar, self).addAction(action)
        btn = ToolButton()
        btn.setDefaultAction(action)
        btn.setToolButtonStyle(self.toolButtonStyle())
        self.addWidget(btn)

    def minimumSizeHint(self):
        return QSize(46, super().minimumSizeHint().height())

    def measureExpandedWidth(self):
        widths = []
        for button in self.activeButtons():
            previous = button.toolButtonStyle()
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            widths.append(button.sizeHint().width())
            button.setToolButtonStyle(previous)
        for action in self.actions():
            if isinstance(action, QWidgetAction):
                widget = action.defaultWidget()
                if widget is not None and not isinstance(widget, ToolButton):
                    widths.append(widget.minimumSizeHint().width())
        margin = self.style().pixelMetric(QStyle.PM_ToolBarItemMargin, None, self)
        frame = self.style().pixelMetric(QStyle.PM_ToolBarFrameWidth, None, self)
        self._expandedWidth = max(58, max(widths or [36]) + 2 * (margin + frame))
        return self._expandedWidth

    def activeButtons(self):
        return [action.defaultWidget() for action in self.actions() if isinstance(action, QWidgetAction)
                and isinstance(action.defaultWidget(), ToolButton)]

    def updatePresentation(self):
        self._compact = self.width() < self._expandedWidth
        style = Qt.ToolButtonIconOnly if self._compact else Qt.ToolButtonTextBesideIcon
        self.setToolButtonStyle(style)
        for button in self.activeButtons():
            button.setToolButtonStyle(style)
        for action in self.actions():
            if isinstance(action, QWidgetAction) and not isinstance(action.defaultWidget(), ToolButton):
                action.setVisible(not self._compact)
                if action.defaultWidget() is not None:
                    action.defaultWidget().setVisible(not self._compact)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updatePresentation()


class ToolButton(QToolButton):
    """ToolBar companion class which ensures all buttons have the same size."""
    minSize = (36, 34)

    def minimumSizeHint(self):
        ms = super(ToolButton, self).minimumSizeHint()
        h1 = ms.height()
        w2, h2 = self.minSize
        return QSize(w2, max(h1, h2))
