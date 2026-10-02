import struct
import subprocess
import sys
import types

import numpy as np
import pytest

import streamer

SR = streamer.SR


def wav_header() -> bytes:
    # Sizes left at 0, as pw-record does while still recording.
    return (b"RIFF" + struct.pack("<I", 0) + b"WAVEfmt "
            + struct.pack("<IHHIIHH", 16, 1, 1, SR, SR * 2, 2, 16)
            + b"data" + struct.pack("<I", 0))


class TestWavTail:
    def test_missing_file_reads_nothing(self, tmp_path):
        assert len(streamer.WavTail(str(tmp_path / "rec.wav")).read()) == 0

    def test_reads_samples_as_they_are_appended(self, tmp_path):
        path = tmp_path / "rec.wav"
        tail = streamer.WavTail(str(path))
        with open(path, "wb") as f:
            f.write(wav_header())
            f.flush()
            assert len(tail.read()) == 0
            f.write(np.array([16384, -16384], np.int16).tobytes() + b"\x00")  # + half a sample
            f.flush()
            assert tail.read().tolist() == [0.5, -0.5]
            f.write(b"\x40")  # the other half: 0x4000 = 16384
            f.flush()
            assert tail.read().tolist() == [0.5]


class FakeDesktop:
    """Stands in for xdotool/xprop/xclip: which window has focus, what was pasted."""

    def __init__(self, monkeypatch):
        self.active, self.clipboard, self.pasted = "42", "what I had copied", []
        monkeypatch.setattr(streamer, "DRYRUN", False)
        monkeypatch.setattr(streamer, "run", self.run)
        monkeypatch.setattr(streamer, "set_clipboard", self.set_clipboard)
        monkeypatch.setattr(streamer.time, "sleep", lambda s: None)
        monkeypatch.setattr(streamer.subprocess, "run", lambda *a, **k: types.SimpleNamespace(
            stdout=self.clipboard))

    def run(self, cmd):
        if cmd[:2] == ["xdotool", "getactivewindow"]:
            return self.active + "\n"
        if cmd[0] == "xprop":
            return 'WM_CLASS(STRING) = "xed", "Xed"\n'
        if cmd[:2] == ["xdotool", "key"]:
            self.pasted.append((self.clipboard, cmd[-1]))
        return ""

    def set_clipboard(self, text):
        self.clipboard = text


class TestPaster:
    def test_pastes_into_the_start_window_and_restores_the_clipboard(self, monkeypatch):
        desk = FakeDesktop(monkeypatch)
        paster = streamer.Paster()
        paster.add("Première phrase.")
        paster.add("Deuxième.")
        assert desk.pasted == [("Première phrase.", "ctrl+v"), (" Deuxième.", "ctrl+v")]
        assert paster.close() is True
        assert desk.clipboard == "what I had copied"

    def test_holds_text_back_while_focus_is_elsewhere(self, monkeypatch):
        desk = FakeDesktop(monkeypatch)
        paster = streamer.Paster()
        desk.active = "7"  # switched to the browser
        paster.add("Pas dans le navigateur.")
        paster.add("Ni ça.")
        assert desk.pasted == []
        desk.active = "42"  # back in the journal
        paster.flush()
        assert desk.pasted == [("Pas dans le navigateur. Ni ça.", "ctrl+v")]

    def test_text_still_held_at_the_end_is_left_in_the_clipboard(self, monkeypatch):
        desk = FakeDesktop(monkeypatch)
        paster = streamer.Paster()
        desk.active = "7"
        paster.add("Gardé pour plus tard.")
        assert paster.close() is False
        assert desk.clipboard == "Gardé pour plus tard."
        assert desk.pasted == []

    def test_terminals_get_ctrl_shift_v(self, monkeypatch):
        desk = FakeDesktop(monkeypatch)
        monkeypatch.setattr(desk, "run", lambda cmd: 'WM_CLASS = "kitty", "kitty"'
                            if cmd[0] == "xprop" else FakeDesktop.run(desk, cmd))
        monkeypatch.setattr(streamer, "run", desk.run)
        assert streamer.Paster().key == "ctrl+shift+v"


def test_silence_has_no_speech_end():
    assert streamer.speech_end(np.zeros(3 * SR, np.float32)) is None
    assert streamer.speech_end(np.zeros(0, np.float32)) is None


class TestCloseMic:
    @pytest.fixture
    def recorder(self):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        yield proc
        proc.kill()

    def test_stops_the_recorder_and_forgets_its_pid(self, tmp_path, monkeypatch, recorder):
        pid_file = tmp_path / "rec.pid"
        pid_file.write_text(f"{recorder.pid}\n")
        monkeypatch.setattr(streamer, "REC_PID", str(pid_file))
        streamer.close_mic(recorder.pid, "test")
        assert recorder.wait(timeout=5) != 0  # interrupted
        assert not pid_file.exists()

    def test_keeps_the_pid_file_of_a_newer_recording(self, tmp_path, monkeypatch, recorder):
        pid_file = tmp_path / "rec.pid"
        pid_file.write_text("999999\n")  # a new recording already started
        monkeypatch.setattr(streamer, "REC_PID", str(pid_file))
        streamer.close_mic(recorder.pid, "test")
        assert pid_file.read_text() == "999999\n"
