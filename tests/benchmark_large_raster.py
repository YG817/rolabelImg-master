"""Manual benchmark: writes an actual 1.81 GB uncompressed TIFF in a temp directory.

Run: .venv/Scripts/python tests/benchmark_large_raster.py
The generated image is removed by TemporaryDirectory after the benchmark.
"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import tempfile
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import rasterio
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QSettings
from PyQt5.QtTest import QTest
import roLabelImg
from label_store import LabelStore


class MemoryInfo(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
        'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
        'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]


def memory_mb():
    kernel = ctypes.WinDLL('kernel32')
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    info = MemoryInfo()
    info.cb = ctypes.sizeof(info)
    query = ctypes.WinDLL('psapi').GetProcessMemoryInfo
    query.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryInfo), wintypes.DWORD]
    if not query(kernel.GetCurrentProcess(), ctypes.byref(info), info.cb):
        raise ctypes.WinError()
    return info.WorkingSetSize / 1024 ** 2


def run():
    with tempfile.TemporaryDirectory(prefix='rolabel-benchmark-') as directory:
        path = os.path.join(directory, 'large.tif')
        tile = np.empty((3, 256, 256), dtype='uint8')
        tile[0], tile[1], tile[2] = 160, 120, 80
        begin = time.monotonic()
        with rasterio.Env(GDAL_CACHEMAX=64 * 1024 ** 2):
            with rasterio.open(path, 'w', driver='GTiff', width=24576, height=24576,
                               count=3, dtype='uint8', tiled=True, blockxsize=256, blockysize=256,
                               transform=rasterio.Affine(1, 0, 100, 0, -1, 100)) as dst:
                for _, bounds in dst.block_windows(1):
                    dst.write(tile, window=bounds)
        print('Fixture created in %.2fs' % (time.monotonic() - begin), flush=True)
        app = QApplication([])
        app.setApplicationName('roLabelImg-benchmark')
        app.setQuitOnLastWindowClosed(False)
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, directory)
        roLabelImg.LabelStore = lambda: LabelStore(os.path.join(directory, 'labels.json'))
        window = roLabelImg.MainWindow()
        window.resize(1200, 800)
        window.show()
        app.processEvents()
        beats, memory = [], []
        timer = QTimer()
        def heartbeat():
            beats.append(time.monotonic())
            memory.append(memory_mb())
            # Exercise move/resize while decoding, without waiting for completion.
            if window._loading:
                window.move(30 + len(beats) % 10, 30)
        timer.timeout.connect(heartbeat)
        timer.start(10)
        baseline = memory_mb()
        begin = time.monotonic()
        window.loadFile(path)
        while window.filePath != path:
            QTest.qWait(10)
            if time.monotonic() - begin > 120:
                raise RuntimeError('Load timed out')
        overview_seconds = time.monotonic() - begin
        window.setZoom(100)
        detail_start = time.monotonic()
        while window.canvas.detailPixmap is None:
            QTest.qWait(10)
            if time.monotonic() - detail_start > 30:
                raise RuntimeError('Detail timed out')
        timer.stop()
        report = dict(file_bytes=os.path.getsize(path), dimensions=[24576, 24576],
                      overview_seconds=round(overview_seconds, 3),
                      detail_seconds=round(time.monotonic() - detail_start, 3),
                      heartbeat_count=len(beats),
                      max_heartbeat_gap_ms=round(max([b-a for a, b in zip([begin] + beats, beats)] or [0])*1000, 2),
                      baseline_working_set_mb=round(baseline, 2),
                      max_sampled_working_set_mb=round(max(memory or [baseline]), 2),
                      preview=[window.image.width(), window.image.height()])
        print(json.dumps(report, indent=2), flush=True)
        Path('tests/benchmark_result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        window.close()
        while window._workers:
            QTest.qWait(10)
        app.processEvents()


if __name__ == '__main__':
    run()
