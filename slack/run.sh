#!/usr/bin/env bash
# Start the Cogmerge Slack bot and keep it up.
#
#   bash slack/run.sh                              # this repo's COGMERGE_REPO
#   bash slack/run.sh Rouxxel/cogmerge_landing_page # override the repo
#
# Picks the right interpreter (slack_bolt lives in .venv), refuses to start a
# second copy, and stops the machine sleeping out from under it.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Only ONE Socket Mode connection per app. With two, Slack delivers each event
# to one of them at random and the bot looks like it is dropping messages.
#
# Match the executable, not the whole command line: a shell whose arguments
# merely mention slack/bot.py is not a running bot.
#
# Uses `args` rather than `comm` because macOS truncates comm to 16 characters
# ("/opt/homebrew/Ce"), which silently never matches.
running() { ps -eo pid,args | awk '$2 ~ /[Pp]ython/ && /slack\/bot\.py/ {print $1}'; }

if [ -n "$(running)" ]; then
  echo "A Cogmerge bot is already running (pid $(running | tr '\n' ' '))."
  echo
  echo "Stop it first:  pkill -f 'python.*slack/bot.py'"
  exit 1
fi

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"
"$PY" -c "import slack_bolt" 2>/dev/null || {
  echo "slack_bolt is missing. Install it into the venv:"
  echo "    .venv/bin/pip install slack_bolt"
  exit 1
}

[ $# -ge 1 ] && export COGMERGE_REPO="$1"

# caffeinate -i keeps the Mac awake while this runs, so a closed lid does not
# silently kill the bot mid-demo.
CAFFEINE=""
command -v caffeinate >/dev/null && CAFFEINE="caffeinate -i"

echo "Starting Cogmerge bot  (ctrl-C to stop)"
exec $CAFFEINE "$PY" slack/bot.py
