#!/usr/bin/env python3
"""Eigene rofi-Modi für den Starter (Super+R) im -ist-Look.

    ist.py fenster   offene Fenster (Hyprland) – Enter springt hin
    ist.py rechner   qalc: Ausdruck tippen + Enter rechnet (Einheiten, Prozent, Währungen); Enter auf Ergebnis kopiert
    ist.py ablage    Zwischenablage-Verlauf (cliphist) – Enter kopiert erneut
    ist.py zeichen   Emoji und Sonderzeichen (englische Unicode-Namen + deutsche Stichwörter) – Enter kopiert
    ist.py web       Websuche: Text + Enter (Kürzel: g, yt, w, gh, aw, maps, dict), Adressen öffnen direkt
    ist.py system    Sperren, Bereitschaft, Neustart, Ausschalten, WLAN/Bluetooth/Nicht stören, Wallpaper, …

rofi-Skriptmodus: ohne Auswahl wird die Liste ausgegeben; nach einer Auswahl ruft rofi das Skript erneut auf
(ROFI_RETV 1 = Zeile, 2 = eigene Eingabe, ROFI_INFO = verstecktes Feld der Zeile). Keine Ausgabe = rofi schließt.
"""
import json
import os
import subprocess
import sys
import unicodedata

sys.path.insert(0, os.path.expanduser("~/.local/share/rice-apps"))
try:
    from rice_i18n import tr          # German source texts; English on non-German systems
except ImportError:
    tr = lambda s: s

MODE = sys.argv[1] if len(sys.argv) > 1 else ""
ARG = sys.argv[2] if len(sys.argv) > 2 else ""
RETV = int(os.environ.get("ROFI_RETV", "0"))
INFO = os.environ.get("ROFI_INFO", "")
RUN = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
HOME = os.path.expanduser("~")


def opt(key, value):
    sys.stdout.write(f"\0{key}\x1f{tr(value) if key == 'message' else value}\n")


def row(text, info="", icon="", meta="", nonselectable=False):
    text = tr(text)
    meta = f"{meta} {tr(meta)}" if meta and tr(meta) != meta else meta     # search keywords in both languages
    parts = [text]
    extra = []
    if icon:
        extra.append(f"icon\x1f{icon}")
    if info:
        extra.append(f"info\x1f{info}")
    if meta:
        extra.append(f"meta\x1f{meta}")
    if nonselectable:
        extra.append("nonselectable\x1ftrue")
    if extra:
        parts.append("\0" + "\x1f".join(extra))
    sys.stdout.write("".join(parts) + "\n")


def dim(t):
    return f"<span alpha='55%'>{esc(tr(t))}</span>"


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def detach(*cmd, stdin=None):
    """Programm unabhängig von rofi starten (rofi wartet sonst auf die Ausgabe)."""
    p = subprocess.Popen(list(cmd), stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    if stdin is not None:
        p.stdin.write(stdin if isinstance(stdin, bytes) else stdin.encode())
        p.stdin.close()


def copy(text, what=None):
    detach("wl-copy", stdin=text)
    detach("notify-send", "-a", "starter", "-t", "1500", f"{what or esc(text[:60])} {tr('kopiert')}")


def sh(*cmd, timeout=3):
    try:
        return subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


# ---------------------------------------------------------------- fenster
def fenster():
    if RETV == 1 and INFO:
        sh("hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{INFO}" }})')
        return
    opt("markup-rows", "true")
    opt("no-custom", "true")
    try:
        clients = json.loads(sh("hyprctl", "clients", "-j") or "[]")
        active = json.loads(sh("hyprctl", "activewindow", "-j") or "{}").get("address")
    except ValueError:
        clients, active = [], None
    clients = [c for c in clients if c.get("mapped") and not c.get("hidden") and c.get("title") is not None]
    clients.sort(key=lambda c: (c.get("focusHistoryID", 99)))
    for c in clients:
        if c.get("address") == active:
            continue          # das Fenster, aus dem man kommt, steht nicht zur Wahl
        cls = c.get("class") or c.get("initialClass") or "?"
        ws = c.get("workspace", {}).get("name", "?")
        ws = "spezial" if str(ws).startswith("special") else ws
        icon = icon_for(cls)
        title = c.get("title") or cls
        row(f"{esc(title[:70])}  {dim(f'{short_class(cls)} · arbeitsfläche {ws}')}", info=c["address"], icon=icon,
            meta=f"{cls} {ws}")
    if not clients:
        opt("message", "keine weiteren fenster offen")


def short_class(cls):
    return cls.split(".")[-1].lower()


def icon_for(cls):
    """Icon-Name aus der .desktop-Datei der Fensterklasse (StartupWMClass oder Dateiname)."""
    cache = os.path.join(RUN, "rofi-ist-icons.json")
    try:
        icons = json.load(open(cache))
    except (OSError, ValueError):
        icons = {}
        dirs = [os.path.join(HOME, ".local/share/applications"), "/usr/share/applications"]
        for d in dirs:
            try:
                names = os.listdir(d)
            except OSError:
                continue
            for n in names:
                if not n.endswith(".desktop"):
                    continue
                try:
                    txt = open(os.path.join(d, n), errors="ignore").read()
                except OSError:
                    continue
                kv = {}
                for line in txt.split("[Desktop Action")[0].splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        kv.setdefault(k.strip(), v.strip())
                ic = kv.get("Icon")
                if not ic:
                    continue
                for key in (kv.get("StartupWMClass"), n[:-8]):
                    if key:
                        icons.setdefault(key.lower(), ic)
        try:
            json.dump(icons, open(cache, "w"))
        except OSError:
            pass
    c = cls.lower()
    return icons.get(c) or icons.get(c.split(".")[-1]) or c


# ---------------------------------------------------------------- rechner
HIST = os.path.join(RUN, "rofi-rechner.json")


def rechner():
    try:
        hist = json.load(open(HIST))
    except (OSError, ValueError):
        hist = []
    if RETV == 1 and INFO:
        copy(INFO, f"Ergebnis {esc(INFO)}")
        return
    opt("markup-rows", "true")
    if RETV == 2 and ARG.strip():
        expr = ARG.strip()
        import re
        q = re.sub(r"%\s*(von|of)\s+", "% * ", expr)               # 12% von 80
        q = re.sub(r"\s(in|nach|zu)\s(?=[^\d\s])", " to ", q)    # 5 km in mi (nicht: „in“ = Zoll)
        q = re.sub(r"\bto\s+(?!-|\+|dec\b|hex\b|bin\b|oct\b|base|roman|time\b|frac|mixed|sci|utc|cet)([A-Za-z€$£]\w*)",
                   r"to -\1", q)                                     # „3,1 mi“ statt „3 mi + 188 yd + …“
        q = re.sub(r"\bmal\b", "*", q)
        q = re.sub(r"\bgeteilt durch\b", "/", q)
        res = sh("qalc", "-t", "-set", "decimal comma on", q, timeout=8).strip().splitlines()
        res = res[-1].strip() if res else "?"
        hist = [[expr, res]] + [h for h in hist if h[0] != expr][:14]
        try:
            json.dump(hist, open(HIST, "w"))
        except OSError:
            pass
        opt("message", f"<b>{esc(expr)}</b>  =  <b>{esc(res)}</b>   " + dim("enter kopiert das ergebnis"))
    else:
        opt("message", tr("ausdruck tippen + enter: ") + dim("12% von 80 · 5 km in mi · sqrt(2) · 100 eur in usd · "
                                                        "3h 20min in s · 0x1f in dec"))
    for expr, res in hist:
        row(f"<b>{esc(res)}</b>  {dim('= ' + expr)}", info=res, meta=expr)


# ---------------------------------------------------------------- ablage
def ablage():
    if RETV == 1 and INFO == "__wipe__":
        sh("cliphist", "wipe")
        detach("notify-send", "-a", "starter", "-t", "1500", "Verlauf geleert")
        return
    if RETV == 1 and INFO:
        data = subprocess.run(["cliphist", "decode"], input=INFO.encode() + b"\n", capture_output=True).stdout
        detach("wl-copy", stdin=data)
        detach("notify-send", "-a", "starter", "-t", "1500", "Wieder in der Zwischenablage")
        return
    opt("markup-rows", "true")
    opt("no-custom", "true")
    lines = sh("cliphist", "list", timeout=4).splitlines()
    if not lines:
        running = sh("pgrep", "-f", "cliphist store").strip()
        opt("message", tr("verlauf ist leer") + ("" if running else dim(" – der verlauf startet mit der nächsten anmeldung")))
        return
    for line in lines[:300]:
        cid, _, prev = line.partition("\t")
        if prev.startswith("[[ binary data"):
            label = "󰋩  " + dim("bild " + prev.strip("[] ").replace("binary data", "").strip())
        else:
            p = " ".join(prev.split())
            label = esc(p[:110]) + ("…" if len(p) > 110 else "")
        row(label, info=line, meta=prev[:200])
    row("󰆴  " + dim("verlauf leeren"), info="__wipe__", meta="leeren löschen wipe clear")


# ---------------------------------------------------------------- zeichen
DE = {  # deutsche Stichwörter zusätzlich zu den englischen Namen
    "😀": "lachen grinsen", "😂": "tränen lachen", "😊": "lächeln", "😍": "verliebt herzaugen", "🤔": "nachdenken",
    "😢": "weinen traurig", "😭": "heulen", "😡": "wütend", "😴": "schlafen müde", "🙏": "bitte danke beten",
    "👍": "daumen hoch gut", "👎": "daumen runter schlecht", "👏": "klatschen applaus", "🙌": "hurra", "💪": "stark muskel",
    "❤": "herz liebe", "🔥": "feuer heiß", "✨": "funkeln glitzer", "🎉": "party feier", "✅": "haken erledigt ok",
    "❌": "kreuz falsch nein", "⚠": "warnung achtung", "💡": "idee glühbirne", "📌": "pin anheften", "📎": "büroklammer",
    "🚀": "rakete start", "⭐": "stern", "☕": "kaffee", "🍕": "pizza", "🍺": "bier", "🎂": "geburtstag kuchen",
    "📅": "kalender datum", "⏰": "wecker", "📧": "email mail", "📞": "telefon", "🏠": "haus zuhause", "🚗": "auto",
    "🎵": "musik note", "📷": "kamera foto", "💻": "laptop computer", "📱": "handy", "🔒": "schloss gesperrt",
    "🔑": "schlüssel", "💀": "totenkopf schädel", "👀": "augen gucken", "🤷": "schulterzucken egal", "😅": "puh schwitzen",
    "🥲": "lächeln träne", "🫠": "schmelzen", "🤝": "handschlag deal", "👋": "winken hallo tschüss", "🐱": "katze",
    "🐶": "hund", "🌙": "mond nacht", "☀": "sonne", "🌧": "regen", "❄": "schnee kalt", "⚡": "blitz strom",
}
SYMBOLS = [
    ("→", "pfeil rechts arrow"), ("←", "pfeil links"), ("↑", "pfeil hoch"), ("↓", "pfeil runter"), ("↔", "pfeil beide"),
    ("⇒", "folgt daraus implies"), ("⇔", "äquivalent"), ("✓", "haken check"), ("✗", "kreuz"), ("•", "punkt bullet"),
    ("…", "auslassung ellipsis"), ("–", "halbgeviertstrich en dash"), ("—", "geviertstrich em dash"),
    ("„", "anführung unten"), ("“", "anführung oben"), ("‚", "einfach unten"), ("‘", "einfach oben"),
    ("»", "guillemet"), ("«", "guillemet"), ("°", "grad degree"), ("€", "euro"), ("£", "pfund"), ("$", "dollar"),
    ("¥", "yen"), ("±", "plusminus"), ("×", "mal times"), ("÷", "geteilt divide"), ("·", "malpunkt"),
    ("≈", "ungefähr approx"), ("≠", "ungleich"), ("≤", "kleiner gleich"), ("≥", "größer gleich"), ("∞", "unendlich"),
    ("√", "wurzel"), ("∑", "summe sigma"), ("∏", "produkt"), ("∫", "integral"), ("∂", "partiell"), ("∆", "delta"),
    ("∇", "nabla"), ("∈", "element"), ("∉", "nicht element"), ("⊂", "teilmenge"), ("∪", "vereinigung"),
    ("∩", "schnitt"), ("∀", "für alle"), ("∃", "existiert"), ("¬", "nicht"), ("∧", "und"), ("∨", "oder"),
    ("α", "alpha"), ("β", "beta"), ("γ", "gamma"), ("δ", "delta klein"), ("ε", "epsilon"), ("λ", "lambda"),
    ("μ", "my mikro"), ("π", "pi"), ("ρ", "rho"), ("σ", "sigma klein"), ("τ", "tau"), ("φ", "phi"), ("ω", "omega klein"),
    ("Ω", "omega ohm"), ("²", "hoch zwei quadrat"), ("³", "hoch drei"), ("½", "halb"), ("¼", "viertel"),
    ("¾", "dreiviertel"), ("‰", "promille"), ("§", "paragraph"), ("©", "copyright"), ("®", "registered"),
    ("™", "trademark"), ("†", "kreuz gestorben"), ("ß", "eszett"), ("ẞ", "großes eszett"), ("⌘", "command"),
    ("⌥", "option alt"), ("⇧", "umschalt shift"), ("⏎", "enter"), ("⌫", "rücktaste backspace"), ("␣", "leerzeichen"),
]


def zeichen():
    if RETV == 1 and INFO:
        copy(INFO, f"{INFO}")
        return
    opt("no-custom", "true")
    cache = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(HOME, ".cache")), "rofi-zeichen.tsv")
    if not os.path.exists(cache):
        out = []
        for ch, kw in SYMBOLS:
            out.append(f"{ch}\t{unicodedata.name(ch, '').lower()}\t{kw}")
        ranges = [(0x1F600, 0x1F64F), (0x1F910, 0x1F9FF), (0x1F300, 0x1F5FF), (0x1F680, 0x1F6FF),
                  (0x1FA70, 0x1FAFF), (0x2600, 0x27BF)]
        for a, b in ranges:
            for cp in range(a, b + 1):
                ch = chr(cp)
                name = unicodedata.name(ch, "")
                if not name or unicodedata.category(ch) not in ("So", "Sm"):
                    continue
                out.append(f"{ch}\t{name.lower()}\t{DE.get(ch, '')}")
        try:
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            open(cache, "w").write("\n".join(out))
        except OSError:
            pass
        lines = out
    else:
        lines = open(cache).read().splitlines()
    for line in lines:
        ch, name, kw = (line.split("\t") + ["", ""])[:3]
        row(f"{ch}   {name}", info=ch, meta=kw)


# ---------------------------------------------------------------- web
ENGINES = {
    "": ("DuckDuckGo", "https://duckduckgo.com/?q={}"),
    "g": ("Google", "https://www.google.com/search?q={}"),
    "yt": ("YouTube", "https://www.youtube.com/results?search_query={}"),
    "w": ("Wikipedia", "https://de.wikipedia.org/w/index.php?search={}"),
    "gh": ("GitHub", "https://github.com/search?q={}&type=repositories"),
    "aw": ("Arch Wiki", "https://wiki.archlinux.org/index.php?search={}"),
    "aur": ("AUR", "https://aur.archlinux.org/packages?K={}"),
    "maps": ("Google Maps", "https://www.google.com/maps/search/{}"),
    "dict": ("dict.cc", "https://www.dict.cc/?s={}"),
}


def web():
    from urllib.parse import quote_plus
    if RETV == 2 and ARG.strip():
        q = ARG.strip()
        if q.startswith(("http://", "https://")) or ("." in q and " " not in q and "/" not in q[:1]
                                                      and len(q.split(".")[-1]) in (2, 3, 4)):
            url = q if "://" in q else "https://" + q
        else:
            key, _, rest = q.partition(" ")
            if key in ENGINES and key and rest:
                url = ENGINES[key][1].format(quote_plus(rest))
            else:
                url = ENGINES[""][1].format(quote_plus(q))
        detach("xdg-open", url)
        return
    if RETV == 1 and INFO:
        return
    opt("markup-rows", "true")
    opt("message", "suchbegriff + enter sucht mit duckduckgo · kürzel davor wählt die seite · adressen öffnen direkt")
    for key, (name, _u) in ENGINES.items():
        if key:
            row(f"<b>{key}</b> …  {dim(name)}", meta=name, nonselectable=True)


# ---------------------------------------------------------------- system
def state(cmd, on_words):
    out = sh(*cmd).lower()
    return any(w in out for w in on_words)


def system():
    act = INFO
    actions = {
        "lock": [os.path.expanduser("~/.config/hypr/lock.sh")],
        "suspend": ["systemctl", "suspend"],
        "logout": ["hyprctl", "dispatch", "hl.dsp.exit()"],
        "reboot": ["systemctl", "reboot"],
        "poweroff": ["systemctl", "poweroff"],
        "wifi": ["bash", "-c", "[ \"$(nmcli radio wifi)\" = enabled ] && nmcli radio wifi off || nmcli radio wifi on"],
        "bt": ["bash", "-c", "bluetoothctl show | grep -q 'Powered: yes' && bluetoothctl power off || bluetoothctl power on"],
        "dnd": ["swaync-client", "-d", "-sw"],
        "wall": [os.path.join(HOME, ".config/hypr/random_wall.sh")],
        "waybar": [os.path.join(HOME, ".config/waybar/scripts/style-switch.sh")],
        "shot": ["hyprshot", "-m", "region"],
        "shotwin": ["hyprshot", "-m", "window"],
        "pick": ["hyprpicker", "-a", "-n"],
        "night": ["bash", "-c", "pkill -x hyprsunset || hyprsunset -t 4500"],
    }
    confirm = {"reboot": "neu starten", "poweroff": "ausschalten", "logout": "abmelden"}
    if RETV == 1 and act:
        if act in confirm:                     # erst nachfragen
            opt("markup-rows", "true")
            opt("no-custom", "true")
            opt("message", tr("wirklich <b>{}</b>? offene programme werden beendet.").replace("{}", tr(confirm[act])))
            row(f"󰄬  {tr('ja')}, {tr(confirm[act])}", info="yes:" + act)
            row("󰜺  abbrechen", info="back")
            return
        if act == "back":
            act = ""
        elif act.startswith("yes:"):
            detach(*actions[act[4:]])
            return
        elif act in actions:
            detach(*actions[act])
            return
    opt("markup-rows", "true")
    opt("no-custom", "true")
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(3) as ex:      # die drei Abfragen gleichzeitig (bluetoothctl allein ~40 ms)
        f_wifi = ex.submit(state, ["nmcli", "radio", "wifi"], ["enabled"])
        f_bt = ex.submit(state, ["bluetoothctl", "show"], ["powered: yes"])
        f_dnd = ex.submit(lambda: sh("swaync-client", "-D").strip() == "true")
        f_sun = ex.submit(lambda: bool(sh("which", "hyprsunset").strip()))
    wifi, bt, dnd, has_sun = f_wifi.result(), f_bt.result(), f_dnd.result(), f_sun.result()
    on = lambda b: f"<b>{tr('an')}</b>" if b else dim("aus")
    rows = [
        ("󰌾", "sperren", dim("super+l"), "lock", "lock sperren bildschirm"),
        ("󰤄", "bereitschaft", dim("suspend"), "suspend", "schlafen suspend standby"),
        ("󰍃", "abmelden", dim("hyprland beenden"), "logout", "logout abmelden"),
        ("󰜉", "neu starten", "", "reboot", "reboot restart neustart"),
        ("󰐥", "ausschalten", "", "poweroff", "shutdown poweroff herunterfahren aus"),
        ("󰖩", "wlan", on(wifi), "wifi", "wifi wlan netz"),
        ("󰂯", "bluetooth", on(bt), "bt", "bluetooth bt"),
        ("󰂛", "nicht stören", on(dnd), "dnd", "dnd nicht stören benachrichtigungen"),
        ("󰸉", "neues wallpaper", dim("super+w · farben passen sich an"), "wall", "wallpaper hintergrund farben"),
        ("󰕮", "waybar-look wechseln", dim("kopfzeile → reiter → klassisch"), "waybar", "waybar leiste look"),
        ("󰹑", "screenshot bereich", dim("super+print"), "shot", "screenshot bildschirmfoto"),
        ("󰖯", "screenshot fenster", dim("super+shift+print"), "shotwin", "screenshot fenster"),
        ("󰈊", "farbe vom bildschirm", dim("pipette · hex wird kopiert"), "pick", "farbe pipette color picker"),
        ("󰖔", "nachtlicht", dim("warmes licht an/aus"), "night", "nachtlicht night blaulicht"),
    ]
    if not has_sun:
        rows = [r for r in rows if r[3] != "night"]
    for icon, name, extra, key, meta in rows:
        row(f"{icon}  {tr(name)}  {extra}", info=key, meta=meta)


if __name__ == "__main__":
    {"fenster": fenster, "rechner": rechner, "ablage": ablage, "zeichen": zeichen, "web": web,
     "system": system}.get(MODE, lambda: None)()
