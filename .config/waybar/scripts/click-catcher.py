#!/usr/bin/env python3
# Unsichtbare Fläche über allen Fenstern, aber unter der Waybar, solange ein Menü offen ist
# (wofi: WLAN/Bluetooth, rofi: Super+R). Ein Klick darauf schließt nur das Menü und erreicht
# kein Fenster. Die Waybar bleibt frei: ihre Fläche ist "exclusive" und wird ausgespart.
# Beendet sich von selbst, sobald kein Menü mehr offen ist.
import subprocess, time
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

MENUS = ("wofi", "rofi")
CLOSED = GLib.get_user_runtime_dir() + "/waybar-menu-closed"

def menu_open():
    return subprocess.run(["pgrep", "-x", "|".join(MENUS)], stdout=subprocess.DEVNULL).returncode == 0

def close_menus(*_):
    for m in MENUS:
        if subprocess.run(["pkill", "-x", m]).returncode == 0:
            with open(CLOSED, "w") as f:
                f.write(f"{int(time.time() * 1000)} {m}")
    Gtk.main_quit()
    return True

win = Gtk.Window()
GtkLayerShell.init_for_window(win)
GtkLayerShell.set_namespace(win, "click-catcher")
GtkLayerShell.set_layer(win, GtkLayerShell.Layer.TOP)
for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
    GtkLayerShell.set_anchor(win, edge, True)
GtkLayerShell.set_exclusive_zone(win, 0)       # 0 = Waybar-Bereich aussparen
GtkLayerShell.set_keyboard_mode(win, GtkLayerShell.KeyboardMode.NONE)

win.set_app_paintable(True)
win.set_visual(win.get_screen().get_rgba_visual())
win.connect("draw", lambda w, cr: (cr.set_source_rgba(0, 0, 0, 0), cr.set_operator(1), cr.paint()) and False)
win.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
win.connect("button-press-event", close_menus)

# Erst warten, bis das Menü da ist (max. 2 s), danach beenden, sobald es weg ist
start = time.monotonic()
def watch():
    if menu_open():
        watch.seen = True
    elif watch.seen or time.monotonic() - start > 2:
        Gtk.main_quit()
        return False
    return True
watch.seen = False
GLib.timeout_add(150, watch)

win.show_all()
Gtk.main()
