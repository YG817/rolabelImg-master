# Copyright (c) 2016 Tzutalin
# Create by TzuTaLin <tzu.ta.lin@gmail.com>

try:
    from PyQt5.QtGui import QImage
except ImportError:
    from PyQt4.QtGui import QImage

from base64 import b64encode, b64decode
from pascal_voc_io import PascalVocWriter
from pascal_voc_io import XML_EXT
import os.path
import sys
import math
from box_geometry import validate_box

class LabelFileError(Exception):
    pass


class LabelFile(object):
    # It might be changed as window creates. By default, using XML ext
    # suffix = '.lif'
    suffix = XML_EXT

    def __init__(self, filename=None):
        self.shapes = ()
        self.imagePath = None
        self.imageData = None
        self.verified = False

    def savePascalVocFormat(self, filename, shapes, imagePath, imageData,
                            lineColor=None, fillColor=None, databaseSrc=None, imageSize=None):
        imgFolderPath = os.path.dirname(imagePath)
        imgFolderName = os.path.split(imgFolderPath)[-1]
        imgFileName = os.path.basename(imagePath)
        imgFileNameWithoutExt = os.path.splitext(imgFileName)[0]
        # Read from file path because self.imageData might be empty if saving to
        # Pascal format
        if imageSize is None:
            from PyQt5.QtGui import QImageReader
            size = QImageReader(imagePath).size()
            if not size.isValid():
                raise LabelFileError('Unable to read image dimensions')
            imageSize = (size.width(), size.height())
        imageShape = [imageSize[1], imageSize[0], 3]
        writer = PascalVocWriter(imgFolderName, imgFileNameWithoutExt,
                                 imageShape, localImgPath=imagePath)
        writer.verified = self.verified

        for shape in shapes:
            points = shape['points']
            validate_box(points)
            label = shape['label']
            # Add Chris
            difficult = int(shape['difficult'])           
            direction = shape['direction']
            isRotated = shape['isRotated']
            # if shape is normal box, save as bounding box 
            # print('direction is %lf' % direction)
            if not isRotated:
                bndbox = LabelFile.convertPoints2BndBox(points)
                if bndbox[2] <= bndbox[0] or bndbox[3] <= bndbox[1]:
                    raise LabelFileError('VOC 整数坐标无法表示这个小框，请调整框或使用 COCO 保存')
                writer.addBndBox(bndbox[0], bndbox[1], bndbox[2], 
                    bndbox[3], label, difficult)
            else: #if shape is rotated box, save as rotated bounding box
                robndbox = LabelFile.convertPoints2RotatedBndBox(shape)
                writer.addRotatedBndBox(robndbox[0],robndbox[1],
                    robndbox[2],robndbox[3],robndbox[4],label,difficult)

        writer.save(targetFile=filename)
        return

    def toggleVerify(self):
        self.verified = not self.verified

    @staticmethod
    def isLabelFile(filename):
        fileSuffix = os.path.splitext(filename)[1].lower()
        return fileSuffix == LabelFile.suffix

    @staticmethod
    def convertPoints2BndBox(points):
        xmin = float('inf')
        ymin = float('inf')
        xmax = float('-inf')
        ymax = float('-inf')
        for p in points:
            x = p[0]
            y = p[1]
            xmin = min(x, xmin)
            ymin = min(y, ymin)
            xmax = max(x, xmax)
            ymax = max(y, ymax)

        # Martin Kersner, 2015/11/12
        # 0-valued coordinates of BB caused an error while
        # training faster-rcnn object detector.
        if xmin < 1:
            xmin = 1

        if ymin < 1:
            ymin = 1

        return (int(xmin), int(ymin), int(xmax), int(ymax))

    # You Hao, 2017/06/121
    @staticmethod
    def convertPoints2RotatedBndBox(shape):
        points = shape['points']
        center = shape['center']
        direction = shape['direction']

        cx = center.x()
        cy = center.y()
        
        w = math.sqrt((points[0][0]-points[1][0]) ** 2 +
            (points[0][1]-points[1][1]) ** 2)

        h = math.sqrt((points[2][0]-points[1][0]) ** 2 +
            (points[2][1]-points[1][1]) ** 2)

        angle = direction % math.pi

        return (round(cx,4),round(cy,4),round(w,4),round(h,4),round(angle,6))
