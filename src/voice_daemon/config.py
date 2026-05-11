import yaml
from pathlib import Path


class DaemonConfig:
    def __init__(self):
        self.path = Path.home() / ".config" / "voice-daemon" / "config.yaml"
        self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                self.data = yaml.safe_load(f) or {}
        else:
            self.data = {}
            self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w') as f:
            yaml.dump(self.data, f)

    def get(self, key, default=None):
        keys = key.split('.')
        val = self.data
        for k in keys:
            val = val.get(k, default)
        return val

    @property
    def hotkey(self):
        return self.get('daemon.hotkey', 'Super+v')

    @property
    def output_method(self):
        return self.get('output.method', 'type')