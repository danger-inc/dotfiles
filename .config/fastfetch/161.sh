#!/usr/bin/env bash
# fastfetch mittig im Fenster, Layout passend zur Fensterbreite, damit nichts umbricht:
#   breit  -> Logo links, Infos rechts
#   mittel -> Logo oben, Infos darunter
#   schmal -> nur Infos
# Logo: make-logo.py (Farben: Kitty-Palette 17-26 aus kitty-colors.sh), siehe config.jsonc.
dir=~/.config/fastfetch

# Sichtbare Breite: Farbcodes entfernen, Spaltensprünge (ESC[nG) von fastfetch mitrechnen
width() {
    perl -CSD -ne 's/\e\[[0-9;]*m|\e\[\?7[lh]//g; chomp;
        $w = /^(.*)\e\[(\d+)G(.*)$/ ? $2 - 1 + length($3) : length($_);
        $m = $w if $w > $m; END { print $m + 0 }'
}

logo_w=$(width < "$dir/161.txt")
info_w=$(fastfetch --logo none --pipe false "$@" 2>/dev/null | width)
gap=4   # logo.padding.right in config.jsonc

cols=$(tput cols 2>/dev/null || echo 80)
if (( cols >= logo_w + gap + info_w )); then
    exec fastfetch --logo-padding-left $(( (cols - logo_w - gap - info_w) / 2 )) "$@"
elif (( cols >= 42 )); then
    block=$(( logo_w > info_w ? logo_w : info_w ))
    exec fastfetch --logo-position top --logo-padding-top 1 \
        --logo-padding-left $(( (cols - block) / 2 )) "$@"
else
    exec fastfetch --logo none "$@"
fi
