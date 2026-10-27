#!/usr/bin/env bash
# Holt die Live-Configs aus ~/.config in dieses Repo (das Repo ist die Kopie, ~/.config das Original).
# Absolute Home-Pfade werden zu @HOME@; install.sh setzt sie beim Installieren wieder ein.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
MAP="$PWD/links.txt"
while read -r name _; do
    [[ -z "$name" || "$name" == \#* ]] && continue
    src="$HOME/$name"; dst="$PWD/$name"
    [[ -e "$src" ]] || { echo "missing: $name"; continue; }
    if [[ -d "$src" ]]; then
        mkdir -p "$dst"
        # Backups (.bak-*), Caches und Symlinks bleiben draußen
        rsync_list=$(cd "$src" && find . -type f ! -name '*.bak*' ! -name '*.pyc' ! -name '*.so' ! -path '*__pycache__*' ! -path './.git/*')
        (cd "$src" && printf '%s\n' "$rsync_list" | cpio -pdmu --quiet "$dst" 2>/dev/null)
        # Dateien, die im Original verschwunden sind, auch hier entfernen
        (cd "$dst" && find . -type f | while read -r f; do [[ -e "$src/$f" ]] || rm -f "$f"; done)
    else
        mkdir -p "$(dirname "$dst")"; cp -L "$src" "$dst"
    fi
done < "$MAP"
# Home-Pfade neutralisieren (nur Textdateien)
grep -rIl "$HOME" --exclude-dir=.git --exclude-dir=.githooks . 2>/dev/null | while read -r f; do
    sed -i "s|$HOME|@HOME@|g" "$f"
done
# Zen-Profilpfad ist persönlich: Abschnitt auskommentiert ins Repo, install.sh trägt das Profil des Installierenden ein
sed -i -E '/^\[templates\.zen\]/,/^$/{/^#ZEN# /!s/^(.)/#ZEN# \1/}' .config/matugen/config.toml
sed -i -E 's|^(#ZEN# output_path = ).*|\1"~/.config/zen/@ZENPROFILE@/chrome/userChrome.css"|' .config/matugen/config.toml
python3 .githooks/privacy-check.py && echo "sync done."
