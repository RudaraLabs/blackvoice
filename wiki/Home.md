# Black Voice

**An offline-first voice assistant for Linux that speaks Hindi, English and Hinglish.**

Say **“Black”**, then tell it what to do. It opens applications, controls the
system, finds files, runs shell commands behind a safety guard, sets timers,
reads the weather and answers questions.

Speech recognition runs on your own machine by default. Nothing is uploaded
unless the offline pass is unsure *and* you have allowed a cloud fallback.

```
  you    black, firefox kholo
  black  Opening firefox.

  you    black, volume 40
  black  Volume set to 40 percent.

  you    black, run command df -h
  black  Run df -h? Say yes to confirm.
```

---

## Start here

| | |
|---|---|
| **[Installation](Installation)** | Install it, including the system packages most guides forget |
| **[Getting Started](Getting-Started)** | First run, the wake word, and what to say first |
| **[Voice Commands](Voice-Commands)** | Every command, in both languages |

## Go deeper

| | |
|---|---|
| **[Configuration](Configuration)** | Every setting in `config.json`, and the environment overrides |
| **[Architecture](Architecture)** | How audio becomes an action |
| **[Security Model](Security-Model)** | Why a misheard word cannot wipe your disk |
| **[Writing Skills](Writing-Skills)** | Add your own commands |
| **[Troubleshooting](Troubleshooting)** | When something does not work |
| **[Contributing](Contributing)** | Development setup and the test suite |
| **[FAQ](FAQ)** | Short answers to common questions |

---

## Why offline first

Most voice assistants send your microphone to someone else's server. Black Voice
does the opposite: [Vosk](https://alphacephei.com/vosk/) runs locally on every
utterance, and the network is something you opt into rather than depend on.

With `language: "both"`, the English and Hindi models both transcribe the same
audio and the more confident transcript wins. That is what makes Hinglish work —
most people do not speak one language at a time, and the software should keep up.

Set `speech.mode` to `"offline"` and nothing ever leaves the machine.

## Requirements

| | |
|---|---|
| OS | Linux (GNOME, KDE, Xfce, or a tiling window manager) |
| Python | 3.9 or newer |
| Audio | PortAudio, plus PulseAudio, PipeWire or ALSA |
| Disk | ~90 MB for the two offline speech models |
| Network | Optional — only for the cloud fallback and the AI backend |

## Project status

Version 0.1.0. The command routing, safety guard, configuration and skill layers
are covered by 125 tests. The audio path — microphone capture, Vosk recognition,
wake word and speech output — needs a real Linux machine with a microphone to
exercise, so treat it as the least-tested part of the system and report what
breaks.

---

<sub>Black Voice is a [Rudra Labs](https://rudralabs.dev) product · MIT licensed</sub>
