
"""VOC I/O uses temporary files; importing this module never rewrites fixtures."""
from pascal_voc_io import PascalVocWriter
from pascal_voc_io import PascalVocReader


def test_voc_write_read_roundtrip(tmp_path):
    path = str(tmp_path / 'test.xml')
    writer = PascalVocWriter('tests', 'test', (512, 512, 1), localImgPath='tests/test.bmp')
    writer.verified = True
    writer.addBndBox(60, 40, 430, 504, 'person', True)
    writer.addBndBox(113, 40, 450, 403, 'face', False)
    writer.save(path)
    reader = PascalVocReader(path)
    shapes = reader.getShapes()
    assert reader.verified
    assert [shape[0] for shape in shapes] == ['person', 'face']
    assert shapes[0][1] == [(60, 40), (430, 40), (430, 504), (60, 504)]
    assert shapes[0][-1] is True and shapes[1][-1] is False
