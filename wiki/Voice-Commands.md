# Voice Commands

Everything below works in English, Hindi and Hinglish. Mixing them mid-sentence
is fine — that is the point.

Anything that matches none of these rules becomes a question for the
[AI backend](Configuration#ai--the-question-answering-backend).

> **Tip:** test a phrase without speaking it — `blackvoice text "firefox kholo"`
> shows you exactly which skill it routes to.

---

## Applications

| English | Hindi / Hinglish |
|---|---|
| `open firefox` | `firefox kholo` |
| `launch vlc` · `start code` | `vlc chalu karo` |
| `close chrome` · `quit spotify` | `chrome band karo` |

Known aliases resolve to whatever is actually installed: `browser`, `terminal`,
`files`, `editor`, `calculator`, `music`, `video`, `settings`, `system monitor`.
So `open browser` finds Firefox, Chromium, Chrome, Brave or Epiphany — whichever
is on the machine.

Anything else is treated as the binary name, then as a `.desktop` entry. Set your
preferred defaults in `skills.browser`, `skills.terminal`, `skills.editor` and
`skills.file_manager` — see [Configuration](Configuration).

## Volume

| English | Hindi / Hinglish |
|---|---|
| `volume up` · `louder` | `awaaz badhao` |
| `volume down` · `quieter` | `awaaz kam karo` |
| `volume 40` · `set volume to 70` | `awaaz 40 karo` |
| `mute` | `awaaz band karo` |
| `unmute` | `awaaz wapas karo` |

Uses PipeWire (`wpctl`), then PulseAudio (`pactl`), then ALSA (`amixer`) —
whichever is present. Up and down move in steps of 10.

## Brightness

| English | Hindi / Hinglish |
|---|---|
| `brightness up` · `brighter` | `roshni badhao` |
| `brightness down` · `dim the screen` | `roshni kam karo` |
| `brightness 70` | `roshni 70 karo` |

Uses `brightnessctl`, then `light`, then raw sysfs. **Never goes below 5%** — a
misheard number should not blank your screen.

If it refuses, you are probably not in the `video` group:

```bash
sudo usermod -aG video $USER    # then log out and back in
```

## Screen and power

| English | Hindi / Hinglish |
|---|---|
| `screenshot` | `screenshot lo` |
| `lock screen` | `screen lock karo` |
| `shut down` | `computer band karo` |
| `restart` · `reboot` | `computer restart karo` |
| `log out` | — |
| `suspend` | — |

Screenshots land in `~/Pictures` with a timestamped name. Six tools are tried:
`gnome-screenshot`, `spectacle`, `grim`, `scrot`, `import`, `maim`.

**Every power action asks for confirmation first.** Say “yes” or “haan” to go
through with it.

## Radios and hardware

| English | Hindi / Hinglish |
|---|---|
| `wifi off` · `turn on the wifi` | `wifi band karo` |
| `bluetooth on` | `bluetooth chalu karo` |
| `battery` · `battery status` | `battery kitni hai` |
| `system info` · `cpu usage` | — |

`battery` reports the charge and, on battery power, the estimated time left.
`system info` shows CPU, memory, disk and uptime.

## Folders and files

| English | Hindi / Hinglish |
|---|---|
| `open downloads` | `downloads kholo` |
| `open documents` · `open desktop` | `documents kholo` |
| `find file report.pdf` | `report.pdf file dhoondo` |
| `create folder demo` | `demo folder banao` |
| `disk space` | — |

Recognised folders: downloads, documents, desktop, pictures, music, videos,
home, trash. Localised XDG directory names are respected, so this works on a
non-English desktop.

`find` uses `plocate`/`locate` when available and falls back to a depth-limited
walk of your home directory, skipping `.git`, `node_modules`, caches and dotfiles.
It returns at most 8 matches.

`create folder` strips anything that is not a letter, digit, space, hyphen or
underscore, and only ever creates inside your home directory.

## Terminal

| English | Hindi / Hinglish |
|---|---|
| `run command df -h` | `terminal me ls chalao` |
| `execute command uptime` | — |

Read-only commands run immediately. Anything else asks first. A short deny-list
never runs at all. This is covered properly in
**[Security Model](Security-Model)** — read it before using this skill.

The recogniser spells out punctuation, so `dash`, `double dash`, `slash`, `dot`,
`star` and `tilde` are translated back into `-`, `--`, `/`, `.`, `*` and `~`.

## Time, date and weather

| English | Hindi / Hinglish |
|---|---|
| `what time is it` · `time` | `kitne baje hain` |
| `what is the date` · `date` | `aaj ki date` |
| `weather` · `weather in Jaipur` | `mausam` |

Weather comes from [wttr.in](https://wttr.in) and needs no API key. With no city
it geolocates by IP; set `skills.weather_city` to pin it.

## Timers and reminders

| English | Hindi / Hinglish |
|---|---|
| `set timer for 5 minutes` | `10 minute ka timer` |
| `remind me to call mom in 20 minutes` | `20 minute baad call karna yaad dilana` |

Seconds, minutes and hours are understood, up to 24 hours. When a timer fires it
speaks and raises a desktop notification.

Timers do not survive a restart — they live in memory only.

## Notes

| English | Hindi / Hinglish |
|---|---|
| `take a note buy milk` | `note me doodh likho` |
| `read my notes` | `mere notes padho` |

Notes append to `~/.local/share/blackvoice/notes.md` with a timestamp. Reading
them speaks the last five.

## Search and media

| English | Hindi / Hinglish |
|---|---|
| `search for python decorators` | `python search karo` |
| `google linux distros` | `google par python dhoondo` |
| `play` · `pause` | `gaana chalao` · `gaana roko` |
| `next` · `next song` | `agla gaana` |
| `previous song` | `pichla gaana` |

Search opens your browser at DuckDuckGo; change `skills.search_url` for a
different engine. Media control needs `playerctl`, falling back to `xdotool`.

## Arithmetic

| English |
|---|
| `calculate 12 * 8` |
| `what is 100 / 4` |
| `5 + 3` |

Only numbers and operators are evaluated — `+ - * / % **` and parentheses. It
parses an abstract syntax tree rather than calling `eval`, so names, calls and
attributes are rejected. Say “x” or “times” for multiplication.

A phrase without an operator is treated as a question, not a sum: *“what is 42”*
goes to the AI.

## Meta

| English | Hindi / Hinglish |
|---|---|
| `help` · `what can you do` | `madad` |
| `stop` · `cancel` · `never mind` | `ruko` · `rehne do` |
| `go to sleep` · `stop listening` | `so jao` |
| `yes` · `ok` · `go ahead` | `haan` · `theek hai` |
| `no` · `don't` | `nahi` · `mat karo` |

“Yes” and “no” only mean something while a confirmation is pending. At any other
time they are just words.

---

## How matching works

Rules are tried in order, first match wins. The generic `open X` and `close X`
rules are deliberately tried **last**, so `open downloads` reaches the folder
rule and `run command df -h` reaches the terminal rule rather than being read as
an application named *“command df -h”*.

Two rules are also rejected when they look like questions instead of commands:

- `calculate` needs an actual operator in the expression
- `open` / `close` reject targets longer than four words, and phrases starting
  with question words (`what`, `why`, `how`, `kya`, `kaise`, …)

There are 42 rules in total. They live in
[`blackvoice/nlu/intents.py`](https://github.com/RudaraLabs/blackvoice/blob/main/blackvoice/nlu/intents.py);
adding your own is covered in **[Writing Skills](Writing-Skills)**.

## When it mishears you

```bash
blackvoice text "the phrase you said"
```

If text mode routes it correctly but speech does not, the problem is
recognition, not routing — see
[Troubleshooting → Recognition is poor](Troubleshooting#recognition-is-poor).
