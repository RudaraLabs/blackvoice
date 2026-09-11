"""Skill behaviour that can be exercised without a microphone or a desktop."""

from __future__ import annotations

import pytest

from blackvoice.audio.wake import strip_wake_word
from blackvoice.config import Config
from blackvoice.core.bus import EventBus
from blackvoice.nlu.intents import Intent
from blackvoice.skills.base import Reply, SkillContext, SkillRegistry, Skill
from blackvoice.skills.control import ControlSkill
from blackvoice.skills.utils import UtilsSkill


@pytest.fixture
def ctx() -> SkillContext:
    return SkillContext(config=Config(), bus=EventBus())


# ------------------------------------------------------------------ calculator
@pytest.mark.parametrize(
    "expression,expected",
    [
        ("2 + 2", "4"),
        ("12 * 8", "96"),
        ("100 / 4", "25"),
        ("2 ** 10", "1024"),
        ("7 % 3", "1"),
        ("10 x 3", "30"),      # the recogniser writes "x" for "times"
        ("-5 + 8", "3"),
    ],
)
def test_calculator(ctx: SkillContext, expression: str, expected: str) -> None:
    skill = UtilsSkill(ctx)
    reply = skill.handle(Intent("calculate", "utils", "calculate", {"expression": expression}))
    assert reply.ok
    assert expected in reply.speech


def test_calculator_rejects_code(ctx: SkillContext) -> None:
    """The evaluator must never execute names or calls."""
    skill = UtilsSkill(ctx)
    for hostile in ["__import__('os').system('ls')", "open('/etc/passwd')", "x + 1"]:
        reply = skill.handle(Intent("calculate", "utils", "calculate", {"expression": hostile}))
        assert not reply.ok


def test_calculator_divide_by_zero(ctx: SkillContext) -> None:
    skill = UtilsSkill(ctx)
    reply = skill.handle(Intent("calculate", "utils", "calculate", {"expression": "1 / 0"}))
    assert not reply.ok
    assert "zero" in reply.speech.lower()


# ----------------------------------------------------------------------- notes
def test_notes_round_trip(ctx: SkillContext, tmp_path, monkeypatch) -> None:
    notes = tmp_path / "notes.md"
    monkeypatch.setattr("blackvoice.skills.utils.NOTES_FILE", notes)
    skill = UtilsSkill(ctx)

    assert skill.handle(Intent("n", "utils", "note_read", {})).speech.startswith("You have no")

    skill.handle(Intent("n", "utils", "note_add", {"text": "buy milk"}))
    skill.handle(Intent("n", "utils", "note_add", {"text": "call mom"}))

    reply = skill.handle(Intent("n", "utils", "note_read", {}))
    assert "buy milk" in reply.display
    assert "call mom" in reply.display
    assert reply.data["count"] == 2


def test_empty_note_is_rejected(ctx: SkillContext) -> None:
    skill = UtilsSkill(ctx)
    assert not skill.handle(Intent("n", "utils", "note_add", {"text": "  "})).ok


# ---------------------------------------------------------------------- timers
def test_timer_parsing(ctx: SkillContext) -> None:
    skill = UtilsSkill(ctx)
    reply = skill.handle(Intent("t", "utils", "timer", {"amount": "5", "unit": "minute"}))
    assert reply.data["seconds"] == 300
    skill.shutdown()


def test_timer_rejects_absurd_durations(ctx: SkillContext) -> None:
    skill = UtilsSkill(ctx)
    reply = skill.handle(Intent("t", "utils", "timer", {"amount": "99", "unit": "hour"}))
    assert not reply.ok
    skill.shutdown()


def test_timer_without_a_duration(ctx: SkillContext) -> None:
    skill = UtilsSkill(ctx)
    assert not skill.handle(Intent("t", "utils", "timer", {})).ok
    skill.shutdown()


# ------------------------------------------------------------------ wake word
@pytest.mark.parametrize(
    "heard,expected",
    [
        ("black open firefox", "open firefox"),
        ("Black, open firefox", "open firefox"),
        ("black", ""),
        ("open firefox", "open firefox"),
        ("blackboard is here", "board is here"),  # known trade-off, see the docstring
    ],
)
def test_strip_wake_word(heard: str, expected: str) -> None:
    assert strip_wake_word(heard, ["black", "blek"]) == expected


# ------------------------------------------------------------------- registry
def test_registry_dispatch(ctx: SkillContext) -> None:
    registry = SkillRegistry()
    registry.register(ControlSkill(ctx))
    reply = registry.dispatch(Intent("help", "control", "help"))
    assert reply.ok
    assert "Black Voice" in reply.display


def test_registry_unknown_skill(ctx: SkillContext) -> None:
    registry = SkillRegistry()
    reply = registry.dispatch(Intent("x", "nope", "nope"))
    assert not reply.ok


def test_registry_survives_a_broken_skill(ctx: SkillContext) -> None:
    class Exploding(Skill):
        name = "boom"

        def handle(self, intent: Intent) -> Reply:
            raise RuntimeError("kaboom")

    registry = SkillRegistry()
    registry.register(Exploding(ctx))
    reply = registry.dispatch(Intent("x", "boom", "anything"))
    assert not reply.ok
    assert "went wrong" in reply.speech


def test_reply_display_defaults_to_speech() -> None:
    assert Reply(speech="hello").display == "hello"
    assert Reply(speech="hi", display="HI").display == "HI"
