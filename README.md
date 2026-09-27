# endophasie

**100% local voice dictation for Linux. Whisper runs on your own GPU — your voice never leaves your machine.**

*Endophasia* is the word for inner speech, the dialogue you hold in your
own head. This tool lets you speak it out loud to your computer with no
one else listening: no cloud, no account, no network call once the
model is downloaded.

Press a shortcut, speak, press it again: the text appears in whatever
window has focus (terminal, editor, browser, notes app).

## How it works

```
Ctrl+Alt+D ──► pw-record ──► $XDG_RUNTIME_DIR/dictate/rec.wav   (RAM only)
   │               (while you speak, the server loads the model)
Ctrl+Alt+D ──► client.py ──► server.py (faster-whisper, GPU) ──► text
                                  └─► clipboard + Ctrl+V / Ctrl+Shift+V
```

- **`dictate`** — the whole user-facing tool: a toggle bound to a keyboard shortcut.
- **`server.py`** — keeps Whisper `large-v3-turbo` in GPU memory, serves a
  Unix socket (mode 600). Started when you *start* recording, so the model
  loads while you talk; exits after 10 idle minutes to free the VRAM.
- **`client.py`** — standard library only, starts in milliseconds.
- **`transcribe.py`** — the actual transcription; also used as a fallback
  when the server is unavailable.

Typical wait after the second key press: **~0.6 s** for a short sentence
(0.5 s transcription + 0.1 s paste, RTX 4060 Laptop).

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
scripts/cinnamon-shortcut.sh              # Cinnamon: binds Ctrl+Alt+D
```

Other desktops: bind `~/.local/bin/dictate` to a shortcut in your
desktop's keyboard settings.

Optional settings in `~/.config/dictate/env`:

```sh
DICTATE_LANG=fr               # recommended: faster and more reliable than auto-detect
# DICTATE_MODEL=large-v3-turbo
# DICTATE_INSERT=type         # simulated typing instead of paste
```

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
| Wayland (`wtype`) | ⚠️ written, untested (paste not yet ported) |
| CPU-only | ⚠️ written, untested |
| AMD GPUs | ❌ not supported by CTranslate2 as far as I know; CPU fallback |

## Lab notes

Every pitfall hit while building this (freeze, silent shortcut, lost
words, a lock leaked through a forked daemon…) is in
[`docs/lab-notes.md`](docs/lab-notes.md), and in the commit messages:
the git history is meant to be read.

## Alternatives

[Kieirra/murmure](https://github.com/Kieirra/murmure) is an established,
cross-platform local speech-to-text tool with LLM post-processing. If you
want something ready-made rather than a small, readable script to learn
from and hack on, look there first.

## License

[AGPL-3.0-or-later](LICENSE). Built with the help of Claude Code.
