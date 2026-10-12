"""Notify geometry/index caches when the existing list-based API is edited."""
import weakref


class TrackedList(list):
    def __init__(self, values, changed):
        super().__init__(values)
        self._changed = weakref.WeakMethod(changed)

    def notify(self):
        callback = self._changed()
        if callback is not None:
            callback()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.notify()

    def __delitem__(self, key):
        super().__delitem__(key)
        self.notify()

    def append(self, value):
        super().append(value)
        self.notify()

    def extend(self, values):
        super().extend(values)
        self.notify()

    def insert(self, index, value):
        super().insert(index, value)
        self.notify()

    def pop(self, index=-1):
        result = super().pop(index)
        self.notify()
        return result

    def remove(self, value):
        super().remove(value)
        self.notify()

    def clear(self):
        super().clear()
        self.notify()

    def reverse(self):
        super().reverse()
        self.notify()

    def sort(self, *args, **kwargs):
        super().sort(*args, **kwargs)
        self.notify()

    def __iadd__(self, values):
        self.extend(values)
        return self

    def __imul__(self, count):
        super().__imul__(count)
        self.notify()
        return self
