# FAQ

### Does it work without internet?

Yes, that is the point. Set `speech.mode` to `"offline"` and nothing ever leaves
the machine. In the default `hybrid` mode it only reaches the network when the
offline pass is unsure *and* you are online.

The AI question-answering skill needs a backend — the default, Ollama, is also
local.

### Is my voice sent anywhere?

In `offline` mode, no. In `hybrid`, only when Vosk's confidence falls below
`fallback_confidence` and a connectivity check succeeds. In `online`, always.

If this matters to you, set `"mode": "offline"` and stop wondering. See
[Security Model → Privacy](Security-Model#privacy).

### Does it really understand Hinglish?

Yes, and not by detecting the language first. With `language: "both"` the English
and Hindi models each transcribe the **same audio** and the more confident result
wins. *“Black, firefox kholo”* and *“Black, open firefox”* both work, and so does
a sentence that switches halfway.

### Will it run on Windows or macOS?

No. It is Linux-only by design — the system commands, desktop integration and
packaging are all Linux. The core routing and skills are portable, but the parts
that make it useful are not.

### Why Vosk rather than Whisper?

Vosk is small (~50 MB), fast on a CPU, and streams — which is what you want for
short commands and a wake word that runs all day. Whisper is more accurate but
heavier and slower, and it does not stream, so a wake word is awkward.

For dictation rather than commands, Whisper would be the better choice.

### Can I change the wake word?

Yes, in `wake.phrases`. A two-word trigger is much more reliable than a single
short word:

```jsonc
"wake": { "phrases": ["hey black", "ok black"] }
```

“black” on its own is close enough to **back**, **block**, **blank** and **lack**
that ordinary conversation can set it off.

### Can I use it without a wake word?

Yes. Click the tray icon, or use `blackvoice text`. Set `wake.enabled` to `false`
to switch the listener off entirely.

### Why is there no global hotkey?

Because every desktop environment grabs keys differently and a hotkey that works
on GNOME but silently fails on i3 is worse than none. Bind
`~/.local/bin/blackvoice text` in your desktop's own keyboard settings.

### How much CPU does it use while idle?

The wake-word detector uses a restricted Vosk grammar, so it only has to decide
between the wake phrases and “not that”. That is much cheaper than full
recognition, which only starts once you have been heard.

### Can it run headless, on a server or over SSH?

Yes:

```bash
blackvoice run --no-ui
```

No Qt, no tray, no display needed. You still need a microphone on that machine.

### Will it run my commands as root?

Never. `sudo`, `doas`, `pkexec` and `su` are refused before anything else is
checked. If a task needs root, it tells you to run it yourself.

### Can I make it run shell commands without confirming?

`"safety": { "confirm_shell": false }`. The deny-list still applies —
`rm -rf`, `mkfs`, `dd` to a device and the rest stay refused. It is not
recommended; read [Security Model](Security-Model) first.

### I upgraded and my safety settings look old

They are. `blocked_patterns` is written into your config on first run and never
touched again, so new default patterns do not reach an existing config. Run
`blackvoice config --reset` or merge them by hand.

### Which AI backend should I use?

**Ollama** if you want everything local and private — this is the default.
**Claude** or **OpenAI** if you want better answers and do not mind the
questions leaving your machine. **None** if you only want commands.

See [Configuration → AI backend](Configuration#ai--the-question-answering-backend).

### Does it remember the conversation?

The AI skill keeps the last six turns for context. Clear it from the tray menu →
*Clear AI conversation*. Nothing is written to disk.

### Do timers survive a restart?

No. Timers and reminders live in memory only. Use `at` or a calendar for
anything that matters.

### Where are my notes stored?

`~/.local/share/blackvoice/notes.md`, as plain markdown with timestamps. Edit it
in any editor.

### Can I add my own commands?

Yes — a skill class, some regex patterns, one line to register it. See
[Writing Skills](Writing-Skills).

### It hears me but does the wrong thing

That is a routing problem, not a recognition one. Confirm it:

```bash
blackvoice text "the exact phrase"
```

If text mode also does the wrong thing, open an issue with the phrase. If text
mode is correct, the problem is recognition — see
[Troubleshooting](Troubleshooting#recognition-is-poor).

### Why does it sound robotic?

espeak-ng is small and instant, and it speaks Hindi out of the box, but it is
robotic. For a natural voice, install
[piper](https://github.com/rhasspy/piper) and point `voice.piper_model` at a
voice file.

### Is it production ready?

Version 0.1.0. The command routing, safety guard, configuration and skill layers
have 165 tests. The audio path needs a real machine with a microphone to
exercise properly, so treat that as the least-proven part and report what breaks.

### How do I uninstall it?

```bash
./install.sh --uninstall
rm -rf ~/.config/blackvoice ~/.local/share/blackvoice ~/.cache/blackvoice
```

The first command removes the program; the second removes your config, models
and notes.

### Who makes this?

[Rudra Labs](https://rudralabs.dev). MIT licensed — use it, fork it, ship it.
