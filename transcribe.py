"""Transcribe an audio file to text, 100% locally (faster-whisper).

Usage: transcribe.py <file.wav>
The text goes to stdout; diagnostics go to stderr.
Configuration through environment variables:
  DICTATE_MODEL   Whisper model (default: large-v3-turbo on GPU, small on CPU)
  DICTATE_LANG    forced language (default: fr; "auto" to detect)
  DICTATE_DEVICE  cuda | cpu (default: cuda if an NVIDIA GPU is visible)
"""

import os
import sys

import ctranslate2
from faster_whisper import WhisperModel


def load_model() -> WhisperModel:
    device = os.environ.get("DICTATE_DEVICE") or (
        "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    )
    default_model = "large-v3-turbo" if device == "cuda" else "small"
    model_name = os.environ.get("DICTATE_MODEL", default_model)
    compute_type = "float16" if device == "cuda" else "int8"
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def transcribe(model: WhisperModel, path: str) -> str:
    lang = os.environ.get("DICTATE_LANG", "fr")
    segments, _ = model.transcribe(
        path,
        language=None if lang == "auto" else lang,
        # Drop silence before transcribing: without it, Whisper
        # "hallucinates" subtitles ("Sous-titrage ST' 501").
        vad_filter=True,
        beam_size=5,
    )
    return " ".join(s.text.strip() for s in segments).strip()


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    print(transcribe(load_model(), sys.argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
