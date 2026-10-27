#!/usr/bin/env python3
"""Privacy check for the dotfiles. Aborts if personal data would be included.

  privacy-check.py           checks all text files in the working directory
  privacy-check.py --staged  checks the staged files (pre-commit hook)

Custom search terms are NOT in the repo but in ~/.config/notes-publish/blocklist.txt.
"""
import os, re, subprocess, sys

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() \
    or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCKLIST = os.path.expanduser("~/.config/notes-publish/blocklist.txt")
SECRETS = [
    (r"/home/(?!user\b)[A-Za-z0-9_.-]+", "absolute path with user name (→ @HOME@)"),
    (r"/Users/[A-Za-z0-9_.-]+", "absolute path with user name"),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}", "email address"),
    (r"\b(gh[opsur]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})", "GitHub token"),
    (r"\bya29\.[A-Za-z0-9_-]{10,}|\b1//0[A-Za-z0-9_-]{20,}", "Google OAuth token"),
    (r"\bAIza[0-9A-Za-z_-]{30,}", "Google API key"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
    (r"\bsk-[A-Za-z0-9_-]{20,}", "API key"),
    (r"(?i)\b(password|passwd|secret|token)\s*=\s*['\"][^'\"]{6,}['\"]", "credentials"),
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
                bad.append((rel, "image contains metadata (re-save it without EXIF/text chunks)"))
            continue
        if b"\0" in raw:
            continue
        text = raw.decode("utf-8", "replace")
        for pat, why in SECRETS:
            for m in re.finditer(pat, text):
                if why == "email address" and OK_MAIL.search(m.group(0)):
                    continue
                if why.startswith("email") and re.search(r"\.(png|jpe?g|svg|css|js|so|conf)$", m.group(0)):
                    continue
                bad.append((rel, why)); break
        low = text.lower()
        for t in terms:
            if t in low:
                bad.append((rel, "term from the blocklist")); break
    if bad:
        print("privacy check: stopped!")
        for rel, why in bad:
            print(f"  {rel}: {why}")
        sys.exit(1)
    print("privacy check: ok")


main()
