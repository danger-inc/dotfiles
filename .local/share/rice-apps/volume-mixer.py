#!/usr/bin/env python3
# Lautstärke-Mixer der Waybar (Linksklick aufs Lautsprecher-Icon): Karte unter dem Icon mit
# Gesamtlautstärke, Ausgabegerät, einem Regler pro App, die gerade Ton abspielt, und Mikrofon.
# Live über "pactl subscribe", Farben aus matugen, durchscheinend mit Blur (layer_rule "blur-volume-mixer").
#
# Läuft dauerhaft im Hintergrund (gestartet aus hyprland.lua), damit der Klick sofort wirkt:
#   SIGUSR1 = ein-/ausblenden (Waybar-Klick), SIGUSR2 = ausblenden (anderes Menü, Klick daneben).
# Sichtbar = Datei $XDG_RUNTIME_DIR/volume-mixer-open existiert (für menu-close-outside.sh),
# PID steht in $XDG_RUNTIME_DIR/volume-mixer.pid.
#
# Zwei Flächen: eine unsichtbare, bildschirmfüllende Klick-Fläche (Klick auf ein Fenster schließt nur
# den Mixer) und darüber die Karte selbst (Namespace "volume-mixer"). Esc schließt ebenfalls.
# Start nur über ~/.config/waybar/scripts/volume-mixer.sh (LD_PRELOAD für gtk4-layer-shell).
import json, os, signal, socket, subprocess, sys, threading, time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk
from gi.repository import Gtk4LayerShell as Layer

WIDTH = 380          # tatsächliche Kartenbreite inkl. Rahmen
BAR_MARGIN = 50      # margin-left/-right der Waybar (config.jsonc)
RUNTIME = GLib.get_user_runtime_dir()
OPEN_FLAG = RUNTIME + "/volume-mixer-open"
PID_FILE = RUNTIME + "/volume-mixer.pid"   # Skripte schicken Signale per kill statt (langsamem) pkill -f
MENU_OPENED = RUNTIME + "/waybar-menu-opened"
MATUGEN_CSS = os.path.expanduser("~/.cache/ist/colors.css")
FALLBACK = ("@define-color background #1a120d; @define-color foreground #f0dfd7; @define-color color9 #ffb68e;"
            "@define-color primary #ffb68e; @define-color on_primary #532200; @define-color secondary #e5bfa9;")
MODE_FILE = RUNTIME + "/volume-mixer-mode"   # „audio“ (Lautsprecher-Klick) oder „bright“ (Helligkeits-Klick)
BACKLIGHT = next((os.path.join("/sys/class/backlight", d) for d in sorted(os.listdir("/sys/class/backlight"))), None) if os.path.isdir("/sys/class/backlight") else None
CSS = """
/* -ist-Look wie scourge, notist, datist, musicalist und der Starter: dunkle Glasfläche, 1-px-Rahmen,
   kleine Abschnittstitel in der Akzentfarbe, flache Regler (4-px-Spur, schmaler Riegel). Altes Design: *.bak-ist */
window.catcher { background: none; }
/* Blur: wie bei swaync am ganzen Fenster anmelden (an der Karte greift es wegen der Einblend-Animation nicht) */
window.mixer { background: none; backdrop-filter: blur(10px); }
.card {
    background-color: alpha(@background, 0.85);
    border: 1px solid alpha(@primary, 0.55); border-radius: 6px; padding: 8px 12px 10px 12px;
    font-family: "JetBrainsMono Nerd Font", monospace; font-weight: bold; color: @foreground;
}
.section { font-size: 12px; color: @primary; margin: 6px 2px 0 2px; }
.section:first-child { margin-top: 0; }
.row { padding: 3px 2px; }
.icon-btn {
    background: none; border: none; box-shadow: none; padding: 0; min-width: 30px; min-height: 30px;
    border-radius: 4px; color: @primary; font-size: 17px;
}
.icon-btn:hover { background-color: alpha(@primary, 0.18); }
.icon-btn:disabled { color: @primary; }
.muted .icon-btn { color: alpha(@foreground, 0.45); }
.name { font-size: 13px; }
.pct { font-size: 12px; min-width: 40px; color: @secondary; }
scale { padding: 6px 0; }
scale trough { background-color: alpha(@foreground, 0.14); border-radius: 2px; min-height: 4px; border: none; }
scale highlight { background-color: @primary; border-radius: 2px; border: none; }
.muted scale highlight { background-color: alpha(@foreground, 0.4); }
scale slider {
    background: @primary; border: none; box-shadow: none; border-radius: 2px;
    min-width: 5px; min-height: 16px; margin: -6px 0;
}
.muted scale slider { background: alpha(@foreground, 0.6); }
.master .name { font-size: 13px; }
.devices, .presets { margin: 2px 0 2px 0; }
.chip {
    background: none; border: 1px solid alpha(@primary, 0.45);
    border-radius: 4px; padding: 1px 8px; min-height: 0; color: @foreground; font-size: 12px; box-shadow: none;
}
.chip:hover { background-color: @primary; border-color: @primary; color: @on_primary; }
.chip.active { background-color: alpha(@primary, 0.24); border-color: @primary; color: @foreground; }
.empty { font-size: 12px; padding: 4px 2px; color: @secondary; }
.hint { font-size: 11px; color: @secondary; margin-top: 6px; }
"""
APP_ICONS = {"firefox": "󰈹", "chromium": "", "google-chrome": "", "spotify": "", "discord": "󰙯",
             "vesktop": "󰙯", "mpv": "", "vlc": "󰕼", "steam": "", "telegram": "", "obs": "󰑋", "musicalist": "󰝚"}


def pactl(*args):
    return subprocess.run(["pactl", *args], capture_output=True, text=True).stdout


def pactl_json(what):
    try:
        return json.loads(pactl("-f", "json", "list", what) or "[]")
    except ValueError:
        return []


def run(*cmd):
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def hypr(cmd):
    """Direkt über den Hyprland-Socket statt hyprctl (spart einen Prozessstart)."""
    path = f"{RUNTIME}/hypr/{os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')}/.socket.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(path)
        s.sendall(b"j/" + cmd.encode())
        data = b""
        while chunk := s.recv(65536):
            data += chunk
    return json.loads(data)


def volume_of(obj):
    chans = list(obj.get("volume", {}).values())
    if not chans:
        return 0
    return round(sum(int(c["value_percent"].rstrip("%")) for c in chans) / len(chans))


def vol_icon(vol, muted):
    return "󰖁" if muted or vol == 0 else "󰕿" if vol < 34 else "󰖀" if vol < 67 else "󰕾"


class Row(Gtk.Box):
    """Symbol (Klick = stumm), Name, Prozent, Regler. setter(vol) / muter() führen die Aktion aus.
    icon: festes Zeichen; None = Lautsprecher-Symbol je nach Lautstärke."""

    def __init__(self, name, icon, setter, muter, icon_name=None, mute_icon=None):
        super().__init__(spacing=10)
        self.add_css_class("row")
        self.setter, self.muter = setter, muter
        self.icon, self.mute_icon = icon, mute_icon
        self.busy_until = 0
        self.pending = None
        self._sync = False

        self.btn = Gtk.Button(valign=Gtk.Align.CENTER, tooltip_text="Stumm an/aus" if muter else None,
                              sensitive=muter is not None)
        self.btn.add_css_class("icon-btn")
        if icon_name:
            self.btn.set_child(Gtk.Image(icon_name=icon_name, pixel_size=22))
        else:
            self.btn.set_label(icon or "")
        self.btn.connect("clicked", lambda *_: self.muter and self.muter())

        mid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
        head = Gtk.Box(spacing=6)
        self.name = Gtk.Label(label=name, xalign=0, hexpand=True, ellipsize=3)
        self.name.add_css_class("name")
        self.pct = Gtk.Label(xalign=1)
        self.pct.add_css_class("pct")
        head.append(self.name)
        head.append(self.pct)
        mid.append(head)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.scale.set_draw_value(False)
        self.scale.set_increments(1, 5)
        self.scale.connect("value-changed", self.on_change)
        mid.append(self.scale)

        self.append(self.btn)
        self.append(mid)

    def set_icon(self, vol, muted):
        if self.icon is None:
            self.btn.set_label(vol_icon(vol, muted))
        elif self.mute_icon:
            self.btn.set_label(self.mute_icon if muted else self.icon)

    def update(self, vol, muted):
        (self.add_css_class if muted else self.remove_css_class)("muted")
        self.set_icon(vol, muted)
        if time.monotonic() < self.busy_until:  # Nutzer zieht gerade: nicht dazwischenfunken
            return
        self.pct.set_label(f"{vol}%")
        self._sync = True
        self.scale.set_value(vol)
        self._sync = False

    def on_change(self, scale):
        if self._sync:
            return
        vol = round(scale.get_value())
        self.pct.set_label(f"{vol}%")
        self.set_icon(vol, self.has_css_class("muted"))
        self.busy_until = time.monotonic() + 0.5
        if self.pending is None:  # beim Ziehen höchstens alle 40 ms an PipeWire schicken
            GLib.timeout_add(40, self.flush)
        self.pending = vol

    def flush(self):
        if self.pending is not None:
            self.setter(self.pending)
        self.pending = None
        return False


class Mixer(Gtk.Application):
    def __init__(self, show_now):
        super().__init__(application_id="de.invincible.VolumeMixer", flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.show_now = show_now
        self.app_rows = {}
        self.app_keys = None
        self.sink_names = None
        self.refresh_id = None

    def do_activate(self):
        self.hold()  # läuft auch ohne sichtbares Fenster weiter
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.load_css()
        self.mon = Gio.File.new_for_path(MATUGEN_CSS).monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.mon.connect("changed", lambda *_: GLib.timeout_add(150, lambda: self.load_css() and False))

        # Unsichtbare Klick-Fläche: spart die Waybar aus (exclusive 0), Klick darauf schließt
        self.catcher = Gtk.Window(application=self)
        self.catcher.add_css_class("catcher")
        Layer.init_for_window(self.catcher)
        Layer.set_namespace(self.catcher, "volume-mixer-catcher")
        Layer.set_layer(self.catcher, Layer.Layer.TOP)
        for edge in (Layer.Edge.TOP, Layer.Edge.BOTTOM, Layer.Edge.LEFT, Layer.Edge.RIGHT):
            Layer.set_anchor(self.catcher, edge, True)
        Layer.set_exclusive_zone(self.catcher, 0)
        Layer.set_keyboard_mode(self.catcher, Layer.KeyboardMode.NONE)
        click = Gtk.GestureClick(button=0)
        click.connect("pressed", lambda *_: self.hide())
        self.catcher.add_controller(click)

        self.win = Gtk.Window(application=self)
        self.win.add_css_class("mixer")
        Layer.init_for_window(self.win)
        Layer.set_namespace(self.win, "volume-mixer")
        Layer.set_layer(self.win, Layer.Layer.OVERLAY)
        Layer.set_anchor(self.win, Layer.Edge.TOP, True)
        Layer.set_anchor(self.win, Layer.Edge.LEFT, True)
        Layer.set_margin(self.win, Layer.Edge.TOP, 10)
        Layer.set_exclusive_zone(self.win, 0)
        Layer.set_keyboard_mode(self.win, Layer.KeyboardMode.ON_DEMAND)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, kv, *_: (kv == Gdk.KEY_Escape and self.hide()) or False)
        self.win.add_controller(keys)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.add_css_class("card")
        outer.set_size_request(WIDTH, -1)
        self.win.set_child(outer)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.audio_box = card
        outer.append(card)
        self.mode = "audio"

        card.append(self.section("ausgabe"))
        self.master = Row("gesamt", None,
                          lambda v: run("pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{v}%"),
                          lambda: run("pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"))
        self.master.add_css_class("master")
        card.append(self.master)
        self.devices = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=6, row_spacing=6,
                                   max_children_per_line=3, homogeneous=False)
        self.devices.add_css_class("devices")
        card.append(self.devices)

        card.append(self.section("apps"))
        self.apps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.append(self.apps)

        self.mic_sep = self.section("mikrofon")
        card.append(self.mic_sep)
        self.mic = Row("mikrofon", "󰍬",
                       lambda v: run("pactl", "set-source-volume", "@DEFAULT_SOURCE@", f"{v}%"),
                       lambda: run("pactl", "set-source-mute", "@DEFAULT_SOURCE@", "toggle"),
                       mute_icon="󰍭")
        card.append(self.mic)

        # Helligkeit (Klick auf das Helligkeits-Modul): eigener Inhalt in derselben Karte
        self.bright_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=False)
        outer.append(self.bright_box)
        self.bright_box.append(self.section("bildschirm"))
        self.bright = Row("helligkeit", "󰃟", self.set_brightness, None)
        self.bright_box.append(self.bright)
        presets = Gtk.Box(spacing=6)
        presets.add_css_class("presets")
        for v in (10, 25, 50, 75, 100):
            b = Gtk.Button(label=f"{v} %")
            b.add_css_class("chip")
            b.connect("clicked", lambda _b, v=v: (self.set_brightness(v), self.bright.update(v, False)))
            presets.append(b)
        self.bright_box.append(presets)
        hint = Gtk.Label(label="mausrad auf dem modul: ±5 %", xalign=0)
        hint.add_css_class("hint")
        self.bright_box.append(hint)
        self.bright_poll = None
        self.shown_at = 0.0

        GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGUSR1, self.toggle)
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGUSR2, self.hide_request)
        for sig in (signal.SIGTERM, signal.SIGINT):
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, self.stop)

        with open(PID_FILE, "w") as f:
            f.write(f"{os.getpid()}\n")
        self.refresh()
        threading.Thread(target=self.listen, daemon=True).start()
        if self.show_now:
            self.show()
        else:  # einmal unsichtbar vorbereiten, damit schon der erste Klick sofort wirkt
            self.win.set_opacity(0)
            self.win.set_visible(True)
            GLib.timeout_add(300, self.prewarm_done)

    def prewarm_done(self):
        if not os.path.exists(OPEN_FLAG):
            self.win.set_visible(False)
        self.win.set_opacity(1)
        return False

    def stop(self):
        self.set_flag(False)
        try:
            os.unlink(PID_FILE)
        except OSError:
            pass
        self.quit()
        return False

    # ---------- Ein-/Ausblenden ----------
    def set_flag(self, on):
        try:
            if on:
                open(OPEN_FLAG, "w").close()
            else:
                os.unlink(OPEN_FLAG)
        except OSError:
            pass

    @staticmethod
    def section(text):
        l = Gtk.Label(label=text, xalign=0)
        l.add_css_class("section")
        return l

    def read_mode(self):
        try:
            m = open(MODE_FILE).read().strip()
        except OSError:
            m = "audio"
        return "bright" if m == "bright" and BACKLIGHT else "audio"

    def set_mode(self, mode):
        self.mode = mode
        self.audio_box.set_visible(mode == "audio")
        self.bright_box.set_visible(mode == "bright")
        if mode == "bright":
            self.read_brightness()

    # ---------- Helligkeit ----------
    def brightness(self):
        try:
            cur = int(open(BACKLIGHT + "/brightness").read())
            mx = int(open(BACKLIGHT + "/max_brightness").read()) or 1
            return round(cur * 100 / mx)
        except (OSError, ValueError, TypeError):
            return 0

    def set_brightness(self, v):
        run("brightnessctl", "-q", "-n2", "set", f"{max(1, int(v))}%")

    def read_brightness(self):
        v = self.brightness()
        self.bright.update(v, False)
        self.bright.set_icon(v, False)
        self.bright.btn.set_label("󰃞" if v < 34 else "󰃟" if v < 67 else "󰃠")
        return self.win.get_visible() and self.mode == "bright"   # weiterpollen, solange sichtbar

    def toggle(self):
        mode = self.read_mode()
        if self.win.get_visible() and mode == self.mode:
            self.hide()
        else:
            self.show()
        return True

    def hide_request(self):
        # Klick aufs andere Icon (Lautstärke <-> Helligkeit): menu-close-outside.sh läuft parallel
        # und kann sein Ausblenden erst nach dem Umschalten schicken – das dann ignorieren.
        if time.monotonic() - self.shown_at > 0.5:
            self.hide()
        return True

    def show(self):
        self.shown_at = time.monotonic()
        try:
            with open(MENU_OPENED, "w") as f:  # Klick aufs Icon soll den Mixer nicht gleich wieder schließen
                f.write(f"{int(time.time() * 1000)} mixer")
        except OSError:
            pass
        run("pkill", "-x", "wofi|rofi")  # andere Menüs samt ihrer Klick-Sperre zu
        run("pkill", "-f", "python3 .*click-catcher\\.py")
        self.set_mode(self.read_mode())
        if self.mode == "bright" and self.bright_poll is None:
            self.bright_poll = GLib.timeout_add(500, self._poll_bright)
        Layer.set_margin(self.win, Layer.Edge.LEFT, self.position())
        self.set_flag(True)
        self.catcher.set_visible(True)
        self.win.set_visible(True)

    def _poll_bright(self):
        if self.read_brightness():
            return True
        self.bright_poll = None
        return False

    def hide(self):
        self.win.set_visible(False)
        self.catcher.set_visible(False)
        self.set_flag(False)

    def position(self):
        """x-Abstand: zentriert unter dem Mauszeiger (= dem Icon), nicht über die Waybar hinaus."""
        try:
            cur = hypr("cursorpos")
            mon = next(m for m in hypr("monitors") if m["focused"])
            mon_w = int(mon["width"] / mon["scale"])
            x = int(cur["x"]) - mon["x"] - WIDTH // 2
            return max(BAR_MARGIN, min(x, mon_w - BAR_MARGIN - WIDTH))
        except (OSError, ValueError, StopIteration, KeyError):
            return BAR_MARGIN

    def load_css(self):
        css = FALLBACK
        try:
            css += open(MATUGEN_CSS).read()
        except OSError:
            pass
        self.css.load_from_string(css + CSS)

    def listen(self):
        while True:  # pactl neu starten, falls PipeWire neu startet
            p = subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                if any(w in line for w in ("sink", "source", "server")):
                    GLib.idle_add(self.schedule_refresh)
            p.wait()
            time.sleep(2)

    def schedule_refresh(self):
        if self.refresh_id is None:
            self.refresh_id = GLib.timeout_add(40, self.refresh)
        return False

    # ---------- Daten aus PipeWire übernehmen ----------
    def refresh(self):
        self.refresh_id = None
        default_sink = pactl("get-default-sink").strip()
        default_source = pactl("get-default-source").strip()
        sinks = pactl_json("sinks")

        for s in sinks:
            if s["name"] == default_sink:
                self.master.update(volume_of(s), s["mute"])
        self.update_devices(sinks, default_sink)

        src = next((s for s in pactl_json("sources") if s["name"] == default_source
                    and not s["name"].endswith(".monitor")), None)
        self.mic.set_visible(src is not None)
        self.mic_sep.set_visible(src is not None)
        if src:
            self.mic.update(volume_of(src), src["mute"])

        self.update_apps(pactl_json("sink-inputs"))
        return False

    def update_devices(self, sinks, default):
        names = [(s["name"], s["description"]) for s in sinks]
        self.devices.set_visible(len(sinks) > 1)
        if names != self.sink_names:
            self.sink_names = names
            while (c := self.devices.get_first_child()):
                self.devices.remove(c)
            self.device_btns = {}
            for name, desc in names:
                b = Gtk.Button(label=desc, tooltip_text=desc)
                b.add_css_class("chip")
                b.get_child().set_ellipsize(3)
                b.get_child().set_max_width_chars(22)
                b.connect("clicked", lambda _b, n=name: run("pactl", "set-default-sink", n))
                self.devices.append(b)
                self.device_btns[name] = b
        for name, b in self.device_btns.items():
            (b.add_css_class if name == default else b.remove_css_class)("active")

    def update_apps(self, inputs):
        # Systemklänge und Pegelmesser (z. B. von pavucontrol) ausblenden
        inputs = [i for i in inputs if i["properties"].get("media.role") != "event"
                  and "peak" not in i["properties"].get("media.name", "").lower()]
        keys = [i["index"] for i in inputs]
        if keys != self.app_keys:
            self.app_keys = keys
            while (c := self.apps.get_first_child()):
                self.apps.remove(c)
            self.app_rows = {}
            for i in inputs:
                row = self.app_row(i)
                self.app_rows[i["index"]] = row
                self.apps.append(row)
            if not inputs:
                empty = Gtk.Label(label="󰝛  keine app spielt ton ab", xalign=0)
                empty.add_css_class("empty")
                self.apps.append(empty)
        for i in inputs:
            self.app_rows[i["index"]].update(volume_of(i), i["mute"])

    def app_row(self, i):
        props = i["properties"]
        idx = i["index"]
        name = props.get("application.name") or props.get("application.process.binary") or "Unbekannt"
        binary = props.get("application.process.binary", "").lower()
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        icon_name = next((n for n in (props.get("application.icon_name"), binary, name.lower())
                          if n and theme.has_icon(n)), None)
        glyph = next((g for k, g in APP_ICONS.items() if k in binary or k in name.lower()), "󰎆")
        return Row(name, glyph,
                   lambda v: run("pactl", "set-sink-input-volume", str(idx), f"{v}%"),
                   lambda: run("pactl", "set-sink-input-mute", str(idx), "toggle"),
                   icon_name=icon_name)


if __name__ == "__main__":
    sys.exit(Mixer("--show" in sys.argv).run(sys.argv[:1]))
