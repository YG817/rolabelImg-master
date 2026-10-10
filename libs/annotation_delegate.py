"""Show a separate sequence for each category without changing label names."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QStyledItemDelegate


class AnnotationDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        ordinal = index.data(Qt.UserRole + 8)
        if ordinal is not None:
            option.text = '#%03d · %s%s' % (ordinal, option.text,
                                          ' [锁定]' if index.data(Qt.UserRole + 9) else '')
