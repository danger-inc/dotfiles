#!/usr/bin/env python3
# bluetooth – Ersatz für blueman-manager (Rechtsklick auf Bluetooth in der Waybar).
# Tabs: ¹geräte (bekannte Geräte: verbinden, Akku, vertrauen, blockieren, entfernen, Audio-Profil)
#       ²suchen (Suche läuft, solange der Tab offen ist; koppeln) ³adapter (an/aus, sichtbar, Name …).
# Direkt über D-Bus (BlueZ) – Änderungen kommen live an. Solange das Fenster offen ist, ist es auch
# der Pairing-Agent: PIN-Abfragen erscheinen als Hinweis oben im Fenster.
import json, os, signal, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tui
import rice_i18n; rice_i18n.install()
from tui import Gio, GLib, Gtk, label, hbox, vbox, esc

BUS = "org.bluez"
DEV, ADP, BAT = "org.bluez.Device1", "org.bluez.Adapter1", "org.bluez.Battery1"
AGENT_PATH = "/de/invincible/bluetooth/agent"
ICONS = {"audio-headset": "󰋎", "audio-headphones": "󰋋", "audio-card": "󰓃", "input-keyboard": "󰌌",
         "input-mouse": "󰍽", "input-gaming": "󰊴", "input-tablet": "󰓶", "phone": "󰏲", "computer": "󰟀",
         "video-display": "󰍹", "camera-photo": "󰄀", "printer": "󰐪", "modem": "󰑩", "network-wireless": "󰖩"}
SERVICES = {"0000110b": "audio", "0000110a": "audio-quelle", "0000111e": "freisprechen", "00001108": "headset",
            "00001124": "eingabe", "00001812": "eingabe", "0000180f": "akku", "0000110e": "fernbedienung",
            "00001105": "dateien", "0000112f": "telefonbuch", "00001132": "nachrichten", "00001116": "netz"}
AGENT_XML = """<node><interface name="org.bluez.Agent1">
<method name="Release"/>
<method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
<method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
<method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
<method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/></method>
<method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
<method name="RequestAuthorization"><arg type="o" direction="in"/></method>
<method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
<method name="Cancel"/>
</interface></node>"""


def prop(proxy, name, default=None):
    v = proxy.get_cached_property(name) if proxy else None
    return default if v is None else v.unpack()


def rssi_pct(rssi):
    return 0 if rssi is None else max(0, min(100, (rssi + 100) * 2))


def nice_error(e):
    msg = getattr(e, "message", str(e))
    msg = msg.split(":", 2)[-1].strip() if "GDBus.Error" in msg else msg
    return {"br-connection-profile-unavailable": "kein passendes profil (gerät aus oder außer reichweite?)",
            "Page Timeout": "gerät antwortet nicht", "Host is down": "gerät ist aus oder außer reichweite",
            "Authentication Failed": "koppeln fehlgeschlagen (pin falsch?)",
            "Authentication Rejected": "koppeln abgelehnt", "Already Exists": "schon gekoppelt",
            "Not Ready": "adapter ist aus", "Operation already in progress": "läuft schon …",
            "In Progress": "läuft schon …", "Resource Not Ready": "adapter ist aus"}.get(msg, msg)


class BtWindow(tui.TuiWindow):
    APP_ID = "de.invincible.Bluetooth"

    def __init__(self, app):
        super().__init__(app, "󰂯 bluetooth", [("devs", "geräte"), ("scan", "suchen"), ("adapter", "adapter")],
                         size=(740, 600), hints=(("klick", "aufklappen"),))
        self.refresh_id = None
        self.scanning = False
        self.agent_id = None
        self.pending = None
        self.cards = {}
        try:
            self.mgr = Gio.DBusObjectManagerClient.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusObjectManagerClientFlags.NONE, BUS, "/", None, None, None)
        except GLib.Error as e:
            self.mgr = None
            self.say(f"bluez nicht erreichbar: {e.message}", error=True, seconds=600)

        # Hinweis für PIN-Abfragen (Agent)
        self.banner = vbox(spacing=6)
        self.banner.add_css_class("banner")
        self.banner.set_visible(False)
        self.content.prepend(self.banner)

        # ¹ geräte
        page = vbox(spacing=8)
        page.set_margin_top(6)
        self.power = tui.Check("bluetooth", callback=self.set_power)
        self.summary = label("", "dim", hexpand=True, ellipsize=True)
        page.append(tui.Panel("󰂯 status", hbox(self.power, self.summary,
                                                tui.Button("+ gerät koppeln", lambda: self.show_tab("scan")),
                                                spacing=12)))
        self.known_panel = tui.Panel("geräte")
        self.devlist = vbox(spacing=0)
        self.known_empty = label("noch keine geräte – unter ²suchen koppeln", "empty", xalign=0.5)
        self.known_panel.body.append(self.devlist)
        self.known_panel.body.append(self.known_empty)
        page.append(self.known_panel)
        self.add_page("devs", page)

        # ² suchen
        page = vbox(spacing=8)
        page.set_margin_top(6)
        self.scan_state = label("", "accent", hexpand=True)
        self.unnamed = tui.Check("unbenannte zeigen", callback=lambda _o: self.schedule())
        self.scan_btn = tui.Button("", self.toggle_scan)
        page.append(tui.Panel("󰂰 suche", hbox(self.scan_state, self.unnamed, self.scan_btn, spacing=12)))
        self.found_panel = tui.Panel("in der nähe")
        self.found = vbox(spacing=0)
        self.found_empty = label("", "empty", xalign=0.5)
        self.found_panel.body.append(self.found)
        self.found_panel.body.append(self.found_empty)
        page.append(self.found_panel)
        self.add_page("scan", page)

        # ³ adapter
        page = vbox(spacing=8)
        page.set_margin_top(6)
        self.adp_panel = tui.Panel("adapter")
        self.a_power = tui.Check("eingeschaltet", callback=self.set_power)
        self.a_disc = tui.Check("sichtbar für andere", callback=lambda on: self.set_adapter("Discoverable", on))
        self.a_pair = tui.Check("koppelbar", callback=lambda on: self.set_adapter("Pairable", on))
        self.a_timeout = tui.Select(lambda t: self.set_adapter("DiscoverableTimeout", GLib.Variant("u", t)),
                                    tooltip="Wie lange sichtbar")
        self.a_name = tui.Entry("name", activate=self.save_name)
        self.a_info = Gtk.Grid(column_spacing=14, row_spacing=3)
        b = self.adp_panel.body
        b.append(hbox(self.a_power, self.a_pair, spacing=16))
        b.append(hbox(self.a_disc, label("für", "dim"), self.a_timeout, spacing=10))
        b.append(hbox(label("name", "dim"), self.a_name, tui.Button("speichern", self.save_name), spacing=10))
        b.append(self.a_info)
        page.append(self.adp_panel)
        self.add_page("adapter", page)
        self.show_tab("devs")

        self.on_tab = self.tab_changed
        self.on_refresh = self.schedule
        if self.mgr:
            for sig in ("object-added", "object-removed", "interface-added", "interface-removed",
                        "interface-proxy-properties-changed"):
                self.mgr.connect(sig, lambda *_: self.schedule())
            self.register_agent()
        self.spin = 0
        self.spin_id = None
        self.refresh()

    def on_show(self):
        self.refresh()
        self.load_cards()
        self.tab_changed(self.current_tab())
        if self.spin_id is None:
            self.spin_id = GLib.timeout_add(90, self.spinner)

    def on_hide(self):
        if self.spin_id is not None:
            GLib.source_remove(self.spin_id)
            self.spin_id = None
        self.reject_pending()
        self.hide_banner()
        if self.adapter is not None and self.scanning:
            self.call(self.adapter, "StopDiscovery")

    def spinner(self):
        if self.scanning:
            self.spin += 1
            self.scan_state.set_label("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[self.spin % 10] + " sucht …")
        return True

    # ---------- D-Bus ----------
    def objects(self):
        if not self.mgr:
            return None, []
        adapter, devs = None, []
        for obj in self.mgr.get_objects():
            a = obj.get_interface(ADP)
            if a and adapter is None:
                adapter = a
            d = obj.get_interface(DEV)
            if d:
                devs.append((d, obj.get_interface(BAT)))
        return adapter, devs

    def call(self, proxy, method, args=None, ok=None, start=None, timeout=60000, done=None):
        if start:
            self.say(start, seconds=60)

        def cb(p, res):
            try:
                p.call_finish(res)
                if ok:
                    self.say(ok)
                if done:
                    done(True)
            except GLib.Error as e:
                self.say(nice_error(e), error=True, seconds=10)
                if done:
                    done(False)
        proxy.call(method, args, Gio.DBusCallFlags.NONE, timeout, None, cb)

    def set_prop(self, proxy, iface, name, value, ok=None):
        if isinstance(value, bool):
            value = GLib.Variant("b", value)
        elif isinstance(value, str):
            value = GLib.Variant("s", value)
        self.call(proxy, "org.freedesktop.DBus.Properties.Set", GLib.Variant("(ssv)", (iface, name, value)), ok=ok)

    def schedule(self):
        if not self.get_visible():
            return
        if self.refresh_id is None:
            self.refresh_id = GLib.timeout_add(80, self.refresh)

    # ---------- Agent (PIN / Bestätigung beim Koppeln) ----------
    def register_agent(self):
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM)
            info = Gio.DBusNodeInfo.new_for_xml(AGENT_XML).interfaces[0]
            self.agent_id = bus.register_object(AGENT_PATH, info, self.agent_call, None, None)
            self.bus = bus
            am = Gio.DBusProxy.new_sync(bus, Gio.DBusProxyFlags.NONE, None, BUS, "/org/bluez",
                                        "org.bluez.AgentManager1", None)
            am.call_sync("RegisterAgent", GLib.Variant("(os)", (AGENT_PATH, "KeyboardDisplay")),
                         Gio.DBusCallFlags.NONE, 3000, None)
            am.call_sync("RequestDefaultAgent", GLib.Variant("(o)", (AGENT_PATH,)), Gio.DBusCallFlags.NONE, 3000, None)
            self.agent_mgr = am
        except GLib.Error as e:
            self.say(f"pairing-agent: {nice_error(e)}", error=True)

    def dev_name(self, path):
        obj = self.mgr.get_object(path) if self.mgr else None
        d = obj.get_interface(DEV) if obj else None
        return prop(d, "Alias", path.rsplit("/", 1)[-1]), d

    def agent_call(self, _conn, _sender, _path, _iface, method, params, inv):
        args = params.unpack()
        if method in ("Release", "Cancel"):
            self.hide_banner()
            inv.return_value(None)
            return
        name, dev = self.dev_name(args[0]) if args else ("", None)
        if method == "DisplayPinCode":
            self.show_banner(f"pin für {name}: <b>{esc(args[1])}</b> – am gerät eingeben", None)
            inv.return_value(None)
        elif method == "DisplayPasskey":
            self.show_banner(f"code für {name}: <b>{args[1]:06d}</b> – am gerät eingeben", None)
            inv.return_value(None)
        elif method == "RequestConfirmation":
            self.show_banner(f"stimmt dieser code auf {esc(name)} überein?  <b>{args[1]:06d}</b>", inv)
        elif method in ("RequestPinCode", "RequestPasskey"):
            self.show_banner(f"pin für {esc(name)} eingeben (steht oft in der anleitung, sonst 0000)", inv,
                             entry="s" if method == "RequestPinCode" else "u")
        elif method in ("RequestAuthorization", "AuthorizeService"):
            if dev and (prop(dev, "Trusted") or prop(dev, "Paired")) and method == "AuthorizeService":
                inv.return_value(None)
            else:
                self.show_banner(f"{esc(name)} möchte sich verbinden. erlauben?", inv)
        else:
            inv.return_dbus_error("org.bluez.Error.Rejected", "unbekannt")

    def show_banner(self, markup, inv, entry=None):
        self.reject_pending()
        self.pending = inv
        tui.clear(self.banner)
        self.banner.append(label("󰂯 " + markup, markup=True, wrap=True))
        if inv is not None:
            row = hbox(spacing=8)
            e = None
            if entry:
                e = tui.Entry("pin", width=12)
                row.append(e)

            def accept():
                if self.pending is not inv:
                    return
                self.pending = None
                if entry == "s":
                    inv.return_value(GLib.Variant("(s)", (e.get_text() or "0000",)))
                elif entry == "u":
                    try:
                        inv.return_value(GLib.Variant("(u)", (int(e.get_text() or "0"),)))
                    except ValueError:
                        inv.return_dbus_error("org.bluez.Error.Rejected", "keine zahl")
                else:
                    inv.return_value(None)
                self.hide_banner()
            if e:
                e.connect("activate", lambda *_: accept())
            row.append(tui.Button("ja" if not entry else "ok", accept))
            row.append(tui.Button("nein", lambda: (self.reject_pending(), self.hide_banner()), danger=True))
            self.banner.append(row)
            if e:
                GLib.idle_add(e.grab_focus)
        else:
            self.banner.append(hbox(tui.Button("ok", self.hide_banner)))
        self.banner.set_visible(True)
        self.present()

    def reject_pending(self):
        if self.pending is not None:
            self.pending.return_dbus_error("org.bluez.Error.Rejected", "abgelehnt")
            self.pending = None

    def hide_banner(self):
        self.banner.set_visible(False)

    # ---------- Anzeige ----------
    def refresh(self):
        self.refresh_id = None
        adapter, devs = self.objects()
        self.adapter = adapter
        powered = bool(prop(adapter, "Powered"))
        self.scanning = bool(prop(adapter, "Discovering"))
        self.power.set_active(powered)
        self.power.set_sensitive(adapter is not None)

        known = [d for d in devs if prop(d[0], "Paired") or prop(d[0], "Bonded") or prop(d[0], "Trusted")
                 or prop(d[0], "Connected")]
        known.sort(key=lambda d: (not prop(d[0], "Connected"), prop(d[0], "Alias", "").lower()))
        show_unnamed = self.unnamed.active
        found = [d for d in devs if d not in known and (show_unnamed or prop(d[0], "Name"))
                 and prop(d[0], "RSSI") is not None]
        found.sort(key=lambda d: -(prop(d[0], "RSSI") or -999))

        conn = [prop(d[0], "Alias") for d in known if prop(d[0], "Connected")]
        if adapter is None:
            self.summary.set_label("kein bluetooth-adapter gefunden")
        elif not powered:
            self.summary.set_label("ausgeschaltet")
        else:
            self.summary.set_label(("● " + ", ".join(conn)) if conn else "○ nichts verbunden")
        self.known_panel.set_title(f"geräte <span alpha='60%'>{len(known)}</span>", markup=True)
        self.known_empty.set_visible(not known)
        tui.sync_rows(self.devlist, known, lambda d: d[0].get_object_path(), self.make_dev, self.update_dev)

        self.scan_btn.set_label("■ stopp" if self.scanning else "⟳ suchen")
        self.scan_btn.set_sensitive(powered)
        self.scan_state.set_label("sucht … " if self.scanning else "bluetooth ist aus" if not powered
                                  else "suche gestoppt")
        self.found_empty.set_visible(not found)
        self.found_empty.set_label("nichts gefunden – gerät in den kopplungsmodus versetzen" if self.scanning
                                   else "⟳ suchen starten")
        self.found_panel.set_title(f"in der nähe <span alpha='60%'>{len(found)}</span>", markup=True)
        tui.sync_rows(self.found, found, lambda d: d[0].get_object_path(), self.make_dev, self.update_dev)
        self.fill_adapter(adapter)
        return False

    def make_dev(self, d):
        row = tui.Row(on_toggle=self.on_dev_toggle)
        row.glyph = label("", "glyph")
        row.name = label("", hexpand=True, ellipsize=True)
        row.bat = label("", "accent", markup=True)
        row.sig = label("", "accent", markup=True)
        row.state = label("", "accent")
        row.set_head(hbox(row.glyph, row.name, row.bat, row.state, row.sig, spacing=10))
        row.key = None
        return row

    def update_dev(self, row, d):
        dev, bat = d
        row.dev, row.batp = dev, bat
        alias = prop(dev, "Alias", "?")
        row.glyph.set_label(ICONS.get(prop(dev, "Icon", ""), "󰂯"))
        row.name.set_label(alias)
        pct = prop(bat, "Percentage")
        row.bat.set_visible(pct is not None)
        if pct is not None:
            row.bat.set_markup(tui.battery(pct))
        connected, paired = prop(dev, "Connected"), prop(dev, "Paired")
        blocked = prop(dev, "Blocked")
        row.state.set_label("⊘ blockiert" if blocked else "● verbunden" if connected
                            else "" if paired else "neu")
        rssi = prop(dev, "RSSI")
        row.sig.set_visible(rssi is not None and not connected)
        if rssi is not None:
            row.sig.set_markup(tui.bars(rssi_pct(rssi)) + f" <span alpha='70%'>{rssi}</span>")
        (row.add_css_class if connected else row.remove_css_class)("connected")
        key = (connected, paired, prop(dev, "Trusted"), blocked)
        if key != row.key:
            row.key = key
            self.build_dev_body(row)

    def build_dev_body(self, row):
        tui.clear(row.body)
        dev = row.dev
        alias = prop(dev, "Alias", "?")
        connected, paired = prop(dev, "Connected"), prop(dev, "Paired")
        btns = hbox(spacing=8)
        if connected:
            btns.append(tui.Button("trennen", lambda: self.call(dev, "Disconnect", ok=f"{alias} getrennt",
                                                                 start=f"trenne {alias} …")))
        elif paired:
            btns.append(tui.Button("verbinden", lambda: self.call(dev, "Connect", ok=f"{alias} verbunden",
                                                                   start=f"verbinde mit {alias} …")))
        else:
            btns.append(tui.Button("koppeln + verbinden", lambda: self.pair(dev)))
        if paired or prop(dev, "Trusted"):
            btns.append(tui.Check("vertraut", prop(dev, "Trusted"),
                                  lambda on: self.set_prop(dev, DEV, "Trusted", on),
                                  tooltip="Darf sich ohne Nachfrage verbinden"))
        btns.append(tui.Check("blockiert", prop(dev, "Blocked"), lambda on: self.set_prop(dev, DEV, "Blocked", on)))
        btns.append(label("", hexpand=True))
        if paired or prop(dev, "Trusted"):
            btns.append(tui.Button("entfernen", lambda: self.remove(row), danger=True))
        row.body.append(btns)
        # Audio-Profil (Kopfhörer: Musik vs. Freisprechen)
        row.profile_box = hbox(label("profil", "dim"), spacing=10)
        row.profile = tui.Select(lambda p: self.set_profile(row, p), max_chars=40)
        row.profile_box.append(row.profile)
        row.profile_box.set_visible(False)
        row.body.append(row.profile_box)
        uuids = prop(dev, "UUIDs", []) or []
        services = sorted({SERVICES[u[:8]] for u in uuids if u[:8] in SERVICES})
        info = f"{prop(dev, 'Address', '')}"
        if services:
            info += "   " + " · ".join(services)
        row.body.append(label(info, "dim", ellipsize=True))
        self.update_profile(row)

    def on_dev_toggle(self, row, open_):
        if open_:
            self.load_cards()

    def pair(self, dev):
        alias = prop(dev, "Alias", "?")
        if self.adapter is not None and not prop(self.adapter, "Pairable"):
            self.set_adapter("Pairable", True)

        def paired(ok):
            if ok:
                self.set_prop(dev, DEV, "Trusted", True)
                self.call(dev, "Connect", ok=f"{alias} verbunden", start=f"verbinde mit {alias} …")
        self.call(dev, "Pair", start=f"kopple {alias} …", ok=f"{alias} gekoppelt", done=paired, timeout=90000)

    def remove(self, row):
        if getattr(row, "confirm", 0) > time.monotonic():
            alias = prop(row.dev, "Alias", "?")
            self.call(self.adapter, "RemoveDevice", GLib.Variant("(o)", (row.dev.get_object_path(),)),
                      ok=f"{alias} entfernt")
        else:
            row.confirm = time.monotonic() + 4
            self.say("nochmal klicken zum entfernen", error=True, seconds=4)

    # ---------- Audio-Profile über PipeWire ----------
    def load_cards(self):
        def get():
            try:
                return json.loads(subprocess.run(["pactl", "-f", "json", "list", "cards"], capture_output=True,
                                                 text=True).stdout or "[]")
            except ValueError:
                return []

        def done(cards):
            if isinstance(cards, list):
                self.cards = {c["name"]: c for c in cards if c["name"].startswith("bluez_card.")}
                for box in (self.devlist, self.found):
                    for row in getattr(box, "rows", {}).values():
                        self.update_profile(row)
        tui.background(get, done=done)

    def card_for(self, row):
        addr = prop(row.dev, "Address", "").replace(":", "_")
        return self.cards.get(f"bluez_card.{addr}")

    def update_profile(self, row):
        card = self.card_for(row) if hasattr(row, "profile") else None
        if not card or not prop(row.dev, "Connected"):
            if hasattr(row, "profile_box"):
                row.profile_box.set_visible(False)
            return
        opts = [(k, v["description"]) for k, v in sorted(card["profiles"].items(),
                                                         key=lambda kv: -kv[1].get("priority", 0))
                if v.get("available", True)]
        row.profile.set_options(opts, card["active_profile"])
        row.profile_box.set_visible(True)

    def set_profile(self, row, p):
        card = self.card_for(row)
        if card:
            subprocess.Popen(["pactl", "set-card-profile", card["name"], p])
            self.say("profil gewechselt")
            GLib.timeout_add(600, lambda: self.load_cards() and False)

    # ---------- Adapter ----------
    def set_power(self, on):
        if self.adapter is None:
            return
        if on:  # per rfkill blockiert? Dann erst freigeben
            subprocess.run(["rfkill", "unblock", "bluetooth"], capture_output=True)
        self.set_prop(self.adapter, ADP, "Powered", on, ok="bluetooth an" if on else "bluetooth aus")

    def set_adapter(self, name, value):
        if self.adapter is not None:
            self.set_prop(self.adapter, ADP, name, value)

    def save_name(self):
        if self.adapter is not None and self.a_name.get_text().strip():
            self.set_prop(self.adapter, ADP, "Alias", self.a_name.get_text().strip(), ok="name gespeichert")

    def fill_adapter(self, a):
        self.adp_panel.set_visible(a is not None)
        if a is None:
            return
        self.adp_panel.set_title(f"󰂯 {esc(a.get_object_path().rsplit('/', 1)[-1])}", markup=True)
        self.a_power.set_active(prop(a, "Powered"))
        self.a_disc.set_active(prop(a, "Discoverable"))
        self.a_pair.set_active(prop(a, "Pairable"))
        t = prop(a, "DiscoverableTimeout", 180)
        opts = [(60, "1 minute"), (180, "3 minuten"), (600, "10 minuten"), (0, "immer")]
        if t not in dict(opts):
            opts.append((t, f"{t} s"))
        self.a_timeout.set_options(opts, t)
        if not self.a_name.has_focus() and self.a_name.get_text() != prop(a, "Alias", ""):
            self.a_name.set_text(prop(a, "Alias", ""))
        rows = [("adresse", prop(a, "Address", "")), ("hersteller", f"0x{prop(a, 'Manufacturer', 0) or 0:04x}"),
                ("klasse", f"0x{prop(a, 'Class', 0) or 0:06x}"),
                ("rollen", " · ".join(prop(a, "Roles", []) or [])), ("status", prop(a, "PowerState", ""))]
        if getattr(self, "_adp_rows", None) != rows:
            self._adp_rows = rows
            tui.clear(self.a_info)
            for r, (k, v) in enumerate(rows):
                self.a_info.attach(label(k, "dim"), 0, r, 1, 1)
                self.a_info.attach(label(str(v)), 1, r, 1, 1)

    # ---------- Suche ----------
    def toggle_scan(self):
        if self.adapter is None:
            return
        self.call(self.adapter, "StopDiscovery" if self.scanning else "StartDiscovery")

    def tab_changed(self, tab):
        if self.adapter is None or not prop(self.adapter, "Powered"):
            return
        if tab == "scan" and not self.scanning:
            self.call(self.adapter, "StartDiscovery")
        elif tab != "scan" and self.scanning:
            self.call(self.adapter, "StopDiscovery")

    def shutdown(self):
        """Prozessende: Agent abmelden."""
        if self.agent_id:
            try:
                self.agent_mgr.call_sync("UnregisterAgent", GLib.Variant("(o)", (AGENT_PATH,)),
                                         Gio.DBusCallFlags.NONE, 1000, None)
            except (GLib.Error, AttributeError):
                pass


if __name__ == "__main__":
    import ricetui
    ricetui.main("bluetooth")
