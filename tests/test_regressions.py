import json
import math
import time
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from PyQt5.QtCore import QPointF, Qt, QTimer, QSize
from PyQt5.QtGui import QImage, QPixmap, QMouseEvent
from PyQt5.QtTest import QTest
from conftest import wait_until
from shape import Shape
from coco_io import save_coco, read_coco
from label_store import LabelStore
from image_loader import read_raster

def write_tiff(path, width=3072, height=2048, dtype='uint16'):
    with rasterio.open(path, 'w', driver='GTiff', width=width, height=height,
                       count=3, dtype=dtype, tiled=True, blockxsize=256, blockysize=256,
                       transform=from_origin(100, 100, 1, 1)) as dst:
        for _, window in dst.block_windows(1):
            tile = np.full((3, int(window.height), int(window.width)), 700 if dtype == 'uint16' else 120, dtype=dtype)
            tile[1] //= 2
            dst.write(tile, window=window)

def make_shape(rotated=False):
    shape = Shape('建筑')
    shape.points = [QPointF(100, 100), QPointF(300, 100), QPointF(300, 250), QPointF(100, 250)]
    shape.isRotated = rotated
    shape.close()
    if rotated:
        shape.rotate(-math.pi / 4)
    return shape

def test_coco_roundtrip_and_geometry(tmp_path):
    shape = make_shape(True)
    points = [(p.x(), p.y()) for p in shape.points]
    data = dict(label=shape.label, points=points, direction=shape.direction,
                isRotated=True, difficult=True)
    path = str(tmp_path / 'scene.json')
    save_coco(path, [data], '/images/scene.tif', (32000, 24000),
              [dict(id=42, name=shape.label, supercategory='')])
    raw = json.loads(open(path, encoding='utf-8').read())
    assert raw['images'][0]['width'] == 32000
    ann = raw['annotations'][0]
    assert ann['category_id'] == 42
    assert ann['area'] == pytest.approx(30000)
    assert ann['bbox'][2] == pytest.approx(350 / math.sqrt(2))
    restored, _ = read_coco(path, '/elsewhere/scene.tif')
    assert restored[0][1] == points
    assert restored[0][2:4] == (shape.direction, True)
    assert restored[0][-1]
    save_coco(path, [], '/images/scene.tif', (32000, 24000), [])
    assert read_coco(path, 'scene.tif')[0] == []

def test_library_persists_ids_names_colors(tmp_path):
    path = str(tmp_path / 'library.json')
    store = LabelStore(path)
    one = dict(store.ensure('建筑'))
    two = dict(store.ensure('车辆'))
    assert one['color'] != two['color']
    store.rename('建筑', '房屋')
    store.delete('车辆')
    other = LabelStore(path)
    assert other.ensure('房屋')['id'] == one['id']
    assert other.ensure('房屋')['color'] == one['color']
    assert other.ensure('船')['id'] > two['id']
    with pytest.raises(ValueError):
        other.rename('房屋', '船')

@pytest.mark.parametrize('scale', [0.1, 1, 3])
@pytest.mark.parametrize('rotated', [False, True])
def test_selected_corner_drag(window, scale, rotated):
    canvas = window.canvas
    canvas.loadPixmap(QPixmap(1000, 1000))
    canvas.scale = scale
    canvas.resize(canvas.sizeHint())
    shape = make_shape(rotated)
    canvas.shapes = [shape]
    window.addLabel(shape)
    canvas.selectShape(shape)
    corner = QPointF(shape[0])
    canvas.selectShapePoint(corner + QPointF(-10 / scale, 0))
    assert canvas.hShape is shape and canvas.hVertex == 0
    opposite = QPointF(shape[2])
    target = corner + QPointF(20, 10)
    canvas.boundedMoveVertex(target)
    assert shape[0] == target
    assert shape[2] == opposite
    a, b = shape[1] - shape[0], shape[3] - shape[0]
    assert a.x() * b.x() + a.y() * b.y() == pytest.approx(0, abs=1e-8)
    assert shape.center == (shape[0] + shape[2]) / 2

def test_mouse_drag_after_list_selection(window):
    canvas = window.canvas
    canvas.loadPixmap(QPixmap(1000, 1000))
    canvas.scale = 1
    canvas.adjustSize()
    shape = make_shape()
    canvas.shapes = [shape]
    window.addLabel(shape)
    window.labelList.setCurrentRow(0)
    press = QPointF(100, 100) + canvas.offsetToCenter()
    QTest.mousePress(canvas, Qt.LeftButton, pos=press.toPoint())
    move = QMouseEvent(QMouseEvent.MouseMove, press + QPointF(25, 15), Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
    canvas.mouseMoveEvent(move)
    QTest.mouseRelease(canvas, Qt.LeftButton, pos=(press + QPointF(25, 15)).toPoint())
    assert shape[0] == QPointF(125, 115)
    assert window.dirty

def test_raster_preview_bounded(tmp_path):
    path = str(tmp_path / 'scene.tif')
    write_tiff(path)
    image, size, stretch = read_raster(path, target=512)
    assert size == (3072, 2048)
    assert image.width() == 512
    detail, size2, stretch2 = read_raster(path, (100, 200, 256, 128), 512, stretch)
    assert detail.size() == QSize(256, 128)
    assert stretch2 == stretch and size2 == size

def test_async_load_export_switch_and_reload(window, tmp_path):
    path = str(tmp_path / 'scene.tif')
    write_tiff(path)
    beats = []
    timer = QTimer()
    timer.timeout.connect(lambda: beats.append(time.monotonic()))
    timer.start(5)
    window.loadFile(path)
    assert window._loading and window.spinner.timer.isActive()
    wait_until(lambda: window.filePath == path)
    assert beats
    assert window.canvas.imageSize == QSize(3072, 2048)
    assert window.image.width() == 2048
    shape = make_shape(True)
    window.canvas.shapes = [shape]
    window.addLabel(shape)
    window.defaultSaveDir = str(tmp_path)
    window.saveFile()
    data = json.loads((tmp_path / 'scene.json').read_text(encoding='utf-8'))
    assert data['images'][0]['width'] == 3072
    window.formatCombo.setCurrentIndex(1)
    window.saveFile()
    from xml.etree import ElementTree
    root = ElementTree.parse(tmp_path / 'scene.xml').getroot()
    assert root.findtext('size/width') == '3072'
    assert root.find('object/robndbox') is not None
    window.loadFile(path)
    wait_until(lambda: window.filePath == path)
    assert len(window.canvas.shapes) == 1
    window.formatCombo.setCurrentIndex(0)
    window.loadFile(path)
    wait_until(lambda: window.filePath == path)
    # The newer XML wins even if the UI had been switched to JSON. VOC rounds
    # its center and angle, so compare its recovered geometry with tolerance.
    assert window.formatCombo.currentIndex() == 1
    for actual, expected in zip(window.canvas.shapes[0].points, shape.points):
        assert (actual.x(), actual.y()) == pytest.approx((expected.x(), expected.y()), abs=1e-3)
    window.setZoom(100)
    wait_until(lambda: window.canvas.detailPixmap is not None)
    assert window.canvas.detailPixmap.width() <= 4096
    timer.stop()

def test_latest_request_and_close(window, tmp_path, monkeypatch):
    import image_loader
    original = image_loader.read_raster
    def delayed(*args, **kwargs):
        time.sleep(0.12)
        return original(*args, **kwargs)
    monkeypatch.setattr(image_loader, 'read_raster', delayed)
    first, second = str(tmp_path / 'first.tif'), str(tmp_path / 'second.tif')
    write_tiff(first, 256, 256)
    write_tiff(second, 512, 256)
    window.loadFile(first)
    window.loadFile(second)
    wait_until(lambda: window.filePath == second)
    assert window.canvas.imageSize.width() == 512
    window.loadFile(first)
    window.close()
    assert window._closePending
    wait_until(lambda: not window._workers)
    assert not window.isVisible()

def test_failed_image_can_recover(window, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr(window, 'errorMessage', lambda *args: errors.append(args))
    invalid = tmp_path / 'bad.tif'
    invalid.write_bytes(b'invalid')
    window.loadFile(str(invalid))
    wait_until(lambda: not window._loading)
    assert errors and not window.spinner.timer.isActive()
    valid = tmp_path / 'ok.png'
    image = QImage(100, 100, QImage.Format_RGB32)
    image.fill(Qt.white)
    image.save(str(valid))
    window.loadFile(str(valid))
    wait_until(lambda: window.filePath == str(valid))


def test_label_manager_ui_and_restart(window, tmp_path, monkeypatch):
    from PyQt5.QtWidgets import QDialog, QInputDialog, QColorDialog, QPushButton, QListWidget
    from PyQt5.QtGui import QColor
    names = iter([('建筑', True), ('房屋', True), ('临时', True)])
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args: next(names))
    monkeypatch.setattr(QColorDialog, 'getColor', lambda *args: QColor('#12ab56'))
    problems = []
    def interact():
        try:
            dialog = next(d for d in window.findChildren(QDialog) if d.isVisible())
            buttons = {b.text(): b for b in dialog.findChildren(QPushButton)}
            labels = dialog.findChild(QListWidget)
            buttons['新增'].click()
            labels.setCurrentRow(0)
            buttons['重命名'].click()
            labels.setCurrentRow(0)
            buttons['颜色'].click()
            buttons['新增'].click()
            labels.setCurrentRow(1)
            buttons['删除'].click()
            assert labels.count() == 1
            assert labels.item(0).text() == '房屋'
            dialog.accept()
        except Exception as exc:
            problems.append(exc)
            for dialog in window.findChildren(QDialog):
                dialog.reject()
    QTimer.singleShot(20, interact)
    window.manageLabels()
    assert not problems
    reloaded = LabelStore(str(tmp_path / 'labels.json'))
    assert reloaded.entries == [dict(id=1, name='房屋', color='#12ab56')]
    assert window.labelHist == ['房屋']


@pytest.mark.parametrize('angle', [math.pi / 2, math.pi, 3 * math.pi / 2])
def test_rotated_resize_at_right_angles(window, angle):
    shape = make_shape(True)
    shape.rotate(shape.direction - angle)
    window.canvas.loadPixmap(QPixmap(1000, 1000))
    window.canvas.shapes = [shape]
    window.addLabel(shape)
    for index in range(4):
        window.canvas.selectShapePoint(shape[index])
        opposite = QPointF(shape[(index + 2) % 4])
        window.canvas.boundedMoveVertex(shape[index] + QPointF(3, 2))
        assert shape[(index + 2) % 4] == opposite
        a, b = shape[1] - shape[0], shape[3] - shape[0]
        assert a.x() * b.x() + a.y() * b.y() == pytest.approx(0, abs=1e-8)


def test_empty_library_does_not_restore_deleted_predefined_labels(window, tmp_path):
    classes = tmp_path / 'classes.txt'
    classes.write_text('removed\n', encoding='utf-8')
    window.labelStore.ensure('removed')
    window.labelStore.delete('removed')
    window.loadPredefinedClasses(str(classes))
    window.refreshLabelLibrary()
    assert window.labelHist == []
