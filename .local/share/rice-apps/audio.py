#!/usr/bin/env python3
# audio – Ersatz für pavucontrol (Rechtsklick auf den Lautsprecher in der Waybar).
# Tabs: ¹wiedergabe (Apps: Lautstärke, Ausgabegerät, Pegel) ²aufnahme (Apps am Mikrofon)
#       ³ausgabe / ⁴eingabe (Geräte: Standard, Anschluss, Lautstärke bis 150 %, Pegel) ⁵karten (Profile).
# Live über "pactl subscribe"; Pegel über parec (nur für den sichtbaren Tab, solange das Fenster offen ist).
import array, json, math, os, signal, subprocess, sys, threading, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tui
import rice_i18n; rice_i18n.install()
from tui import Gtk, GLib, label, hbox, vbox, esc

PEAK_CLIENT = "tui-peak"
APP_ICONS = {"firefox": "󰈹", "zen": "󰈹", "chromium": "", "chrome": "", "spotify": "", "discord": "󰙯",
             "vesktop": "󰙯", "mpv": "", "vlc": "󰕼", "steam": "", "telegram": "", "obs": "󰑋",
             "wine": "󰡶", "kitty": "", "scourge": "󰕧", "zoom": "󰍫", "teams": "󰊻", "musicalist": "󰝚"}
PORT_ICONS = {"Headphones": "󰋋", "Headset": "󰋎", "Speaker": "󰓃", "HDMI": "󰡁", "Mic": "󰍬",
              "Line": "󰟅", "Bluetooth": "󰂯"}


def pactl(*args):
    return subprocess.run(["pactl", *args], capture_output=True, text=True).stdout


def pjson(what):
    try:
        return json.loads(pactl("-f", "json", "list", what) or "[]")
    except ValueError:
        return []


def run(*cmd):
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def volume_of(obj):
    chans = list(obj.get("volume", {}).values())
    if not chans:
        return 0
    return round(sum(int(c["value_percent"].rstrip("%")) for c in chans) / len(chans))


def db_of(obj):
    chans = list(obj.get("volume", {}).values())
    try:
        d = max(float(c["db"].split()[0]) for c in chans)
        return "-∞ dB" if d == float("-inf") else f"{d:+.1f} dB"
    except (ValueError, KeyError, IndexError):
        return ""


def vol_glyph(vol, muted):
    return "󰖁" if muted or vol == 0 else "󰕿" if vol < 34 else "󰖀" if vol < 67 else "󰕾"


def snapshot():
    """Alles auf einmal aus PipeWire holen (im Hintergrund-Thread)."""
    return {
        "default_sink": pactl("get-default-sink").strip(),
        "default_source": pactl("get-default-source").strip(),
        "sinks": pjson("sinks"),
        "sources": [s for s in pjson("sources") if not s["name"].endswith(".monitor")],
        "inputs": pjson("sink-inputs"),
        "outputs": pjson("source-outputs"),
        "cards": pjson("cards"),
    }


def is_own(stream):
    p = stream.get("properties", {})
    name = (p.get("application.name") or "") + (p.get("media.name") or "")
    return PEAK_CLIENT in name or "peak detect" in name.lower() or p.get("media.role") == "event"


# ---------- Pegel ----------
class Peak:
    """Ein parec-Prozess, der laufend den Spitzenpegel (0–100, logarithmisch) misst."""

    def __init__(self, device, stream=None):
        cmd = ["parec", "--raw", "--format=s16le", "--rate=8000", "--channels=1", "--latency-msec=30",
               f"--client-name={PEAK_CLIENT}", f"--stream-name={PEAK_CLIENT}", "-d", device]
        if stream is not None:
            cmd.append(f"--monitor-stream={stream}")
        self.level = 0.0
        self.proc = tui.spawn_watch(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        while True:
            data = self.proc.stdout.read(480)
            if not data:
                return
            a = array.array("h", data[: len(data) // 2 * 2])
            p = max(max(a, default=0), -min(a, default=0)) / 32768
            lvl = 0 if p <= 0.001 else max(0.0, 1 + 20 * math.log10(p) / 60) * 100
            self.level = max(lvl, self.level)

    def take(self):
        """Wert zum Anzeigen; fällt danach sanft ab."""
        v = self.level
        self.level = max(0.0, v - 6)
        return v

    def stop(self):
        try:
            self.proc.kill()
        except OSError:
            pass


# ---------- Bausteine ----------
class VolumeLine(Gtk.Box):
    """󰕾 ■■■■■■■■····│···  64%   + optional Pegelzeile darunter."""

    def __init__(self, setter, muter, maximum=150, glyphs=None, peak=True):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.glyphs = glyphs  # (normal, stumm) oder None = Lautsprecher je nach Stufe
        self.mute = Gtk.Button(tooltip_text="Stumm an/aus (m)")
        self.mute.add_css_class("flat")
        self.mute.add_css_class("big")
        self.mute.connect("clicked", lambda *_: muter())
        self.pct = label("", "mono-pct", xalign=1)
        self.meter = tui.Meter(maximum, lambda v: (setter(v), self._pct(v)))
        line = hbox(self.mute, self.meter, self.pct, spacing=8)
        self.append(line)
        self.peak = None
        if peak:
            self.peak = tui.Meter(100, interactive=False, glyph="▪", small=True)
            self.peak.set_margin_start(40)
            self.peak.set_margin_end(54)
            self.append(self.peak)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, kv, *_: (kv in (ord("m"),) and (muter() or True)) or False)
        self.meter.add_controller(keys)

    def _pct(self, v):
        self.pct.set_label(f"{v}%")

    def update(self, vol, muted):
        self.meter.set_value(vol, muted)
        if not self.meter.pending:
            self.pct.set_label(f"{self.meter.value}%")
        if self.glyphs:
            self.mute.set_label(self.glyphs[1] if muted else self.glyphs[0])
        else:
            self.mute.set_label(vol_glyph(vol, muted))
        (self.mute.add_css_class if muted else self.mute.remove_css_class)("off")



def stream_name(i):
    p = i["properties"]
    return p.get("application.name") or p.get("application.process.binary") or p.get("node.name") or "Unbekannt"


def stream_glyph(i, fallback):
    p = i["properties"]
    hay = (p.get("application.process.binary", "") + " " + stream_name(i)).lower()
    return next((g for k, g in APP_ICONS.items() if k in hay), fallback)


def port_glyph(port, fallback):
    hay = (port or {}).get("type", "") + " " + (port or {}).get("name", "")
    return next((g for k, g in PORT_ICONS.items() if k.lower() in hay.lower()), fallback)


# ---------- App ----------
class AudioWindow(tui.TuiWindow):
    APP_ID = "de.invincible.Audio"

    def __init__(self, app):
        super().__init__(app, "󰕾 audio",
                         [("play", "wiedergabe"), ("rec", "aufnahme"), ("out", "ausgabe"),
                          ("in", "eingabe"), ("cards", "karten")],
                         size=(780, 620), hints=(("scroll/←→", "lautstärke"), ("m", "stumm")))
        self.data = None
        self.peaks = {}
        self.refresh_id = None
        self.busy = False
        self.again = False

        self.pages = {}
        for tid, empty in (("play", "󰝛  keine app spielt gerade ton ab"),
                           ("rec", "󰍭  keine app nimmt gerade auf"),
                           ("out", "keine ausgabegeräte"), ("in", "keine eingabegeräte"),
                           ("cards", "keine soundkarten")):
            box = vbox(spacing=6)
            box.set_margin_top(6)
            box.set_margin_bottom(6)
            lst = vbox(spacing=8)
            e = label(empty, "empty", xalign=0.5)
            box.append(lst)
            box.append(e)
            self.pages[tid] = (lst, e)
            self.add_page(tid, box)
        self.show_tab("play")

        self.on_refresh = self.refresh
        self.on_tab = lambda _t: self.sync_peaks()
        self.tick_id = None
        self.refresh()
        threading.Thread(target=self.listen, daemon=True).start()

    def on_show(self):
        self.refresh()
        if self.tick_id is None:
            self.tick_id = GLib.timeout_add(50, self.tick)

    def on_hide(self):
        for _spec, p in self.peaks.values():
            p.stop()
        self.peaks = {}
        if self.tick_id is not None:
            GLib.source_remove(self.tick_id)
            self.tick_id = None

    # ---------- Daten ----------
    def listen(self):
        while True:
            p = tui.spawn_watch(["pactl", "subscribe"], stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                if any(w in line for w in ("sink", "source", "server", "card")):
                    GLib.idle_add(self.schedule)
            p.wait()
            time.sleep(2)

    def schedule(self):
        if not self.get_visible():  # versteckt: beim nächsten Öffnen neu laden
            return False
        if self.refresh_id is None:
            self.refresh_id = GLib.timeout_add(50, self.refresh)
        return False

    def refresh(self):
        self.refresh_id = None
        if self.busy:
            self.again = True
            return False
        self.busy = True
        tui.background(snapshot, done=self.apply)
        return False

    def apply(self, data):
        self.busy = False
        if isinstance(data, Exception):
            self.say(f"pactl: {data}", error=True)
            return
        self.data = data
        self.sinks_by_index = {s["index"]: s for s in data["sinks"]}
        self.sources_by_index = {s["index"]: s for s in data["sources"]}
        self.fill_streams("play", [i for i in data["inputs"] if not is_own(i)], output=True)
        self.fill_streams("rec", [o for o in data["outputs"] if not is_own(o)], output=False)
        self.fill_devices("out", data["sinks"], data["default_sink"], output=True)
        self.fill_devices("in", data["sources"], data["default_source"], output=False)
        self.fill_cards(data["cards"])
        self.sync_peaks()
        if self.again:
            self.again = False
            self.refresh()

    def _set_empty(self, tid, items):
        lst, e = self.pages[tid]
        e.set_visible(not items)

    # ---------- Apps ----------
    def fill_streams(self, tid, streams, output):
        lst, _ = self.pages[tid]
        self._set_empty(tid, streams)
        devs = self.data["sinks"] if output else self.data["sources"]
        options = [(d["index"], d["description"]) for d in devs]

        def make(i):
            idx = i["index"]
            kind = "sink-input" if output else "source-output"
            p = tui.Panel()
            p.media = label("", "dim", hexpand=True, ellipsize=True)
            move = "move-sink-input" if output else "move-source-output"
            p.dev = tui.Select(lambda d: (run("pactl", move, str(idx), str(d)), self.say("gerät gewechselt")),
                               tooltip="Ausgabegerät für diese App" if output else "Mikrofon für diese App")
            p.vol = VolumeLine(lambda v: run("pactl", f"set-{kind}-volume", str(idx), f"{v}%"),
                               lambda: run("pactl", f"set-{kind}-mute", str(idx), "toggle"),
                               glyphs=None if output else ("󰍬", "󰍭"), peak=output)
            p.body.append(hbox(p.media, label("→" if output else "←", "accent"), p.dev))
            p.body.append(p.vol)
            return p

        def update(p, i):
            pr = i["properties"]
            name = stream_name(i)
            glyph = stream_glyph(i, "󰎆" if output else "󰍬")
            p.set_title(f"{glyph} {esc(name.lower())}", markup=True)
            media = pr.get("media.name", "")
            p.media.set_label(media if media and media.lower() != name.lower() else pr.get("application.process.binary", ""))
            p.dev.set_options(options, i.get("sink" if output else "source"))
            p.vol.update(volume_of(i), i["mute"])
            p.stream = i

        tui.sync_rows(lst, streams, lambda i: i["index"], make, update)

    # ---------- Geräte ----------
    def fill_devices(self, tid, devs, default, output):
        lst, _ = self.pages[tid]
        self._set_empty(tid, devs)
        kind = "sink" if output else "source"

        def make(d):
            name = d["name"]
            p = tui.Panel()
            p.std = tui.Button("★ als standard", lambda: (run("pactl", f"set-default-{kind}", name),
                                                          self.say(f"standard: {p.desc}")))
            p.is_std = label("★ standard", "accent")
            p.port = tui.Select(lambda port: run("pactl", f"set-{kind}-port", name, port), tooltip="Anschluss")
            p.info = label("", "dim", hexpand=True, ellipsize=True)
            p.vol = VolumeLine(lambda v: run("pactl", f"set-{kind}-volume", name, f"{v}%"),
                               lambda: run("pactl", f"set-{kind}-mute", name, "toggle"),
                               glyphs=None if output else ("󰍬", "󰍭"))
            p.body.append(hbox(p.info, p.port, p.std, p.is_std))
            p.body.append(p.vol)
            return p

        def update(p, d):
            p.desc = d["description"]
            is_default = d["name"] == default
            ports = d.get("ports", [])
            active = next((x for x in ports if x["name"] == d.get("active_port")), None)
            glyph = port_glyph(active, "󰓃" if output else "󰍬")
            if "bluez" in d["name"]:
                glyph = "󰂯"
            p.set_title(f"{glyph} {esc(d['description'])}", markup=True)
            p.set_active(is_default)
            p.std.set_visible(not is_default)
            p.is_std.set_visible(is_default)
            p.port.set_visible(len(ports) > 1)
            p.port.set_options([(x["name"], x["description"] + ("" if x.get("availability") != "not available"
                                                               else "  (nicht eingesteckt)")) for x in ports],
                               d.get("active_port"))
            state = {"RUNNING": "● aktiv", "IDLE": "○ bereit", "SUSPENDED": "◌ ruht"}.get(d.get("state"), "")
            p.info.set_label(f"{state}   {db_of(d)}   {d.get('sample_specification', '')}")
            p.vol.update(volume_of(d), d["mute"])
            p.dev = d

        tui.sync_rows(lst, devs, lambda d: d["name"], make, update)

    # ---------- Karten ----------
    def fill_cards(self, cards):
        lst, _ = self.pages["cards"]
        self._set_empty("cards", cards)

        def make(c):
            name = c["name"]
            p = tui.Panel()
            p.info = label("", "dim", hexpand=True, ellipsize=True)
            p.prof = tui.Select(lambda prof: (run("pactl", "set-card-profile", name, prof),
                                              self.say("profil gewechselt")), tooltip="Profil", max_chars=40)
            p.body.append(hbox(label("profil", "accent"), p.prof, p.info))
            return p

        def update(p, c):
            pr = c["properties"]
            desc = pr.get("device.description") or c["name"]
            glyph = "󰂯" if c["name"].startswith("bluez") else "󰡁" if "hdmi" in desc.lower() else "󰓃"
            p.set_title(f"{glyph} {esc(desc)}", markup=True)
            profs = sorted(c["profiles"].items(), key=lambda kv: (-kv[1].get("priority", 0)))
            opts = [(k, v["description"] + ("" if v.get("available", True) else "  (nicht verfügbar)"))
                    for k, v in profs]
            p.prof.set_options(opts, c["active_profile"])
            p.info.set_label(pr.get("api.alsa.card.name") or pr.get("device.bus", "") or c["driver"])
            p.set_active(c["active_profile"] != "off")

        tui.sync_rows(lst, cards, lambda c: c["name"], make, update)

    # ---------- Pegel ----------
    def wanted_peaks(self):
        if not self.data or not self.get_visible():
            return {}
        tab = self.current_tab()
        want = {}
        if tab == "out":
            for s in self.data["sinks"]:
                want[("dev", s["name"])] = (s["monitor_source"], None)
        elif tab == "in":
            for s in self.data["sources"]:
                want[("dev", s["name"])] = (s["name"], None)
        elif tab == "play":
            for i in self.data["inputs"]:
                sink = self.sinks_by_index.get(i.get("sink"))
                if sink and not is_own(i):
                    want[("stream", i["index"])] = (sink["monitor_source"], i["index"])
        return want

    def sync_peaks(self):
        want = self.wanted_peaks()
        for k in list(self.peaks):
            if k not in want or self.peaks[k][0] != want[k]:
                self.peaks.pop(k)[1].stop()
        for k, spec in want.items():
            if k not in self.peaks:
                self.peaks[k] = (spec, Peak(*spec))

    def tick(self):
        tab = self.current_tab()
        if tab in ("out", "in", "play") and self.peaks:
            lst, _ = self.pages[tab]
            for key, row in getattr(lst, "rows", {}).items():
                k = ("stream", key) if tab == "play" else ("dev", key)
                peak = self.peaks.get(k)
                if peak and row.vol.peak:
                    row.vol.peak.set_value(round(peak[1].take()))
        return True



if __name__ == "__main__":
    import ricetui
    ricetui.main("audio")
