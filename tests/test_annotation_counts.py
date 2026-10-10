from unittest.mock import patch
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QStyleOptionViewItem, QScrollArea
from PyQt5.QtTest import QTest
from shape import Shape


def prepare(window):
    window.image = QImage(640, 480, QImage.Format_RGB32)
    window.image.fill(Qt.black)
    window.canvas.loadPixmap(QPixmap.fromImage(window.image))
    window.filePath = 'counts.png'
    window.toggleActions(True)
    window.setZoom(100)
    QApplication.processEvents()


def add(window, label):
    window.pushUndo()
    shape = Shape(label)
    shape.isRotated = False
    shape.points = [QPointF(50, 50), QPointF(150, 50), QPointF(150, 120), QPointF(50, 120)]
    shape.close()
    window.canvas.shapes.append(shape)
    window.addLabel(shape)
    window.setDirty()
    return shape


def numbers(window):
    return [(window.labelList.item(row).text(), window.labelList.item(row).data(Qt.UserRole + 8))
            for row in range(window.labelList.count())]


def test_category_sequences_and_dynamic_total_add_delete_undo_redo(window):
    prepare(window)
    shapes = [add(window, label) for label in ('A', 'A', 'A', 'B')]
    assert numbers(window) == [('A', 1), ('A', 2), ('A', 3), ('B', 1)]
    assert window.annotationCountLabel.text() == '标注框总数：4'
    assert window._annotationCounts == {'A': 3, 'B': 1}
    window.labelList.setCurrentRow(1)
    window.deleteSelectedShape()
    assert numbers(window) == [('A', 1), ('A', 2), ('B', 1)]
    assert window.annotationCountLabel.text() == '标注框总数：3'
    window.undoAnnotation()
    assert numbers(window) == [('A', 1), ('A', 2), ('A', 3), ('B', 1)]
    assert window.annotationCountLabel.text() == '标注框总数：4'
    window.redoAnnotation()
    assert window._annotationCounts == {'A': 2, 'B': 1}
    add(window, 'B')
    assert numbers(window)[-1] == ('B', 2)
    window.resetState()
    assert window.annotationCountLabel.text() == '标注框总数：0'
    assert not window._annotationCounts


def test_relabel_and_copy_update_category_counts_without_changing_locks(window):
    prepare(window)
    first = add(window, 'A')
    second = add(window, 'B')
    assert first.identifier != second.identifier
    window.labelList.setCurrentRow(0)
    window.toggleSelectedLocks()
    window.pushUndo()
    window.shapesToItems[first].setText('B')
    assert numbers(window) == [('B', 1), ('B', 2)]
    assert window._annotationCounts == {'B': 2}
    assert '第 1 / 2 个' in window.shapesToItems[first].toolTip()
    window.undoAnnotation()
    assert numbers(window) == [('A', 1), ('B', 1)]
    assert window.canvas.shapes[0].locked
    window.canvas.selectShape(window.canvas.shapes[1])
    window.copySelectedShape()
    assert numbers(window) == [('A', 1), ('B', 1), ('B', 2)]
    assert window.annotationCountLabel.text() == '标注框总数：3'


def test_reloading_hidden_boxes_and_delegate_use_per_category_sequences(window):
    prepare(window)
    shapes = [add(window, name) for name in ('A', 'B', 'A')]
    for shape in shapes:
        window.shapesToItems[shape].setCheckState(Qt.Unchecked)
    assert window.annotationCountLabel.text() == '标注框总数：3'
    raw = [(s.label, [(p.x(), p.y()) for p in s.points], s.direction, s.isRotated, None, None, False)
           for s in shapes]
    window.loadLabels(raw)
    assert numbers(window) == [('A', 1), ('B', 1), ('A', 2)]
    option = QStyleOptionViewItem()
    window.labelList.itemDelegate().initStyleOption(option, window.labelList.model().index(2, 0))
    assert option.text == '#002 · A'
    window.loadLabels([])
    assert window.annotationCountLabel.text() == '标注框总数：0'


def test_caption_visibility_follows_box_and_never_changes_coordinates(window):
    prepare(window)
    shape = add(window, 'Bridge')
    points = list(shape.points)
    with patch.object(shape, 'paintLabel', wraps=shape.paintLabel) as draw:
        window.canvas.grab()
        assert draw.called
        draw.reset_mock()
        window.shapesToItems[shape].setCheckState(Qt.Unchecked)
        window.canvas.grab()
        assert not draw.called
        window.shapesToItems[shape].setCheckState(Qt.Checked)
        window.setZoom(200)
        QApplication.processEvents()
        window.canvas.grab()
        assert draw.called
    assert shape.points == points
    assert window._annotationCounts == {'Bridge': 1}


def test_total_stays_visible_below_scrolling_controls_in_narrow_dock(window):
    prepare(window)
    add(window, 'A')
    window.resizeDocks([window.dock], [200], Qt.Horizontal)
    QTest.qWait(20)
    panel = window.dock.findChild(QScrollArea)
    panel.verticalScrollBar().setValue(panel.verticalScrollBar().maximum())
    footer = window.annotationCountLabel
    assert footer.isVisible()
    assert window.dock.rect().contains(footer.mapTo(window.dock, footer.rect().center()))
    assert footer.parentWidget() is window.dock.widget()
    panel.verticalScrollBar().setValue(0)
    assert window.dock.rect().contains(footer.mapTo(window.dock, footer.rect().center()))
