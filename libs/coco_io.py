"""COCO detection + polygon segmentation, with lossless rectangle metadata."""
import json
import os
import tempfile
from box_geometry import validate_box


def atomic_json(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    fd, temporary = tempfile.mkstemp(prefix='.annotations-', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_coco(path, shapes, image_path, size, categories, verified=False):
    category_ids = {entry['name']: entry['id'] for entry in categories}
    annotations = []
    for index, shape in enumerate(shapes, 1):
        points = shape['points']
        xs, ys = zip(*points)
        area = validate_box(points)
        annotations.append(dict(id=index, image_id=1, category_id=category_ids[shape['label']],
                                bbox=[min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)],
                                segmentation=[[coordinate for p in points for coordinate in p]],
                                area=area, iscrowd=0,
                                attributes=dict(isRotated=shape['isRotated'],
                                                direction=shape['direction'], difficult=bool(shape['difficult']))))
    atomic_json(path, dict(images=[dict(id=1, file_name=os.path.basename(image_path),
                                      source_path=os.path.abspath(image_path),
                                      width=size[0], height=size[1], verified=verified)],
                           annotations=annotations, categories=categories))


def read_coco(path, image_path):
    with open(path, encoding='utf-8') as stream:
        data = json.load(stream)
    images = [im for im in data['images']
              if os.path.basename(im['file_name']) == os.path.basename(image_path)]
    if len(images) != 1:
        raise ValueError('COCO must contain exactly one matching image: ' + os.path.basename(image_path))
    image = images[0]
    categories = {c['id']: c['name'] for c in data['categories']}
    shapes = []
    for annotation in data['annotations']:
        if annotation['image_id'] != image['id']:
            continue
        attrs = annotation.get('attributes', {})
        polygons = annotation.get('segmentation', [])
        if isinstance(polygons, list) and len(polygons) == 1 and len(polygons[0]) == 8:
            points = list(zip(polygons[0][::2], polygons[0][1::2]))
        else:
            x, y, w, h = annotation['bbox']
            points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        import math
        inferred = math.atan2(points[1][1] - points[0][1], points[1][0] - points[0][0]) % (2 * math.pi)
        shapes.append((categories[annotation['category_id']], points,
                       attrs.get('direction', inferred), attrs.get('isRotated', bool(inferred)),
                       None, None, attrs.get('difficult', False)))
    return shapes, image.get('verified', False)
