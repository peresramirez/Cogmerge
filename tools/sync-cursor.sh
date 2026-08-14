#!/usr/bin/env bash
# Generate the .cursor/ tree from .claude/, so the two can never drift.
#
#   bash tools/sync-cursor.sh           regenerate .cursor/ from .claude/
#   bash tools/sync-cursor.sh --check   exit 1 if they are out of sync (for CI)
#
# .claude/ is the single source of truth. Cursor reads .claude/ natively via its
# compatibility paths, but .cursor/ takes precedence on a name conflict -- so if
# these two ever disagree, the .cursor/ copy silently wins. That is the whole
# reason this script exists: never hand-edit .cursor/skills or .cursor/agents.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

build() {
  local out="$1"
  rm -rf "$out/skills/cogmerge" "$out/agents"
  mkdir -p "$out/skills" "$out/agents"

  cp -R .claude/skills/cogmerge "$out/skills/cogmerge"
  cp .claude/agents/cogmerge-*.md "$out/agents/"

  # Rewrite the skill-root paths so each tree is self-contained: an adopter can
  # take .cursor/ alone, or .claude/ alone, and every command still resolves.
  find "$out" -name '*.md' -type f -print0 | while IFS= read -r -d '' f; do
    sed -i '' 's|\.claude/skills/cogmerge|.cursor/skills/cogmerge|g' "$f" 2>/dev/null \
      || sed -i 's|\.claude/skills/cogmerge|.cursor/skills/cogmerge|g' "$f"
  done
  find "$out" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
}

if [ "$CHECK" = 1 ]; then
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  build "$TMP"
  X=(-x __pycache__ -x '*.pyc')
  if diff -r -q "${X[@]}" "$TMP/skills/cogmerge" .cursor/skills/cogmerge >/dev/null 2>&1 \
     && diff -r -q "${X[@]}" "$TMP/agents" .cursor/agents >/dev/null 2>&1; then
    echo "in sync: .cursor/ matches .claude/"
  else
    echo "OUT OF SYNC — .cursor/ does not match .claude/" >&2
    diff -r "${X[@]}" "$TMP/skills/cogmerge" .cursor/skills/cogmerge 2>&1 | head -20 >&2 || true
    diff -r "${X[@]}" "$TMP/agents" .cursor/agents 2>&1 | head -20 >&2 || true
    echo >&2
    echo "Fix with: bash tools/sync-cursor.sh" >&2
    exit 1
  fi
else
  build .cursor
  echo "regenerated from .claude/:"
  find .cursor/skills .cursor/agents -type f | sort | sed 's/^/  /'
fi
