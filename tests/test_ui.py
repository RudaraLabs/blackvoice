"""Overlay behaviour that can be checked without a desktop.

These run under the offscreen Qt platform and are skipped entirely when PyQt6
is not installed, so the suite still passes on a headless install that never
pulled the UI extra.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PyQt6", reason="the UI extra is not installed")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from blackvoice.ui.overlay import Overlay, _supports_window_opacity  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize(
    "platform,expected",
    [
        ("xcb", True),
        ("windows", True),
        ("cocoa", True),
        ("wayland", False),
        ("wayland-egl", False),
        ("offscreen", False),
        ("minimal", False),
        ("vnc", False),
        ("eglfs", False),
    ],
)
def test_platforms_without_opacity_are_recognised(monkeypatch, platform, expected) -> None:
    monkeypatch.setattr(
        "blackvoice.ui.overlay.QGuiApplication.platformName",
        staticmethod(lambda: platform),
    )
    assert _supports_window_opacity() is expected


def test_overlay_never_sets_opacity_where_it_is_unsupported(app, monkeypatch) -> None:
    """Qt logs a warning on every attempt, which used to flood the journal.

    One activation called setWindowOpacity three times; a tray icon that sits
    there all day turns that into thousands of lines.
    """
    overlay = Overlay(timeout=1.0)
    assert overlay._can_fade is False, "offscreen should not claim opacity support"

    calls = []
    monkeypatch.setattr(
        type(overlay), "setWindowOpacity",
        lambda self, value: calls.append(value),
    )

    overlay.show_state("listening")
    overlay.show_heard("open firefox")
    overlay.show_reply("Opening firefox.")
    overlay.fade_out()

    assert calls == [], f"opacity was set {len(calls)} times on a platform without it"
    assert not overlay.isVisible()


def test_overlay_still_shows_and_hides_without_the_fade(app) -> None:
    overlay = Overlay(timeout=1.0)
    overlay.pop()
    assert overlay.isVisible()
    overlay.fade_out()
    assert not overlay.isVisible()


def test_setup_state_is_labelled(app) -> None:
    """First run downloads ~90 MB; the card must say why it is not responding."""
    overlay = Overlay(timeout=1.0)
    overlay.show_state("setup")
    assert "downloading" in overlay.state_label.text().lower()
