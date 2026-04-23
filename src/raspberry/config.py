import yaml
from threading import Lock

class DotDict:
    def __init__(self, data):
        for key, value in (data or {}).items():
            if isinstance(value, dict):
                value = DotDict(value)
            self.__dict__[key] = value

    def __getattr__(self, item):
        raise AttributeError(f"Config key '{item}' not found")

    def to_dict(self):
        return self.__dict__

class Config:
    _instance = None
    _lock = Lock()

    def __new__(cls, config_path="config.local.yml"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._load(config_path)
        return cls._instance

    def _load(self, config_path):
        with open(config_path, "r") as f:
            raw = yaml.safe_load(f) or {}
            self._data = DotDict(raw)

    def __getattr__(self, item):
        return getattr(self._data, item)
    
    @staticmethod
    def instance(cls):
        return cls()