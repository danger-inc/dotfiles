#!/usr/bin/env python3
# Creates ~/.config/fastfetch/161.txt: "161" as a halftone with glitch.
#   - digits from the narrow font Anton, sampled as dots (● large, • small)
#   - dots get a bit smaller towards the bottom, color gradient primary -> tertiary
#   - glitch: single rows shifted, color fringe on the outer edges (dark left, light right)
# Finished ANSI file, fastfetch shows it with "file-raw" (see config.jsonc).
# Colors: kitty palette 17-26 from kitty-colors.sh, recolors live on Super+W.
# Regenerate: python3 ~/.config/fastfetch/make-logo.py
import os, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

TEXT = "161"
COLS, ROWS = 30, 10          # size of the digits in terminal cells
GAP = 0.12                   # gap between the digits (fraction of the digit height)
DOTS = "•●"                  # small -> large
FALL = 0.35                  # how much smaller the dots get towards the bottom
THRESH = 0.33                # coverage from which a cell gets a dot
SHIFTS = {3: 1, 7: -1}       # glitch: row -> offset in columns
SUBLINE = "\U000F08C7  A R C H   L I N U X"

GRAD = [17, 18, 19, 20, 21, 22]   # gradient
SHINE, DEEP = 23, 26              # lighter / darker fringe, line
E = "\033["

font_file = subprocess.run(["fc-match", "-f", "%{file}", "Anton"], capture_output=True, text=True).stdout
font = ImageFont.truetype(font_file, 400)

# set the digits one by one and sample them to COLS x ROWS (gray levels = coverage per cell)
parts = []
for ch in TEXT:
    im = Image.new("L", (900, 900), 0)
    ImageDraw.Draw(im).text((200, 50), ch, font=font, fill=255)
    parts.append(im.crop(im.getbbox()))
ph = max(p.height for p in parts)
scale = COLS / (sum(p.width for p in parts) + GAP * ph * (len(parts) - 1))
cover = np.zeros((ROWS, COLS))
x = 0.0
for p in parts:
    pw = max(1, round(p.width * scale))
    a = np.asarray(p.resize((pw, ROWS), Image.LANCZOS)) / 255
    xi = round(x)
    cover[:, xi:xi + pw] = a[:, :max(0, min(pw, COLS - xi))]
    x += pw + GAP * ph * scale

W = COLS + 4                 # room for offset and fringe
cells = [[None] * W for _ in range(ROWS)]
for y in range(ROWS):
    for x in range(COLS):
        if cover[y, x] < THRESH:
            continue
        v = cover[y, x] * (1 - FALL * y / (ROWS - 1))
        dot = DOTS[min(len(DOTS) - 1, int(v * len(DOTS) * 1.05))]
        t = (y / (ROWS - 1) * 0.75 + x / (COLS - 1) * 0.25) * (len(GRAD) - 1)
        cells[y][x + 2 + SHIFTS.get(y, 0)] = (dot, f"38;5;{GRAD[min(5, int(t))]}")

# color fringe only on outer edges (two free cells next to it), so the hole of the 6 stays free
for y in range(ROWS):
    row = cells[y][:]
    for x in range(W):
        if row[x] is None:
            continue
        if x > 1 and row[x - 1] is None and row[x - 2] is None:
            cells[y][x - 1] = ("•", f"38;5;{DEEP}")
        if x < W - 2 and row[x + 1] is None and row[x + 2] is None:
            cells[y][x + 1] = ("•", f"38;5;{SHINE}")

lines = []
for row in cells:
    s, cur = "", None
    for c in row:
        if c is None:
            s += " "
            continue
        if c[1] != cur:
            s += f"{E}{c[1]}m"
            cur = c[1]
        s += c[0]
    lines.append(s.rstrip() + f"{E}0m")

sub_w = len(SUBLINE) + 1     # the Arch symbol is wider
lines += ["", f"{E}38;5;{SHINE}m" + "━" * W + f"{E}0m",
          f"{E}35m" + " " * ((W - sub_w) // 2) + SUBLINE + f"{E}0m"]
path = os.path.expanduser("~/.config/fastfetch/161.txt")
open(path, "w").write("\n".join(lines) + "\n")
print(f"{path}: {W} Spalten x {len(lines)} Zeilen")
