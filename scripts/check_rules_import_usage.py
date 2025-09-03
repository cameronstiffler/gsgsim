#!/usr/bin/env python3
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FAILS = []


def check_file(p: pathlib.Path):
    s = p.read_text(encoding="utf-8", errors="ignore")
    for m in re.finditer(r"^\s*from\s+\.rules\s+import\s+([^\n#]+)", s, flags=re.M):
        names = [x.strip() for x in m.group(1).split(",") if x.strip()]
        for name in names:
            # require a real usage, not just the import line
            # simple, conservative check: word boundary occurrence elsewhere
            pattern = r"\b" + re.escape(name) + r"\b"
            # wipe the import line itself to avoid a false positive
            s_wo = s.replace(m.group(0), "")
            if not re.search(pattern, s_wo):
                FAILS.append((str(p), name))


def main():
    for p in ROOT.rglob("gsgsim/**/*.py"):
        check_file(p)
    if FAILS:
        for fn, name in FAILS:
            print(f"[rules-import-unused] {fn}: '{name}' imported from .rules but not used", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
