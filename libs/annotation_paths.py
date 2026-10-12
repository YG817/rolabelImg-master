"""Keep annotation paths unique and check their source before overwriting."""
import hashlib
import json
import os
from xml.etree import ElementTree


def identity(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def file_revision(path):
    """Identify the file that failed to load, rather than banning its name."""
    try:
        stat = os.stat(path)
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns
    except OSError:
        return None


def empty_annotation_placeholder(path):
    """An empty file/container has no existing annotation records to lose."""
    try:
        with open(path, 'rb') as stream:
            content = stream.read(65)
        return len(content) <= 64 and content.decode('utf-8-sig').strip() in ('', '{}', '[]')
    except (OSError, UnicodeError):
        return False


def annotation_path(image, suffix, savedir=None, image_root=None, images=()):
    image = os.path.abspath(image)
    directory = os.path.dirname(image)
    destination = os.path.abspath(savedir or directory)
    relative = os.path.basename(image)
    if savedir and image_root:
        root = os.path.abspath(image_root)
        try:
            inside = os.path.commonpath([identity(image), identity(root)]) == identity(root)
        except ValueError:
            inside = False
        if inside:
            relative = os.path.relpath(image, root)
        else:
            token = hashlib.sha256(identity(image).encode('utf-8')).hexdigest()[:12]
            return os.path.join(destination, relative + '--' + token + suffix)
    elif savedir and identity(destination) != identity(directory):
        # Single-image sessions have no shared root. Include source identity so
        # opening another directory later cannot overwrite this image's labels.
        token = hashlib.sha256(identity(image).encode('utf-8')).hexdigest()[:12]
        relative = os.path.basename(image) + '--' + token
        return os.path.join(destination, relative + suffix)
    stem = os.path.splitext(identity(image))[0]
    collisions = {identity(p) for p in images
                  if os.path.splitext(identity(p))[0] == stem}
    if len(collisions) > 1:
        return os.path.join(destination, relative + suffix)
    return os.path.join(destination, os.path.splitext(relative)[0] + suffix)


def annotation_source(path):
    """Return an absolute source path when the annotation records one."""
    if path.lower().endswith('.json'):
        with open(path, encoding='utf-8') as stream:
            data = json.load(stream)
        if not isinstance(data, dict) or not isinstance(data.get('images'), list):
            raise ValueError('COCO 标注缺少有效的 images 列表')
        images = data['images']
        if not all(isinstance(image, dict) for image in images):
            raise ValueError('COCO 影像信息格式无效')
        source = images[0].get('source_path') if len(images) == 1 else None
        if source is not None and not isinstance(source, str):
            raise ValueError('COCO source_path 必须是文本路径')
        return source if source and os.path.isabs(source) else None
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise ValueError('标注 XML 内容损坏：%s' % exc) from exc
    source = root.findtext('path')
    return source if source and os.path.isabs(source) else None


def safe_to_overwrite(path, image, loaded_paths=()):
    if not os.path.isfile(path):
        return True
    # A newly created empty placeholder has no annotations to preserve.
    if empty_annotation_placeholder(path):
        return True
    source = annotation_source(path)
    if source:
        return identity(source) == identity(image)
    # Older annotations may lack a full path. Only overwrite a file explicitly
    # loaded for this image, rather than guessing who owns an existing file.
    return identity(path) in {identity(p) for p in loaded_paths}
