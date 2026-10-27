#!/usr/bin/env bash
# Fetches the live configs from ~/.config into this repo (the repo is the copy, ~/.config the original).
# Absolute home paths become @HOME@; install.sh puts them back on install.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
MAP="$PWD/links.txt"
while read -r name _; do
    [[ -z "$name" || "$name" == \#* ]] && continue
    src="$HOME/$name"; dst="$PWD/$name"
    [[ -e "$src" ]] || { echo "missing: $name"; continue; }
    if [[ -d "$src" ]]; then
        mkdir -p "$dst"
        # backups (.bak-*), caches and symlinks stay out
        rsync_list=$(cd "$src" && find . -type f ! -name '*.bak*' ! -name '*.pyc' ! -name '*.so' ! -path '*__pycache__*' ! -path './.git/*')
        (cd "$src" && printf '%s\n' "$rsync_list" | cpio -pdmu --quiet "$dst" 2>/dev/null)
        # files that disappeared in the original are removed here as well
        (cd "$dst" && find . -type f | while read -r f; do [[ -e "$src/$f" ]] || rm -f "$f"; done)
    else
        mkdir -p "$(dirname "$dst")"; cp -L "$src" "$dst"
    fi
done < "$MAP"
# neutralize home paths (text files only)
grep -rIl "$HOME" --exclude-dir=.git --exclude-dir=.githooks . 2>/dev/null | while read -r f; do
    sed -i "s|$HOME|@HOME@|g" "$f"
done
# static german labels become english in the repo (the live config stays german)
sed -i -f i18n-static.sed .config/rofi/config.rasi .config/swaync/config.json .config/waybar/scripts/wifi-menu.sh \
    .config/waybar/scripts/bluetooth-menu.sh .config/waybar/config-classic.jsonc .config/waybar/config-suite.jsonc .config/hypr/scripts/apply-colors.sh
# the Zen profile path is personal: section commented out in the repo, install.sh fills in the installer's profile
sed -i -E '/^\[templates\.zen\]/,/^$/{/^#ZEN# /!s/^(.)/#ZEN# \1/}' .config/matugen/config.toml
sed -i -E 's|^(#ZEN# output_path = ).*|\1"~/.config/zen/@ZENPROFILE@/chrome/userChrome.css"|' .config/matugen/config.toml
python3 .githooks/privacy-check.py && echo "sync done."
