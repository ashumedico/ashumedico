"""Where T-Amp keeps its state: %APPDATA%\\T-Amp on Windows, ~/.config/t-amp elsewhere."""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile

DEFAULTS = {
    "volume": 80,
    "balance": 0,
    "eq_on": False,
    "eq_auto": False,
    "eq_preamp": 0.0,
    "eq_gains": [0.0] * 10,
    "eq_per_track": {},
    "shuffle": False,
    "repeat": False,
    "scale": 0,                 # 0 = pick from the screen size on first run
    "show_eq": False,
    "show_pl": True,
    "shade": False,
    "pl_rows": 4,               # playlist height in 29-px steps beyond the minimum
    "pos": None,                # [x, y] of the main stack
    "search_pos": None,
    "search_size": None,
    "search_kind": "songs",
    "vis_mode": "spectrum",     # spectrum | scope | off
    "vis_thin": False,
    "vis_peaks": True,
    "time_remaining": False,
    "always_on_top": False,
    "media_keys": True,
    "region": "IN",
    "engine_checked": 0,
    "cookies": None,            # YouTube sign-in: None | "browser:firefox" | path to cookies.txt
    "playlist": [],
    "current": -1,
}


def state_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, "T-Amp")
    else:
        path = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "t-amp")
    os.makedirs(path, exist_ok=True)
    return path


class Settings(dict):
    def __init__(self, path: str | None = None):
        super().__init__(copy.deepcopy(DEFAULTS))
        self.path = path or os.path.join(state_dir(), "state.json")
        try:
            with open(self.path, encoding="utf-8") as fh:
                saved = json.load(fh)
            if isinstance(saved, dict):
                self.update({k: v for k, v in saved.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass  # first run, or a damaged file: start from defaults

    def save(self) -> None:
        folder = os.path.dirname(self.path)
        fd, tmp = tempfile.mkstemp(prefix=".state-", suffix=".json", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(dict(self), fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
