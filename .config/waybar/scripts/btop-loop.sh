#!/bin/bash
# Läuft im btop-Fenster. Super+W lädt die Farben inzwischen live per SIGUSR2 nach (apply-colors.sh),
# die Neustart-Schleife ist nur noch ein Fallback: liegt die Markierung vor, startet btop neu,
# sonst geht das Fenster nach q ganz normal zu.
mark="${XDG_RUNTIME_DIR:-/tmp}/btop-farben-neu"
while true; do
    btop
    [[ -e $mark ]] || break
    rm -f "$mark"
done
