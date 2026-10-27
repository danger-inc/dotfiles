#!/usr/bin/env python3
"""Cursor-Theme „ist-punkt“ (Punkt mit Ring) in der aktuellen matugen-Farbe bauen.

Gebaut wird abwechselnd nach ~/.local/share/icons/ist-punkt-a und -b: so ist jedes
Umfärben für Hyprland ein echter Theme-Wechsel (gleicher Name wird gecacht).
~/.local/share/icons/ist-punkt zeigt als Link auf den aktuellen; nur diesen Namen
sehen Apps (gsettings), damit GTK nie live neu lädt.
Inhalt:
  - hyprcursor (SVG, scharf bei jeder Skalierung) für Hyprland
  - XCursor (PNG-Größen 24–72) für GTK/X11-Apps
Aufruf: make-cursor.py [--apply]   (--apply setzt den Cursor sofort)
Wird von ~/.config/hypr/scripts/apply-colors.sh (Super+W) aufgerufen.
"""
import json, os, re, shutil, struct, subprocess, sys, tempfile

import gi
gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg
import cairo

NAME = "ist-punkt"
HOME = os.path.expanduser("~")
ICONS = os.path.join(HOME, ".local/share/icons")
COLORS = os.path.join(HOME, ".cache/matugen/colors.css")
CONFIG = os.path.join(HOME, ".config/ist-cursor/config.json")
XSIZES = (24, 32, 36, 48, 64, 72)

# Einstellungen (Scourge → system & hardware → Cursor schreibt CONFIG)
DEFAULTS = {
    "scale": 1.3,        # Formen um die Mitte vergrößern (32er-Raster bleibt)
    "color": "primary",  # primary | secondary | tertiary | neutral | custom
    "custom": "#8fcef3", # nur bei color = custom
    "ring": 0.55,        # Deckkraft des Rings um den Punkt (0 = kein Ring)
    "outline": 1.0,      # Stärke der dunklen Kontur (0 = keine)
    "dot": 3.6,          # Radius des Mittelpunkts
    "link": 6.5,         # Radius des Rings über Links
    "wait_ms": 260,      # Bildwechsel der Warte-Punkte
}
COLOR_SOURCES = ["primary", "secondary", "tertiary", "neutral", "custom"]


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG) as fh:
            cfg.update({k: v for k, v in json.load(fh).items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({k: cfg[k] for k in DEFAULTS}, fh, indent=1)
    os.replace(tmp, CONFIG)


def palette():
    pal = {"primary": "#8fcef3", "on_primary": "#003549", "secondary": "#b5c9d7", "tertiary": "#cac1ea",
           "foreground": "#dfe3e7", "background": "#0f1417"}
    try:
        css = open(COLORS).read()
        for name in pal:
            m = re.search(rf"@define-color {name} (#[0-9a-fA-F]{{6}})", css)
            if m:
                pal[name] = m.group(1)
    except OSError:
        pass
    return pal


def colors(cfg=None):
    cfg = cfg or load_config()
    pal = palette()
    src = cfg.get("color", "primary")
    if src == "primary":
        return pal["primary"], pal["on_primary"]
    if src == "neutral":
        return pal["foreground"], pal["background"]
    if src == "custom" and re.fullmatch(r"#[0-9a-fA-F]{6}", str(cfg.get("custom", ""))):
        return cfg["custom"], pal["background"]
    return pal.get(src, pal["primary"]), pal["background"]


# ---------- Formen (32er-Raster, Hotspot jeweils Mitte) ----------

def shapes(c, k, cfg=None):
    cfg = cfg or load_config()
    O = max(0.0, float(cfg["outline"]))          # Konturfaktor
    D = float(cfg["dot"])                        # Punkt-Radius
    L = float(cfg["link"])                       # Link-Ring
    R = max(0.0, min(1.0, float(cfg["ring"])))   # Ring-Deckkraft
    sw = lambda w: round(w * O, 2)
    dot = lambda x, y, r, w=1.2, op=1: f"<circle cx='{x}' cy='{y}' r='{r}' fill='{c}' stroke='{k}' stroke-width='{sw(w)}' opacity='{op}'/>"
    line = lambda d, w=1.5: ((f"<path d='{d}' fill='none' stroke='{k}' stroke-width='{w + 2 * O}' stroke-linecap='round'/>" if O else "")
                             + f"<path d='{d}' fill='none' stroke='{c}' stroke-width='{w}' stroke-linecap='round'/>")
    ring_r = max(D + 2.5, 7.5)
    ring = (f"<circle cx='16' cy='16' r='{ring_r}' fill='{k}' fill-opacity='{round(R * .64, 2)}' stroke='{c}' stroke-opacity='{R}' stroke-width='1.2'/>"
            if R > 0 else "")
    base = ring + dot(16, 16, D)
    # Kleine Plakette unten rechts für Sonderzeiger (Hilfe, Kopieren …)
    badge = lambda inner: base + f"<circle cx='24.5' cy='24.5' r='5' fill='{k}' stroke='{c}' stroke-width='1.2'/>" + inner

    def axis(pts):  # Mittelpunkt + zwei Punkte entlang einer Achse (Größe ändern)
        return dot(16, 16, round(D * .9, 2)) + "".join(dot(x, y, 2.1, 1) for x, y in pts)

    def wait(lit):  # drei Punkte, füllen sich von links nach rechts
        return "".join(dot(9 + i * 7, 16, 2.8, 1, 1 if i < lit else .28) for i in range(3))

    S = {
        "default": [base],
        "pointer": [f"<circle cx='16' cy='16' r='{L}' fill='{c}' fill-opacity='.18' stroke='{c}' stroke-width='1.8'/>"
                    + dot(16, 16, round(D * .62, 2), 1)],
        "text": [f"<rect x='14' y='6' width='4' height='20' rx='2' fill='{c}' stroke='{k}' stroke-width='{sw(1.2)}'/>"],
        "vertical-text": [f"<rect x='6' y='14' width='20' height='4' rx='2' fill='{c}' stroke='{k}' stroke-width='{sw(1.2)}'/>"],
        "wait": [wait(n) for n in (1, 2, 3, 0)],
        "move": [dot(16, 16, D) + "".join(dot(x, y, 2, 1) for x, y in ((16, 6), (16, 26), (6, 16), (26, 16)))],
        "grab": [(f"<circle cx='16' cy='16' r='{L}' fill='none' stroke='{k}' stroke-width='{1.6 + 2 * O}'/>" if O else "")
                 + f"<circle cx='16' cy='16' r='{L}' fill='none' stroke='{c}' stroke-width='1.6' stroke-dasharray='2.6 2.5'/>"
                 + dot(16, 16, round(D * .62, 2), 1)],
        "grabbing": [dot(16, 16, round(D * 1.4, 2), 1.4)],
        "crosshair": [line("M16 4.5 V9 M16 23 V27.5 M4.5 16 H9 M23 16 H27.5")
                      + f"<circle cx='16' cy='16' r='6' fill='none' stroke='{c}' stroke-width='1.4'/><circle cx='16' cy='16' r='1.3' fill='{c}'/>"],
        "ew-resize": [axis(((7, 16), (25, 16)))],
        "ns-resize": [axis(((16, 7), (16, 25)))],
        "nwse-resize": [axis(((9.6, 9.6), (22.4, 22.4)))],
        "nesw-resize": [axis(((22.4, 9.6), (9.6, 22.4)))],
        "col-resize": [line("M16 6 V26", 1.4) + axis(((8, 16), (24, 16)))],
        "row-resize": [line("M6 16 H26", 1.4) + axis(((16, 8), (16, 24)))],
        "not-allowed": [f"<circle cx='16' cy='16' r='7.5' fill='{k}' fill-opacity='.35' stroke='{c}' stroke-width='1.8'/>" + line("M10.7 21.3 L21.3 10.7", 1.8)],
        "help": [badge(f"<path d='M22.6 23 Q22.6 21.6 24.5 21.6 Q26.4 21.6 26.4 23 Q26.4 24.2 24.5 24.6 V25.4' fill='none' stroke='{c}' stroke-width='1.2' stroke-linecap='round'/><circle cx='24.5' cy='27.2' r='.7' fill='{c}'/>")],
        "copy": [badge(f"<path d='M24.5 22 V27 M22 24.5 H27' stroke='{c}' stroke-width='1.4' stroke-linecap='round'/>")],
        "alias": [badge(f"<path d='M22.5 26.5 L26.5 22.5 M23.5 22.5 H26.5 V25.5' fill='none' stroke='{c}' stroke-width='1.3' stroke-linecap='round' stroke-linejoin='round'/>")],
        "context-menu": [badge(f"<path d='M22.3 22.8 H26.7 M22.3 24.5 H26.7 M22.3 26.2 H26.7' stroke='{c}' stroke-width='1' stroke-linecap='round'/>")],
        "zoom-in": [badge(f"<path d='M24.5 22 V27 M22 24.5 H27' stroke='{c}' stroke-width='1.4' stroke-linecap='round'/>")],
        "zoom-out": [badge(f"<path d='M22 24.5 H27' stroke='{c}' stroke-width='1.4' stroke-linecap='round'/>")],
        "cell": [line("M16 9 V23 M9 16 H23", 2.2)],
    }
    S["progress"] = [base.replace("cx='16' cy='16'", "cx='13' cy='13'") +
                     "".join(dot(18 + i * 4.5, 26, 1.7, .9, 1 if i < n else .28) for i in range(3)) for n in (1, 2, 3, 0)]
    S["no-drop"] = S["not-allowed"]
    return S


# Alle Namen, unter denen Apps die Formen anfragen (CSS/cursor-shape-v1 und alte X11-Namen)
ALIASES = {
    "default": ["left_ptr", "arrow", "top_left_arrow", "left_arrow", "right_ptr", "draft_large", "draft_small", "center_ptr", "x-cursor", "X_cursor"],
    "pointer": ["hand", "hand1", "hand2", "pointing_hand", "e29285e634086352946a0e7090d73106", "9d800788f1b08800ae810202380a0822"],
    "text": ["xterm", "ibeam"],
    "vertical-text": [],
    "wait": ["watch", "clock"],
    "progress": ["left_ptr_watch", "half-busy", "00000000000000020006000e7e9ffc3f", "08e8e1c95fe2fc01f976f1e063a24ccd", "3ecb610c1bf2410f44200f48c40d3599"],
    "move": ["fleur", "all-scroll", "size_all", "dnd-move", "4498f0e0c1937ffe01fd06f973665830", "9081237383d90e509aa00f00170e968f"],
    "grab": ["openhand", "fcf1c3c7cd4491d801f1e1c78f100000", "5aca4d189052212118709018842178c0"],
    "grabbing": ["closedhand", "dnd-none", "208530c400c041818281048008011002"],
    "crosshair": ["cross", "tcross", "cross_reverse", "diamond_cross", "target", "color-picker"],
    "ew-resize": ["e-resize", "w-resize", "right_side", "left_side", "sb_h_double_arrow", "h_double_arrow", "size_hor", "size-hor", "028006030e0e7ebffc7f7070c0600140", "14fef782d02440884392942c11205230"],
    "ns-resize": ["n-resize", "s-resize", "top_side", "bottom_side", "sb_v_double_arrow", "v_double_arrow", "size_ver", "size-ver", "00008160000006810000408080010102", "2870a09082c103050810ffdffffe0204"],
    "nwse-resize": ["nw-resize", "se-resize", "top_left_corner", "bottom_right_corner", "bd_double_arrow", "size_fdiag", "size-fdiag", "c7088f0f3e6c8088236ef8e1e3e70000"],
    "nesw-resize": ["ne-resize", "sw-resize", "top_right_corner", "bottom_left_corner", "fd_double_arrow", "size_bdiag", "size-bdiag", "fcf1c3c7cd4491d801f1e1c78f100000x"],
    "col-resize": ["split_h", "sb_h_double_arrow_col"],
    "row-resize": ["split_v"],
    "not-allowed": ["crossed_circle", "forbidden", "circle", "03b6e0fcb3499374a867c041f52298f0"],
    "no-drop": ["dnd-no-drop"],
    "help": ["question_arrow", "whats_this", "left_ptr_help", "5c6cd98b3f3ebcb1f9c7f1c204630408", "d9ce0ab605698f320427677b458ad60b"],
    "copy": ["dnd-copy", "1081e37283d90000800003c07f3ef6bf", "6407b0e94181790501fd1e167b474872"],
    "alias": ["link", "dnd-link", "3085a0e285430894940527032f8b26df", "640fb0e74195791501fd1ed57b41487f"],
    "context-menu": [],
    "zoom-in": ["zoom_in"],
    "zoom-out": ["zoom_out"],
    "cell": ["plus"],
}
ALIASES["nesw-resize"][-1] = "50585d75b494802d0151028115016902"
ANIMATED = ("wait", "progress")


def svg(inner, scale=None):
    if scale is None:
        scale = load_config()["scale"]
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'>"
            f"<g transform='translate(16 16) scale({scale}) translate(-16 -16)'>{inner}</g></svg>")


def render(svgtext, size):
    h = Rsvg.Handle.new_from_data(svgtext.encode())
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    r = Rsvg.Rectangle()
    r.x, r.y, r.width, r.height = 0, 0, size, size
    h.render_document(cairo.Context(surf), r)
    surf.flush()
    stride, data = surf.get_stride(), bytes(surf.get_data())
    return b"".join(data[y * stride:y * stride + size * 4] for y in range(size))  # ARGB vormultipliziert, LE


def write_xcursor(path, frames, delay, scale):
    chunks = []
    for size in XSIZES:
        for f in frames:
            px = render(svg(f, scale), size)
            hot = size // 2
            chunks.append((size, struct.pack("<9I", 36, 0xFFFD0002, size, 1, size, size, hot, hot, delay) + px))
    head = 16 + 12 * len(chunks)
    toc, body, pos = b"", b"", head
    for size, data in chunks:
        toc += struct.pack("<3I", 0xFFFD0002, size, pos)
        body += data
        pos += len(data)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<4sIII", b"Xcur", 16, 0x10000, len(chunks)) + toc + body)


def next_slot():
    link = os.path.join(ICONS, NAME)
    cur = os.readlink(link) if os.path.islink(link) else ""
    return NAME + ("-b" if cur.endswith("-a") else "-a")


def build():
    cfg = load_config()
    c, k = colors(cfg)
    slot = next_slot()
    OUT = os.path.join(ICONS, slot)
    S = shapes(c, k, cfg)
    delay = max(60, int(cfg["wait_ms"]))
    tmp = tempfile.mkdtemp(prefix="ist-cursor-")
    try:
        src = os.path.join(tmp, "src")
        os.makedirs(os.path.join(src, "hyprcursors"))
        with open(os.path.join(src, "manifest.hl"), "w") as fh:
            fh.write(f"name = {slot}\ndescription = Punkt-Cursor der -ist-Apps ({c})\nversion = 1\ncursors_directory = hyprcursors\n")
        xdir = os.path.join(tmp, "cursors")
        os.makedirs(xdir)
        for shape, frames in S.items():
            d = os.path.join(src, "hyprcursors", shape)
            os.makedirs(d)
            meta = ["resize_algorithm = bilinear", "hotspot_x = 0.5", "hotspot_y = 0.5", "nominal_size = 1.0"]
            names = ALIASES.get(shape, [])
            if names:
                meta.append("define_override = " + ";".join(names))
            for i, f in enumerate(frames):
                fn = f"{shape}_{i}.svg"
                open(os.path.join(d, fn), "w").write(svg(f, cfg["scale"]))
                meta.append(f"define_size = 0, {fn}" + (f", {delay}" if len(frames) > 1 else ""))
            open(os.path.join(d, "meta.hl"), "w").write("\n".join(meta) + "\n")
            write_xcursor(os.path.join(xdir, shape), frames, delay if shape in ANIMATED else 0, cfg["scale"])
            for a in names:
                os.symlink(shape, os.path.join(xdir, a))
        subprocess.run(["hyprcursor-util", "--create", src, "--output", tmp], check=True, stdout=subprocess.DEVNULL)
        built = os.path.join(tmp, f"theme_{slot}")
        new = OUT + ".new"
        shutil.rmtree(new, ignore_errors=True)
        shutil.copytree(built, new, symlinks=True)
        shutil.copytree(xdir, os.path.join(new, "cursors"), symlinks=True)
        with open(os.path.join(new, "index.theme"), "w") as fh:
            fh.write(f"[Icon Theme]\nName={slot}\nComment=Punkt-Cursor der -ist-Apps\nInherits=Adwaita\n")
        shutil.rmtree(OUT, ignore_errors=True)
        os.rename(new, OUT)
        link = os.path.join(ICONS, NAME)
        if os.path.isdir(link) and not os.path.islink(link):
            shutil.rmtree(link)  # alte Einzelordner-Version
        tmp_link = link + ".tmp"
        if os.path.lexists(tmp_link):
            os.remove(tmp_link)
        os.symlink(slot, tmp_link)
        os.replace(tmp_link, link)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return slot, c


def apply(slot):
    # Hyprland zeichnet fast alle Cursor selbst (Apps fordern per cursor-shape-Protokoll nur
    # eine Form an) – darum genügt es, Hyprland das neue Theme zu geben. Der Name wechselt
    # (a/b), weil Hyprland denselben Namen nicht neu einliest.
    subprocess.run(["hyprctl", "setcursor", slot, "24"], stdout=subprocess.DEVNULL)
    # Apps sehen dauerhaft nur den Link „ist-punkt“. Würde der gsettings-Name bei jedem Umfärben
    # wechseln, lädt GTK3 sein Theme live neu – und Waybar stürzt danach beim nächsten Hovern ab
    # (GTK3-Bug mit verwaisten Cursorn bei Skalierung 2, Coredump 2026-10-19 13:04).
    # Neu gestartete Apps lesen über den Link automatisch die aktuelle Farbe.
    key = ["org.gnome.desktop.interface", "cursor-theme"]
    cur = subprocess.run(["gsettings", "get", *key], capture_output=True, text=True).stdout.strip().strip("'")
    if cur != NAME:
        subprocess.run(["gsettings", "set", *key, NAME], stderr=subprocess.DEVNULL)
    # Sichtbaren Cursor sofort neu zeichnen, ohne ihn auszublenden (Details in refresh.py).
    subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "refresh.py")],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


if __name__ == "__main__":
    slot, col = build()
    if "--apply" in sys.argv:
        apply(slot)
    print(f"{slot} gebaut ({col})")
