#!/usr/bin/env python3
# Notification module for waybar: reads swaync-client -swb and colors the
# dot with the matugen color "primary". If colors.css changes (Super+W),
# the output is rewritten immediately – without reloading waybar.
import json, os, re, select, subprocess, sys

COLORS = os.path.expanduser("~/.cache/matugen/colors.css")
BELL, DOT = "", ""

def primary():
    try:
        m = re.search(r"@define-color primary (#[0-9a-fA-F]{6});", open(COLORS).read())
        return m.group(1) if m else "red"
    except OSError:
        return "red"

def emit(data, color):
    has = data.get("alt", "").endswith("notification") and "none" not in data.get("alt", "")
    text = BELL + (f"<span foreground='{color}'><sup>{DOT}</sup></span>" if has else "")
    print(json.dumps({**data, "text": text}), flush=True)

def mtime():
    try:
        return os.stat(COLORS).st_mtime
    except OSError:
        return 0

swaync = subprocess.Popen(["swaync-client", "-swb"], stdout=subprocess.PIPE, text=True)
last, color, seen = None, primary(), mtime()
while True:
    ready, _, _ = select.select([swaync.stdout], [], [], 0.5)
    if ready:
        line = swaync.stdout.readline()
        if not line:
            sys.exit(1)
        last = json.loads(line)
        emit(last, color)
    elif mtime() != seen:
        seen, color = mtime(), primary()
        if last:
            emit(last, color)
