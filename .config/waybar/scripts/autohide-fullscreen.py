#!/usr/bin/env python3
"""Hide waybar in fullscreen and show it when the top screen edge is touched.
Waybar is on the overlay layer (above fullscreen windows); outside fullscreen it stays
visible as usual and reserves its space. Visibility is toggled via SIGUSR1, the state is
counted here (back to "visible" for a new waybar process)."""
import json, os, sys, select, signal, socket, subprocess, time

RT = os.environ["XDG_RUNTIME_DIR"]
HIS = os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
BASE = f"{RT}/hypr/{HIS}"
EDGE = 1       # pixels from the top edge from which it is shown
LEAVE = 80     # below that hide again (bar: 10 margin + 46 height)


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
        # bar present: window below it (mode "maximized", the app notices nothing); otherwise real fullscreen
        if fs:
            hypr("dispatch hl.dsp.window.fullscreen_state({internal=%d, client=2})" % (1 if want else 2))


def fullscreen():
    try:
        return bool(json.loads(hypr("j/activeworkspace")).get("hasfullscreen"))
    except Exception:
        return False


# menus/cards from the waybar (layer surfaces, open no window): end the fullscreen
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
        # a new window (also a re-shown one, e.g. rice-netz) or menu surface ends the fullscreen
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
