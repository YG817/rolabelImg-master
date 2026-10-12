"""Choose an existing category or create one for a single annotation."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QDialogButtonBox
from ui_theme import ModernDialog, ModernComboBox, panel, ui_label, set_role


class ShapeLabelDialog(ModernDialog):
    def __init__(self, parent, entries, current_label=None):
        super().__init__(parent, Qt.Popup)
        editing = current_label is not None
        self.setWindowTitle('更改标签' if editing else '选择或新增标签')
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(ui_label(self.windowTitle(), 'sectionTitle'))
        layout.addWidget(ui_label('仅修改这个标注框，其他标注保持原样。' if editing
                                  else '为刚画好的标注框选择类别。'))
        body, fields = panel()
        fields.setContentsMargins(12, 12, 12, 12)
        fields.setSpacing(8)
        self.category = ModernComboBox(body)
        self.category.setEditable(True)
        for entry in entries:
            self.category.addItem(entry['name'])
            self.category.setItemData(self.category.count() - 1, entry['color'], Qt.UserRole + 2)
        if editing:
            self.category.setCurrentText(current_label)
        else:
            self.category.setCurrentIndex(-1)
        self.category.lineEdit().setPlaceholderText('选择类别，或输入新类别')
        fields.addWidget(self.category)
        fields.addWidget(ui_label('新类别会自动保存到本地类别库。'))
        layout.addWidget(body)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        self.buttons.button(QDialogButtonBox.Ok).setText('确认修改' if editing else '确定')
        self.buttons.button(QDialogButtonBox.Cancel).setText('取消')
        set_role(self.buttons.button(QDialogButtonBox.Ok), 'primary')
        self.category.currentTextChanged.connect(self.updateConfirmButton)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.updateConfirmButton()

    def updateConfirmButton(self):
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.category.currentText().strip()))

    def accept(self):
        if self.category.currentText().strip():
            super().accept()
