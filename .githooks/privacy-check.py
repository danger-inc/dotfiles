#!/usr/bin/env python3
"""Datenschutz-Prüfung für die Dotfiles. Bricht ab, wenn persönliche Daten mitkommen würden.

  privacy-check.py           prüft alle Textdateien im Arbeitsverzeichnis
  privacy-check.py --staged  prüft die vorgemerkten Dateien (pre-commit-Hook)

Eigene Suchbegriffe stehen NICHT im Repo, sondern in ~/.config/notes-publish/blocklist.txt.
"""
import os, re, subprocess, sys

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() \
    or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCKLIST = os.path.expanduser("~/.config/notes-publish/blocklist.txt")
SECRETS = [
    (r"/home/(?!user\b)[A-Za-z0-9_.-]+", "absoluter Pfad mit Benutzername (→ @HOME@)"),
    (r"/Users/[A-Za-z0-9_.-]+", "absoluter Pfad mit Benutzername"),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}", "E-Mail-Adresse"),
    (r"\b(gh[opsur]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})", "GitHub-Token"),
    (r"\bya29\.[A-Za-z0-9_-]{10,}|\b1//0[A-Za-z0-9_-]{20,}", "Google-OAuth-Token"),
    (r"\bAIza[0-9A-Za-z_-]{30,}", "Google-API-Schlüssel"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "privater Schlüssel"),
    (r"\bsk-[A-Za-z0-9_-]{20,}", "API-Schlüssel"),
    (r"(?i)\b(password|passwd|secret|token)\s*=\s*['\"][^'\"]{6,}['\"]", "Zugangsdaten"),
]
OK_MAIL = re.compile(r"@(users\.noreply\.github\.com|example\.(com|org|net)|beispiel\.(de|com|org)|localhost)$", re.I)
IMG = re.compile(r"\.(png|jpe?g|webp|gif)$", re.I)


def files():
    args = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"] if "--staged" in sys.argv else ["git", "ls-files", "-co", "--exclude-standard"]
    out = subprocess.run(args, capture_output=True, text=True, cwd=ROOT).stdout
    return [f for f in out.splitlines() if f]


def blocklist():
    try:
        return [l.strip().lower() for l in open(BLOCKLIST, encoding="utf-8") if l.strip() and not l.startswith("#")]
    except OSError:
        return []


def main():
    bad, terms = [], blocklist()
    for rel in files():
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path) or rel.startswith(".githooks/"):
            continue
        raw = open(path, "rb").read()
        if IMG.search(rel):                       # Bilder: nur Metadaten (EXIF/Text-Chunks) sind kritisch
            if b"eXIf" in raw or b"tEXt" in raw or b"iTXt" in raw or b"Exif\x00" in raw[:4096]:
                bad.append((rel, "Bild enthält Metadaten (mit dem Screenshot-Skript neu speichern)"))
            continue
        if b"\0" in raw:
            continue
        text = raw.decode("utf-8", "replace")
        for pat, why in SECRETS:
            for m in re.finditer(pat, text):
                if why == "E-Mail-Adresse" and OK_MAIL.search(m.group(0)):
                    continue
                if why.startswith("E-Mail") and re.search(r"\.(png|jpe?g|svg|css|js|so|conf)$", m.group(0)):
                    continue
                bad.append((rel, why)); break
        low = text.lower()
        for t in terms:
            if t in low:
                bad.append((rel, "Sperrbegriff aus der Blocklist")); break
    if bad:
        print("Datenschutz-Prüfung: gestoppt!")
        for rel, why in bad:
            print(f"  {rel}: {why}")
        sys.exit(1)
    print("Datenschutz-Prüfung: ok")


main()
