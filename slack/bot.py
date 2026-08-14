"""Cogmerge in Slack — ask why the code is the way it is.

    python3 slack/bot.py

Socket Mode, so there is no public URL, no ngrok tunnel and no request URLs that
go stale when your laptop changes network. The bot dials out to Slack.

    /cogmerge src/webhooks/stripe.py
    /cogmerge why do we debounce the stripe webhook?
    /cogmerge is debounce_webhook safe to remove?

Answers come from the same scoped retrieval `check.py` uses, so a question about
a file is filtered to that file's node_set rather than semantically guessed at.
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".claude/skills/cogmerge/scripts"))
import backend  # noqa: E402

try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
except ImportError:
    raise SystemExit(
        "The Slack bot needs slack_bolt (the only part of Cogmerge that has a\n"
        "dependency):\n\n    pip install slack_bolt\n"
    )

# A token that looks like a path or a dotted symbol — used to decide whether we
# can scope the query instead of searching the whole repo's memory.
_PATHISH = re.compile(r"[\w./-]+\.(?:py|ts|tsx|js|jsx|go|rs|rb|java|kt|sql|ya?ml)(?::\w+)?")
_SYMBOL = re.compile(r"\b([a-z_][a-z0-9_]{3,})\b")


def scope_for(text: str) -> list[str] | None:
    """Turn a question into node_set tags, or None to search unscoped."""
    surfaces = _PATHISH.findall(text)
    if not surfaces:
        return None
    tags = [f"surface:{s}" for s in surfaces]
    # A path also matches records tagged at symbol level under it, and vice
    # versa, so include the bare file for path:symbol queries.
    tags += [f"surface:{s.split(':')[0]}" for s in surfaces if ":" in s]
    return sorted(set(tags)) + [f"repo:{backend.REPO}"]


# Slack's mrkdwn is NOT Markdown. Bold is *one* asterisk, there are no headings
# and no tables. An LLM writing normal Markdown renders as literal **asterisks**,
# so we ask for Slack syntax AND convert deterministically -- the prompt is a
# preference, this is the guarantee.
SLACK_STYLE = (
    "Answer using Slack mrkdwn, never Markdown. Bold is *single asterisks*. "
    "Italic is _underscores_. Code is `backticks`. There are NO headings and NO "
    "tables — never emit #, ##, ** or a | table. Use short lines and • bullets. "
    "Answer from the recorded intent only: quote the rationale and any rejected "
    "alternatives verbatim, then finish with ONE source line in the form "
    "`— alice · feat/stripe-debounce · PR #121`. Do not repeat the source after "
    "every point. If nothing was recorded, say so plainly instead of reasoning "
    "from the code."
)

_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_HEAD = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
_BULLET = re.compile(r"^(\s*)[-*]\s+")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]{5,}\|?\s*$")


def to_mrkdwn(text: str) -> str:
    """Markdown -> Slack mrkdwn. Line-based: cross-line regex eats newlines."""
    text = _BOLD.sub(r"*\1*", text)  # **bold** -> *bold*, safe across lines

    out = []
    for line in text.splitlines():
        if _TABLE_SEP.match(line):
            continue  # |---|---| separator row
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            line = "• " + " · ".join(c for c in cells if c)
        else:
            line = _HEAD.sub(r"*\1*", line)
            line = _BULLET.sub(r"\1• ", line)
        out.append(line)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def answer(question: str) -> str:
    if not question.strip():
        return (
            "Ask me about a file, a symbol, or just ask why.\n"
            "• `/cogmerge src/webhooks/stripe.py`\n"
            "• `/cogmerge why do we debounce the stripe webhook?`"
        )

    be = backend.get()
    tags = scope_for(question)
    results = be.search(question, tags, system_prompt=SLACK_STYLE)
    if not results and tags:
        # a scoped miss must not read as "nothing known"
        results = be.search(question, None, system_prompt=SLACK_STYLE)

    if not results:
        return (
            f":grey_question: Nothing recorded about that in *{backend.REPO}* yet.\n"
            "_Intent gets captured when someone seals a branch — this answers from "
            "what the team has recorded, not from reading the code._"
        )
    return to_mrkdwn("\n\n".join(str(r) for r in results))


app = App(token=os.environ["SLACK_BOT_TOKEN"])


@app.command("/cogmerge")
def slash(ack, command, respond):
    ack()  # Slack demands an ack inside 3s; retrieval takes longer than that.
    question = command.get("text", "")

    # in_channel: everyone sees the question and the answer. The team learning
    # why together is the point -- an ephemeral reply teaches one person.
    respond(
        response_type="in_channel",
        text=f"<@{command['user_id']}> asked: _{question}_\n:hourglass_flowing_sand: searching the team's memory…",
    )
    respond(response_type="in_channel", replace_original=True, text=answer(question))


@app.event("app_mention")
def mention(event, say):
    text = re.sub(r"<@[^>]+>", "", event.get("text", "")).strip()
    say(text=answer(text), thread_ts=event.get("thread_ts") or event.get("ts"))


if __name__ == "__main__":
    for var in ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"):
        if not os.getenv(var):
            raise SystemExit(f"{var} missing from .env — see slack/README.md")

    backend.banner()
    print(f"Cogmerge Slack bot up. Ask with /cogmerge in any channel.")
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
