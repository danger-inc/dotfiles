"""Small German → English layer for the rice helpers (waybar menus, mixer, osd).

The sources are written in German. On a system whose locale is not German (or with RICE_LANG=en (or ~/.config/rice-lang))
install() hooks the GTK text setters and tr() translates every string through rice-i18n-en.json.
Keys may contain {} for variable parts ("verbinde mit {} …"); a leading symbol/glyph is ignored.
RICE_I18N_COLLECT=<file> appends every untranslated string to that file (to extend the catalog).
"""
import json, os, re

_DIR = os.path.dirname(os.path.abspath(__file__))
_PREFIX = re.compile(r"^([^\w<{(\[]*)(.*)$", re.S)


def lang():
    """RICE_LANG, then ~/.config/rice-lang (one line: de or en), then the locale; German only for de_*."""
    try:
        forced = open(os.path.expanduser("~/.config/rice-lang")).read().strip()
    except OSError:
        forced = ""
    for v in (os.environ.get("RICE_LANG"), forced, os.environ.get("LC_ALL"), os.environ.get("LC_MESSAGES"),
              os.environ.get("LANG")):
        if v:
            return "de" if v.lower().startswith("de") else "en"
    return "en"


EN = lang() != "de"
_exact, _templates = {}, []
if EN:
    try:
        _cat = json.load(open(os.path.join(_DIR, "rice-i18n-en.json"), encoding="utf-8"))
    except (OSError, ValueError):
        _cat = {}
    for k, v in _cat.items():
        if "{}" in k:
            rx = "^" + "(.+?)".join(re.escape(p) for p in k.split("{}")) + "$"
            _templates.append((re.compile(rx, re.S), v))
        else:
            _exact[k] = v
    _templates.sort(key=lambda t: -len(t[0].pattern))


def _collect(s):
    path = os.environ.get("RICE_I18N_COLLECT")
    if path and re.search(r"[a-zäöüß]{3}", s):
        with open(path, "a", encoding="utf-8") as f:
            f.write(s.replace("\n", "\\n") + "\n")


def _core(s):
    if s in _exact:
        return _exact[s]
    for rx, out in _templates:
        m = rx.match(s)
        if m:
            for g in m.groups():
                out = out.replace("{}", g, 1)
            return out
    return None


def _split(s):
    """leading glyphs/spaces + text + trailing spaces"""
    pre, rest = _PREFIX.match(s).groups()
    core = rest.rstrip()
    return pre, core, rest[len(core):]


def tr(s):
    if not EN or not isinstance(s, str) or not s:
        return s
    r = _core(s)
    if r is not None:
        return r
    pre, core, post = _split(s)
    if core:
        r = _core(core)
        if r is None and " · " in core:             # "audio · eingabe · headset"
            parts = [_core(p) for p in core.split(" · ")]
            if any(p is not None for p in parts):
                r = " · ".join(p if p is not None else o for p, o in zip(parts, core.split(" · ")))
        if r is not None:
            return pre + r + post
    _collect(s)
    return s


_done = False


def install():
    """Hook the GTK/Pango text setters (no-op for German systems)."""
    global _done
    if _done or not EN:
        return
    _done = True
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import GObject, Gtk, Pango

    def wrap(cls, name, argpos=0):
        orig = getattr(cls, name)

        def f(self, *a, **kw):
            if len(a) > argpos and isinstance(a[argpos], str):
                a = a[:argpos] + (tr(a[argpos]),) + a[argpos + 1:]
            return orig(self, *a, **kw)
        setattr(cls, name, f)

    for cls, names in ((Gtk.Label, ("set_label", "set_text", "set_markup", "set_tooltip_text")),
                       (Gtk.Button, ("set_label", "set_tooltip_text")),
                       (Gtk.MenuButton, ("set_label", "set_tooltip_text")),
                       (Gtk.Entry, ("set_placeholder_text", "set_tooltip_text")),
                       (Gtk.Widget, ("set_tooltip_text", "set_tooltip_markup")),
                       (Gtk.Window, ("set_title",)),
                       (Pango.Layout, ("set_text", "set_markup"))):
        for n in names:
            if hasattr(cls, n):
                wrap(cls, n)

    init = GObject.Object.__init__
    keys = ("label", "tooltip_text", "tooltip_markup", "placeholder_text", "title")

    def obj_init(self, *a, **kw):
        for k in keys:
            if isinstance(kw.get(k), str):
                kw[k] = tr(kw[k])
        return init(self, *a, **kw)
    GObject.Object.__init__ = obj_init
