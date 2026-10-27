#!/usr/bin/env python3
# netz – replacement for nm-connection-editor (right click on wifi in the waybar).
# Tabs: ¹wlan (networks, connect with password right in the row, hidden network)
#       ²verbindungen (saved connections + VPN: on/off, automatic, edit IPv4/DNS,
#                      show password, delete) ³geräte (addresses + live throughput).
# Everything via nmcli; "nmcli monitor" reports changes live.
import os, re, signal, subprocess, sys, threading, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tui
import rice_i18n; rice_i18n.install()
from tui import Gtk, GLib, label, hbox, vbox, esc

TYPE_GLYPHS = {"802-11-wireless": "󰖩", "wifi": "󰖩", "802-3-ethernet": "󰈀", "ethernet": "󰈀", "vpn": "󰦝",
               "wireguard": "󰦝", "bluetooth": "󰂯", "gsm": "󰐻", "bridge": "󰌘", "loopback": "󰑙",
               "tun": "󰦝", "wifi-p2p": "󰖩"}
TYPE_NAMES = {"802-11-wireless": "wlan", "802-3-ethernet": "kabel", "vpn": "vpn", "wireguard": "wireguard",
              "bluetooth": "bluetooth", "gsm": "mobil", "bridge": "bridge", "loopback": "loopback"}


def nmcli(*args, check=False):
    p = subprocess.run(["nmcli", *args], capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip().removeprefix("Error: ").removeprefix("Fehler: "))
    return p.stdout


def split_t(line):
    """Split an nmcli -t line at unescaped ':'."""
    parts = re.split(r"(?<!\\):", line)
    return [p.replace("\\:", ":").replace("\\\\", "\\") for p in parts]


def kv(text):
    out = {}
    for line in text.splitlines():
        k, _, v = line.partition(":")
        out.setdefault(k, v)
    return out


def human(rate):
    for unit in ("B/s", "KiB/s", "MiB/s", "GiB/s"):
        if rate < 1024 or unit == "GiB/s":
            return f"{rate:.0f} {unit}" if unit == "B/s" else f"{rate:.1f} {unit}"
        rate /= 1024


# ---------- Daten ----------
def wifi_snapshot():
    radio = nmcli("radio", "wifi").strip() == "enabled"
    nets = {}
    if radio:
        out = nmcli("-t", "--escape", "yes", "-f", "IN-USE,BSSID,SSID,SIGNAL,SECURITY,CHAN,FREQ,RATE",
                    "dev", "wifi", "list", "--rescan", "no")
        for line in out.splitlines():
            f = split_t(line)
            if len(f) < 8 or not f[2]:
                continue
            inuse, _bssid, ssid, sig, sec, chan, freq, rate = f[:8]
            sig = int(sig or 0)
            n = nets.get(ssid)
            if n is None or sig > n["signal"] or inuse == "*":
                nets[ssid] = {"ssid": ssid, "signal": max(sig, n["signal"] if n else 0),
                              "security": "" if sec in ("", "--") else sec, "chan": chan,
                              "band": "5G" if freq.startswith("5") else "6G" if freq.startswith("6") else "2.4G",
                              "rate": rate, "inuse": inuse == "*" or (n and n["inuse"])}
    return radio, sorted(nets.values(), key=lambda n: (not n["inuse"], -n["signal"]))


def connections():
    cons = []
    for line in nmcli("-t", "-f", "NAME,UUID,TYPE,DEVICE,AUTOCONNECT,ACTIVE", "con", "show").splitlines():
        f = split_t(line)
        if len(f) >= 6 and f[2] != "loopback":
            cons.append({"name": f[0], "uuid": f[1], "type": f[2], "device": f[3],
                         "auto": f[4] == "yes", "active": f[5] == "yes"})
    wifi = [c["uuid"] for c in cons if c["type"] == "802-11-wireless"]
    if wifi:  # SSID per saved wifi connection (name ≠ SSID, e.g. "Netz 1")
        uuid = None
        for line in nmcli("-t", "-f", "connection.uuid,802-11-wireless.ssid", "con", "show", *wifi).splitlines():
            k, _, v = line.partition(":")
            if k == "connection.uuid":
                uuid = v
            elif k == "802-11-wireless.ssid":
                for c in cons:
                    if c["uuid"] == uuid:
                        c["ssid"] = v
    return sorted(cons, key=lambda c: (not c["active"], c["type"] != "802-11-wireless", c["name"].lower()))


def devices():
    devs = []
    for line in nmcli("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev").splitlines():
        f = split_t(line)
        if len(f) >= 4 and f[1] not in ("loopback", "wifi-p2p"):
            info = kv(nmcli("-t", "dev", "show", f[0]))
            devs.append({"name": f[0], "type": f[1], "state": f[2], "con": f[3], "info": info})
    return devs


def snapshot():
    radio, nets = wifi_snapshot()
    return {"radio": radio, "nets": nets, "cons": connections(), "devs": devices()}


def con_details(uuid):
    fields = "ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns,ipv6.method,connection.autoconnect"
    return kv(nmcli("-t", "-f", fields, "con", "show", uuid).replace("\\:", ":"))


# ---------- window ----------
class NetWindow(tui.TuiWindow):
    APP_ID = "de.invincible.Network"

    def __init__(self, app):
        super().__init__(app, "󰖩 netz", [("wifi", "wlan"), ("cons", "verbindungen"), ("devs", "geräte")],
                         size=(780, 640), hints=(("klick", "aufklappen"), ("^r", "neu laden")))
        self.data = None
        self.busy = self.again = False
        self.refresh_id = None
        self.last_bytes = {}
        self.on_refresh = lambda: (self.rescan(), self.refresh())
        self.on_tab = lambda _t: self.refresh()

        # ¹ wlan
        page = vbox(spacing=8)
        page.set_margin_top(6)
        self.radio = tui.Check("wlan", callback=self.set_radio, tooltip="WLAN an/aus")
        self.now = label("", "dim", hexpand=True, ellipsize=True)
        self.scan_btn = tui.Button("⟳ scannen", self.rescan)
        top = tui.Panel("󰖩 status", hbox(self.radio, self.now, self.scan_btn, spacing=12))
        page.append(top)
        self.nets_panel = tui.Panel("netze")
        self.nets = vbox(spacing=0)
        self.nets_empty = label("", "empty", xalign=0.5)
        self.nets_panel.body.append(self.nets)
        self.nets_panel.body.append(self.nets_empty)
        page.append(self.nets_panel)
        page.append(self.hidden_panel())
        self.add_page("wifi", page)

        # ² verbindungen
        page = vbox(spacing=8)
        page.set_margin_top(6)
        p = tui.Panel("gespeichert")
        self.cons = vbox(spacing=0)
        p.body.append(self.cons)
        p.body.append(hbox(label("", hexpand=True),
                           tui.Button("+ neu ↗", lambda: self.spawn("nm-connection-editor", "--create"),
                                      tooltip="Neue Verbindung (VPN, Kabel, …) im NetworkManager-Editor")))
        page.append(p)
        self.add_page("cons", page)

        # ³ geräte
        page = vbox(spacing=8)
        page.set_margin_top(6)
        self.devs = vbox(spacing=8)
        page.append(self.devs)
        self.add_page("devs", page)
        self.show_tab("wifi")

        self.timer = None
        self.ticks = 0
        self.refresh()
        threading.Thread(target=self.listen, daemon=True).start()

    def on_show(self):
        self.rescan(quiet=True)
        self.refresh()
        if self.timer is None:
            self.timer = GLib.timeout_add(1000, self.tick)

    def on_hide(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        self.last_bytes = {}

    # ---------- general ----------
    def spawn(self, *cmd):
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def act(self, start, ok, *args, after=None):
        """Run an nmcli command in the background, message in the status line."""
        if start:
            self.say(start, seconds=60)

        def done(res):
            if isinstance(res, Exception):
                self.say(str(res), error=True, seconds=10)
            else:
                self.say(ok)
                if after:
                    after()
            self.schedule()
        tui.background(lambda: nmcli(*args, check=True), done=done)

    def listen(self):
        while True:
            p = tui.spawn_watch(["nmcli", "monitor"], stdout=subprocess.PIPE, text=True)
            for _ in p.stdout:
                GLib.idle_add(self.schedule)
            p.wait()
            time.sleep(2)

    def schedule(self):
        if not self.get_visible():
            return False
        if self.refresh_id is None:
            self.refresh_id = GLib.timeout_add(250, self.refresh)
        return False

    def refresh(self):
        self.refresh_id = None
        if self.busy:
            self.again = True
            return False
        self.busy = True
        tui.background(snapshot, done=self.apply)
        return False

    def rescan(self, quiet=False):
        if not quiet:
            self.say("suche netze …", seconds=4)
        tui.background(lambda: nmcli("dev", "wifi", "rescan"),
                       done=lambda _r: GLib.timeout_add(2500, lambda: self.refresh() and False))

    def tick(self):
        self.ticks += 1
        if not self.get_visible():
            return True
        self.update_traffic()  # also in the background so the history is already there when switching
        if self.current_tab() == "wifi" and self.ticks % 6 == 0:
            self.refresh()
        return True

    def apply(self, data):
        self.busy = False
        if isinstance(data, Exception):
            self.say(f"nmcli: {data}", error=True)
            return
        self.data = data
        self.fill_wifi()
        self.fill_cons()
        self.fill_devs()
        if self.again:
            self.again = False
            self.refresh()

    # ---------- wlan ----------
    def set_radio(self, on):
        self.act(None, "wlan an" if on else "wlan aus", "radio", "wifi", "on" if on else "off",
                 after=(lambda: self.rescan(quiet=True)) if on else None)

    def saved_for(self, ssid):
        return next((c for c in self.data["cons"] if c.get("ssid") == ssid), None)

    def fill_wifi(self):
        d = self.data
        self.radio.set_active(d["radio"])
        self.scan_btn.set_sensitive(d["radio"])
        wdev = next((x for x in d["devs"] if x["type"] == "wifi"), None)
        cur = next((n for n in d["nets"] if n["inuse"]), None)
        if not d["radio"]:
            self.now.set_label("ausgeschaltet")
        elif cur and wdev:
            ip = wdev["info"].get("IP4.ADDRESS[1]", "").split("/")[0]
            self.now.set_label(f"● {cur['ssid']}   {ip}")
        else:
            self.now.set_label("○ nicht verbunden")
        self.nets_panel.set_title(f"netze <span alpha='60%'>{len(d['nets'])}</span>", markup=True)
        self.nets_empty.set_visible(not d["nets"])
        self.nets_empty.set_label("wlan ist aus" if not d["radio"] else "keine netze gefunden – ⟳ scannen")
        tui.sync_rows(self.nets, d["nets"], lambda n: n["ssid"], self.make_net, self.update_net)

    def make_net(self, n):
        row = tui.Row(on_toggle=self.on_net_toggle)
        row.bars = label("", "accent", markup=True)
        row.ssid = label("", hexpand=True, ellipsize=True)
        row.lock = label("", "dim")
        row.meta = label("", "dim")
        row.mark = label("", "accent")
        row.set_head(hbox(row.bars, row.ssid, row.mark, row.lock, row.meta, spacing=10))
        row.key = None
        return row

    def update_net(self, row, n):
        saved = self.saved_for(n["ssid"])
        row.bars.set_markup(tui.bars(n["signal"]))
        row.ssid.set_label(n["ssid"])
        row.lock.set_label("󰌾" if n["security"] else "󰌿")
        row.lock.set_tooltip_text(n["security"] or "offen")
        row.meta.set_label(f"{n['band']:>4} ch{n['chan']:<3} {n['signal']:>3}%")
        row.mark.set_label("● verbunden" if n["inuse"] else "★ gespeichert" if saved else "")
        row.net = n
        key = (n["inuse"], saved["uuid"] if saved else None, bool(n["security"]))
        if key != row.key:  # only rebuild actions when the state changes
            row.key = key
            self.build_net_body(row, n, saved)

    def build_net_body(self, row, n, saved):
        tui.clear(row.body)
        ssid = n["ssid"]
        btns = hbox(spacing=8)
        if n["inuse"]:
            wdev = next((x["name"] for x in self.data["devs"] if x["type"] == "wifi"), None)
            btns.append(tui.Button("trennen", lambda: self.act(f"trenne {ssid} …", f"getrennt von {ssid}",
                                                                "dev", "disconnect", wdev)))
        elif saved:
            btns.append(tui.Button("verbinden", lambda: self.act(f"verbinde mit {ssid} …", f"verbunden mit {ssid}",
                                                                  "con", "up", "uuid", saved["uuid"])))
        elif n["security"]:
            pw = tui.Entry("passwort", password=True)
            go = lambda: pw.get_text() and self.act(f"verbinde mit {ssid} …", f"verbunden mit {ssid}",
                                                    "dev", "wifi", "connect", ssid, "password", pw.get_text())
            pw.connect("activate", lambda *_: go())
            show = tui.Check("zeigen", callback=lambda on: pw.set_visibility(on))
            row.body.append(hbox(pw, show, spacing=8))
            btns.append(tui.Button("verbinden", go))
            row.focus_entry = pw
        else:
            btns.append(tui.Button("verbinden", lambda: self.act(f"verbinde mit {ssid} …", f"verbunden mit {ssid}",
                                                                  "dev", "wifi", "connect", ssid)))
        if saved:
            btns.append(tui.Button("passwort zeigen", lambda: self.show_psk(saved["uuid"], row)))
            btns.append(tui.Button("einstellungen", lambda: self.open_con(saved["uuid"])))
            btns.append(tui.Button("vergessen", lambda: self.forget(saved, row), danger=True))
        row.psk = label("", "accent")
        row.psk.set_selectable(True)
        btns.append(row.psk)
        row.body.append(btns)
        row.body.append(label(f"{n['security'] or 'offen'} · {n['rate']}", "dim"))

    def on_net_toggle(self, row, open_):
        if open_:
            for other in self.nets.rows.values():
                if other is not row and other.is_open:
                    other.toggle(False)
            e = getattr(row, "focus_entry", None)
            if e and not row.net["inuse"]:
                e.grab_focus()

    def show_psk(self, uuid, row):
        def done(res):
            row.psk.set_label(f"󰌾 {res.strip()}" if isinstance(res, str) and res.strip() else "kein passwort")
        tui.background(lambda: nmcli("-s", "-g", "802-11-wireless-security.psk", "con", "show", uuid), done=done)

    def forget(self, con, row):
        if getattr(row, "confirm", 0) > time.monotonic():
            self.act(None, f"{con['name']} vergessen", "con", "delete", "uuid", con["uuid"])
        else:
            row.confirm = time.monotonic() + 4
            self.say(f"nochmal klicken, um {con['name']} wirklich zu löschen", error=True, seconds=4)

    def hidden_panel(self):
        row = tui.Row()
        row.set_head(hbox(label("+", "accent"), label("verstecktes netz …"), spacing=10))
        ssid = tui.Entry("ssid", width=20)
        pw = tui.Entry("passwort (leer = offen)", password=True)

        def go():
            if not ssid.get_text():
                return
            args = ["dev", "wifi", "connect", ssid.get_text(), "hidden", "yes"]
            if pw.get_text():
                args += ["password", pw.get_text()]
            self.act(f"verbinde mit {ssid.get_text()} …", f"verbunden mit {ssid.get_text()}", *args)
        pw.connect("activate", lambda *_: go())
        row.body.append(hbox(ssid, pw, tui.Button("verbinden", go), spacing=8))
        box = vbox(row)
        return box

    # ---------- verbindungen ----------
    def open_con(self, uuid):
        self.show_tab("cons")
        row = getattr(self.cons, "rows", {}).get(uuid)
        if row:
            row.toggle(True)

    def fill_cons(self):
        tui.sync_rows(self.cons, self.data["cons"], lambda c: c["uuid"], self.make_con, self.update_con)

    def make_con(self, c):
        row = tui.Row(on_toggle=self.on_con_toggle)
        row.glyph = label("", "glyph")
        row.name = label("", hexpand=True, ellipsize=True)
        row.kind = label("", "dim")
        row.state = label("", "accent")
        row.set_head(hbox(row.glyph, row.name, row.state, row.kind, spacing=10))
        row.loaded = False

        uuid = c["uuid"]
        row.toggle_btn = tui.Button("", lambda: self.act(
            None, "getrennt" if row.con["active"] else f"{row.con['name']} aktiv",
            "con", "down" if row.con["active"] else "up", "uuid", uuid))
        row.auto = tui.Check("automatisch verbinden", callback=lambda on: self.act(
            None, "gespeichert", "con", "modify", "uuid", uuid, "connection.autoconnect", "yes" if on else "no"))
        row.body.append(hbox(row.toggle_btn, row.auto, label("", hexpand=True),
                             tui.Button("erweitert ↗", lambda: self.spawn("nm-connection-editor", f"--edit={uuid}"),
                                        tooltip="Alle Einstellungen im NetworkManager-Editor"),
                             tui.Button("löschen", lambda: self.forget(row.con, row), danger=True)))
        # IPv4-Editor
        row.method = tui.Select(lambda m: self.ip_method(row, m), tooltip="IPv4")
        row.addr = tui.Entry("192.168.1.50/24")
        row.gw = tui.Entry("gateway")
        row.dns = tui.Entry("dns, z. b. 1.1.1.1 9.9.9.9")
        grid = Gtk.Grid(column_spacing=10, row_spacing=6)
        for i, (name, w) in enumerate((("ipv4", row.method), ("adresse", row.addr), ("gateway", row.gw),
                                       ("dns", row.dns))):
            grid.attach(label(name, "dim"), 0, i, 1, 1)
            grid.attach(w, 1, i, 1, 1)
        row.method.set_halign(Gtk.Align.START)
        row.ipbox = vbox(grid, hbox(tui.Button("speichern + neu verbinden", lambda: self.save_ip(row)),
                                    row_psk := label("", "accent")), spacing=8)
        row.psk = row_psk
        row.psk_btn = tui.Button("passwort zeigen", lambda: self.show_psk(uuid, row))
        row.ipbox.get_last_child().append(row.psk_btn)
        row.body.append(row.ipbox)
        return row

    def update_con(self, row, c):
        row.con = c
        row.glyph.set_label(TYPE_GLYPHS.get(c["type"], "󰛳"))
        row.name.set_label(c["name"])
        row.kind.set_label(TYPE_NAMES.get(c["type"], c["type"]))
        row.state.set_label(f"● {c['device']}" if c["active"] else "")
        row.toggle_btn.set_label("trennen" if c["active"] else "verbinden")
        row.auto.set_active(c["auto"])
        row.ipbox.set_visible(c["type"] in ("802-11-wireless", "802-3-ethernet"))
        row.psk_btn.set_visible(c["type"] == "802-11-wireless")

    def on_con_toggle(self, row, open_):
        if open_ and row.ipbox.get_visible():
            def done(d):
                if isinstance(d, Exception):
                    return
                m = d.get("ipv4.method", "auto")
                row.method.set_options([("auto", "automatisch (dhcp)"), ("manual", "manuell"),
                                        ("shared", "mit anderen teilen"), ("disabled", "aus")], m)
                row.addr.set_text(d.get("ipv4.addresses", ""))
                row.gw.set_text(d.get("ipv4.gateway", ""))
                row.dns.set_text(d.get("ipv4.dns", "").replace(",", " "))
                self.ip_method(row, m, apply=False)
            tui.background(con_details, row.con["uuid"], done=done)

    def ip_method(self, row, m, apply=False):
        row.method.set_options(row.method.options or [], m)
        row.addr.set_sensitive(m == "manual")
        row.gw.set_sensitive(m == "manual")

    def save_ip(self, row):
        m = row.method.current or "auto"
        args = ["con", "modify", "uuid", row.con["uuid"], "ipv4.method", m,
                "ipv4.dns", " ".join(row.dns.get_text().replace(",", " ").split())]
        if m == "manual":
            if not row.addr.get_text():
                self.say("manuell braucht eine adresse, z. b. 192.168.1.50/24", error=True)
                return
            args += ["ipv4.addresses", row.addr.get_text(), "ipv4.gateway", row.gw.get_text()]
        else:
            args += ["ipv4.addresses", "", "ipv4.gateway", ""]
        uuid, active = row.con["uuid"], row.con["active"]
        self.act("speichere …", "gespeichert", *args,
                 after=(lambda: self.act(None, "neu verbunden", "con", "up", "uuid", uuid)) if active else None)

    # ---------- geräte ----------
    def fill_devs(self):
        tui.sync_rows(self.devs, self.data["devs"], lambda d: d["name"], self.make_dev, self.update_dev)

    def make_dev(self, d):
        p = tui.Panel()
        p.grid = Gtk.Grid(column_spacing=14, row_spacing=3)
        p.body.append(p.grid)
        p.down = tui.Spark(32)
        p.up = tui.Spark(32)
        p.down_l = label("", "mono-pct")
        p.up_l = label("", "mono-pct")
        p.down_l.set_width_chars(11)
        p.up_l.set_width_chars(11)
        p.traffic = vbox(hbox(label("↓", "accent"), p.down_l, p.down), hbox(label("↑", "accent"), p.up_l, p.up),
                         spacing=0)
        p.btn = tui.Button("", lambda: self.act(None, "erledigt", "dev",
                                                "disconnect" if p.dev["state"].startswith("connected") else "connect",
                                                p.dev["name"]))
        p.body.append(hbox(p.traffic, label("", hexpand=True), p.btn))
        p.shown = None
        return p

    def update_dev(self, p, d):
        p.dev = d
        i = d["info"]
        connected = d["state"].startswith("connected")
        p.set_title(f"{TYPE_GLYPHS.get(d['type'], '󰛳')} {esc(d['name'])} "
                    f"<span alpha='60%'>{esc(d['type'])}</span>", markup=True)
        p.set_active(connected)
        p.btn.set_label("trennen" if connected else "verbinden")
        p.btn.set_visible(d["type"] in ("wifi", "ethernet"))
        rows = [("status", d["state"].replace("connected", "verbunden").replace("disconnected", "getrennt")
                 .replace("unavailable", "nicht verfügbar").replace("unmanaged", "nicht verwaltet")),
                ("verbindung", d["con"] or "–"), ("mac", i.get("GENERAL.HWADDR", "–"))]
        ip4 = [v for k, v in sorted(i.items()) if k.startswith("IP4.ADDRESS")]
        ip6 = [v for k, v in sorted(i.items()) if k.startswith("IP6.ADDRESS") and not v.startswith("fe80")]
        dns = [v for k, v in sorted(i.items()) if k.startswith("IP4.DNS") or k.startswith("IP6.DNS")]
        if ip4:
            rows.append(("ipv4", "  ".join(ip4)))
        if i.get("IP4.GATEWAY"):
            rows.append(("gateway", i["IP4.GATEWAY"]))
        if ip6:
            rows.append(("ipv6", ip6[0]))
        if dns:
            rows.append(("dns", "  ".join(dns[:3])))
        if rows != p.shown:
            p.shown = rows
            tui.clear(p.grid)
            for r, (k, v) in enumerate(rows):
                p.grid.attach(label(k, "dim"), 0, r, 1, 1)
                v_l = label(v, ellipsize=True, hexpand=True)
                v_l.set_selectable(True)
                p.grid.attach(v_l, 1, r, 1, 1)
        p.traffic.set_visible(connected)

    def update_traffic(self):
        now = time.monotonic()
        for name, p in getattr(self.devs, "rows", {}).items():
            try:
                rx = int(open(f"/sys/class/net/{name}/statistics/rx_bytes").read())
                tx = int(open(f"/sys/class/net/{name}/statistics/tx_bytes").read())
            except (OSError, ValueError):
                continue
            last = self.last_bytes.get(name)
            self.last_bytes[name] = (now, rx, tx)
            if last:
                dt = max(now - last[0], 0.1)
                drx, dtx = (rx - last[1]) / dt, (tx - last[2]) / dt
                p.down.push(drx)
                p.up.push(dtx)
                p.down_l.set_label(human(drx))
                p.up_l.set_label(human(dtx))


if __name__ == "__main__":
    import ricetui
    ricetui.main("netz")
