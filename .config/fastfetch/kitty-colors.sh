#!/usr/bin/env bash
# Schreibt die Logo-Farben für "161" als Kitty-Palettenfarben 17-24 nach
# ~/.cache/matugen/colors-kitty-161.conf (von kitty.conf eingebunden).
# Weil das Logo Palettenfarben nutzt, färbt Kitty es bei Super+W live mit um.
#   17-22 Verlauf primary -> tertiary, 23 Glanzkante, 24 Schlagschatten,
#   25/26 Schattenkante hell/dunkel (primary mit background gemischt)
# Aufruf aus ~/.config/hypr/scripts/apply-colors.sh nach matugen.
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
    # primary Richtung background abdunkeln: mix <prozent-primary>
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
