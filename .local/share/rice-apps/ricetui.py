#!/usr/bin/env python3
# rice-tui: hält die Apps audio, netz und bluetooth fertig gebaut im Hintergrund bereit, damit sie
# beim Rechtsklick in der Waybar sofort erscheinen (wie der Lautstärke-Mixer).
#   Start:   ricetui.py --daemon          (aus hyprland.lua)
#   Öffnen:  echo audio > $XDG_RUNTIME_DIR/rice-tui.fifo   (macht ~/.local/bin/rice-audio usw.)
#            "audio" = ein/aus (hat das Fenster schon den Fokus: verstecken), "audio:out" = Tab öffnen,
#            "audio:hide" = verstecken.
# Schließen versteckt die Fenster nur; Timer, Pegel und Bluetooth-Suche laufen nur, solange sie offen sind.
import os, signal, sys, warnings

# Software-Renderer: sieht gleich aus (Blur macht Hyprland), braucht aber nur halb so viel Speicher
os.environ.setdefault("GSK_RENDERER", "cairo")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tui
import rice_i18n; rice_i18n.install()  # noqa: E402  (setzt die GTK-Versionen)
from tui import Gio, GLib, Gtk  # noqa: E402

RUNTIME = GLib.get_user_runtime_dir()
FIFO = RUNTIME + "/rice-tui.fifo"
PID_FILE = RUNTIME + "/rice-tui.pid"
APPS = {"audio": ("audio", "AudioWindow"), "netz": ("network", "NetWindow"),
        "bluetooth": ("bluetooth", "BtWindow")}


class Daemon(Gtk.Application):
    def __init__(self, show):
        super().__init__(application_id="de.invincible.RiceTui", flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.show_first = show
        self.wins = {}

    def do_activate(self):
        self.hold()
        tui.Theme.get()  # einmal laden, damit schon das erste Fenster fertig gestylt ist
        for name, (mod, cls) in APPS.items():
            module = __import__(mod)
            self.wins[name] = getattr(module, cls)(self)

        if os.path.exists(FIFO) and not os.path.isfile(FIFO):
            os.unlink(FIFO)
        if not os.path.exists(FIFO):
            os.mkfifo(FIFO, 0o600)
        # O_RDWR: die Leitung bleibt offen, auch wenn gerade niemand schreibt (kein EOF-Dauerfeuer)
        self.fd = os.open(FIFO, os.O_RDWR | os.O_NONBLOCK)
        GLib.io_add_watch(self.fd, GLib.PRIORITY_HIGH, GLib.IOCondition.IN, self.on_fifo)
        with open(PID_FILE, "w") as f:
            f.write(f"{os.getpid()}\n")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for sig in (signal.SIGTERM, signal.SIGINT):
                GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, self.stop)
        if self.show_first:
            self.toggle(self.show_first)
        else:  # Fenster schon mal unsichtbar vorbereiten, damit auch das erste Öffnen sofort geht
            for win in self.wins.values():
                GLib.idle_add(lambda w=win: w.realize() and False)

    def on_fifo(self, fd, _cond):
        try:
            data = os.read(fd, 4096).decode(errors="ignore")
        except BlockingIOError:
            return True
        for cmd in data.split():
            self.toggle(cmd)
        return True

    def toggle(self, cmd):
        name, _, tab = cmd.partition(":")
        win = self.wins.get(name)
        if win is None:
            return
        if tab == "hide" or (win.get_visible() and win.is_active() and not tab):
            win.set_visible(False)
            return
        if tab:
            win.show_tab(tab)
        win.present()
        GLib.idle_add(self.close_menus)

    def close_menus(self):
        """Offenes WLAN-/Bluetooth-Menü (wofi samt Klick-Sperre) und den Lautstärke-Mixer zumachen –
        erst nach dem Einblenden, damit es das Fenster nicht verzögert."""
        if os.path.exists(RUNTIME + "/volume-mixer-open"):
            try:
                os.kill(int(open(RUNTIME + "/volume-mixer.pid").read()), signal.SIGUSR2)
            except (OSError, ValueError):
                pass
        for pid in os.listdir("/proc"):
            if pid.isdigit():
                try:
                    comm = open(f"/proc/{pid}/comm").read().strip()
                    if comm == "wofi" or (comm == "python3" and b"click-catcher" in
                                          open(f"/proc/{pid}/cmdline", "rb").read()):
                        os.kill(int(pid), signal.SIGTERM)
                except OSError:
                    pass
        return False

    def stop(self):
        bt = self.wins.get("bluetooth")
        if bt:
            bt.shutdown()
        for path in (PID_FILE, FIFO):
            try:
                os.unlink(path)
            except OSError:
                pass
        self.quit()
        return False


def running_pid():
    try:
        pid = int(open(PID_FILE).read())
        os.kill(pid, 0)
        return pid if os.path.exists(FIFO) else None
    except (OSError, ValueError):
        return None


def main(show=None):
    args = sys.argv[1:]
    show = next((a.split("=", 1)[1] for a in args if a.startswith("--show=")), show)
    if running_pid():  # läuft schon: nur Bescheid geben
        if show:
            with open(FIFO, "w") as f:
                f.write(show + "\n")
        if "--daemon" not in args:
            return 0
        os.kill(running_pid(), signal.SIGTERM)  # --daemon: alten Prozess ersetzen
        import time
        time.sleep(0.5)
    return Daemon(show).run(None)


if __name__ == "__main__":
    sys.exit(main())
