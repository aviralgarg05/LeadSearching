from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any


class ProgressWriter:
    def __init__(self, path: Path):
        self.path = path
        self._last_write = 0.0

    def update(self, payload: dict[str, Any], force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_write < 0.5:  # throttle
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp.replace(self.path)
        self._last_write = now
