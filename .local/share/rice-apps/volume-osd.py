#!/usr/bin/env python3
# On-screen display at the bottom center for volume AND brightness: one pill with a slider each as soon as the
# value changes (keys, waybar, mixer, Scourge …). If both are active they stack (brightness
# on top) instead of overlapping; if the musicalist preview is open, they move up over the card.
# Runs permanently (started from hyprland.lua via volume-osd). Volume via "pactl subscribe",
# brightness via kernel notification on /sys/class/backlight (no polling). Colors live from matugen.
# Start only through the start script: gtk4-layer-shell must be loaded before libwayland (LD_PRELOAD).
import glob, json, os, re, select, socket, subprocess, sys, threading, time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk
from gi.repository import Gtk4LayerShell as Layer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rice_i18n; rice_i18n.install()

MATUGEN_CSS = os.path.expanduser("~/.cache/ist/colors.css")
FALLBACK = "@define-color background #1a120d; @define-color foreground #f0dfd7; @define-color color9 #ffb68e;"
CSS = """
window.osd { background: none; }
.pill {
    background-color: @background; border: 2px solid @color9; border-radius: 22px;
    padding: 10px 18px; font-family: "JetBrainsMono Nerd Font", monospace; font-weight: 800;
    opacity: 0; transform: translateY(12px) scale(0.94);
    transition: opacity 160ms ease-in, transform 200ms ease-in;
}
.pill.on {
    opacity: 1; transform: none;
    transition: opacity 180ms ease-out, transform 260ms cubic-bezier(0.2, 0.9, 0.3, 1.15);
}
.icon { color: @color9; font-size: 20px; min-width: 26px; }
.pct { color: @foreground; font-size: 14px; min-width: 46px; }
.muted .icon, .muted .pct { color: alpha(@foreground, 0.45); }
levelbar trough { background-color: alpha(@foreground, 0.15); border-radius: 6px; min-height: 8px; border: none; }
levelbar block.filled { background-color: @color9; border-radius: 6px; border: none; }
levelbar block.empty { background: none; border: none; }
.muted levelbar block.filled { background-color: alpha(@foreground, 0.35); }
.over levelbar block.filled { background-color: #ffb4ab; }
"""
SHOW_MS = 1500        # how long a pill stays after the last change
SLIDE_MS = 220        # slide in/out (height) – counterpart to the CSS transition time
GAP = 10              # gap between the pills
BASE_MARGIN = 70      # distance to the bottom screen edge
WIDTH = 380           # fixed width: both pills equally wide, the surface never changes width
RUNTIME = os.environ.get("XDG_RUNTIME_DIR", "/tmp")


def read_volume():
    out = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], capture_output=True, text=True).stdout
    m = re.search(r"([\d.]+)", out)
    return (round(float(m.group(1)) * 100) if m else None), "MUTED" in out


def backlight_dir():
    devs = sorted(glob.glob("/sys/class/backlight/*"))
    return devs[0] if devs else None


def read_brightness(dev):
    try:
        with open(f"{dev}/brightness") as f:
            cur = int(f.read())
        with open(f"{dev}/max_brightness") as f:
            mx = int(f.read())
        return round(cur * 100 / mx) if mx else None
    except (OSError, ValueError):
        return None


def hypr(cmd):
    """Request to the Hyprland socket (fast, without a hyprctl process). None on error."""
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            s.connect(f"{RUNTIME}/hypr/{sig}/.socket.sock")
            s.sendall(cmd.encode())
            data = b""
            while chunk := s.recv(65536):
                data += chunk
        return json.loads(data)
    except (OSError, ValueError):
        return None


def music_card_top():
    """Distance of the top edge of the musicalist preview to the bottom screen edge (0 = not open)."""
    layers = hypr("j/layers")
    if not layers:
        return 0
    for mon in layers.values():
        for level in mon.get("levels", {}).values():
            for l in level:
                if l.get("namespace") == "music-preview" and l.get("h", 0) > 0:
                    mons = hypr("j/monitors") or []
                    for m in mons:
                        scale = m.get("scale", 1) or 1
                        mh = m["height"] / scale
                        if m["x"] <= l["x"] < m["x"] + m["width"] / scale:
                            return round(m["y"] + mh - l["y"])
    return 0


class Pill:
    """One display (icon, bar, percent) in a revealer that slides it open and closed smoothly."""

    def __init__(self, osd):
        self.osd = osd
        self.box = Gtk.Box(spacing=12)
        self.box.add_css_class("pill")
        self.icon = Gtk.Label(label="")
        self.icon.add_css_class("icon")
        self.bar = Gtk.LevelBar(min_value=0, max_value=100, mode=Gtk.LevelBarMode.CONTINUOUS,
                                valign=Gtk.Align.CENTER, hexpand=True)
        for name in ("low", "high", "full"):
            self.bar.remove_offset_value(name)
        self.pct = Gtk.Label(label="0%", xalign=1)
        self.pct.add_css_class("pct")
        for w in (self.icon, self.bar, self.pct):
            self.box.append(w)
        self.rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_UP,
                                transition_duration=SLIDE_MS, child=self.box)
        self.rev.connect("notify::child-revealed", lambda *_: osd.maybe_hide())
        self.hide_id = None
        self.shown_value = None       # displayed (animated) bar value
        self.target = 0
        self.tick_id = None

    @property
    def active(self):
        return self.rev.get_reveal_child() or self.rev.get_child_revealed()

    def show(self, value, icon, text, classes=()):
        self.icon.set_label(icon)
        self.pct.set_label(text)
        for cls in ("muted", "over"):
            (self.box.add_css_class if cls in classes else self.box.remove_css_class)(cls)
        fresh = not self.rev.get_reveal_child()
        self.animate_to(min(value, 100), jump=fresh)
        self.rev.set_reveal_child(True)
        self.box.add_css_class("on")
        if self.hide_id:
            GLib.source_remove(self.hide_id)
        self.hide_id = GLib.timeout_add(SHOW_MS, self.hide)

    def hide(self):
        self.hide_id = None
        self.box.remove_css_class("on")
        self.rev.set_reveal_child(False)
        return False

    # bar glides to the new value instead of jumping
    def animate_to(self, value, jump=False):
        self.target = value
        if jump or self.shown_value is None:
            self.shown_value = value
            self.bar.set_value(value)
            return
        self.start_value, self.start_time = self.shown_value, time.monotonic()
        if self.tick_id is None:
            self.tick_id = self.bar.add_tick_callback(self._tick)

    def _tick(self, _w, _clock):
        t = min(1.0, (time.monotonic() - self.start_time) / 0.14)
        ease = 1 - (1 - t) ** 3
        self.shown_value = self.start_value + (self.target - self.start_value) * ease
        self.bar.set_value(self.shown_value)
        if t >= 1.0:
            self.tick_id = None
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE


class OSD(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="de.invincible.VolumeOSD", flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.last_vol = self.last_bri = None
        self.margin = BASE_MARGIN
        self.margin_goal = BASE_MARGIN
        self.margin_tick = None
        self.watch_id = None

    def do_activate(self):
        self.hold()  # keeps running even without a visible window
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.load_css()
        self.mon = Gio.File.new_for_path(MATUGEN_CSS).monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.mon.connect("changed", lambda *_: GLib.timeout_add(150, lambda: self.load_css() and False))

        self.win = Gtk.Window(application=self)
        self.win.add_css_class("osd")
        Layer.init_for_window(self.win)
        Layer.set_namespace(self.win, "volume-osd")
        Layer.set_layer(self.win, Layer.Layer.OVERLAY)
        Layer.set_anchor(self.win, Layer.Edge.BOTTOM, True)
        Layer.set_margin(self.win, Layer.Edge.BOTTOM, self.margin)
        Layer.set_keyboard_mode(self.win, Layer.KeyboardMode.NONE)
        Layer.set_exclusive_zone(self.win, -1)

        self.vol = Pill(self)
        self.bri = Pill(self)
        # brightness on top, volume below; the gap belongs to the upper pill so it slides along
        self.bri.box.set_margin_bottom(GAP)
        stack = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.END)
        stack.set_size_request(WIDTH, 1)   # never 0×0 (otherwise invalid layer surface)
        stack.append(self.bri.rev)
        stack.append(self.vol.rev)
        self.win.set_child(stack)

        self.last_vol = read_volume()      # remember the start state, do not show it
        threading.Thread(target=self.listen_volume, daemon=True).start()
        self.dev = backlight_dir()
        if self.dev:
            self.last_bri = read_brightness(self.dev)
            threading.Thread(target=self.listen_brightness, daemon=True).start()

    def load_css(self):
        css = FALLBACK
        try:
            css += open(MATUGEN_CSS).read()
        except OSError:
            pass
        self.css.load_from_string(css + CSS)

    # ----- sources -----
    def listen_volume(self):
        while True:  # restart pactl in case PipeWire restarts
            p = subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                if "'change' on sink" in line or "'change' on server" in line:
                    GLib.idle_add(self.check_volume)
            p.wait()
            time.sleep(2)

    def listen_brightness(self):
        # the kernel reports every change via sysfs_notify on actual_brightness → poll() wakes up
        while True:
            try:
                with open(f"{self.dev}/actual_brightness") as f:
                    f.read()
                    poller = select.poll()
                    poller.register(f, select.POLLPRI | select.POLLERR)
                    while True:
                        if poller.poll():
                            f.seek(0)
                            f.read()
                            GLib.idle_add(self.check_brightness)
            except OSError:
                time.sleep(2)

    def check_volume(self):
        now = read_volume()
        if now[0] is not None and now != self.last_vol:
            self.last_vol = now
            vol, muted = now
            icon = "󰖁" if muted or vol == 0 else "󰕿" if vol < 34 else "󰖀" if vol < 67 else "󰕾"
            classes = [c for c, on in (("muted", muted), ("over", vol > 100)) if on]
            self.present(self.vol, vol, icon, "stumm" if muted else f"{vol}%", classes)
        return False

    def check_brightness(self):
        now = read_brightness(self.dev)
        if now is not None and now != self.last_bri:
            self.last_bri = now
            icon = "󰃞" if now < 34 else "󰃟" if now < 67 else "󰃠"
            self.present(self.bri, now, icon, f"{now}%")
        return False

    # ----- displays -----
    def present(self, pill, value, icon, text, classes=()):
        if not self.win.get_visible():
            self.set_margin(self.wanted_margin(), animate=False)
            self.win.set_visible(True)
        pill.show(value, icon, text, classes)
        if self.watch_id is None:     # while visible: dodge the music preview
            self.watch_id = GLib.timeout_add(200, self.watch)

    def maybe_hide(self):
        if not self.vol.active and not self.bri.active and self.win.get_visible():
            self.win.set_visible(False)

    def wanted_margin(self):
        top = music_card_top()
        return max(BASE_MARGIN, top + 12) if top else BASE_MARGIN

    def watch(self):
        if not self.win.get_visible():
            self.watch_id = None
            return False
        self.set_margin(self.wanted_margin())
        return True

    def set_margin(self, goal, animate=True):
        if goal == self.margin_goal and (self.margin == goal or self.margin_tick):
            return
        self.margin_goal = goal
        if not animate:
            self.margin = goal
            Layer.set_margin(self.win, Layer.Edge.BOTTOM, goal)
            return
        self.margin_from, self.margin_t0 = self.margin, time.monotonic()
        if self.margin_tick is None:
            self.margin_tick = self.win.add_tick_callback(self._margin_step)

    def _margin_step(self, _w, _clock):
        t = min(1.0, (time.monotonic() - self.margin_t0) / 0.22)
        ease = 1 - (1 - t) ** 3
        self.margin = round(self.margin_from + (self.margin_goal - self.margin_from) * ease)
        Layer.set_margin(self.win, Layer.Edge.BOTTOM, self.margin)
        if t >= 1.0:
            self.margin_tick = None
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE


if __name__ == "__main__":
    sys.exit(OSD().run(sys.argv))
