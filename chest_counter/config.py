"""Konfiguration: Standardwerte + config.json im Datenordner."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "FortniteChestCounter"

DEFAULT_CONFIG: dict[str, Any] = {
    # Tastennamen der "keyboard"-Bibliothek oder Scan-Codes (Zahl).
    # Deutsche Tastatur: "´" (Taste links neben Backspace) = +1, "ß" = -1.
    "hotkeys": {
        "increment": "´",
        "decrement": "ß",
        "set_value": "f6",
        "calibrate": "f9",
        "move_overlay": "f10",
        "toggle_detection": "f11",
        "quit": "ctrl+shift+f12",
    },
    # Taste, mit der du in Fortnite interagierst (Truhe öffnen)
    "interact_key": "e",
    "detection": {
        "enabled": True,
        # Scan-Region als Anteil der Bildschirmgröße (links, oben, rechts, unten)
        "region": [0.48, 0.45, 0.78, 0.70],
        "monitor": 1,
        "fps": 15,
        "brightness_threshold": 200,
        "match_threshold": 0.75,
        # Sekunden nach dem Tastendruck, in denen der Hinweis verschwinden muss
        "open_timeout": 2.0,
        "cooldown": 1.5,
        # Anzahl aufeinanderfolgender Frames zur Entprellung
        "debounce_frames": 2,
        # Vorlagen werden für die Suche auf diese Skalen gestreckt (Auflösungsunterschiede)
        "scales": [1.0],
    },
    "overlay": {
        "x": 40,
        "y": 40,
        "font_family": "Segoe UI",
        "font_size": 28,
        "color": "#FFD34D",
        "flash_color": "#5CFF7A",
        "shadow_color": "#000000",
        "label": "Truhen",
    },
}


def data_dir() -> Path:
    """Ordner für config.json, stats.json, Vorlagen und Log."""
    base = os.environ.get("APPDATA")
    path = Path(base) / APP_NAME if base else Path.home() / f".{APP_NAME.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def templates_dir(base: Path | None = None) -> Path:
    path = (base or data_dir()) / "templates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Lädt die Konfiguration. Fehlende Werte werden mit Standardwerten ergänzt
    und die Datei wird (neu) geschrieben, damit der Nutzer alle Optionen sieht."""
    path = path or data_dir() / "config.json"
    user: dict[str, Any] = {}
    if path.exists():
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Kaputte Datei sichern statt sie stillschweigend zu überschreiben
            path.replace(path.with_suffix(".broken.json"))
            user = {}
    config = _deep_merge(DEFAULT_CONFIG, user)
    save_config(config, path)
    return config


def save_config(config: dict[str, Any], path: Path | None = None) -> None:
    path = path or data_dir() / "config.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
