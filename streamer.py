"""Pause mode: show what you said each time you pause long enough (X11).

Usage: streamer.py <rec.wav> <recorder pid> [lang]

Started by `dictate` together with pw-record when DICTATE_PAUSE > 0.
Follows the WAV file as it grows. Short pauses (hesitations) do not cut:
only DICTATE_PAUSE seconds of silence send what was said since the last
cut to the server, with the text so far as context, and paste the result
into the window that had focus when recording started.

Why long pauses only: cutting at every 300 ms pause (tried 2026-09-27)
split sentences in the middle, and Whisper closed each piece with "…".

On SIGUSR1 (sent by dictate on stop), or if the recorder dies, it
transcribes what is left, pastes it, restores the clipboard and exits.
If focus moved to another window, text is held back instead of landing
there: pasted when focus comes back, else left in the clipboard at the end.

Settings (environment or ~/.config/dictate/env):
  DICTATE_PAUSE         silence (s) that shows the text; 0 (default) = off,
                        one block after you stop (checked by dictate)
  DICTATE_AFTER_PAUSE   continue (default): the mic stays open after the
                        text is shown; stop: the mic closes
  DICTATE_MIC_IDLE      continue mode: close the mic after this many
                        seconds without speech (default: 30)
  DICTATE_DRYRUN=1      print chunks instead of pasting (tests)
"""

import os
import signal
import subprocess
import sys
import time
import wave

import numpy as np
from faster_whisper.vad import VadOptions, get_speech_timestamps

from client import request

SR = 16000
RUN = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "dictate")
CHUNK_WAV = os.path.join(RUN, "chunk.wav")
REC_PID = os.path.join(RUN, "rec.pid")
NOTIF = os.path.join(RUN, "notify.id")
PAUSE_S = float(os.environ.get("DICTATE_PAUSE", "0"))
AFTER_PAUSE = os.environ.get("DICTATE_AFTER_PAUSE", "continue")
MIC_IDLE_S = float(os.environ.get("DICTATE_MIC_IDLE", "30"))
TAIL_S = PAUSE_S + 2      # VAD only looks at the end of the buffer: cheap even after minutes
PAD = SR * 3 // 10        # 0.3 s kept after the last word; long silences invite hallucinations
POLL_S = 0.25
DRYRUN = bool(os.environ.get("DICTATE_DRYRUN"))
TERMINALS = ("terminator", "terminal", "kitty", "alacritty", "konsole", "xterm",
             "tilix", "wezterm", "ghostty")

stopping = False


def on_stop(*_):
    global stopping
    stopping = True


def log(msg: str) -> None:
    print(f"{time.strftime('%T')} streamer: {msg}", file=sys.stderr, flush=True)


def run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def notify(msg: str, timeout_ms: int = 2000) -> None:
    """Replaces dictate's "recording" notification (same replace-id)."""
    try:
        old = open(NOTIF).read().strip()
    except FileNotFoundError:
        old = ""
    nid = run(["notify-send", "-p", "-t", str(timeout_ms), *(["-r", old] if old else []),
               "-a", "dictate", "Dictation", msg]).strip()
    if nid:
        with open(NOTIF, "w") as f:
            f.write(nid)


def set_clipboard(text: str) -> None:
    # xclip forks a daemon that serves the selection and inherits our pipes:
    # capturing its output would block until someone else copies something.
    subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class WavTail:
    """Reads the samples pw-record appends to a WAV file that is still being
    written (the header's size fields are not final yet, so they are ignored)."""

    def __init__(self, path: str):
        self.path, self.f, self.rest = path, None, b""

    def read(self) -> np.ndarray:
        if self.f is None:
            try:
                self.f = open(self.path, "rb")
            except FileNotFoundError:
                return np.zeros(0, np.float32)
            head = self.f.read(4096)
            i = head.find(b"data")
            if i < 0:                       # header not fully written yet
                self.f.close()
                self.f = None
                return np.zeros(0, np.float32)
            self.f.seek(i + 8)              # "data" + 4-byte size
        raw = self.rest + self.f.read()
        cut = len(raw) - len(raw) % 2       # int16 samples: keep a stray byte
        self.rest = raw[cut:]
        return np.frombuffer(raw[:cut], np.int16).astype(np.float32) / 32768


def speech_end(audio: np.ndarray) -> int | None:
    """Sample index where the last speech in `audio` ends, None if silent."""
    if len(audio) == 0:
        return None
    sp = get_speech_timestamps(
        audio, VadOptions(min_silence_duration_ms=500, speech_pad_ms=100))
    return sp[-1]["end"] if sp else None


class Paster:
    """Pastes into the window that had focus at start, via the clipboard,
    and gives the clipboard its previous (text) content back at the end."""

    def __init__(self):
        self.win = run(["xdotool", "getactivewindow"]).strip()
        cls = run(["xprop", "-id", self.win, "WM_CLASS"]).lower() if self.win else ""
        self.key = "ctrl+shift+v" if any(t in cls for t in TERMINALS) else "ctrl+v"
        self.saved = None if DRYRUN else (
            subprocess.run(["xclip", "-o", "-selection", "clipboard"],
                           capture_output=True, text=True).stdout or None)
        self.pending: list[str] = []
        self.pasted = False

    def add(self, text: str) -> None:
        self.pending.append(text)
        self.flush()

    def flush(self) -> None:
        if not self.pending:
            return
        text = " ".join(self.pending)
        if self.pasted:
            text = " " + text                     # space between chunks
        if DRYRUN:
            print(text, flush=True)
        else:
            if run(["xdotool", "getactivewindow"]).strip() != self.win:
                return                            # focus moved: hold back
            set_clipboard(text)
            run(["xdotool", "key", "--clearmodifiers", self.key])
            time.sleep(0.3)                       # let the app read the clipboard
        self.pending.clear()
        self.pasted = True

    def close(self) -> bool:
        """True if everything was pasted; else the held-back text is left
        in the clipboard."""
        self.flush()
        if DRYRUN:
            return True
        if self.pending:
            set_clipboard(" ".join(self.pending))
            return False
        if self.saved is not None:
            set_clipboard(self.saved)
        return True


def close_mic(rec_pid: int, reason: str) -> None:
    """Stop the recording ourselves (no key press): SIGINT finalizes the WAV,
    and rec.pid goes away so the next shortcut starts a new recording
    instead of signalling a pid the system may have reused."""
    try:
        os.kill(rec_pid, signal.SIGINT)
    except ProcessLookupError:
        pass
    try:
        if open(REC_PID).read().strip() == str(rec_pid):
            os.unlink(REC_PID)
    except FileNotFoundError:
        pass
    log(f"mic closed: {reason}")


def main() -> int:
    wav_path, rec_pid = sys.argv[1], int(sys.argv[2])
    lang = sys.argv[3] if len(sys.argv) > 3 else ""
    if PAUSE_S <= 0:
        return 0
    signal.signal(signal.SIGUSR1, on_stop)
    tail, paster = WavTail(wav_path), Paster()
    buf = np.zeros(0, np.float32)
    heard = False                     # buf holds speech not sent yet
    last_voice = time.monotonic()     # for DICTATE_MIC_IDLE
    self_closed = ""                  # why we closed the mic, if we did
    words, chunks, audio_s, t_stop = 0, 0, 0.0, None
    context = ""

    def emit(chunk: np.ndarray) -> None:
        nonlocal words, chunks, context
        with wave.open(CHUNK_WAV, "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(SR)
            w.writeframes((np.clip(chunk, -1, 1) * 32767).astype(np.int16).tobytes())
        try:
            text = request(CHUNK_WAV, lang, context[-300:]).strip()
        except Exception as e:                    # keep going: next chunk may work
            log(f"chunk failed: {e}")
            return
        if text:
            paster.add(text)
            context = f"{context} {text}".strip()
            words += len(text.split())
            chunks += 1

    while True:
        new = tail.read()
        buf = np.concatenate([buf, new])
        audio_s += len(new) / SR
        recorder_gone = not os.path.exists(f"/proc/{rec_pid}")
        if stopping or recorder_gone:
            t_stop = time.monotonic()
            buf = np.concatenate([buf, tail.read()])      # last bytes after SIGINT
            end = speech_end(buf)
            if end is not None:
                emit(buf[:end + PAD])
            break
        now = time.monotonic()
        if len(buf) >= SR:
            start = max(0, len(buf) - int(TAIL_S * SR))
            end = speech_end(buf[start:])
            if end is not None:
                end += start
                heard = True
                last_voice = max(last_voice, now - (len(buf) - end) / SR)
            elif heard:
                # Silence longer than the window we look at: the loop was
                # busy (transcribing); find the end over the whole buffer.
                end = speech_end(buf)
            if heard and end is not None and len(buf) - end >= PAUSE_S * SR:
                if AFTER_PAUSE == "stop":     # close first: nothing said during
                    self_closed = "after the pause"   # the transcription gets lost
                    close_mic(rec_pid, self_closed)
                emit(buf[:end + PAD])
                buf, heard = buf[-SR // 2:], False
            elif not heard:
                buf = buf[-SR // 2:]                      # silence only: drop it
        if (not self_closed and AFTER_PAUSE != "stop"
                and now - last_voice >= MIC_IDLE_S):
            self_closed = f"no speech for {MIC_IDLE_S:.0f} s"
            close_mic(rec_pid, self_closed)
        paster.flush()                          # focus may have come back
        time.sleep(POLL_S)

    complete = paster.close()
    if os.path.exists(CHUNK_WAV):
        os.unlink(CHUNK_WAV)
    wait_ms = int((time.monotonic() - t_stop) * 1000)
    with open(os.path.join(RUN, "stats.log"), "a") as f:
        print(f"{time.strftime('%T')} pause={PAUSE_S:g}s audio={audio_s:.0f}s chunks={chunks} "
              f"words={words} final_wait={wait_ms}ms closed_by={'streamer' if self_closed else 'key'}",
              file=f)
    if not complete:
        notify("📋 Focus changed: text left in the clipboard", 4000)
    elif self_closed:
        # dictate's stop call did not run: its cleanup and "✅ Done" are ours.
        notify(f"⏹️ Mic closed ({self_closed})")
    if self_closed and tail.f is not None:
        # Delete the audio, unless a new recording already replaced the file.
        try:
            if os.stat(wav_path).st_ino == os.fstat(tail.f.fileno()).st_ino:
                os.unlink(wav_path)
        except FileNotFoundError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
