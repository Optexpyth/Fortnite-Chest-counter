"""Globale Hotkeys über die keyboard-Bibliothek (funktionieren auch, während Fortnite im Fokus ist)."""
from __future__ import annotations

import logging
from typing import Callable, Union

log = logging.getLogger(__name__)

Key = Union[str, int]

# Scan-Codes für Tasten, die je nach Layout/Bibliothek nicht per Name auflösbar sind.
# "´" ist auf deutschen Tastaturen eine Tottaste – deshalb der Fallback auf den Scan-Code.
FALLBACK_SCAN_CODES: dict[str, int] = {
    "ß": 12,
    "´": 13,
    "`": 13,
    "^": 41,
}


def _key_label(key: Key) -> str:
    return f"Scan-Code {key}" if isinstance(key, int) else str(key)


def register_hotkeys(bindings: dict[str, Key], actions: dict[str, Callable[[], None]]) -> list[str]:
    """Registriert alle Hotkeys. Gibt eine Liste von Warnungen für nicht registrierbare Tasten zurück."""
    import keyboard  # erst hier importieren, damit Tests ohne die Bibliothek laufen

    warnings: list[str] = []
    for name, callback in actions.items():
        key = bindings.get(name)
        if key in (None, ""):
            continue
        try:
            keyboard.add_hotkey(key, callback)
            log.info("Hotkey %s -> %s", _key_label(key), name)
            continue
        except (ValueError, KeyError) as exc:
            fallback = FALLBACK_SCAN_CODES.get(key) if isinstance(key, str) else None
            if fallback is None:
                warnings.append(f"Hotkey '{_key_label(key)}' für {name} ungültig: {exc}")
                log.warning(warnings[-1])
                continue
        try:
            keyboard.add_hotkey(fallback, callback)
            log.info("Hotkey %s (Scan-Code %d) -> %s", key, fallback, name)
        except (ValueError, KeyError) as exc:
            warnings.append(f"Hotkey '{key}' für {name} konnte nicht registriert werden: {exc}")
            log.warning(warnings[-1])
    return warnings


def make_key_checker(key: Key) -> Callable[[], bool]:
    """Liefert eine Funktion, die prüft, ob die Interaktionstaste gerade gedrückt ist."""
    import keyboard

    try:
        keyboard.is_pressed(key)
    except (ValueError, KeyError):
        fallback = FALLBACK_SCAN_CODES.get(key) if isinstance(key, str) else None
        if fallback is None:
            raise
        key = fallback

    def is_down() -> bool:
        try:
            return bool(keyboard.is_pressed(key))
        except (ValueError, KeyError):
            return False

    return is_down


def unhook_all() -> None:
    try:
        import keyboard

        keyboard.unhook_all()
    except Exception:  # noqa: BLE001 – beim Beenden egal
        pass
