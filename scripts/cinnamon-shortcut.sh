#!/usr/bin/env bash
# Bind dictate to a Cinnamon keyboard shortcut (default: Ctrl+Alt+D).
# Usage: scripts/cinnamon-shortcut.sh [binding] [lang]
#   e.g. scripts/cinnamon-shortcut.sh '<Primary><Alt>f' fr
#        scripts/cinnamon-shortcut.sh '<Primary><Alt>e' en
# One entry per command ("dictate fr", "dictate en"...): re-running it
# updates that entry instead of adding a new one.
set -euo pipefail

BINDING="${1:-<Primary><Alt>d}"
LANG_CODE="${2:-}"
CMD="$HOME/.local/bin/dictate${LANG_CODE:+ $LANG_CODE}"
BASE=/org/cinnamon/desktop/keybindings/custom-keybindings
SCHEMA=org.cinnamon.desktop.keybindings

# gsettings prints "['__dummy__', 'custom0']", or "@as []" when empty.
mapfile -t list < <(gsettings get "$SCHEMA" custom-list | sed -e 's/^@as //' -e "s/[][' ]//g" | tr ',' '\n' | grep -v '^$' || true)

# Reuse the entry running this exact command if there is one, else take the next free customN.
slot=""
for s in "${list[@]}"; do
  [[ "$s" == __dummy__ ]] && continue
  if [[ "$(dconf read "$BASE/$s/command")" == "'$CMD'" ]]; then slot=$s; break; fi
done
if [[ -z "$slot" ]]; then
  n=0; while printf '%s\n' "${list[@]}" | grep -qx "custom$n"; do n=$((n + 1)); done
  slot="custom$n"; list+=("$slot")
fi

dconf write "$BASE/$slot/name" "'dictate${LANG_CODE:+ ($LANG_CODE)}'"
dconf write "$BASE/$slot/command" "'$CMD'"
dconf write "$BASE/$slot/binding" "['$BINDING']"

# Cinnamon (js/ui/keybindings.js) only (re)loads custom bindings on a
# "changed::custom-list" signal: editing an entry's command or binding in
# dconf is not picked up on its own. Emptying the list then writing it
# back forces the reload. '__dummy__' is skipped by Cinnamon; it is kept
# first only because that is the shape cinnamon-settings writes.
entries="'__dummy__'"
for s in "${list[@]}"; do [[ "$s" != __dummy__ ]] && entries+=", '$s'"; done
gsettings set "$SCHEMA" custom-list "[]"
sleep 0.5
gsettings set "$SCHEMA" custom-list "[$entries]"

echo "$CMD bound to $BINDING (slot $slot)"
