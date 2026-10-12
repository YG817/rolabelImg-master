"""A bounded uniform grid for point picking and clipped annotation painting."""
import math
from PyQt5.QtCore import QRectF


class ShapeIndex:
    CELL = 256.0
    MAX_SHAPE_CELLS = 256

    def __init__(self):
        self.reset([])

    def reset(self, shapes):
        self.shapes = shapes
        self._listDirty = True
        self._dirty = set()
        self._records = {}
        self._buckets = {}
        self._large = set()
        self.maxLabelLength = 0

    def listChanged(self):
        self._listDirty = True

    def geometryChanged(self, shape):
        if shape in self._records:
            self._dirty.add(shape)

    def cells(self, rect, maximum):
        left, right = math.floor(rect.left() / self.CELL), math.floor(rect.right() / self.CELL)
        top, bottom = math.floor(rect.top() / self.CELL), math.floor(rect.bottom() / self.CELL)
        if (right - left + 1) * (bottom - top + 1) > maximum:
            return None
        return [(x, y) for x in range(left, right + 1) for y in range(top, bottom + 1)]

    def add(self, shape, rank):
        rect = shape.boundingRect()
        cells = self.cells(rect, self.MAX_SHAPE_CELLS)
        self._records[shape] = (rank, rect, cells)
        self.maxLabelLength = max(self.maxLabelLength, len(str(shape.label or '')))
        if cells is None:
            self._large.add(shape)
        else:
            for cell in cells:
                self._buckets.setdefault(cell, set()).add(shape)

    def remove(self, shape):
        rank, rect, cells = self._records.pop(shape)
        if cells is None:
            self._large.discard(shape)
        else:
            for cell in cells:
                bucket = self._buckets[cell]
                bucket.discard(shape)
                if not bucket:
                    del self._buckets[cell]
        return rank

    def synchronize(self):
        if self._listDirty:
            self._records.clear()
            self._buckets.clear()
            self._large.clear()
            self.maxLabelLength = 0
            for rank, shape in enumerate(self.shapes):
                shape.watchGeometry(self.geometryChanged)
                self.add(shape, rank)
            self._listDirty = False
            self._dirty.clear()
        else:
            dirty, self._dirty = self._dirty, set()
            for shape in dirty:
                if shape in self._records:
                    self.add(shape, self.remove(shape))

    def query(self, rect, reverse=False):
        self.synchronize()
        cells = self.cells(rect, 4096)
        if cells is None:
            candidates = self._records.keys()
        else:
            candidates = set(self._large)
            for cell in cells:
                candidates.update(self._buckets.get(cell, ()))
        return sorted((shape for shape in candidates if self._records[shape][1].intersects(rect)),
                      key=lambda shape: self._records[shape][0], reverse=reverse)
