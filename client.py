"""Minimal client for the transcription server (standard library only:
starts in a few ms, unlike transcribe.py which loads the model).

Usage: client.py <file.wav> [lang]  → text on stdout; exit code 1 on error.
Also imported by streamer.py (request()).
"""

import os
import socket
import sys
import time

# Per-user runtime directory (tmpfs, mode 700): never a shared /tmp, where
# another user could create the folder first and intercept the socket.
RUN = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}", "dictate")
SOCK = os.path.join(RUN, "server.sock")


def request(path: str, lang: str = "", prompt: str = "") -> str:
    """Transcribe `path` on the server. `prompt`: text preceding this audio
    (keeps style and punctuation consistent across chunks). Raises
    RuntimeError on a server-side error."""
    # Tabs and newlines are the protocol's separators.
    prompt = " ".join(prompt.split())
    # A stale socket (server killed hard) or a server still loading refuses
    # connections: retry for a while instead of failing the dictation.
    deadline = time.monotonic() + 20
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        while True:
            try:
                s.connect(SOCK)
                break
            except (ConnectionRefusedError, FileNotFoundError):
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.1)
        s.sendall(f"{path}\t{lang}\t{prompt}\n".encode())
        data = b"".join(iter(lambda: s.recv(65536), b"")).decode()
    status, _, body = data.partition("\n")
    if status != "OK":
        raise RuntimeError(body)
    return body


if __name__ == "__main__":
    try:
        print(request(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""))
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
