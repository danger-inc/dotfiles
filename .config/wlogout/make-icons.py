#!/usr/bin/env python3
# Creates the wlogout icons in the current matugen colors:
# <name>.png in primary, <name>-hover.png in background (for the filled card).
# Runs on every open through launch.sh, so it is up to date right after Super+W.
import os, re, subprocess

cache = os.path.expanduser("~/.cache/ist")
css = open(f"{cache}/colors.css").read()
col = dict(re.findall(r"@define-color (\w+) (#[0-9a-fA-F]{6});", css))
out = f"{cache}/wlogout"
os.makedirs(out, exist_ok=True)

icons = {
    "lock":     '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "logout":   '<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3"/><path d="M10 8l-4 4 4 4"/><path d="M6 12h10"/>',
    "suspend":  '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    "reboot":   '<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/>',
    "shutdown": '<path d="M12 3v9"/><path d="M6.3 6.8a8 8 0 1 0 11.4 0"/>',
}

for name, body in icons.items():
    for suffix, color in (("", col["primary"]), ("-hover", col["background"])):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
               f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
        subprocess.run(["rsvg-convert", "-w", "128", "-h", "128", "-o", f"{out}/{name}{suffix}.png"],
                       input=svg.encode(), check=True)
