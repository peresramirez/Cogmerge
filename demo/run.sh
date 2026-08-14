#!/usr/bin/env bash
# The 90-second demo. Run from the project root: bash demo/run.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$ROOT/demo/payments-api"
S="$ROOT/.claude/skills/cogmerge/scripts"

[ -d "$REPO" ] || { echo "Run 'bash demo/setup.sh' first."; exit 1; }

echo "=== 1. Alice finished her branch three days ago. Her intent was sealed. ==="
python3 "$S/seal.py" "$ROOT/demo/alice_intent.json"

echo
echo "=== 2. Bob's PR. Git says clean, CI says green, a reviewer says LGTM. ==="
git -C "$REPO" --no-pager diff main...refactor/webhook-cleanup --stat

echo
echo "=== 3. What Cogmerge remembers about the code he is touching ==="
python3 "$S/check.py" --base main --head refactor/webhook-cleanup \
  --cwd "$REPO" --exclude-branch refactor/webhook-cleanup
