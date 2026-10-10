"""Run inside the frozen client to verify Qt, TIFF, PROJ and annotation I/O."""
import json
from pathlib import Path
import tempfile
import traceback


def smoke_test(report, root):
    result = {'ok': False}
    try:
        import numpy as np
        import ssl
        assert ssl.create_default_context(), 'Python HTTPS runtime missing'
        import rasterio
        from rasterio.transform import from_origin
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtGui import QImage
        import resources
        from lib import newIcon
        from image_loader import read_raster
        from geo_metadata import read_center_coordinates
        from coco_io import save_coco, read_coco
        from pascal_voc_io import PascalVocWriter, PascalVocReader
        import roLabelImg  # Ensure every GUI import works in the bundle.
        app = QApplication.instance() or QApplication([])
        assert not newIcon('app').isNull(), 'Qt icon resources missing'
        assert (root / 'data' / 'predefined_classes.txt').is_file(), 'Class resource missing'
        with tempfile.TemporaryDirectory() as directory:
            image_path = str(Path(directory) / 'sample.tif')
            with rasterio.open(image_path, 'w', driver='GTiff', width=64, height=32, count=1,
                               dtype='uint8', crs='EPSG:4326', transform=from_origin(18, -17, 0.01, 0.01)) as raster:
                raster.write(np.full((1, 32, 64), 100, dtype='uint8'))
            image, size, _ = read_raster(image_path)
            assert not image.isNull() and size == (64, 32)
            assert read_center_coordinates(image_path).get('text'), 'PROJ/coordinate transform failed'
            png = str(Path(directory) / 'sample.png')
            assert image.save(png) and not QImage(png).isNull()
            coco = str(Path(directory) / 'sample.json')
            save_coco(coco, [], image_path, size, [{'id': 1, 'name': 'Bridge', 'supercategory': ''}])
            assert read_coco(coco, image_path)[0] == []
            voc = str(Path(directory) / 'sample.xml')
            writer = PascalVocWriter(directory, 'sample', (32, 64, 1), localImgPath=image_path)
            writer.addBndBox(1, 2, 20, 25, 'Bridge', False)
            writer.save(voc)
            assert len(PascalVocReader(voc).getShapes()) == 1
        result = {'ok': True, 'checks': ['Qt/icons', 'class resources', 'TIFF/GDAL', 'PROJ', 'PNG', 'COCO', 'VOC', 'GUI imports']}
    except Exception:
        result['error'] = traceback.format_exc()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1
