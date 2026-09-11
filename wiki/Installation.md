# Installation

Black Voice targets Linux. It needs Python 3.9+, PortAudio for the microphone,
and a speech engine for talking back.

## The short way

```bash
git clone https://github.com/RudaraLabs/blackvoice.git
cd blackvoice
./install.sh --system
```

Then check it:

```bash
blackvoice doctor
```

`doctor` prints what is installed, what is missing, and the exact command to fix
each gap. Run it first whenever something misbehaves.

## What the installer does

| Step | Where it lands |
|---|---|
| System packages (`--system` only) | via apt / dnf / pacman / zypper |
| Virtualenv + dependencies | `~/.local/share/blackvoice-venv` |
| `blackvoice` command | `~/.local/bin/blackvoice` |
| Desktop entry and icon | `~/.local/share/applications`, `~/.local/share/icons` |
| systemd user unit | `~/.config/systemd/user/blackvoice.service` |
| Speech models (~90 MB) | `~/.local/share/blackvoice/models` |

Nothing is installed system-wide except the distro packages, and those only when
you pass `--system`.

### Installer options

```bash
./install.sh              # Python side only; tells you what system packages are missing
./install.sh --system     # also installs the distro packages (needs sudo)
./install.sh --no-models  # skip the ~90 MB model download
./install.sh --uninstall  # remove everything the installer created
```

`--uninstall` leaves your config, models and notes alone. Delete those yourself
if you want them gone:

```bash
rm -rf ~/.config/blackvoice ~/.local/share/blackvoice ~/.cache/blackvoice
```

## System packages

`--system` installs these for you. If you would rather do it by hand:

**Debian / Ubuntu / Mint / Pop!\_OS**

```bash
sudo apt install portaudio19-dev python3-dev python3-venv espeak-ng \
  libnotify-bin playerctl brightnessctl pulseaudio-utils gnome-screenshot
```

**Fedora / RHEL**

```bash
sudo dnf install portaudio-devel python3-devel espeak-ng \
  libnotify playerctl brightnessctl pulseaudio-utils gnome-screenshot
```

**Arch / Manjaro**

```bash
sudo pacman -S --needed portaudio espeak-ng libnotify playerctl \
  brightnessctl libpulse gnome-screenshot
```

**openSUSE**

```bash
sudo zypper install portaudio-devel python3-devel espeak-ng \
  libnotify-tools playerctl brightnessctl pulseaudio-utils
```

### What each package is for

| Package | Without it |
|---|---|
| `portaudio19-dev` | **No microphone at all.** This one is not optional. |
| `python3-venv` | The installer cannot create its virtualenv |
| `espeak-ng` | No speech output — replies are printed, not spoken |
| `pulseaudio-utils` / PipeWire | Volume commands do nothing |
| `brightnessctl` | Brightness commands do nothing |
| `playerctl` | Media keys (play, next, previous) do nothing |
| `libnotify-bin` | No desktop notifications for timers and reminders |
| `gnome-screenshot` | Screenshots fail — `grim`, `scrot`, `maim` and `spectacle` also work |

## Manual install

If you would rather not use the installer:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
blackvoice setup          # download the Vosk models
blackvoice doctor
```

The optional extras can be installed separately if you want a smaller footprint:

```bash
pip install -e ".[offline]"   # Vosk only, no cloud fallback
pip install -e ".[ui]"        # PyQt6 tray icon and overlay
pip install -e ".[online]"    # cloud fallback
pip install -e ".[tts]"       # pyttsx3 speech output
```

Without `[ui]` it runs headless (`blackvoice run --no-ui`), which is fine over
SSH or on a server.

## Speech models

```bash
blackvoice setup                  # both languages
blackvoice setup --language en    # English only
blackvoice setup --language hi    # Hindi only
blackvoice setup --force          # re-download
```

Models come from [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models)
and land in `~/.local/share/blackvoice/models`. If the download fails behind a
proxy, fetch the zips by hand and extract them there — the folder names must stay
as they are:

```
~/.local/share/blackvoice/models/
├── vosk-model-small-en-us-0.15/
└── vosk-model-small-hi-0.22/
```

You can point at bigger models by setting `speech.model_en` / `speech.model_hi`
to an absolute path. See [Configuration](Configuration).

## Running on login

```bash
systemctl --user enable --now blackvoice
systemctl --user status blackvoice
journalctl --user -u blackvoice -f      # follow the logs
```

## Upgrading

```bash
cd blackvoice
git pull
./install.sh
```

One thing the upgrade does **not** do: your `~/.config/blackvoice/config.json`
was written on first run and is never overwritten, so new default settings — and
in particular new entries in `safety.blocked_patterns` — do not reach an existing
config. After an upgrade, either merge them by hand or reset:

```bash
blackvoice config --reset
```

## Next

→ **[Getting Started](Getting-Started)**
