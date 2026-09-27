#!/usr/bin/env bash
# Regression test for the 2026-09-27 freeze: key auto-repeat launched
# dozens of transcriptions in parallel (18 × 1.4 GB → RAM full, machine
# frozen). Simulates a held-down key, on start and then on stop, and
# checks there is never more than one transcription at a time.
set -uo pipefail
cd "$(dirname "$0")/.."
export DICTATE_DRYRUN=1
RUN="${XDG_RUNTIME_DIR:-/tmp}/dictate"

count_py() { pgrep -fc '\.venv/bin/python .*transcribe\.py' || true; }
# Key held ~0.6 s at ~30 repeats/s (beyond 1 s, a "stop" call is
# legitimate: that is dictate's MIN_REC_MS threshold).
burst() { for _ in $(seq 18); do ./dictate & sleep 0.033; done; wait; }

pkill -x pw-record; rm -f "$RUN/rec.pid"

echo "== burst on start (18 calls / 0.6 s)"
burst
rec=$(pgrep -xc pw-record)
echo "   active pw-record: $rec (expected: 1)"

sleep 2
echo "== burst on stop (18 calls / 0.6 s), watching transcriptions"
max=0
( burst ) &
B=$!
while kill -0 "$B" 2>/dev/null; do
  n=$(count_py); (( n > max )) && max=$n; sleep 0.1
done
echo "   max concurrent transcriptions: $max (expected: 1)"
echo "   leftover pw-record: $(pgrep -xc pw-record) (expected: 0)"

(( rec == 1 && max == 1 )) && ! pgrep -x pw-record >/dev/null && echo "OK" || { echo "FAIL"; exit 1; }
