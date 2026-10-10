"""Validate exported geometry without imposing a minimum object size."""
import math


def validate_box(points):
    if len(points) != 4:
        raise ValueError('矩形标注必须包含四个顶点')
    if not all(math.isfinite(value) for point in points for value in point):
        raise ValueError('标注坐标包含非有限数值')
    for i, point in enumerate(points):
        other = points[(i + 1) % 4]
        if math.hypot(point[0] - other[0], point[1] - other[1]) <= 1e-8:
            raise ValueError('标注框的宽或高为零，请重新绘制')
    origin = points[0]
    relative = [(x - origin[0], y - origin[1]) for x, y in points]
    area = abs(sum(relative[i][0] * relative[(i + 1) % 4][1]
                   - relative[(i + 1) % 4][0] * relative[i][1]
                   for i in range(4))) / 2
    if area <= 1e-12:
        raise ValueError('标注框面积为零，请重新绘制')
    return area
