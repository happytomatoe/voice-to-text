#!/usr/bin/env bash
# Reject commits that include a Co-Authored-By trailer.
# pre-commit invokes this at the commit-msg stage, passing the path to the
# commit message file as $1. The pi git-commit skill forbids Co-Authored-By
# lines, so this enforces that rule mechanically.
set -euo pipefail

msg_file="${1:?commit message file required}"

if grep -iqE '^[[:space:]]*Co-Authored-By:' "$msg_file"; then
    echo "ERROR: commit message contains a 'Co-Authored-By' trailer." >&2
    echo "Remove it — the pi git-commit skill forbids Co-Authored-By lines." >&2
    exit 1
fi
