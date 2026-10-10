#!/usr/bin/env python
# -*- coding: utf8 -*-
import codecs
import os.path
import re
import sys
import hashlib

from functools import partial
from collections import defaultdict

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    # needed for py3+qt4
    # Ref:
    # http://pyqt.sourceforge.net/Docs/PyQt4/incompatible_apis.html
    # http://stackoverflow.com/questions/21217399/pyqt4-qtcore-qvariant-object-instead-of-a-string
    if sys.version_info.major >= 3:
        import sip
        sip.setapi('QVariant', 2)
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import resources
# Add internal libs
dir_name = os.path.abspath(os.path.dirname(__file__))
libs_path = os.path.join(dir_name, 'libs')
sys.path.insert(0, libs_path)
from lib import struct, newAction, newIcon, addActions, fmtShortcut
from shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from canvas import Canvas
from zoomWidget import ZoomWidget
from colorDialog import ColorDialog
from labelFile import LabelFile, LabelFileError
from toolBar import ToolBar
from pascal_voc_io import PascalVocReader
from pascal_voc_io import XML_EXT
from ustr import ustr
from image_loader import ImageLoader, Spinner
from coco_io import save_coco, read_coco
from label_store import LabelStore, canonical_label_name
from ui_theme import apply_theme, style_label_item
from category_delegate import CategoryDelegate, CategoryTable
from browser_launcher import BrowserLauncher
from quick_guide import create_quick_guide
from annotation_paths import annotation_path, annotation_source, identity, safe_to_overwrite
from box_geometry import validate_box
from annotation_delegate import AnnotationDelegate
from inspection import InspectionDialog
from view_layout import ImageScrollArea, ResponsiveRow, PanelScrollArea
from app_version import APP_VERSION
from update_checker import UpdateController

__appname__ = 'roLabelImg'

# Utility functions and classes.


def have_qstring():
    '''p3/qt5 get rid of QString wrapper as py3 has native unicode str type'''
    return not (sys.version_info.major >= 3 or QT_VERSION_STR.startswith('5.'))


def util_qt_strlistclass():
    return QStringList if have_qstring() else list


class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            addActions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


# PyQt5: TypeError: unhashable type: 'QListWidgetItem'
class HashableQListWidgetItem(QListWidgetItem):

    def __init__(self, *args):
        super(HashableQListWidgetItem, self).__init__(*args)

    def __hash__(self):
        return hash(id(self))


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, defaultFilename=None, defaultPrefdefClassFile=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)
        # Save as Pascal voc xml
        self.defaultSaveDir = None
        self.usingPascalVocFormat = False
        LabelFile.suffix = '.json'
        self._generation = 0
        self._workers = set()
        self._tutorialWorker = None
        self._loading = False
        self._detailWorker = None
        self._loadWorker = None
        self._pendingLoad = None
        self._closePending = False
        self._raster = False
        self._stretch = None
        self._detailKey = None
        self._detailTimer = QTimer(self)
        self._detailTimer.setSingleShot(True)
        self._detailTimer.timeout.connect(self.loadVisibleRegion)
        try:
            self.labelStore = LabelStore()
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, 'Label library', 'Cannot read label library: %s' % exc)
            raise
        # For loading all image under a directory
        self.mImgList = []
        self.dirname = None
        self.labelHist = []
        self.lastOpenDir = None

        # Whether we need to save or not.
        self.dirty = False

        self.isEnableCreate = True
        self.isEnableCreateRo = True
        self._activeDraw = None
        self._lastDrawTool = 'rotated'
        self._undoStack = []
        self._redoStack = []
        self._annotationPaths = {}
        self._failedAnnotationPaths = set()
        self._annotationWarnings = []
        self._nextAnnotationId = 1
        self._annotationCounts = {}
        self._syncSelection = False
        self._zoomSerial = 0

        # Enble auto saving if pressing next
        self.autoSaving = True
        self._noSelectionSlot = False
        self._beginner = True
        self.screencast = "https://youtu.be/7D5lvol_QRA"
        # For a demo of original labelImg, please see "https://youtu.be/p0nR2YsCY_U"

        # Main widgets and related state.
        self.itemsToShapes = {}
        self.shapesToItems = {}

        listLayout = QVBoxLayout()
        listLayout.setContentsMargins(12, 12, 12, 12)
        listLayout.setSpacing(10)
        
        listLayout.addWidget(QLabel('标注类别 · 点选连续标注，保留当前工具'))
        self.categoryGrid = CategoryTable(0, 2)
        self.categoryGrid.setObjectName('categoryGrid')
        self.categoryGrid.horizontalHeader().hide()
        self.categoryGrid.verticalHeader().hide()
        self.categoryGrid.setShowGrid(False)
        self.categoryGrid.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.categoryGrid.setSelectionMode(QAbstractItemView.SingleSelection)
        self.categoryGrid.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.categoryGrid.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.categoryGrid.setWordWrap(True)
        self.categoryGrid.setMinimumHeight(260)
        self.categoryGrid.verticalHeader().setDefaultSectionSize(38)
        self.categoryGrid.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.categoryGrid.setItemDelegate(CategoryDelegate(self.categoryGrid))
        self.categoryGrid.itemSelectionChanged.connect(self.categorySelectionChanged)
        self.categoryGrid.columnsChanged.connect(self.refreshCategoryGrid)
        listLayout.addWidget(self.categoryGrid, 3)
        self.formatCombo = QComboBox()
        self.formatCombo.addItems(['COCO (*.json)', 'Pascal VOC (*.xml)'])
        self.formatCombo.currentIndexChanged.connect(self.changeExportFormat)
        manageButton = QPushButton('管理标签与颜色')
        manageButton.setObjectName('labelManager')
        manageButton.clicked.connect(self.manageLabels)
        listLayout.addWidget(ResponsiveRow([QLabel('导出'), self.formatCombo, manageButton]))
        self.centerCoordinates = QLineEdit()
        self.centerCoordinates.setReadOnly(True)
        self.centerCoordinates.setPlaceholderText('打开带地理参考的 TIFF 后显示')
        self.copyCoordinatesButton = QPushButton('复制')
        self.copyCoordinatesButton.setToolTip('复制影像中心经纬度')
        self.copyCoordinatesButton.setEnabled(False)
        self.copyCoordinatesButton.clicked.connect(self.copyCenterCoordinates)
        listLayout.addWidget(ResponsiveRow([QLabel('中心经纬度 WGS84'), self.centerCoordinates,
                                            self.copyCoordinatesButton]))

        # Create and add a widget for showing current label items
        self.labelList = QListWidget()
        self.labelList.setMinimumHeight(110)
        self.labelList.setItemDelegate(AnnotationDelegate(self.labelList))
        self.labelList.itemDoubleClicked.connect(self.focusAnnotation)
        self.labelList.setSelectionMode(QAbstractItemView.ExtendedSelection)
        labelListContainer = QWidget()
        labelListContainer.setLayout(listLayout)
        self.labelList.itemActivated.connect(self.labelSelectionChanged)
        self.labelList.itemSelectionChanged.connect(self.labelSelectionChanged)
        self.deleteSelectedButton = QPushButton('删除所选')
        self.deleteSelectedButton.setEnabled(False)
        self.deleteSelectedButton.clicked.connect(self.deleteSelectedShape)
        focusButton = QPushButton('定位')
        focusButton.setToolTip('定位所选框；也可双击列表条目')
        focusButton.clicked.connect(self.focusAnnotation)
        self.lockButton = QPushButton('锁定/解锁')
        self.lockButton.setToolTip('锁定后可选择和定位，但不能移动、缩放、旋转或删除；切图后清除')
        self.lockButton.clicked.connect(self.toggleSelectedLocks)
        annotationTitle = QLabel('标注框')
        annotationTitle.setToolTip('Ctrl / Shift 多选标注框')
        listLayout.addWidget(ResponsiveRow([annotationTitle, focusButton,
                                            self.lockButton, self.deleteSelectedButton]))
        # Connect to itemChanged to detect checkbox changes.
        self.labelList.itemChanged.connect(self.labelItemChanged)
        listLayout.addWidget(self.labelList, 2)
        self.annotationCountLabel = QLabel('标注框总数：0')
        self.annotationCountLabel.setStyleSheet('color: #245ac2; font-weight: 600; padding: 6px 12px;')
        self.annotationCountLabel.setWordWrap(True)
        self.annotationCountLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        self.dock = QDockWidget(u'Box Labels', self)
        self.dock.setObjectName(u'Label')
        labelListContainer.setMinimumWidth(0)
        labelListContainer.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        listLayout.setSizeConstraint(QLayout.SetNoConstraint)
        for label in labelListContainer.findChildren(QLabel):
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        dockContainer = QWidget()
        dockContainer.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        dockLayout = QVBoxLayout(dockContainer)
        dockLayout.setContentsMargins(0, 0, 0, 0)
        dockLayout.setSpacing(0)
        dockLayout.setSizeConstraint(QLayout.SetNoConstraint)
        dockLayout.addWidget(PanelScrollArea(labelListContainer), 1)
        dockLayout.addWidget(self.annotationCountLabel)
        self.dock.setWidget(dockContainer)

        # Tzutalin 20160906 : Add file list and dock to move faster
        self.fileListWidget = QListWidget()
        self.fileListWidget.setTextElideMode(Qt.ElideMiddle)
        self.fileListWidget.itemDoubleClicked.connect(self.fileitemDoubleClicked)
        filelistLayout = QVBoxLayout()
        filelistLayout.setContentsMargins(12, 12, 12, 12)
        filelistLayout.addWidget(self.fileListWidget)
        fileListContainer = QWidget()
        fileListContainer.setLayout(filelistLayout)
        self.filedock = QDockWidget(u'File List', self)
        self.filedock.setObjectName(u'File')
        fileListContainer.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.filedock.setWidget(PanelScrollArea(fileListContainer))

        self.zoomWidget = ZoomWidget()
        self.colorDialog = ColorDialog(parent=self)

        self.canvas = Canvas()
        self.canvas.zoomRequest.connect(self.zoomRequest)

        scroll = ImageScrollArea()
        scroll.setWidget(self.canvas)
        self.scrollBars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()
        }
        self.canvas.scrollRequest.connect(self.scrollRequest)
        self.canvas.panRequest.connect(self.panImage)
        for bar in self.scrollBars.values():
            bar.valueChanged.connect(self.scheduleDetail)
            bar.valueChanged.connect(self.updateInspectionViewport)

        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.setDirty)
        self.canvas.editStarted.connect(self.pushUndo)
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)
        self.canvas.status.connect(self.status)

        self.canvas.hideNRect.connect(self.enableCreate)
        self.canvas.hideRRect.connect(self.enableCreateRo)

        self.setCentralWidget(scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        # Tzutalin 20160906 : Add file list and dock to move faster
        self.addDockWidget(Qt.RightDockWidgetArea, self.filedock)
        self.dockFeatures = QDockWidget.DockWidgetClosable\
            | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)
        self.filedock.setFeatures(self.filedock.features() ^ self.dockFeatures)

        # Actions
        action = partial(newAction, self)
        quit = action('&Quit', self.close,
                      'Ctrl+Q', 'quit', u'Quit application')

        open = action('&Open', self.openFile,
                      'Ctrl+O', 'open', u'Open image or label file')

        opendir = action('&Open Dir', self.openDir,
                         'Ctrl+u', 'open', u'Open Dir')

        changeSavedir = action('&Change default saved Annotation dir', self.changeSavedir,
                               'Ctrl+r', 'open', u'Change default saved Annotation dir')

        openAnnotation = action('&Open Annotation', self.openAnnotation,
                                'Ctrl+Shift+O', 'openAnnotation', u'Open Annotation')

        openNextImg = action('&Next Image', self.openNextImg,
                             'd', 'next', u'Open Next')

        openPrevImg = action('&Prev Image', self.openPrevImg,
                             'a', 'prev', u'Open Prev')

        verify = action('&Verify Image', self.verifyImg,
                        None, 'verify', u'Verify Image')

        save = action('&Save', self.saveFile,
                      'Ctrl+S', 'save', u'Save labels to file', enabled=False)
        saveAs = action('&Save As', self.saveFileAs,
                        'Ctrl+Shift+S', 'save-as', u'Save labels to a different file',
                        enabled=False)
        close = action('&Close', self.closeFile,
                       'Ctrl+W', 'close', u'Close current file')
        color1 = action('Box &Line Color', self.chooseColor1,
                        'Ctrl+L', 'color_line', u'Choose Box line color')
        color2 = action('Box &Fill Color', self.chooseColor2,
                        'Ctrl+Shift+L', 'color', u'Choose Box fill color')

        createMode = action('Create\nRectBox', self.setCreateMode,
                            'Ctrl+N', 'new', u'Start drawing Boxs', enabled=False)
        editMode = action('&Edit\nRectBox', self.setEditMode,
                          'Ctrl+J', 'edit', u'Move and edit Boxs', enabled=False)

        create = action('Create\nRectBox', self.createShape,
                        'w', 'new', u'Draw boxes continuously; click again to stop',
                        checkable=True, enabled=False)

        createRo = action('Create\nRotatedRBox', self.createRoShape,
                          'e', 'newRo', u'Draw rotated boxes continuously; click again to stop',
                          checkable=True, enabled=False)

        delete = action('Delete\nRectBox', self.deleteSelectedShape,
                        'Delete', 'delete', u'Delete', enabled=False)
        undo = action('撤销', self.undoAnnotation, 'Ctrl+Z', 'undo', '撤销上一次标注操作', enabled=False)
        redo = action('重做', self.redoAnnotation, 'Ctrl+Y', 'undo', '恢复上一次撤销的标注操作', enabled=False)
        cycleOverlap = action('选择下一个重叠框', self.canvas.cycleOverlapping,
                              'Alt+Q', tip='鼠标指向重叠区域，按 Alt+Q 循环选择')
        inspect = action('大图巡检', self.showInspection, 'F2', tip='小地图跳转与手动分区检查进度')
        copy = action('&Duplicate\nRectBox', self.copySelectedShape,
                      'Ctrl+D', 'copy', u'Create a duplicate of the selected Box',
                      enabled=False)

        advancedMode = action('&Advanced Mode', self.toggleAdvancedMode,
                              'Ctrl+Shift+A', 'expert', u'Switch to advanced mode',
                              checkable=True)

        hideAll = action('&Hide\nRectBox', partial(self.togglePolygons, False),
                         'Ctrl+H', 'hide', u'Hide all Boxs',
                         enabled=False)
        showAll = action('&Show\nRectBox', partial(self.togglePolygons, True),
                         'Ctrl+A', 'hide', u'Show all Boxs',
                         enabled=False)

        help = action('&Tutorial', self.tutorial, 'Ctrl+T', 'help',
                      u'Show demos')
        self.tutorialAction = help

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            u"Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." % (fmtShortcut("Ctrl+[-+]"),
                                             fmtShortcut("Ctrl+Wheel")))
        self.zoomWidget.setEnabled(False)

        zoomIn = action('Zoom &In', partial(self.addZoom, 1),
                        'Ctrl++', 'zoom-in', u'Increase zoom level', enabled=False)
        zoomOut = action('&Zoom Out', partial(self.addZoom, -1),
                         'Ctrl+-', 'zoom-out', u'Decrease zoom level', enabled=False)
        zoomOrg = action('&Original size', partial(self.setZoom, 100),
                         'Ctrl+=', 'zoom', u'Zoom to original size', enabled=False)
        fitWindow = action('&Fit Window', self.setFitWindow,
                           'Ctrl+F', 'fit-window', u'Zoom follows window size',
                           checkable=True, enabled=False)
        fitWidth = action('Fit &Width', self.setFitWidth,
                          'Ctrl+Shift+F', 'fit-width', u'Zoom follows window width',
                          checkable=True, enabled=False)
        # Group zoom controls into a list for easier toggling.
        zoomActions = (self.zoomWidget, zoomIn, zoomOut,
                       zoomOrg, fitWindow, fitWidth)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        shapeLineColor = action('Shape &Line Color', self.chshapeLineColor,
                                icon='color_line', tip=u'Change the line color for this specific shape',
                                enabled=False)
        shapeFillColor = action('Shape &Fill Color', self.chshapeFillColor,
                                icon='color', tip=u'Change the fill color for this specific shape',
                                enabled=False)

        labels = self.dock.toggleViewAction()
        labels.setText('Show/Hide Label Panel')
        labels.setShortcut('Ctrl+Shift+P')

        # Lavel list context menu.
        labelMenu = QMenu()
        addActions(labelMenu, (delete,))
        self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labelList.customContextMenuRequested.connect(
            self.popLabelListMenu)

        # Store actions for further handling.
        self.actions = struct(save=save, saveAs=saveAs, open=open, close=close,
                              lineColor=color1, fillColor=color2,
                              create=create, createRo=createRo, delete=delete, copy=copy, undo=undo, redo=redo,
                              createMode=createMode, editMode=editMode, advancedMode=advancedMode,
                              shapeLineColor=shapeLineColor, shapeFillColor=shapeFillColor,
                              zoom=zoom, zoomIn=zoomIn, zoomOut=zoomOut, zoomOrg=zoomOrg,
                              fitWindow=fitWindow, fitWidth=fitWidth,
                              zoomActions=zoomActions,
                              fileMenuActions=(
                                  open, opendir, save, saveAs, close, quit),
                              beginner=(), advanced=(),
                              editMenu=(undo, redo, copy, delete, cycleOverlap,
                                        None, color1, color2),
                              beginnerContext=(create, createRo, copy, delete),
                              advancedContext=(createMode, editMode, copy,
                                               delete, shapeLineColor, shapeFillColor),
                              onLoadActive=(
                                  close, create, createMode, editMode),
                              onShapesPresent=(saveAs, hideAll, showAll))

        self.menus = struct(
            file=self.menu('&File'),
            edit=self.menu('&Edit'),
            view=self.menu('&View'),
            help=self.menu('&Help'),
            recentFiles=QMenu('Open &Recent'),
            labelList=labelMenu)

        addActions(self.menus.file,
                   (open, opendir, changeSavedir, openAnnotation, self.menus.recentFiles, save, saveAs, close, None, quit))
        # QMenuBar displays an action's icon instead of its text on Windows.
        # Keep the question mark in the label so both parts stay visible.
        self.guideAction = action('❔ 操作说明', self.showUserGuide, 'F1')
        self.menuBar().removeAction(self.menus.help.menuAction())
        self.menuBar().addAction(self.guideAction)
        self.updater = UpdateController(self)
        self.updateAction = action('版本与更新', self.updater.show_settings)
        self.menuBar().addAction(self.updateAction)
        if getattr(sys, 'frozen', False):
            self.updater.schedule()
        self.addAction(help)
        addActions(self.menus.view, (
            labels, advancedMode, inspect, None,
            hideAll, showAll, None,
            zoomIn, zoomOut, zoomOrg, None,
            fitWindow, fitWidth))

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        addActions(self.canvas.menus[0], self.actions.beginnerContext)
        addActions(self.canvas.menus[1], (
            action('&Copy here', self.copyShape),
            action('&Move here', self.moveShape)))

        self.tools = self.toolbar('Tools')
        self.actions.beginner = (
            open, opendir, openNextImg, openPrevImg, verify, save, None, create, createRo, copy, delete, None,
            zoomIn, zoom, zoomOut, fitWindow, fitWidth)

        self.actions.advanced = (
            open, save, None,
            createMode, editMode, None,
            hideAll, showAll)

        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()
        self.spinner = Spinner(self)
        self.saveStatus = QLabel('未打开影像')
        self.saveStatus.setObjectName('saveStatus')
        self.statusBar().addPermanentWidget(self.saveStatus)
        self.statusBar().addPermanentWidget(self.spinner)

        # Application state.
        self.image = QImage()
        self.filePath = ustr(defaultFilename)
        self.recentFiles = []
        self.maxRecent = 7
        self.lineColor = None
        self.fillColor = None
        self.zoom_level = 100
        self.fit_window = False
        # Add Chris
        self.difficult = False

        # Load predefined classes to the list
        self.loadPredefinedClasses(defaultPrefdefClassFile)
        self.seedReferenceClasses(defaultPrefdefClassFile)
        self.refreshLabelLibrary()
        # XXX: Could be completely declarative.
        # Restore application settings.
        if have_qstring():
            types = {
                'filename': QString,
                'recentFiles': QStringList,
                'window/size': QSize,
                'window/position': QPoint,
                'window/geometry': QByteArray,
                'line/color': QColor,
                'fill/color': QColor,
                'advanced': bool,
                # Docks and toolbars:
                'window/state': QByteArray,
                'savedir': QString,
                'lastOpenDir': QString,
            }
        else:
            types = {
                'filename': str,
                'recentFiles': list,
                'window/size': QSize,
                'window/position': QPoint,
                'window/geometry': QByteArray,
                'line/color': QColor,
                'fill/color': QColor,
                'advanced': bool,
                # Docks and toolbars:
                'window/state': QByteArray,
                'savedir': str,
                'lastOpenDir': str,
            }

        self.settings = settings = Settings(types)
        self.settings.types['exportFormat'] = int
        self.formatCombo.setCurrentIndex(1 if settings.get('exportFormat', 0) == 1 else 0)
        self.recentFiles = list(settings.get('recentFiles', []))
        size = settings.get('window/size', QSize(1280, 850))
        position = settings.get('window/position', QPoint(0, 0))
        self.resize(size)
        self.move(position)
        saveDir = ustr(settings.get('savedir', None))
        self.lastOpenDir = ustr(settings.get('lastOpenDir', None))
        if saveDir is not None and os.path.exists(saveDir):
            self.defaultSaveDir = saveDir
            self.statusBar().showMessage('%s started. Annotation will be saved to %s' %
                                         (__appname__, self.defaultSaveDir))
            self.statusBar().show()

        # or simply:
        # self.restoreGeometry(settings['window/geometry']
        self.restoreState(settings.get('window/state', QByteArray()))
        self.lineColor = QColor(settings.get('line/color', Shape.line_color))
        self.fillColor = QColor(settings.get('fill/color', Shape.fill_color))
        Shape.line_color = self.lineColor
        Shape.fill_color = self.fillColor
        # Add chris
        Shape.difficult = self.difficult

        def xbool(x):
            if isinstance(x, QVariant):
                return x.toBool()
            return bool(x)

        if xbool(settings.get('advanced', False)):
            self.actions.advancedMode.setChecked(True)
            self.toggleAdvancedMode()

        # Populate the File menu dynamically.
        self.updateFileMenu()
        # Since loading the file may take some time, make sure it runs in the
        # background.
        self.queueEvent(partial(self.loadFile, self.filePath or ""))

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)
        scroll.viewportResized.connect(self.workspaceResized)
        QApplication.instance().installEventFilter(self)

        self.populateModeActions()
        apply_theme(self)
        self.status('就绪  ·  W 普通框  /  E 旋转框  /  Ctrl + 滚轮缩放  /  F1 使用说明', 0)

    ## Support Functions ##

    def eventFilter(self, watched, event):
        if event.type() not in (QEvent.KeyPress, QEvent.KeyRelease, QEvent.ShortcutOverride, QEvent.WindowDeactivate):
            return False
        if isinstance(watched, QWidget) and watched.window() is self:
            if event.type() == QEvent.WindowDeactivate:
                self.canvas.setSpacePan(False)
            if event.type() in (QEvent.KeyPress, QEvent.KeyRelease, QEvent.ShortcutOverride) and event.key() == Qt.Key_Space:
                if event.type() == QEvent.KeyRelease and self.canvas._spacePanHeld:
                    if not event.isAutoRepeat():
                        self.canvas.setSpacePan(False)
                    event.accept()
                    return True
                # Space remains normal text input in labels and zoom fields.
                typing = isinstance(watched, (QLineEdit, QTextEdit, QPlainTextEdit)) and not watched.isReadOnly()
                typing = typing or isinstance(watched, QAbstractSpinBox)
                typing = typing or (isinstance(watched, QComboBox) and watched.isEditable())
                if not typing and not self.image.isNull() and not self._loading:
                    if event.type() == QEvent.KeyPress and not event.isAutoRepeat():
                        self.canvas.setFocus(Qt.ShortcutFocusReason)
                        self.canvas.setSpacePan(True)
                    event.accept()
                    return True
        return super(MainWindow, self).eventFilter(watched, event)

    def copyCenterCoordinates(self):
        text = self.centerCoordinates.text()
        if text:
            QApplication.clipboard().setText(text)
            self.status('已复制中心经纬度：' + text)

    def showUserGuide(self):
        if not hasattr(self, '_guideDialog'):
            self._guideDialog = create_quick_guide(self)
        self._guideDialog.show()
        self._guideDialog.raise_()
        self._guideDialog.activateWindow()

    def changeExportFormat(self, index):
        self.usingPascalVocFormat = index == 1
        LabelFile.suffix = '.xml' if self.usingPascalVocFormat else '.json'
        if hasattr(self, 'settings'):
            self.settings['exportFormat'] = index
        if self.filePath and not self._loading:
            self.setDirty()

    def refreshLabelLibrary(self):
        names = [entry['name'] for entry in self.labelStore.entries]
        if self.labelHist == names and hasattr(self, '_libraryReady'):
            return
        self._libraryReady = True
        self.labelHist = names
        self.refreshCategoryGrid()

    def selectedCategory(self):
        selected = self.categoryGrid.selectedItems()
        if selected:
            category_id = selected[0].data(Qt.UserRole)
            for entry in self.labelStore.entries:
                if entry['id'] == category_id:
                    return entry
        return None

    def refreshCategoryGrid(self):
        grid = self.categoryGrid
        previous = grid.selectedItems()
        selected_id = previous[0].data(Qt.UserRole) if previous else None
        grid.blockSignals(True)
        try:
            columns = 2 if grid.viewport().width() >= 360 else 1
            grid.clearContents()
            grid.setColumnCount(columns)
            grid.setRowCount((len(self.labelStore.entries) + columns - 1) // columns)
            for index, entry in enumerate(self.labelStore.entries):
                row, column = divmod(index, columns)
                item = QTableWidgetItem(entry['name'])
                item.setData(Qt.UserRole, entry['id'])
                item.setData(Qt.UserRole + 1, entry['name'])
                item.setData(Qt.UserRole + 2, entry['color'])
                item.setToolTip('%s · 类别颜色 %s' % (entry['name'], entry['color']))
                grid.setItem(row, column, item)
                if entry['id'] == selected_id:
                    grid.setCurrentCell(row, column)
        finally:
            grid.blockSignals(False)
        if selected_id is not None and self.selectedCategory() is None:
            self.stopDrawing()

    def categorySelectionChanged(self):
        entry = self.selectedCategory()
        if entry:
            if not self.image.isNull():
                self.selectDrawTool(self._activeDraw or self._lastDrawTool)
            else:
                self.status('当前类别：%s · 打开影像后可绘制' % entry['name'])
        elif hasattr(self, 'actions'):
            self.stopDrawing()
            self.status('已取消预选类别 · 按 W 或 E 画框后再选择标签')

    def applyLabelColor(self, shape):
        entry = self.labelStore.ensure(canonical_label_name(shape.label))
        shape.label = entry['name']
        shape.line_color = QColor(entry['color'])
        shape.fill_color = QColor(entry['color'])
        shape.fill_color.setAlpha(65)
        shape.select_line_color = shape.line_color.lighter(140)
        self.refreshLabelLibrary()

    def manageLabels(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Manage labels / 管理标签')
        dialog.resize(440, 420)
        layout = QVBoxLayout(dialog)
        explanation = QLabel('标签和颜色自动保存到本地。\n重命名同步修改当前影像；删除正在使用的类别前需先修改对应标注。\n其他影像已保存的标注文件不会被批量修改。')
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        labels = QListWidget()
        labels.setIconSize(QSize(20, 20))
        layout.addWidget(labels)

        def refresh(selected_name=None):
            labels.clear()
            for entry in self.labelStore.entries:
                item = QListWidgetItem(entry['name'])
                style_label_item(item, entry['color'])
                labels.addItem(item)
                if entry['name'] == selected_name:
                    labels.setCurrentItem(item)
            self.refreshLabelLibrary()

        def mutate(operation):
            selected = labels.currentItem()
            if operation != 'add' and selected is None:
                return
            old = selected.text() if selected else ''
            selection = None
            try:
                if operation in ('add', 'rename'):
                    name, ok = QInputDialog.getText(dialog, 'Label name / 标签名', '名称',
                                                  QLineEdit.Normal, old if operation == 'rename' else '')
                    if not ok or not name.strip():
                        return
                    name = name.strip()
                    if operation == 'add':
                        self.labelStore.ensure(name)
                        selection = name
                    else:
                        self.labelStore.rename(old, name)
                        selection = name
                        for shape, item in list(self.shapesToItems.items()):
                            if shape.label == old:
                                item.setText(name)
                elif operation == 'delete':
                    if any(shape.label == old for shape in self.canvas.shapes):
                        QMessageBox.information(dialog, 'Label in use', '该类别用于当前影像，请先修改或删除对应标注。')
                        return
                    self.labelStore.delete(old)
                else:
                    entry = next(e for e in self.labelStore.entries if e['name'] == old)
                    color = QColorDialog.getColor(QColor(entry['color']), dialog)
                    if not color.isValid():
                        return
                    entry['color'] = color.name()
                    selection = old
                    self.labelStore.save()
                    self.labelList.blockSignals(True)
                    try:
                        for shape, item in self.shapesToItems.items():
                            if shape.label == old:
                                self.applyLabelColor(shape)
                                style_label_item(item, shape.line_color)
                    finally:
                        self.labelList.blockSignals(False)
                    self.canvas.update()
                refresh(selection)
                self.refreshCategoryGrid()
            except (OSError, ValueError) as exc:
                QMessageBox.warning(dialog, 'Label library', str(exc))

        buttons = QHBoxLayout()
        for caption, operation in [('新增', 'add'), ('重命名', 'rename'), ('删除', 'delete'), ('颜色', 'color')]:
            button = QPushButton(caption)
            button.clicked.connect(partial(mutate, operation))
            buttons.addWidget(button)
        layout.addLayout(buttons)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        refresh()
        dialog.exec_()

    def noShapes(self):
        return not self.itemsToShapes

    def toggleAdvancedMode(self, value=True):
        self.stopDrawing()
        self._beginner = not value
        self.canvas.setEditing(True)
        self.populateModeActions()
        if value:
            self.actions.createMode.setEnabled(True)
            self.actions.editMode.setEnabled(False)
            # self.dock.setFeatures(self.dock.features() | self.dockFeatures)
        else:
            pass
            # self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

    def populateModeActions(self):
        if self.beginner():
            tool, menu = self.actions.beginner, self.actions.beginnerContext
        else:
            tool, menu = self.actions.advanced, self.actions.advancedContext
        self.tools.clear()
        addActions(self.tools, tool)
        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (self.actions.create,) if self.beginner()\
            else (self.actions.createMode, self.actions.editMode)
        addActions(self.menus.edit, actions + self.actions.editMenu)

    def setBeginner(self):
        self.tools.clear()
        addActions(self.tools, self.actions.beginner)

    def setAdvanced(self):
        self.tools.clear()
        addActions(self.tools, self.actions.advanced)

    def setDirty(self):
        self.dirty = True
        self.updateAnnotationStats()
        self.canvas.verified = False
        self.actions.save.setEnabled(True)
        self.updateSaveStatus()
        shape = self.canvas.selectedShape or (self.canvas.shapes[-1] if self.canvas.shapes else None)
        if shape:
            self.invalidateInspection([shape.boundingRect()])

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.create.setEnabled(True)
        self.actions.createRo.setEnabled(True)
        self.updateSaveStatus()

    def updateSaveStatus(self):
        self.setWindowTitle(__appname__ + (' *' if self.dirty else ''))
        if not self.filePath:
            text, color = '未打开影像', '#65758b'
        elif self.dirty:
            text, color = '● 有未保存修改', '#b65b00'
        elif self._annotationPaths.get(LabelFile.suffix):
            text, color = '✓ 已保存', '#267548'
        else:
            text, color = '尚未保存标注', '#65758b'
        self.saveStatus.setText(text)
        self.saveStatus.setStyleSheet('color: %s; padding: 0 8px;' % color)
        self.saveStatus.setToolTip(self._annotationPaths.get(LabelFile.suffix, self.filePath or ''))

    def enableCreate(self,b):
        self.isEnableCreate = not b
        self.actions.create.setEnabled(self.isEnableCreate or self._activeDraw == 'normal')

    def enableCreateRo(self,b):
        self.isEnableCreateRo = not b
        self.actions.createRo.setEnabled(self.isEnableCreateRo or self._activeDraw == 'rotated')

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)
        self.actions.createRo.setEnabled(value)
        if not value:
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)
            self.actions.save.setEnabled(False)
            self.shapeSelectionChanged(False)

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        # print(message)
        self.statusBar().showMessage(message, delay)
        self.statusBar().show()

    def resetState(self):
        self._annotationPaths.clear()
        self._failedAnnotationPaths.clear()
        self._nextAnnotationId = 1
        self.stopDrawing()
        self._zoomSerial += 1
        self._undoStack.clear()
        self._redoStack.clear()
        self.actions.undo.setEnabled(False)
        self.actions.redo.setEnabled(False)
        self.centerCoordinates.clear()
        self.centerCoordinates.setPlaceholderText('等待影像地理参考信息')
        self.centerCoordinates.setToolTip('')
        self.copyCoordinatesButton.setEnabled(False)
        self._generation += 1
        self._pendingLoad = None
        self._loading = False
        self._raster = False
        self._detailKey = None
        self._detailTimer.stop()
        for worker in self._workers:
            worker.requestInterruption()
        self.spinner.setRunning(False)
        self.image = QImage()
        self.dirty = False
        self.toggleActions(False)
        self.itemsToShapes.clear()
        self.shapesToItems.clear()
        self.labelList.clear()
        self.updateAnnotationStats()
        self.filePath = None
        self.imageData = None
        self.labelFile = None
        self.canvas.resetState()
        self.updateSaveStatus()
        if hasattr(self, '_inspectionDialog'):
            self._inspectionDialog.clearImage()

    def currentItem(self):
        items = self.labelList.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filePath):
        if filePath in self.recentFiles:
            self.recentFiles.remove(filePath)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filePath)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    ## Callbacks ##
    def tutorial(self):
        if self._tutorialWorker is not None or self._closePending:
            return
        worker = BrowserLauncher(self.screencast, self)
        self._tutorialWorker = worker
        self._workers.add(worker)
        self.tutorialAction.setEnabled(False)
        worker.failed.connect(self.tutorialFailed)
        worker.finished.connect(self.workerFinished)
        self.status('正在打开系统默认浏览器。视频需要网络；F1 可查看离线使用说明。', 10000)
        worker.start()

    def tutorialFailed(self, message):
        if self._closePending:
            return
        # Nonmodal: a failed browser must not lock the annotation window.
        notice = QDialog(self)
        notice.setObjectName('tutorialError')
        notice.setWindowTitle('无法打开视频教程')
        layout = QVBoxLayout(notice)
        layout.addWidget(QLabel(message + '\n可复制下面的地址到浏览器，或按 F1 查看离线说明。'))
        link = QLineEdit(self.screencast, notice)
        link.setReadOnly(True)
        layout.addWidget(link)
        close = QDialogButtonBox(QDialogButtonBox.Close, notice)
        close.rejected.connect(notice.close)
        layout.addWidget(close)
        notice.resize(520, 150)
        notice.setAttribute(Qt.WA_DeleteOnClose)
        notice.setWindowModality(Qt.NonModal)
        notice.show()

    # create Normal Rect
    def createShape(self, checked=False):
        self.selectDrawTool('normal' if checked else None)

    # create Rotated Rect
    def createRoShape(self, checked=False):
        self.selectDrawTool('rotated' if checked else None)

    def stopDrawing(self):
        self._activeDraw = None
        if hasattr(self, 'actions'):
            self.actions.create.setChecked(False)
            self.actions.createRo.setChecked(False)
        if hasattr(self, 'canvas'):
            self.canvas._editingGesture = self.canvas._rotatingGesture = False
            self.canvas.current = None
            self.canvas.line.points = []
            self.canvas.setEditing(True)
            self.canvas.update()

    def selectDrawTool(self, kind):
        if kind:
            self._lastDrawTool = kind
        if kind is None:
            self.stopDrawing()
            self.status('已退出连续标注模式')
            return
        entry = self.selectedCategory()
        self.canvas.current = None
        self.canvas.line.points = []
        self.canvas._editingGesture = self.canvas._rotatingGesture = False
        self.canvas.setEditing(False)
        self.canvas.canDrawRotatedRect = kind == 'rotated'
        self._activeDraw = kind
        self.actions.create.setChecked(kind == 'normal')
        self.actions.createRo.setChecked(kind == 'rotated')
        self.status('连续标注：%s · %s · 再次点击当前工具退出' %
                    (entry['name'] if entry else '画框后选择标签', '普通框' if kind == 'normal' else '旋转框'), 0)

    def toggleDrawingSensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.actions.editMode.setEnabled(not drawing)
            

    def toggleDrawMode(self, edit=True):
        self.canvas.setEditing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def setCreateMode(self):
        print('setCreateMode')
        assert self.advanced()
        self.toggleDrawMode(False)

    def setEditMode(self):
        assert self.advanced()
        self.stopDrawing()
        self.toggleDrawMode(True)

    def updateFileMenu(self):
        currFilePath = self.filePath

        def exists(filename):
            return os.path.exists(filename)
        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f !=
                 currFilePath and exists(f)]
        for i, f in enumerate(files):
            icon = newIcon('labels')
            action = QAction(
                icon, '&%d %s' % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.loadRecent, f))
            menu.addAction(action)

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    # Tzutalin 20160906 : Add file list and dock to move faster
    def fileitemDoubleClicked(self, item=None):
        if item is None:
            return
        if not self.mayContinue():
            return
        filename = item.data(Qt.UserRole)
        if filename:
            self.loadFile(filename)

    def refreshImageList(self):
        self.fileListWidget.clear()
        for path in self.mImgList:
            name = os.path.relpath(path, self.dirname) if self.dirname else os.path.basename(path)
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            self.fileListWidget.addItem(item)
            if path == self.filePath:
                self.fileListWidget.setCurrentItem(item)
                self.fileListWidget.scrollToItem(item)
        self.filedock.setWindowTitle('影像列表 · %d 张' % len(self.mImgList))

    # React to canvas signals.
    def shapeSelectionChanged(self, selected=False):
        if self._syncSelection:
            return
        if self._noSelectionSlot:
            self._noSelectionSlot = False
        else:
            shape = self.canvas.selectedShape
            if shape:
                self.labelList.blockSignals(True)
                self.labelList.clearSelection()
                if shape in self.shapesToItems:
                    self.shapesToItems[shape].setSelected(True)
                self.labelList.blockSignals(False)
            else:
                self.labelList.blockSignals(True)
                self.labelList.clearSelection()
                self.labelList.blockSignals(False)
        self.actions.delete.setEnabled(selected)
        self.deleteSelectedButton.setEnabled(selected)
        self.actions.copy.setEnabled(selected)
        self.actions.shapeLineColor.setEnabled(selected)
        self.actions.shapeFillColor.setEnabled(selected)

    def addLabel(self, shape):
        self.applyLabelColor(shape)
        if shape.identifier is None:
            shape.identifier = self._nextAnnotationId
        self._nextAnnotationId = max(self._nextAnnotationId, shape.identifier + 1)
        item = HashableQListWidgetItem(shape.label)
        item.setData(Qt.UserRole + 9, shape.locked)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        style_label_item(item, shape.line_color)
        self.itemsToShapes[item] = shape
        self.shapesToItems[shape] = item
        self.labelList.addItem(item)
        self.updateAnnotationStats()
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)

    def remLabel(self, shape):
        if shape is None:
            # print('rm empty label')
            return
        item = self.shapesToItems[shape]
        self.labelList.takeItem(self.labelList.row(item))
        del self.shapesToItems[shape]
        del self.itemsToShapes[item]
        self.updateAnnotationStats()

    def updateAnnotationStats(self, force=False):
        if self.labelList.signalsBlocked() and not force:
            return
        items = [(self.labelList.item(row), self.itemsToShapes.get(self.labelList.item(row)))
                 for row in range(self.labelList.count())]
        counts = defaultdict(int)
        for item, shape in items:
            if shape is not None:
                counts[shape.label] += 1
        self._annotationCounts = dict(counts)
        ordinals = defaultdict(int)
        blocked = self.labelList.blockSignals(True)
        try:
            for item, shape in items:
                if shape is None:
                    continue
                ordinals[shape.label] += 1
                item.setData(Qt.UserRole + 8, ordinals[shape.label])
                item.setToolTip('%s · 第 %d / %d 个\n双击定位；可临时锁定以防误改' %
                                (shape.label, ordinals[shape.label], counts[shape.label]))
        finally:
            self.labelList.blockSignals(blocked)
        self.annotationCountLabel.setText('标注框总数：%d' % sum(counts.values()))
        self.annotationCountLabel.setToolTip('\n'.join('%s：%d 个' % pair for pair in counts.items()) or '当前影像尚无标注框')

    def loadLabels(self, shapes):
        for shape in shapes:
            validate_box(shape[1])
        self.canvas.deSelectShape()
        self.labelList.clear()
        self.itemsToShapes.clear()
        self.shapesToItems.clear()
        s = []
        blocked = self.labelList.blockSignals(True)
        try:
            for label, points, direction, isRotated, line_color, fill_color, difficult in shapes:
                shape = Shape(label=label)
                for x, y in points:
                    shape.addPoint(QPointF(x, y))
                shape.difficult = difficult
                shape.direction = direction
                shape.isRotated = isRotated
                shape.close()
                s.append(shape)
                self.addLabel(shape)
        finally:
            self.labelList.blockSignals(blocked)
            self.updateAnnotationStats(force=True)

        self.canvas.loadShapes(s)
        self.invalidateInspection([shape.boundingRect() for shape in s])

    def saveLabels(self, annotationFilePath):
        annotationFilePath = ustr(annotationFilePath)
        if self.labelFile is None:
            self.labelFile = LabelFile()
            self.labelFile.verified = self.canvas.verified

        def format_shape(s):
            return dict(label=s.label,
                        line_color=s.line_color.getRgb()
                        if s.line_color != self.lineColor else None,
                        fill_color=s.fill_color.getRgb()
                        if s.fill_color != self.fillColor else None,
                        points=[(p.x(), p.y()) for p in s.points],
                       # add chris
                        difficult = s.difficult,
                        # You Hao 2017/06/21
                        # add for rotated bounding box
                        direction = s.direction,
                        center = s.center,
                        isRotated = s.isRotated)

        shapes = [format_shape(shape) for shape in self.canvas.shapes]
        self.labelFile.verified = self.canvas.verified
        # Can add differrent annotation formats here
        try:
            if self.usingPascalVocFormat is True:
                print ('Img: ' + self.filePath + ' -> Its xml: ' + annotationFilePath)
                self.labelFile.savePascalVocFormat(annotationFilePath, shapes, self.filePath, self.imageData,
                                                   self.lineColor.getRgb(), self.fillColor.getRgb(),
                                                   imageSize=(self.canvas.imageSize.width(), self.canvas.imageSize.height()))
            else:
                for shape in shapes:
                    self.labelStore.ensure(shape['label'])
                save_coco(annotationFilePath, shapes, self.filePath,
                          (self.canvas.imageSize.width(), self.canvas.imageSize.height()),
                          self.labelStore.categories(), self.canvas.verified)
            return True
        except (LabelFileError, OSError, ValueError, KeyError) as e:
            self.errorMessage(u'Error saving label data',
                              u'<b>%s</b>' % e)
            return False

    def copySelectedShape(self):
        if not self.canvas.selectedShape:
            return
        self.pushUndo()
        self.addLabel(self.canvas.copySelectedShape())
        self.setDirty()
        # fix copy and delete
        self.shapeSelectionChanged(True)

    def labelSelectionChanged(self):
        if self._syncSelection:
            return
        items = self.labelList.selectedItems()
        self._syncSelection = True
        try:
            self.canvas.deSelectShape()
            self.canvas.unHighlight()
            for shape in self.canvas.shapes:
                shape.selected = False
            for item in items:
                self.itemsToShapes[item].selected = True
            if items:
                self.canvas.selectedShape = self.itemsToShapes[items[-1]]
            self.canvas.update()
        finally:
            self._syncSelection = False
        self.actions.delete.setEnabled(bool(items))
        self.deleteSelectedButton.setEnabled(bool(items))
        for action in (self.actions.copy, self.actions.shapeLineColor, self.actions.shapeFillColor):
            action.setEnabled(len(items) == 1)

    def centerOnImagePoint(self, point):
        generation = self._generation
        def center():
            if generation != self._generation or self._closePending:
                return
            viewport = self.centralWidget().viewport()
            local = (point + self.canvas.offsetToCenter()) * self.canvas.scale
            self.scrollBars[Qt.Horizontal].setValue(round(local.x() - viewport.width() / 2))
            self.scrollBars[Qt.Vertical].setValue(round(local.y() - viewport.height() / 2))
        QTimer.singleShot(0, center)

    def focusAnnotation(self, item=None):
        if item not in self.itemsToShapes:
            item = self.currentItem()
        shape = self.itemsToShapes.get(item)
        if shape is None:
            return
        bounds = shape.boundingRect()
        viewport = self.centralWidget().viewport()
        margin = max(bounds.width(), bounds.height()) * 0.35 + 20
        zoom = min(viewport.width() / (bounds.width() + 2 * margin),
                   viewport.height() / (bounds.height() + 2 * margin)) * 100
        self.setZoom(min(500, zoom))
        self.centerOnImagePoint(bounds.center())
        self.canvas.setFocus()
        self.status('定位 %s · 第 %d / %d 个' % (shape.label, self.shapesToItems[shape].data(Qt.UserRole + 8),
                                              self._annotationCounts[shape.label]))

    def toggleSelectedLocks(self):
        shapes = [self.itemsToShapes[item] for item in self.labelList.selectedItems()]
        if not shapes:
            return
        locked = any(not shape.locked for shape in shapes)
        self.labelList.blockSignals(True)
        try:
            for shape in shapes:
                shape.locked = locked
                self.shapesToItems[shape].setData(Qt.UserRole + 9, locked)
        finally:
            self.labelList.blockSignals(False)
        self.canvas._editingGesture = self.canvas._rotatingGesture = False
        self.canvas.unHighlight()
        self.canvas.update()
        self.status('已%s %d 个标注框（当前影像内有效）' % ('临时锁定' if locked else '解锁', len(shapes)))

    def showInspection(self):
        if not self.filePath or self.image.isNull() or self._loading:
            self.status('请先打开影像，再使用大图巡检')
            return
        if not hasattr(self, '_inspectionDialog'):
            self._inspectionDialog = InspectionDialog(self.settings.data, self)
            self._inspectionDialog.regionRequested.connect(self.focusInspectionRegion)
            self._inspectionDialog.markRequested.connect(self.markInspectionRegion)
            self._inspectionDialog.originalSizeRequested.connect(self.restoreOriginalImageSize)
            self._inspectionDialog.fitRequested.connect(self.setFitWindow)
        if self._inspectionDialog.path != self.filePath:
            self._inspectionDialog.setImage(self.filePath, self.image, self.canvas.imageSize)
        self.updateInspectionViewport()
        self._inspectionDialog.show()
        self._inspectionDialog.raise_()

    def focusInspectionRegion(self, region):
        viewport = self.centralWidget().viewport()
        zoom = min(viewport.width() / region.width(), viewport.height() / region.height()) * 95
        self.canvas.zoomAnchor = None
        self.setZoom(min(500, zoom))
        self.centerOnImagePoint(region.center())

    def restoreOriginalImageSize(self):
        if self.image.isNull():
            return
        self.canvas.zoomAnchor = None
        self.setZoom(100)
        self.centerOnImagePoint(QPointF(self.canvas.imageSize.width() / 2,
                                       self.canvas.imageSize.height() / 2))

    def markInspectionRegion(self):
        if self.dirty and not self.saveFile():
            return
        self._inspectionDialog.markComplete()
        self.status('已记录本分区的人工检查进度')

    def invalidateInspection(self, rectangles):
        if hasattr(self, '_inspectionDialog') and self._inspectionDialog.path == self.filePath:
            self._inspectionDialog.invalidateRects(rectangles)

    def updateInspectionViewport(self, *args):
        if not hasattr(self, '_inspectionDialog') or self.image.isNull():
            return
        if self._inspectionDialog.path != self.filePath or self.canvas.scale <= 0:
            return
        viewport = self.centralWidget().viewport()
        origin = self.canvas.transformPos(QPointF(self.canvas.mapFrom(viewport, QPoint(0, 0))))
        self._inspectionDialog.overview.viewport = QRectF(origin.x(), origin.y(),
                                                         viewport.width() / self.canvas.scale,
                                                         viewport.height() / self.canvas.scale)
        self._inspectionDialog.overview.update()

    def labelItemChanged(self, item):
        shape = self.itemsToShapes[item]
        label = item.text()
        if label != shape.label:
            shape.label = item.text()
            self.applyLabelColor(shape)
            self.labelList.blockSignals(True)
            style_label_item(item, shape.line_color)
            self.labelList.blockSignals(False)
            self.canvas.update()
            self.setDirty()
        else:  # User probably changed item visibility
            self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)

    # Callback functions:
    def newShape(self):
        """Finalize a box using the category chosen before drawing."""
        entry = self.selectedCategory()
        if entry is None:
            name = self.chooseShapeLabel(self.canvas.shapes[-1])
            if not name:
                self.canvas.shapes.pop()
                self.canvas.update()
                return
            entry = self.labelStore.ensure(name)
        self.pushUndo(self.canvas.shapes[:-1])
        self.addLabel(self.canvas.setLastLabel(entry['name']))
        self.setDirty()
        self.status('已标注 %s · 可继续绘制，点击当前工具退出' % entry['name'])

    def chooseShapeLabel(self, shape):
        dialog = QDialog(self, Qt.Popup)
        dialog.setWindowTitle('选择或新增标签')
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('选择标签，或输入新标签名称'))
        combo = QComboBox(dialog)
        combo.setEditable(True)
        combo.addItems([entry['name'] for entry in self.labelStore.entries])
        combo.setCurrentIndex(-1)
        combo.setMinimumWidth(260)
        layout.addWidget(combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
        buttons.accepted.connect(lambda: dialog.accept() if combo.currentText().strip() else None)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.adjustSize()
        point = shape.boundingRect().bottomLeft()
        local = (point + self.canvas.offsetToCenter()) * self.canvas.scale
        position = self.canvas.mapToGlobal(local.toPoint()) + QPoint(0, 12)
        available = self.screen().availableGeometry()
        position.setX(max(available.left(), min(position.x(), available.right() - dialog.width())))
        position.setY(max(available.top(), min(position.y(), available.bottom() - dialog.height())))
        dialog.move(position)
        combo.setFocus()
        return combo.currentText().strip() if dialog.exec_() == QDialog.Accepted else None

    def pushUndo(self, shapes=None):
        if self.canvas.selectedShape:
            self.invalidateInspection([self.canvas.selectedShape.boundingRect()])
        self._undoStack.append(self.annotationSnapshot(shapes))
        self._undoStack = self._undoStack[-100:]
        self._redoStack.clear()
        self.actions.redo.setEnabled(False)
        self.actions.undo.setEnabled(True)

    def annotationSnapshot(self, shapes=None):
        if shapes is None:
            shapes = self.canvas.shapes
        return ([s.copy() for s in shapes], [self.canvas.isVisible(s) for s in shapes],
                self.canvas.verified)

    def annotationSignature(self, snapshot):
        shapes, visibility, verified = snapshot
        return ([(s.label, s.isRotated, s.direction, s.difficult,
                  s.line_color.getRgb(), s.fill_color.getRgb(),
                  [(p.x(), p.y()) for p in s.points]) for s in shapes], visibility, verified)

    def undoAnnotation(self):
        if self.canvas.current is not None:
            self.canvas.current = None
            self.canvas.line.points = []
            self.canvas.drawingPolygon.emit(False)
            self.canvas.update()
            return
        if not self._undoStack:
            return
        current = self.annotationSnapshot()
        while self._undoStack:
            previous = self._undoStack.pop()
            if self.annotationSignature(previous) != self.annotationSignature(current):
                self._redoStack.append(current)
                self.restoreAnnotationSnapshot(previous)
                self.status('已撤销 · Ctrl+Y 可重做')
                return
        self.actions.undo.setEnabled(False)

    def redoAnnotation(self):
        if self.canvas.current is not None or not self._redoStack:
            return
        self._undoStack.append(self.annotationSnapshot())
        self.restoreAnnotationSnapshot(self._redoStack.pop())
        self.status('已重做上一次标注操作')

    def restoreAnnotationSnapshot(self, snapshot):
        shapes, visibility, verified = snapshot
        self.invalidateInspection([s.boundingRect() for s in self.canvas.shapes + shapes])
        locks = {s.identifier: s.locked for s in self.canvas.shapes if s.identifier is not None}
        for shape in shapes:
            shape.locked = locks.get(shape.identifier, shape.locked)
        self._syncSelection = True
        self.labelList.blockSignals(True)
        try:
            self.canvas.unHighlight()
            self.canvas.selectedShape = None
            self.canvas._editingGesture = self.canvas._rotatingGesture = False
            self.canvas.visible.clear()
            self.itemsToShapes.clear()
            self.shapesToItems.clear()
            self.labelList.clear()
            self.canvas.loadShapes(shapes)
            for shape, visible in zip(shapes, visibility):
                shape.selected = False
                line_color, fill_color = QColor(shape.line_color), QColor(shape.fill_color)
                self.addLabel(shape)
                shape.line_color, shape.fill_color = line_color, fill_color
                style_label_item(self.shapesToItems[shape], shape.line_color)
                self.canvas.visible[shape] = visible
                self.shapesToItems[shape].setCheckState(Qt.Checked if visible else Qt.Unchecked)
        finally:
            self.labelList.blockSignals(False)
            self._syncSelection = False
        self.shapeSelectionChanged(False)
        self.setDirty()
        self.canvas.verified = verified
        self.actions.undo.setEnabled(bool(self._undoStack))
        self.actions.redo.setEnabled(bool(self._redoStack))
        self.canvas.update()

    def panImage(self, dx, dy):
        for orientation, delta in ((Qt.Horizontal, dx), (Qt.Vertical, dy)):
            bar = self.scrollBars[orientation]
            bar.setValue(bar.value() - delta)

    def scrollRequest(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scrollBars[orientation]
        bar.setValue(round(bar.value() + max(40, bar.singleStep() * 3) * units))

    def setZoom(self, value):
        viewport = self.centralWidget().viewport()
        first_view = self.canvas.viewportSize.isEmpty()
        self.canvas.viewportSize = viewport.size()
        if first_view and not self.image.isNull():
            self.canvas.adjustSize()
            self.scrollBars[Qt.Horizontal].setValue(round(viewport.width() / 2 + self.canvas.imageSize.width() * self.canvas.scale / 2))
            self.scrollBars[Qt.Vertical].setValue(round(viewport.height() / 2 + self.canvas.imageSize.height() * self.canvas.scale / 2))
        global_pos = self.canvas.zoomAnchor or QCursor.pos()
        anchor = viewport.mapFromGlobal(global_pos)
        if not viewport.rect().contains(anchor):
            anchor = viewport.rect().center()
        before = self.canvas.transformPos(self.canvas.mapFromGlobal(viewport.mapToGlobal(anchor)))
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)
        if not self.image.isNull():
            self.canvas.adjustSize()
            self._zoomSerial += 1
            serial = self._zoomSerial
            global_anchor = viewport.mapToGlobal(anchor)
            self.restoreZoomAnchor(before, global_anchor, serial)
            # Scrollbar appearance can resize the viewport after this event.
            QTimer.singleShot(0, lambda: self.restoreZoomAnchor(before, global_anchor, serial))

    def restoreZoomAnchor(self, point, global_anchor, serial):
        if serial != self._zoomSerial or self.image.isNull():
            return
        viewport = self.centralWidget().viewport()
        anchor = viewport.mapFromGlobal(global_anchor)
        after = (point + self.canvas.offsetToCenter()) * self.canvas.scale
        current = QPointF(self.canvas.mapTo(viewport, QPoint())) + after
        for orientation, delta in ((Qt.Horizontal, current.x() - anchor.x()),
                                   (Qt.Vertical, current.y() - anchor.y())):
            bar = self.scrollBars[orientation]
            bar.setValue(bar.value() + round(delta))
        self.canvas.update()
        self.scheduleDetail()
        self.updateInspectionViewport()

    def addZoom(self, increment=1):
        # Relative steps give the same moderate pace for huge and small images.
        current = self.zoomWidget.value()
        target = current * (1.15 ** increment)
        if increment and round(target, 2) == current:
            target = current + (0.01 if increment > 0 else -0.01)
        self.setZoom(target)

    def zoomRequest(self, delta):
        units = delta / (8 * 15)
        self.addZoom(units)

    def setFitWindow(self, value=True):
        self._zoomSerial += 1
        self.canvas.viewOffset = QPointF()
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()
        self.centerOnImagePoint(QPointF(self.canvas.imageSize.width() / 2,
                                       self.canvas.imageSize.height() / 2))

    def setFitWidth(self, value=True):
        self._zoomSerial += 1
        self.canvas.viewOffset = QPointF()
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()
        self.centerOnImagePoint(QPointF(self.canvas.imageSize.width() / 2,
                                       self.canvas.imageSize.height() / 2))

    def togglePolygons(self, value):
        for item, shape in self.itemsToShapes.items():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def loadFile(self, filePath=None):
        filePath = ustr(filePath or self.settings.get('filename', ''))
        if not filePath or not os.path.isfile(filePath):
            return False
        if os.path.splitext(filePath)[1].lower() in ('.json', '.xml'):
            if self.filePath:
                self.loadAnnotation(filePath)
            else:
                self.errorMessage('Open image first', 'Please open the matching image before its annotation.')
            return False
        self.resetState()
        self.canvas.setEnabled(False)
        self._loading = True
        self.spinner.setRunning(True)
        self.status('Loading image / 正在加载影像 …', 0)
        self._pendingLoad = (filePath, self._generation)
        self.startPendingLoad()
        return True

    def startPendingLoad(self):
        # At most one overview decode; rapid navigation replaces the pending path.
        if self._loadWorker is not None or self._pendingLoad is None:
            return
        path, generation = self._pendingLoad
        self._pendingLoad = None
        worker = ImageLoader(path, self)
        worker.generation = generation
        self._loadWorker = worker
        self._workers.add(worker)
        worker.loaded.connect(self.imageLoaded)
        worker.failed.connect(self.imageLoadFailed)
        worker.finished.connect(self.workerFinished)
        worker.start()

    def workerFinished(self):
        worker = self.sender()
        self._workers.discard(worker)
        if self._tutorialWorker is worker:
            self._tutorialWorker = None
            self.tutorialAction.setEnabled(True)
        if self._loadWorker is worker:
            self._loadWorker = None
        if self._detailWorker is worker:
            self._detailWorker = None
            self.scheduleDetail()
        worker.deleteLater()
        if self._closePending:
            if not self._workers:
                self.close()
        else:
            self.startPendingLoad()

    def imageLoadFailed(self, message):
        if self.sender().generation != self._generation:
            return
        self._loading = False
        self.spinner.setRunning(False)
        self.status('Image load failed')
        self.errorMessage('Error opening image', message)

    def imageLoaded(self, result):
        if self.sender().generation != self._generation:
            return
        self._loading = False
        self.spinner.setRunning(False)
        self.image = result['image']
        self.filePath = result['path']
        self._raster = result['raster']
        self._stretch = result['stretch']
        coordinates = result.get('coordinates', {})
        self.centerCoordinates.setText(coordinates.get('text', ''))
        self.centerCoordinates.setCursorPosition(0)
        self.centerCoordinates.setPlaceholderText(coordinates.get('message', '无地理参考信息'))
        self.centerCoordinates.setToolTip(coordinates.get('message', ''))
        self.copyCoordinatesButton.setEnabled(bool(coordinates.get('text')))
        self.canvas.loadPixmap(QPixmap.fromImage(self.image), QSize(*result['size']))
        self.canvas.setEditing(True)
        self.canvas.setEnabled(True)
        self.adjustScale(initial=True)
        self.paintCanvas()
        self.centerOnImagePoint(QPointF(self.canvas.imageSize.width() / 2,
                                       self.canvas.imageSize.height() / 2))
        self.toggleActions(True)
        self.setClean()
        self.addRecentFile(self.filePath)
        if self.filePath not in self.mImgList:
            self.dirname = None
            self.mImgList = [self.filePath]
        self.refreshImageList()
        annotations = self.findAnnotations()
        if annotations:
            self.loadAnnotation(annotations[0])
        message = 'Loaded %s (%s × %s)' % (os.path.basename(self.filePath), *result['size'])
        if annotations:
            message += ' · 读取标注：' + os.path.basename(annotations[0])
            if len(annotations) > 1:
                message += '（采用最近修改的文件，另一格式保留）'
        if self._annotationWarnings:
            message += ' · ' + '；'.join(dict.fromkeys(self._annotationWarnings))
        self.status(message, 10000)
        if self.selectedCategory():
            self.selectDrawTool(self._lastDrawTool)
        self.canvas.setFocus()
        self.scheduleDetail()
        if hasattr(self, '_inspectionDialog'):
            self._inspectionDialog.setImage(self.filePath, self.image, self.canvas.imageSize)
            self.updateInspectionViewport()

    def scheduleDetail(self, *args):
        if self._raster and not self._loading and self.filePath and not self._closePending:
            self._detailTimer.start(120)

    def loadVisibleRegion(self):
        if self._closePending or not self._raster or not self.filePath or self._detailWorker is not None:
            return
        scale = self.canvas.scale
        if scale <= min(self.image.width() / self.canvas.imageSize.width(),
                        self.image.height() / self.canvas.imageSize.height()):
            return
        viewport = self.centralWidget().viewport()
        origin = self.canvas.transformPos(QPointF(self.canvas.mapFrom(viewport, QPoint(0, 0))))
        width, height = self.canvas.imageSize.width(), self.canvas.imageSize.height()
        x, y = max(0, int(origin.x())), max(0, int(origin.y()))
        w = min(width - x, int(viewport.width() / scale) + 2)
        h = min(height - y, int(viewport.height() / scale) + 2)
        if w <= 0 or h <= 0:
            return
        key = (self._generation, x, y, w, h, round(scale, 5))
        if key == self._detailKey:
            return
        self._detailKey = key
        worker = ImageLoader(self.filePath, self, (x, y, w, h), self._stretch,
                             min(4096, max(viewport.width(), viewport.height()) + 2))
        worker.generation = self._generation
        self._detailWorker = worker
        self._workers.add(worker)
        worker.loaded.connect(self.detailLoaded)
        worker.failed.connect(self.detailFailed)
        worker.finished.connect(self.workerFinished)
        self.spinner.setRunning(True)
        worker.start()

    def detailLoaded(self, result):
        if self.sender().generation == self._generation:
            self.canvas.detailPixmap = QPixmap.fromImage(result['image'])
            self.canvas.detailRect = QRectF(*result['bounds'])
            self.canvas.update()
            self.spinner.setRunning(False)

    def detailFailed(self, message):
        if self.sender().generation == self._generation:
            self.spinner.setRunning(False)
            self.status('Detail read failed: ' + message)

    def loadAnnotation(self, path):
        try:
            if path.lower().endswith('.json'):
                shapes, verified = read_coco(path, self.filePath)
            else:
                reader = PascalVocReader(path)
                shapes, verified = reader.getShapes(), reader.verified
            self.loadLabels(shapes)
            self._undoStack.clear()
            self._redoStack.clear()
            self.actions.undo.setEnabled(False)
            self.actions.redo.setEnabled(False)
            self.canvas.verified = verified
            self.labelFile = LabelFile()
            self._annotationPaths[os.path.splitext(path)[1].lower()] = os.path.abspath(path)
            self._failedAnnotationPaths.discard(identity(path))
            index = 0 if path.lower().endswith('.json') else 1
            self.formatCombo.blockSignals(True)
            try:
                self.formatCombo.setCurrentIndex(index)
            finally:
                self.formatCombo.blockSignals(False)
            self.usingPascalVocFormat = index == 1
            LabelFile.suffix = '.xml' if index else '.json'
            self.settings['exportFormat'] = index
            self.setClean()
            return True
        except Exception as exc:
            self._failedAnnotationPaths.add(identity(path))
            self.errorMessage('Error opening annotation', str(exc))
            return False

    def resizeEvent(self, event):
        self.scheduleDetail()
        super(MainWindow, self).resizeEvent(event)
        self.updateInspectionViewport()

    def workspaceResized(self):
        if self.image.isNull():
            self.canvas.resize(self.centralWidget().viewport().size())
            return
        viewport = self.centralWidget().viewport()
        old_size = self.canvas.viewportSize
        center = self.canvas.transformPos(QPointF(self.canvas.mapFrom(viewport,
                                          QPoint(old_size.width() // 2, old_size.height() // 2))))
        self._zoomSerial += 1
        self.canvas.viewportSize = viewport.size()
        if self.zoomMode != self.MANUAL_ZOOM:
            self.adjustScale()
        self.paintCanvas()
        self.centerOnImagePoint(center)
        self.updateInspectionViewport()

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.viewportSize = self.centralWidget().viewport().size()
        self.canvas.adjustSize()
        self.canvas.update()
        self.scheduleDetail()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        self.zoomWidget.setValue(100 * value)

    def scaleFitWindow(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        w1 = max(1, self.centralWidget().viewport().width() - 2.0)
        h1 = max(1, self.centralWidget().viewport().height() - 2.0)
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.imageSize.width() - 0.0
        h2 = self.canvas.imageSize.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = max(1, self.centralWidget().viewport().width() - 2.0)
        return w / self.canvas.imageSize.width()

    def closeEvent(self, event):
        if not self._closePending and not self.mayContinue():
            event.ignore()
            return
        self.updater.cancel()
        if self._workers:
            self._closePending = True
            self._pendingLoad = None
            self._generation += 1
            self._detailTimer.stop()
            for worker in self._workers:
                worker.requestInterruption()
            # Never destroy a running QThread or block the GUI with wait().
            self.hide()
            event.ignore()
            return
        self.canvas.setSpacePan(False)
        QApplication.instance().removeEventFilter(self)
        s = self.settings
        # If it loads images from dir, don't load it at the begining
        if self.dirname is None:
            s['filename'] = self.filePath if self.filePath else ''
        else:
            s['filename'] = ''

        s['window/size'] = self.size()
        s['window/position'] = self.pos()
        s['window/state'] = self.saveState()
        s['line/color'] = self.lineColor
        s['fill/color'] = self.fillColor
        s['recentFiles'] = self.recentFiles
        s['advanced'] = not self._beginner
        if self.defaultSaveDir is not None and len(self.defaultSaveDir) > 1:
            s['savedir'] = ustr(self.defaultSaveDir)
        else:
            s['savedir'] = ""

        if self.lastOpenDir is not None and len(self.lastOpenDir) > 1:
            s['lastOpenDir'] = self.lastOpenDir
        else:
            s['lastOpenDir'] = ""

    ## User Dialogs ##

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def scanAllImages(self, folderPath):
        extensions = ['.jpeg', '.jpg', '.png', '.bmp', '.tif', '.tiff', '.img', '.vrt', '.jp2']
        images = []

        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relatviePath = os.path.join(root, file)
                    path = ustr(os.path.abspath(relatviePath))
                    images.append(path)
        images.sort(key=lambda x: x.lower())
        return images

    def changeSavedir(self, _value=False):
        if self.defaultSaveDir is not None:
            path = ustr(self.defaultSaveDir)
        else:
            path = '.'

        dirpath = ustr(QFileDialog.getExistingDirectory(self,
                                                       '%s - Save to the directory' % __appname__, path,  QFileDialog.ShowDirsOnly
                                                       | QFileDialog.DontResolveSymlinks))

        if dirpath is not None and len(dirpath) > 1:
            self.defaultSaveDir = dirpath

        self.statusBar().showMessage('%s . Annotation will be saved to %s' %
                                     ('Change saved folder', self.defaultSaveDir))
        self.statusBar().show()

    def openAnnotation(self, _value=False):
        if not self.filePath or not self.mayContinue():
            return
        filename, _ = QFileDialog.getOpenFileName(self, 'Open annotation',
                                                os.path.dirname(self.filePath),
                                                'Annotations (*.json *.xml)')
        if filename:
            self.loadAnnotation(filename)

    def openDir(self, _value=False):
        if not self.mayContinue():
            return

        path = os.path.dirname(self.filePath)\
            if self.filePath else '.'

        if self.lastOpenDir is not None and len(self.lastOpenDir) > 1:
            path = self.lastOpenDir

        dirpath = ustr(QFileDialog.getExistingDirectory(self,
                                                     '%s - Open Directory' % __appname__, path,  QFileDialog.ShowDirsOnly
                                                     | QFileDialog.DontResolveSymlinks))

        if not dirpath:
            return
        self.lastOpenDir = dirpath
        images = self.scanAllImages(dirpath)
        if not images:
            self.status('所选文件夹及子文件夹中没有支持的影像', 10000)
            return
        self.dirname = dirpath
        self.filePath = None
        self.mImgList = images
        self.refreshImageList()
        self.loadFile(images[0])

    def verifyImg(self, _value=False):
        # Proceding next image without dialog if having any label
         if self.filePath is not None:
            try:
                self.labelFile.toggleVerify()
            except AttributeError:
                # If the labelling file does not exist yet, create if and
                # re-save it with the verified attribute.
                self.saveFile()
                if self.labelFile is not None:
                    self.labelFile.toggleVerify()
            if self.labelFile is not None:
                self.canvas.verified = True
            self.paintCanvas()
            self.saveFile()

    def openPrevImg(self, _value=False):
        if not self.mayContinue():
            return

        if len(self.mImgList) <= 0:
            return

        if self.filePath is None:
            return

        currIndex = self.mImgList.index(self.filePath)
        if currIndex - 1 >= 0:
            filename = self.mImgList[currIndex - 1]
            if filename:
                self.loadFile(filename)

    def openNextImg(self, _value=False):
        if not self.mayContinue():
            return

        if len(self.mImgList) <= 0:
            return

        filename = None
        if self.filePath is None:
            filename = self.mImgList[0]
        else:
            currIndex = self.mImgList.index(self.filePath)
            if currIndex + 1 < len(self.mImgList):
                filename = self.mImgList[currIndex + 1]

        if filename:
            self.loadFile(filename)


    def openFile(self, _value=False):
        if not self.mayContinue():
            return
        path = os.path.dirname(ustr(self.filePath)) if self.filePath else '.'
        formats = ['*.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        filters = "Image & Label files (%s)" % ' '.join(formats + ['*.tif', '*.tiff', '*.img', '*.vrt', '*.jp2', '*.json', '*.xml'])
        filename = QFileDialog.getOpenFileName(self, '%s - Choose Image or Label file' % __appname__, path, filters)
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]
            self.loadFile(filename)

    def saveFile(self, _value=False):
        if not self.filePath or self._loading:
            return False
        savedPath = self.defaultAnnotationPath(LabelFile.suffix)
        if not self.defaultSaveDir:
            savedPath = self._annotationPaths.get(LabelFile.suffix, savedPath)
        return self._saveFile(savedPath)

    def defaultAnnotationPath(self, suffix):
        path = annotation_path(self.filePath, suffix, self.defaultSaveDir,
                               self.dirname, self.mImgList)
        if os.path.isfile(path):
            try:
                source = annotation_source(path)
            except (OSError, ValueError):
                return path
            if source and identity(source) != identity(self.filePath):
                alternative = os.path.join(os.path.dirname(path), os.path.basename(self.filePath) + suffix)
                if os.path.isfile(alternative):
                    try:
                        owner = annotation_source(alternative)
                    except (OSError, ValueError):
                        owner = None
                    if not owner or identity(owner) != identity(self.filePath):
                        token = hashlib.sha256(identity(self.filePath).encode('utf-8')).hexdigest()[:12]
                        alternative = os.path.join(os.path.dirname(path), os.path.basename(self.filePath) + '--' + token + suffix)
                return alternative
        return path

    def findAnnotations(self):
        self._annotationWarnings = []
        directory = self.defaultSaveDir or os.path.dirname(self.filePath)
        stem = os.path.splitext(os.path.basename(self.filePath))[0]
        same_names = {identity(p) for p in self.mImgList
                      if os.path.splitext(os.path.basename(p))[0].casefold() == stem.casefold()}
        found = []
        for suffix in (LabelFile.suffix, '.xml' if LabelFile.suffix == '.json' else '.json'):
            canonical = self.defaultAnnotationPath(suffix)
            legacy = os.path.join(directory, stem + suffix)
            for path in dict.fromkeys((canonical, legacy)):
                if not os.path.isfile(path):
                    continue
                try:
                    source = annotation_source(path)
                    if source and identity(source) != identity(self.filePath):
                        self._annotationWarnings.append('存在来源不匹配的标注，未自动读取；可手动打开核对并另存为')
                        continue
                    if not source and identity(path) == identity(legacy) and len(same_names) > 1:
                        self._annotationWarnings.append('旧版同名标注无法确定来源，请手动打开核对')
                        continue
                    if not source and self.defaultSaveDir and identity(directory) != identity(os.path.dirname(self.filePath)):
                        self._annotationWarnings.append('共享目录中的旧标注缺少来源，请手动打开一次并保存')
                        continue
                except (OSError, ValueError, AttributeError):
                    # Let the normal reader report malformed canonical files.
                    if identity(path) != identity(canonical):
                        continue
                if path not in found:
                    found.append(path)
        return sorted(found, key=lambda p: (os.stat(p).st_mtime_ns,
                                            p.lower().endswith(LabelFile.suffix)), reverse=True)

    def saveFileAs(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._saveFile(self.saveFileDialog())

    def saveFileDialog(self):
        caption = '%s - Choose File' % __appname__
        filters = 'File (*%s)' % LabelFile.suffix
        openDialogPath = self.currentPath()
        dlg = QFileDialog(self, caption, openDialogPath, filters)
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        filenameWithoutExtension = os.path.splitext(self.filePath)[0]
        dlg.selectFile(filenameWithoutExtension)
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)
        if dlg.exec_():
            return dlg.selectedFiles()[0]
        return ''

    def _saveFile(self, annotationFilePath):
        if not self.filePath or self._loading:
            return False
        annotationFilePath = ustr(annotationFilePath)
        if annotationFilePath and not annotationFilePath.lower().endswith(LabelFile.suffix):
            annotationFilePath = os.path.splitext(annotationFilePath)[0] + LabelFile.suffix
        if not annotationFilePath:
            return False
        try:
            if identity(annotationFilePath) in self._failedAnnotationPaths:
                raise ValueError('此标注文件读取失败，已阻止覆盖。请修复原文件，或另存为一个新文件。')
            if not safe_to_overwrite(annotationFilePath, self.filePath,
                                     self._annotationPaths.values()):
                raise ValueError('目标标注属于其他影像，或缺少来源信息。请使用“另存为”选择新文件。')
            os.makedirs(os.path.dirname(os.path.abspath(annotationFilePath)), exist_ok=True)
        except (OSError, ValueError) as exc:
            self.errorMessage('无法保存标注', str(exc))
            return False
        if self.saveLabels(annotationFilePath):
            self._annotationPaths[LabelFile.suffix] = os.path.abspath(annotationFilePath)
            self.setClean()
            self.statusBar().showMessage('Saved to  %s' % annotationFilePath)
            self.statusBar().show()
            return True
        return False

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    def mayContinue(self):
        if not self.dirty:
            return True
        if self.autoSaving and self.defaultSaveDir:
            return bool(self.saveFile())
        return self.discardChangesDialog()

    def discardChangesDialog(self):
        choice = QMessageBox.warning(
            self, '有未保存的标注', '当前影像的标注已修改，是否保存后继续？',
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save)
        if choice == QMessageBox.Save:
            return bool(self.saveFile())
        return choice == QMessageBox.Discard

    def errorMessage(self, title, message):
        return QMessageBox.critical(self, title,
                                    '<p><b>%s</b></p>%s' % (title, message))

    def currentPath(self):
        return os.path.dirname(self.filePath) if self.filePath else '.'

    def chooseColor1(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.lineColor = color
            # Change the color for all shape lines:
            Shape.line_color = self.lineColor
            self.canvas.update()
            self.setDirty()

    def chooseColor2(self):
        color = self.colorDialog.getColor(self.fillColor, u'Choose fill color',
                                          default=DEFAULT_FILL_COLOR)
        if color:
            self.fillColor = color
            Shape.fill_color = self.fillColor
            self.canvas.update()
            self.setDirty()

    def deleteSelectedShape(self):
        selected = [self.itemsToShapes[item] for item in self.labelList.selectedItems()]
        if not selected and self.canvas.selectedShape:
            selected = [self.canvas.selectedShape]
        if not selected:
            return
        unlocked = [shape for shape in selected if not shape.locked]
        if len(unlocked) != len(selected):
            self.status('锁定的框不会删除；请先点击“锁定/解锁”')
        selected = unlocked
        if not selected:
            return
        self.invalidateInspection([shape.boundingRect() for shape in selected])
        self.pushUndo()
        self.labelList.blockSignals(True)
        try:
            self.canvas.unHighlight()
            self.canvas.selectedShape = None
            self.canvas._editingGesture = self.canvas._rotatingGesture = False
            for shape in selected:
                self.canvas.shapes.remove(shape)
                self.canvas.visible.pop(shape, None)
                self.remLabel(shape)
        finally:
            self.labelList.blockSignals(False)
        self.shapeSelectionChanged(False)
        self.canvas.update()
        self.setDirty()
        if self.noShapes():
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)

    def chshapeLineColor(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.canvas.selectedShape.line_color = color
            self.canvas.update()
            self.setDirty()

    def chshapeFillColor(self):
        color = self.colorDialog.getColor(self.fillColor, u'Choose fill color',
                                          default=DEFAULT_FILL_COLOR)
        if color:
            self.canvas.selectedShape.fill_color = color
            self.canvas.update()
            self.setDirty()

    def copyShape(self):
        self.canvas.endMove(copy=True)
        self.addLabel(self.canvas.selectedShape)
        self.setDirty()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()

    def loadPredefinedClasses(self, predefClassesFile):
        if not os.path.exists(self.labelStore.path) and predefClassesFile and os.path.exists(predefClassesFile):
            with codecs.open(predefClassesFile, 'r', 'utf8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.labelStore.ensure(line)

    def seedReferenceClasses(self, predefClassesFile):
        reference = os.path.join(dir_name, 'data', 'predefined_classes.txt')
        if not predefClassesFile or not os.path.isfile(reference) or not os.path.isfile(predefClassesFile):
            return
        if os.path.abspath(predefClassesFile) != os.path.abspath(reference):
            return
        if self.labelStore.reference_initialized:
            return
        with codecs.open(reference, 'r', 'utf8') as stream:
            for line in stream:
                if line.strip():
                    self.labelStore.ensure(line.strip())
        self.labelStore.reference_initialized = True
        self.labelStore.save()

    def loadPascalXMLByFilename(self, xmlPath):
        if self.filePath is None:
            return
        if os.path.isfile(xmlPath) is False:
            return

        tVocParseReader = PascalVocReader(xmlPath)
        shapes = tVocParseReader.getShapes()
        self.loadLabels(shapes)
        self.canvas.verified = tVocParseReader.verified


class Settings(object):
    """Convenience dict-like wrapper around QSettings."""

    def __init__(self, types=None):
        self.data = QSettings()
        self.types = defaultdict(lambda: QVariant, types if types else {})

    def __setitem__(self, key, value):
        t = self.types[key]
        self.data.setValue(key,
                           t(value) if not isinstance(value, t) else value)

    def __getitem__(self, key):
        return self._cast(key, self.data.value(key))

    def get(self, key, default=None):
        return self._cast(key, self.data.value(key, default))

    def _cast(self, key, value):
        # XXX: Very nasty way of converting types to QVariant methods :P
        t = self.types.get(key)
        if t is not None and t != QVariant:
            if t is str:
                return ustr(value)
            else:
                try:
                    method = getattr(QVariant, re.sub(
                        '^Q', 'to', t.__name__, count=1))
                    return method(value)
                except AttributeError as e:
                    # print(e)
                    return value
        return value


def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def read(filename, default=None):
    try:
        with open(filename, 'rb') as f:
            return f.read()
    except:
        return default


def get_main_app(argv=[]):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(newIcon("app"))
    # Tzutalin 201705+: Accept extra agruments to change predefined class file
    # Usage : labelImg.py image predefClassFile
    win = MainWindow(argv[1] if len(argv) >= 2 else None,
                     argv[2] if len(argv) >= 3 else os.path.join(dir_name, 'data', 'predefined_classes.txt'))
    win.show()
    return app, win


def main(argv=[]):
    '''construct main app and run it'''
    app, _win = get_main_app(argv)
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main(sys.argv))
