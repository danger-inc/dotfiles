#!/usr/bin/env bash
# Waybar-Look reihum wechseln (Klick auf „|“ in der Leiste):
#   kopfzeile (variants/v3) → reiter (variants/v5) → klassisch (style-classic) → …
#   style-switch.sh [next|kopfzeile|reiter|klassisch]   – ohne Argument: next
# Nur das Stylesheet wechselt (Waybar lädt es selbst neu); zwischen neu und klassisch wechselt auch die Config
# (Symlink config.jsonc), dann wird Waybar neu gestartet (nie per SIGUSR2 – das ließ Waybar abstürzen).
DIR="$HOME/.config/waybar"
CSS="$DIR/style.css"
NAMES=(kopfzeile reiter klassisch)
declare -A FILE=([kopfzeile]=variants/v3.css [reiter]=variants/v5.css [klassisch]=style-classic.css)
declare -A CONF=([kopfzeile]=suite [reiter]=suite [klassisch]=classic)

cur_file=$(grep -o 'waybar/\(variants/v[0-9]\|style-[a-z]*\)\.css' "$CSS" | head -1 | sed 's#^waybar/##')
cur=klassisch
for n in "${NAMES[@]}"; do [ "${FILE[$n]}" = "$cur_file" ] && cur=$n; done

want="${1:-next}"
if [ "$want" = next ]; then
    for i in "${!NAMES[@]}"; do [ "${NAMES[$i]}" = "$cur" ] && want=${NAMES[$(( (i + 1) % ${#NAMES[@]} ))]}; done
fi
[ -n "${FILE[$want]:-}" ] || { echo "unbekannt: $want (${NAMES[*]})" >&2; exit 2; }

sed -i "s#waybar/\(variants/v[0-9]\|style-[a-z]*\)\.css#waybar/${FILE[$want]}#" "$CSS"
link="config-${CONF[$want]}.jsonc"
if [ "$(readlink "$DIR/config.jsonc")" != "$link" ]; then
    ln -sfn "$link" "$DIR/config.jsonc"
    pkill -x waybar
    for _ in $(seq 20); do pgrep -x waybar >/dev/null || break; sleep 0.05; done
    setsid -f waybar >/dev/null 2>&1 </dev/null
fi
