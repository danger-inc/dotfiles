# TODO vor Reddit-Veröffentlichung (Stand 2026-10-27, Test als Fremd-Nachbauer)

Test: frisches Arch-Rootfs (~/.cache/suite-installtest/arch), alle App-Installer laufen sauber; Hyprland-Config `config ok`.

## In Arbeit (Blocker 2–5)
- [x] 2. Fehlende Dateien in ein Repo: volume-osd(.py), volume-mixer.py, ricetui.py+audio/bluetooth/network.py, rice-audio/netz/bluetooth, wofi-ondemand(.so + Quelle), cursor/make-cursor.py, ist-colors.py (Apps liefern es nicht)
- [x] 3. Waybar `"output": "eDP-1"` fest + `"bat": "BAT0"` → monitorunabhängig
- [x] 4. Erststart ohne Wallpaper: ~/.config/wallpapers fehlt → random_wall.sh bricht ab; Start-Wallpaper mitliefern/Fallback
- [x] 5. packages.txt vervollständigen (awww, cliphist, brightnessctl, wofi, rofi, jq, networkmanager, bluez(-utils), hyprsunset, hyprpicker, wf-recorder, libnotify, xdg-desktop-portal-hyprland, polkit-Agent, python-gobject, gtk4, zen-browser(AUR), wlogout(AUR) kennzeichnen; unbenutzte quickshell/hyprpaper raus)

## Noch offen
- [ ] 1. Repo danger-inc/dotfiles ist PRIVATE → am Ende public schalten (zuerst alles unten erledigen)
- [x] 6. hypridle und swaync werden in hyprland.lua nicht gestartet (evtl. systemd-User-Dienste bei dir) → exec_cmd ergänzen
- [x] 7. hyprlock-Hintergrund ~/.cache/current_wallpaper.png nur durch Super+L → Idle-Sperre ohne Bild; lock.sh/hyprlock-Pfad fixen
- [x] 8. Fremdautor „L€yzS“ in wallpaper-picker.sh, scripts/wallpaper-picker2.sh, scripts/wallpapers/random-wallpaper.sh, waybar/style-classic.css → Credit oder entfernen
- [x] 9. swaync/icons/battery-quarter-solid.svg = Font Awesome Pro (nicht weiterverteilbar) → ersetzen
- [x] 10. LICENSE fehlt
- [x] 11. (lokal squashed, Backup-Branch old-history; Force-Push steht noch aus) Git-Historie enthält Fremddateien → vor Public ggf. neu aufsetzen (squash / neues Repo)
- [x] 12. Tote alte Config-Schicht entfernen: hypr/hyprland.conf, hypr/configs/*.conf (wal, grimblast, Ekran Görüntülerim, Kitty-Efeckt mp3, WhiteSur)
- [x] 13. hyprpaper.conf (windows-11.png), wallpaper-picker*.sh (Live Wallpapers), doppelte lock.sh entfernen
- [x] 14. matugen/config.toml: Zen-Profilpfad `ikm0rhe8.Default (release)` (persönlich, legt Müllordner an) → entfernen/optional
- [x] 15. install.sh meldet immer „Probelauf“ (`${DRY:+…}` bei DRY=0)
- [x] 16. README-Widersprüche: Quickshell vs Waybar, rofi/wofi/waybar-Erklärung, Hook-Hinweis
- [x] 17. Installer-Ausgaben deutsch, READMEs englisch → vereinheitlichen
- [x] 18. divist: Autostart nur wenn installiert (test -x); rechner-Modus nutzt qalc (libqalculate ergänzt). Ob divist öffentlich wird: deine Entscheidung
- [x] 19. Hartkodiert: kb_layout de, tty1 `exec Hyprland` in config.fish → im README erwähnen
- [x] 20. README `yay -S --needed - < packages.txt` bricht bei unbekanntem Paket ab; yay nicht vorinstalliert → Repo-/AUR-Pakete trennen

## Erledigt 2026-10-27 (2–5), noch NICHT committet
- 2: rice-apps-Dateien + rice-*/volume-osd in links.txt; .local/* wird kopiert statt verlinkt; install.sh baut wofi-ondemand.so (gcc) und warnt, wenn tui.py fehlt (Apps zuerst installieren)
- 3: "output"/"bat" aus beiden Waybar-Configs entfernt (live + Repo)
- 4: hypr/default-wallpaper.jpg (generiert, 200 KB), random_wall.sh kopiert es in ~/.config/wallpapers falls leer; Autostart ruft random_wall.sh beim ersten Start. Im Arch-Container getestet.
- 5: packages.txt (nur offizielle Repos, Kommentare → `grep -v '^#' | pacman -S -`) + packages-aur.txt (wlogout, zen-browser-bin); README angepasst
- Test: pacman-Install + install.sh im frischen Arch-Rootfs lief durch (cmp fehlte → diffutils ergänzt)
