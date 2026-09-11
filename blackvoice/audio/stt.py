"""Hybrid speech-to-text.

Offline Vosk is the default path: it is fast, private and works with no network.
When Vosk comes back unsure (or the model is missing), and the machine is
online, the same audio is retried against a cloud recogniser.

With ``language = "both"`` two Vosk models run over the same buffer and the more
confident transcript wins, which is what makes Hinglish commands work.
"""

from __future__ import annotations

import json
import logging
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..config import AudioConfig, SpeechConfig
from .mic import Microphone, rms_level

log = logging.getLogger(__name__)


@dataclass
class Transcript:
    text: str
    confidence: float = 0.0
    language: str = "en"
    source: str = "vosk"

    def __bool__(self) -> bool:
        return bool(self.text.strip())


# --------------------------------------------------------------------------- #
# Offline: Vosk
# --------------------------------------------------------------------------- #
class VoskRecognizer:
    """One loaded Vosk model plus its streaming recogniser."""

    def __init__(self, model_path: Path, sample_rate: int, language: str) -> None:
        self.language = language
        self.model_path = model_path
        self.sample_rate = sample_rate
        self._rec = None
        self._model = None

    def load(self) -> bool:
        try:
            from vosk import Model, KaldiRecognizer, SetLogLevel
        except ImportError:
            log.warning("vosk is not installed; offline recognition disabled")
            return False

        if not self.model_path.exists():
            log.warning(
                "Vosk model missing at %s - run 'blackvoice setup' to download it",
                self.model_path,
            )
            return False

        SetLogLevel(-1)  # Vosk is extremely noisy on stdout otherwise
        try:
            self._model = Model(str(self.model_path))
            self._rec = KaldiRecognizer(self._model, self.sample_rate)
            self._rec.SetWords(True)
        except Exception:
            log.exception("could not load Vosk model at %s", self.model_path)
            return False

        log.info("loaded Vosk model (%s) from %s", self.language, self.model_path.name)
        return True

    @property
    def ready(self) -> bool:
        return self._rec is not None

    def reset(self) -> None:
        if self._rec is not None:
            # Draining the final result clears the internal state.
            self._rec.FinalResult()

    def accept(self, block: bytes) -> bool:
        """Feed audio; True means an utterance boundary was detected."""
        if self._rec is None:
            return False
        return bool(self._rec.AcceptWaveform(block))

    def partial(self) -> str:
        if self._rec is None:
            return ""
        try:
            return json.loads(self._rec.PartialResult()).get("partial", "")
        except (json.JSONDecodeError, TypeError):
            return ""

    def final(self) -> Transcript:
        if self._rec is None:
            return Transcript("", 0.0, self.language)
        try:
            data = json.loads(self._rec.FinalResult())
        except (json.JSONDecodeError, TypeError):
            return Transcript("", 0.0, self.language)

        text = (data.get("text") or "").strip()
        words = data.get("result") or []
        if words:
            confidence = sum(w.get("conf", 0.0) for w in words) / len(words)
        else:
            confidence = 0.0
        return Transcript(text, confidence, self.language, source="vosk")


# --------------------------------------------------------------------------- #
# Online fallback
# --------------------------------------------------------------------------- #
class OnlineRecognizer:
    """Cloud recogniser used only when the offline pass is unsure."""

    #: tried in order; the first non-empty result wins
    LANG_CODES = {"en": ["en-IN", "en-US"], "hi": ["hi-IN"], "both": ["en-IN", "hi-IN"]}

    def __init__(self, cfg: SpeechConfig, sample_rate: int) -> None:
        self.cfg = cfg
        self.sample_rate = sample_rate
        self._sr = None

    def _engine(self):
        if self._sr is None:
            try:
                import speech_recognition as sr
            except ImportError:
                log.debug("SpeechRecognition is not installed; online fallback disabled")
                return None
            self._sr = sr
        return self._sr

    def transcribe(self, pcm: bytes) -> Optional[Transcript]:
        sr = self._engine()
        if sr is None or not pcm:
            return None

        recogniser = sr.Recognizer()
        recogniser.operation_timeout = self.cfg.online_timeout
        audio = sr.AudioData(pcm, self.sample_rate, 2)

        for code in self.LANG_CODES.get(self.cfg.language, ["en-IN"]):
            try:
                text = recogniser.recognize_google(audio, language=code)
            except sr.UnknownValueError:
                continue
            except sr.RequestError as exc:
                log.warning("online recognition unavailable: %s", exc)
                return None
            except Exception:
                log.debug("online recognition failed for %s", code, exc_info=True)
                continue

            if text and text.strip():
                lang = "hi" if code.startswith("hi") else "en"
                # The free endpoint returns no score; treat a hit as fairly good.
                return Transcript(text.strip(), 0.85, lang, source="online")
        return None


_LAST_NET_CHECK = (0.0, False)


def is_online(timeout: float = 1.0, cache_seconds: float = 20.0) -> bool:
    """Cheap connectivity probe, cached so we do not hammer it per utterance."""
    global _LAST_NET_CHECK
    now = time.monotonic()
    checked_at, result = _LAST_NET_CHECK
    if now - checked_at < cache_seconds:
        return result
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=timeout):
            result = True
    except OSError:
        result = False
    _LAST_NET_CHECK = (now, result)
    return result


# --------------------------------------------------------------------------- #
# The hybrid front end
# --------------------------------------------------------------------------- #
class HybridSTT:
    def __init__(self, speech: SpeechConfig, audio: AudioConfig) -> None:
        self.speech = speech
        self.audio = audio
        self.recognizers: List[VoskRecognizer] = []
        self.online = OnlineRecognizer(speech, audio.sample_rate)
        self._loaded = False

    # ------------------------------------------------------------- loading
    def load(self) -> None:
        if self._loaded or self.speech.mode == "online":
            self._loaded = True
            return

        wanted = ["en", "hi"] if self.speech.language == "both" else [self.speech.language]
        from ..config import Config

        cfg = Config()  # only used for its model_path() helper
        cfg.speech = self.speech

        for lang in wanted:
            rec = VoskRecognizer(cfg.model_path(lang), self.audio.sample_rate, lang)
            if rec.load():
                self.recognizers.append(rec)

        if not self.recognizers and self.speech.mode == "offline":
            log.error(
                "No Vosk model could be loaded and mode is 'offline'. "
                "Run 'blackvoice setup' to download the models."
            )
        self._loaded = True

    @property
    def has_offline(self) -> bool:
        return any(r.ready for r in self.recognizers)

    # --------------------------------------------------------- transcribing
    def transcribe_pcm(self, pcm: bytes) -> Transcript:
        """Recognise a complete utterance held in memory."""
        self.load()
        best = Transcript("", 0.0)

        if self.speech.mode != "online":
            for rec in self.recognizers:
                rec.reset()
                rec.accept(pcm)
                result = rec.final()
                if result and result.confidence > best.confidence:
                    best = result

        if self._should_fall_back(best):
            log.debug(
                "falling back online (offline gave %r @ %.2f)", best.text, best.confidence
            )
            remote = self.online.transcribe(pcm)
            if remote:
                return remote

        return best

    def _should_fall_back(self, offline: Transcript) -> bool:
        if self.speech.mode == "offline":
            return False
        if self.speech.mode == "online":
            return True
        # hybrid
        if not self.has_offline:
            return is_online()
        unsure = (not offline) or offline.confidence < self.speech.fallback_confidence
        return unsure and is_online()

    # ------------------------------------------------------------ streaming
    def listen_once(
        self,
        mic: Microphone,
        on_partial=None,
        on_level=None,
    ) -> Transcript:
        """Record until the speaker goes quiet, then transcribe the whole thing.

        Endpointing is done on the RMS level rather than on Vosk's own utterance
        boundaries, so it behaves the same way when only the online path exists.
        """
        self.load()
        for rec in self.recognizers:
            rec.reset()

        chunks: List[bytes] = []
        seconds_per_block = mic.seconds_per_block
        silent_for = 0.0
        elapsed = 0.0
        heard_speech = False
        last_partial = ""

        while elapsed < self.audio.max_command_seconds:
            block = mic.read(timeout=1.0)
            if block is None:
                if heard_speech:
                    break
                continue

            chunks.append(block)
            elapsed += seconds_per_block
            level = rms_level(block)
            if on_level:
                on_level(level)

            if level >= self.audio.silence_threshold:
                heard_speech = True
                silent_for = 0.0
            else:
                silent_for += seconds_per_block

            # Live partial text for the overlay, from the first model only.
            if on_partial and self.recognizers:
                primary = self.recognizers[0]
                primary.accept(block)
                partial = primary.partial()
                if partial and partial != last_partial:
                    last_partial = partial
                    on_partial(partial)

            if heard_speech and silent_for >= self.audio.silence_timeout:
                break

        if not heard_speech:
            return Transcript("", 0.0)

        return self.transcribe_pcm(b"".join(chunks))
