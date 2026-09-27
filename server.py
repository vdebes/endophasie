"""Transcription server: keeps the model loaded in GPU memory.

Listens on a Unix socket ($XDG_RUNTIME_DIR/dictate/server.sock, mode 600).
The socket only appears once the model is loaded: its existence means "ready".
Protocol: the client sends a WAV file path + "\n"; the server replies
"OK\n<text>" or "ERR\n<message>", then closes the connection.
Exits on its own after DICTATE_IDLE_S seconds without a request
(default: 600), to give the GPU memory back.
"""

import os
import socket
import sys

from transcribe import load_model, transcribe

RUN = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "dictate")
SOCK = os.path.join(RUN, "server.sock")
IDLE_S = int(os.environ.get("DICTATE_IDLE_S", "600"))


def main() -> int:
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
            except socket.timeout:
                break
            with conn:
                path = conn.makefile().readline().strip()
                try:
                    reply = "OK\n" + transcribe(model, path)
                except Exception as e:  # the server survives an unreadable file
                    reply = f"ERR\n{e}"
                conn.sendall(reply.encode())
    finally:
        os.unlink(SOCK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
