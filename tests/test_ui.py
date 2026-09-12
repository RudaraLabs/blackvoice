"""Overlay behaviour that can be checked without a desktop.

These run under the offscreen Qt platform and are skipped entirely when PyQt6
or its shared libraries are unavailable, so the suite still passes on a headless
install that never pulled the UI extra.
"""

from __future__ import annotations

import os

import pytest

# Choose the platform before anything Qt is imported. setdefault is not enough:
# a caller can export QT_QPA_PLATFORM as an empty string, which setdefault
# leaves alone and Qt then reads as "pick whatever the system offers".
if not os.environ.get("QT_QPA_PLATFORM"):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Importing PyQt6 alone succeeds even when Qt's shared libraries are missing -
# it is QtWidgets that pulls in libEGL - so the guard has to name that module.
pytest.importorskip("PyQt6.QtWidgets", reason="PyQt6 or its Qt libraries are unavailable")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from blackvoice.ui.overlay import Overlay, _supports_window_opacity  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------- detection
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


# ---------------------------------------------------------------- behaviour
def _record_opacity(overlay, monkeypatch) -> list:
    calls: list = []
    monkeypatch.setattr(
        type(overlay), "setWindowOpacity",
        lambda self, value: calls.append(value),
    )
    return calls


def test_no_opacity_is_set_when_the_platform_cannot_do_it(app, monkeypatch) -> None:
    """Qt logs a warning on every attempt, which used to flood the journal.

    One activation called setWindowOpacity three times; a tray icon that sits
    there all day turns that into thousands of lines for a 180 ms fade.

    ``_can_fade`` is forced rather than inferred from the ambient platform, so
    the branch is what is under test and not whatever Qt picked on this machine.
    """
    overlay = Overlay(timeout=1.0)
    overlay._can_fade = False
    calls = _record_opacity(overlay, monkeypatch)

    overlay.show_state("listening")
    overlay.show_heard("open firefox")
    overlay.show_reply("Opening firefox.")
    overlay.fade_out()

    assert calls == [], f"opacity was set {len(calls)} times on a platform without it"
    assert not overlay.isVisible()


def test_opacity_is_still_used_where_it_works(app, monkeypatch) -> None:
    """The fade must not be lost on the platforms that do support it."""
    overlay = Overlay(timeout=1.0)
    overlay.hide()
    overlay._can_fade = True
    calls = _record_opacity(overlay, monkeypatch)

    overlay.pop()

    assert calls, "the fade should still start where opacity is supported"


def test_overlay_shows_and_hides_without_the_fade(app) -> None:
    overlay = Overlay(timeout=1.0)
    overlay._can_fade = False

    overlay.pop()
    assert overlay.isVisible()

    overlay.fade_out()
    assert not overlay.isVisible()


def test_setup_state_is_labelled(app) -> None:
    """First run downloads ~90 MB; the card must say why it is not responding."""
    overlay = Overlay(timeout=1.0)
    overlay.show_state("setup")
    assert "downloading" in overlay.state_label.text().lower()
