#!/usr/bin/env bash
# fastfetch centered in the window, layout matching the window width so nothing wraps:
#   wide   -> logo left, info right
#   medium -> logo on top, info below
#   narrow -> info only
# Logo: make-logo.py (colors: kitty palette 17-26 from kitty-colors.sh), see config.jsonc.
dir=~/.config/fastfetch

# visible width: strip color codes, count fastfetch's column jumps (ESC[nG)
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
