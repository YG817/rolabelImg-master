"""Area editing must select real geometry and remain one undoable operation."""
import math
from PyQt5.QtCore import QPointF, Qt, QEvent
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QMouseEvent
from test_interactive_editing import prepare, add, drag, mouse


def test_region_contains_all_vertices_reverse_drag_and_hidden_boxes(window):
    prepare(window)
    inside = add(window, [(100, 100), (200, 100), (200, 200), (100, 200)])
    tiny = add(window, [(150, 150), (151, 150), (151, 151), (150, 151)])
    partial = add(window, [(240, 240), (340, 240), (340, 340), (240, 340)])
    hidden = add(window, [(120, 120), (140, 120), (140, 140), (120, 140)])
    window.canvas.setShapeVisible(hidden, False)
    window.actions.createRo.trigger()
    window.actions.selectRegion.trigger()
    assert window._activeDraw is None
    assert window.canvas.mode == window.canvas.REGION
    drag(window.canvas, QPointF(300, 300), QPointF(80, 80))
    assert {window.itemsToShapes[i] for i in window.labelList.selectedItems()} == {inside, tiny}
    assert inside.selected and tiny.selected and not partial.selected and not hidden.selected
    assert len(window.canvas.shapes) == 4
    assert not window.dirty and not window._undoStack
    assert window.selectionCountLabel.text() == '已选 2 个'
    assert window.editSelectedButton.isEnabled()
    window.actions.selectRegion.trigger()
    assert window.canvas.editing()


def test_region_append_and_escape_restores_single_box_editing(window):
    prepare(window)
    first = add(window, [(100, 100), (200, 100), (200, 200), (100, 200)])
    second = add(window, [(400, 100), (500, 100), (500, 200), (400, 200)])
    window.actions.selectRegion.trigger()
    drag(window.canvas, QPointF(80, 80), QPointF(220, 220))
    canvas = window.canvas
    for kind, point, button, buttons in ((QEvent.MouseButtonPress, QPointF(380, 80), Qt.LeftButton, Qt.LeftButton),
                                          (QEvent.MouseButtonRelease, QPointF(520, 220), Qt.LeftButton, Qt.NoButton)):
        local = (point + canvas.offsetToCenter()) * canvas.scale
        QApplication.sendEvent(canvas, QMouseEvent(kind, local, button, buttons, Qt.ControlModifier))
    assert {window.itemsToShapes[i] for i in window.labelList.selectedItems()} == {first, second}
    from PyQt5.QtTest import QTest
    QTest.keyClick(canvas, Qt.Key_Escape)
    assert canvas.editing() and not window.actions.selectRegion.isChecked()
    mouse(canvas, QEvent.MouseButtonPress, QPointF(150, 150), Qt.LeftButton, Qt.LeftButton)
    mouse(canvas, QEvent.MouseButtonRelease, QPointF(150, 150), Qt.LeftButton, Qt.NoButton)
    assert first.selected and not second.selected
    assert len(window.labelList.selectedItems()) == 1


def test_batch_class_and_rectangle_conversion_skip_locked_and_undo(window):
    prepare(window)
    first = add(window, [(100, 100), (200, 100), (200, 180), (100, 180)], True)
    first.rotate(math.pi / 4)
    rect = first.boundingRect()
    before = [QPointF(p) for p in first.points]
    second = add(window, [(400, 100), (500, 100), (500, 200), (400, 200)])
    second.locked = True
    window.selectRegionAnnotations([first, second])
    assert window.applyAnnotationEdits('CargoShip', 'normal')
    assert first.label == 'CargoShip' and not first.isRotated and first.direction == 0
    assert first.points == [rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()]
    assert second.label == 'Bridge' and not second.isRotated
    assert window._annotationCounts == {'CargoShip': 1, 'Bridge': 1}
    assert window.dirty and len(window._undoStack) == 1
    window.undoAnnotation()
    assert window.canvas.shapes[0].points == before and window.canvas.shapes[0].isRotated
    assert all(s.label == 'Bridge' for s in window.canvas.shapes)
    window.redoAnnotation()
    assert window.canvas.shapes[0].label == 'CargoShip'
    window.selectRegionAnnotations([window.canvas.shapes[0]])
    assert window.applyAnnotationEdits(kind='rotated')
    assert window.canvas.shapes[0].isRotated


def test_region_delete_all_can_be_restored_in_one_undo(window):
    prepare(window)
    first = add(window, [(100, 100), (200, 100), (200, 200), (100, 200)])
    second = add(window, [(400, 100), (500, 100), (500, 200), (400, 200)])
    window.actions.selectRegion.trigger()
    drag(window.canvas, QPointF(50, 50), QPointF(550, 250))
    window.deleteSelectedButton.click()
    assert not window.canvas.shapes and window.labelList.count() == 0
    window.undoAnnotation()
    assert len(window.canvas.shapes) == 2 and window.labelList.count() == 2
    window.redoAnnotation()
    assert not window.canvas.shapes


def test_switching_tools_cancels_partial_region_without_new_annotation(window):
    prepare(window)
    window.actions.selectRegion.trigger()
    mouse(window.canvas, QEvent.MouseButtonPress, QPointF(50, 50), Qt.LeftButton, Qt.LeftButton)
    window.actions.create.trigger()
    assert window.canvas.drawing() and window.canvas._regionStart is None
    assert not window.actions.selectRegion.isChecked()
    assert not window.canvas.shapes


def test_region_shortcut_keeps_existing_center_marker_shortcut(window):
    prepare(window)
    from PyQt5.QtTest import QTest
    window.activateWindow()
    window.canvas.setFocus()
    QApplication.processEvents()
    QTest.keyClick(window.canvas, Qt.Key_B, Qt.ControlModifier)
    assert window.canvas.mode == window.canvas.REGION
    QTest.keyClick(window.canvas, Qt.Key_B, Qt.ControlModifier)
    assert window.canvas.editing()
    before = window.canvas.showCenter
    QTest.keyClick(window.canvas, Qt.Key_B)
    assert window.canvas.showCenter != before
