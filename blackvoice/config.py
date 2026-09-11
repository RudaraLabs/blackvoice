"""Configuration for Black Voice.

Config lives at ``~/.config/blackvoice/config.json`` and is created with sane
defaults on first run. Every value can also be overridden by an environment
variable of the form ``BLACKVOICE_<SECTION>_<KEY>`` (upper case), which is handy
for systemd units and quick experiments.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict, fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

APP_NAME = "blackvoice"
APP_TITLE = "Black Voice"

#: Branding. Defined once here so the vendor line never drifts between the
#: README, the About dialog, the desktop entry and the package metadata.
APP_VENDOR = "Rudra Labs"
APP_ATTRIBUTION = f"A {APP_VENDOR} product"


def _xdg(var: str, fallback: str) -> Path:
    return Path(os.environ.get(var) or Path.home() / fallback)


CONFIG_DIR = _xdg("XDG_CONFIG_HOME", ".config") / APP_NAME
DATA_DIR = _xdg("XDG_DATA_HOME", ".local/share") / APP_NAME
CACHE_DIR = _xdg("XDG_CACHE_HOME", ".cache") / APP_NAME

CONFIG_FILE = CONFIG_DIR / "config.json"
MODELS_DIR = DATA_DIR / "models"
NOTES_FILE = DATA_DIR / "notes.md"
HISTORY_FILE = DATA_DIR / "history.jsonl"
LOG_FILE = CACHE_DIR / "blackvoice.log"


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    block_size: int = 8000
    input_device: Optional[int] = None       # None = system default mic
    #: RMS level (0..1) below which a block counts as silence
    silence_threshold: float = 0.012
    #: stop capturing a command after this many seconds of silence
    silence_timeout: float = 1.2
    #: hard cap on a single command utterance
    max_command_seconds: float = 12.0


@dataclass
class SpeechConfig:
    """Hybrid speech-to-text: Vosk offline first, cloud only as a fallback."""

    #: "hybrid" | "offline" | "online"
    mode: str = "hybrid"
    #: Vosk model folders, resolved under MODELS_DIR when not absolute
    model_en: str = "vosk-model-small-en-us-0.15"
    model_hi: str = "vosk-model-small-hi-0.22"
    #: which language model to load: "en", "hi" or "both"
    language: str = "both"
    #: below this Vosk confidence the hybrid mode retries online
    fallback_confidence: float = 0.55
    #: seconds to wait on the online recogniser before giving up
    online_timeout: float = 6.0
    #: fetch the models on first run when they are not installed yet. They
    #: cannot ship in the distribution packages - a post-install script must
    #: not use the network, and it runs as root while the models belong to a
    #: user - so first run is where this legitimately happens.
    auto_download: bool = True


@dataclass
class WakeConfig:
    enabled: bool = True
    #: any of these spoken words activates the assistant
    phrases: List[str] = field(default_factory=lambda: ["black", "blek", "blak"])
    #: global hotkey shown in the UI (bound by your desktop environment)
    hotkey: str = "Ctrl+Alt+Space"
    #: play a short beep when activated
    chime: bool = True


@dataclass
class VoiceConfig:
    """Text-to-speech output."""

    #: "auto" | "piper" | "espeak" | "pyttsx3" | "none"
    engine: str = "auto"
    rate: int = 165
    volume: float = 0.9
    #: espeak voice ids
    voice_en: str = "en-us"
    voice_hi: str = "hi"
    piper_model: str = ""


@dataclass
class AIConfig:
    """LLM backend for free-form questions."""

    #: "ollama" | "anthropic" | "openai" | "none"
    provider: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    anthropic_model: str = "claude-opus-5"
    openai_model: str = "gpt-4o-mini"
    #: left blank on purpose - read from ANTHROPIC_API_KEY / OPENAI_API_KEY
    api_key: str = ""
    max_tokens: int = 512
    timeout: float = 30.0
    system_prompt: str = (
        "You are Black Voice, a concise Linux desktop assistant. "
        "Answer in at most three short sentences. "
        "If the user speaks Hindi or Hinglish, reply in the same style."
    )


@dataclass
class SafetyConfig:
    """Guard rails for the terminal skill."""

    #: run shell commands only after the user confirms
    confirm_shell: bool = True
    #: commands matching these patterns are refused outright
    blocked_patterns: List[str] = field(
        default_factory=lambda: [
            r"\brm\s+-[a-zA-Z]*[rf]",
            r"\bmkfs(\.|\s)",
            r"\bdd\s+.*of=/dev/",
            r">\s*/dev/sd",
            r":\s*\(\s*\)\s*\{.*\}\s*;\s*:",   # fork bomb, spaced or not
            r"\bchmod\s+-R\s+777\s+/",
            r"\b(shutdown|reboot|halt|poweroff)\b",
            r"\b(curl|wget)\b[^|]*\|\s*(ba|z|k)?sh",
            r"\bmv\s+[^\s]+\s+/dev/null",
            r"\buserdel\b|\bpasswd\b",
        ]
    )
    shell_timeout: float = 20.0
    #: truncate command output shown back to the user
    max_output_chars: int = 2000


@dataclass
class UIConfig:
    #: show the tray icon and popup overlay
    enabled: bool = True
    #: keep the overlay on screen for N seconds after a reply
    overlay_timeout: float = 8.0
    theme: str = "light"
    show_notifications: bool = True


@dataclass
class SkillsConfig:
    #: city for weather, e.g. "Jaipur"
    weather_city: str = ""
    search_url: str = "https://duckduckgo.com/?q={query}"
    #: preferred applications; blank means auto-detect
    browser: str = ""
    terminal: str = ""
    file_manager: str = ""
    editor: str = ""


@dataclass
class Config:
    audio: AudioConfig = field(default_factory=AudioConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)
    wake: WakeConfig = field(default_factory=WakeConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)

    # ------------------------------------------------------------------ paths
    @property
    def models_dir(self) -> Path:
        return MODELS_DIR

    def model_path(self, which: str) -> Path:
        """Absolute path to a Vosk model directory ("en" or "hi")."""
        name = self.speech.model_en if which == "en" else self.speech.model_hi
        p = Path(name).expanduser()
        return p if p.is_absolute() else MODELS_DIR / name

    # ------------------------------------------------------------------- i/o
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, path: Optional[Path] = None) -> Path:
        path = path or CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        path = path or CONFIG_FILE
        cfg = cls()
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                cfg = _merge(cfg, raw)
            except (json.JSONDecodeError, OSError) as exc:
                # A broken config should never stop the assistant from starting.
                print(f"[blackvoice] config unreadable ({exc}); using defaults")
        else:
            cfg.save(path)
        _apply_env(cfg)
        return cfg


def _merge(obj: Any, raw: Dict[str, Any]) -> Any:
    """Recursively overlay ``raw`` onto a dataclass instance, ignoring junk keys."""
    known = {f.name for f in fields(obj)}
    for key, value in raw.items():
        if key not in known:
            continue
        current = getattr(obj, key)
        if is_dataclass(current) and isinstance(value, dict):
            setattr(obj, key, _merge(current, value))
        else:
            setattr(obj, key, value)
    return obj


def _apply_env(cfg: Config) -> None:
    """Support BLACKVOICE_AI_PROVIDER=openai style overrides."""
    for section in fields(cfg):
        sub = getattr(cfg, section.name)
        if not is_dataclass(sub):
            continue
        for f in fields(sub):
            env_key = f"BLACKVOICE_{section.name.upper()}_{f.name.upper()}"
            if env_key not in os.environ:
                continue
            raw = os.environ[env_key]
            try:
                setattr(sub, f.name, _coerce(raw, getattr(sub, f.name)))
            except (TypeError, ValueError):
                print(f"[blackvoice] ignoring bad env value for {env_key}")


def _coerce(raw: str, current: Any) -> Any:
    if isinstance(current, bool):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    if isinstance(current, list):
        return [x.strip() for x in raw.split(",") if x.strip()]
    return raw


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, DATA_DIR, CACHE_DIR, MODELS_DIR):
        d.mkdir(parents=True, exist_ok=True)
