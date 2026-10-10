"""Readable English category tiles with a compact color swatch."""
from PyQt5.QtCore import Qt, QSize, QRect, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPen
from PyQt5.QtWidgets import QStyledItemDelegate, QStyle, QTableWidget


class CategoryTable(QTableWidget):
    columnsChanged = pyqtSignal()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns = 2 if self.viewport().width() >= 360 else 1
        if columns != self.columnCount():
            self.columnsChanged.emit()

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        toggle_off = event.button() == Qt.LeftButton and item is not None and item.isSelected()
        super().mousePressEvent(event)
        if toggle_off:
            self.clearSelection()
            self.setCurrentItem(None)


class CategoryDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(190, 38)

    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        painter.fillRect(rect, QColor('#dceaff' if selected else '#f0f5ff' if hovered else '#ffffff'))
        if selected:
            painter.setPen(QPen(QColor('#6292e8'), 1))
            painter.drawRect(rect.adjusted(1, 1, -2, -2))
        color = QColor(index.data(Qt.UserRole + 2))
        painter.setPen(QPen(QColor('#65758b'), 1))
        painter.setBrush(color)
        painter.drawRoundedRect(rect.x() + 8, rect.y() + 10, 18, 18, 4, 4)
        name = index.data(Qt.UserRole + 1) or ''
        text_rect = QRect(rect.x() + 34, rect.y() + 2, rect.width() - 40, rect.height() - 4)
        font = painter.font()
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor('#243247'))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(name, Qt.ElideRight, text_rect.width()))
        painter.restore()
