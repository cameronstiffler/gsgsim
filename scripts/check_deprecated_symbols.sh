#!/usr/bin/env bash
set -euo pipefail
# Add any other deprecated identifiers here (regex | separated)
PATTERN='deploy_cli'

# Scan code dirs, but ignore this hook file itself, backups, .git, and venvs
HITS=$(grep -RIn -E "$PATTERN" -- gsgsim tests 2>/dev/null \
  | grep -v -E 'check_deprecated_symbols\.sh|\.bak\.|/\.git/|/\.venv/' || true)

if [[ -n "$HITS" ]]; then
  echo "[deprecated-symbols] Found banned symbol(s):"
  echo "$HITS"
  exit 1
fi
