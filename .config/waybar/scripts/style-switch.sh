#!/usr/bin/env bash
# Cycle the waybar look (click on "|" in the bar):
#   kopfzeile (variants/v3) → reiter (variants/v5) → klassisch (style-classic) → …
#   style-switch.sh [next|kopfzeile|reiter|klassisch]   – without argument: next
# Only the stylesheet changes (waybar reloads it itself); between new and classic the config changes too
# (symlink config.jsonc), then waybar is restarted (never via SIGUSR2 – that crashed waybar).
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
