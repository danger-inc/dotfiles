#!/usr/bin/env bash
# Writes the logo colors for "161" as kitty palette colors 17-24 to
# ~/.cache/matugen/colors-kitty-161.conf (included by kitty.conf).
# Because the logo uses palette colors, kitty recolors it live on Super+W.
#   17-22 gradient primary -> tertiary, 23 highlight edge, 24 drop shadow,
#   25/26 shadow edge light/dark (primary mixed with background)
# Called from ~/.config/hypr/scripts/apply-colors.sh after matugen.
colors=~/.cache/ist/colors.css
out=~/.cache/matugen/colors-kitty-161.conf

hex() { sed -n "s/^@define-color $1 #\([0-9a-fA-F]\{6\}\);/\1/p" "$colors"; }

a=$(hex primary) b=$(hex tertiary)
{
    echo "# Automatisch erzeugt von ~/.config/fastfetch/kitty-colors.sh"
    for i in 0 1 2 3 4 5; do
        printf 'color%d #%02x%02x%02x\n' $((17 + i)) \
            $(( 0x${a:0:2} + (0x${b:0:2} - 0x${a:0:2}) * i / 5 )) \
            $(( 0x${a:2:2} + (0x${b:2:2} - 0x${a:2:2}) * i / 5 )) \
            $(( 0x${a:4:2} + (0x${b:4:2} - 0x${a:4:2}) * i / 5 ))
    done
    echo "color23 #$(hex foreground)"
    echo "color24 #$(hex color4)"
    # darken primary towards background: mix <percent-primary>
    c=$(hex background)
    mix() {
        printf '#%02x%02x%02x\n' \
            $(( (0x${a:0:2} * $1 + 0x${c:0:2} * (100 - $1)) / 100 )) \
            $(( (0x${a:2:2} * $1 + 0x${c:2:2} * (100 - $1)) / 100 )) \
            $(( (0x${a:4:2} * $1 + 0x${c:4:2} * (100 - $1)) / 100 ))
    }
    echo "color25 $(mix 62)"
    echo "color26 $(mix 38)"
} > "$out"
