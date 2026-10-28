#!/usr/bin/env bash
# Deutsches Datum fuer hyprlock (de_DE-Locale ist nicht installiert)
t=(Montag Dienstag Mittwoch Donnerstag Freitag Samstag Sonntag)
m=(Januar Februar März April Mai Juni Juli August September Oktober November Dezember)
echo "${t[$(date +%u)-1]}, $(date +%-d). ${m[$(date +%-m)-1]} $(date +%Y)"
