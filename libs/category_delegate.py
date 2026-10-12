"""Readable English category tiles with a compact color swatch."""
from PyQt5.QtCore import Qt, QSize, QRect, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPen
from PyQt5.QtWidgets import QStyledItemDelegate, QStyle, QTableWidget


class CategoryTable(QTableWidget):
    columnsChanged = pyqtSignal()

    def columnsForWidth(self):
        # The table's own width is stable when its scrollbar appears/disappears.
        return 2 if self.width() >= 340 else 1

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns = self.columnsForWidth()
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
        rect = option.rect.adjusted(2, 2, -2, -2)
        name = index.data(Qt.UserRole + 1)
        if not name:
            painter.restore()
            return
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        painter.setRenderHint(painter.Antialiasing)
        painter.setPen(QPen(QColor('#d3e1fa'), 1) if selected else Qt.NoPen)
        painter.setBrush(QColor('#edf3ff' if selected else '#f9fafb' if hovered else '#ffffff'))
        painter.drawRoundedRect(rect, 5, 5)
        color = QColor(index.data(Qt.UserRole + 2))
        painter.setPen(QPen(color.darker(115), 1))
        painter.setBrush(color)
        painter.drawRoundedRect(rect.x() + 7, rect.center().y() - 6, 13, 13, 3, 3)
        text_rect = QRect(rect.x() + 29, rect.y(), rect.width() - 35, rect.height())
        font = painter.font()
        font.setWeight(QFont.Medium if selected else QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor('#243247'))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(name, Qt.ElideRight, text_rect.width()))
        painter.restore()
