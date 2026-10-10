"""Regression checks for data loss, file compatibility and editing workflows."""
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'libs'))

from PyQt5.QtCore import QSettings, QStandardPaths, Qt, QPointF, QEvent, QCoreApplication
from PyQt5.QtGui import QImage, QPixmap, QMouseEvent
from PyQt5.QtWidgets import QApplication, QMessageBox, QStyleOptionViewItem
from PyQt5.QtTest import QTest
import roLabelImg
from label_store import LabelStore
from annotation_paths import annotation_path
from box_geometry import validate_box
from pascal_voc_io import PascalVocReader, PascalVocWriter
from xml.etree import ElementTree


class SafetyWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        QStandardPaths.setTestModeEnabled(True)
        cls.app.setApplicationName('roLabelImg-safety-tests')
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(self.root))
        QSettings().clear()
        self.store_patch = patch.object(roLabelImg, 'LabelStore',
                                        lambda: LabelStore(str(self.root / 'labels.json')))
        self.store_patch.start()
        self.window = roLabelImg.MainWindow()
        self.window.resetState()
        self.window.image = QImage(1200, 900, QImage.Format_RGB32)
        self.window.image.fill(Qt.white)
        self.window.canvas.loadPixmap(QPixmap.fromImage(self.window.image))
        self.window.toggleActions(True)
        self.window.filePath = str(self.root / 'images' / 'scene.png')
        self.window.defaultSaveDir = str(self.root / 'annotations')
        self.window.dirname = str(self.root / 'images')

    def tearDown(self):
        self.window.dirty = False
        self.window.close()
        for _ in range(1000):
            if not self.window._workers:
                break
            QTest.qWait(10)
        self.assertFalse(self.window._workers, 'Background workers did not finish')
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.store_patch.stop()
        self.app.processEvents()
        self.temp.cleanup()

    def add(self, name='Bridge'):
        self.window.loadLabels([(name, [(10, 10), (100, 10), (100, 80), (10, 80)],
                                 0, False, None, None, False)])
        self.window.setDirty()

    def test_subdirectories_and_extensions_do_not_overwrite(self):
        w = self.window
        a, b = str(self.root / 'images' / 'a' / 'same.png'), str(self.root / 'images' / 'b' / 'same.png')
        w.mImgList = [a, b]
        w.filePath = a
        self.add()
        self.assertTrue(w.saveFile())
        first = self.root / 'annotations' / 'a' / 'same.json'
        original = first.read_bytes()
        w.filePath = b
        w._annotationPaths.clear()
        self.add('CargoShip')
        self.assertTrue(w.saveFile())
        self.assertEqual(first.read_bytes(), original)
        self.assertTrue((self.root / 'annotations' / 'b' / 'same.json').exists())
        png, tif = str(self.root / 'images' / 'same.png'), str(self.root / 'images' / 'same.tif')
        w.mImgList = [png, tif]
        self.assertNotEqual(annotation_path(png, '.json', w.defaultSaveDir, w.dirname, w.mImgList),
                            annotation_path(tif, '.json', w.defaultSaveDir, w.dirname, w.mImgList))

    def test_wrong_source_and_unknown_files_are_not_overwritten(self):
        w = self.window
        self.add()
        self.assertTrue(w.saveFile())
        path = w.defaultAnnotationPath('.json')
        original = Path(path).read_bytes()
        w.filePath = str(self.root / 'images' / 'different.png')
        w._annotationPaths.clear()
        with patch.object(w, 'errorMessage') as error:
            self.assertFalse(w._saveFile(path))
            self.assertTrue(error.called)
        self.assertEqual(Path(path).read_bytes(), original)

    def test_separate_single_image_sessions_have_unique_paths(self):
        destination = str(self.root / 'output')
        a = annotation_path(str(self.root / 'a' / 'same.png'), '.json', destination)
        b = annotation_path(str(self.root / 'b' / 'same.png'), '.json', destination)
        self.assertNotEqual(a, b)

    def test_navigation_save_failure_blocks_switch_and_close(self):
        w = self.window
        self.add()
        with patch.object(w, 'saveFile', return_value=False) as save:
            self.assertFalse(w.mayContinue())
            w.openPrevImg()
            w.openNextImg()
            w.show()
            self.assertFalse(w.close())
            self.assertTrue(w.dirty)
            self.assertEqual(save.call_count, 4)

    def test_save_discard_cancel_choices(self):
        w = self.window
        w.defaultSaveDir = None
        self.add()
        for choice, expected in ((QMessageBox.Cancel, False), (QMessageBox.Discard, True)):
            with patch.object(QMessageBox, 'warning', return_value=choice):
                self.assertEqual(w.mayContinue(), expected)
                self.assertTrue(w.dirty)
        with patch.object(QMessageBox, 'warning', return_value=QMessageBox.Save):
            self.assertTrue(w.mayContinue())
            self.assertFalse(w.dirty)
            self.assertTrue((self.root / 'images' / 'scene.json').exists())

    def test_all_navigation_uses_the_same_auto_save_policy(self):
        w = self.window
        self.add()
        self.assertTrue(w.mayContinue())
        self.assertFalse(w.dirty)
        self.assertTrue(Path(w.defaultAnnotationPath('.json')).exists())

    def test_zero_width_and_height_are_cancelled_but_tiny_boxes_work(self):
        w = self.window
        self.add()
        w.loadLabels([])
        w.refreshLabelLibrary()
        w.categoryGrid.setCurrentCell(0, 0)
        canvas = w.canvas
        for end in ((110, 10), (10, 110), (10, 10), (11, 11)):
            canvas.handleDrawing(QPointF(10, 10))
            canvas.line[1] = QPointF(*end)
            canvas.handleDrawing(QPointF(*end))
        self.assertEqual(len(canvas.shapes), 1)
        self.assertEqual(validate_box([(p.x(), p.y()) for p in canvas.shapes[0].points]), 1)

    def test_invalid_import_keeps_existing_labels_and_save_is_blocked(self):
        w = self.window
        self.add()
        invalid = [('Bridge', [(10, 10)] * 4, 0, False, None, None, False)]
        with self.assertRaises(ValueError):
            w.loadLabels(invalid)
        self.assertEqual(len(w.canvas.shapes), 1)
        w.canvas.shapes[0].points = [QPointF(10, 10)] * 4
        with patch.object(w, 'errorMessage') as error:
            self.assertFalse(w.saveFile())
            self.assertTrue(error.called)
        self.assertTrue(w.dirty)
        self.assertFalse(Path(w.defaultAnnotationPath('.json')).exists())

    def test_voc_without_custom_type_and_optional_fields(self):
        path = self.root / 'external.XML'
        path.write_text('<annotation><object><name>Bridge</name>'
                        '<bndbox><xmin>1</xmin><ymin>2</ymin><xmax>30</xmax><ymax>40</ymax></bndbox>'
                        '</object><object><name>CargoShip</name><robndbox>'
                        '<cx>100</cx><cy>100</cy><w>40</w><h>20</h><angle>0.5</angle>'
                        '</robndbox></object></annotation>', encoding='utf-8')
        shapes = PascalVocReader(str(path)).getShapes()
        self.assertEqual(len(shapes), 2)
        self.assertFalse(shapes[0][3])
        self.assertTrue(shapes[1][3])
        self.assertFalse(shapes[0][-1])

    def test_voc_failed_replacement_preserves_existing_file(self):
        path = self.root / 'original.xml'
        writer = PascalVocWriter('images', 'scene', (100, 100, 3))
        writer.addBndBox(1, 2, 30, 40, 'Bridge', False)
        writer.save(str(path))
        original = path.read_bytes()
        with patch('pascal_voc_io.os.replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                writer.save(str(path))
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(list(self.root.glob('.annotations-*.tmp')))

    def test_dirty_title_and_persistent_status_clear_only_after_success(self):
        w = self.window
        self.add()
        self.assertEqual(w.windowTitle(), 'roLabelImg *')
        self.assertIn('未保存', w.saveStatus.text())
        w.status('鼠标坐标变化')
        self.assertIn('未保存', w.saveStatus.text())
        self.assertTrue(w.saveFile())
        self.assertEqual(w.windowTitle(), 'roLabelImg')
        self.assertIn('已保存', w.saveStatus.text())
        w.setDirty()
        with patch.object(w, 'saveLabels', return_value=False):
            self.assertFalse(w.saveFile())
        self.assertEqual(w.windowTitle(), 'roLabelImg *')

    def test_newest_format_is_selected_and_format_preference_is_saved(self):
        w = self.window
        self.add()
        self.assertTrue(w.saveFile())
        json_path = w.defaultAnnotationPath('.json')
        w.formatCombo.setCurrentIndex(1)
        self.add('CargoShip')
        self.assertTrue(w.saveFile())
        xml_path = w.defaultAnnotationPath('.xml')
        os.utime(json_path, (1000, 1000))
        os.utime(xml_path, (2000, 2000))
        w.formatCombo.setCurrentIndex(0)
        self.assertEqual(w.findAnnotations()[0], xml_path)
        self.assertTrue(w.loadAnnotation(w.findAnnotations()[0]))
        self.assertEqual(w.canvas.shapes[0].label, 'CargoShip')
        self.assertEqual(w.formatCombo.currentIndex(), 1)
        self.assertEqual(w.settings.get('exportFormat'), 1)
        self.assertFalse(w.dirty)
        self.assertTrue(w.saveFile())
        self.assertEqual(json.loads(Path(json_path).read_text(encoding='utf-8'))['annotations'][0]['category_id'],
                         w.labelStore.ensure('Bridge')['id'])

    def test_category_change_preserves_normal_drawing(self):
        w = self.window
        w.labelStore.ensure('Bridge')
        w.labelStore.ensure('CargoShip')
        w.refreshLabelLibrary()
        w.actions.create.trigger()
        w.categoryGrid.setCurrentCell(0, 0)
        self.assertEqual(w._activeDraw, 'normal')
        w.categoryGrid.setCurrentCell(0, 1)
        self.assertEqual(w._activeDraw, 'normal')

    def test_control_draws_inside_existing_box_and_overlap_selection_cycles(self):
        w = self.window
        self.add()
        w.refreshLabelLibrary()
        w.categoryGrid.setCurrentCell(0, 0)
        canvas = w.canvas
        for kind, point, buttons in ((QEvent.MouseButtonPress, QPointF(40, 30), Qt.LeftButton),
                                     (QEvent.MouseButtonRelease, QPointF(80, 60), Qt.NoButton)):
            local = (point + canvas.offsetToCenter()) * canvas.scale
            event = QMouseEvent(kind, local, Qt.LeftButton, buttons, Qt.ControlModifier)
            canvas.mousePressEvent(event) if kind == QEvent.MouseButtonPress else canvas.mouseReleaseEvent(event)
        self.assertEqual(len(canvas.shapes), 2)
        third = canvas.shapes[0].copy()
        canvas.shapes.append(third)
        canvas._hoverPoint = QPointF(50, 40)
        selected = set()
        for _ in range(3):
            canvas.cycleOverlapping()
            selected.add(canvas.selectedShape)
        self.assertEqual(len(selected), 3)

    def test_undo_redo_and_new_branch_clear_redo(self):
        w = self.window
        self.add()
        w.pushUndo()
        w.canvas.shapes[0].moveBy(QPointF(20, 30))
        w.setDirty()
        w.undoAnnotation()
        self.assertEqual(w.canvas.shapes[0][0], QPointF(10, 10))
        self.assertTrue(w.actions.redo.isEnabled())
        w.redoAnnotation()
        self.assertEqual(w.canvas.shapes[0][0], QPointF(30, 40))
        w.undoAnnotation()
        w.pushUndo()
        w.canvas.shapes[0].moveBy(QPointF(5, 5))
        w.setDirty()
        self.assertFalse(w.actions.redo.isEnabled())
        w.redoAnnotation()
        self.assertEqual(w.canvas.shapes[0][0], QPointF(15, 15))

    def test_delete_redo_and_image_reset_clear_history(self):
        w = self.window
        self.add()
        w.labelList.setCurrentRow(0)
        w.deleteSelectedShape()
        self.assertEqual(len(w.canvas.shapes), 0)
        w.undoAnnotation()
        self.assertEqual(len(w.canvas.shapes), 1)
        w.redoAnnotation()
        self.assertEqual(len(w.canvas.shapes), 0)
        w.undoAnnotation()
        w.resetState()
        self.assertFalse(w.actions.redo.isEnabled())
        self.assertFalse(w.actions.undo.isEnabled())

    def test_numbers_copy_lock_and_unlock(self):
        w = self.window
        self.add()
        w.labelList.setCurrentRow(0)
        shape = w.canvas.selectedShape
        option = QStyleOptionViewItem()
        w.labelList.itemDelegate().initStyleOption(option, w.labelList.model().index(0, 0))
        self.assertIn('#001', option.text)
        self.assertEqual(w.labelList.item(0).text(), 'Bridge')
        w.toggleSelectedLocks()
        self.assertTrue(shape.locked)
        points = [QPointF(p) for p in shape.points]
        QTest.keyClick(w.canvas, Qt.Key_Right)
        self.assertEqual(shape.points, points)
        w.deleteSelectedShape()
        self.assertEqual(len(w.canvas.shapes), 1)
        w.copySelectedShape()
        self.assertEqual(len(w.canvas.shapes), 2)
        self.assertFalse(w.canvas.selectedShape.locked)
        self.assertNotEqual(w.canvas.shapes[0].identifier, w.canvas.shapes[1].identifier)
        w.labelList.setCurrentRow(0)
        w.toggleSelectedLocks()
        self.assertFalse(shape.locked)
        w.deleteSelectedShape()
        self.assertEqual(len(w.canvas.shapes), 1)

    def test_focus_finds_object_without_changing_geometry(self):
        w = self.window
        self.add()
        shape = w.canvas.shapes[0]
        shape.moveBy(QPointF(600, 500))
        points = [QPointF(p) for p in shape.points]
        w.show()
        self.app.processEvents()
        w.labelList.setCurrentRow(0)
        w.focusAnnotation()
        self.app.processEvents()
        center = ((shape.boundingRect().center() + w.canvas.offsetToCenter()) * w.canvas.scale).toPoint()
        viewport = w.centralWidget().viewport()
        self.assertTrue(viewport.rect().contains(w.canvas.mapTo(viewport, center)))
        self.assertEqual(shape.points, points)

    def test_inspection_progress_saves_then_marks_and_survives_reopen(self):
        w = self.window
        self.add()
        w.showInspection()
        dialog = w._inspectionDialog
        self.assertFalse(dialog.isModal())
        dialog.markButton.click()
        self.assertFalse(w.dirty)
        self.assertIn(0, dialog.overview.completed)
        dialog.clearImage()
        dialog.setImage(w.filePath, w.image, w.canvas.imageSize)
        self.assertIn(0, dialog.overview.completed)
        dialog.selectRegion(1)
        self.app.processEvents()
        self.assertEqual(dialog.overview.active, 1)
        self.assertEqual(len(w.canvas.shapes), 1)
        w.setDirty()
        self.assertNotIn(0, dialog.overview.completed)

    def test_inspection_does_not_mark_if_saving_fails(self):
        w = self.window
        self.add()
        w.showInspection()
        dialog = w._inspectionDialog
        with patch.object(w, 'saveFile', return_value=False):
            dialog.markButton.click()
        self.assertFalse(dialog.overview.completed)
        self.assertTrue(w.dirty)

    def test_chinese_voc_works_with_standard_xml_fallback(self):
        import pascal_voc_io
        path = self.root / '中文标注.xml'
        writer = PascalVocWriter('影像', '中文影像', (100, 100, 3), localImgPath='D:/影像/测试.png')
        writer.addBndBox(1, 2, 30, 40, '桥梁测试', False)
        with patch.object(pascal_voc_io, 'etree', ElementTree):
            writer.save(str(path))
            self.assertEqual(PascalVocReader(str(path)).getShapes()[0][0], '桥梁测试')

    def test_failed_annotation_read_cannot_overwrite_original(self):
        w = self.window
        self.add()
        self.assertTrue(w.saveFile())
        path = w.defaultAnnotationPath('.json')
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        del data['annotations']
        Path(path).write_text(json.dumps(data), encoding='utf-8')
        original = Path(path).read_bytes()
        with patch.object(w, 'errorMessage'):
            self.assertFalse(w.loadAnnotation(path))
            w.setDirty()
            self.assertFalse(w.saveFile())
        self.assertEqual(Path(path).read_bytes(), original)

    def test_unknown_legacy_file_in_shared_directory_requires_manual_import(self):
        w = self.window
        self.add()
        self.assertTrue(w.saveFile())
        path = w.defaultAnnotationPath('.json')
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        del data['images'][0]['source_path']
        Path(path).write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual(w.findAnnotations(), [])
        self.assertTrue(w._annotationWarnings)
        self.assertTrue(w.loadAnnotation(path))
        self.assertTrue(w.saveFile())
        self.assertIn('source_path', json.loads(Path(path).read_text(encoding='utf-8'))['images'][0])

    def test_different_extensions_opened_separately_get_separate_outputs(self):
        w = self.window
        w.filePath = str(self.root / 'images' / 'same.png')
        w.mImgList = [w.filePath]
        self.add()
        self.assertTrue(w.saveFile())
        first = Path(w.defaultAnnotationPath('.json'))
        original = first.read_bytes()
        w.filePath = str(self.root / 'images' / 'same.tif')
        w.mImgList = [w.filePath]
        w._annotationPaths.clear()
        self.add('CargoShip')
        self.assertTrue(w.saveFile())
        self.assertEqual(first.read_bytes(), original)
        self.assertNotEqual(Path(w.defaultAnnotationPath('.json')), first)


if __name__ == '__main__':
    unittest.main()
