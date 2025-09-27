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


class ProgressReader:
    """Read progress information from JSON files."""
    
    def __init__(self, path: Path):
        self.path = path
    
    def read(self) -> dict[str, Any] | None:
        """Read current progress data."""
        if not self.path.exists():
            return None
        
        try:
            with self.path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    
    def get_status(self) -> str:
        """Get current status string."""
        data = self.read()
        if not data:
            return "unknown"
        return data.get("status", "unknown")
    
    def get_progress(self) -> float:
        """Get progress percentage (0-100)."""
        data = self.read()
        if not data:
            return 0.0
        return data.get("progress", 0.0)
    
    def is_complete(self) -> bool:
        """Check if operation is complete."""
        return self.get_status() == "complete"
    
    def is_running(self) -> bool:
        """Check if operation is currently running."""
        return self.get_status() == "running"
