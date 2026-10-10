"""Shared desktop styling; no external assets or theme packages required."""
from PyQt5.QtCore import Qt, QSize, QByteArray
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QPixmap, QPainter, QPen, QBrush
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QApplication, QStyle, QToolButton


STYLESHEET = '''
QMainWindow, QDialog { background: #f3f5f9; }
QWidget { color: #273449; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; }
QMenuBar { background: #ffffff; border-bottom: 1px solid #e1e6ee; padding: 5px; }
QMenuBar::item { padding: 5px 12px; border-radius: 4px; }
QMenuBar::item:selected, QMenu::item:selected { background: #e8f0ff; color: #245ac2; }
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


def style_label_item(item, color):
    """Readable names independent of the user-selected annotation color."""
    color = QColor(color)
    item.setForeground(QBrush(QColor('#243247')))
    font = item.font()
    font.setWeight(QFont.DemiBold)
    item.setFont(font)
    swatch = QPixmap(40, 40)
    swatch.fill(Qt.transparent)
    painter = QPainter(swatch)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor('#65758b'), 2))
    painter.setBrush(color)
    painter.drawRoundedRect(3, 3, 34, 34, 7, 7)
    painter.end()
    swatch.setDevicePixelRatio(2)
    item.setIcon(QIcon(swatch))
    item.setToolTip('%s · 类别颜色 %s' % (item.text(), color.name()))


def line_icon(paths):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
           '<g fill="none" stroke="#3c6596" stroke-width="1.7" stroke-linecap="round" '
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
    window.dock.setWindowTitle('标注与类别')
    window.filedock.setWindowTitle('影像列表')
    window.categoryGrid.setToolTip('点选类别后保留最近使用的绘制工具；首次默认旋转框，再点同一类别取消。')
    window.labelList.setToolTip('Ctrl / Shift 多选标注，再点击“删除所选”或按 Delete；小框也可在列表中直接选择')
    window.labelList.setSpacing(2)
    window.fileListWidget.setSpacing(2)
    window.fileListWidget.setToolTip('双击打开影像；A / D 切换上一张 / 下一张')
    window.formatCombo.setToolTip('当前影像的保存格式；COCO 保留旋转框四角坐标')
    window.zoomWidget.setToolTip('缩放比例 · Ctrl + 滚轮每格约放大 15% / 对应缩小，横纵滚动条始终可用')
    window.resizeDocks([window.dock, window.filedock], [720, 110], Qt.Vertical)
    if not window.settings.get('window/state', QByteArray()):
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
        '复制标注': '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 5V3H3v13h2"/>',
        '删除标注': '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
        '放大': '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M6 10h8m-4-4v8"/>',
        '缩小': '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M6 10h8"/>',
        '适应窗口': '<path d="M3 8V3h5m8 0h5v5M3 16v5h5m8 0h5v-5"/><rect x="7" y="7" width="10" height="10"/>',
        '适应宽度': '<path d="M3 3v18m18-18v18M5 12h14M8 9l-3 3 3 3m8-6 3 3-3 3"/>',
        '修改类别': '<path d="m4 16 12-12 4 4L8 20H4zm9-9 4 4"/>',
    }
    for action in window.findChildren(QAction):
        if action.text() in icons:
            action.setIcon(line_icon(icons[action.text()]))
