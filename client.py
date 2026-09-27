"""Minimal client for the transcription server (standard library only:
starts in a few ms, unlike transcribe.py which loads the model).

Usage: client.py <file.wav>  → text on stdout; exit code 1 on error.
"""

import os
import socket
import sys
import time

SOCK = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "dictate", "server.sock")

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
    s.sendall((sys.argv[1] + "\n").encode())
    data = b"".join(iter(lambda: s.recv(65536), b"")).decode()

status, _, body = data.partition("\n")
if status != "OK":
    print(body, file=sys.stderr)
    sys.exit(1)
print(body)
