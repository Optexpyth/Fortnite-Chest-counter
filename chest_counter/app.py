"""Verdrahtet Erkennung, Hotkeys, Speicherung und Overlay."""
from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path

from . import config as cfgmod
from .detector import (
    ChestStateMachine,
    TemplateMatcher,
    extract_template,
    load_templates,
    preprocess,
    save_template,
)
from .storage import ChestStats

log = logging.getLogger(__name__)


class DetectionWorker(threading.Thread):
    """Scannt die Scan-Region und meldet geöffnete Truhen über die Event-Queue."""

    def __init__(self, config: dict, templates_path: Path, events: queue.Queue, stats: ChestStats):
        super().__init__(name="detection", daemon=True)
        self.cfg = config["detection"]
        self.interact_key = config["interact_key"]
        self.templates_path = templates_path
        self.events = events
        self.stats = stats
        self.enabled = threading.Event()
        if self.cfg["enabled"]:
            self.enabled.set()
        self.stop_event = threading.Event()
        self.calibrate_request = threading.Event()
        self.matcher = TemplateMatcher(load_templates(templates_path), self.cfg["scales"])
        self.machine = ChestStateMachine(
            open_timeout=float(self.cfg["open_timeout"]),
            cooldown=float(self.cfg["cooldown"]),
            debounce_frames=int(self.cfg["debounce_frames"]),
        )

    def status(self) -> tuple[str, str]:
        """(Art, Text) für das Overlay: 'ok' zeigt nur einen grünen Punkt."""
        if not self.enabled.is_set():
            return "paused", "Auto-Erkennung pausiert (F11)"
        if len(self.matcher) == 0:
            return "warn", "Keine Vorlage – an einer Truhe F9 drücken"
        return "ok", "Auto-Erkennung aktiv"

    def _calibrate(self, capture, threshold: int) -> None:
        binary = preprocess(capture.grab(), threshold)
        template = extract_template(binary)
        if template is None:
            self.events.put(("toast", "Kalibrierung fehlgeschlagen: kein Hinweis gefunden"))
            return
        path = save_template(self.templates_path, template)
        self.matcher.add(template)
        log.info("Neue Vorlage gespeichert: %s (%dx%d)", path, template.shape[1], template.shape[0])
        self.events.put(("toast", f"Vorlage gespeichert ({path.name})"))
        self.events.put(("status", *self.status()))

    def run(self) -> None:
        from .capture import RegionCapture
        from .hotkeys import make_key_checker

        try:
            capture = RegionCapture(self.cfg["region"], int(self.cfg["monitor"]))
            key_down = make_key_checker(self.interact_key)
        except Exception as exc:  # noqa: BLE001
            log.exception("Erkennung konnte nicht gestartet werden")
            self.events.put(("status", "warn", f"Erkennung aus: {exc}"))
            return

        threshold = int(self.cfg["brightness_threshold"])
        match_threshold = float(self.cfg["match_threshold"])
        interval = 1.0 / max(1, int(self.cfg["fps"]))
        log.info("Scan-Region: %s", capture.box)

        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                if self.calibrate_request.is_set():
                    self.calibrate_request.clear()
                    self._calibrate(capture, threshold)
                elif self.enabled.is_set() and len(self.matcher):
                    score = self.matcher.best_score(preprocess(capture.grab(), threshold))
                    now = time.monotonic()
                    if self.machine.update(now, score >= match_threshold, key_down()):
                        total = self.stats.add(1)
                        log.info("Truhe erkannt (Score %.2f) – gesamt %d", score, total)
                        self.events.put(("total", total, True))
                else:
                    self.machine.reset()
            except Exception:  # noqa: BLE001 – Erkennung soll nie das Programm beenden
                log.exception("Fehler in der Erkennung")
                time.sleep(1.0)
            self.stop_event.wait(max(0.0, interval - (time.monotonic() - started)))
        capture.close()


class App:
    def __init__(self, initial_value: int | None = None):
        self.data_path = cfgmod.data_dir()
        self.config = cfgmod.load_config()
        self.stats = ChestStats(self.data_path / "stats.json")
        self.first_run = not self.stats.exists and initial_value is None
        if initial_value is not None:
            self.stats.set(initial_value)
        self.events: queue.Queue = queue.Queue()
        self.detector = DetectionWorker(self.config, cfgmod.templates_dir(self.data_path), self.events, self.stats)
        self.overlay = None

    # ---------- Hotkey-Aktionen (laufen im keyboard-Thread) ----------
    def _increment(self) -> None:
        self.events.put(("total", self.stats.add(1), True))

    def _decrement(self) -> None:
        self.events.put(("total", self.stats.add(-1), False))

    def _toggle_detection(self) -> None:
        if self.detector.enabled.is_set():
            self.detector.enabled.clear()
        else:
            self.detector.enabled.set()
        self.events.put(("status", *self.detector.status()))

    def _calibrate(self) -> None:
        self.detector.calibrate_request.set()

    # ---------- UI-Thread ----------
    def _save_overlay_settings(self, values: dict) -> None:
        self.config["overlay"].update(values)
        cfgmod.save_config(self.config)
        log.info("Overlay-Einstellungen gespeichert: %s", values)

    def _ask_start_value(self, first_run: bool = False) -> None:
        if first_run:
            title = "Startwert festlegen"
            prompt = "Wie viele Truhen hast du schon geöffnet,\nbevor du mit dem Zählen anfängst?"
        else:
            title = "Zählerstand setzen"
            prompt = "Neuer Zählerstand (Gesamtzahl geöffneter Truhen):"

        def done(value: int | None) -> None:
            if value is None:
                if first_run:
                    self.stats.set(0)
                return
            total = self.stats.set(value)
            log.info("Zählerstand manuell gesetzt: %d", total)
            self.overlay.set_total(total)
            self.overlay.toast(f"Zählerstand auf {total} gesetzt")

        self.overlay.ask_value(title, prompt, self.stats.total, done)

    def _process_events(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                return
            kind = event[0]
            if kind == "total":
                self.overlay.set_total(event[1], flash=event[2])
            elif kind == "status":
                self.overlay.set_status(event[1], event[2])
            elif kind == "scale":
                self.overlay.change_scale(event[1])
            elif kind == "toast":
                self.overlay.toast(event[1])
            elif kind == "set_value":
                self._ask_start_value()
            elif kind == "move":
                moving = self.overlay.toggle_move_mode()
                self.overlay.toast("Ziehen = verschieben · Mausrad/Ecke = Größe · F10 = fertig" if moving else "Position & Größe gespeichert")
            elif kind == "quit":
                self.shutdown()
                return

    def shutdown(self) -> None:
        from .hotkeys import unhook_all

        unhook_all()
        self.detector.stop_event.set()
        if self.overlay:
            self.overlay.close()

    def run(self) -> None:
        from .hotkeys import register_hotkeys
        from .overlay import Overlay

        self.overlay = Overlay(self.config, self._save_overlay_settings)
        self.overlay.set_total(self.stats.total)
        self.overlay.set_status(*self.detector.status())

        actions = {
            "increment": self._increment,
            "decrement": self._decrement,
            "set_value": lambda: self.events.put(("set_value",)),
            "calibrate": self._calibrate,
            "move_overlay": lambda: self.events.put(("move",)),
            "toggle_detection": self._toggle_detection,
            "bigger": lambda: self.events.put(("scale", +0.1)),
            "smaller": lambda: self.events.put(("scale", -0.1)),
            "quit": lambda: self.events.put(("quit",)),
        }
        try:
            for warning in register_hotkeys(self.config["hotkeys"], actions):
                self.overlay.toast(warning, 8000)
        except Exception as exc:  # noqa: BLE001
            log.exception("Hotkeys konnten nicht registriert werden")
            self.overlay.toast(f"Hotkeys fehlgeschlagen: {exc}", 10000)

        self.detector.start()
        self.overlay.poll(self._process_events)
        if self.first_run:
            self.overlay.root.after(300, lambda: self._ask_start_value(first_run=True))
        log.info("Gestartet – Gesamtstand %d", self.stats.total)
        try:
            self.overlay.run()
        finally:
            self.detector.stop_event.set()
