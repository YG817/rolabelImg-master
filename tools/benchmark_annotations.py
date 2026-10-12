"""Compare full scans with indexed queries on a fixed synthetic scene."""
import os, sys, time, statistics, json
from pathlib import Path
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'libs')]
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QPainterPathStroker, QImage, QPainter, QFontDatabase
from PyQt5.QtWidgets import QApplication
from shape import Shape
from canvas import Canvas

app = QApplication([])
for path in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/segoeui.ttf'):
    QFontDatabase.addApplicationFont(path)
canvas = Canvas()
for row in range(100):
    for col in range(100):
        shape = Shape('Bridge')
        x, y = col * 120, row * 120
        shape.points = [QPointF(x, y), QPointF(x + 40, y), QPointF(x + 40, y + 30), QPointF(x, y + 30)]
        shape.isRotated = False
        shape.close()
        canvas.shapes.append(shape)
point = QPointF(60, 60)

def scan_pick():
    for shape in reversed(canvas.shapes):
        if shape.nearestVertex(point, 14) is not None:
            return shape
    for shape in reversed(canvas.shapes):
        if shape.containsPoint(point):
            return shape
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        path = shape.makePath()
        path.closeSubpath()
        if stroker.createStroke(path).contains(point):
            return shape

def indexed_pick():
    candidates = canvas.hitShapes(point)
    shape, vertex = canvas.vertexAt(point, candidates)
    if shape:
        return shape
    shape, edge = canvas.edgeAt(point, candidates)
    return shape or next((s for s in candidates if canvas.containsHit(s, point)), None)

def measure(function, repeats):
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        function()
        samples.append((time.perf_counter() - start) * 1000)
    return round(statistics.median(samples), 3)

start = time.perf_counter()
canvas._shapeIndex.synchronize()
build_ms = (time.perf_counter() - start) * 1000
assert scan_pick() is indexed_pick() is None
viewport = QRectF(0, 0, 1024, 768)
clipped = canvas._shapeIndex.query(viewport.adjusted(-96, -96, 96, 96))
target = QImage(1024, 768, QImage.Format_RGB32)
def paint(shapes):
    target.fill(Qt.black)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.Antialiasing)
    for shape in shapes:
        shape.paint(painter)
    for shape in shapes:
        shape.paintLabel(painter)
    painter.end()

result = {
    'scene': '10,000 boxes, 120-pixel spacing, 40 x 30 boxes, zoom 100%, Windows offscreen',
    'index_build_ms': round(build_ms, 3),
    'full_scan_pick_ms': measure(scan_pick, 10),
    'indexed_pick_ms': measure(indexed_pick, 300),
    'near_pointer_candidates': len(canvas.hitShapes(point)),
    'full_scan_paint_ms': measure(lambda: paint(canvas.shapes), 5),
    'clipped_paint_ms': measure(lambda: paint(clipped), 30),
    'viewport_candidates': len(clipped),
    'note': 'Microbenchmarks of picking and annotation drawing, not whole-app latency or a real TIFF workload.'
}
(ROOT / 'build').mkdir(exist_ok=True)
(ROOT / 'build' / 'annotation-benchmark.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
