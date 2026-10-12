#!/usr/bin/python
# -*- coding: utf-8 -*-


try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from lib import distance
import math
import weakref
from geometry_tracking import TrackedList

DEFAULT_LINE_COLOR = QColor(0, 255, 0, 128)
DEFAULT_FILL_COLOR = QColor(255, 0, 0, 128)
DEFAULT_SELECT_LINE_COLOR = QColor(255, 255, 255)
DEFAULT_SELECT_FILL_COLOR = QColor(0, 128, 255, 155)
DEFAULT_VERTEX_FILL_COLOR = QColor(0, 255, 0, 255)
DEFAULT_HVERTEX_FILL_COLOR = QColor(255, 0, 0)


class Shape(object):
    P_SQUARE, P_ROUND = range(2)

    MOVE_VERTEX, NEAR_VERTEX = range(2)

    # The following class variables influence the drawing
    # of _all_ shape objects.
    line_color = DEFAULT_LINE_COLOR
    fill_color = DEFAULT_FILL_COLOR
    select_line_color = DEFAULT_SELECT_LINE_COLOR
    select_fill_color = DEFAULT_SELECT_FILL_COLOR
    vertex_fill_color = DEFAULT_VERTEX_FILL_COLOR
    hvertex_fill_color = DEFAULT_HVERTEX_FILL_COLOR
    point_type = P_ROUND
    point_size = 10
    scale = 1.0

    def __init__(self, label=None, line_color=None,difficult = False):
        self._geometryListeners = []
        self._pathCache = self._boundsCache = self._vertexCache = self._labelEdgeCache = None
        self.label = label
        self.points = []
        self.fill = False
        self.selected = False
        self.difficult = difficult
        self.identifier = None
        self.locked = False

        self.direction = 0  # added by hy
        self.center = None # added by hy
        self.isRotated = True 

        self._highlightIndex = None
        self._highlightMode = self.NEAR_VERTEX
        self._highlightSettings = {
            self.NEAR_VERTEX: (4, self.P_ROUND),
            self.MOVE_VERTEX: (1.5, self.P_SQUARE),
        }

        self._closed = False

        if line_color is not None:
            # Override the class line_color attribute
            # with an object attribute. Currently this
            # is used for drawing the pending line a different color.
            self.line_color = line_color

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, value):
        self._label = value
        self.geometryChanged()

    @property
    def points(self):
        return self._points

    @points.setter
    def points(self, values):
        self._points = TrackedList(values, self.geometryChanged)
        self.geometryChanged()

    def watchGeometry(self, callback):
        ref = weakref.WeakMethod(callback)
        if ref not in self._geometryListeners:
            self._geometryListeners.append(ref)

    def geometryChanged(self):
        self._pathCache = self._boundsCache = self._vertexCache = self._labelEdgeCache = None
        alive = []
        for ref in self._geometryListeners:
            callback = ref()
            if callback is not None:
                alive.append(ref)
                callback(self)
        self._geometryListeners = alive


    def rotate(self, theta):
        for i, p in enumerate(self.points):
            self.points[i] = self.rotatePoint(p, theta)
        self.direction -= theta
        self.direction = self.direction % (2 * math.pi)

    def rotatePoint(self, p, theta):
        order = p-self.center;
        cosTheta = math.cos(theta)
        sinTheta = math.sin(theta)
        pResx = cosTheta * order.x() + sinTheta * order.y()
        pResy = - sinTheta * order.x() + cosTheta * order.y()
        pRes = QPointF(self.center.x() + pResx, self.center.y() + pResy)
        return pRes

    def close(self):
        self.center = QPointF((self.points[0].x()+self.points[2].x()) / 2, (self.points[0].y()+self.points[2].y()) / 2)
        # print("refresh center!")
        self._closed = True

    def reachMaxPoints(self):
        if len(self.points) >= 4:
            return True
        return False

    def addPoint(self, point):
        if self.points and len(self.points) == 4 and point == self.points[0]:
            self.close()
        else:
            self.points.append(point)

    def popPoint(self):
        if self.points:
            return self.points.pop()
        return None

    def isClosed(self):
        return self._closed

    def setOpen(self):
        self._closed = False

    def paint(self, painter):
        if self.points:
            # Outline paths must not inherit the brush from handles or previews.
            painter.setBrush(Qt.NoBrush)
            color = self.select_line_color if self.selected else self.line_color
            pen = QPen(color)
            # Try using integer sizes for smoother drawing(?)
            pen.setWidth(max(1, int(round(2.0 / self.scale))))
            painter.setPen(pen)

            line_path = self.makePath()
            vertex_key = (self.scale, self.point_size, self.point_type, self._highlightIndex, self._highlightMode)
            if self._vertexCache is None or self._vertexCache[0] != vertex_key:
                vrtx_path = QPainterPath()
                for i in range(len(self.points)):
                    self.drawVertex(vrtx_path, i)
                self._vertexCache = (vertex_key, vrtx_path)
            vrtx_path = self._vertexCache[1]
            self.vertex_fill_color = self.hvertex_fill_color if self._highlightIndex is not None else Shape.vertex_fill_color
            if self.isClosed():
                line_path.lineTo(self.points[0])

            # dir_path = QPainterPath()
            # tempP = self.points[0]+QPointF(10,10)
            # print('direction2 is %lf, a os %lf' % (self.direction,math.tan(self.direction)))
            # dir_path.moveTo(tempP)
            # dir_path.lineTo(tempP + QPointF(10, (10-tempP.x())* math.tan(self.direction)+tempP.y()))
            # painter.drawPath(dir_path)

            painter.drawPath(line_path)
            painter.drawPath(vrtx_path)
            painter.fillPath(vrtx_path, self.vertex_fill_color)
            if self.fill:
                color = self.select_fill_color if self.selected else self.fill_color
                painter.fillPath(line_path, color)

            if self.center is not None:
                center_path = QPainterPath()
                d = self.point_size / self.scale
                center_path.addRect(self.center.x() - d / 2, self.center.y() - d / 2, d, d)
                painter.drawPath(center_path)
                if self.isRotated:
                    painter.fillPath(center_path, self.vertex_fill_color)
                else:
                    painter.fillPath(center_path, QColor(0, 0, 0))

    def labelEdge(self):
        """Return the same local top-left corner and top edge while rotating.

        Screen-space extrema change corners during rotation. Project into the
        box's own orientation instead, which also handles reverse-direction
        drawing and either vertex winding without sorting or changing points.
        """
        if len(self.points) != 4:
            return None
        if self._labelEdgeCache is not None and self._labelEdgeCache[0] == self.direction:
            return self._labelEdgeCache[1]
        along = QPointF(math.cos(self.direction), math.sin(self.direction))
        down = QPointF(-along.y(), along.x())
        center = (self.points[0] + self.points[2]) / 2
        def projection(point, axis):
            delta = point - center
            return delta.x() * axis.x() + delta.y() * axis.y()
        index = min(range(4), key=lambda i: projection(self.points[i], along)
                    + projection(self.points[i], down))
        neighbors = ((index + 1) % 4, (index - 1) % 4)
        end = max(neighbors, key=lambda i: projection(self.points[i], along))
        edge = self.points[index], self.points[end]
        self._labelEdgeCache = (self.direction, edge)
        return edge

    def paintLabel(self, painter):
        edge = self.labelEdge()
        if not self.label or edge is None:
            return
        # Draw in screen coordinates so a small, legible caption does not
        # become enormous or disappear as the image zoom changes.
        corner, endpoint = (painter.transform().map(point) for point in edge)
        direction = endpoint - corner
        painter.save()
        painter.resetTransform()
        painter.translate(corner)
        painter.rotate(math.degrees(math.atan2(direction.y(), direction.x())))
        font = painter.font()
        font.setPixelSize(12)
        font.setBold(False)
        painter.setFont(font)
        metrics = QFontMetricsF(font)
        text = str(self.label)
        rect = QRectF(3, -metrics.height() - 4,
                      metrics.horizontalAdvance(text) + 4, metrics.height() + 2)
        painter.fillRect(rect, QColor(0, 0, 0, 115))
        color = QColor(self.line_color)
        color.setAlpha(255)
        painter.setPen(color)
        painter.drawText(QPointF(rect.x() + 2, rect.y() + metrics.ascent() + 1), text)
        painter.restore()

    def paintNormalCenter(self, painter):
        if self.center is not None:
            center_path = QPainterPath();
            d = self.point_size / self.scale
            center_path.addRect(self.center.x() - d / 2, self.center.y() - d / 2, d, d)
            painter.drawPath(center_path)
            if not self.isRotated:
                painter.fillPath(center_path, QColor(0, 0, 0))

    def drawVertex(self, path, i):
        d = self.point_size / self.scale
        shape = self.point_type
        point = self.points[i]
        if i == self._highlightIndex:
            size, shape = self._highlightSettings[self._highlightMode]
            d *= size
        if self._highlightIndex is not None:
            self.vertex_fill_color = self.hvertex_fill_color
        else:
            self.vertex_fill_color = Shape.vertex_fill_color
        if shape == self.P_SQUARE:
            path.addRect(point.x() - d / 2, point.y() - d / 2, d, d)
        elif shape == self.P_ROUND:
            path.addEllipse(point, d / 2.0, d / 2.0)
        else:
            assert False, "unsupported vertex shape"
    # def drawVertex(self, path, center):
    #     pass

    def nearestVertex(self, point, epsilon):
        if not self.points:
            return None
        index = min(range(len(self.points)), key=lambda i: distance(self.points[i] - point))
        return index if distance(self.points[index] - point) <= epsilon else None

    def containsPoint(self, point):
        if not self.boundingRect().contains(point):
            return False
        return self.makePath().contains(point)

    def makePath(self):
        if self._pathCache is None:
            path = QPainterPath()
            if self.points:
                path.moveTo(self.points[0])
                for point in self.points[1:]:
                    path.lineTo(point)
            self._pathCache = path
        return QPainterPath(self._pathCache)

    def boundingRect(self):
        if self._boundsCache is None:
            self._boundsCache = self.makePath().boundingRect()
        return QRectF(self._boundsCache)

    def moveBy(self, offset):
        self.points = [p + offset for p in self.points]

    def moveVertexBy(self, i, offset):
        self.points[i] = self.points[i] + offset

    def highlightVertex(self, i, action):
        self._highlightIndex = i
        self._highlightMode = action

    def highlightClear(self):
        self._highlightIndex = None

    def copy(self):
        shape = Shape("%s" % self.label)
        shape.points = [QPointF(p) for p in self.points]
        
        shape.center = QPointF(self.center) if self.center is not None else None
        shape.direction = self.direction
        shape.isRotated = self.isRotated

        shape.fill = self.fill
        shape.selected = self.selected
        shape._closed = self._closed
        if self.line_color != Shape.line_color:
            shape.line_color = self.line_color
        if self.fill_color != Shape.fill_color:
            shape.fill_color = self.fill_color
        shape.difficult = self.difficult 
        shape.identifier = self.identifier
        shape.locked = self.locked
        return shape

    def __len__(self):
        return len(self.points)

    def __getitem__(self, key):
        return self.points[key]

    def __setitem__(self, key, value):
        self.points[key] = value
