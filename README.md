<div align="center">

<img src="assets/logo.svg" width="140" alt="Black Voice">

# Black Voice

**An offline-first voice assistant for Linux — speaks Hindi, English and Hinglish.**

<sub>A RUDRA LABS PRODUCT</sub>

</div>

---

Say **“Black”**, then tell it what to do. It opens apps, changes the volume,
finds files, runs shell commands (carefully), sets timers, reads the weather and
answers questions. Speech recognition runs on your own machine by default —
nothing is uploaded unless the offline pass is unsure and you allowed the online
fallback.

```
  you    black, firefox kholo
  black  Opening firefox.

  you    black, volume 40
  black  Volume set to 40 percent.

  you    black, run command df -h
  black  Run df -h? Say yes to confirm.
```

## Install

```bash
git clone https://github.com/RudaraLabs/blackvoice.git
cd black-voice
./install.sh --system
```

`--system` installs the distro packages (PortAudio, espeak-ng, playerctl and
friends) and needs sudo. Without it, only the Python side is installed and you
are told what is missing. The installer creates a virtualenv in
`~/.local/share/blackvoice-venv`, puts a `blackvoice` command in
`~/.local/bin`, adds a desktop entry, and downloads the speech models (~90 MB).

Check everything landed:

```bash
blackvoice doctor
```

> **Full documentation is in the [wiki](https://github.com/RudaraLabs/blackvoice/wiki)** —
> installation detail, every voice command, the configuration reference, the
> security model and how to write your own skills.

### Manual install

```bash
sudo apt install portaudio19-dev python3-dev espeak-ng libnotify-bin playerctl brightnessctl
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
blackvoice setup          # download the Vosk models
```

## Use

```bash
blackvoice                 # tray icon + popup overlay (the normal way)
blackvoice run --no-ui     # terminal only, no desktop needed
blackvoice text            # type commands instead of speaking
blackvoice text "open firefox"
blackvoice doctor          # what is installed, what is missing
blackvoice devices         # list microphones
blackvoice say "hello"     # test text-to-speech
```

Start it on login:

```bash
systemctl --user enable --now blackvoice
```

There is no global hotkey built in, because every desktop grabs keys
differently. Bind `~/.local/bin/blackvoice text` in your desktop's keyboard
settings, or just click the tray icon.

## What it understands

Both languages work for everything below; mixing them mid-sentence is fine.

| | English | Hindi / Hinglish |
|---|---|---|
| **Apps** | `open firefox`, `close chrome` | `firefox kholo`, `chrome band karo` |
| **Volume** | `volume up`, `volume 40`, `mute` | `awaaz badhao`, `awaaz band karo` |
| **Brightness** | `brightness down`, `brightness 70` | `roshni kam karo` |
| **Screen** | `screenshot`, `lock screen` | `screenshot lo`, `screen lock karo` |
| **Power** | `shut down`, `restart`, `log out` | `computer band karo` |
| **Radios** | `wifi off`, `bluetooth on` | `wifi band karo` |
| **Status** | `battery`, `system info` | `battery kitni hai` |
| **Folders** | `open downloads` | `downloads kholo` |
| **Files** | `find file report.pdf`, `disk space` | `report.pdf file dhoondo` |
| **Shell** | `run command df -h` | `terminal me ls chalao` |
| **Clock** | `what time is it`, `what is the date` | `kitne baje hain`, `aaj ki date` |
| **Weather** | `weather`, `weather in Jaipur` | `mausam` |
| **Timers** | `set timer for 5 minutes` | `10 minute ka timer` |
| **Reminders** | `remind me to call mom in 20 minutes` | |
| **Notes** | `take a note buy milk`, `read my notes` | `note me doodh likho` |
| **Search** | `search for python decorators` | `google par python dhoondo` |
| **Media** | `play`, `next`, `previous` | `gaana chalao`, `agla gaana` |
| **Maths** | `calculate 12 * 8` | |
| **Meta** | `help`, `stop`, `go to sleep` | `madad`, `ruko`, `so jao` |

Anything that matches none of these becomes a question for the AI backend.

## How it works

```
  microphone ──► wake word ──► hybrid STT ──► router ──► skill ──► speaker
                  (Vosk         (Vosk, then    (regex     (system, files,   (piper /
                   grammar)      cloud if       rules)     terminal, ai,     espeak-ng)
                                 unsure)                   utils)
                        │                           │
                        └──────── event bus ────────┴──► tray icon + overlay
```

**Hybrid recognition.** Vosk runs locally on every utterance. With
`language: "both"`, the English and Hindi models both transcribe the same audio
and the more confident one wins — that is what makes Hinglish work. Only when
Vosk comes back below `fallback_confidence` (and you are online) is the audio
retried against the cloud recogniser. Set `speech.mode` to `"offline"` to
guarantee nothing ever leaves the machine.

**Portability.** Every system action probes for the tool that is actually
installed — PipeWire before PulseAudio before ALSA, `brightnessctl` before
`light` before raw sysfs, six different screenshot tools — so it works across
GNOME, KDE, Xfce and the tiling window managers without configuration.

## Safety

Voice recognition mishears things, so shell access is deliberately narrow:

- **Blocked outright** — `rm -rf`, `mkfs`, `dd` to a device, fork bombs,
  `curl … | sh`, anything under `sudo`/`pkexec`. These never run, no matter what.
- **Asks first** — anything that could change the system, and anything that
  chains commands with `;`, `&&` or a pipe. You confirm out loud.
- **Runs immediately** — a short list of read-only commands (`ls`, `df`, `cat`,
  `git status`, …).

Power actions (shutdown, restart, log out) always ask before firing. The
arithmetic skill parses an AST and evaluates only numbers and operators, so
`calculate __import__('os')…` does nothing.

The deny-list lives in your config file under `safety.blocked_patterns`. It is
copied there on first run, so **if you upgrade Black Voice, new default patterns
are not added to an existing config** — run `blackvoice config --reset` (or merge
them by hand) after an upgrade if you want them.

## Configuration

`~/.config/blackvoice/config.json`, created on first run.

```jsonc
{
  "speech": {
    "mode": "hybrid",              // "hybrid" | "offline" | "online"
    "language": "both",            // "en" | "hi" | "both"
    "fallback_confidence": 0.55    // below this, hybrid mode tries the cloud
  },
  "wake": {
    "phrases": ["black", "blek", "blak"],
    "chime": true
  },
  "voice": {
    "engine": "auto",              // auto | piper | espeak | spd-say | pyttsx3 | none
    "rate": 165
  },
  "ai": {
    "provider": "ollama",          // ollama | anthropic | openai | none
    "ollama_model": "llama3.2",
    "anthropic_model": "claude-opus-5"
  },
  "safety": { "confirm_shell": true },
  "skills": { "weather_city": "Jaipur" }
}
```

Any value can be overridden by an environment variable — useful in the systemd
unit:

```bash
BLACKVOICE_SPEECH_MODE=offline BLACKVOICE_AI_PROVIDER=none blackvoice
```

### AI backend

Local by default. Install [Ollama](https://ollama.com) and pull a model:

```bash
ollama pull llama3.2
```

For Claude, set `ai.provider` to `"anthropic"`, `pip install anthropic`, and
export `ANTHROPIC_API_KEY` (an `ant auth login` profile works too). For OpenAI,
set `"openai"` and export `OPENAI_API_KEY`. Set `"none"` to disable
question-answering entirely; unrecognised commands then just say so.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `could not open microphone` | `sudo apt install portaudio19-dev` then reinstall `sounddevice`; check `blackvoice devices` |
| Wake word never fires | Models missing — `blackvoice setup`. Or use the tray icon. |
| No speech output | `sudo apt install espeak-ng`, then `blackvoice say "test"` |
| Volume commands do nothing | Install `pulseaudio-utils` (`pactl`) or use PipeWire's `wpctl` |
| Brightness refused | `sudo usermod -aG video $USER`, log out and back in |
| No tray icon | Some GNOME setups need the AppIndicator extension; the overlay still works |
| Recognition is poor | Try `speech.language: "en"` to load one model, or `mode: "online"` |

Logs: `~/.cache/blackvoice/blackvoice.log`, or run with `-v`.

## Development

```bash
pip install -e ".[all,dev]"
pytest                     # 125 tests, no microphone required
blackvoice text            # exercise the router without speaking
```

The wiki lives in `wiki/` and is published by a GitHub Actions workflow on every
push that touches it. Editing the wiki on GitHub directly does not work — the
next sync overwrites it. Change `wiki/` and open a pull request instead.

Adding a skill is three steps: write a `Skill` subclass with a `handle` method,
add its patterns to `RULES` in `blackvoice/nlu/intents.py`, and register it in
`Engine.__init__`. Put specific rules before general ones — the router returns
the first match.

```
blackvoice/
  app.py            engine: audio loop, wake state machine, confirmations
  cli.py            command line
  config.py         dataclass config + env overrides
  audio/            mic, hybrid STT, TTS, wake word
  nlu/              intent patterns (hi + en) and the router
  skills/           system, files, terminal, ai, utils, control
  ui/               tray icon, overlay, painted logo
  core/             event bus, logging, shell safety
```

## Licence

MIT © 2026 Rudra Labs.
