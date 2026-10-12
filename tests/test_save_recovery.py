import json
import pytest
from pathlib import Path
from test_interactive_editing import prepare, add


def setup_image(window, tmp_path):
    window.resetState()
    prepare(window)
    window.filePath = str(tmp_path / 'scene.tif')
    window.defaultSaveDir = None
    window.dirname = None
    add(window, [(100, 100), (200, 100), (200, 200), (100, 200)])
    return tmp_path / 'scene.json'


def test_removed_failed_json_can_be_recreated_in_image_folder(window, tmp_path, monkeypatch):
    path = setup_image(window, tmp_path)
    path.write_text('{broken', encoding='utf-8')
    monkeypatch.setattr(window, 'errorMessage', lambda *a: None)
    assert not window.loadAnnotation(str(path))
    original = path.read_bytes()
    window.setDirty()
    assert not window.saveFile()
    assert path.read_bytes() == original
    path.unlink()
    assert window.saveFile()
    assert json.loads(path.read_text(encoding='utf-8'))['images'][0]['source_path'] == window.filePath
    assert not window._failedAnnotationPaths and not window.dirty


@pytest.mark.parametrize('placeholder', ['', '{}', '[]'])
def test_recreated_empty_json_and_save_as_in_same_folder(window, tmp_path, monkeypatch, placeholder):
    path = setup_image(window, tmp_path)
    path.write_text('{broken', encoding='utf-8')
    monkeypatch.setattr(window, 'errorMessage', lambda *a: None)
    assert not window.loadAnnotation(str(path))
    path.unlink()
    path.write_text(placeholder, encoding='utf-8')
    assert window._saveFile(str(path))
    path.unlink()
    assert window._saveFile(str(path))
    assert len(json.loads(path.read_text(encoding='utf-8'))['annotations']) == 1


def test_loaded_valid_json_deleted_does_not_block_resaving(window, tmp_path):
    path = setup_image(window, tmp_path)
    assert window.saveFile()
    assert window.loadAnnotation(str(path))
    path.unlink()
    window.setDirty()
    assert window.saveFile()
    assert path.exists()


def test_repair_and_other_image_guard_remain_active(window, tmp_path, monkeypatch):
    path = setup_image(window, tmp_path)
    assert window.saveFile()
    valid = path.read_text(encoding='utf-8')
    path.write_text('{broken', encoding='utf-8')
    monkeypatch.setattr(window, 'errorMessage', lambda *a: None)
    assert not window.loadAnnotation(str(path))
    path.write_text(valid, encoding='utf-8')
    assert window.saveFile()
    data = json.loads(valid)
    data['images'][0]['source_path'] = str(tmp_path / 'another.tif')
    path.write_text(json.dumps(data), encoding='utf-8')
    assert not window._saveFile(str(path))
    assert json.loads(path.read_text(encoding='utf-8'))['images'][0]['source_path'].endswith('another.tif')


def test_initial_empty_placeholder_is_safe_to_save(window, tmp_path, monkeypatch):
    path = setup_image(window, tmp_path)
    path.touch()
    monkeypatch.setattr(window, 'errorMessage', lambda *a: None)
    assert not window.loadAnnotation(str(path))
    assert window.saveFile()
