"""The Black Voice engine.

Owns the audio loop and the wake-word state machine, and turns transcripts into
skill calls. The UI never talks to the audio layer directly - it subscribes to
the event bus and calls :meth:`Engine.activate` / :meth:`Engine.submit_text`.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from .audio.mic import Microphone, MicrophoneUnavailable
from .audio.stt import HybridSTT, Transcript
from .audio.tts import Speaker
from .audio.wake import WakeWordDetector, strip_wake_word
from .config import Config, ensure_dirs
from .core.bus import EventBus, Topic
from .nlu.intents import Intent
from .nlu.router import Router
from .skills.ai import AISkill
from .skills.base import Reply, SkillContext, SkillRegistry
from .skills.control import ControlSkill
from .skills.files import FilesSkill
from .skills.system import SystemSkill
from .skills.terminal import TerminalSkill
from .skills.utils import UtilsSkill

log = logging.getLogger(__name__)


class State:
    IDLE = "idle"           # waiting for the wake word
    LISTENING = "listening"  # capturing a command
    THINKING = "thinking"    # running a skill
    SPEAKING = "speaking"
    ASLEEP = "asleep"        # wake word ignored until the user asks for it


class PendingConfirmation:
    """A skill asked a yes/no question and is waiting for the answer."""

    #: a confirmation goes stale after this many seconds
    TTL = 30.0

    def __init__(self, prompt: str, on_confirm: Callable[[], Reply]) -> None:
        self.prompt = prompt
        self.on_confirm = on_confirm
        self.created = time.monotonic()

    @property
    def expired(self) -> bool:
        return time.monotonic() - self.created > self.TTL


class Engine:
    def __init__(self, config: Optional[Config] = None) -> None:
        ensure_dirs()
        self.config = config or Config.load()
        self.bus = EventBus()

        self.speaker = Speaker(self.config.voice)
        self.stt = HybridSTT(self.config.speech, self.config.audio)
        self.router = Router()

        self.skills = SkillRegistry()
        ctx = SkillContext(config=self.config, bus=self.bus, say=self.say)
        self.ai_skill = AISkill(ctx)
        self.utils_skill = UtilsSkill(ctx)
        for skill in (
            ControlSkill(ctx),
            SystemSkill(ctx),
            FilesSkill(ctx),
            TerminalSkill(ctx),
            self.ai_skill,
            self.utils_skill,
        ):
            self.skills.register(skill)

        self.wake = WakeWordDetector(
            self.config.wake,
            self.config.model_path("en"),
            self.config.audio.sample_rate,
        )

        self._state = State.IDLE
        self._running = threading.Event()
        self._activate = threading.Event()
        self._pending: Optional[PendingConfirmation] = None
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------- state
    @property
    def state(self) -> str:
        return self._state

    def _set_state(self, state: str) -> None:
        if state == self._state:
            return
        self._state = state
        log.debug("state -> %s", state)
        self.bus.publish(Topic.STATE, state=state)

    def say(self, text: str) -> None:
        """Speak and show a line of text."""
        if not text:
            return
        self.speaker.say(text)

    # -------------------------------------------------------- public api
    def activate(self) -> None:
        """Start listening now, as if the wake word had been heard."""
        self._activate.set()

    def wake_up(self) -> None:
        if self._state == State.ASLEEP:
            self._set_state(State.IDLE)

    def start(self, background: bool = True) -> None:
        """Start the audio loop. With ``background`` it returns immediately."""
        if self._running.is_set():
            return
        self._running.set()
        if background:
            self._thread = threading.Thread(target=self._loop, name="engine", daemon=True)
            self._thread.start()
        else:
            self._loop()

    def stop(self) -> None:
        self._running.clear()
        self._activate.set()  # unblock the loop if it is waiting
        self.utils_skill.shutdown()
        self.speaker.shutdown()
        self.bus.publish(Topic.SHUTDOWN)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    # -------------------------------------------------------- audio loop
    def _loop(self) -> None:
        self.stt.load()
        wake_ready = self.wake.load()
        if not wake_ready:
            log.warning(
                "wake word is unavailable - trigger Black Voice from the tray icon "
                "or your desktop's %s shortcut",
                self.config.wake.hotkey,
            )

        try:
            mic = Microphone(self.config.audio).open()
        except MicrophoneUnavailable as exc:
            log.error("%s", exc)
            self.bus.publish(Topic.ERROR, message=str(exc))
            self._running.clear()
            return

        self._set_state(State.IDLE)
        try:
            while self._running.is_set():
                if self._activate.is_set():
                    self._activate.clear()
                    self.wake_up()
                    self._converse(mic)
                    continue

                block = mic.read(timeout=0.3)
                if block is None:
                    continue

                if self._state == State.ASLEEP or not wake_ready:
                    continue

                if self.wake.feed(block):
                    log.info("wake word detected")
                    self._converse(mic)
        finally:
            mic.close()
            self._set_state(State.IDLE)

    def _converse(self, mic: Microphone) -> None:
        """One activation: listen, understand, act, answer."""
        self.speaker.stop()
        mic.drain()
        self._set_state(State.LISTENING)
        if self.config.wake.chime:
            self._chime()

        transcript = self.stt.listen_once(
            mic,
            on_partial=lambda text: self.bus.publish(Topic.HEARD, text=text, partial=True),
            on_level=lambda level: self.bus.publish(Topic.LEVEL, level=level),
        )

        if not transcript:
            log.debug("nothing heard")
            self._set_state(State.IDLE)
            return

        text = strip_wake_word(transcript.text, self.config.wake.phrases)
        log.info("heard %r (%.2f, %s)", text, transcript.confidence, transcript.source)
        self.bus.publish(
            Topic.HEARD,
            text=text,
            partial=False,
            confidence=transcript.confidence,
            source=transcript.source,
        )

        if not text:
            self._set_state(State.IDLE)
            return

        reply = self.process(text)
        self._deliver(reply)

        # The microphone heard our own voice; throw that away.
        self.speaker.wait_until_idle(timeout=20.0)
        mic.drain()
        self.wake.reset()
        if self._state != State.ASLEEP:
            self._set_state(State.IDLE)

    def _chime(self) -> None:
        """A short beep so the user knows we are listening."""
        player = self.skills.get("system")
        if player is None:
            return
        for argv in (["canberra-gtk-play", "-i", "message"], ["pw-play", "/usr/share/sounds/freedesktop/stereo/message.oga"]):
            if player.which(argv[0]):
                player.spawn(argv)
                return

    # ------------------------------------------------------ text pipeline
    def submit_text(self, text: str) -> Reply:
        """Handle a typed command (CLI text mode, or the overlay's input box)."""
        self.bus.publish(Topic.HEARD, text=text, partial=False, source="text")
        reply = self.process(text)
        self._deliver(reply)
        return reply

    def process(self, text: str) -> Reply:
        """Route ``text`` to a skill and return its reply."""
        with self._lock:
            pending = self._pending
            if pending and pending.expired:
                log.debug("pending confirmation expired")
                self._pending = pending = None

            if pending is not None:
                answered = self._answer_confirmation(text, pending)
                if answered is not None:
                    self._pending = None
                    return answered

        self._set_state(State.THINKING)
        intent = self.router.route(text)
        reply = self.skills.dispatch(intent)

        if reply.confirm and reply.on_confirm:
            with self._lock:
                self._pending = PendingConfirmation(reply.confirm, reply.on_confirm)
            self.bus.publish(Topic.CONFIRM, prompt=reply.confirm)

        if reply.data.get("sleep"):
            self._set_state(State.ASLEEP)

        return reply

    def _answer_confirmation(
        self, text: str, pending: PendingConfirmation
    ) -> Optional[Reply]:
        """Return a reply when ``text`` is a yes or a no, else ``None``."""
        intent = self.router.route(text)
        if intent.skill != "control":
            return None
        if intent.action == "affirm":
            log.info("confirmed: %s", pending.prompt)
            self._set_state(State.THINKING)
            return pending.on_confirm()
        if intent.action in {"deny", "cancel"}:
            log.info("declined: %s", pending.prompt)
            return Reply("Cancelled.")
        return None

    def _deliver(self, reply: Reply) -> None:
        if not reply.speech and not reply.display:
            return
        self.bus.publish(
            Topic.REPLY,
            speech=reply.speech,
            display=reply.display,
            ok=reply.ok,
            data=reply.data,
        )
        if reply.speech:
            self._set_state(State.SPEAKING)
            self.speaker.say(reply.speech)

    # -------------------------------------------------------- diagnostics
    def describe(self) -> str:
        """A short report of what is and is not working - used by ``doctor``."""
        self.stt.load()
        self.wake.load()
        lines = [
            f"Speech mode      {self.config.speech.mode}",
            f"Offline models   {len(self.stt.recognizers)} loaded"
            + (" (none - run 'blackvoice setup')" if not self.stt.has_offline else ""),
            f"Wake word        {'ready' if self.wake.ready else 'unavailable'}",
            f"Text to speech   {self.speaker.engine}",
            f"AI backend       {self.config.ai.provider}",
        ]
        return "\n".join(lines)
