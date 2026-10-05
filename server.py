"""Transcription server: keeps the model loaded in GPU memory.

Listens on a Unix socket ($XDG_RUNTIME_DIR/dictate/server.sock, mode 600).
The socket only appears once the model is loaded: its existence means "ready".
Protocol: the client sends "<wav path>\t<lang>\t<prompt>\n" (lang and
prompt may be empty or omitted); the server replies
"OK\n<text>" or "ERR\n<message>", then closes the connection.
Exits on its own after DICTATE_IDLE_S seconds without a request
(default: 600), to give the GPU memory back.
"""

import os
import signal
import socket
import sys

from client import SOCK
from transcribe import load_model, transcribe

IDLE_S = int(os.environ.get("DICTATE_IDLE_S", "600"))


def parse_request(line: str) -> tuple[str, str, str]:
    """"<wav path>\t<lang>\t<prompt>\n" → (path, lang, prompt); missing
    fields are empty (older clients send only the path, or path and lang)."""
    path, lang, prompt = (line.rstrip("\n").split("\t") + ["", ""])[:3]
    return path, lang, prompt


def main() -> int:
    # systemd stops the service with SIGTERM, which by default kills Python
    # without running `finally`: the socket would stay behind, and clients
    # would take it for a ready server. Turn SIGTERM into a clean exit.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    model = load_model()
    if os.path.exists(SOCK):
        os.unlink(SOCK)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old_umask = os.umask(0o177)                 # socket created as 600 right away
    srv.bind(SOCK)
    os.umask(old_umask)
    srv.listen(4)
    srv.settimeout(IDLE_S)
    print(f"ready ({SOCK}), exiting after {IDLE_S} s idle", file=sys.stderr)
    try:
        while True:
            try:
                conn, _ = srv.accept()
            except TimeoutError:
                break
            with conn:
                path, lang, prompt = parse_request(conn.makefile().readline())
                try:
                    reply = "OK\n" + transcribe(model, path, lang or None, prompt or None)
                except Exception as e:  # the server survives an unreadable file
                    reply = f"ERR\n{e}"
                conn.sendall(reply.encode())
    finally:
        os.unlink(SOCK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
