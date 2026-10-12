"""Compact, local operation reference grouped by task."""
from html import escape
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QTabWidget, QTextBrowser, QDialogButtonBox
from ui_theme import ModernDialog as QDialog, ui_label


SECTIONS = [
    ('标注与编辑', '两种方式，按需选择',
     '先选类别 → 连续绘制，保留最近使用的工具（首次默认旋转框）；再点同一类别取消。<br>'
     '不选类别 → 按 W / E 画框，完成后选择或输入标签。', [
        ('W / E', '普通框 / 旋转框；再按一次退出绘制'),
        ('左键拖空白处', '新建标注框'),
        ('左键拖框内部', '移动已有框，连续绘制时也可使用'),
        ('左键拖四角', '调整标注框大小'),
        ('左键拖边中段', '只调整这一条边，对边固定；普通框和旋转框均支持'),
        ('左键拖圆形手柄', '旋转框；右键拖角点也可旋转'),
        ('右键双击标注框', '更改这个框的标签；选择已有类别或输入新类别，可撤销'),
        ('Ctrl / Shift + 点列表', '多选标注，再点“删除所选”或按 Delete'),
        ('Ctrl+B / 框选编辑', '拖出区域选中完整包含的可见标注；再按 Ctrl+B 或 Esc 退出'),
        ('Ctrl / Shift + 框选', '追加多个区域的标注；锁定框需先解锁再修改'),
        ('Ctrl+M / 修改所选', '批量修改类别、普通框或旋转框；可撤销、重做'),
        ('Ctrl+Z / Ctrl+D', '撤销操作 / 复制所选框'),
        ('Ctrl+Y', '重做上一次撤销的标注操作'),
        ('Ctrl + 左键拖动', '绘制状态下从已有框内部新建重叠目标'),
        ('Alt+Q', '鼠标指向重叠区域，循环选择标注框'),
        ('双击列表 / 锁定/解锁', '放大定位目标 / 防止移动、旋转与删除'),
        ('列表编号 / 底部总数', '各类别独立编号；总数随增删、撤销、重做更新'),
        ('Esc', '取消未完成的框或标签弹窗'),
        ('方向键 / Z X C V', '微移所选框 / 调整旋转角度'),
     ]),
    ('影像与视图', '看图、定位与缩放',
     '右下角显示当前影像；打开目录后显示目录及子目录中的影像。<br>'
     '双击条目切图，悬停查看完整路径。', [
        ('Ctrl+O / Ctrl+U', '打开单张影像 / 打开影像目录'),
        ('A / D', '上一张 / 下一张影像'),
        ('F2', '打开大图巡检：小地图跳转，手动记录分区检查进度'),
        ('Ctrl + 滚轮', '以鼠标为中心缩放，每格约放大 15%，缩小按对应比例'),
        ('滚轮 / Shift + 滚轮', '上下移动 / 左右移动；横纵滚动条始终可用'),
        ('F2 内恢复按钮', '恢复原始大小（100%），或显示整幅影像'),
        ('中键 / Alt + 左键拖动', '平移影像，可在标注框上使用'),
        ('按住空格 + 左键拖动', '临时切换小手平移，不修改标注；松开空格恢复'),
        ('Ctrl+F / Ctrl+Shift+F', '适应窗口 / 适应宽度'),
        ('Ctrl+=', '恢复 100% 比例'),
        ('Ctrl+Shift+P', '显示或隐藏右侧标注面板'),
        ('左侧工具栏右边缘', '收窄只显示图标；最大宽度刚好显示图标和文字'),
        ('右侧区域间分隔条', '上下调整列表空间或底部留白；标题、按钮和输入项间距不变'),
        ('R / N', '显示或隐藏旋转框 / 普通框'),
        ('中心经纬度 → 复制', '复制当前影像的 WGS84 中心坐标'),
     ]),
    ('文件与保存', '保存前确认格式与目录',
     '首次默认 COCO，后续记住格式；两种格式并存时读取较新标注。<br>'
     '有保存目录时，切图或退出自动保存；否则提供保存、放弃、取消。保存失败不会继续。<br>'
     '误删 JSON 后可直接重新保存；空 JSON 占位文件也可保存。未修复的损坏文件仍受保护。', [
        ('Ctrl+S', '保存当前影像的标注'),
        ('Ctrl+Shift+S', '标注另存为'),
        ('Ctrl+R', '设置标注保存目录'),
        ('Ctrl+Shift+O', '读取 JSON / XML 标注，需先打开对应影像'),
        ('确认并保存按钮', '将影像标记为已确认并保存'),
        ('管理标签与颜色', '新增、重命名、删除类别，或修改类别颜色'),
        ('Ctrl+W / Ctrl+Q', '关闭当前影像 / 退出软件'),
        ('F1', '打开这份操作快捷说明'),
        ('版本与更新 → 检查更新', '查看更新日志，在软件内下载；显示进度，可取消、重试'),
        ('下载完成 → 退出并安装', '先处理未保存标注，再退出软件启动 Windows 安装向导'),
     ]),
]


def create_quick_guide(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle('操作快捷说明')
    dialog.resize(760, 650)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(22, 18, 22, 16)
    layout.setSpacing(12)
    title = ui_label('操作快捷说明', 'dialogTitle')
    layout.addWidget(title)
    subtitle = ui_label('按操作分类查阅 · 此窗口可保持打开，不影响主窗口操作')
    layout.addWidget(subtitle)
    tabs = QTabWidget(dialog)
    tabs.setStyleSheet('QTabWidget::pane { border: none; } '
                      'QTabBar::tab { padding: 9px 20px; margin-right: 5px; background: #eef0f3; '
                      'color: #667085; border-top-left-radius: 6px; border-top-right-radius: 6px; } '
                      'QTabBar::tab:selected { background: #ffffff; color: #245bc1; }')
    for name, heading, intro, rows in SECTIONS:
        browser = QTextBrowser(tabs)
        browser.setStyleSheet('QTextBrowser { background: white; border: 1px solid #dfe5ee; padding: 12px; }')
        browser.setOpenExternalLinks(False)
        body = ''.join('<tr bgcolor="%s"><td width="43%%"><b>%s</b></td><td>%s</td></tr>' %
                       ('#f0f4fa' if index % 2 == 0 else '#ffffff', escape(key), escape(description))
                       for index, (key, description) in enumerate(rows))
        browser.setHtml('<html><body style="font-family: Microsoft YaHei UI; color: #273449; font-size: 13px;">'
                        '<h3 style="color: #245ac2;">%s</h3><p style="line-height: 150%%;">%s</p>'
                        '<table width="100%%" cellspacing="0" cellpadding="8">%s</table>'
                        '</body></html>' % (escape(heading), intro, body))
        tabs.addTab(browser, name)
    layout.addWidget(tabs)
    footer = QLabel('单字母快捷键请在画布中使用；输入标签时按键用于输入文字。')
    footer.setStyleSheet('color: #65758b; font-size: 12px;')
    layout.addWidget(footer)
    close = QDialogButtonBox(QDialogButtonBox.Close)
    close.button(QDialogButtonBox.Close).setText('关闭')
    close.rejected.connect(dialog.hide)
    layout.addWidget(close)
    return dialog
