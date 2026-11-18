"""Dauerhafte Speicherung der Gesamtzahl geöffneter Truhen."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path


class ChestStats:
    """Thread-sicherer Zähler, der jede Änderung sofort atomar auf die Platte schreibt."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._total = self._load()

    def _load(self) -> int:
        if not self.path.exists():
            return 0
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return max(0, int(data.get("total", 0)))
        except (OSError, ValueError, TypeError, AttributeError):
            backup = self.path.with_suffix(".broken.json")
            try:
                self.path.replace(backup)
            except OSError:
                pass
            return 0

    def _save(self) -> None:
        payload = {
            "total": self._total,
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    @property
    def total(self) -> int:
        with self._lock:
            return self._total

    @property
    def exists(self) -> bool:
        """False beim allerersten Start (noch kein Zählerstand gespeichert)."""
        return self.path.exists()

    def set(self, value: int) -> int:
        """Setzt den Zählerstand direkt, z. B. als Startwert vor dem ersten Zählen."""
        with self._lock:
            self._total = max(0, int(value))
            self._save()
            return self._total

    def add(self, amount: int = 1) -> int:
        """Addiert amount (darf negativ sein, Ergebnis nie < 0) und gibt den neuen Stand zurück."""
        with self._lock:
            self._total = max(0, self._total + amount)
            self._save()
            return self._total
