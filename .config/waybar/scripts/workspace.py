#!/usr/bin/env python3
# Workspace-Button für Waybar: ein Aufruf pro Workspace-Nummer.
# Ersetzt hyprland/workspaces, weil dessen Klick noch das alte
# "dispatch workspace N" schickt, das Hyprland im Lua-Modus ablehnt.
#   workspace.py N          -> gibt JSON aus, sobald sich der aktive Workspace ändert
#   workspace.py N --go     -> wechselt zu Workspace N (für on-click)
import json, os, socket, subprocess, sys

ws = sys.argv[1]

if "--go" in sys.argv:
    subprocess.run(["hyprctl", "dispatch", f"hl.dsp.focus({{ workspace = {ws} }})"],
                   stdout=subprocess.DEVNULL)
    sys.exit()


def active():
    try:
        out = subprocess.run(["hyprctl", "activeworkspace", "-j"],
                             capture_output=True, text=True).stdout
        return str(json.loads(out)["id"])
    except Exception:
        return None


last = None


def emit(cur):
    global last
    if cur == last:
        return
    last = cur
    print(json.dumps({"text": ws, "class": "active" if cur == ws else ""}), flush=True)


emit(active())

sock_path = os.path.join(os.environ["XDG_RUNTIME_DIR"], "hypr",
                         os.environ["HYPRLAND_INSTANCE_SIGNATURE"], ".socket2.sock")
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect(sock_path)
buf = b""
while True:
    data = s.recv(4096)
    if not data:
        break
    buf += data
    *lines, buf = buf.split(b"\n")
    for line in lines:
        ev, _, payload = line.decode(errors="ignore").partition(">>")
        if ev == "workspacev2":
            emit(payload.split(",")[0])
        elif ev in ("focusedmonv2", "moveworkspacev2"):
            emit(active())
