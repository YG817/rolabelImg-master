import math
import pytest
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QImage, QPainter
from shape import Shape


@pytest.mark.parametrize('order', [(0, 1, 2, 3), (1, 0, 3, 2), (3, 2, 1, 0), (2, 3, 0, 1)])
def test_caption_stays_on_original_top_edge_through_full_rotation(order):
    corners = [QPointF(100, 100), QPointF(400, 100), QPointF(400, 300), QPointF(100, 300)]
    shape = Shape('Pentagon')
    shape.points = [QPointF(corners[i]) for i in order]
    shape.close()
    top_left, top_right = order.index(0), order.index(1)
    for angle in range(361):
        rotated = shape.copy()
        rotated.rotate(math.radians(angle))
        before = list(rotated.points)
        start, end = rotated.labelEdge()
        assert start == rotated.points[top_left]
        assert end == rotated.points[top_right]
        assert rotated.points == before


def test_caption_follows_move_resize_and_preserves_painter_transform(app):
    shape = Shape('Bridge')
    shape.points = [QPointF(100, 100), QPointF(400, 100), QPointF(400, 300), QPointF(100, 300)]
    shape.close()
    shape.rotate(math.radians(35))
    shape.moveBy(QPointF(50, 20))
    assert shape.labelEdge() == (shape.points[0], shape.points[1])
    image = QImage(1000, 1000, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.scale(1.5, 1.5)
    painter.translate(20, 30)
    original = painter.transform()
    points = list(shape.points)
    shape.paintLabel(painter)
    assert painter.transform() == original
    assert shape.points == points
    painter.end()
