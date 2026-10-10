"""Runnable with unittest even in the application's Python without pytest."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'libs'))

from PyQt5.QtCore import QPointF, QSettings, Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap, QColor
from PyQt5.QtWidgets import QApplication, QDialog, QListWidget, QPushButton, QInputDialog, QColorDialog
import roLabelImg
from label_store import LabelStore


class ContinuousWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setApplicationName('roLabelImg-continuous-tests')
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.original_store = roLabelImg.LabelStore
        roLabelImg.LabelStore = lambda: LabelStore(str(self.path / 'labels.json'))
        QSettings().clear()
        self.window = roLabelImg.MainWindow()
        image = QImage(1200, 900, QImage.Format_RGB32)
        image.fill(Qt.white)
        self.window.image = image
        self.window.filePath = str(self.path / 'image.png')
        self.window.canvas.loadPixmap(QPixmap.fromImage(image))
        self.window.toggleActions(True)

    def tearDown(self):
        self.window.dirty = False
        self.window.close()
        roLabelImg.LabelStore = self.original_store
        self.temp.cleanup()

    def draw(self, start, end):
        canvas = self.window.canvas
        canvas.handleDrawing(QPointF(*start))
        canvas.line[1] = QPointF(*end)
        canvas.handleDrawing(QPointF(*end))

    def select(self, name):
        grid = self.window.categoryGrid
        for row in range(grid.rowCount()):
            for column in range(grid.columnCount()):
                item = grid.item(row, column)
                if item and item.data(Qt.UserRole + 1) == name:
                    grid.setCurrentCell(row, column)
                    return
        self.fail('Missing category: ' + name)

    def test_continuous_drawing_switch_and_exit(self):
        self.window.labelStore.ensure('Bridge')
        self.window.labelStore.ensure('Container')
        self.window.refreshLabelLibrary()
        self.assertEqual(self.window.categoryGrid.columnCount(), 2)
        self.assertEqual(self.window.categoryGrid.rowCount(), 1)
        self.assertIsNone(self.window.selectedCategory())
        self.select('Bridge')
        self.assertTrue(self.window.actions.createRo.isChecked())
        self.window.actions.create.trigger()
        self.assertTrue(self.window.actions.create.isChecked())
        self.draw((10, 10), (80, 70))
        self.draw((100, 100), (160, 170))
        self.assertEqual([s.label for s in self.window.canvas.shapes], ['Bridge'] * 2)
        self.assertTrue(self.window.canvas.drawing())
        self.assertEqual(self.window._activeDraw, 'normal')
        self.select('Container')
        self.assertTrue(self.window.actions.create.isChecked())
        self.window.actions.createRo.trigger()
        self.assertFalse(self.window.actions.create.isChecked())
        self.assertTrue(self.window.actions.createRo.isChecked())
        self.draw((200, 200), (260, 270))
        self.draw((300, 300), (350, 360))
        self.assertEqual([s.label for s in self.window.canvas.shapes[-2:]], ['Container'] * 2)
        self.assertTrue(all(s.isRotated for s in self.window.canvas.shapes[-2:]))
        self.assertTrue(self.window.actions.createRo.isChecked())
        self.assertEqual(self.window.labelList.count(), 4)
        self.window.actions.createRo.trigger()
        self.assertIsNone(self.window._activeDraw)
        self.assertTrue(self.window.canvas.editing())
        self.assertFalse(self.window.actions.createRo.isChecked())

    def test_cancel_partial_and_rename_selected_category(self):
        self.window.labelStore.ensure('旧类别')
        self.window.refreshLabelLibrary()
        self.select('旧类别')
        self.window.actions.create.trigger()
        self.window.canvas.handleDrawing(QPointF(10, 10))
        self.assertIsNotNone(self.window.canvas.current)
        self.window.actions.create.trigger()
        self.assertIsNone(self.window.canvas.current)
        self.assertEqual(len(self.window.canvas.shapes), 0)
        self.window.labelStore.rename('旧类别', '新类别')
        self.window.refreshLabelLibrary()
        self.assertEqual(self.window.selectedCategory()['name'], '新类别')
        self.window.actions.create.trigger()
        self.window.labelStore.delete('新类别')
        self.window.refreshLabelLibrary()
        self.assertIsNone(self.window.selectedCategory())
        self.assertTrue(self.window.canvas.editing())
        self.assertFalse(self.window.actions.create.isChecked())

    def test_reference_classes_seed_once(self):
        reference = str(ROOT / 'data' / 'predefined_classes.txt')
        self.window.seedReferenceClasses(reference)
        self.window.refreshLabelLibrary()
        self.assertEqual(len(self.window.labelStore.entries), 18)
        self.assertEqual(self.window.labelStore.entries[0]['name'], 'Bridge')
        self.assertEqual(self.window.categoryGrid.columnCount(), 2)
        self.assertEqual(self.window.categoryGrid.rowCount(), 9)
        self.window.labelStore.delete('Bridge')
        reopened = LabelStore(str(self.path / 'labels.json'))
        self.assertTrue(reopened.reference_initialized)
        self.assertEqual(len(reopened.entries), 17)

    def test_bilingual_library_and_annotation_migrate_to_english(self):
        legacy = self.path / 'legacy.json'
        legacy.write_text('{"next_id": 8, "reference_initialized": true, "labels": '
                          '[{"id": 7, "name": "桥梁 | Bridge", "color": "#123456"}]}',
                          encoding='utf-8')
        migrated = LabelStore(str(legacy))
        self.assertEqual(migrated.entries, [{'id': 7, 'name': 'Bridge', 'color': '#123456'}])
        self.assertEqual(LabelStore(str(legacy)).entries, migrated.entries)
        self.assertEqual(migrated.ensure('桥梁 | Bridge')['id'], 7)
        self.window.loadLabels([('桥梁 | Bridge', [(10, 10), (50, 10), (50, 50), (10, 50)],
                                 0, False, None, None, False)])
        self.assertEqual(self.window.canvas.shapes[0].label, 'Bridge')
        self.assertEqual(self.window.labelList.item(0).text(), 'Bridge')

    def test_management_keeps_grid_selection_and_stops_when_deleted(self):
        self.window.labelStore.ensure('建筑 | Bridge')
        self.window.refreshLabelLibrary()
        self.select('建筑 | Bridge')
        self.window.actions.create.trigger()
        errors = []

        def interact():
            try:
                dialog = next(d for d in self.window.findChildren(QDialog) if d.isVisible())
                labels = dialog.findChild(QListWidget)
                buttons = {b.text(): b for b in dialog.findChildren(QPushButton)}
                labels.setCurrentRow(0)
                buttons['重命名'].click()
                self.assertEqual(self.window.selectedCategory()['name'], '新类别')
                buttons['颜色'].click()
                self.assertEqual(self.window.categoryGrid.item(0, 0).data(Qt.UserRole + 2), '#abcdef')
                buttons['删除'].click()
                self.assertIsNone(self.window.selectedCategory())
                self.assertTrue(self.window.canvas.editing())
                self.assertFalse(self.window.actions.create.isChecked())
                dialog.accept()
            except Exception as exc:
                errors.append(exc)
                for dialog in self.window.findChildren(QDialog):
                    dialog.reject()

        QTimer.singleShot(0, interact)
        with patch.object(QInputDialog, 'getText', return_value=('新类别', True)), \
             patch.object(QColorDialog, 'getColor', return_value=QColor('#abcdef')):
            self.window.manageLabels()
        self.assertFalse(errors, errors)


if __name__ == '__main__':
    unittest.main()
