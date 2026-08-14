#!/usr/bin/env bash
# Install Cogmerge into the current repository.
#
#   curl -fsSL https://raw.githubusercontent.com/peresramirez/Cogmerge/main/install.sh | bash
#
# Options (pass after `| bash -s --`):
#   --claude        only the Claude Code tree (.claude/)
#   --cursor        only the Cursor tree (.cursor/)
#   --codex         only the Codex tree (.agents/ — Cursor reads this too)
#   --all           all three (default)
#   --dir <path>    target repo (default: current directory)
#
# Installs nothing you have to run: no daemon, no MCP server, no dependencies.
# Uninstall is `rm -rf .claude/skills/cogmerge .cursor/skills/cogmerge`.
set -euo pipefail

REPO_TARBALL="https://codeload.github.com/peresramirez/Cogmerge/tar.gz/refs/heads/main"
TARGET="$PWD"
WANT="all"

while [ $# -gt 0 ]; do
  case "$1" in
    --claude) WANT="claude"; shift ;;
    --cursor) WANT="cursor"; shift ;;
    --codex)  WANT="codex";  shift ;;
    --all|--both) WANT="all"; shift ;;
    --dir)    TARGET="$2";   shift 2 ;;
    -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

say()  { printf '  %s\n' "$*"; }
warn() { printf '  !! %s\n' "$*" >&2; }

[ -d "$TARGET" ] || { echo "no such directory: $TARGET" >&2; exit 1; }
cd "$TARGET"
git rev-parse --git-dir >/dev/null 2>&1 || warn "not a git repository — Cogmerge keys memory to branches and diffs, so it needs one"

command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

printf '\nCogmerge — installing into %s\n\n' "$TARGET"

# COGMERGE_SRC lets you install from a local checkout instead of downloading —
# used by the test suite, and handy on a locked-down network.
if [ -n "${COGMERGE_SRC:-}" ]; then
  SRC="$COGMERGE_SRC"
  say "installing from local source: $SRC"
else
  curl -fsSL "$REPO_TARBALL" | tar xz -C "$TMP" --strip-components=1
  SRC="$TMP"
fi

# ---- agent trees -----------------------------------------------------------
if [ "$WANT" = "claude" ] || [ "$WANT" = "all" ]; then
  mkdir -p .claude/skills .claude/agents
  cp -R "$SRC/.claude/skills/cogmerge" .claude/skills/
  cp "$SRC"/.claude/agents/cogmerge-*.md .claude/agents/
  find .claude/skills/cogmerge -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
  say "installed .claude/skills/cogmerge and .claude/agents/  (Claude Code)"
fi

if [ "$WANT" = "cursor" ] || [ "$WANT" = "all" ]; then
  mkdir -p .cursor/skills .cursor/agents .cursor/rules
  cp -R "$SRC/.cursor/skills/cogmerge" .cursor/skills/
  cp "$SRC"/.cursor/agents/cogmerge-*.md .cursor/agents/
  cp "$SRC/.cursor/rules/cogmerge.mdc" .cursor/rules/
  find .cursor/skills/cogmerge -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
  say "installed .cursor/skills, .cursor/agents and .cursor/rules  (Cursor)"
fi

if [ "$WANT" = "codex" ] || [ "$WANT" = "all" ]; then
  # Codex scans $REPO_ROOT/.agents/skills. Cursor reads it too, so this one
  # directory covers both -- .codex/skills is NOT a Codex path.
  mkdir -p .agents/skills .agents/agents
  cp -R "$SRC/.agents/skills/cogmerge" .agents/skills/
  cp "$SRC"/.agents/agents/cogmerge-*.md .agents/agents/
  find .agents/skills/cogmerge -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
  say "installed .agents/skills and .agents/agents  (Codex, also read by Cursor)"
fi

# ---- shared contract -------------------------------------------------------
if [ -f AGENTS.md ] && ! grep -q "Cogmerge" AGENTS.md 2>/dev/null; then
  printf '\n' >> AGENTS.md
  cat "$SRC/AGENTS.md" >> AGENTS.md
  say "appended the Cogmerge section to your existing AGENTS.md"
elif [ ! -f AGENTS.md ]; then
  cp "$SRC/AGENTS.md" AGENTS.md
  say "created AGENTS.md"
else
  say "AGENTS.md already mentions Cogmerge — left alone"
fi

if [ "$WANT" != "cursor" ]; then
  if [ ! -f CLAUDE.md ]; then
    echo '@AGENTS.md' > CLAUDE.md
    say "created CLAUDE.md -> @AGENTS.md"
  elif ! grep -q "AGENTS.md" CLAUDE.md; then
    printf '\n@AGENTS.md\n' >> CLAUDE.md
    say "pointed your CLAUDE.md at AGENTS.md"
  fi
fi

# ---- config ----------------------------------------------------------------
[ -f .env.example ] || { cp "$SRC/.env.example" .env.example; say "created .env.example"; }

if [ -f .gitignore ] && ! grep -qx '.env' .gitignore; then
  printf '\n# Cogmerge credentials\n.env\n__pycache__/\n*.pyc\n' >> .gitignore
  say "added .env to .gitignore"
elif [ ! -f .gitignore ]; then
  printf '.env\n__pycache__/\n*.pyc\n' > .gitignore
  say "created .gitignore with .env"
fi

SKILLROOT=".claude"
[ "$WANT" = "cursor" ] && SKILLROOT=".cursor"
[ "$WANT" = "codex" ]  && SKILLROOT=".agents"

cat <<EOF

Installed. Two steps left:

  1. cp .env.example .env      and add your Cognee credentials
  2. python3 $SKILLROOT/skills/cogmerge/scripts/smoke.py

Then just work normally — your agent reads AGENTS.md and checks before it merges.

Using your own Qdrant cluster? Set COGMERGE_BACKEND=qdrant, then run
  python3 $SKILLROOT/skills/cogmerge/scripts/init_qdrant.py
once after your first seal, or every scoped lookup silently returns "nothing found".

EOF
