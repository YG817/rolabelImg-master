"""Shared desktop styling; no external assets or theme packages required."""
from PyQt5.QtCore import Qt, QSize, QByteArray, QPointF, QRect, QRectF
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QPixmap, QPainter, QPen, QBrush, QKeySequence
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import (QApplication, QStyle, QToolButton, QComboBox, QFrame,
                            QVBoxLayout, QLabel, QSizePolicy, QLayout, QListView,
                            QStyledItemDelegate, QMenu, QDialog, QDialogButtonBox,
                            QMenuBar, QProxyStyle)


STYLESHEET = '''
QMainWindow, QDialog { background: #f3f5f9; }
QWidget { color: #273449; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; }
QMenuBar { background: #ffffff; border-bottom: 1px solid #e1e6ee; padding: 5px; }
QMenu::item:selected { background: #e8f0ff; color: #245ac2; }
QMenu { background: white; border: 1px solid #dce3ed; padding: 6px; }
QMenu::item { padding: 7px 28px; }
QToolBar { background: #ffffff; border: none; border-right: 1px solid #e1e6ee; spacing: 3px; padding: 8px; }
QToolBar QToolButton { text-align: left; padding: 6px 8px; border: 1px solid transparent; border-radius: 6px; min-height: 24px; }
QToolButton:hover, QPushButton:hover { background: #eaf1ff; border-color: #b9cef4; }
QToolButton:pressed, QPushButton:pressed { background: #d9e7ff; }
QToolButton:checked { background: #e5eeff; color: #245ac2; border-color: #bdd0f6; }
QToolButton:disabled, QPushButton:disabled { color: #9aa6b6; }
QToolBar::separator { background: #e1e6ee; margin: 7px 4px; height: 1px; }
QDockWidget { font-weight: 600; border: none; }
QDockWidget::title { background: #edf1f7; padding: 10px 12px; border-bottom: 1px solid #dfe5ee; }
QListWidget { background: #ffffff; border: 1px solid #dfe5ee; border-radius: 6px; padding: 4px; outline: none; }
QListWidget::item { padding: 7px 6px; min-height: 20px; border-radius: 4px; }
QListWidget::item:hover { background: #f0f5ff; }
QListWidget::item:selected { background: #e3edff; color: #172b4d; border: 1px solid #aac4f3; }
QTableWidget#categoryGrid { background: #ffffff; border: 1px solid #dfe5ee; border-radius: 6px; gridline-color: transparent; outline: none; }
QTableWidget#categoryGrid::item { padding: 3px; color: #243247; border: 1px solid transparent; }
QTableWidget#categoryGrid::item:hover { background: #f0f5ff; }
QTableWidget#categoryGrid::item:selected { background: #dceaff; color: #172b4d; border: 1px solid #6292e8; }
QLineEdit, QComboBox, QDoubleSpinBox { background: #ffffff; border: 1px solid #ccd6e3; border-radius: 5px; padding: 6px 8px; min-height: 20px; selection-background-color: #3976db; }
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border-color: #3976db; }
QPushButton { background: #ffffff; border: 1px solid #ccd6e3; border-radius: 5px; padding: 7px 12px; }
QPushButton#labelManager { background: #346bd1; color: #ffffff; border-color: #346bd1; font-weight: 600; }
QPushButton#labelManager:hover { background: #2459b9; }
QCheckBox { spacing: 7px; padding: 3px 0; }
QStatusBar { background: #ffffff; border-top: 1px solid #dfe5ee; color: #627087; padding: 3px; }
QStatusBar::item { border: none; }
QScrollArea { border: none; }
QScrollBar:vertical { background: #edf1f6; width: 11px; margin: 0; }
QScrollBar:horizontal { background: #edf1f6; height: 11px; margin: 0; }
QScrollBar::handle { background: #b4c0d0; border-radius: 4px; min-width: 24px; min-height: 24px; }
QScrollBar::handle:hover { background: #8b9cb3; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QTextBrowser { background: #ffffff; border: 1px solid #dfe5ee; padding: 18px; }
QToolTip { background: #26354b; color: #ffffff; border: none; padding: 7px; }
'''

# Neutral surfaces and a single accent keep the image as the visual focus.
STYLESHEET += '''
QMainWindow, QDialog { background: #f6f7f9; }
QWidget { color: #344054; font-size: 13px; }
QLabel { color: #475467; background: transparent; font-weight: 400; }
QLabel[role="sectionTitle"] { color: #182230; font-size: 14px; font-weight: 600; }
QLabel[role="muted"] { color: #667085; font-size: 12px; }
QLabel[role="badge"] { color: #475467; background: #f2f4f7; border-radius: 5px; padding: 4px 8px; font-size: 12px; }
QLabel[role="dialogTitle"] { color: #182230; font-size: 21px; font-weight: 600; }
QFrame[role="panel"] { background: #ffffff; border: 1px solid #e4e7ec; border-radius: 9px; }
QFrame[role="divider"] { background: #eaecf0; border: none; max-height: 1px; }
QMenuBar { padding: 4px 8px; border-bottom: 1px solid #eaecf0; }
QToolBar { spacing: 1px; padding: 8px 6px; border-right: 1px solid #eaecf0; }
QToolBar QToolButton { padding: 5px 8px; border-radius: 6px; color: #475467; }
QToolButton:checked { background: #edf3ff; border-color: #d3e1fa; color: #245bc1; }
QDockWidget { font-weight: 400; }
QDockWidget::title { background: #f6f7f9; color: #475467; padding: 9px 14px; border: none; }
QPushButton { background: #ffffff; color: #344054; border: 1px solid #d0d5dd; border-radius: 6px; padding: 7px 12px; font-weight: 400; }
QPushButton:hover { background: #f9fafb; border-color: #98a2b3; }
QPushButton:pressed { background: #f2f4f7; }
QPushButton:disabled { background: #f9fafb; border-color: #eaecf0; color: #98a2b3; }
QPushButton[role="primary"] { background: #346bd1; color: #ffffff; border-color: #346bd1; font-weight: 600; }
QPushButton[role="primary"]:hover { background: #285cb9; border-color: #285cb9; }
QPushButton[role="primary"]:disabled { background: #e8eef8; border-color: #e8eef8; color: #98a8c2; }
QPushButton[role="quiet"] { background: #f9fafb; border-color: #eaecf0; color: #475467; }
QPushButton[role="danger"] { color: #b54747; }
QPushButton[role="danger"]:disabled { color: #98a2b3; }
QPushButton#labelManager { background: #ffffff; color: #475467; border-color: #d0d5dd; font-weight: 400; }
QPushButton#labelManager:hover { background: #f9fafb; }
QLineEdit, QComboBox, QDoubleSpinBox { background: #ffffff; color: #344054; border: 1px solid #d0d5dd; border-radius: 6px; padding: 7px 10px; min-height: 20px; }
QLineEdit:read-only { background: #f9fafb; color: #667085; }
QComboBox { padding-right: 30px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 28px; border: none; background: transparent; }
QComboBox::down-arrow { width: 8px; height: 8px; }
QComboBox[modern="true"]::down-arrow { image: none; width: 0px; height: 0px; }
QComboBox QLineEdit { border: none; background: transparent; padding: 0px; min-height: 0px; }
QComboBox QAbstractItemView { background: #ffffff; color: #344054; border: 1px solid #d0d5dd; padding: 5px; outline: none; selection-background-color: #edf3ff; selection-color: #245bc1; }
QComboBox QAbstractItemView::item { min-height: 30px; padding: 4px 8px; }
QListWidget { border: 1px solid #eaecf0; border-radius: 6px; padding: 3px; }
QListWidget::item { padding: 6px 8px; min-height: 22px; border: 1px solid transparent; }
QListWidget::item:selected { background: #edf3ff; border: 1px solid #d3e1fa; color: #245bc1; }
QTableWidget#categoryGrid { border: none; border-radius: 0px; padding: 0px; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar:horizontal { background: #f6f7f9; height: 8px; }
QScrollBar::handle { background: #cbd1da; border-radius: 4px; }
QScrollBar::handle:disabled { background: transparent; }
QMainWindow::separator { background: #eaecf0; width: 7px; height: 8px; }
QMainWindow::separator:hover { background: #c7d6ee; }
QSplitter#rightSections::handle { background: #f6f7f9; }
QSplitter#rightSections::handle:hover { background: #dce6f6; }
QDockWidget#ToolsDock { background: white; }
QStatusBar { border-top: 1px solid #eaecf0; color: #667085; }
QSpinBox { background: white; color: #344054; border: 1px solid #d0d5dd; border-radius: 6px; padding: 6px 26px 6px 10px; min-height: 20px; }
QSpinBox::up-button, QSpinBox::down-button { background: transparent; border: none; width: 22px; }
'''


class ComboOptionDelegate(QStyledItemDelegate):
    def __init__(self, combo):
        super().__init__(combo)
        self.combo = combo

    def sizeHint(self, option, index):
        return QSize(option.fontMetrics.horizontalAdvance(str(index.data() or '')) + 70,
                     max(36, option.fontMetrics.height() + 16))

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect.adjusted(3, 1, -3, -1)
        selected = str(index.data() or '') == self.combo.currentText()
        hovered = bool(option.state & (QStyle.State_Selected | QStyle.State_MouseOver))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#edf3ff' if selected else '#f5f7fb' if hovered else '#ffffff'))
        painter.drawRoundedRect(rect, 5, 5)
        left = rect.left() + 11
        color = index.data(Qt.UserRole + 2)
        if color:
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(left, rect.center().y() - 6, 12, 12), 3, 3)
            left += 23
        painter.setFont(option.font)
        painter.setPen(QColor('#245bc1' if selected else '#344054'))
        text_rect = QRect(left, rect.top(), max(0, rect.right() - 28 - left), rect.height())
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         option.fontMetrics.elidedText(str(index.data() or ''), Qt.ElideRight, text_rect.width()))
        if selected:
            x, y = rect.right() - 14, rect.center().y()
            painter.setPen(QPen(QColor('#346bd1'), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(QPointF(x - 4, y), QPointF(x - 1, y + 3))
            painter.drawLine(QPointF(x - 1, y + 3), QPointF(x + 5, y - 3))
        painter.restore()


class ModernComboBox(QComboBox):
    """A small outlined chevron replaces the native beveled arrow button."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setProperty('modern', True)
        self.setMaxVisibleItems(8)
        view = QListView(self)
        view.setUniformItemSizes(True)
        view.setMouseTracking(True)
        view.setSpacing(2)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setView(view)
        self.setItemDelegate(ComboOptionDelegate(self))

    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        popup.setObjectName('comboOptionsPopup')
        popup.setStyleSheet('QFrame#comboOptionsPopup { background: white; border: 1px solid #d0d5dd; '
                            'border-radius: 7px; } QListView { background: white; border: none; padding: 4px; } '
                            'QScrollBar:vertical { width: 8px; background: transparent; } '
                            'QScrollBar::handle:vertical { background: #cbd1da; border-radius: 4px; min-height: 24px; } '
                            'QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }')

    def setEditable(self, editable):
        super().setEditable(editable)
        if editable and self.completer():
            completion = self.completer().popup()
            if completion is None:
                return
            completion.setItemDelegate(ComboOptionDelegate(self))
            completion.setStyleSheet('QAbstractItemView { background: white; color: #344054; '
                                    'border: 1px solid #d0d5dd; padding: 4px; outline: none; }')
            if isinstance(completion, QListView):
                completion.setUniformItemSizes(True)
                completion.setSpacing(2)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor('#667085' if self.isEnabled() else '#b2bac6'), 1.5,
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        x, y = self.width() - 16, self.height() / 2
        painter.drawLine(QPointF(x - 4, y - 2), QPointF(x, y + 2))
        painter.drawLine(QPointF(x, y + 2), QPointF(x + 4, y - 2))
        painter.end()


def set_role(widget, role):
    widget.setProperty('role', role)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class ModernDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    def showEvent(self, event):
        translations = {'OK': '确定', 'Ok': '确定', 'Cancel': '取消', 'Close': '关闭',
                        'Apply': '应用', 'Save': '保存', 'Discard': '放弃'}
        for box in self.findChildren(QDialogButtonBox):
            for button in box.buttons():
                original = button.text().replace('&', '')
                if original in translations:
                    button.setText(translations[original])
        super().showEvent(event)


class NavigationStyle(QProxyStyle):
    """Reserve room for both menu icons and names; Fusion normally chooses one."""
    def __init__(self, parent):
        # Own a separate style, never Qt's shared application style.
        super().__init__('Fusion')
        self.setParent(parent)

    def sizeFromContents(self, kind, option, size, widget=None):
        if kind == QStyle.CT_MenuBarItem:
            text = option.text
            if not text and widget is not None and not option.icon.isNull():
                # QMenuBar clears option.text for icon actions before asking
                # its style for a size. Recover it from the owning action.
                text = next((a.text() for a in widget.actions()
                             if a.icon().cacheKey() == option.icon.cacheKey()), '')
            text = text.replace('&', '')
            return QSize(option.fontMetrics.horizontalAdvance(text) + 24 +
                         (26 if not option.icon.isNull() else 0), max(30, option.fontMetrics.height() + 12))
        return super().sizeFromContents(kind, option, size, widget)


class ModernMenuBar(QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._navigationStyle = NavigationStyle(self)
        self.setStyle(self._navigationStyle)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor('#ffffff'))
        painter.setPen(QColor('#eaecf0'))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        painter.setFont(self.font())
        for action in self.actions():
            if not action.isVisible():
                continue
            rect = self.actionGeometry(action)
            active = self.activeAction() is action
            if active:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor('#edf3ff'))
                painter.drawRoundedRect(rect, 5, 5)
            left = rect.left() + 12
            if not action.icon().isNull():
                action.icon().paint(painter, QRect(left, rect.center().y() - 9, 18, 18))
                left += 26
            painter.setPen(QColor('#245bc1' if active else '#344054'))
            painter.drawText(QRect(left, rect.top(), rect.right() - left - 10, rect.height()),
                             Qt.AlignLeft | Qt.AlignVCenter | Qt.TextShowMnemonic, action.text())
        painter.end()


class ModernMenu(QMenu):
    """Keep Qt menu behavior, with separate label and shortcut columns."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet('QMenu { background: white; color: #344054; border: 1px solid #d0d5dd; '
                           'padding: 5px; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; } '
                           'QMenu::item { padding: 8px 14px 8px 34px; } '
                           'QMenu::separator { height: 1px; background: #eaecf0; margin: 5px 12px; }')
        self.aboutToShow.connect(self.prepareLayout)

    @staticmethod
    def label(action):
        import re
        return re.sub(r'&(.)', r'\1', action.text().split('\t')[0].replace('&&', '\0')).replace('\0', '&').replace('\n', ' ')

    @staticmethod
    def shortcutText(action):
        return action.shortcut().toString(QKeySequence.NativeText)

    def prepareLayout(self):
        metrics = self.fontMetrics()
        actions = [a for a in self.actions() if a.isVisible() and not a.isSeparator()]
        label_width = max([metrics.horizontalAdvance(self.label(a)) for a in actions] or [0])
        shortcut_width = max([metrics.horizontalAdvance(self.shortcutText(a)) for a in actions] or [0])
        screen = self.screen().availableGeometry()
        self.setMinimumWidth(min(screen.width() - 24, max(220, label_width + shortcut_width + 110)))

    def textRects(self, action):
        rect = self.actionGeometry(action)
        shortcut_width = max([self.fontMetrics().horizontalAdvance(self.shortcutText(a))
                              for a in self.actions() if a.isVisible()] or [0])
        right = rect.right() - 20
        shortcut = QRect(right - shortcut_width, rect.top(), shortcut_width, rect.height())
        label = QRect(rect.left() + 37, rect.top(), max(0, shortcut.left() - 26 - rect.left() - 37), rect.height())
        return label, shortcut

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor('#ffffff'))
        painter.setPen(QPen(QColor('#d0d5dd'), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        for action in self.actions():
            if not action.isVisible():
                continue
            rect = self.actionGeometry(action)
            if action.isSeparator():
                painter.setPen(QPen(QColor('#eaecf0'), 1))
                painter.drawLine(rect.left() + 12, rect.center().y(), rect.right() - 12, rect.center().y())
                continue
            active = self.activeAction() is action and action.isEnabled()
            if active:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor('#edf3ff'))
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 5, 5)
            color = QColor('#245bc1' if active else '#344054' if action.isEnabled() else '#98a2b3')
            icon_rect = QRect(rect.left() + 10, rect.center().y() - 9, 18, 18)
            if action.isCheckable() and action.isChecked():
                painter.setPen(QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                painter.drawLine(icon_rect.left() + 3, icon_rect.center().y(), icon_rect.left() + 7, icon_rect.bottom() - 3)
                painter.drawLine(icon_rect.left() + 7, icon_rect.bottom() - 3, icon_rect.right() - 1, icon_rect.top() + 3)
            elif not action.icon().isNull():
                action.icon().paint(painter, icon_rect, Qt.AlignCenter,
                                    QIcon.Normal if action.isEnabled() else QIcon.Disabled)
            label_rect, shortcut_rect = self.textRects(action)
            painter.setFont(self.font())
            painter.setPen(color)
            painter.drawText(label_rect, Qt.AlignLeft | Qt.AlignVCenter,
                             self.fontMetrics().elidedText(self.label(action), Qt.ElideRight, label_rect.width()))
            painter.setPen(QColor('#667085' if action.isEnabled() else '#b2bac6'))
            painter.drawText(shortcut_rect, Qt.AlignRight | Qt.AlignVCenter, self.shortcutText(action))
            if action.menu():
                x, y = rect.right() - 8, rect.center().y()
                painter.setPen(QPen(color, 1.5, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(QPointF(x - 2, y - 3), QPointF(x + 1, y))
                painter.drawLine(QPointF(x + 1, y), QPointF(x - 2, y + 3))
        painter.end()


def panel():
    frame = QFrame()
    frame.setProperty('role', 'panel')
    frame.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(9)
    layout.setSizeConstraint(QLayout.SetNoConstraint)
    return frame, layout


def ui_label(text, role='muted'):
    label = QLabel(text)
    label.setProperty('role', role)
    label.setWordWrap(True)
    if role == 'badge':
        label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
    return label


def style_label_item(item, color):
    """Readable names independent of the user-selected annotation color."""
    color = QColor(color)
    item.setForeground(QBrush(QColor('#243247')))
    font = item.font()
    font.setWeight(QFont.Normal)
    item.setFont(font)
    swatch = QPixmap(40, 40)
    swatch.fill(Qt.transparent)
    painter = QPainter(swatch)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(color).darker(115), 1))
    painter.setBrush(color)
    painter.drawRoundedRect(8, 8, 24, 24, 5, 5)
    painter.end()
    swatch.setDevicePixelRatio(2)
    item.setIcon(QIcon(swatch))
    item.setToolTip('%s · 类别颜色 %s' % (item.text(), color.name()))


def line_icon(paths):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
           '<g fill="none" stroke="#667085" stroke-width="1.7" stroke-linecap="round" '
           'stroke-linejoin="round">' + paths + '</g></svg>')
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def initialize_application_theme():
    """Initialize shared Qt style before creating widgets, once per application."""
    app = QApplication.instance()
    if app is None:
        raise RuntimeError('Create QApplication before initializing the theme')
    if app.property('roLabelImgThemeInitialized'):
        return
    # Replacing the application style deletes the previous QStyle and repolishes
    # every widget, including closed windows awaiting destruction. Never repeat
    # this for each MainWindow: Qt's Windows style caches can retain old pointers.
    app.setStyle('Fusion')
    app.setFont(QFont('Microsoft YaHei UI', 10))
    # Explicit light palette also keeps native popups legible in Windows dark mode.
    palette = app.style().standardPalette()
    palette.setColor(QPalette.Highlight, QColor('#346bd1'))
    palette.setColor(QPalette.HighlightedText, QColor('#ffffff'))
    app.setPalette(palette)
    app.setProperty('roLabelImgThemeInitialized', True)


def apply_theme(window):
    initialize_application_theme()
    window.setStyleSheet(STYLESHEET)
    window.setMinimumSize(960, 640)
    window.dock.setMinimumWidth(0)
    window.filedock.setMinimumWidth(0)
    window.dock.setWindowTitle('标注工作区')
    window.filedock.setWindowTitle('影像列表')
    window.categoryGrid.setToolTip('点选类别后保留最近使用的绘制工具；首次默认旋转框，再点同一类别取消。')
    window.labelList.setToolTip('Ctrl / Shift 多选标注，再点击“删除所选”或按 Delete；小框也可在列表中直接选择')
    window.labelList.setSpacing(2)
    window.fileListWidget.setSpacing(2)
    window.fileListWidget.setToolTip('双击打开影像；A / D 切换上一张 / 下一张')
    window.formatCombo.setToolTip('当前影像的保存格式；COCO 保留旋转框四角坐标')
    window.zoomWidget.setToolTip('缩放比例 · Ctrl + 滚轮每格约放大 15% / 对应缩小，横纵滚动条始终可用')
    if not window.settings.get('window/state', QByteArray()):
        window.resizeDocks([window.dock, window.filedock], [720, 110], Qt.Vertical)
        window.resizeDocks([window.dock], [420], Qt.Horizontal)
    # Compact labels keep every main tool accessible without the old tall buttons.
    names = {'&Open': '打开影像', '&Open Dir': '打开目录', '&Next Image': '下一张',
             '&Prev Image': '上一张', '&Verify Image': '确认并保存', '&Save': '保存标注',
             '&Save As': '另存为', '&Close': '关闭影像', '&Quit': '退出',
             'Create\nRectBox': '普通矩形', 'Create\nRotatedRBox': '旋转矩形',
             '&Edit\nRectBox': '编辑标注', 'Delete\nRectBox': '删除标注',
             '&Duplicate\nRectBox': '复制标注',
             'Zoom &In': '放大', '&Zoom Out': '缩小', '&Original size': '原始比例',
             '&Fit Window': '适应窗口', 'Fit &Width': '适应宽度',
             '&Advanced Mode': '高级模式', '&Hide\nRectBox': '隐藏全部标注',
             '&Show\nRectBox': '显示全部标注', '&Tutorial': '视频教程',
             '&Open Annotation': '打开标注文件',
             '&Change default saved Annotation dir': '设置标注保存目录',
             'Show/Hide Label Panel': '显示／隐藏标注面板',
             'Box &Line Color': '默认边框颜色', 'Box &Fill Color': '默认填充颜色',
             'Shape &Line Color': '当前框边框颜色', 'Shape &Fill Color': '当前框填充颜色'}
    from PyQt5.QtWidgets import QAction
    for action in window.findChildren(QAction):
        if action.text() in names:
            action.setText(names[action.text()])
            key = action.shortcut().toString()
            action.setToolTip(action.text() + ('  ·  ' + key if key else ''))
    for menu, title in [(window.menus.file, '文件'), (window.menus.edit, '编辑'),
                        (window.menus.view, '视图'), (window.menus.help, '帮助')]:
        menu.setTitle(title)
    window.tools.setIconSize(QSize(20, 20))
    window.tools.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    for button in window.tools.findChildren(QToolButton):
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    icons = {
        '打开影像': '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m4 18 5-6 4 4 3-4 5 6"/>',
        '打开目录': '<path d="M3 7V5h7l2 3h9v12H3V7zm0 4h18"/>',
        '下一张': '<path d="M4 12h15m-6-6 6 6-6 6"/>',
        '上一张': '<path d="M20 12H5m6-6-6 6 6 6"/>',
        '确认并保存': '<circle cx="12" cy="12" r="9"/><path d="m7 12 3 3 7-7"/>',
        '保存标注': '<path d="M4 3h13l3 3v15H4zM8 3v6h8V3M8 21v-7h8v7"/>',
        '普通矩形': '<rect x="4" y="5" width="16" height="14" rx="1"/><path d="M2 5h4M4 3v4m14 12h4m-2-2v4"/>',
        '旋转矩形': '<path d="m3 8 14-5 4 13-14 5zM3 3h5M3 3v5"/>',
        '框选编辑': '<path d="M3 8V3h5m8 0h5v5M3 16v5h5m8 0h5v-5"/><path stroke-dasharray="2 2" d="M7 7h10v10H7z"/>',
        '修改所选标注': '<path d="m4 16 12-12 4 4L8 20H4zm9-9 4 4"/>',
        '复制标注': '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 5V3H3v13h2"/>',
        '删除标注': '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
        '放大': '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M6 10h8m-4-4v8"/>',
        '缩小': '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M6 10h8"/>',
        '适应窗口': '<path d="M3 8V3h5m8 0h5v5M3 16v5h5m8 0h5v-5"/><rect x="7" y="7" width="10" height="10"/>',
        '适应宽度': '<path d="M3 3v18m18-18v18M5 12h14M8 9l-3 3 3 3m8-6 3 3-3 3"/>',
        '修改类别': '<path d="m4 16 12-12 4 4L8 20H4zm9-9 4 4"/>',
        '撤销': '<path d="m8 5-5 5 5 5M3 10h10a6 6 0 0 1 0 12"/>',
        '重做': '<path d="m16 5 5 5-5 5m5-5H11a6 6 0 0 0 0 12"/>',
        '默认边框颜色': '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 8h8v8H8z"/>',
        '默认填充颜色': '<path d="m4 13 8-8 8 8-8 8zM7 4l5 5m-8 4h16"/>',
        '当前框边框颜色': '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 8h8v8H8z"/>',
        '当前框填充颜色': '<path d="m4 13 8-8 8 8-8 8zM7 4l5 5m-8 4h16"/>',
        '关闭影像': '<path d="m6 6 12 12M6 18 18 6"/>',
        '退出': '<path d="M10 3H4v18h6m3-15 6 6-6 6m-5-6h13"/>',
        '打开标注文件': '<path d="M5 3h10l4 4v14H5zM15 3v5h4M8 12h8m-8 4h6"/>',
        '设置标注保存目录': '<path d="M3 7V5h7l2 3h9v12H3zM8 14h8m-4-4v8"/>',
    }
    for action in window.findChildren(QAction):
        if action.text() in icons:
            action.setIcon(line_icon(icons[action.text()]))
    navigation = [
        (window.menus.file.menuAction(), '<path d="M5 3h10l4 4v14H5zM15 3v5h4M8 12h8m-8 4h6"/>'),
        (window.menus.edit.menuAction(), '<path d="m4 16 12-12 4 4L8 20H4zm9-9 4 4"/>'),
        (window.menus.view.menuAction(), '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'),
        (window.guideAction, '<circle cx="12" cy="12" r="9"/><path d="M9 8a3 3 0 0 1 6 1c0 2-3 2-3 4m0 3h.01"/>'),
        (window.updateAction, '<path d="M20 7a9 9 0 0 0-15-2L3 7m0-5v5h5M4 17a9 9 0 0 0 15 2l2-2m0 5v-5h-5"/>')]
    for action, paths in navigation:
        action.setIcon(line_icon(paths))
    window.constrainToolsWidth()
