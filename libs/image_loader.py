"""Bounded raster reads. QImage decoding happens exclusively in worker threads."""
import math
import os
import sys

from PyQt5.QtCore import QThread, pyqtSignal, QSize, Qt, QTimer
from PyQt5.QtGui import QImage, QImageReader, QPainter, QColor, QPen
from PyQt5.QtWidgets import QWidget


def read_raster(path, bounds=None, target=2048, stretch=None):
    try:
        import numpy as np
        import rasterio
    except ImportError as exc:
        raise RuntimeError(
            '遥感影像依赖不可用：%s\n当前 Python：%s\n'
            '请在当前 Python 环境安装 requirements.txt 后重启软件。'
            % (exc, sys.executable)) from exc
    from rasterio.enums import Resampling, ColorInterp
    from rasterio.windows import Window

    with rasterio.Env(GDAL_CACHEMAX=64 * 1024 * 1024):
        with rasterio.open(path) as src:
            width, height = src.width, src.height
            x, y, w, h = bounds or (0, 0, width, height)
            ratio = min(1.0, float(target) / max(w, h))
            ow, oh = max(1, int(math.ceil(w * ratio))), max(1, int(math.ceil(h * ratio)))
            rgb = [ColorInterp.red, ColorInterp.green, ColorInterp.blue]
            indexes = ([src.colorinterp.index(c) + 1 for c in rgb]
                       if all(c in src.colorinterp for c in rgb)
                       else list(range(1, min(src.count, 3) + 1)))
            data = src.read(indexes, window=Window(x, y, w, h),
                            out_shape=(len(indexes), oh, ow), masked=True,
                            resampling=Resampling.nearest)
            if stretch is None:
                stretch = []
                for band in data:
                    values = band.compressed()
                    if band.dtype == np.uint8:
                        stretch.append((0.0, 255.0))
                    elif values.size:
                        lo, hi = np.percentile(values[np.isfinite(values)], (2, 98)) if np.isfinite(values).any() else (0, 1)
                        stretch.append((float(lo), float(max(hi, lo + 1))))
                    else:
                        stretch.append((0.0, 1.0))
            channels = []
            for band, (lo, hi) in zip(data, stretch):
                channels.append(np.clip(np.nan_to_num((band.astype('float32').filled(lo) - lo)
                                                     * (255.0 / (hi - lo))), 0, 255).astype('uint8'))
            while len(channels) < 3:
                channels.append(channels[0])
            pixels = np.ascontiguousarray(np.stack(channels, axis=-1))
            image = QImage(pixels.data, ow, oh, pixels.strides[0], QImage.Format_RGB888).copy()
            return image, (width, height), stretch


class ImageLoader(QThread):
    loaded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, path, parent=None, bounds=None, stretch=None, target=2048):
        super(ImageLoader, self).__init__(parent)
        self.path, self.bounds, self.stretch, self.target = path, bounds, stretch, target

    def run(self):
        try:
            raster = os.path.splitext(self.path)[1].lower() in ('.tif', '.tiff', '.vrt', '.img', '.jp2')
            if raster:
                image, size, stretch = read_raster(self.path, self.bounds, self.target, self.stretch)
            else:
                reader = QImageReader(self.path)
                size = reader.size()
                if not size.isValid():
                    raise ValueError(reader.errorString())
                # Some Qt codecs ignore scaledSize and allocate a full decode buffer.
                if size.width() * size.height() > 64 * 1024 * 1024:
                    image, size, stretch = read_raster(self.path, self.bounds, self.target, self.stretch)
                    raster = True
                else:
                    image = reader.read()
                    if image.isNull():
                        raise ValueError(reader.errorString())
                    size, stretch = (size.width(), size.height()), None
            if not self.isInterruptionRequested():
                coordinates = dict(text='', message='当前影像不含可读取的地理参考')
                if raster and self.bounds is None:
                    from geo_metadata import read_center_coordinates
                    coordinates = read_center_coordinates(self.path)
                self.loaded.emit(dict(path=self.path, image=image, size=size,
                                      raster=raster, stretch=stretch, bounds=self.bounds,
                                      coordinates=coordinates))
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))


class Spinner(QWidget):
    """Nonmodal status indicator, animated by the GUI event loop."""
    def __init__(self, parent=None):
        super(Spinner, self).__init__(parent)
        self.setFixedSize(26, 26)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.hide()

    def setRunning(self, running):
        self.setVisible(running)
        self.timer.start(40) if running else self.timer.stop()

    def tick(self):
        self.angle = (self.angle + 24) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor('#288bdb'), 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(4, 4, 18, 18, -self.angle * 16, 270 * 16)
