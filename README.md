# endophasie

**100% local voice dictation for Linux. Whisper runs on your own GPU — your voice never leaves your machine.**

> [!WARNING]
> **endophasie is an experimental project**, built as a hands-on exercise and
> tested on a single machine. It is meant to be read, learned from and hacked on.
> **Looking for a mature, cross-platform, ready-to-use solution?** Use
> [Kieirra/murmure](https://github.com/Kieirra/murmure) instead.

*Endophasia* is the word for inner speech, the dialogue you hold in your
own head. This tool lets you speak it out loud to your computer with no
one else listening: no cloud, no account, no network call once the
model is downloaded.

Press a shortcut, speak, press it again: the text appears in whatever
window has focus (terminal, editor, browser, notes app). One shortcut per
language: `Ctrl+Alt+F` for French, `Ctrl+Alt+E` for English (see below why).

## How it works

```
Ctrl+Alt+F ──► pw-record ──► $XDG_RUNTIME_DIR/dictate/rec.wav   (RAM only)
   │               (while you speak, the server loads the model)
Ctrl+Alt+F ──► client.py ──► server.py (faster-whisper, GPU) ──► text
                                  └─► clipboard + Ctrl+V / Ctrl+Shift+V
```

- **`dictate`** — the whole user-facing tool: a toggle bound to a keyboard shortcut.
- **`server.py`** — keeps Whisper `large-v3-turbo` in GPU memory, serves a
  Unix socket (mode 600). Started when you *start* recording, so the model
  loads while you talk; exits after 10 idle minutes to free the VRAM.
- **`client.py`** — standard library only, starts in milliseconds.
- **`transcribe.py`** — the actual transcription; also used as a fallback
  when the server is unavailable.
- **`streamer.py`** — pause mode (optional, below): follows the recording
  and pastes what you said each time you pause long enough.

Typical wait after the second key press: **~0.6 s** for a short sentence
(0.5 s transcription + 0.1 s paste, RTX 4060 Laptop).

### Pause mode: see your text without stopping

By default the text arrives in one block when you press the shortcut
again. With `DICTATE_PAUSE=4`, a silence of 4 seconds pastes what you
have said so far, and you keep talking. Shorter pauses (hesitations,
looking for a word) do not cut anything. Each piece is transcribed with
the text before it as context, so style and punctuation carry over.

- **The text stays where you started.** If you switch to another window,
  it is held back and pasted when you come back, never into the browser
  or the mail client you switched to. If the dictation ends first, it is
  left in the clipboard (with a notification).
- **Away from the keyboard** (`DICTATE_AFTER_PAUSE=continue`, the
  default): the mic stays open after each paste, e.g. with a headset
  across the room, and closes on its own after `DICTATE_MIC_IDLE`
  seconds without speech (default: 30).
- **At the keyboard** (`DICTATE_AFTER_PAUSE=stop`): the mic closes after
  the first paste, so typing noise cannot be transcribed afterwards.
- The shortcut stops it at any time, in both modes.

Why 4 seconds and not less: cutting at every short pause (300 ms) was
tried first and rolled back, because Whisper closed each half-sentence
with "…". A pause long enough to be deliberate usually ends a sentence.

## Requirements

- Linux with an **X11** session and **PipeWire** (`pw-record`)
- `xdotool`, `xclip`, `xprop`; `notify-send` (optional)
- [`uv`](https://docs.astral.sh/uv/)
- An **NVIDIA GPU with its driver** (tested: 8 GB VRAM). No CUDA toolkit
  needed: cuBLAS/cuDNN are installed as Python wheels inside `.venv/`.
  Without a GPU, it falls back to the CPU with the `small` model (slower,
  untested).
- ~4.5 GB of disk: 2.6 GB for `.venv/`, 1.6 GB for the model.

On Debian/Ubuntu/Mint: `sudo apt install xdotool xclip x11-utils`

## Install

```sh
git clone https://github.com/vdebes/endophasie.git && cd endophasie
uv sync                                   # creates .venv/ (downloads ~2.6 GB)
ln -s "$PWD/dictate" ~/.local/bin/dictate
mkdir -p ~/.config/systemd/user
ln -s "$PWD/dictate-server.service" ~/.config/systemd/user/
systemctl --user daemon-reload
scripts/cinnamon-shortcut.sh '<Primary><Alt>f' fr   # Cinnamon: French
scripts/cinnamon-shortcut.sh '<Primary><Alt>e' en   # Cinnamon: English
```

Other desktops: bind `~/.local/bin/dictate fr` (or any language code) to
a shortcut in your desktop's keyboard settings.

Optional settings in `~/.config/dictate/env`:

```sh
DICTATE_LANG=fr               # language when `dictate` gets no argument (default: auto)
# DICTATE_LANG=fr,en          # detect, but only among these languages
# DICTATE_BEAM=5              # default 1 (~25% faster, same quality in tests)
# DICTATE_MODEL=large-v3-turbo
# DICTATE_INSERT=type         # simulated typing instead of paste
# DICTATE_PAUSE=4             # pause mode: paste after 4 s of silence (default 0: off)
# DICTATE_AFTER_PAUSE=continue  # or stop: close the mic after the first paste
# DICTATE_MIC_IDLE=30         # continue mode: close the mic after 30 s without speech
```

### Why one shortcut per language

Two traps, learned the hard way:

- **Forcing a language translates.** With `DICTATE_LANG=fr`, English
  speech comes out as fluent French: Whisper outputs the forced language
  whatever it hears.
- **Detection hears your accent, not your words.** English spoken with a
  French accent was detected as French with 100% confidence, so
  auto-detection (even restricted to `fr,en`) translated it too, and not
  even consistently.

Choosing the language yourself at the start is the only reliable option.

The first dictation downloads the model (~1.6 GB) into
`~/.cache/huggingface/`. After that, everything runs offline
(`HF_HUB_OFFLINE=1` is enforced).

## Privacy

- Audio is recorded to `$XDG_RUNTIME_DIR` (tmpfs, i.e. RAM, mode 700)
  and deleted right after transcription.
- The transcript is never written anywhere; it goes to the clipboard
  just long enough to be pasted, then your previous clipboard content
  is restored (text only).
- `stats.log` holds counters (durations, word counts) for diagnostics,
  never content.

## Safety

The transcription runs under a cgroup memory cap (`MemoryMax=3G`), with a
lock and a debounce against key auto-repeat. These exist because the
first version froze the author's machine: a held-down key launched 18
transcriptions at once. `tests/burst.sh` replays that scenario.

## Status

| | |
|---|---|
| Linux Mint 22.1, Cinnamon, X11, NVIDIA | ✅ daily use |
| Pause mode (X11) | ✅ tested on real dictation (4 s and 5 s pauses) |
| Wayland (`wtype`) | ⚠️ written, untested (paste not yet ported) |
| CPU-only | ⚠️ written, untested |
| AMD GPUs | ❌ not supported by CTranslate2 as far as I know; CPU fallback |

## Next

- **Pause mode with a Bluetooth headset**, away from the PC: untested.
  The headset mic switches to its lower-quality "call" profile, must be
  the default source for `pw-record`, and a locked screen leaves no
  window to paste into.

## Lab notes

Every pitfall hit while building this (freeze, silent shortcut, lost
words, a lock leaked through a forked daemon…) is in
[`docs/lab-notes.md`](docs/lab-notes.md), and in the commit messages:
the git history is meant to be read.

## Alternatives

[Kieirra/murmure](https://github.com/Kieirra/murmure) is a mature,
cross-platform local speech-to-text tool with LLM post-processing: the
recommended choice for a turnkey setup. endophasie takes the other road:
a small, readable, Linux-only experiment where every pitfall is documented.

## License

[AGPL-3.0-or-later](LICENSE). Built with the help of Claude Code.
