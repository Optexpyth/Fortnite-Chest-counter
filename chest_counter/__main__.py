"""Einstieg: python -m chest_counter [--set N] [--show]"""
from __future__ import annotations

import argparse
import logging
import sys

from . import config as cfgmod


def _setup_logging() -> None:
    handlers: list[logging.Handler] = [
        logging.FileHandler(cfgmod.data_dir() / "log.txt", encoding="utf-8"),
    ]
    if sys.stderr is not None:  # bei --noconsole-EXE gibt es kein stderr
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chest_counter", description="Fortnite Chest Counter mit Overlay")
    parser.add_argument("--set", type=int, metavar="N", help="Zählerstand vor dem Start auf N setzen (Startwert)")
    parser.add_argument("--show", action="store_true", help="Nur aktuellen Zählerstand und Datenordner anzeigen")
    args = parser.parse_args(argv)

    if args.set is not None and args.set < 0:
        parser.error("--set muss ≥ 0 sein")

    if args.show:
        from .storage import ChestStats

        stats = ChestStats(cfgmod.data_dir() / "stats.json")
        print(f"Geöffnete Truhen gesamt: {stats.total}")
        print(f"Datenordner: {cfgmod.data_dir()}")
        return 0

    _setup_logging()
    from .app import App

    App(initial_value=args.set).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
