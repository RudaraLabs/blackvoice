"""Command line entry point for Black Voice."""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path
from typing import List, Optional

from . import __version__
from .config import APP_TITLE, CONFIG_FILE, LOG_FILE, MODELS_DIR, Config, ensure_dirs
from .core.logs import setup_logging


def _unicode_console() -> bool:
    """True when stdout can actually render the box-drawing banner.

    A terminal under ``LANG=C`` (or a Windows console on cp1252) raises
    UnicodeEncodeError on the nice glyphs, which is a silly way for a diagnostic
    command to die - so fall back to ASCII there.
    """
    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    return "utf" in encoding


_UNICODE = _unicode_console()

OK = "✓" if _UNICODE else "[ok]"
BAD = "✗" if _UNICODE else "[--]"
DOT = "·" if _UNICODE else "-"
ARROW = "→" if _UNICODE else "->"
BULLET = "•" if _UNICODE else "*"

_BANNER_UNICODE = r"""
  ██████  ██       █████   ██████ ██   ██     ██    ██  ██████  ██  ██████ ███████
  ██   ██ ██      ██   ██ ██      ██  ██      ██    ██ ██    ██ ██ ██      ██
  ██████  ██      ███████ ██      █████       ██    ██ ██    ██ ██ ██      █████
  ██   ██ ██      ██   ██ ██      ██  ██       ██  ██  ██    ██ ██ ██      ██
  ██████  ███████ ██   ██  ██████ ██   ██       ████    ██████  ██  ██████ ███████
"""

_BANNER_ASCII = r"""
  ####  #      ###   ####  #  #    #  #  ###  #  ####  ###
  #   # #     #   # #      # #     #  # #   # # #     #
  ####  #     ##### #      ##      #  # #   # # #     ###
  #   # #     #   # #      # #      ##  #   # # #     #
  ####  ##### #   #  ####  #  #     ##   ###  #  #### ###
"""

BANNER = _BANNER_UNICODE if _UNICODE else _BANNER_ASCII


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_run(args: argparse.Namespace) -> int:
    from .app import Engine

    config = Config.load()
    engine = Engine(config)

    if args.no_ui or not config.ui.enabled:
        return _run_headless(engine)

    try:
        from .ui.tray import TrayApp
    except ImportError as exc:
        print(f"PyQt6 is not available ({exc}); falling back to headless mode.")
        print("Install it with:  pip install PyQt6")
        return _run_headless(engine)

    return TrayApp(engine).run()


def _run_headless(engine) -> int:
    from .core.bus import Topic

    engine.bus.subscribe(
        Topic.HEARD,
        lambda e: None if e.get("partial") else print(f"  you  {e.get('text', '')}"),
    )
    engine.bus.subscribe(
        Topic.REPLY,
        lambda e: print(f"  {APP_TITLE.split()[0].lower()}  {e.get('display') or e.get('speech')}\n"),
    )
    engine.bus.subscribe(Topic.ERROR, lambda e: print(f"  error  {e.get('message')}"))

    print(BANNER)
    print(engine.describe())
    print('\nListening. Say "Black" to wake me. Press Ctrl+C to quit.\n')

    try:
        engine.start(background=False)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        engine.stop()
    return 0


def cmd_text(args: argparse.Namespace) -> int:
    """Type commands instead of speaking them - handy for testing the router."""
    from .app import Engine

    engine = Engine(Config.load())

    if args.command:
        reply = engine.process(" ".join(args.command))
        print(reply.display or reply.speech)
        engine.stop()
        return 0 if reply.ok else 1

    print(BANNER)
    print('Type a command, or "quit" to exit.\n')
    try:
        while True:
            try:
                line = input("  you  ").strip()
            except EOFError:
                break
            if not line:
                continue
            if line.lower() in {"quit", "exit", "q"}:
                break
            reply = engine.process(line)
            print(f"  black  {reply.display or reply.speech}\n")
    except KeyboardInterrupt:
        print()
    finally:
        engine.stop()
    return 0


def cmd_say(args: argparse.Namespace) -> int:
    """Check that text-to-speech works."""
    from .audio.tts import Speaker

    config = Config.load()
    speaker = Speaker(config.voice)
    text = " ".join(args.text) or "Black Voice is ready."
    print(f"Engine: {speaker.engine}")
    speaker.say(text)
    speaker.wait_until_idle(timeout=30)
    speaker.shutdown()
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    """Download the offline speech models."""
    from . import models

    ensure_dirs()
    wanted = ["en", "hi"] if args.language == "both" else [args.language]
    failures = 0

    for lang in wanted:
        name = models.MODEL_URLS[lang][0]
        if (MODELS_DIR / name).exists() and not args.force:
            print(f"{OK} {name} already installed")
            continue

        print(f"{ARROW} downloading {name}")
        last = [-1]

        def _progress(_lang: str, done: int, total: int) -> None:
            percent = int(done * 100 / total) if total else 0
            if percent == last[0]:
                return
            last[0] = percent
            bar = f"  {percent:3d}%  {done / 2**20:6.1f} MiB"
            print(chr(13) + bar, end="", flush=True)

        ok = models.download(lang, on_progress=_progress)
        print()
        if ok:
            print(f"{OK} {name} installed")
        else:
            failures += 1

    if failures:
        print()
        print("Some models could not be installed.")
        print(f"You can download them by hand into {MODELS_DIR} from")
        print("https://alphacephei.com/vosk/models")
        return 1

    print()
    print(f"Models are in {MODELS_DIR}")
    print("Run 'blackvoice doctor' to check everything is wired up.")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Report what is installed and what is missing."""
    from .app import Engine

    print(BANNER)
    config = Config.load()
    problems: List[str] = []

    print("Python packages")
    for module, why, fatal in [
        ("sounddevice", "microphone capture", True),
        ("numpy", "audio buffers", True),
        ("vosk", "offline speech recognition", False),
        ("speech_recognition", "online fallback", False),
        ("PyQt6", "tray icon and overlay", False),
        ("requests", "AI and weather", True),
        ("psutil", "battery and system info", False),
    ]:
        try:
            __import__(module)
            print(f"  {OK} {module:<20} {why}")
        except ImportError:
            print(f"  {BAD} {module:<20} {why}")
            if fatal:
                problems.append(f"pip install {module}")

    print("\nSystem tools")
    for tool, why in [
        ("espeak-ng", "text to speech"),
        ("pactl", "volume (PulseAudio)"),
        ("wpctl", "volume (PipeWire)"),
        ("brightnessctl", "screen brightness"),
        ("playerctl", "media keys"),
        ("nmcli", "Wi-Fi"),
        ("notify-send", "desktop notifications"),
        ("gnome-screenshot", "screenshots"),
        ("ollama", "local AI answers (optional)"),
    ]:
        mark = OK if shutil.which(tool) else DOT
        print(f"  {mark} {tool:<20} {why}")

    print("\nModels")
    for lang in ("en", "hi"):
        path = config.model_path(lang)
        if path.exists():
            print(f"  {OK} {lang}  {path}")
        else:
            print(f"  {BAD} {lang}  missing ({path})")

    if not any(config.model_path(l).exists() for l in ("en", "hi")):
        problems.append("blackvoice setup")

    print("\nMicrophones")
    try:
        from .audio.mic import list_devices

        devices = list_devices()
        if devices:
            for dev in devices:
                print(f"  {DOT} [{dev['index']}] {dev['name']}")
        else:
            print(f"  {BAD} no input devices found")
            problems.append("check that a microphone is connected")
    except Exception as exc:
        print(f"  {BAD} {exc}")
        problems.append("install PortAudio: sudo apt install portaudio19-dev")

    print("\nEngine")
    try:
        print("  " + Engine(config).describe().replace("\n", "\n  "))
    except Exception as exc:
        print(f"  {BAD} could not start the engine: {exc}")

    print(f"\nConfig  {CONFIG_FILE}")
    print(f"Log     {LOG_FILE}")

    if problems:
        print("\nTo fix:")
        for item in problems:
            print(f"  {BULLET} {item}")
        return 1

    print("\nEverything looks good.")
    return 0


def cmd_devices(args: argparse.Namespace) -> int:
    from .audio.mic import list_devices

    try:
        devices = list_devices()
    except Exception as exc:
        print(exc)
        return 1

    if not devices:
        print("No input devices found.")
        return 1

    print("Input devices:\n")
    for dev in devices:
        print(f"  [{dev['index']:2d}]  {dev['name']}  ({dev['channels']} ch, {dev['sample_rate']} Hz)")
    print("\nSet one with:  audio.input_device  in", CONFIG_FILE)
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    config = Config.load()
    if args.reset:
        path = Config().save()
        print(f"Configuration reset to defaults: {path}")
        return 0
    if args.path:
        print(CONFIG_FILE)
        return 0
    import json

    print(json.dumps(config.to_dict(), indent=2))
    return 0


# --------------------------------------------------------------------------- #
# argument parsing
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blackvoice",
        description=f"{APP_TITLE} - an offline-first voice assistant for Linux.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  blackvoice setup              download the offline models\n"
            "  blackvoice                    run with the tray icon\n"
            "  blackvoice run --no-ui        run in the terminal\n"
            "  blackvoice text 'open firefox'\n"
            "  blackvoice doctor             check the installation\n"
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="warnings and errors only")
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_TITLE} {__version__}",
        help="print the version and exit",
    )

    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="start the assistant (default)")
    run.add_argument("--no-ui", action="store_true", help="terminal only, no tray icon")
    run.set_defaults(func=cmd_run)

    text = sub.add_parser("text", help="type commands instead of speaking")
    text.add_argument("command", nargs="*", help="run one command and exit")
    text.set_defaults(func=cmd_text)

    setup = sub.add_parser("setup", help="download the offline speech models")
    setup.add_argument(
        "--language", choices=["en", "hi", "both"], default="both",
        help="which models to fetch (default: both)",
    )
    setup.add_argument("--force", action="store_true", help="re-download even if present")
    setup.set_defaults(func=cmd_setup)

    doctor = sub.add_parser("doctor", help="check the installation")
    doctor.set_defaults(func=cmd_doctor)

    devices = sub.add_parser("devices", help="list microphones")
    devices.set_defaults(func=cmd_devices)

    say = sub.add_parser("say", help="test text to speech")
    say.add_argument("text", nargs="*")
    say.set_defaults(func=cmd_say)

    config = sub.add_parser("config", help="show or reset the configuration")
    config.add_argument("--path", action="store_true", help="print the config file path")
    config.add_argument("--reset", action="store_true", help="restore the defaults")
    config.set_defaults(func=cmd_config)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    # Belt and braces: a stray non-ASCII character in a filename or an error
    # message must not kill the program on a non-UTF-8 console.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError, ValueError):
            pass

    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    if not getattr(args, "func", None):
        args.func = cmd_run
        args.no_ui = False

    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
