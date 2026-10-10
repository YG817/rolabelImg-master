"""Persistent label names, stable COCO category IDs and colors."""
import colorsys
import json
import os

from PyQt5.QtCore import QStandardPaths
from PyQt5.QtGui import QColor
from coco_io import atomic_json


LEGACY_REFERENCE_NAMES = {
    '桥梁 | Bridge': 'Bridge',
    '集装箱 | Container': 'Container',
    '停车场 | ParkingLot': 'ParkingLot',
    '铁路站 | RailwayYard': 'RailwayYard',
    '油罐 | OilTank': 'OilTank',
    '输电站 | TransTower': 'TransTower',
    '光伏阵列 | PVArray': 'PVArray',
    '货船 | CargoShip': 'CargoShip',
    '高层住宅 | Residence': 'Residence',
    '操场 | Playground': 'Playground',
    '别墅区 | VillaArea': 'VillaArea',
    '五角大楼 | Pentagon': 'Pentagon',
    '园区场棚 | YardShed': 'YardShed',
    '体育场 | Stadium': 'Stadium',
    '军舰 | warship': 'warship',
    '吊装码头 | LiftingWharf': 'LiftingWharf',
    '箱式养殖 | ConAquaculture': 'ConAquaculture',
    '机场 | airport': 'airport',
}


def canonical_label_name(name):
    """Translate only the shipped bilingual labels, leaving user labels intact."""
    return LEGACY_REFERENCE_NAMES.get(name, name)


class LabelStore:
    def __init__(self, path=None):
        self.path = path or os.path.join(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation), 'labels.json')
        self.entries = []
        self.next_id = 1
        self.reference_initialized = False
        if os.path.exists(self.path):
            with open(self.path, encoding='utf-8') as stream:
                data = json.load(stream)
            self.entries = data['labels']
            self.next_id = max(data.get('next_id', 1), max([e['id'] for e in self.entries] or [0]) + 1)
            self.reference_initialized = data.get('reference_initialized', False)
            migrated = False
            names = {entry['name'] for entry in self.entries}
            for entry in list(self.entries):
                old = entry['name']
                new = canonical_label_name(old)
                if new == old:
                    continue
                if new in names:
                    self.entries.remove(entry)
                else:
                    entry['name'] = new
                    names.add(new)
                names.discard(old)
                migrated = True
            if migrated:
                self.save()

    def save(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        atomic_json(self.path, dict(next_id=self.next_id, labels=self.entries,
                                    reference_initialized=self.reference_initialized))

    def ensure(self, name):
        name = canonical_label_name(name.strip())
        if not name:
            raise ValueError('Label must not be empty')
        for entry in self.entries:
            if entry['name'] == name:
                return entry
        r, g, b = colorsys.hsv_to_rgb((self.next_id * 0.61803398875) % 1, 0.72, 0.95)
        entry = dict(id=self.next_id, name=name, color=QColor(int(r * 255), int(g * 255), int(b * 255)).name())
        self.next_id += 1
        self.entries.append(entry)
        self.save()
        return entry

    def rename(self, old, new):
        new = new.strip()
        if not new or any(e['name'] == new and e['name'] != old for e in self.entries):
            raise ValueError('Label is empty or already exists')
        next(e for e in self.entries if e['name'] == old)['name'] = new
        self.save()

    def delete(self, name):
        self.entries = [e for e in self.entries if e['name'] != name]
        self.save()

    def categories(self):
        return [dict(id=e['id'], name=e['name'], supercategory='') for e in self.entries]
