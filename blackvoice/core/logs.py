"""Logging setup: colourised console plus a rotating file in the cache dir."""

from __future__ import annotations

import logging
import logging.handlers
import sys

from ..config import CACHE_DIR, LOG_FILE

_COLOURS = {
    "DEBUG": "\033[38;5;244m",
    "INFO": "\033[38;5;255m",
    "WARNING": "\033[38;5;214m",
    "ERROR": "\033[38;5;203m",
    "CRITICAL": "\033[48;5;203;38;5;231m",
}
_RESET = "\033[0m"


class _ConsoleFormatter(logging.Formatter):
    def __init__(self, colour: bool) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)-22s %(message)s", "%H:%M:%S")
        self.colour = colour

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if not self.colour:
            return text
        return f"{_COLOURS.get(record.levelname, '')}{text}{_RESET}"


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(_ConsoleFormatter(colour=sys.stderr.isatty()))
    root.addHandler(console)

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s %(message)s")
        )
        root.addHandler(file_handler)
    except OSError:
        # Read-only home, container, whatever - console logging still works.
        pass

    # These libraries are chatty at DEBUG and add nothing useful.
    for noisy in ("urllib3", "requests", "comtypes", "sounddevice"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
