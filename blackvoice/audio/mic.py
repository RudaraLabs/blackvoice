"""Microphone capture.

Wraps ``sounddevice`` in a small blocking iterator that yields raw 16-bit mono
PCM blocks, plus helpers for level metering and silence detection. Import of
``sounddevice`` is deferred so that the rest of Black Voice (config, CLI help,
text mode) still works on a machine with no PortAudio installed.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Iterator, List, Optional

from ..config import AudioConfig

log = logging.getLogger(__name__)


class MicrophoneUnavailable(RuntimeError):
    """Raised when no usable input device could be opened."""


def _import_sounddevice():
    try:
        import sounddevice as sd  # noqa: WPS433 - deliberate lazy import
    except (ImportError, OSError) as exc:
        raise MicrophoneUnavailable(
            "sounddevice/PortAudio is not available. "
            "Install it with:  sudo apt install portaudio19-dev && pip install sounddevice"
        ) from exc
    return sd


def list_devices() -> List[dict]:
    """Return the input devices PortAudio can see."""
    sd = _import_sounddevice()
    devices = []
    for index, dev in enumerate(sd.query_devices()):
        if dev.get("max_input_channels", 0) > 0:
            devices.append(
                {
                    "index": index,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": int(dev.get("default_samplerate", 0)),
                }
            )
    return devices


def rms_level(block: bytes) -> float:
    """Root-mean-square loudness of an int16 block, normalised to 0..1."""
    try:
        import numpy as np
    except ImportError:
        return 0.0
    if not block:
        return 0.0
    samples = np.frombuffer(block, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples ** 2)) / 32768.0)


class Microphone:
    """A restartable microphone stream.

    Usage::

        with Microphone(cfg) as mic:
            for block in mic.blocks():
                ...
    """

    def __init__(self, cfg: AudioConfig) -> None:
        self.cfg = cfg
        self._queue: "queue.Queue[bytes]" = queue.Queue(maxsize=64)
        self._stream = None
        self._stop = threading.Event()

    # ----------------------------------------------------------- lifecycle
    def open(self) -> "Microphone":
        sd = _import_sounddevice()
        self._stop.clear()

        def _callback(indata, frames, time_info, status):  # noqa: ANN001
            if status:
                log.debug("audio status: %s", status)
            try:
                self._queue.put_nowait(bytes(indata))
            except queue.Full:
                # Dropping a block is better than blocking the audio thread.
                log.debug("audio queue full, dropping a block")

        try:
            self._stream = sd.RawInputStream(
                samplerate=self.cfg.sample_rate,
                blocksize=self.cfg.block_size,
                device=self.cfg.input_device,
                dtype="int16",
                channels=1,
                callback=_callback,
            )
            self._stream.start()
        except Exception as exc:
            raise MicrophoneUnavailable(f"could not open microphone: {exc}") from exc

        log.info(
            "microphone open (%d Hz, block %d, device %s)",
            self.cfg.sample_rate,
            self.cfg.block_size,
            self.cfg.input_device if self.cfg.input_device is not None else "default",
        )
        return self

    def close(self) -> None:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                log.debug("error while closing the audio stream", exc_info=True)
            self._stream = None
        self.drain()

    def __enter__(self) -> "Microphone":
        return self.open()

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -------------------------------------------------------------- reading
    def drain(self) -> None:
        """Throw away buffered audio, e.g. after the assistant finished speaking."""
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def read(self, timeout: float = 0.5) -> Optional[bytes]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def blocks(self) -> Iterator[bytes]:
        """Yield audio blocks until :meth:`close` is called."""
        while not self._stop.is_set():
            block = self.read()
            if block:
                yield block

    @property
    def seconds_per_block(self) -> float:
        return self.cfg.block_size / float(self.cfg.sample_rate)
