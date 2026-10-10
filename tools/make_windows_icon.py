"""Convert an existing PNG to Windows ICO without changing the artwork."""
import argparse
from pathlib import Path
from PyQt5.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'icons' / 'expert2.png')
    parser.add_argument('--output', type=Path, default=ROOT / 'icons' / 'roLabelImg.ico')
    args = parser.parse_args()
    image = QImage(str(args.source))
    if image.isNull() or image.width() != image.height() or not 1 <= image.width() <= 256:
        parser.error('Use a square PNG between 1 and 256 pixels')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(args.output), 'ICO'):
        raise RuntimeError('Qt could not write the Windows ICO file')
    print('Windows icon:', args.output)


if __name__ == '__main__':
    main()
