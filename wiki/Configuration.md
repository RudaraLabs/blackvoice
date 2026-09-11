# Configuration

Configuration lives at `~/.config/blackvoice/config.json`. It is created with
defaults on first run.

```bash
blackvoice config           # print the current configuration
blackvoice config --path    # print the file path
blackvoice config --reset   # restore the defaults
```

> **After upgrading:** your existing config is never overwritten, so new default
> settings — including new entries in `safety.blocked_patterns` — do not reach
> it. Merge them by hand or run `blackvoice config --reset`.

## Environment overrides

Any value can be overridden by an environment variable named
`BLACKVOICE_<SECTION>_<KEY>`:

```bash
BLACKVOICE_SPEECH_MODE=offline BLACKVOICE_AI_PROVIDER=none blackvoice
```

Useful in the systemd unit:

```ini
[Service]
Environment=BLACKVOICE_SPEECH_MODE=offline
Environment=BLACKVOICE_UI_ENABLED=false
```

Booleans accept `1/0`, `true/false`, `yes/no`, `on/off`. Lists are
comma-separated. A value that will not parse is ignored with a warning rather
than crashing the assistant.

---

## `speech` — recognition

```jsonc
"speech": {
  "mode": "hybrid",
  "model_en": "vosk-model-small-en-us-0.15",
  "model_hi": "vosk-model-small-hi-0.22",
  "language": "both",
  "fallback_confidence": 0.55,
  "online_timeout": 6.0,
  "auto_download": true
}
```

| Key | Default | What it does |
|---|---|---|
| `mode` | `hybrid` | `offline` — Vosk only, nothing ever leaves the machine. `online` — cloud only. `hybrid` — Vosk first, cloud only when unsure. |
| `language` | `both` | `en`, `hi`, or `both`. With `both`, two models transcribe the same audio and the more confident wins — this is what makes Hinglish work. |
| `fallback_confidence` | `0.55` | Below this Vosk score, `hybrid` retries online. Raise it to use the cloud more, lower it to use it less. |
| `model_en` / `model_hi` | small models | A bare name resolves under `~/.local/share/blackvoice/models`; an absolute path is used as-is. |
| `online_timeout` | `6.0` | Seconds to wait on the cloud recogniser. |
| `auto_download` | `true` | Fetch the models on first run when they are missing. Set to `false` on a metered connection and run `blackvoice setup` yourself. |

Nothing is downloaded when `mode` is `"online"` — that configuration never uses
a local model.

**Privacy:** set `mode` to `"offline"` and no audio is ever sent anywhere. In
`hybrid`, audio only leaves the machine when Vosk is unsure *and* you are online.

**Using a larger model** — the small models are ~50 MB and tuned for commands.
For better accuracy, download a larger one and point at it:

```jsonc
"model_en": "/home/you/models/vosk-model-en-us-0.22"
```

Loading two large models doubles the memory cost, so consider
`"language": "en"` if you do.

## `wake` — the wake word

```jsonc
"wake": {
  "enabled": true,
  "phrases": ["black", "blek", "blak"],
  "hotkey": "Ctrl+Alt+Space",
  "chime": true
}
```

| Key | Default | What it does |
|---|---|---|
| `enabled` | `true` | Turn off to use only the tray icon and text input. |
| `phrases` | three spellings of “black” | Anything in this list activates it. The extra spellings catch how the recogniser writes the word. |
| `hotkey` | `Ctrl+Alt+Space` | **Display only.** Black Voice does not grab keys — bind this in your desktop's keyboard settings. |
| `chime` | `true` | Short beep when it starts listening. |

### False triggers

A single short word is a weak wake word. “black” is close enough to **back**,
**block**, **blank**, **lack** and **slack** that ordinary conversation can set
it off. A two-word trigger is far more reliable:

```jsonc
"phrases": ["hey black", "ok black"]
```

## `audio` — the microphone

```jsonc
"audio": {
  "sample_rate": 16000,
  "block_size": 8000,
  "input_device": null,
  "silence_threshold": 0.012,
  "silence_timeout": 1.2,
  "max_command_seconds": 12.0
}
```

| Key | Default | What it does |
|---|---|---|
| `input_device` | `null` | System default. Use `blackvoice devices` to find an index. |
| `silence_threshold` | `0.012` | Loudness below this counts as silence. Raise it in a noisy room, lower it if quiet speech gets cut off. |
| `silence_timeout` | `1.2` | Seconds of silence that end a command. Raise it if it cuts you off mid-sentence. |
| `max_command_seconds` | `12.0` | Hard cap on one utterance. |
| `sample_rate` | `16000` | What the Vosk models expect. Changing it breaks recognition. |

## `voice` — speech output

```jsonc
"voice": {
  "engine": "auto",
  "rate": 165,
  "volume": 0.9,
  "voice_en": "en-us",
  "voice_hi": "hi",
  "piper_model": ""
}
```

`engine` is `auto` by default and picks the best available: **piper** (neural,
needs a voice model), then **espeak-ng** (tiny, instant, speaks Hindi), then
**spd-say**, then **pyttsx3**. Set it explicitly to force one, or `"none"` to
print replies instead of speaking them.

Hindi text is detected by its Devanagari characters and spoken with `voice_hi`.

```bash
blackvoice say "testing one two three"
```

For piper, set `piper_model` to the absolute path of a `.onnx` voice.

## `ai` — the question-answering backend

```jsonc
"ai": {
  "provider": "ollama",
  "ollama_url": "http://localhost:11434",
  "ollama_model": "llama3.2",
  "anthropic_model": "claude-opus-5",
  "openai_model": "gpt-4o-mini",
  "api_key": "",
  "max_tokens": 512,
  "timeout": 30.0,
  "system_prompt": "..."
}
```

### Ollama (default, local)

```bash
ollama pull llama3.2
```

Nothing leaves the machine. If Ollama is not running you get a clear message
telling you to start it.

### Claude

```jsonc
"ai": { "provider": "anthropic", "anthropic_model": "claude-opus-5" }
```

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
```

An `ant auth login` profile works too — leave the key unset and the SDK finds it.
Requests use `effort: "low"`, because a spoken answer should be quick and short.

### OpenAI

```jsonc
"ai": { "provider": "openai", "openai_model": "gpt-4o-mini" }
```

```bash
export OPENAI_API_KEY=sk-...
```

### Off

```jsonc
"ai": { "provider": "none" }
```

Unrecognised commands then say so instead of being answered.

> **Keep keys out of the config file.** `api_key` exists for awkward setups, but
> the environment variables above are read automatically and are the better
> place. The config file is world-readable on most systems.

The assistant remembers the last six turns for context. Clear it from the tray
menu → *Clear AI conversation*.

## `safety` — the shell guard

```jsonc
"safety": {
  "confirm_shell": true,
  "blocked_patterns": ["..."],
  "shell_timeout": 20.0,
  "max_output_chars": 2000
}
```

| Key | Default | What it does |
|---|---|---|
| `confirm_shell` | `true` | Ask before running anything that is not read-only. **Leave this on.** |
| `blocked_patterns` | 10 patterns | Regexes that are refused outright, confirmation or not. |
| `shell_timeout` | `20.0` | Kill a command that runs longer. |
| `max_output_chars` | `2000` | Truncate output shown back to you. |

Turning `confirm_shell` off does **not** disable the deny-list — destructive
commands are still refused. Read **[Security Model](Security-Model)** before
changing anything here.

## `ui` — tray and overlay

```jsonc
"ui": {
  "enabled": true,
  "overlay_timeout": 8.0,
  "theme": "light",
  "show_notifications": true
}
```

Set `enabled` to `false` (or run `blackvoice run --no-ui`) for headless
operation. `overlay_timeout` is how long the popup stays after a reply.

## `skills` — per-skill preferences

```jsonc
"skills": {
  "weather_city": "",
  "search_url": "https://duckduckgo.com/?q={query}",
  "browser": "",
  "terminal": "",
  "file_manager": "",
  "editor": ""
}
```

`weather_city` pins the weather instead of geolocating by IP. The four
application fields override auto-detection, so `open browser` opens the one you
actually want:

```jsonc
"browser": "firefox",
"terminal": "alacritty",
"editor": "code"
```

For a different search engine, keep the `{query}` placeholder:

```jsonc
"search_url": "https://www.google.com/search?q={query}"
```

## Where things live

| Path | Contents |
|---|---|
| `~/.config/blackvoice/config.json` | this file |
| `~/.local/share/blackvoice/models/` | speech models |
| `~/.local/share/blackvoice/notes.md` | your notes |
| `~/.cache/blackvoice/blackvoice.log` | rotating log, 1 MB × 3 |

These follow `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `XDG_CACHE_HOME` when set.
