#!/usr/bin/env python3
# rice-tui: keeps the apps audio, netz and bluetooth fully built in the background so they
# appear instantly on a right click in the waybar (like the volume mixer).
#   Start:   ricetui.py --daemon          (from hyprland.lua)
#   Open:    echo audio > $XDG_RUNTIME_DIR/rice-tui.fifo   (done by ~/.local/bin/rice-audio etc.)
#            "audio" = toggle (if the window already has focus: hide), "audio:out" = open tab,
#            "audio:hide" = hide.
# Closing only hides the windows; timers, levels and the bluetooth scan run only while they are open.
import os, signal, sys, warnings

# software renderer: looks the same (Hyprland does the blur) but needs only half the memory
os.environ.setdefault("GSK_RENDERER", "cairo")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tui
import rice_i18n; rice_i18n.install()  # noqa: E402  (sets the GTK versions)
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
        tui.Theme.get()  # load once, so even the first window is already styled
        for name, (mod, cls) in APPS.items():
            module = __import__(mod)
            self.wins[name] = getattr(module, cls)(self)

        if os.path.exists(FIFO) and not os.path.isfile(FIFO):
            os.unlink(FIFO)
        if not os.path.exists(FIFO):
            os.mkfifo(FIFO, 0o600)
        # O_RDWR: the pipe stays open even when nobody is writing (no EOF flood)
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
        else:  # prepare windows invisibly so even the first open is instant
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
        """Close an open wifi/bluetooth menu (wofi including its click lock) and the volume mixer –
        only after showing, so it does not delay the window."""
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
    if running_pid():  # already running: just notify it
        if show:
            with open(FIFO, "w") as f:
                f.write(show + "\n")
        if "--daemon" not in args:
            return 0
        os.kill(running_pid(), signal.SIGTERM)  # --daemon: replace the old process
        import time
        time.sleep(0.5)
    return Daemon(show).run(None)


if __name__ == "__main__":
    sys.exit(main())
