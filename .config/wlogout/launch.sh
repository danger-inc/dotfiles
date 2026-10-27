#!/usr/bin/env bash
# Öffnet wlogout mit 5 kompakten, mittig platzierten Karten.
# Ein zweiter Klick auf den Power-Knopf schließt es wieder.
pkill -x wlogout && exit 0
~/.config/wlogout/make-icons.py

card_w=118 card_h=216   # Kartengröße inkl. Rand (8px je Seite), logische Pixel
read -r w h < <(hyprctl monitors -j | python3 -c '
import json, sys
m = next(m for m in json.load(sys.stdin) if m["focused"])
w, h = m["width"] / m["scale"], m["height"] / m["scale"]
if m["transform"] % 2: w, h = h, w
print(int(w), int(h))')

lr=$(( (w - 5 * card_w) / 2 ))
tb=$(( (h - card_h) / 2 ))
exec wlogout -b 5 -c 0 -r 0 -L "$lr" -R "$lr" -T "$tb" -B "$tb" -p layer-shell
