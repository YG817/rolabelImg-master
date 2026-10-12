"""A compact, neutral form for the existing batch annotation operation."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox
from ui_theme import ModernComboBox, ModernDialog as QDialog, panel, ui_label, set_role


class BatchEditDialog(QDialog):
    def __init__(self, parent, count, locked_count, categories):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowTitle('批量编辑标注')
        self.resize(480, 380)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(16)
        heading = QHBoxLayout()
        heading.addWidget(ui_label('编辑所选标注', 'dialogTitle'), 1)
        heading.addWidget(ui_label('%d 个标注' % count, 'badge'))
        layout.addLayout(heading)
        layout.addWidget(ui_label('更改仅应用于当前选中的标注。'))
        body, fields = panel()
        fields.setContentsMargins(16, 16, 16, 16)
        fields.setSpacing(8)
        fields.addWidget(ui_label('标注类别', 'sectionTitle'))
        self.category = ModernComboBox(body)
        self.category.setEditable(True)
        self.category.addItems(categories)
        colors = {entry['name']: entry['color'] for entry in parent.labelStore.entries}
        for index, name in enumerate(categories):
            if name in colors:
                self.category.setItemData(index, colors[name], Qt.UserRole + 2)
        self.category.setCurrentIndex(-1)
        self.category.lineEdit().setPlaceholderText('保持当前类别')
        fields.addWidget(self.category)
        fields.addWidget(ui_label('选择已有类别，或输入新类别；留空则不修改。'))
        fields.addSpacing(8)
        fields.addWidget(ui_label('矩形类型', 'sectionTitle'))
        self.kind = ModernComboBox(body)
        self.kind.addItems(['保留原类型', '普通矩形', '旋转矩形'])
        fields.addWidget(self.kind)
        fields.addWidget(ui_label('转为普通矩形时，使用原框的外接矩形。'))
        self.kind.setToolTip('转为旋转矩形后，可拖动圆形手柄旋转；转为普通矩形采用外接框。')
        layout.addWidget(body)
        if locked_count:
            layout.addWidget(ui_label('%d 个锁定框将跳过本次修改。' % locked_count))
        footer = QHBoxLayout()
        footer.addWidget(ui_label('Ctrl+Z 可撤销本次修改'), 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.button(QDialogButtonBox.Ok).setText('应用修改')
        set_role(buttons.button(QDialogButtonBox.Ok), 'primary')
        buttons.button(QDialogButtonBox.Cancel).setText('取消')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        layout.addLayout(footer)
