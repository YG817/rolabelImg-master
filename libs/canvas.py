
try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

#from PyQt4.QtOpenGL import *

from shape import Shape
from lib import distance
from box_geometry import validate_box
import math

CURSOR_DEFAULT = Qt.ArrowCursor
CURSOR_POINT = Qt.PointingHandCursor
CURSOR_DRAW = Qt.CrossCursor
CURSOR_MOVE = Qt.ClosedHandCursor
CURSOR_GRAB = Qt.OpenHandCursor

# class Canvas(QGLWidget):


class Canvas(QWidget):
    zoomRequest = pyqtSignal(int)
    scrollRequest = pyqtSignal(int, int)
    panRequest = pyqtSignal(int, int)
    newShape = pyqtSignal()
    selectionChanged = pyqtSignal(bool)
    shapeMoved = pyqtSignal()
    editStarted = pyqtSignal()
    drawingPolygon = pyqtSignal(bool)

    hideRRect = pyqtSignal(bool)
    hideNRect = pyqtSignal(bool)
    status = pyqtSignal(str)

    CREATE, EDIT = list(range(2))

    epsilon = 14.0  # Hit radius in screen pixels, independent of zoom.



    def __init__(self, *args, **kwargs):
        super(Canvas, self).__init__(*args, **kwargs)
        # Initialise local state.
        self.mode = self.EDIT
        self.shapes = []
        self.current = None
        self.selectedShape = None  # save the selected shape here
        self.selectedShapeCopy = None
        self.lineColor = QColor(0, 0, 255)
        self.line = Shape(line_color=self.lineColor)
        self.prevPoint = QPointF()
        self.offsets = QPointF(), QPointF()
        self.scale = 1.0
        self.pixmap = QPixmap()
        self.imageSize = QSize()
        self.detailPixmap = None
        self.detailRect = None
        self.visible = {}
        self._hideBackround = False
        self.hideBackround = False
        self.hShape = None
        self.hVertex = None
        self._painter = QPainter()
        self._cursor = CURSOR_DEFAULT
        # Menus:
        self.menus = (QMenu(), QMenu())
        # Set widget options.
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.WheelFocus)
        self.verified = False
        # judge can draw rotate rect
        self.canDrawRotatedRect = True
        self.hideRotated = False
        self.hideNormal = False
        self.canOutOfBounding = False
        self.showCenter = False
        self._panButton = Qt.NoButton
        self._panGlobalPos = None
        self._spacePanHeld = False
        self._spacePanSuppressMouse = False
        self._lastGlobalPos = None
        self._editingGesture = False
        self._rotatingGesture = False
        self._editRecorded = False
        self.viewOffset = QPointF()
        self.zoomAnchor = None
        self.viewportSize = QSize()

    def enterEvent(self, ev):
        self.overrideCursor(self._cursor)

    def leaveEvent(self, ev):
        self.restoreCursor()

    def focusOutEvent(self, ev):
        self.setSpacePan(False)
        self.endPan()
        self.restoreCursor()

    def setSpacePan(self, held):
        if held == self._spacePanHeld:
            return
        self._spacePanHeld = held
        if held:
            self.unHighlight()
            self._editingGesture = self._rotatingGesture = False
            self.overrideCursor(CURSOR_GRAB)
            self.status.emit('按住空格拖动影像 · 松开空格恢复标注')
        else:
            # Releasing Space before the mouse must not finish a new box or
            # continue editing the box under the pointer.
            self._spacePanSuppressMouse = self._panButton != Qt.NoButton
            self.endPan()
            self.overrideCursor(CURSOR_DRAW if self.drawing() else CURSOR_DEFAULT)
        self.update()

    def endPan(self):
        self._panButton = Qt.NoButton
        self._panGlobalPos = None
        self._cursor = CURSOR_DEFAULT
        self.restoreCursor()
        if self._spacePanHeld:
            self.overrideCursor(CURSOR_GRAB)

    def isVisible(self, shape):
        return self.visible.get(shape, True)

    def drawing(self):
        return self.mode == self.CREATE

    def editing(self):
        return self.mode == self.EDIT

    def setEditing(self, value=True):
        self.mode = self.EDIT if value else self.CREATE
        if not value:  # Create
            self.unHighlight()
            self.deSelectShape()

    def unHighlight(self):
        if self.hShape:
            self.hShape.highlightClear()
        self.hVertex = self.hShape = None

    def selectedVertex(self):
        return self.hVertex is not None

    def mouseMoveEvent(self, ev):
        """Update line with last point and current coordinates."""
        previous_global = self._lastGlobalPos
        self._lastGlobalPos = ev.globalPos()
        self._hoverPoint = self.transformPos(ev.pos())
        if self._spacePanHeld and self._panButton == Qt.NoButton and ev.buttons() & Qt.LeftButton:
            self._panButton = Qt.LeftButton
            self._panGlobalPos = previous_global or ev.globalPos()
        if self._panButton != Qt.NoButton:
            if ev.buttons() & self._panButton:
                # Local coordinates change as the scroll area moves the canvas.
                # Screen coordinates keep the image anchored to the pointer.
                delta = ev.globalPos() - self._panGlobalPos
                self._panGlobalPos = ev.globalPos()
                self.panRequest.emit(delta.x(), delta.y())
                self.overrideCursor(CURSOR_MOVE)
            else:
                self.endPan()
            ev.accept()
            return
        if self._spacePanHeld or self._spacePanSuppressMouse:
            if self._spacePanHeld:
                self.overrideCursor(CURSOR_GRAB)
            ev.accept()
            return
        pos = self.transformPos(ev.pos())
        if self.selectedShape and self.selectedShape.locked and ev.buttons() & (Qt.LeftButton | Qt.RightButton):
            self.status.emit('当前框已锁定；请先解锁')
            return

        self.restoreCursor()

        # Polygon drawing.
        if self.drawing() and self.current and not self._editingGesture:

            self.overrideCursor(CURSOR_DRAW)
            if self.current:
                color = self.lineColor
                if self.outOfPixmap(pos):
                    # Don't allow the user to draw outside the pixmap.
                    # Project the point to the pixmap's edges.
                    pos = self.intersectionPoint(self.current[-1], pos)
                elif len(self.current) > 1 and self.closeEnough(pos, self.current[0]):
                    # Attract line to starting point and colorise to alert the
                    # user:                    
                    pos = self.current[0]
                    color = self.current.line_color
                    self.overrideCursor(CURSOR_POINT)
                    self.current.highlightVertex(0, Shape.NEAR_VERTEX)
                self.line[1] = pos
                self.line.line_color = color
                self.repaint()
                self.current.highlightClear()
                self.status.emit("width is %d, height is %d." % (pos.x()-self.line[0].x(), pos.y()-self.line[0].y()))
            return

        # Polygon copy moving.
        if self._rotatingGesture and ev.buttons() & (Qt.LeftButton | Qt.RightButton):
            self.recordGesture()
            angle = self.getAngle(self.selectedShape.center, pos, self.prevPoint)
            if not self.rotateOutOfBound(angle):
                self.selectedShape.rotate(angle)
                self.prevPoint = pos
                self.shapeMoved.emit()
                self.update()
            return

        if Qt.RightButton & ev.buttons():
            # print("right button")
            # if self.selectedShapeCopy and self.prevPoint:
            #     print("select shape copy")
            #     self.overrideCursor(CURSOR_MOVE)
            #     self.boundedMoveShape(self.selectedShapeCopy, pos)
            #     self.repaint()
            # elif self.selectedShape:
            #     print("select shape")
            #     self.selectedShapeCopy = self.selectedShape.copy()
            #     self.repaint()
            if self.selectedVertex() and self.selectedShape and self.selectedShape.isRotated:
                self.boundedRotateShape(pos)
                self.shapeMoved.emit()
                self.repaint()
            self.status.emit("(%d,%d)." % (pos.x(), pos.y()))
            return

        # Polygon/Vertex moving.
        if Qt.LeftButton & ev.buttons() and self._editingGesture:
            self.recordGesture()
            if self.selectedVertex():
                # if self.outOfPixmap(pos):
                #     print("chule ")
                #     return
                # else:
                # print("meiyou chujie")
                self.boundedMoveVertex(pos)
                self.shapeMoved.emit()
                self.repaint()
            elif self.selectedShape and self.prevPoint:
                self.overrideCursor(CURSOR_MOVE)
                self.boundedMoveShape(self.selectedShape, pos)
                self.shapeMoved.emit()
                self.repaint()
                self.status.emit("(%d,%d)." % (pos.x(), pos.y()))
            return

        # Just hovering over the canvas, 2 posibilities:
        # - Highlight shapes
        # - Highlight vertex
        # Update shape/vertex fill and tooltip value accordingly.
        self.setToolTip("Image")
        rotation_shape = self.rotationAt(pos)
        if rotation_shape:
            self.overrideCursor(Qt.SizeAllCursor)
            self.setToolTip('左键拖动圆形手柄旋转')
            return
        candidates = self.hitShapes()
        vertex_shape, vertex_index = self.vertexAt(pos)
        for shape in ([vertex_shape] if vertex_shape else candidates):
            # Look for a nearby vertex to highlight. If that fails,
            # check if we happen to be inside a shape.
            index = vertex_index if shape is vertex_shape else None
            if index is not None:
                if self.selectedVertex():
                    self.hShape.highlightClear()
                self.hVertex, self.hShape = index, shape
                shape.highlightVertex(index, shape.MOVE_VERTEX)
                self.overrideCursor(CURSOR_POINT)
                # self.setToolTip("Click & drag to move point.")
                # self.setStatusTip(self.toolTip())
                self.update()
                break
            elif self.containsHit(shape, pos):
                if self.selectedVertex():
                    self.hShape.highlightClear()
                self.hVertex, self.hShape = None, shape
                # self.setToolTip(
                #     "Click & drag to move shape '%s'" % shape.label)
                # self.setStatusTip(self.toolTip())
                self.overrideCursor(CURSOR_GRAB)
                self.update()
                break
        else:  # Nothing found, clear highlights, reset state.
            if self.hShape:
                self.hShape.highlightClear()
                self.update()
            self.hVertex, self.hShape = None, None
            self.overrideCursor(CURSOR_DRAW if self.drawing() else CURSOR_DEFAULT)
        
        self.status.emit("(%d,%d)." % (pos.x(), pos.y()))
        

    def mousePressEvent(self, ev):
        self._lastGlobalPos = ev.globalPos()
        self._spacePanSuppressMouse = False
        pos = self.transformPos(ev.pos())
        self.setFocus(Qt.MouseFocusReason)
        if self._panButton != Qt.NoButton:
            ev.accept()
            return
        explicit_pan = ev.button() == Qt.MiddleButton or (
            ev.button() == Qt.LeftButton and (self._spacePanHeld or bool(ev.modifiers() & Qt.AltModifier)))
        empty_pan = (ev.button() == Qt.LeftButton and self.editing()
                     and self.vertexAt(pos)[0] is None and self.rotationAt(pos) is None
                     and not any(self.containsHit(shape, pos) for shape in self.hitShapes()))
        if self.pixmap is not None and not self.pixmap.isNull() and (explicit_pan or empty_pan):
            self._panButton = ev.button()
            self._panGlobalPos = ev.globalPos()
            self.overrideCursor(CURSOR_MOVE)
            self.status.emit('拖动影像 · 空格 + 左键、中键或 Alt + 左键可在标注上拖动影像')
            ev.accept()
            return
        if self._spacePanHeld:
            ev.accept()
            return
        # print('sldkfj %d %d' % (pos.x(), pos.y()))
        if ev.button() == Qt.LeftButton:
            force_draw = self.drawing() and bool(ev.modifiers() & Qt.ControlModifier)
            rotation_shape = self.rotationAt(pos)
            hit = rotation_shape or self.vertexAt(pos)[0] or next(
                (s for s in self.hitShapes() if self.containsHit(s, pos)), None)
            if hit and self.current is None and not force_draw:
                if rotation_shape:
                    self.selectShape(rotation_shape)
                else:
                    self.selectShapePoint(pos)
                self._editingGesture = not hit.locked
                self._rotatingGesture = rotation_shape is not None
                self._editRecorded = False
                self.prevPoint = pos
                self.update()
            elif self.drawing():
                self.deSelectShape()
                self.unHighlight()
                self.handleDrawing(pos)
            else:                
                self.selectShapePoint(pos)
                self.prevPoint = pos
                self.repaint()
        elif ev.button() == Qt.RightButton and self.current is None:
            self.selectShapePoint(pos)
            if self.selectedShape and self.selectedShape.locked:
                self.status.emit('当前框已锁定；请先解锁')
                return
            self._editingGesture = self.selectedShape is not None
            self._rotatingGesture = bool(self.selectedVertex() and self.selectedShape and self.selectedShape.isRotated)
            self._editRecorded = False
            self.hideBackroundShapes(True)
            # if self.selectedShape is not None:
            #     print('point is (%d, %d)' % (pos.x(), pos.y()))
            #     self.selectedShape.rotate(10)

            self.prevPoint = pos
            self.repaint()

    def mouseReleaseEvent(self, ev):  
        self._lastGlobalPos = ev.globalPos()
        if self._panButton != Qt.NoButton:
            if ev.button() == self._panButton:
                self.endPan()
            ev.accept()
            return
        if self._spacePanHeld or self._spacePanSuppressMouse:
            self._spacePanSuppressMouse = False
            ev.accept()
            return
        if self._editingGesture:
            self._editingGesture = self._rotatingGesture = False
            self.hideBackroundShapes(False)
            self.update()
            return
        self.hideBackroundShapes(False)      
        if ev.button() == Qt.RightButton and not self.selectedVertex():            
            menu = self.menus[bool(self.selectedShapeCopy)]
            self.restoreCursor()
            if not menu.exec_(self.mapToGlobal(ev.pos()))\
               and self.selectedShapeCopy:
                # Cancel the move by deleting the shadow copy.
                self.selectedShapeCopy = None
                self.repaint()
        elif ev.button() == Qt.LeftButton and self.selectedShape:
            self.overrideCursor(CURSOR_GRAB)
        elif ev.button() == Qt.LeftButton:
            pos = self.transformPos(ev.pos())
            if self.drawing() and self.current:
                self.line[1] = pos if not self.outOfPixmap(pos) else self.intersectionPoint(self.current[0], pos)
                if distance(self.line[1] - self.current[0]) * self.scale < 2:
                    self.current = None
                    self.drawingPolygon.emit(False)
                    self.update()
                    return
                self.handleDrawing(pos)

    def recordGesture(self):
        if not self._editRecorded:
            self.editStarted.emit()
            self._editRecorded = True

    def containsHit(self, shape, point):
        if shape.containsPoint(point):
            return True
        # A screen-space tolerance makes tiny boxes and their edges selectable.
        stroker = QPainterPathStroker()
        stroker.setWidth(12.0 / self.scale)
        path = shape.makePath()
        path.closeSubpath()
        return stroker.createStroke(path).contains(point)

    def rotationHandle(self, shape):
        midpoint = (shape[0] + shape[1]) / 2
        outward = midpoint - shape.center
        length = distance(outward)
        if length < 1e-9:
            outward, length = QPointF(0, -1), 1
        handle = midpoint + outward * (28.0 / self.scale / length)
        if self.outOfPixmap(handle):
            handle = midpoint - outward * (28.0 / self.scale / length)
        return handle

    def rotationAt(self, point):
        for shape in self.hitShapes():
            if not shape.locked and shape.isRotated and (shape.selected or shape is self.hShape):
                if distance(point - self.rotationHandle(shape)) * self.scale <= 11:
                    return shape
        return None

    def endMove(self, copy=False):
        assert self.selectedShape and self.selectedShapeCopy
        shape = self.selectedShapeCopy
        if copy:
            shape.identifier = None
            shape.locked = False
        #del shape.fill_color
        #del shape.line_color
        if copy:
            self.shapes.append(shape)
            self.selectedShape.selected = False
            self.selectedShape = shape
            self.repaint()
        else:
            self.selectedShape.points = [p for p in shape.points]
        self.selectedShapeCopy = None

    def hideBackroundShapes(self, value):
        # print("hideBackroundShapes")
        self.hideBackround = value
        if self.selectedShape:
            # Only hide other shapes if there is a current selection.
            # Otherwise the user will not be able to select a shape.
            self.setHiding(True)
            self.repaint()

    def handleDrawing(self, pos):
        if self.current and self.current.reachMaxPoints() is False:
            initPos = self.current[0]
            minX = initPos.x()
            minY = initPos.y()
            targetPos = self.line[1]
            maxX = targetPos.x()
            maxY = targetPos.y()
            self.current.addPoint(QPointF(maxX, minY))
            self.current.addPoint(targetPos)
            self.current.addPoint(QPointF(minX, maxY))
            self.current.addPoint(initPos)
            self.line[0] = self.current[-1]
            if self.current.isClosed():
                self.finalise()
        elif not self.outOfPixmap(pos):
            self.current = Shape()
            self.current.addPoint(pos)
            self.line.points = [pos, pos]
            self.setHiding()
            self.drawingPolygon.emit(True)
            self.update()

    def setHiding(self, enable=True):
        self._hideBackround = self.hideBackround if enable else False

    def canCloseShape(self):
        return self.drawing() and self.current and len(self.current) > 2

    def mouseDoubleClickEvent(self, ev):
        # We need at least 4 points here, since the mousePress handler
        # adds an extra one before this handler is called.
        if self.canCloseShape() and len(self.current) > 3:
            self.current.popPoint()
            self.finalise()

    def selectShape(self, shape):
        if self.selectedShape is shape:
            return
        self.deSelectShape()
        shape.selected = True
        self.selectedShape = shape
        self.setHiding()
        self.selectionChanged.emit(True)
        self.update()

    def selectShapePoint(self, point):
        """Select the first shape created which contains this point."""
        # Hit-test at press time; selection signals can synchronously clear hover.
        vertex_shape, vertex_index = self.vertexAt(point)
        self.deSelectShape()
        if vertex_shape is not None:
            index, shape = vertex_index, vertex_shape
            self.hVertex, self.hShape = index, shape
            shape.highlightVertex(index, shape.MOVE_VERTEX)

            shape.selected = True
            self.selectedShape = shape
            self.calculateOffsets(shape, point)
            self.setHiding()
            self.selectionChanged.emit(True)
            self.hVertex, self.hShape = index, shape

            return
        self.unHighlight()
        for shape in self.hitShapes():
            if self.containsHit(shape, point):
                shape.selected = True
                self.selectedShape = shape
                self.calculateOffsets(shape, point)
                self.setHiding()
                self.selectionChanged.emit(True)
                return

    def cycleOverlapping(self):
        point = self._hoverPoint if hasattr(self, '_hoverPoint') else self.prevPoint
        visible = set(self.hitShapes())
        candidates = [s for s in reversed(self.shapes) if s in visible and self.containsHit(s, point)]
        if candidates:
            current = candidates.index(self.selectedShape) if self.selectedShape in candidates else -1
            self.selectShape(candidates[(current + 1) % len(candidates)])
            self.status.emit('已选择重叠框；Alt + Q 可继续切换')

    def hitShapes(self):
        shapes = [s for s in reversed(self.shapes) if self.isVisible(s)
                  and not (s.isRotated and self.hideRotated)
                  and not (not s.isRotated and self.hideNormal)]
        if self.selectedShape in shapes:
            shapes.remove(self.selectedShape)
            shapes.insert(0, self.selectedShape)
        return shapes

    def vertexAt(self, point):
        for shape in self.hitShapes():
            if shape.locked:
                continue
            bounds = shape.boundingRect()
            if (bounds.width() * self.scale < 2 * self.epsilon
                    and bounds.height() * self.scale < 2 * self.epsilon
                    and shape.containsPoint(point)):
                # For tiny boxes, keep the interior available for moving;
                # enlarged corner targets remain accessible outside the box.
                continue
            index = shape.nearestVertex(point, self.epsilon / self.scale)
            if index is not None:
                return shape, index
        return None, None

    def calculateOffsets(self, shape, point):
        rect = shape.boundingRect()
        x1 = rect.x() - point.x()
        y1 = rect.y() - point.y()
        x2 = (rect.x() + rect.width()) - point.x()
        y2 = (rect.y() + rect.height()) - point.y()
        self.offsets = QPointF(x1, y1), QPointF(x2, y2)

    def boundedMoveVertex(self, pos):
        # print("Moving Vertex")
        index, shape = self.hVertex, self.hShape
        if shape.locked:
            return
        point = shape[index]

        if not self.canOutOfBounding and self.outOfPixmap(pos):
            return
            # pos = self.intersectionPoint(point, pos)

        # print("index is %d" % index)
        sindex = (index + 2) % 4
        # get the other 3 points after transformed
        p2,p3,p4 = self.getAdjointPoints(shape.direction, shape[sindex], pos, index)
        candidate = [QPointF(p) for p in shape.points]
        candidate[index], candidate[(index + 1) % 4], candidate[(index + 3) % 4] = pos, p2, p4
        try:
            validate_box([(p.x(), p.y()) for p in candidate])
        except ValueError:
            self.status.emit('不能把标注框缩成零宽或零高')
            return
        
        pcenter = (pos+p3)/2        
        if self.canOutOfBounding and self.outOfPixmap(pcenter):
            return
        # if one pixal out of map , do nothing
        if not self.canOutOfBounding and (self.outOfPixmap(p2) or
            self.outOfPixmap(p3) or
            self.outOfPixmap(p4)):
                return

        # move 4 pixal one by one 
        shape.moveVertexBy(index, pos - point)
        lindex = (index + 1) % 4
        
        rindex = (index + 3) % 4
        shape[lindex] = p2
        # shape[sindex] = p3
        shape[rindex] = p4
        shape.close()

        # calculate the height and weight, and show it
        w = math.sqrt((p4.x()-p3.x()) ** 2 + (p4.y()-p3.y()) ** 2)
        h = math.sqrt((p3.x()-p2.x()) ** 2 + (p3.y()-p2.y()) ** 2)
        self.status.emit("width is %d, height is %d." % (w,h))

    
    def getAdjointPoints(self, theta, p3, p1, index):
        # Orthogonal projections remain stable at 90/270 degrees, unlike slopes.
        axis = QPointF(math.cos(theta), math.sin(theta))
        normal = QPointF(-math.sin(theta), math.cos(theta))
        delta = p3 - p1
        along = axis * (delta.x() * axis.x() + delta.y() * axis.y())
        across = normal * (delta.x() * normal.x() + delta.y() * normal.y())
        p2, p4 = p1 + along, p1 + across
        return (p2, p3, p4) if index % 2 == 0 else (p4, p3, p2)

    def boundedRotateShape(self, pos):
        # print("Rotate Shape2")          
        # judge if some vertex is out of pixma
        index, shape = self.hVertex, self.hShape
        if shape.locked:
            return
        point = shape[index]

        angle = self.getAngle(shape.center,pos,point)
        # for i, p in enumerate(shape.points):
        #     if self.outOfPixmap(shape.rotatePoint(p,angle)):
        #         # print("out of pixmap")
        #         return
        if not self.rotateOutOfBound(angle):
            shape.rotate(angle)
            self.prevPoint = pos

    def getAngle(self, center, p1, p2):
        dx1 = p1.x() - center.x();
        dy1 = p1.y() - center.y();

        dx2 = p2.x() - center.x();
        dy2 = p2.y() - center.y();

        c = math.sqrt(dx1*dx1 + dy1*dy1) * math.sqrt(dx2*dx2 + dy2*dy2)
        if c == 0: return 0
        y = (dx1*dx2+dy1*dy2)/c
        if y>1: return 0
        angle = math.acos(y)

        if (dx1*dy2-dx2*dy1)>0:   
            return angle
        else:
            return -angle

    def boundedMoveShape(self, shape, pos):
        if shape.locked:
            return
        if shape.isRotated and self.canOutOfBounding:
            c = shape.center
            dp = pos - self.prevPoint
            dc = c + dp
            if dc.x() < 0:
                dp -= QPointF(min(0,dc.x()), 0)
            if dc.y() < 0:                
                dp -= QPointF(0, min(0,dc.y()))                
            if dc.x() >= self.imageSize.width():
                dp += QPointF(min(0, self.imageSize.width() - 1  - dc.x()), 0)
            if dc.y() >= self.imageSize.height():
                dp += QPointF(0, min(0, self.imageSize.height() - 1 - dc.y()))

        else:            
            if self.outOfPixmap(pos):
                return False  # No need to move
            o1 = pos + self.offsets[0]
            if self.outOfPixmap(o1):
                pos -= QPointF(min(0, o1.x()), min(0, o1.y()))
            o2 = pos + self.offsets[1]
            if self.outOfPixmap(o2):
                pos += QPointF(min(0, self.imageSize.width() - 1 - o2.x()),
                               min(0, self.imageSize.height() - 1 - o2.y()))
            dp = pos - self.prevPoint
        # The next line tracks the new position of the cursor
        # relative to the shape, but also results in making it
        # a bit "shaky" when nearing the border and allows it to
        # go outside of the shape's area for some reason. XXX
        #self.calculateOffsets(self.selectedShape, pos)
        
        if dp:
            shape.moveBy(dp)
            self.prevPoint = pos
            shape.close()
            return True
        return False


    def boundedMoveShape2(self, shape, pos):
        if self.outOfPixmap(pos):
            return False  # No need to move
        o1 = pos + self.offsets[0]
        if self.outOfPixmap(o1):
            pos -= QPointF(min(0, o1.x()), min(0, o1.y()))
        o2 = pos + self.offsets[1]
        if self.outOfPixmap(o2):
            pos += QPointF(min(0, self.imageSize.width() - o2.x()),
                           min(0, self.imageSize.height() - o2.y()))
        # The next line tracks the new position of the cursor
        # relative to the shape, but also results in making it
        # a bit "shaky" when nearing the border and allows it to
        # go outside of the shape's area for some reason. XXX
        #self.calculateOffsets(self.selectedShape, pos)
        dp = pos - self.prevPoint
        if dp:
            shape.moveBy(dp)
            self.prevPoint = pos
            shape.close()
            return True
        return False

    def deSelectShape(self):
        for shape in self.shapes:
            shape.selected = False
        if self.selectedShape:
            self.selectedShape.selected = False
            self.selectedShape = None
            self.setHiding(False)
            self.selectionChanged.emit(False)
            self.update()

    def deleteSelected(self):
        if self.selectedShape:
            shape = self.selectedShape
            self.shapes.remove(self.selectedShape)
            self.selectedShape = None
            self.update()
            return shape

    def copySelectedShape(self):
        if self.selectedShape:
            shape = self.selectedShape.copy()
            shape.identifier = None
            shape.locked = False
            self.deSelectShape()
            self.shapes.append(shape)
            shape.selected = True
            self.selectedShape = shape
            self.boundedShiftShape(shape)
            return shape

    def boundedShiftShape(self, shape):
        # Try to move in one direction, and if it fails in another.
        # Give up if both fail.
        point = shape[0]
        offset = QPointF(2.0, 2.0)
        self.calculateOffsets(shape, point)
        self.prevPoint = point
        if not self.boundedMoveShape(shape, point - offset):
            self.boundedMoveShape(shape, point + offset)

    def paintEvent(self, event):
        if self.pixmap is None or self.pixmap.isNull():
            p = QPainter(self)
            p.fillRect(self.rect(), QColor('#e9edf3'))
            p.setPen(QColor('#556780'))
            font = p.font()
            font.setPointSize(18)
            p.setFont(font)
            p.drawText(self.rect().adjusted(24, -35, -24, -35), Qt.AlignCenter, '遥感影像标注')
            font.setPointSize(10)
            p.setFont(font)
            p.setPen(QColor('#75859b'))
            p.drawText(self.rect().adjusted(24, 35, -24, 35), Qt.AlignCenter,
                       'Ctrl + O 打开影像    ·    Ctrl + U 打开目录\nF1 查看操作快捷说明')
            return

        p = self._painter
        p.begin(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.HighQualityAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        p.scale(self.scale, self.scale)
        p.translate(self.offsetToCenter())

        p.drawPixmap(QRectF(0, 0, self.imageSize.width(), self.imageSize.height()),
                     self.pixmap, QRectF(self.pixmap.rect()))
        if self.detailPixmap is not None:
            p.drawPixmap(self.detailRect, self.detailPixmap, QRectF(self.detailPixmap.rect()))
        Shape.scale = self.scale
        for shape in self.shapes:
            if (shape.selected or not self._hideBackround) and self.isVisible(shape):
                if (shape.isRotated and not self.hideRotated) or (not shape.isRotated and not self.hideNormal):
                    shape.fill = shape.selected or shape == self.hShape
                    shape.paint(p)
                    if not shape.locked and shape.isRotated and (shape.selected or shape is self.hShape):
                        p.save()
                        handle = self.rotationHandle(shape)
                        p.setPen(QPen(QColor('#2463cf'), 2.0 / self.scale))
                        p.drawLine((shape[0] + shape[1]) / 2, handle)
                        p.setBrush(QColor('#ffffff'))
                        p.drawEllipse(handle, 7.0 / self.scale, 7.0 / self.scale)
                        p.restore()
                elif self.showCenter:
                    shape.fill = shape.selected or shape == self.hShape
                    shape.paintNormalCenter(p)

        # Captions follow the same visibility rules as their boxes and are
        # painted after all outlines, so neighboring boxes cannot cover them.
        for shape in self.shapes:
            if ((shape.selected or not self._hideBackround) and self.isVisible(shape)
                    and ((shape.isRotated and not self.hideRotated)
                         or (not shape.isRotated and not self.hideNormal))):
                shape.paintLabel(p)

        if self.current:
            self.current.paint(p)
            self.line.paint(p)
        if self.selectedShapeCopy:
            self.selectedShapeCopy.paint(p)

        # Paint rect
        if self.current is not None and len(self.line) == 2:
            leftTop = self.line[0]
            rightBottom = self.line[1]
            rectWidth = rightBottom.x() - leftTop.x()
            rectHeight = rightBottom.y() - leftTop.y()
            color = QColor(0, 220, 0)
            p.setPen(color)
            brush = QBrush(Qt.BDiagPattern)
            p.setBrush(brush)
            p.drawRect(QRectF(leftTop.x(), leftTop.y(), rectWidth, rectHeight))
            
            #draw dialog line of rectangle
            p.setPen(self.lineColor)
            p.drawLine(QPointF(leftTop.x(), rightBottom.y()), QPointF(rightBottom.x(), leftTop.y()))

        self.setAutoFillBackground(True)
        if self.verified:
            pal = self.palette()
            pal.setColor(self.backgroundRole(), QColor(184, 239, 38, 128))
            self.setPalette(pal)
        else:
            pal = self.palette()
            pal.setColor(self.backgroundRole(), QColor('#e9edf3'))
            self.setPalette(pal)

        p.end()

    def transformPos(self, point):
        """Convert from widget-logical coordinates to painter-logical coordinates."""
        return point / self.scale - self.offsetToCenter()

    def offsetToCenter(self):
        s = self.scale
        if not self.viewportSize.isEmpty():
            # The image has a viewport of scrollable space on each side,
            # even when it is smaller than the workspace. Its origin and all
            # movement therefore belong to the scrollbar coordinate system.
            return QPointF(self.viewportSize.width() / s, self.viewportSize.height() / s)
        area = super(Canvas, self).size()
        w, h = self.imageSize.width() * s, self.imageSize.height() * s
        aw, ah = area.width(), area.height()
        x = (aw - w) / (2 * s) if aw > w else 0
        y = (ah - h) / (2 * s) if ah > h else 0
        return QPointF(x, y) + self.viewOffset / s

    def outOfPixmap(self, p):
        w, h = self.imageSize.width(), self.imageSize.height()
        return not (0 <= p.x() < w and 0 <= p.y() < h)

    def finalise(self):
        assert self.current
        try:
            validate_box([(p.x(), p.y()) for p in self.current.points])
        except ValueError:
            self.current = None
            self.line.points = []
            self.setHiding(False)
            self.drawingPolygon.emit(False)
            self.status.emit('已取消无效框：请拖动绘制具有宽度和高度的矩形')
            self.update()
            return
        self.current.isRotated = self.canDrawRotatedRect
        # print(self.canDrawRotatedRect)
        self.current.close()
        self.shapes.append(self.current)
        self.current = None
        self.setHiding(False)
        self.drawingPolygon.emit(False)
        self.newShape.emit()
        self.update()

    def closeEnough(self, p1, p2):
        #d = distance(p1 - p2)
        #m = (p1-p2).manhattanLength()
        # print "d %.2f, m %d, %.2f" % (d, m, d - m)
        return distance(p1 - p2) < self.epsilon

    def intersectionPoint(self, p1, p2):
        # Cycle through each image edge in clockwise fashion,
        # and find the one intersecting the current line segment.
        # http://paulbourke.net/geometry/lineline2d/
        size = self.imageSize
        points = [(0, 0),
                  (size.width(), 0),
                  (size.width(), size.height()),
                  (0, size.height())]
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        d, i, (x, y) = min(self.intersectingEdges((x1, y1), (x2, y2), points))
        x3, y3 = points[i]
        x4, y4 = points[(i + 1) % 4]
        if (x, y) == (x1, y1):
            # Handle cases where previous point is on one of the edges.
            if x3 == x4:
                return QPointF(x3, min(max(0, y2), max(y3, y4)))
            else:  # y3 == y4
                return QPointF(min(max(0, x2), max(x3, x4)), y3)
        return QPointF(x, y)

    def intersectingEdges(self, x1y1, x2y2, points):
        """For each edge formed by `points', yield the intersection
        with the line segment `(x1,y1) - (x2,y2)`, if it exists.
        Also return the distance of `(x2,y2)' to the middle of the
        edge along with its index, so that the one closest can be chosen."""
        x1, y1 = x1y1
        x2, y2 = x2y2
        for i in range(4):
            x3, y3 = points[i]
            x4, y4 = points[(i + 1) % 4]
            denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
            nua = (x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)
            nub = (x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)
            if denom == 0:
                # This covers two cases:
                #   nua == nub == 0: Coincident
                #   otherwise: Parallel
                continue
            ua, ub = nua / denom, nub / denom
            if 0 <= ua <= 1 and 0 <= ub <= 1:
                x = x1 + ua * (x2 - x1)
                y = y1 + ua * (y2 - y1)
                m = QPointF((x3 + x4) / 2, (y3 + y4) / 2)
                d = distance(m - QPointF(x2, y2))
                print("return=",d,i,(x,y))
                yield d, i, (x, y)

    # These two, along with a call to adjustSize are required for the
    # scroll area.
    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        if self.pixmap:
            return QSize(max(1, math.ceil(self.scale * self.imageSize.width())) + 2 * self.viewportSize.width(),
                         max(1, math.ceil(self.scale * self.imageSize.height())) + 2 * self.viewportSize.height())
        return super(Canvas, self).minimumSizeHint()

    def wheelEvent(self, ev):
        qt_version = 4 if hasattr(ev, "delta") else 5
        if qt_version == 4:
            if ev.orientation() == Qt.Vertical:
                v_delta = ev.delta()
                h_delta = 0
            else:
                h_delta = ev.delta()
                v_delta = 0
        else:
            delta = ev.angleDelta()
            h_delta = delta.x()
            v_delta = delta.y()
        # print('scrolling vdelta is %d, hdelta is %d' % (v_delta, h_delta))
        mods = ev.modifiers()
        if Qt.ControlModifier == int(mods) and v_delta:
            self.zoomAnchor = self.mapToGlobal(ev.pos())
            self.zoomRequest.emit(v_delta)
            self.zoomAnchor = None
        else:
            if mods & Qt.ShiftModifier and v_delta:
                self.scrollRequest.emit(v_delta, Qt.Horizontal)
            elif v_delta:
                self.scrollRequest.emit(v_delta, Qt.Vertical)
            h_delta and self.scrollRequest.emit(h_delta, Qt.Horizontal)
        ev.accept()

    def keyPressEvent(self, ev):
        key = ev.key()
        if key == Qt.Key_Space:
            if not ev.isAutoRepeat():
                self.setSpacePan(True)
            ev.accept()
            return
        if self._spacePanHeld:
            ev.accept()
            return
        if not (ev.modifiers() & Qt.ControlModifier) and self.selectedShape and self.selectedShape.locked and key in (
                Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down, Qt.Key_Z, Qt.Key_X, Qt.Key_C, Qt.Key_V):
            self.status.emit('当前框已锁定；请先解锁')
            ev.accept()
            return
        if ev.modifiers() & Qt.ControlModifier:
            ev.ignore()
            return
        if self.selectedShape and key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down,
                                          Qt.Key_Z, Qt.Key_X, Qt.Key_C, Qt.Key_V):
            self.editStarted.emit()
        
        if key == Qt.Key_Escape and self.current:
            print('ESC press')
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
        elif key == Qt.Key_Return and self.canCloseShape():
            self.finalise()
        elif key == Qt.Key_Left and self.selectedShape:
            self.moveOnePixel('Left')
        elif key == Qt.Key_Right and self.selectedShape:
            self.moveOnePixel('Right')
        elif key == Qt.Key_Up and self.selectedShape:
            self.moveOnePixel('Up')
        elif key == Qt.Key_Down and self.selectedShape:
            self.moveOnePixel('Down')
        elif key == Qt.Key_Z and self.selectedShape and\
             self.selectedShape.isRotated and not self.rotateOutOfBound(0.1):
            self.selectedShape.rotate(0.1)
            self.shapeMoved.emit() 
            self.update()  
        elif key == Qt.Key_X and self.selectedShape and\
             self.selectedShape.isRotated and not self.rotateOutOfBound(0.01):
            self.selectedShape.rotate(0.01) 
            self.shapeMoved.emit()
            self.update()  
        elif key == Qt.Key_C and self.selectedShape and\
             self.selectedShape.isRotated and not self.rotateOutOfBound(-0.01):
            self.selectedShape.rotate(-0.01) 
            self.shapeMoved.emit()
            self.update()  
        elif key == Qt.Key_V and self.selectedShape and\
             self.selectedShape.isRotated and not self.rotateOutOfBound(-0.1):
            self.selectedShape.rotate(-0.1)
            self.shapeMoved.emit()
            self.update()
        elif key == Qt.Key_R:
            self.hideRotated = not self.hideRotated
            self.hideRRect.emit(self.hideRotated)
            self.update()
        elif key == Qt.Key_N:
            self.hideNormal = not self.hideNormal
            self.hideNRect.emit(self.hideNormal)
            self.update()
        elif key == Qt.Key_O:
            self.canOutOfBounding = not self.canOutOfBounding
        elif key == Qt.Key_B:
            self.showCenter = not self.showCenter
            self.update()


    def rotateOutOfBound(self, angle):
        if self.canOutOfBounding:
            return False
        for i, p in enumerate(self.selectedShape.points):
            if self.outOfPixmap(self.selectedShape.rotatePoint(p,angle)):
                return True
        return False

    def keyReleaseEvent(self, ev):
        if ev.key() == Qt.Key_Space:
            if not ev.isAutoRepeat():
                self.setSpacePan(False)
            ev.accept()
            return
        super(Canvas, self).keyReleaseEvent(ev)

    def moveOnePixel(self, direction):
        # print(self.selectedShape.points)
        if direction == 'Left' and not self.moveOutOfBound(QPointF(-1.0, 0)):
            # print("move Left one pixel")
            self.selectedShape.points[0] += QPointF(-1.0, 0)
            self.selectedShape.points[1] += QPointF(-1.0, 0)
            self.selectedShape.points[2] += QPointF(-1.0, 0)
            self.selectedShape.points[3] += QPointF(-1.0, 0)
            self.selectedShape.center += QPointF(-1.0, 0)
        elif direction == 'Right' and not self.moveOutOfBound(QPointF(1.0, 0)):
            # print("move Right one pixel")
            self.selectedShape.points[0] += QPointF(1.0, 0)
            self.selectedShape.points[1] += QPointF(1.0, 0)
            self.selectedShape.points[2] += QPointF(1.0, 0)
            self.selectedShape.points[3] += QPointF(1.0, 0)
            self.selectedShape.center += QPointF(1.0, 0)
        elif direction == 'Up' and not self.moveOutOfBound(QPointF(0, -1.0)):
            # print("move Up one pixel")
            self.selectedShape.points[0] += QPointF(0, -1.0)
            self.selectedShape.points[1] += QPointF(0, -1.0)
            self.selectedShape.points[2] += QPointF(0, -1.0)
            self.selectedShape.points[3] += QPointF(0, -1.0)
            self.selectedShape.center += QPointF(0, -1.0)
        elif direction == 'Down' and not self.moveOutOfBound(QPointF(0, 1.0)):
            # print("move Down one pixel")
            self.selectedShape.points[0] += QPointF(0, 1.0)
            self.selectedShape.points[1] += QPointF(0, 1.0)
            self.selectedShape.points[2] += QPointF(0, 1.0)
            self.selectedShape.points[3] += QPointF(0, 1.0)
            self.selectedShape.center += QPointF(0, 1.0)
        self.shapeMoved.emit()
        self.repaint()

    def moveOutOfBound(self, step):
        points = [p1+p2 for p1, p2 in zip(self.selectedShape.points, [step]*4)]
        return True in map(self.outOfPixmap, points)

    def setLastLabel(self, text):
        assert text
        self.shapes[-1].label = text
        return self.shapes[-1]

    def undoLastLine(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.setOpen()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)

    def resetAllLines(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.setOpen()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)
        self.current = None
        self.drawingPolygon.emit(False)
        self.update()

    def loadPixmap(self, pixmap, imageSize=None):
        self.viewOffset = QPointF()
        self.pixmap = pixmap
        self.imageSize = imageSize or pixmap.size()
        self.detailPixmap = self.detailRect = None
        self.shapes = []
        self.repaint()

    def loadShapes(self, shapes):
        self.unHighlight()
        self.selectedShape = None
        self.shapes = list(shapes)
        self.current = None
        self.repaint()

    def setShapeVisible(self, shape, value):
        self.visible[shape] = value
        self.repaint()

    def overrideCursor(self, cursor):
        self.restoreCursor()
        self._cursor = cursor
        QApplication.setOverrideCursor(cursor)

    def restoreCursor(self):
        QApplication.restoreOverrideCursor()

    def resetState(self):
        self.setSpacePan(False)
        self._spacePanSuppressMouse = False
        self._lastGlobalPos = None
        self.viewOffset = QPointF()
        self._editingGesture = self._rotatingGesture = False
        self.endPan()
        self.restoreCursor()
        self.pixmap = None
        self.imageSize = QSize()
        self.detailPixmap = self.detailRect = None
        self.shapes = []
        self.current = self.selectedShape = self.selectedShapeCopy = None
        self.hShape = self.hVertex = None
        self.visible.clear()
        self.verified = False
        self.update()
