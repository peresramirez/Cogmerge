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


def answer(question: str) -> str:
    if not question.strip():
        return (
            "Ask me about a file, a symbol, or just ask why.\n"
            "• `/cogmerge src/webhooks/stripe.py`\n"
            "• `/cogmerge why do we debounce the stripe webhook?`"
        )

    prompt = (
        f"{question}\n\n"
        "Answer from the recorded intent only. Quote the rationale and any "
        "rejected alternatives verbatim, and always name the branch, PR and "
        "author each point came from. If nothing was recorded about this, say "
        "so plainly rather than reasoning from the code."
    )

    be = backend.get()
    tags = scope_for(question)
    results = be.search(prompt, tags)
    if not results and tags:
        results = be.search(prompt, None)  # scoped miss must not read as "nothing known"

    if not results:
        return (
            f":grey_question: Nothing recorded about that in *{backend.REPO}* yet.\n"
            "_Intent gets captured when someone seals a branch — this answers from "
            "what the team has recorded, not from reading the code._"
        )
    return "\n\n".join(str(r) for r in results)


app = App(token=os.environ["SLACK_BOT_TOKEN"])


@app.command("/cogmerge")
def slash(ack, command, respond):
    ack()  # Slack demands an ack inside 3s; retrieval takes longer than that.
    respond(
        response_type="ephemeral",
        text=f":hourglass_flowing_sand: Looking up _{command.get('text', '')}_ …",
    )
    respond(response_type="ephemeral", replace_original=True, text=answer(command.get("text", "")))


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
