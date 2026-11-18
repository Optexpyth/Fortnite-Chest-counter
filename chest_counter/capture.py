"""Bildschirmaufnahme der Scan-Region mit mss."""
from __future__ import annotations

from typing import Sequence

import numpy as np


def region_to_pixels(region: Sequence[float], monitor: dict) -> dict:
    """Wandelt eine Region aus Bildschirmanteilen (links, oben, rechts, unten) in mss-Pixelkoordinaten um."""
    left, top, right, bottom = (min(1.0, max(0.0, float(v))) for v in region)
    if right <= left or bottom <= top:
        raise ValueError(f"Ungültige Scan-Region: {list(region)}")
    width, height = monitor["width"], monitor["height"]
    return {
        "left": monitor["left"] + int(left * width),
        "top": monitor["top"] + int(top * height),
        "width": max(1, int((right - left) * width)),
        "height": max(1, int((bottom - top) * height)),
    }


class RegionCapture:
    """Nimmt die Scan-Region auf. Muss in dem Thread erzeugt werden, der auch grab() aufruft."""

    def __init__(self, region: Sequence[float], monitor_index: int = 1):
        import mss

        self._sct = mss.mss()
        monitors = self._sct.monitors
        if not 0 <= monitor_index < len(monitors):
            monitor_index = 1 if len(monitors) > 1 else 0
        self.box = region_to_pixels(region, monitors[monitor_index])

    def grab(self) -> np.ndarray:
        """Liefert die Region als BGRA-Array."""
        return np.asarray(self._sct.grab(self.box))

    def close(self) -> None:
        self._sct.close()
