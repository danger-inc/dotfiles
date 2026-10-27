#!/usr/bin/env bash
# Install the dotfiles: link files into ~ (existing ones move to ~/.dotfiles-backup/<date>).
# Files with @HOME@ are rendered (copied) instead of linked, because Hyprland & co. do not resolve $HOME.
#   ./install.sh            everything
#   ./install.sh hypr kitty only these parts (name = folder under .config)
#   ./install.sh --dry-run  only show
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

place() {                       # place <relative path>
    local rel="$1" from="$SRC/$1" to="$HOME/$1"
    if [[ -e "$to" || -L "$to" ]]; then
        [[ -f "$to" && ! -L "$to" ]] && ! grep -qI "@HOME@" "$from" && cmp -s "$from" "$to" && return
        if [[ -L "$to" && "$(readlink -f "$to")" == "$(readlink -f "$from")" ]]; then return; fi
        act "mkdir -p '$BACKUP/$(dirname "$rel")' && mv '$to' '$BACKUP/$rel'"
    fi
    act "mkdir -p '$(dirname "$to")'"
    if grep -qI '@HOME@' "$from" 2>/dev/null; then
        act "sed 's|@HOME@|$HOME|g' '$from' > '$to' && chmod --reference='$from' '$to'"
    elif [[ "$rel" == .local/* ]]; then   # the -ist apps overwrite files in rice-apps on update: copy instead of link
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
        # folder: each file on its own, so local extra files (caches, wallpapers …) stay in the target
        while read -r f; do place "$name/${f#./}"; done < <(cd "$SRC/$name" && find . -type f)
    else
        place "$name"
    fi
done < "$SRC/links.txt"

# Zen browser: only enable the theme section in the matugen config if a Zen profile exists
M="$HOME/.config/matugen/config.toml"
if [[ -f "$M" ]] && grep -q '^#ZEN# ' "$M" && wanted ".config/matugen"; then
    Z=$(sed -n '/^\[Install/,/^$/s/^Default=//p' "$HOME/.config/zen/profiles.ini" 2>/dev/null | head -1 || true)
    if [[ -n "$Z" && -d "$HOME/.config/zen/$Z" ]]; then
        act "sed -i -e 's|@ZENPROFILE@|$Z|' -e 's|^#ZEN# ||' '$M'"
    else echo "Zen browser not found – zen theme skipped (section [templates.zen] in ~/.config/matugen/config.toml)"; fi
fi

# build the wofi focus fix (LD_PRELOAD)
W="$HOME/.local/share/rice-apps/wofi-ondemand"
if [[ -f "$W/wofi-ondemand.c" ]] && wanted ".local/share/rice-apps/wofi-ondemand"; then
    if command -v gcc >/dev/null; then act "gcc -shared -fPIC -O2 -o '$W/wofi-ondemand.so' '$W/wofi-ondemand.c'"
    else echo "gcc missing – wofi-ondemand.so not built (waybar menus will not close when you click another icon)"; fi
fi
[[ -f "$HOME/.local/share/rice-apps/tui.py" ]] || echo "NOTE: ~/.local/share/rice-apps/tui.py is missing – install one of the -ist apps first (e.g. wallist, inquirist); the waybar menus need it."

say "== done =="
echo "rendered files (with a home path) are copies: run ./install.sh again after editing them in the repo."
echo "packages: see packages.txt   ·   generate colors: Super+W (matugen)"
