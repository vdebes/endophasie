# Lab notes — building 100% local dictation in one session

Raw logbook, in the order things actually happened (2026-09-27). Source
material for a tutorial, not the tutorial itself. Each pitfall points to
the commit that fixed it: `git log` tells the same story with diffs.

## Test machine

- Linux Mint 22.1, Cinnamon 6.4, **X11**, encrypted home directory (ecryptfs)
- NVIDIA RTX 4060 Laptop, 8 GB VRAM, driver 580 (CUDA 13.0 on the driver side)
- No system CUDA toolkit (`nvcc` absent), and none is needed
- 30 GB RAM, **no swap** (this matters, see the freeze below)
- Mic: HyperX SoloCast, PipeWire 1.0.5
- Four keyboard layouts configured: fr azerty, fr lafayette, us, fr ergol

## Steps

1. The only `sudo` step: `sudo apt install xdotool` (xclip was already there).
2. Isolated project:
   ```sh
   uv init --python 3.12
   uv add faster-whisper nvidia-cublas-cu12 nvidia-cudnn-cu12
   ```
   → `.venv/` = 2.6 GB (faster-whisper 1.2.1, CTranslate2 4.8.2, cuBLAS 12.9, cuDNN 9.26).
   Python 3.12 rather than the latest, as GPU libraries often lag behind.
3. GPU check: `uv run python -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())"` → `1`
4. First load of `large-v3-turbo`: 1.6 GB download into `~/.cache/huggingface/`, offline afterwards.
5. `dictate` (toggle script) + `transcribe.py`, symlinked into `~/.local/bin/`.
6. Cinnamon shortcut `Ctrl+Alt+D` through dconf (`scripts/cinnamon-shortcut.sh`), later replaced
   by one shortcut per language (`Ctrl+Alt+F` French, `Ctrl+Alt+E` English).
   `Super+D` is already taken (show desktop).
7. Resident server: `server.py` (Unix socket, mode 600) + `client.py` (stdlib only) +
   `dictate-server.service` (systemd user unit). Started by `dictate` **when recording starts**,
   so the model loads while you speak; exits after 10 idle minutes (frees ~2 GB of VRAM).
8. Insertion by paste (xclip + `Ctrl+V`, or `Ctrl+Shift+V` in a terminal), clipboard restored.
9. Settings in `~/.config/dictate/env`, read by both the script and the systemd unit.

## Pitfalls

- **`libcublas.so.12 is not found`** — the NVIDIA wheels live in `.venv/`, where the
  dynamic loader does not look. Fix: `LD_LIBRARY_PATH=<site-packages>/nvidia/{cublas,cudnn}/lib`,
  set by `dictate`. *(commit "Add dictate")*
- **Hallucination on silence** — 3 s of silence came back as "Sous-titrage ST' 501": Whisper
  was trained largely on film subtitles. Fix: `vad_filter=True`. Verified: 3 s without speech → "".
- **ydotool rejected** — it sends US-QWERTY keycodes, so text is scrambled on AZERTY/Ergo-L,
  accents are unreliable, and it requires access to `/dev/uinput` (system-wide keystroke
  injection). xdotool (X11) and wtype (Wayland) send characters, not keycodes.
- **"No network call" was false at first** — loading a model by name makes huggingface_hub
  check the Hub for a new revision on every load. Fix: `HF_HUB_OFFLINE=1`.
  *(commit "Force HF_HUB_OFFLINE")*
- **Machine freeze, hard reset needed** — key auto-repeat launched the script dozens of times
  per second → 18 transcriptions at once × 1.4 GB ≈ 25 GB, no swap → OOM, frozen desktop.
  Diagnosed from `journalctl -b -1 -k` (the OOM killer's task dump). Fixes: `flock` (one
  instance), 1 s debounce, cgroup memory cap (`systemd-run -p MemoryMax=3G`, `MemoryMax=` in
  the unit). Regression test: `tests/burst.sh`.
  **Lesson: always cap the RAM of a local model launched from a keyboard shortcut.**
  *(commit "Fix machine freeze")*
- **Forked processes inherit file descriptors** — `pw-record` and later the `xclip` daemon
  would have kept the lock held (`9>&-` removes it). Otherwise the next call is silently
  ignored. Any process that outlives the script must be started without the lock fd.
- **Silent shortcut after the reboot** — the binding had been written straight into dconf.
  Cinnamon's source (`js/ui/keybindings.js`) shows it only re-reads custom bindings on a
  `changed::custom-list` signal, so emptying and rewriting that list fixes it. `__dummy__`
  is skipped by Cinnamon; it was a red herring. Same cause the second time, after renaming
  the command. *(commits "Add Cinnamon shortcut script" and "Correct the shortcut fix")*
- **`xdotool key` is not a reliable shortcut test** — a synthetic `ctrl+alt+d` stopped
  firing the binding while real key presses worked every time. Test with your fingers.
- **Only the first word typed** — `xdotool type --delay 0` is too fast; apps drop the rest.
  Found with content-free counters in `stats.log` (17 words transcribed, 1 on screen).
  12 ms (xdotool's default) fixes it… at 1.7 s for 135 characters, hence the paste later.
- **A faster server re-opened the debounce hole** — transcription released the lock before
  the stop key was released, so auto-repeat started a new recording. Hence the debounce after
  a stop, too. Caught by `tests/burst.sh`. *(commit "Debounce after stop too")*
- **Tests need testing** — the first burst test hung (`jobs -p` under zsh made `wait` block on
  the monitor loop), counted its own command line in `pgrep -f`, then passed while one of its
  checks said "0 instead of 1". A test that prints OK is not the same as a test that checks.

- **Language: forcing it translates, detecting it hears the accent** — `DICTATE_LANG=fr`
  turned English speech into French. Restricting auto-detection to `fr,en` did not help:
  Whisper's language ID gave fr = 1.00 / en = 0.00 on English spoken with a French accent,
  yet a one-word "Seriously?" came out in English. Fix: one shortcut per language
  (`Ctrl+Alt+F` / `Ctrl+Alt+E`). *(commit "Pick the language per shortcut")*
- **Stale socket after a restart** — SIGTERM killed the server without running its cleanup;
  the leftover socket looked like a ready server while the new one was still loading →
  ConnectionRefused. Fix: SIGTERM handler + client retry. *(commit "Fix stale socket")*
- **Freeze your benchmark input** — a temporary option kept the last recording for
  measurements; two new dictations during the benchmark silently replaced it, and one
  simulation compared a new recording against the old one's reference (112% "difference").
  Copy the file aside before measuring.

## Tried and rolled back: live mode (text pasted while speaking)

Built and tested the same day, then reverted at the user's request (code kept in a local
`git stash`, not in the history).

- **Design** — `streamer.py` followed the growing WAV, cut it at speech pauses (Silero VAD,
  300 ms), sent each chunk to the server with the text so far as `initial_prompt`, and pasted
  it into the window that had focus at start (held back if focus moved).
- **What worked** — 80 s of speech in 8 chunks, **final wait 67 ms** (vs ~6 s in one block).
- **What killed it: ellipses.** Each chunk ends where the speaker paused, often mid-sentence.
  Whisper, trained on subtitles, closes an unfinished sentence with "…". Every hesitation
  became a cut, every cut a "…". In one-block mode it sees whole sentences and punctuates
  them properly. The offline simulation had compared *words* only, not punctuation, so it
  could not see this. Measure what the user will read.
- **Word by word rejected before coding** — pasted text cannot be revised, while spoken
  thought is full of restarts; freezing words early is the wrong trade-off.
- **Also learned** — without the "⏳ Transcribing…" notification on stop, the user could no
  longer tell whether the mic was open. Visible state matters as much as speed.
- **Worth retrying** — cut only on *long* pauses (≥ 0.7–1 s), which are more likely sentence
  ends; hypothesis, not measured.

## Pause mode (2026-10-02): the retry that worked

The live-mode code, taken back from the stash, with one change of principle: cut only on
a **deliberate** pause (`DICTATE_PAUSE`, seconds), never on hesitations, and no forced cut
after 15 s of continuous speech (that one also split sentences).

- **Two uses, one setting** — `DICTATE_AFTER_PAUSE=continue` keeps the mic open (headset,
  away from the keyboard) with a safety close after `DICTATE_MIC_IDLE` s without speech;
  `stop` closes it after the first paste (at the keyboard: typing noise is not transcribed).
- **VAD on the tail only** — the buffer can hold minutes of speech between two long pauses;
  Silero runs on the last `PAUSE + 2` s at each poll, the whole buffer only after the loop
  was busy transcribing. 0.3 s kept after the last word: long trailing silences invite
  hallucinations.
- **When the streamer closes the mic itself**, it also removes `rec.pid`: a stale pid could
  be reused by an unrelated process, which the next shortcut would then SIGINT. It deletes
  the WAV only if it is still the file it read (same inode), not a new recording.
- **Testing without a mic** — a fake `pw-record` replaying a speech file with scripted
  silences, in a separate `XDG_RUNTIME_DIR` (socket symlinked). First run "failed": the
  excerpt had a real 6 s gap of its own. Map the test audio with the VAD first.
- **Real dictation** — 5 s, then 4 s: hesitations did not cut, no "…" seen; final wait
  0.7–0.9 s on 11–41 s of speech. Kept at 4 s.

## CPU mode (2026-10-02)

The fallback for machines without an NVIDIA GPU (AMD included), never run until now. Forced
with `DICTATE_DEVICE=cpu` on the test machine (20 cores), `small` model, int8, on a 15 s
English speech clip.

- **Works**: matches the GPU transcription of the same passage, apart from a comma and the
  last word, cut off by the end of the clip.
- **Warm server**: 3.3–3.9 s per request (vs ~0.9 s on the GPU for 13 s); load 2.5 s; ~740 MB
  of RAM. One-shot `transcribe.py` (fallback path, model loaded each time): ~6 s.
- **Found on the way: a fresh install cannot get its model.** `dictate` sets
  `HF_HUB_OFFLINE=1`, so the first dictation fails with `LocalEntryNotFoundError` instead of
  downloading, contrary to what the README said. It never showed here because
  `large-v3-turbo` was downloaded before offline mode was forced. Same for `small`: the
  first CPU run had to be done without `HF_HUB_OFFLINE`. To fix in the install script
  (download the model once, explicitly).
- **Still heavy on a CPU-only machine**: `uv sync` installs the CUDA wheels anyway (they are
  plain dependencies), so 2.6 GB of `.venv/` for nothing.

## Measurements

- Model load (cached): 2.8 s · transcription of 3 s of audio: 0.8 s
- Server cold start: ~2.7 s · requests on a warm server: ~80 ms (silence) to ~0.9 s (13 s of speech)

Wait after the second key press (from `stats.log`: counters only, never the text):

| Version | Speech | Transcription | Insertion | Wait |
|---|---|---|---|---|
| v1 load every time, typing at 12 ms | 7 s | ~3 s | ~1.3 s | ~4.5 s |
| v2 resident server, typing at 12 ms | 13 s | 0.91 s | 1.67 s | 2.6 s |
| v3 resident server + paste | 5 s | 0.49 s | 0.11 s | **0.6 s** |

User verdict: v1 and v2 "slower than typing"; v3 "YES! it's faster". Later, dictating this
project's own chat messages: "works very well".

Transcription time grows with audio length: 0.5 s for 5 s, 0.9 s for 13 s, **6.3 s for 161 s**.
Long journal entries still wait several seconds at the end.

### beam_size (157 s recording, read aloud)

| beam | time | words |
|---|---|---|
| 5 | 6.15 s | 469 |
| 1 | 4.58 s (−25%) | 467 |

6 differences; against the source text beam 1 was right 3 times, wrong once. → default 1.

### Transcribing while speaking (simulation)

Replayed the recording as a live stream: cut at speech pauses, transcribe each chunk as soon
as it ends, previous text passed as `initial_prompt`.

| Recording | Wait today | Chunked (best setting) | Words differing from one-block |
|---|---|---|---|
| 157 s | 6.2 s | 1.6 s (pauses ≥ 0.5 s, chunks ≥ 5 s) | 3.4% |
| 37 s | 1.8 s | 0.6 s (pauses ≥ 0.3 s, chunks ≤ 8 s) | 5.4% |

The limit is the speaker, not the GPU: reading aloud leaves few pauses (3 in 37 s), so the
last chunk stays long. A sliding window with "stable prefix" commits (what online services
do) would make the wait constant, at the cost of complexity and continuous GPU use.
Next: implement chunking, show each chunk as it lands, measure on real journal dictation.

## Privacy

- Audio recorded to `$XDG_RUNTIME_DIR` (tmpfs, RAM, mode 700), deleted after transcription.
- `HF_HUB_OFFLINE=1`: no network call after the initial model download.
- Diagnostics log counters, never content.

## Untested

- Wayland / `wtype` (and paste on Wayland: `wl-copy`), AMD GPUs (CPU mode only tested on an
  NVIDIA machine, forced), French on the CPU `small` model.
- Restoring an image from the clipboard (lost: only text is restored).
