#!/usr/bin/env bash
# Bind dictate to a Cinnamon keyboard shortcut (default: Ctrl+Alt+D).
# Usage: scripts/cinnamon-shortcut.sh [binding]   e.g. '<Super>v'
# Re-running it updates the existing entry instead of adding a new one.
set -euo pipefail

BINDING="${1:-<Primary><Alt>d}"
CMD="$HOME/.local/bin/dictate"
BASE=/org/cinnamon/desktop/keybindings/custom-keybindings
SCHEMA=org.cinnamon.desktop.keybindings

# gsettings prints "['__dummy__', 'custom0']", or "@as []" when empty.
mapfile -t list < <(gsettings get "$SCHEMA" custom-list | sed -e 's/^@as //' -e "s/[][' ]//g" | tr ',' '\n' | grep -v '^$' || true)

# Reuse an existing dictate entry if there is one, else take the next free customN.
slot=""
for s in "${list[@]}"; do
  [[ "$s" == __dummy__ ]] && continue
  if [[ "$(dconf read "$BASE/$s/command")" == *dictate* ]]; then slot=$s; break; fi
done
if [[ -z "$slot" ]]; then
  n=0; while printf '%s\n' "${list[@]}" | grep -qx "custom$n"; do n=$((n + 1)); done
  slot="custom$n"; list+=("$slot")
fi

dconf write "$BASE/$slot/name" "'dictate'"
dconf write "$BASE/$slot/command" "'$CMD'"
dconf write "$BASE/$slot/binding" "['$BINDING']"

# Cinnamon only picks up entries listed in custom-list, and did not
# reload one written straight into dconf after a reboot. Rewriting the
# list, with the '__dummy__' first entry that cinnamon-settings itself
# uses, makes it re-read the bindings.
entries="'__dummy__'"
for s in "${list[@]}"; do [[ "$s" != __dummy__ ]] && entries+=", '$s'"; done
gsettings set "$SCHEMA" custom-list "[]"
sleep 0.5
gsettings set "$SCHEMA" custom-list "[$entries]"

echo "dictate bound to $BINDING (slot $slot)"
