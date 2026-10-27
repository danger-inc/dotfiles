#!/usr/bin/env python3
"""Waybar im Vollbild verstecken und beim Berühren des oberen Bildschirmrands einblenden.
Waybar liegt auf der Overlay-Ebene (über Vollbildfenstern); ausserhalb des Vollbilds bleibt sie
normal sichtbar und reserviert ihren Platz. Sichtbarkeit wird per SIGUSR1 umgeschaltet, der Zustand
hier mitgezählt (bei neuem Waybar-Prozess zurück auf „sichtbar“)."""
import json, os, sys, select, signal, socket, subprocess, time

RT = os.environ["XDG_RUNTIME_DIR"]
HIS = os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
BASE = f"{RT}/hypr/{HIS}"
EDGE = 1       # Pixel vom oberen Rand, ab dem eingeblendet wird
LEAVE = 80     # darunter wieder ausblenden (Leiste: 10 Rand + 46 Höhe)


def hypr(cmd):
    with socket.socket(socket.AF_UNIX) as s:
        s.connect(f"{BASE}/.socket.sock")
        s.sendall(cmd.encode())
        data = b""
        while (b := s.recv(65536)):
            data += b
    return data.decode()


def waybar_pid():
    r = subprocess.run(["pgrep", "-x", "waybar"], capture_output=True, text=True)
    return int(r.stdout.split()[0]) if r.stdout.split() else None


pid = None
shown = True


def set_shown(want):
    global pid, shown
    cur = waybar_pid()
    if cur != pid:
        pid, shown = cur, True
    if cur and shown != want:
        os.kill(cur, signal.SIGUSR1)
        shown = want
        # Leiste da: Fenster darunter (Modus „maximiert“, die App merkt nichts); sonst echtes Vollbild
        if fs:
            hypr("dispatch hl.dsp.window.fullscreen_state({internal=%d, client=2})" % (1 if want else 2))


def fullscreen():
    try:
        return bool(json.loads(hypr("j/activeworkspace")).get("hasfullscreen"))
    except Exception:
        return False


# Menüs/Karten aus der Waybar (Layer-Flächen, öffnen kein Fenster): beenden das Vollbild
MENUS = {"wofi", "rofi", "volume-mixer", "swaync-control-center", "logout_dialog"}


def leave_fullscreen():
    try:
        ws = json.loads(hypr("j/activeworkspace"))["id"]
        for c in json.loads(hypr("j/clients")):
            if c["workspace"]["id"] == ws and c["fullscreen"]:
                hypr("dispatch hl.dsp.window.fullscreen_state({internal=0, client=0, window='address:%s'})" % c["address"])
    except Exception:
        pass


def cursor_y():
    try:
        return float(hypr("cursorpos").split(",")[1])
    except Exception:
        return 1e9


ev = socket.socket(socket.AF_UNIX)
ev.connect(f"{BASE}/.socket2.sock")
fs = fullscreen()
set_shown(not fs)
while True:
    r, _, _ = select.select([ev], [], [], 0.1 if fs else None)
    if r:
        data = ev.recv(65536)
        if not data:
            break
        # Neues Fenster (auch ein wieder eingeblendetes, z. B. rice-netz) oder Menü-Fläche beendet das Vollbild
        if fs and any((l.startswith("openlayer>>") and l[11:] in MENUS) or l.startswith("openwindow>>")
                      for l in data.decode(errors="replace").splitlines()):
            leave_fullscreen()
        new = fullscreen()
        if new != fs:
            fs = new
            set_shown(not fs)
    if fs:
        y = cursor_y()
        if y <= EDGE:
            set_shown(True)
        elif y > LEAVE:
            set_shown(False)
