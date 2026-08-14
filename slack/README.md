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

**1. Create the app** — [api.slack.com/apps](https://api.slack.com/apps) →
**Create New App** → **From an app manifest** → pick your workspace → **Next** →
switch the tab to **YAML**, paste all of [`manifest.yaml`](./manifest.yaml) →
**Next** → **Create**.

**2. Generate the app-level token** — **Basic Information** → *App-Level Tokens*
→ **Generate Token and Scopes**. Name it anything, add the **`connections:write`**
scope, Generate, copy the **`xapp-…`** value. Socket Mode will not connect
without this scope.

**3. Install, and get the bot token** — **Install App** → *Install to Workspace* →
**Allow** → copy the **Bot User OAuth Token** (**`xoxb-…`**).

**4. Add both to `.env`**

```dotenv
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
```

**5. Run it**

```bash
pip install slack_bolt
bash slack/run.sh                                  # uses COGMERGE_REPO from .env
bash slack/run.sh your-org/your-repo               # or answer about another repo
```

`run.sh` picks the right interpreter, refuses to start a second copy, and keeps
the machine awake while it runs.

## Keeping it running

The bot is a foreground process, not a service. It answers only while it is up.

| How | Command | Survives |
|---|---|---|
| A spare terminal tab | `bash slack/run.sh` | until you close the tab |
| Detached | `nohup bash slack/run.sh > /tmp/cogmerge-bot.log 2>&1 &` | closing the terminal, not a reboot |
| Always-on box | same, on a server someone else keeps up | everything |

`run.sh` wraps the process in `caffeinate -i` on macOS, so a closed lid or an
idle screen will not kill it mid-demo. It does **not** survive a reboot — for
that, run it somewhere that stays up.

 
**Never run two copies.** Slack allows multiple Socket Mode connections for one
app but delivers each event to only one of them, at random — so a second bot
looks exactly like the first one dropping messages intermittently. `run.sh`
refuses to start if one is already running; stop it with:

```bash
pkill -f 'python.*slack/bot.py'
```

## One bot answers about one repo

The bot answers from `COGMERGE_REPO`. Ask it about a repo it is not scoped to
and it will correctly say nothing is recorded. To cover two projects, run two
copies **with different Slack apps** — or restart it pointed at the other repo.

**6. Use it** — `/cogmerge <anything>` works in any channel right away. For
`@Cogmerge` mentions, invite the bot to that channel first: `/invite @Cogmerge`.

## Adding your team

Workspace name (top left) → **Invite people to \<workspace\>**. For a quick
setup, enable the **shareable invite link** in that dialog so people can join
themselves.

Slack's **guest** accounts (single- and multi-channel) are **paid-plan only** —
on the free plan everyone you invite is a full member with access to every public
channel. Fine for a team or a demo; just don't plan to scope anyone's visibility
that way.

### You need fewer people than you think

The developers whose decisions Cogmerge answers with **live in the memory, not in
Slack**. Ask `/cogmerge why do we debounce the stripe webhook?` and the answer
comes back attributed to `alice`, branch `feat/stripe-debounce`, PR #121 —
whether or not Alice is in the workspace, still on the team, or reachable.

That is the point. One account is enough to see it work: you ask, and the answer
comes from someone who isn't there.

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
