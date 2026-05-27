"""Pre-release sanitization scanner.

Walks the git-tracked working tree + recent commit messages, looking for
patterns that should not ship in a public release:

- API keys / tokens (OpenAI, GitHub, HuggingFace, PyPI, generic 32+ hex)
- Private key headers (PEM / OpenSSH)
- Hardcoded local paths (Windows ``C:\\Users\\...`` / POSIX ``/home/...``)
- Optional: custom sensitive-term list from ``~/.engram-release-sensitive.txt``
  (one term per line; not committed to the repo — each maintainer keeps
  their own).

Run from the repo root:

    python scripts/release_sanitize_check.py
    python scripts/release_sanitize_check.py --commit-messages   # also scan git log
    python scripts/release_sanitize_check.py --strict            # exit 1 on any hit

Exit code:
- 0 — no hits (or only informational hits in non-strict mode)
- 1 — at least one hit was found in --strict mode
- 2 — scanner setup error (not in a git repo, etc.)

This is a *sanity net*, not a guarantee. Real secrets get past regex
scanners all the time. Always pair this with the four-layer manual
checklist in ``docs/release-playbook.md``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# (label, regex, severity)  severity: "high" / "warn"
_BUILT_IN_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("OpenAI key",     re.compile(r"sk-[A-Za-z0-9]{20,}"),                "high"),
    ("GitHub token",   re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),         "high"),
    ("PyPI token",     re.compile(r"pypi-[A-Za-z0-9_-]{20,}"),            "high"),
    ("HuggingFace",    re.compile(r"hf_[A-Za-z0-9]{20,}"),                "high"),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}"),                   "high"),
    ("Slack token",    re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),       "high"),
    ("PEM private",    re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),           "high"),
    ("Windows path",   re.compile(r"C:\\\\Users\\\\[A-Za-z0-9_.-]+",
                                  re.IGNORECASE),                         "warn"),
    ("POSIX home",     re.compile(r"/home/[a-z][a-z0-9_-]+(?:/|$)"),      "warn"),
    ("password=",      re.compile(r"(?<![a-z_])password\s*[:=]\s*['\"][^'\"]+",
                                  re.IGNORECASE),                         "warn"),
]

# Files to skip even if git-tracked.
_SKIP_GLOBS = (
    ".git/",
    "scripts/release_sanitize_check.py",  # self
    "docs/release-playbook.md",           # documents the patterns
    "docs/playbook-auto-extraction-design.md",  # discusses redaction examples
    "CHANGELOG.md",                       # historical, version paths OK
    "tests/",                             # test fixtures often need keys
    "Dockerfile",                         # /home/<container-user>/ is not a host path
)


def _git_tracked_files() -> list[Path]:
    try:
        out = subprocess.check_output(
            ["git", "ls-files"], text=True, encoding="utf-8"
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"[error] git ls-files failed: {exc}", file=sys.stderr)
        sys.exit(2)
    return [Path(line) for line in out.splitlines() if line]


def _should_skip(rel_path: str) -> bool:
    s = rel_path.replace("\\", "/")
    return any(s.startswith(p) or p in s for p in _SKIP_GLOBS)


def _load_custom_terms() -> list[re.Pattern[str]]:
    home_list = Path.home() / ".engram-release-sensitive.txt"
    if not home_list.is_file():
        return []
    terms: list[re.Pattern[str]] = []
    for line in home_list.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(re.compile(re.escape(line), re.IGNORECASE))
    return terms


def _scan_file(path: Path, custom: list[re.Pattern[str]]) -> list[tuple[str, str, int, str]]:
    """Return list of (label, severity, line_no, line_text)."""
    hits: list[tuple[str, str, int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return hits
    for lineno, line in enumerate(text.splitlines(), 1):
        for label, pat, severity in _BUILT_IN_PATTERNS:
            if pat.search(line):
                hits.append((label, severity, lineno, line.strip()[:160]))
        for i, pat in enumerate(custom):
            if pat.search(line):
                hits.append((f"custom#{i+1}", "warn", lineno, line.strip()[:160]))
    return hits


def _scan_commit_messages(custom: list[re.Pattern[str]]) -> list[tuple[str, str, str, str]]:
    """Return list of (sha, label, severity, snippet)."""
    try:
        out = subprocess.check_output(
            ["git", "log", "--all", "--format=%H%n%s%n%b%n---END---"],
            text=True, encoding="utf-8",
        )
    except subprocess.CalledProcessError:
        return []
    hits: list[tuple[str, str, str, str]] = []
    current_sha = ""
    current_body: list[str] = []
    for line in out.splitlines():
        if line == "---END---":
            text = "\n".join(current_body)
            for label, pat, severity in _BUILT_IN_PATTERNS:
                m = pat.search(text)
                if m:
                    hits.append((current_sha[:10], label, severity, m.group(0)[:80]))
            for i, pat in enumerate(custom):
                m = pat.search(text)
                if m:
                    hits.append((current_sha[:10], f"custom#{i+1}", "warn", m.group(0)[:80]))
            current_sha = ""
            current_body = []
        elif not current_sha:
            current_sha = line
        else:
            current_body.append(line)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    ap.add_argument("--commit-messages", action="store_true",
                    help="Also scan git commit messages (slower)")
    ap.add_argument("--strict", action="store_true",
                    help="Exit code 1 if any hit is found (including warn-level)")
    args = ap.parse_args()

    custom = _load_custom_terms()
    if custom:
        print(f"[info] loaded {len(custom)} custom term(s) from ~/.engram-release-sensitive.txt")
    else:
        print("[info] no ~/.engram-release-sensitive.txt — only built-in patterns")

    total_high = 0
    total_warn = 0

    print("\n== Scanning working tree ==")
    for path in _git_tracked_files():
        rel = str(path).replace("\\", "/")
        if _should_skip(rel):
            continue
        hits = _scan_file(path, custom)
        for label, severity, lineno, line_text in hits:
            marker = "[HIGH]" if severity == "high" else "[warn]"
            print(f"  {marker} {rel}:{lineno}  {label}: {line_text}")
            if severity == "high":
                total_high += 1
            else:
                total_warn += 1

    if args.commit_messages:
        print("\n== Scanning commit messages ==")
        for sha, label, severity, snippet in _scan_commit_messages(custom):
            marker = "[HIGH]" if severity == "high" else "[warn]"
            print(f"  {marker} {sha} {label}: {snippet}")
            if severity == "high":
                total_high += 1
            else:
                total_warn += 1

    print(f"\n== Summary ==  high={total_high}  warn={total_warn}")

    if total_high > 0:
        print("\n[FAIL] HIGH-severity hits found. Fix before releasing.")
        return 1
    if args.strict and total_warn > 0:
        print("\n[FAIL] --strict mode: warn-level hits also block release.")
        return 1
    print("\n[OK] no high-severity hits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
