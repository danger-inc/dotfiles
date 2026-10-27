#!/usr/bin/env bash
# Dotfiles installieren: Dateien nach ~ verlinken (bestehende wandern nach ~/.dotfiles-backup/<datum>).
# Dateien mit @HOME@ werden gerendert (kopiert) statt verlinkt, weil Hyprland & Co. kein $HOME auflösen.
#   ./install.sh            alles
#   ./install.sh hypr kitty nur diese Bausteine (Name = Ordner unter .config)
#   ./install.sh --dry-run  nur anzeigen
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP=$(date +%Y-%m-%d_%H%M%S); BACKUP="$HOME/.dotfiles-backup/$STAMP"
DRY=0; ONLY=()
for a in "$@"; do [[ "$a" == --dry-run ]] && DRY=1 || ONLY+=("$a"); done

say()  { printf '\033[1;36m%s\033[0m\n' "$*"; }
act()  { (( DRY )) && echo "  [dry] $*" || eval "$@"; }

wanted() {
    (( ${#ONLY[@]} )) || return 0
    local n; for n in "${ONLY[@]}"; do [[ "$1" == *"/$n" || "$1" == *"/$n/"* || "$1" == *"/$n."* ]] && return 0; done
    return 1
}

place() {                       # place <relativer Pfad>
    local rel="$1" from="$SRC/$1" to="$HOME/$1"
    if [[ -e "$to" || -L "$to" ]]; then
        [[ -f "$to" && ! -L "$to" ]] && ! grep -qI "@HOME@" "$from" && cmp -s "$from" "$to" && return
        if [[ -L "$to" && "$(readlink -f "$to")" == "$(readlink -f "$from")" ]]; then return; fi
        act "mkdir -p '$BACKUP/$(dirname "$rel")' && mv '$to' '$BACKUP/$rel'"
    fi
    act "mkdir -p '$(dirname "$to")'"
    if grep -qI '@HOME@' "$from" 2>/dev/null; then
        act "sed 's|@HOME@|$HOME|g' '$from' > '$to' && chmod --reference='$from' '$to'"
    elif [[ "$rel" == .local/* ]]; then   # die -ist-Apps überschreiben Dateien in rice-apps beim Update: kopieren statt verlinken
        act "cp -p '$from' '$to'"
    else
        act "ln -s '$from' '$to'"
    fi
}

say "== installing dotfiles ($( ((DRY)) && echo "dry run, " )backup: $BACKUP) =="
while read -r name _; do
    [[ -z "$name" || "$name" == \#* ]] && continue
    wanted "$name" || continue
    [[ -e "$SRC/$name" ]] || continue
    if [[ -d "$SRC/$name" ]]; then
        # Ordner: jede Datei einzeln, damit lokale Zusatzdateien (Caches, Wallpaper …) im Ziel bleiben
        while read -r f; do place "$name/${f#./}"; done < <(cd "$SRC/$name" && find . -type f)
    else
        place "$name"
    fi
done < "$SRC/links.txt"

# Zen-Browser: Theme-Abschnitt in der matugen-Config nur aktivieren, wenn ein Zen-Profil existiert
M="$HOME/.config/matugen/config.toml"
if [[ -f "$M" ]] && grep -q '^#ZEN# ' "$M" && wanted ".config/matugen"; then
    Z=$(sed -n '/^\[Install/,/^$/s/^Default=//p' "$HOME/.config/zen/profiles.ini" 2>/dev/null | head -1 || true)
    if [[ -n "$Z" && -d "$HOME/.config/zen/$Z" ]]; then
        act "sed -i -e 's|@ZENPROFILE@|$Z|' -e 's|^#ZEN# ||' '$M'"
    else echo "Zen browser not found – zen theme skipped (section [templates.zen] in ~/.config/matugen/config.toml)"; fi
fi

# wofi-Fokus-Fix (LD_PRELOAD) bauen
W="$HOME/.local/share/rice-apps/wofi-ondemand"
if [[ -f "$W/wofi-ondemand.c" ]] && wanted ".local/share/rice-apps/wofi-ondemand"; then
    if command -v gcc >/dev/null; then act "gcc -shared -fPIC -O2 -o '$W/wofi-ondemand.so' '$W/wofi-ondemand.c'"
    else echo "gcc missing – wofi-ondemand.so not built (waybar menus will not close when you click another icon)"; fi
fi
[[ -f "$HOME/.local/share/rice-apps/tui.py" ]] || echo "NOTE: ~/.local/share/rice-apps/tui.py is missing – install one of the -ist apps first (e.g. wallist, inquirist); the waybar menus need it."

say "== done =="
echo "rendered files (with a home path) are copies: run ./install.sh again after editing them in the repo."
echo "packages: see packages.txt   ·   generate colors: Super+W (matugen)"
