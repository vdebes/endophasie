"""Transcribe an audio file to text, 100% locally (faster-whisper).

Usage: transcribe.py <file.wav> [lang]
The text goes to stdout; diagnostics go to stderr.
Configuration through environment variables (or ~/.config/dictate/env):
  DICTATE_MODEL   Whisper model (default: large-v3-turbo on GPU, small on CPU)
  DICTATE_LANG    "auto" (default), one language code ("fr"), or a list
                  ("fr,en"): the language is then detected but restricted
                  to that list. Beware: a single forced language makes
                  Whisper *translate* speech in any other language into it.
  DICTATE_DEVICE  cuda | cpu (default: cuda if an NVIDIA GPU is visible)
"""

import os
import sys

import ctranslate2
from faster_whisper import WhisperModel, decode_audio


def load_model() -> WhisperModel:
    device = os.environ.get("DICTATE_DEVICE") or (
        "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    )
    default_model = "large-v3-turbo" if device == "cuda" else "small"
    model_name = os.environ.get("DICTATE_MODEL", default_model)
    compute_type = "float16" if device == "cuda" else "int8"
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def pick_language(model: WhisperModel, audio, setting: str) -> str | None:
    """None lets Whisper detect freely; a list restricts detection to it,
    so a two-word clip cannot come out as Dutch for a French speaker."""
    langs = [l.strip() for l in setting.split(",") if l.strip()]
    if setting == "auto" or not langs:
        return None
    if len(langs) == 1:
        return langs[0]
    _, _, probs = model.detect_language(audio, vad_filter=True)
    scores = dict(probs)
    return max(langs, key=lambda l: scores.get(l, 0.0))


def transcribe(model: WhisperModel, path: str, lang: str | None = None) -> str:
    """lang (e.g. "en"), when given, wins over DICTATE_LANG."""
    audio = decode_audio(path, sampling_rate=16000)
    lang = pick_language(model, audio, lang or os.environ.get("DICTATE_LANG", "auto"))
    segments, _ = model.transcribe(
        audio,
        language=lang,
        # Drop silence before transcribing: without it, Whisper
        # "hallucinates" subtitles ("Sous-titrage ST' 501").
        vad_filter=True,
        beam_size=5,
    )
    return " ".join(s.text.strip() for s in segments).strip()


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 2
    print(transcribe(load_model(), sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
