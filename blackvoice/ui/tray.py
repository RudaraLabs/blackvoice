"""Tray icon and the Qt application entry point.

The engine runs on its own thread and publishes to the event bus. This module
turns those events into Qt signals, which Qt then delivers on the GUI thread -
that queued hop is what makes it safe to touch widgets from here.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Optional

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .. import __version__
from ..app import Engine
from ..config import APP_ATTRIBUTION, APP_TITLE, APP_VENDOR, CONFIG_FILE, LOG_FILE
from ..core.bus import Event, Topic
from .icons import app_icon, tray_icon
from .overlay import Overlay

log = logging.getLogger(__name__)


class BusBridge(QObject):
    """Re-emits bus events as Qt signals on the GUI thread."""

    state = pyqtSignal(str)
    heard = pyqtSignal(str, bool)
    reply = pyqtSignal(str, bool)
    level = pyqtSignal(float)
    error = pyqtSignal(str)

    def attach(self, engine: Engine) -> None:
        engine.bus.subscribe(Topic.STATE, lambda e: self.state.emit(e.get("state", "idle")))
        engine.bus.subscribe(Topic.LEVEL, lambda e: self.level.emit(float(e.get("level", 0.0))))
        engine.bus.subscribe(Topic.ERROR, lambda e: self.error.emit(e.get("message", "")))
        engine.bus.subscribe(Topic.HEARD, self._on_heard)
        engine.bus.subscribe(Topic.REPLY, self._on_reply)

    def _on_heard(self, event: Event) -> None:
        self.heard.emit(event.get("text", ""), bool(event.get("partial", False)))

    def _on_reply(self, event: Event) -> None:
        text = event.get("display") or event.get("speech") or ""
        self.reply.emit(text, bool(event.get("ok", True)))


class TrayApp:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setApplicationName(APP_TITLE)
        self.app.setApplicationDisplayName(APP_TITLE)
        # Without this the desktop cannot match the running process to
        # blackvoice.desktop, so GNOME shows a generic icon - or none at all -
        # in the dock. On Wayland it is the only association that works; on X11
        # it sets WM_CLASS, which StartupWMClass in the .desktop file matches.
        self.app.setDesktopFileName("blackvoice")
        self.app.setApplicationVersion(__version__)
        self.app.setOrganizationName(APP_VENDOR)
        self.app.setWindowIcon(app_icon())
        self.app.setQuitOnLastWindowClosed(False)

        self.overlay = Overlay(timeout=engine.config.ui.overlay_timeout)
        self.overlay.submitted.connect(self._on_typed)

        self.tray = QSystemTrayIcon(tray_icon(), self.app)
        self.tray.setToolTip(f"{APP_TITLE} — ready")
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.setContextMenu(self._build_menu())

        self.bridge = BusBridge()
        self.bridge.attach(engine)
        self.bridge.state.connect(self._on_state, Qt.ConnectionType.QueuedConnection)
        self.bridge.heard.connect(self.overlay.show_heard, Qt.ConnectionType.QueuedConnection)
        self.bridge.reply.connect(self.overlay.show_reply, Qt.ConnectionType.QueuedConnection)
        self.bridge.level.connect(self.overlay.show_level, Qt.ConnectionType.QueuedConnection)
        self.bridge.error.connect(self._on_error, Qt.ConnectionType.QueuedConnection)

    # --------------------------------------------------------------- menu
    def _build_menu(self) -> QMenu:
        menu = QMenu()

        listen = QAction("Listen now", menu)
        listen.triggered.connect(self.engine.activate)
        menu.addAction(listen)

        type_action = QAction("Type a command…", menu)
        type_action.triggered.connect(self.overlay.focus_input)
        menu.addAction(type_action)

        menu.addSeparator()

        new_chat = QAction("Clear AI conversation", menu)
        new_chat.triggered.connect(self.engine.ai_skill.reset)
        menu.addAction(new_chat)

        help_action = QAction("What can I say?", menu)
        help_action.triggered.connect(lambda: self.engine.submit_text("help"))
        menu.addAction(help_action)

        menu.addSeparator()

        settings_action = QAction("Settings…", menu)
        settings_action.triggered.connect(self.open_settings)
        menu.addAction(settings_action)

        config_action = QAction("Edit the config file…", menu)
        config_action.triggered.connect(self._open_config)
        menu.addAction(config_action)

        logs_action = QAction("Open log file…", menu)
        logs_action.triggered.connect(lambda: self._xdg_open(str(LOG_FILE)))
        menu.addAction(logs_action)

        about = QAction("About Black Voice", menu)
        about.triggered.connect(self._about)
        menu.addAction(about)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        return menu

    @staticmethod
    def _xdg_open(path: str) -> None:
        try:
            subprocess.Popen(
                ["xdg-open", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            log.warning("could not open %s", path)

    def open_settings(self) -> None:
        """Open the settings window, reusing it if it is already up."""
        from .settings import SettingsWindow

        existing = getattr(self, "_settings", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return

        self._settings = SettingsWindow(self.engine.config)
        self._settings.saved.connect(self._on_settings_saved)
        self._settings.show()

    def _on_settings_saved(self) -> None:
        # Most of the engine reads its configuration once at startup, so the
        # window tells the user to restart. What can be applied live is.
        self.overlay._timeout_ms = int(self.engine.config.ui.overlay_timeout * 1000)
        log.info("settings reloaded")

    def _open_config(self) -> None:
        self.engine.config.save()  # make sure the file exists before opening it
        self._xdg_open(str(CONFIG_FILE))

    def _about(self) -> None:
        box = QMessageBox()
        box.setWindowIcon(app_icon())
        box.setIconPixmap(app_icon().pixmap(64, 64))
        box.setWindowTitle(f"About {APP_TITLE}")
        # The vendor line is deliberately small and grey: it should sit under
        # the product name, not compete with it.
        box.setText(
            f"<b style='font-size:15px'>{APP_TITLE}</b> "
            f"<span style='color:#7A7A7A'>{__version__}</span>"
            f"<br><span style='color:#7A7A7A;letter-spacing:1px'>"
            f"{APP_ATTRIBUTION.upper()}</span>"
        )
        box.setInformativeText(
            "An offline-first voice assistant for Linux.\n\n"
            f"Wake word: say “Black”\n"
            f"Hotkey:    {self.engine.config.wake.hotkey}\n\n"
            f"{self.engine.describe()}\n\n"
            f"© 2026 {APP_VENDOR} · MIT licence"
        )
        box.exec()

    # ------------------------------------------------------------- events
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.engine.activate()

    def _on_typed(self, text: str) -> None:
        # Engine work can block; keep it off the GUI thread's critical path.
        QTimer.singleShot(0, lambda: self.engine.submit_text(text))

    def _on_state(self, state: str) -> None:
        self.tray.setIcon(tray_icon(listening=state == "listening"))
        self.tray.setToolTip(f"{APP_TITLE} — {state}")
        self.overlay.show_state(state)

    def _on_error(self, message: str) -> None:
        if not message:
            return
        log.error("%s", message)
        if self.tray.supportsMessages():
            self.tray.showMessage(APP_TITLE, message, app_icon(), 6000)
        else:
            self.overlay.show_reply(message, ok=False)

    # -------------------------------------------------------------- run
    def run(self) -> int:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning(
                "no system tray on this desktop; the overlay still works "
                "but there will be no icon"
            )
        else:
            self.tray.show()

        self.engine.start(background=True)
        try:
            return self.app.exec()
        finally:
            self.engine.stop()

    def quit(self) -> None:
        self.engine.stop()
        self.app.quit()


def run_ui(engine: Optional[Engine] = None) -> int:
    engine = engine or Engine()
    return TrayApp(engine).run()
