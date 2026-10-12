"""Scrollable image workspace and narrow, responsive dock controls."""
from PyQt5.QtCore import Qt, QSize, QEvent, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QBoxLayout, QScrollArea, QSizePolicy, QLayout, QLabel,
                            QLineEdit, QComboBox, QSplitter, QSplitterHandle)
from PyQt5.QtGui import QPainter, QColor, QPen


class SectionHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setToolTip('上下拖动，调整相邻区域的高度')

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(QColor('#b8c4d3'), 2, Qt.SolidLine, Qt.RoundCap))
        center = self.rect().center()
        painter.drawLine(center.x() - 14, center.y(), center.x() + 14, center.y())


class SectionSplitter(QSplitter):
    def createHandle(self):
        return SectionHandle(self.orientation(), self)


class ImageScrollArea(QScrollArea):
    viewportResized = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setWidgetResizable(False)
        self.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.viewport() and event.type() == QEvent.Resize:
            self.viewportResized.emit()
        return super().eventFilter(watched, event)


class ResponsiveRow(QWidget):
    def __init__(self, controls):
        super().__init__()
        self.row = QBoxLayout(QBoxLayout.LeftToRight, self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSizeConstraint(QLayout.SetNoConstraint)
        for control in controls:
            self.row.addWidget(control, 1 if isinstance(control, (QLineEdit, QComboBox)) else 0)
        self.setMinimumWidth(0)
        # Rows are fixed controls; only lists or a trailing spacer grow vertically.
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    def resizeEvent(self, event):
        needed = 0
        for i in range(self.row.count()):
            control = self.row.itemAt(i).widget()
            needed += (control.fontMetrics().horizontalAdvance(control.text())
                       if isinstance(control, QLabel) else control.minimumSizeHint().width())
        needed += self.row.spacing() * (self.row.count() - 1)
        direction = QBoxLayout.TopToBottom if self.width() < needed else QBoxLayout.LeftToRight
        if self.row.direction() != direction:
            self.row.setDirection(direction)
            self.updateGeometry()
        super().resizeEvent(event)

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())


class PanelScrollArea(QScrollArea):
    def __init__(self, content):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(content)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)

    def minimumSizeHint(self):
        return QSize(0, 0)
