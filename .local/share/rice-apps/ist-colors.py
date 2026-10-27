#!/usr/bin/env python3
# Schreibt die Farben der Suite-Auswahl (istheme.resolve) für Leiste und Terminal nach ~/.cache/ist/:
#   colors.css         – Waybar (und alles, was GTK-CSS-Farben liest)
#   colors-kitty.conf  – Kitty (kitty.conf bindet sie ein), danach die 161-Logo-Farben
# sowie für rofi, hyprlock, Fensterrahmen (Hyprland) und btop, und lädt alles neu, was sich geändert hat.
#   ist-colors.py            einmal ausführen (auch aus apply-colors.sh nach matugen)
#   ist-colors.py --watch    wartet auf Änderungen von ~/.config/ist-theme.json (Autostart)
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import istheme  # noqa: E402

OUT = os.path.expanduser("~/.cache/ist")
MATUGEN_KITTY = os.path.expanduser("~/.cache/matugen/colors-kitty.conf")
WAYBAR_CSS = os.path.expanduser("~/.config/waybar/style.css")
LOGO = os.path.expanduser("~/.config/fastfetch/kitty-colors.sh")
MATUGEN = os.path.expanduser("~/.cache/matugen")
BTOP_THEME = os.path.expanduser("~/.config/btop/themes/ist.theme")


def mix(a, b, pct):
    """pct % von a, Rest b."""
    ra, rb = istheme._rgb(a), istheme._rgb(b)
    return istheme._hex(*(x * pct / 100 + y * (100 - pct) / 100 for x, y in zip(ra, rb)))


def kitty_conf(css, light):
    c = istheme.parse(css)
    bg, fg, pri, sec, ter = (c[k] for k in ("background", "foreground", "primary", "secondary", "tertiary"))
    if light:   # Signalfarben, die auf hellem Grund lesbar bleiben
        sig = {1: "#ba1a1a", 9: "#d32f2f", 2: "#2e7d32", 10: "#43934a", 3: "#8a6100", 11: "#a87a10"}
        c0, c7 = mix(fg, bg, 70), mix(fg, bg, 75)
    else:
        sig = {1: "#f2b8b5", 9: "#f9dedc", 2: "#a6d189", 10: "#b9e09f", 3: "#e5c890", 11: "#efd7a8"}
        c0, c7 = c.get("surface_container", bg), mix(fg, bg, 85)
    p = {0: c0, 4: pri, 5: ter, 6: sec, 7: c7, 8: c["outline"], 12: pri, 13: ter, 14: sec, 15: fg, **sig}
    lines = ["# Automatisch erzeugt von ~/.local/share/rice-apps/ist-colors.py (Auswahl der Suite, hell/dunkel)",
             f"foreground {fg}", f"background {bg}", f"cursor {pri}",
             f"selection_foreground {c['on_primary']}", f"selection_background {pri}", f"url_color {ter}", ""]
    lines += [f"color{i} {p[i]}" for i in range(16)]
    return "\n".join(lines) + "\n"


def _a(col, alpha):
    return col + "%02x" % alpha


def rofi_conf(c):
    bg, pri = c["background"], c["primary"]
    return ("* {\n"
            f"    bg: {_a(bg, 0x99)};\n    bg-input: {_a(bg, 0x4d)};\n    border-dim: {_a(pri, 0x73)};\n"
            f"    bg-alt: {c['surface_container']};\n    bg-selected: {pri};\n    fg: {c['foreground']};\n"
            f"    fg-dim: {c['outline']};\n    fg-selected: {c['on_primary']};\n    border-color: {pri};\n"
            f"    bg-panel: {_a(bg, 0xd9)};\n    bg-tab: {_a(pri, 0x38)};\n    bg-hover: {_a(pri, 0x1f)};\n"
            f"    line: {_a(pri, 0x8c)};\n    fg-accent: {pri};\n}}\n")


def hyprlock_conf(c):
    r = lambda k: "rgb(%s)" % c[k][1:]
    return (f"$background = {r('background')}\n$foreground = {r('foreground')}\n$color0 = {r('background')}\n"
            f"$color1 = {r('primary')}\n$color2 = {r('secondary')}\n$color3 = {r('tertiary')}\n"
            f"$color7 = {r('foreground')}\n$color9 = {r('primary')}\n")


def hyprland_lua(c, light):
    return ("return {\n"
            f'    active1  = "rgba({c["primary"][1:]}ee)",\n    active2  = "rgba({c["tertiary"][1:]}ee)",\n'
            f'    inactive = "rgba({c["outline"][1:]}aa)",\n}}\n')


def btop_theme(c, light):
    bg, fg, pri, sec, ter = (c[k] for k in ("background", "foreground", "primary", "secondary", "tertiary"))
    err = "#ba1a1a" if light else "#ffb4ab"
    t = {"main_bg": bg, "main_fg": fg, "title": pri, "hi_fg": pri, "selected_bg": mix(pri, bg, 30),
         "selected_fg": fg, "inactive_fg": c["outline"], "graph_text": mix(fg, bg, 80),
         "meter_bg": c["surface_container"], "proc_misc": sec, "cpu_box": pri, "mem_box": sec, "net_box": ter,
         "proc_box": pri, "div_line": mix(c["outline"], bg, 50)}
    for name, col in (("temp", sec), ("cpu", sec), ("process", sec)):
        t.update({f"{name}_start": col, f"{name}_mid": pri, f"{name}_end": err})
    t.update({"used_start": pri, "used_mid": ter, "used_end": err})
    for name, col in (("free", sec), ("cached", ter), ("available", pri), ("download", sec), ("upload", ter)):
        t.update({f"{name}_start": mix(col, bg, 45), f"{name}_mid": col, f"{name}_end": mix(col, fg, 70)})
    return "".join(f'theme[{k}]="{v}"\n' for k, v in t.items())


def write(path, text):
    try:
        if open(path, encoding="utf-8").read() == text:
            return False
    except OSError:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    return True


def _at():
    """Gemeinsamer Umschaltzeitpunkt (Epoche) aus der Auswahldatei, 0 wenn keiner gesetzt ist."""
    try:
        import json
        with open(istheme.CONFIG, encoding="utf-8") as f:
            at = float(json.load(f).get("at") or 0)
    except (OSError, ValueError, AttributeError, TypeError):
        return 0.0
    return at if 0 < at - time.time() < 1.0 else 0.0


# Vorlauf (s) vor dem Umschaltzeitpunkt, negativ = danach: Leiste, Rahmen und Terminal wechseln hart, die Apps blenden
# über – darum springen sie zur Mitte der Überblendung (at + 0,16 s). Werte aus Videomessungen (60 fps) abgeglichen.
LEAD_WAYBAR = -0.16
LEAD_BORDER = -0.13
LEAD_KITTY = -0.043


def _wait(t):
    d = t - time.time()
    if d > 0:
        time.sleep(d)


def run(at=0.0):
    os.makedirs(OUT, exist_ok=True)
    css, light = istheme.resolve()
    # Dunkel + Automatisch: matugens eigene Kitty-Datei unverändert (feinere Abstufungen als die Ableitung)
    kconf = None
    if istheme.load()["theme"] == "auto" and not light:
        try:
            kconf = open(MATUGEN_KITTY, encoding="utf-8").read()
        except OSError:
            pass
    if kconf is None:
        kconf = kitty_conf(css, light)
    changed_css = write(f"{OUT}/colors.css", css)
    write(f"{OUT}/colors-kitty.conf", kconf)
    c = istheme.parse(css)
    stock = istheme.load()["theme"] == "auto" and not light   # Dunkel + Automatisch: matugens Dateien unverändert

    def pick(name, fallback):
        if stock:
            try:
                return open(f"{MATUGEN}/{name}", encoding="utf-8").read()
            except OSError:
                pass
        return fallback
    write(f"{OUT}/colors-rofi.rasi", pick("colors-rofi.rasi", rofi_conf(c)))
    write(f"{OUT}/colors-hyprlock.conf", pick("colors-hyprlock.conf", hyprlock_conf(c)))
    border = write(f"{OUT}/colors-hyprland.lua", pick("colors-hyprland.lua", hyprland_lua(c, light)))
    btop = False
    try:
        btop = write(BTOP_THEME, open(os.path.expanduser("~/.config/btop/themes/matugen.theme"),
                                      encoding="utf-8").read() if stock else btop_theme(c, light))
    except OSError:
        pass
    # Dateien sind geschrieben; die sichtbaren Auslöser kommen gestaffelt, damit alles zum Zeitpunkt `at` erscheint
    steps = []
    if changed_css:   # Waybar lädt nur bei echter Inhaltsänderung des Stylesheets neu
        def waybar():
            try:
                s = open(WAYBAR_CSS, encoding="utf-8").read()
                s = re.sub(r"^/\* matugen-reload:.*", f"/* matugen-reload: {time.time_ns()} */", s, flags=re.M)
                open(WAYBAR_CSS, "w", encoding="utf-8").write(s)
            except OSError:
                pass
            subprocess.call(["swaync-client", "-rs"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        steps.append((LEAD_WAYBAR, waybar))
    if border and "--no-reload" not in sys.argv:   # apply-colors.sh lädt Hyprland selbst
        steps.append((LEAD_BORDER, lambda: subprocess.call(["hyprctl", "reload"], stdout=subprocess.DEVNULL,
                                                           stderr=subprocess.DEVNULL)))
    steps.append((LEAD_KITTY, lambda: subprocess.call(["pkill", "-USR1", "-x", "kitty"])))
    if btop:
        steps.append((0.0, lambda: subprocess.call(["pkill", "-USR2", "-x", "btop"])))
    import threading
    names = {}

    def fire(lead, fn):
        if at:
            _wait(at - lead)
        t = time.time()
        fn()
        if os.environ.get("IST_COLORS_DEBUG"):
            print("step lead=%.3f start %+.3f end %+.3f (rel. at)" % (lead, t - at, time.time() - at), flush=True)
    th = [threading.Thread(target=fire, args=st) for st in steps]
    for t in th:
        t.start()
    for t in th:
        t.join()
    subprocess.call(["bash", LOGO])


def watch():
    run()
    cfg = istheme.CONFIG
    p = subprocess.Popen(["inotifywait", "-m", "-q", "-e", "close_write,moved_to", "--format", "%f",
                          os.path.dirname(cfg)], stdout=subprocess.PIPE, text=True)
    for name in p.stdout:
        if name.strip() == os.path.basename(cfg):
            time.sleep(0.05)
            run(_at())


if __name__ == "__main__":
    watch() if "--watch" in sys.argv else run()
