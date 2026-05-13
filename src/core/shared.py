class MemorySharedDict:
    def __init__(self, manager):
        # Shared lock and dict
        object.__setattr__(self, "_lock", manager.Lock())
        object.__setattr__(self, "_dict", manager.dict())

    # Helper context
    def _acquire(self):
        self._lock.acquire()

    def _release(self):
        self._lock.release()

    # Dictionary-like item access
    def __getitem__(self, key):
        self._acquire()
        try:
            return self._dict[key]
        finally:
            self._release()

    def __setitem__(self, key, value):
        self._acquire()
        try:
            self._dict[key] = value
        finally:
            self._release()

    # Dictionary methods
    def get(self, key, default=None):
        self._acquire()
        try:
            return self._dict.get(key, default)
        finally:
            self._release()

    def keys(self):
        self._acquire()
        try:
            return list(self._dict.keys())
        finally:
            self._release()

    def items(self):
        self._acquire()
        try:
            return list(self._dict.items())
        finally:
            self._release()

    def values(self):
        self._acquire()
        try:
            return list(self._dict.values())
        finally:
            self._release()

    def __contains__(self, key):
        self._acquire()
        try:
            return key in self._dict
        finally:
            self._release()

    def __delitem__(self, key):
        self._acquire()
        try:
            del self._dict[key]
        finally:
            self._release()

    # Attribute-style access (optional)
    def __getattr__(self, name):
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"{name} not found")

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            self[name] = value