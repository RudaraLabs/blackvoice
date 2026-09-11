"""Guard rails for anything that reaches a shell.

Voice recognition is fuzzy, so a misheard word must never turn into a destructive
command. Every shell request passes through :class:`ShellGuard`, which either
refuses it outright, or marks it as needing an explicit confirmation from the
user before it runs.
"""

from __future__ import annotations

import logging
import re
import shlex
from dataclasses import dataclass
from enum import Enum
from typing import List, Pattern

from ..config import SafetyConfig

log = logging.getLogger(__name__)


class Verdict(Enum):
    ALLOW = "allow"           # safe, read-only-ish command
    CONFIRM = "confirm"       # plausible but needs a human yes
    BLOCK = "block"           # never run this


@dataclass
class Decision:
    verdict: Verdict
    reason: str = ""

    @property
    def blocked(self) -> bool:
        return self.verdict is Verdict.BLOCK

    @property
    def needs_confirmation(self) -> bool:
        return self.verdict is Verdict.CONFIRM


#: Commands that only read state. These skip the confirmation prompt.
READ_ONLY = {
    "ls", "pwd", "whoami", "date", "cal", "uptime", "df", "du", "free",
    "cat", "head", "tail", "wc", "file", "stat", "find", "grep", "which",
    "uname", "hostname", "id", "ps", "top", "env", "printenv", "echo",
    "lsblk", "lscpu", "lsusb", "ip", "ping", "tree", "history", "git",
}

#: Shell metacharacters that let one command smuggle in another.
_CHAINING = re.compile(r"[;&|`$(){}<>]|\|\||&&")


class ShellGuard:
    def __init__(self, cfg: SafetyConfig) -> None:
        self.cfg = cfg
        self._blocked: List[Pattern[str]] = []
        for pattern in cfg.blocked_patterns:
            try:
                self._blocked.append(re.compile(pattern, re.IGNORECASE))
            except re.error as exc:
                log.warning("skipping invalid safety pattern %r: %s", pattern, exc)

    def check(self, command: str) -> Decision:
        cmd = (command or "").strip()
        if not cmd:
            return Decision(Verdict.BLOCK, "empty command")

        for pattern in self._blocked:
            if pattern.search(cmd):
                log.warning("blocked command %r (matched %s)", cmd, pattern.pattern)
                return Decision(
                    Verdict.BLOCK,
                    "That command is on the blocked list, so I will not run it.",
                )

        if _CHAINING.search(cmd):
            return Decision(
                Verdict.CONFIRM,
                "This chains several commands together.",
            )

        try:
            parts = shlex.split(cmd)
        except ValueError:
            return Decision(Verdict.BLOCK, "I could not parse that command safely.")

        if not parts:
            return Decision(Verdict.BLOCK, "empty command")

        program = parts[0].rsplit("/", 1)[-1]

        if program in {"sudo", "doas", "pkexec", "su"}:
            return Decision(
                Verdict.BLOCK,
                "I do not run commands as root. Please run that one yourself.",
            )

        if program in READ_ONLY:
            return Decision(Verdict.ALLOW, "read-only command")

        if self.cfg.confirm_shell:
            return Decision(Verdict.CONFIRM, f"{program!r} can change things on your system.")

        return Decision(Verdict.ALLOW, "confirmation disabled in config")

    def truncate(self, text: str) -> str:
        limit = self.cfg.max_output_chars
        if len(text) <= limit:
            return text
        return text[:limit] + f"\n... [{len(text) - limit} more characters truncated]"
