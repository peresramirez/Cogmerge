# Cogmerge in Slack

Ask why the code is the way it is, without DMing three people.

```
/cogmerge src/webhooks/stripe.py
/cogmerge why do we debounce the stripe webhook?
/cogmerge is debounce_webhook safe to remove?
```

The bot answers from your team's recorded decisions — verbatim rationale,
rejected alternatives, and who decided it — using the same scoped retrieval
`check.py` uses. Ask about a file and the query is filtered to that file's
`node_set` rather than semantically guessed at.

## Why not Cognee's own Slack integration

[Cognee ships one](https://docs.cognee.ai/integrations/slack-integration), and it
is the right choice for some teams — but not here:

- It is **for self-hosted Cognee**. Its own docs call it "a separate app from the
  cloud/SaaS Slack integration… do not point one at the other's server." A Cognee
  Cloud tenant exposes **no Slack endpoints** — verify with
  `curl $COGNEE_BASE_URL/openapi.json | grep -i slack`.
- It needs `cognee>=1.5.0.dev1`, a pre-release. `pip install cognee` does not
  have it.
- `/cognee-ask` is a generic memory query. It does not apply Cogmerge's
  `surface:path:symbol` scoping, so you lose the precision and the branch / PR /
  author attribution that make an answer worth trusting.

If you self-host Cognee and want general team memory in Slack, use theirs. If you
want to ask about *code decisions* against Cognee Cloud, use this.

## Setup

**1. Create the Slack app** — [api.slack.com/apps](https://api.slack.com/apps) →
**Create New App** → **From an app manifest** → pick your workspace → paste
[`manifest.yaml`](./manifest.yaml) → Create.

**2. Get two tokens**

| Token | Where | Starts with |
|---|---|---|
| App-level token | **Basic Information** → *App-Level Tokens* → Generate, scope `connections:write` | `xapp-` |
| Bot token | **OAuth & Permissions** → *Install to Workspace* → copy Bot User OAuth Token | `xoxb-` |

**3. Add them to `.env`**

```dotenv
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
```

**4. Run it**

```bash
pip install slack_bolt
python3 slack/bot.py
```

Then `/cogmerge <anything>` in any channel, or `@Cogmerge` in a thread.

## Socket Mode, on purpose

This uses Socket Mode — the bot dials out to Slack over a WebSocket — so there is
**no public URL, no ngrok, and no request URLs to re-paste** when your laptop
changes network or a free tunnel rotates its hostname. It runs from a laptop
behind NAT.

The tradeoff: something has to keep the process running. For a team, run it
anywhere that stays up. Socket Mode is also the only part of Cogmerge with a
dependency (`slack_bolt`) — everything else is stdlib.

## What it does not do

It **reads** memory; it does not write it. Sealing intent stays in the editor,
where the conversation and the diff actually are — that is the moment of highest
fidelity, and a Slack message is a poor substitute for it.
