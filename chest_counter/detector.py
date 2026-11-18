"""Bildverarbeitung und Zustandsautomat für die Truhen-Erkennung.

Bewusst ohne Abhängigkeit von Bildschirmaufnahme oder Tastatur, damit alles
mit synthetischen Bildern getestet werden kann.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

# Mindestanzahl heller Pixel, damit ein Zuschnitt als Vorlage taugt
MIN_TEMPLATE_PIXELS = 30


def preprocess(frame: np.ndarray, brightness_threshold: int) -> np.ndarray:
    """BGR/BGRA/Graustufen → Binärbild (0/255): nur helle Pixel (weißer UI-Text) bleiben."""
    if frame.ndim == 3:
        code = cv2.COLOR_BGRA2GRAY if frame.shape[2] == 4 else cv2.COLOR_BGR2GRAY
        gray = cv2.cvtColor(frame, code)
    else:
        gray = frame
    _, binary = cv2.threshold(gray, brightness_threshold, 255, cv2.THRESH_BINARY)
    return binary


def extract_template(binary: np.ndarray, pad: int = 6) -> np.ndarray | None:
    """Schneidet ein Binärbild auf die Bounding-Box der hellen Pixel zu (+Rand).

    Gibt None zurück, wenn zu wenig helle Pixel vorhanden sind (kein Hinweis sichtbar).
    """
    points = cv2.findNonZero(binary)
    if points is None or len(points) < MIN_TEMPLATE_PIXELS:
        return None
    x, y, w, h = cv2.boundingRect(points)
    height, width = binary.shape[:2]
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(width, x + w + pad), min(height, y + h + pad)
    return binary[y0:y1, x0:x1].copy()


class TemplateMatcher:
    """Sucht gespeicherte Vorlagen in einem Binärbild."""

    def __init__(self, templates: Iterable[np.ndarray] = (), scales: Iterable[float] = (1.0,)):
        self.scales = [float(s) for s in scales] or [1.0]
        self._templates: list[np.ndarray] = []
        for template in templates:
            self.add(template)

    def add(self, template: np.ndarray) -> None:
        for scale in self.scales:
            if scale == 1.0:
                scaled = template
            else:
                size = (max(1, round(template.shape[1] * scale)), max(1, round(template.shape[0] * scale)))
                scaled = cv2.resize(template, size, interpolation=cv2.INTER_NEAREST)
            if cv2.countNonZero(scaled) >= MIN_TEMPLATE_PIXELS:
                self._templates.append(scaled)

    def __len__(self) -> int:
        return len(self._templates)

    def best_score(self, binary: np.ndarray) -> float:
        """Höchster Übereinstimmungswert (0..1) über alle Vorlagen."""
        bright = cv2.countNonZero(binary)
        best = 0.0
        for template in self._templates:
            th, tw = template.shape[:2]
            if th > binary.shape[0] or tw > binary.shape[1]:
                continue
            # Schnellabbruch: deutlich weniger helle Pixel als die Vorlage → kann nicht passen.
            # Verhindert außerdem Scheintreffer auf (fast) einfarbigen Bildern.
            if bright < 0.5 * cv2.countNonZero(template):
                continue
            result = cv2.matchTemplate(binary, template, cv2.TM_CCOEFF_NORMED)
            result = np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)
            best = max(best, float(result.max()))
        return min(best, 1.0)


def load_templates(directory: Path) -> list[np.ndarray]:
    templates = []
    for file in sorted(directory.glob("*.png")):
        image = cv2.imread(str(file), cv2.IMREAD_GRAYSCALE)
        if image is not None:
            _, binary = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
            templates.append(binary)
    return templates


def save_template(directory: Path, template: np.ndarray) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    index = 1
    while (directory / f"chest_{index}.png").exists():
        index += 1
    path = directory / f"chest_{index}.png"
    cv2.imwrite(str(path), template)
    return path


class State(Enum):
    IDLE = "idle"          # kein Truhen-Hinweis sichtbar
    PROMPT = "prompt"      # Hinweis sichtbar, noch nicht interagiert
    SEARCHING = "searching"  # Interaktionstaste gedrückt, warte auf Verschwinden des Hinweises


@dataclass
class ChestStateMachine:
    """Entscheidet anhand von (Zeit, Hinweis sichtbar, Taste gedrückt), wann eine Truhe geöffnet wurde.

    Gezählt wird, wenn der Hinweis verschwindet, nachdem die Interaktionstaste
    gedrückt wurde – und zwar innerhalb von ``open_timeout`` Sekunden nach dem
    Tastendruck, während die Taste noch gehalten wird oder höchstens
    ``release_grace`` Sekunden vorher losgelassen wurde.
    """

    open_timeout: float = 2.0
    cooldown: float = 1.5
    debounce_frames: int = 2
    release_grace: float = 0.6

    state: State = field(default=State.IDLE, init=False)
    _stable_visible: bool = field(default=False, init=False)
    _raw_visible: bool = field(default=False, init=False)
    _raw_run: int = field(default=0, init=False)
    _raw_run_start: float = field(default=0.0, init=False)
    _press_time: float = field(default=0.0, init=False)
    _last_key_down: float = field(default=float("-inf"), init=False)
    _cooldown_until: float = field(default=float("-inf"), init=False)

    def reset(self) -> None:
        self.state = State.IDLE
        self._stable_visible = False
        self._raw_run = 0

    def _debounce(self, now: float, visible: bool) -> tuple[bool, float]:
        """Gibt (stabil sichtbar, Zeitpunkt der letzten Änderung des Rohsignals) zurück."""
        if visible == self._raw_visible:
            self._raw_run += 1
        else:
            self._raw_visible = visible
            self._raw_run = 1
            self._raw_run_start = now
        if self._raw_run >= max(1, self.debounce_frames):
            self._stable_visible = self._raw_visible
        return self._stable_visible, self._raw_run_start

    def update(self, now: float, prompt_visible: bool, key_down: bool) -> bool:
        """Verarbeitet einen Frame. Gibt True zurück, wenn genau jetzt eine Truhe gezählt wird."""
        if key_down:
            self._last_key_down = now
        visible, changed_at = self._debounce(now, prompt_visible)

        if now < self._cooldown_until:
            self.state = State.IDLE
            return False

        if self.state is State.IDLE:
            if visible:
                self.state = State.PROMPT

        if self.state is State.PROMPT:
            if not visible:
                self.state = State.IDLE
            elif key_down:
                self.state = State.SEARCHING
                self._press_time = now
            return False

        if self.state is State.SEARCHING:
            if not visible:
                # Zeitpunkt, an dem der Hinweis wirklich verschwand (vor der Entprellung)
                gone_at = changed_at
                in_time = gone_at - self._press_time <= self.open_timeout
                key_recent = gone_at - self._last_key_down <= self.release_grace or key_down
                self.state = State.IDLE
                if in_time and key_recent:
                    self._cooldown_until = now + self.cooldown
                    return True
                return False
            if now - self._press_time > self.open_timeout:
                # Hinweis ist noch da – Öffnen wurde abgebrochen
                self.state = State.PROMPT
        return False
