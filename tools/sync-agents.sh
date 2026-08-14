#!/usr/bin/env bash
# Generate the .cursor/ and .agents/ trees from .claude/, so they cannot drift.
#
#   bash tools/sync-agents.sh           regenerate both from .claude/
#   bash tools/sync-agents.sh --check   exit 1 if they are out of sync (for CI)
#
# .claude/ is the single source of truth.
#
#   .claude/skills   Claude Code, natively
#   .agents/skills   Codex ($REPO_ROOT/.agents/skills) and Cursor, both natively
#   .cursor/skills   Cursor, and it WINS over the others on a name conflict
#
# That precedence is why this script exists: hand-edit .cursor/ and it silently
# beats .claude/ forever. Never edit the generated trees.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

# $1 = destination root, $2 = the skill path to rewrite references to
build() {
  local out="$1" skillpath="$2"
  rm -rf "$out/skills/cogmerge" "$out/agents"
  mkdir -p "$out/skills" "$out/agents"

  cp -R .claude/skills/cogmerge "$out/skills/cogmerge"
  cp .claude/agents/cogmerge-*.md "$out/agents/"
  find "$out" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

  # Rewrite skill-root paths so each tree is self-contained: an adopter can take
  # any one of them alone and every command in it still resolves.
  find "$out" -name '*.md' -type f -print0 | while IFS= read -r -d '' f; do
    sed -i '' "s|\.claude/skills/cogmerge|$skillpath|g" "$f" 2>/dev/null \
      || sed -i "s|\.claude/skills/cogmerge|$skillpath|g" "$f"
  done
}

X=(-x __pycache__ -x '*.pyc')

if [ "$CHECK" = 1 ]; then
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  build "$TMP/cursor" ".cursor/skills/cogmerge"
  build "$TMP/agents" ".agents/skills/cogmerge"

  fail=0
  for pair in "cursor:.cursor" "agents:.agents"; do
    src="$TMP/${pair%%:*}"; dst="${pair##*:}"
    if ! diff -r -q "${X[@]}" "$src/skills/cogmerge" "$dst/skills/cogmerge" >/dev/null 2>&1 \
       || ! diff -r -q "${X[@]}" "$src/agents" "$dst/agents" >/dev/null 2>&1; then
      echo "OUT OF SYNC — $dst does not match .claude/" >&2
      diff -r "${X[@]}" "$src/skills/cogmerge" "$dst/skills/cogmerge" 2>&1 | head -12 >&2 || true
      fail=1
    fi
  done
  if [ "$fail" = 1 ]; then
    echo >&2; echo "Fix with: bash tools/sync-agents.sh" >&2; exit 1
  fi
  echo "in sync: .cursor/ and .agents/ both match .claude/"
else
  build .cursor ".cursor/skills/cogmerge"
  build .agents ".agents/skills/cogmerge"
  echo "regenerated from .claude/:"
  find .cursor .agents -type f | sort | sed 's/^/  /'
fi
