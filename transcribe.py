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


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    device = os.environ.get("DICTATE_DEVICE") or (
        "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    )
    default_model = "large-v3-turbo" if device == "cuda" else "small"
    model_name = os.environ.get("DICTATE_MODEL", default_model)
    compute_type = "float16" if device == "cuda" else "int8"
    lang = os.environ.get("DICTATE_LANG", "fr")

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(
        sys.argv[1],
        language=None if lang == "auto" else lang,
        # Drop silence before transcribing: without it, Whisper
        # "hallucinates" subtitles ("Sous-titrage ST' 501").
        vad_filter=True,
        beam_size=5,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
