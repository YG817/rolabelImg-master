"""Small overview and explicit, persistent inspection checkpoints for large images."""
import hashlib
from PyQt5.QtCore import Qt, QPointF, QRectF, QSize, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen
from PyQt5.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QPushButton, QSpinBox)
from annotation_paths import identity


class OverviewMap(QWidget):
    activated = pyqtSignal(QPointF)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 180)
        self.preview = QPixmap()
        self.imageSize = QSize()
        self.viewport = QRectF()
        self.divisions = 6
        self.completed = set()
        self.active = 0

    def imageRect(self):
        if self.preview.isNull():
            return QRectF()
        size = self.preview.size()
        size.scale(self.size() - QSize(16, 16), Qt.KeepAspectRatio)
        return QRectF((self.width() - size.width()) / 2,
                      (self.height() - size.height()) / 2, size.width(), size.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#e9edf3'))
        target = self.imageRect()
        if target.isEmpty():
            painter.drawText(self.rect(), Qt.AlignCenter, '打开影像后可巡检')
            return
        painter.drawPixmap(target, self.preview, QRectF(self.preview.rect()))
        count = self.divisions
        for index in range(count * count):
            row, col = divmod(index, count)
            region = QRectF(target.x() + col * target.width() / count,
                            target.y() + row * target.height() / count,
                            target.width() / count, target.height() / count)
            if index in self.completed:
                painter.fillRect(region, QColor(38, 175, 99, 95))
            painter.setPen(QPen(QColor('#ffffff'), 1))
            painter.drawRect(region)
            if index == self.active:
                painter.setPen(QPen(QColor('#ffd344'), 3))
                painter.drawRect(region.adjusted(1, 1, -1, -1))
        if not self.viewport.isEmpty():
            visible = QRectF(target.x() + self.viewport.x() / self.imageSize.width() * target.width(),
                             target.y() + self.viewport.y() / self.imageSize.height() * target.height(),
                             self.viewport.width() / self.imageSize.width() * target.width(),
                             self.viewport.height() / self.imageSize.height() * target.height())
            painter.setPen(QPen(QColor('#288bff'), 2))
            painter.drawRect(visible.intersected(target))

    def mousePressEvent(self, event):
        target = self.imageRect()
        if event.button() == Qt.LeftButton and target.contains(event.pos()):
            self.activated.emit(QPointF((event.x() - target.x()) / target.width(),
                                       (event.y() - target.y()) / target.height()))


class InspectionDialog(QDialog):
    regionRequested = pyqtSignal(QRectF)
    markRequested = pyqtSignal()
    originalSizeRequested = pyqtSignal()
    fitRequested = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.path = None
        self.progress = {}
        self.setWindowTitle('大图巡检 · 小地图与分区进度')
        self.resize(390, 420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('黄色：当前分区  蓝色：当前视野  绿色：已人工检查'))
        self.overview = OverviewMap(self)
        layout.addWidget(self.overview, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel('横向 / 纵向分区数'))
        self.divisions = QSpinBox()
        self.divisions.setRange(2, 20)
        self.divisions.setValue(6)
        row.addWidget(self.divisions)
        layout.addLayout(row)
        self.progressLabel = QLabel()
        layout.addWidget(self.progressLabel)
        row = QHBoxLayout()
        previous = QPushButton('上一分区')
        following = QPushButton('下一分区')
        self.markButton = QPushButton('完成本分区')
        previous.clicked.connect(lambda: self.selectRegion(self.overview.active - 1))
        following.clicked.connect(lambda: self.selectRegion(self.overview.active + 1))
        self.markButton.clicked.connect(lambda checked=False: self.markRequested.emit())
        row.addWidget(previous)
        row.addWidget(following)
        row.addWidget(self.markButton)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.originalSizeButton = QPushButton('恢复原始大小（100%）')
        self.fitButton = QPushButton('显示整幅影像')
        self.originalSizeButton.clicked.connect(lambda checked=False: self.originalSizeRequested.emit())
        self.fitButton.clicked.connect(lambda checked=False: self.fitRequested.emit())
        row.addWidget(self.originalSizeButton)
        row.addWidget(self.fitButton)
        layout.addLayout(row)
        note = QLabel('点击小地图跳转。分区完成需手动确认；\n确认前保存修改，编辑涉及的分区会取消完成标记。')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.overview.activated.connect(self.selectAt)
        self.divisions.valueChanged.connect(self.changeGrid)
        self.refresh()

    def setImage(self, path, image, size):
        self.path = path
        self.key = 'inspection/' + hashlib.sha256(identity(path).encode('utf-8')).hexdigest()
        saved = self.settings.value(self.key, {})
        self.progress = saved if isinstance(saved, dict) and saved.get('size') == [size.width(), size.height()] else {}
        self.progress.setdefault('size', [size.width(), size.height()])
        self.progress.setdefault('grids', {})
        self.overview.preview = QPixmap.fromImage(image.scaled(640, 360, Qt.KeepAspectRatio, Qt.FastTransformation))
        self.overview.imageSize = size
        self.overview.active = 0
        self.changeGrid()

    def clearImage(self):
        self.path = None
        self.progress = {}
        self.overview.preview = QPixmap()
        self.overview.imageSize = QSize()
        self.overview.viewport = QRectF()
        self.overview.completed.clear()
        self.refresh()

    def changeGrid(self, value=None):
        self.overview.divisions = self.divisions.value()
        self.overview.active = 0
        self.overview.completed = set(self.progress.get('grids', {}).get(str(self.divisions.value()), []))
        self.refresh()

    def selectAt(self, point):
        count = self.divisions.value()
        self.selectRegion(min(count - 1, int(point.y() * count)) * count
                          + min(count - 1, int(point.x() * count)))

    def selectRegion(self, index):
        if not self.path:
            return
        count = self.divisions.value()
        self.overview.active = max(0, min(count * count - 1, index))
        row, col = divmod(self.overview.active, count)
        width, height = self.overview.imageSize.width() / count, self.overview.imageSize.height() / count
        self.regionRequested.emit(QRectF(col * width, row * height, width, height))
        self.refresh()

    def markComplete(self):
        if self.path:
            self.overview.completed.add(self.overview.active)
            self.persist()

    def invalidateRects(self, rectangles):
        if not self.path or not self.progress.get('grids'):
            return
        changed = False
        size = self.overview.imageSize
        for grid, completed in list(self.progress['grids'].items()):
            count = int(grid)
            remaining = []
            for index in completed:
                row, col = divmod(index, count)
                region = QRectF(col * size.width() / count, row * size.height() / count,
                                size.width() / count, size.height() / count)
                if any(region.intersects(rect) for rect in rectangles):
                    changed = True
                else:
                    remaining.append(index)
            self.progress['grids'][grid] = remaining
        if changed:
            self.overview.completed = set(self.progress['grids'].get(str(self.divisions.value()), []))
            self.settings.setValue(self.key, self.progress)
            self.refresh()

    def persist(self):
        self.progress['grids'][str(self.divisions.value())] = sorted(self.overview.completed)
        self.settings.setValue(self.key, self.progress)
        self.refresh()

    def refresh(self):
        self.progressLabel.setText('分区 %d / %d · 已人工检查 %d 个' % (
            self.overview.active + 1, self.divisions.value() ** 2, len(self.overview.completed)))
        self.markButton.setEnabled(self.path is not None)
        self.originalSizeButton.setEnabled(self.path is not None)
        self.fitButton.setEnabled(self.path is not None)
        self.overview.update()
