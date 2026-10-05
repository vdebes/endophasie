#!/usr/bin/env bash
# install.sh — install endophasie for the current user (no root, except
# for missing system packages, which it offers to install with apt).
# Safe to run again: it updates links and settings instead of duplicating them.
#
# Supported: Linux, X11, PipeWire, NVIDIA GPU. Without an NVIDIA GPU it
# installs the CPU mode (slower). Wayland is refused: pasting the text is
# not ported yet, so dictation would silently do nothing.
set -euo pipefail

DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/dictate"
CONF="$CONF_DIR/env"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
BIN="$HOME/.local/bin"

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
warn() { printf '\033[33m⚠ %s\033[0m\n' "$1"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }
ok()   { printf '✓ %s\n' "$1"; }

step "Checking the system"
[[ "$(uname -s)" == Linux ]] || die "Linux only (see the README for cross-platform alternatives)."
case "${XDG_SESSION_TYPE:-}" in
  wayland) die "Wayland session detected: not supported yet (pasting the text is not ported).
  Log in with an X11 session (\"Xorg\" on the login screen), then run ./install.sh again." ;;
  x11) ok "X11 session" ;;
  *) warn "Session type unknown (XDG_SESSION_TYPE='${XDG_SESSION_TYPE:-}'): assuming X11." ;;
esac
command -v pw-record >/dev/null || die "pw-record not found: PipeWire is required to record the mic."
ok "PipeWire (pw-record)"

# Command → Debian/Ubuntu package providing it.
declare -A PKG=([xdotool]=xdotool [xclip]=xclip [xprop]=x11-utils [notify-send]=libnotify-bin)
missing=()
for cmd in xdotool xclip xprop notify-send; do
  command -v "$cmd" >/dev/null || missing+=("${PKG[$cmd]}")
done
if (( ${#missing[@]} )); then
  if command -v apt-get >/dev/null; then
    echo "Missing system packages: ${missing[*]}"
    read -rp "Install them now with 'sudo apt install ${missing[*]}'? [Y/n] " answer
    [[ "${answer:-y}" =~ ^[Yy]$ ]] || die "Install them, then run ./install.sh again."
    sudo apt-get install -y "${missing[@]}"
  else
    die "Missing: ${missing[*]} (package names on Debian/Ubuntu; install their equivalent with your package manager)."
  fi
fi
ok "xdotool, xclip, xprop, notify-send"

command -v uv >/dev/null || die "uv not found. Install it (https://docs.astral.sh/uv/), e.g.:
  curl -LsSf https://astral.sh/uv/install.sh | sh
then open a new terminal and run ./install.sh again."
ok "uv"

if command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1; then
  device=cuda
  ok "NVIDIA GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)"
else
  device=cpu
  warn "No NVIDIA GPU found: installing the CPU mode (small model, ~4x slower than a GPU).
  AMD GPUs are not supported by the transcription library."
fi

step "Python environment (.venv/; with CUDA, ~2.6 GB the first time)"
# --no-dev: no lint/test tools. Without a GPU, no CUDA wheels (2.6 GB).
# --inexact: keep packages already there (a developer's tools, say).
sync_args=(--quiet --inexact --no-dev --no-build)   # wheels only: no setup script runs
[[ $device == cuda ]] || sync_args+=(--no-group gpu)
(cd "$DIR" && uv sync "${sync_args[@]}")
ok ".venv/ ready"

step "Settings ($CONF)"
mkdir -p "$CONF_DIR"
if [[ -f "$CONF" ]]; then
  ok "kept as is (already exists)"
else
  cat > "$CONF" <<'EOF'
# endophasie settings — read by dictate and by the systemd service.
# Uncomment to change a default. Details in the README.
# DICTATE_LANG=fr               # language when dictate gets no argument (default: auto)
# DICTATE_BEAM=5                # default 1 (~25% faster, same quality in tests)
# DICTATE_MODEL=large-v3-turbo  # default: large-v3-turbo on GPU, small on CPU
# DICTATE_INSERT=type           # simulated typing instead of paste
# DICTATE_PAUSE=4               # pause mode: paste after 4 s of silence (default 0: off)
# DICTATE_AFTER_PAUSE=continue  # or stop: close the mic after the first paste
# DICTATE_MIC_IDLE=30           # continue mode: close the mic after 30 s without speech
EOF
  ok "created (all defaults)"
fi

step "Whisper model (downloaded once, then everything runs offline)"
# shellcheck source=/dev/null
model="$(set -a; . "$CONF"; echo "${DICTATE_MODEL:-}")"
[[ -n "$model" ]] || { [[ $device == cuda ]] && model=large-v3-turbo || model=small; }
# dictate forces HF_HUB_OFFLINE=1: without this step the first dictation
# would fail instead of downloading the model.
(cd "$DIR" && uv run --no-sync --no-build --quiet python -c \
  "import sys; from faster_whisper import download_model; download_model(sys.argv[1])" "$model")
ok "$model in ~/.cache/huggingface/"

step "Command and service"
mkdir -p "$BIN" "$UNIT_DIR"
ln -sfn "$DIR/dictate" "$BIN/dictate"
ln -sfn "$DIR/dictate-server.service" "$UNIT_DIR/dictate-server.service"
systemctl --user daemon-reload
# Restart a server left running by a previous version (no-op otherwise).
systemctl --user try-restart dictate-server.service
ok "$BIN/dictate → $DIR/dictate"
ok "dictate-server.service (started on your first dictation)"

step "Keyboard shortcuts"
if [[ "${XDG_CURRENT_DESKTOP:-}" == *Cinnamon* ]]; then
  "$DIR/scripts/cinnamon-shortcut.sh" '<Primary><Alt>f' fr
  "$DIR/scripts/cinnamon-shortcut.sh" '<Primary><Alt>e' en
  shortcuts="Ctrl+Alt+F (French) or Ctrl+Alt+E (English)"
else
  warn "Not Cinnamon (${XDG_CURRENT_DESKTOP:-unknown desktop}): bind these commands to shortcuts
  in your desktop's keyboard settings:
    $BIN/dictate fr    (French)
    $BIN/dictate en    (English)"
  shortcuts="your shortcut"
fi

step "Done"
echo "Click into any text field, press $shortcuts, speak,
then press it again: the text appears where the cursor is.
The first dictation takes a few seconds more (the model loads)."
