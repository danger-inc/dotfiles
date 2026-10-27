#!/usr/bin/env python3
"""Have the visible cursor redrawn after a theme change – without hiding it.

On `hyprctl setcursor` Hyprland loads the new theme but only redraws the currently visible cursor
when the requested cursor name changes. This invisible surface
covers the screen and itself shows the new arrow there (from the theme link, so already
in the new color). Then it disappears, the app below requests its shape again –
for Hyprland a different name, so it draws from the new theme. The pointer stays visible the whole
time. Hyprland only checks the pointer focus on movement, hence a 1 px nudge each.
"""
import json, subprocess

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gdk, GLib, Gtk, GtkLayerShell

def hypr(*args):
    return subprocess.run(["hyprctl", *args], capture_output=True, text=True).stdout


def cursor_pos():
    try:
        p = json.loads(hypr("-j", "cursorpos"))
        return round(p["x"]), round(p["y"])
    except (ValueError, KeyError):
        return None


def move(x, y):
    hypr("dispatch", f"hl.dsp.cursor.move({{ x = {x}, y = {y} }})")


def nudge(dx, expect=None):
    """Move the pointer 1 px – only if it is still where we expect it (otherwise the
    user is moving it right now, which triggers the re-check anyway)."""
    pos = cursor_pos()
    if pos is None or (expect is not None and pos != expect):
        return None
    move(pos[0] + dx, pos[1])
    return pos[0] + dx, pos[1]


# Full-screen (per monitor): even a moving pointer lands on it safely. It catches clicks
# only in the ~70 ms between appearing and disappearing.
wins = []
disp = Gdk.Display.get_default()
for i in range(disp.get_n_monitors()):
    win = Gtk.Window()
    GtkLayerShell.init_for_window(win)
    GtkLayerShell.set_namespace(win, "cursor-refresh")
    GtkLayerShell.set_layer(win, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_monitor(win, disp.get_monitor(i))
    for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
        GtkLayerShell.set_anchor(win, edge, True)
    GtkLayerShell.set_exclusive_zone(win, -1)      # also above the waybar
    GtkLayerShell.set_keyboard_mode(win, GtkLayerShell.KeyboardMode.NONE)
    win.set_app_paintable(True)
    win.set_visual(win.get_screen().get_rgba_visual())
    win.connect("draw", lambda w, cr: (cr.set_source_rgba(0, 0, 0, 0), cr.set_operator(1), cr.paint()) and False)
    wins.append(win)

state = {"pos": None, "done": False}


def finish(*_):
    if state["done"]:
        return False
    state["done"] = True
    for w in wins:
        w.destroy()
    Gdk.Display.get_default().flush()
    GLib.timeout_add(20, lambda: (nudge(-1, state["pos"]), Gtk.main_quit()) and False)
    return False


def on_realize(w):
    # "arrow" is unknown to the cursor-shape protocol → GTK draws it itself from the theme
    w.get_window().set_cursor(Gdk.Cursor.new_from_name(w.get_display(), "arrow"))


def on_map(*_):
    if not state.get("mapped"):
        state["mapped"] = True
        GLib.timeout_add(30, lambda: state.update(pos=nudge(1)) and False)
    return False


def on_enter(*_):
    if state.get("entered"):
        return False
    state["entered"] = True
    GLib.timeout_add(40, finish)  # GTK sets the cursor on enter; wait one frame
    return False


for win in wins:
    win.connect("realize", on_realize)
    win.connect("map-event", on_map)
    win.connect("enter-notify-event", on_enter)
    win.show_all()
GLib.timeout_add(1200, finish)  # Sicherheitsnetz
Gtk.main()
