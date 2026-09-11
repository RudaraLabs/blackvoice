"""Run shell commands dictated by voice.

Everything here goes through :class:`~blackvoice.core.safety.ShellGuard` first.
Read-only commands run straight away; anything that could change the system
needs a spoken "yes"; a short deny-list never runs at all.
"""

from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path

from ..core.safety import ShellGuard
from ..nlu.intents import Intent
from .base import Reply, Skill, SkillContext

log = logging.getLogger(__name__)

#: Words the recogniser produces for shell punctuation.
SPOKEN_SYMBOLS = {
    " dash ": " -",
    " double dash ": " --",
    " slash ": "/",
    " dot ": ".",
    " star ": "*",
    " tilde ": "~",
}


class TerminalSkill(Skill):
    name = "terminal"

    def __init__(self, ctx: SkillContext) -> None:
        super().__init__(ctx)
        self.guard = ShellGuard(ctx.config.safety)

    def handle(self, intent: Intent) -> Reply:
        if intent.action != "run":
            return Reply.error("I do not know that terminal command.")
        return self._do_run(intent)

    # ------------------------------------------------------------- running
    @staticmethod
    def _detranscribe(command: str) -> str:
        """Undo the recogniser's habit of spelling out punctuation."""
        padded = f" {command.strip()} "
        for spoken, symbol in SPOKEN_SYMBOLS.items():
            padded = padded.replace(spoken, symbol)
        return padded.strip()

    def _do_run(self, intent: Intent) -> Reply:
        command = self._detranscribe(intent.slots.get("command", ""))
        if not command:
            return Reply.error("What command should I run?")

        decision = self.guard.check(command)
        if decision.blocked:
            log.warning("refused command %r: %s", command, decision.reason)
            return Reply.error(decision.reason)

        if decision.needs_confirmation:
            return Reply(
                speech=f"Run {command}? {decision.reason} Say yes to confirm.",
                display=f"$ {command}\n\n{decision.reason}",
                confirm=f"Run: {command}",
                on_confirm=lambda: self._execute(command),
            )

        return self._execute(command)

    def _execute(self, command: str) -> Reply:
        try:
            argv = shlex.split(command)
        except ValueError:
            return Reply.error("I could not parse that command safely.")

        # Chained commands were already flagged for confirmation, so a shell is
        # acceptable here - but only because the guard has vetted the string.
        use_shell = len(argv) != len(command.split()) or any(
            ch in command for ch in ";|&><"
        )

        try:
            result = subprocess.run(
                command if use_shell else argv,
                shell=use_shell,
                capture_output=True,
                text=True,
                timeout=self.config.safety.shell_timeout,
                cwd=str(Path.home()),
            )
        except subprocess.TimeoutExpired:
            return Reply.error(
                f"That command took longer than {self.config.safety.shell_timeout:.0f} seconds, "
                "so I stopped it."
            )
        except FileNotFoundError:
            return Reply.error(f"{argv[0]} is not installed.")
        except OSError as exc:
            return Reply.error(f"I could not run that: {exc.strerror}")

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if result.returncode != 0:
            detail = stderr or stdout or f"exit code {result.returncode}"
            return Reply(
                speech="That command failed.",
                display=f"$ {command}\n\n{self.guard.truncate(detail)}",
                ok=False,
                data={"returncode": result.returncode},
            )

        if not stdout:
            return Reply("Done.", display=f"$ {command}\n\n(no output)")

        lines = stdout.splitlines()
        speech = (
            f"Done. {len(lines)} lines of output."
            if len(lines) > 3
            else "Done. " + " ".join(lines)
        )
        return Reply(
            speech=speech,
            display=f"$ {command}\n\n{self.guard.truncate(stdout)}",
            data={"returncode": 0, "lines": len(lines)},
        )
