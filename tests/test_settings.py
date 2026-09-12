"""The settings window.

The form is generated from the Config dataclass, so the tests that matter are
about that generation staying honest: every field reachable, every value
round-tripping to disk, and the AI on/off switch meaning what it says.
"""

from __future__ import annotations

import dataclasses
import json
import os

import pytest

if not os.environ.get("QT_QPA_PLATFORM"):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

pytest.importorskip("PyQt6.QtWidgets", reason="PyQt6 or its Qt libraries are unavailable")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from blackvoice.config import Config  # noqa: E402
from blackvoice.ui import settings as st  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, monkeypatch):
    # The save path pops a modal; tests must not block on it.
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    return st.SettingsWindow(Config())


# ------------------------------------------------------------------ coverage
def test_every_config_field_is_editable(window) -> None:
    """A field added to the config must not silently miss the window.

    This is the whole reason the form is generated rather than hand-written.
    """
    config = Config()
    missing = []
    for section, _title in st.SECTIONS:
        sub = getattr(config, section)
        for field in dataclasses.fields(sub):
            key = f"{section}.{field.name}"
            if key not in window._editors:
                missing.append(key)
    assert not missing, f"not editable from the settings window: {missing}"


def test_every_section_has_a_tab(window) -> None:
    titles = {window.tabs.tabText(i) for i in range(window.tabs.count())}
    assert titles == {title for _s, title in st.SECTIONS}


def test_choice_fields_offer_the_real_options(window) -> None:
    for key, options in st.CHOICES.items():
        widget = window._editors[key].widget
        listed = [widget.itemText(i) for i in range(widget.count())]
        assert listed == options, f"{key} offers {listed}"


# ----------------------------------------------------------------- AI switch
def test_turning_ai_off_sets_provider_to_none(window) -> None:
    window.ai_enabled.setChecked(False)
    assert window._collect()["ai.provider"] == "none"


def test_turning_ai_back_on_restores_a_working_provider(window) -> None:
    window.ai_enabled.setChecked(False)
    window._editors["ai.provider"].value = "none"
    window.ai_enabled.setChecked(True)
    # "none" while enabled would be a contradiction; it falls back to the default.
    assert window._collect()["ai.provider"] == "ollama"


def test_ai_fields_are_greyed_out_when_disabled(window) -> None:
    window.ai_enabled.setChecked(False)
    assert not window._editors["ai.ollama_model"].widget.isEnabled()
    window.ai_enabled.setChecked(True)
    assert window._editors["ai.ollama_model"].widget.isEnabled()


def test_disabling_ai_says_commands_are_unaffected(window) -> None:
    window.ai_enabled.setChecked(False)
    assert "commands are unaffected" in window.note.text().lower()


# -------------------------------------------------------------- round trip
def test_edits_reach_the_config_file(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    path = tmp_path / "config.json"

    # Redirect where Config.save() defaults to, rather than patching the
    # method - patching it and then calling it re-enters the patch.
    monkeypatch.setattr("blackvoice.config.CONFIG_FILE", path)

    config = Config()
    window = st.SettingsWindow(config)

    window._editors["ai.ollama_model"].value = "qwen2.5:1.5b"
    window._editors["ai.ollama_url"].value = "http://192.168.1.50:11434"
    window._editors["speech.mode"].value = "offline"
    window._editors["wake.phrases"].value = ["hey black", "ok black"]
    window._editors["audio.silence_threshold"].value = 0.008

    window._save()

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["ai"]["ollama_model"] == "qwen2.5:1.5b"
    assert written["ai"]["ollama_url"] == "http://192.168.1.50:11434"
    assert written["speech"]["mode"] == "offline"
    assert written["wake"]["phrases"] == ["hey black", "ok black"]

    # And the file must load back into a Config that agrees.
    reloaded = Config.load(path)
    assert reloaded.speech.mode == "offline"
    assert reloaded.wake.phrases == ["hey black", "ok black"]
    assert reloaded.audio.silence_threshold == pytest.approx(0.008)


def test_restore_defaults_resets_the_widgets(window, monkeypatch) -> None:
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    window._editors["speech.mode"].value = "online"
    window._restore_defaults()
    assert window._editors["speech.mode"].value == Config().speech.mode


def test_api_key_is_masked(window) -> None:
    """The config file is world-readable on most systems."""
    from PyQt6.QtWidgets import QLineEdit

    widget = window._editors["ai.api_key"].widget
    assert widget.echoMode() == QLineEdit.EchoMode.Password


def test_help_text_exists_for_the_fields_people_change(window) -> None:
    for key in ("ai.provider", "speech.mode", "wake.phrases",
                "audio.silence_threshold", "safety.confirm_shell"):
        assert st.HELP.get(key), f"{key} has no explanation"
