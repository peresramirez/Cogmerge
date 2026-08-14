<h1 align="center">Cogmerge</h1>

<p align="center"><strong>Git merges the code. Cogmerge merges the intent.</strong></p>

<p align="center">
  <img alt="memory: Cognee" src="https://img.shields.io/badge/memory-Cognee-6D4AFF?style=flat-square">
  <img alt="vectors: Qdrant" src="https://img.shields.io/badge/vectors-Qdrant-FF4D5E?style=flat-square">
  <img alt="runtime: Claude Code" src="https://img.shields.io/badge/runtime-Claude%20Code-FFB020?style=flat-square">
  <img alt="skill + 2 subagents" src="https://img.shields.io/badge/skill-%2B%202%20subagents-6D4AFF?style=flat-square">
  <br>
  <img alt="dependencies: none" src="https://img.shields.io/badge/dependencies-none-2ECC8F?style=flat-square">
  <img alt="python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-12121A?style=flat-square">
  <img alt="status: working" src="https://img.shields.io/badge/demo-verified%20end%20to%20end-2ECC8F?style=flat-square">
  <img alt="license: MIT" src="https://img.shields.io/badge/license-MIT-12121A?style=flat-square">
</p>

<p align="center">
Cogmerge gives every merge a memory — it captures <em>why</em> developers and their
agents made the decisions they made, and warns you before a branch silently undoes them.
</p>

<p align="center"><img src="docs/workflow.svg" alt="Cogmerge workflow: SEAL captures intent from an agent conversation into Cognee and Qdrant tagged by code surface; CHECK turns an incoming diff into the same surface tags, retrieves the matching intent, and an adjudicator subagent blocks the merge on a contradiction. Both lanes meet at one shared CodeSurface node." width="100%"></p>

---

## The failure it prevents

```
Alice, PR #121   Adds debounce_webhook(). Tells her agent why:
                 "Stripe caps us at 25 req/s. I rejected a Redis queue —
                  extra failure mode, no monitoring. No test, because
                  reproducing it needs a live rate limit. Don't remove this."
                 Then she closes the terminal. The conversation is deleted.

Bob, PR #128     Asks his agent to clean up the webhook module.
                 His agent sees an untested no-op wrapper. It inlines it away.

git merge        clean. No conflict. Not even a nearby line.
CI               green. Nothing tested it, by design.
AI reviewer      "LGTM, nice simplification."
production       429s from Stripe, next Tuesday.
```

Nothing in that chain is broken. It failed because the only input that mattered was
thrown away when Alice closed her terminal.

Git indexes code by *file*. Cogmerge indexes **reasoning by code surface** — so the
moment an agent touches `src/webhooks/stripe.py:debounce_webhook`, every decision
anyone made about that exact symbol, **including the ones they decided against**, is
one hop away.

## How it works

Two operations, shown in the diagram above.

**SEAL** — when a branch is finished, the `cogmerge-distiller` subagent reads the
conversation and the diff and extracts the *negative space*: rejected alternatives,
landmines, deliberate omissions, invariants. It never restates the diff — if the
diff shows it, it is not intent. The record is stored in Cognee, tagged
`surface:path:symbol`, and embedded in Qdrant.

**CHECK** — before any merge, the diff is reduced to surfaces deterministically (no
LLM), those surfaces become a `nodeName` filter so retrieval stays scoped as the
repo grows, and `GRAPH_COMPLETION` runs over that slice. The
`cogmerge-adjudicator` subagent then rules on each record — `contradicts`,
`depends_on`, or `unrelated`. A HIGH finding blocks the merge and returns the
original author's verbatim rationale plus a paste-ready re-prompt.

**The surface tag is the join key.** Alice's record and Bob's diff meet on the one
symbol they both touched — two developers who never spoke, connected by the code.

**The agent harness is the runtime.** There is no CLI, no MCP server, no LLM SDK.
`AGENTS.md` tells any agent when to act, two subagents do the reasoning, and the
scripts only do what a subagent cannot: write to Cognee and query it back.

## Quickstart

```bash
cp .env.example .env          # add your Cognee Cloud credentials
python3 .claude/skills/cogmerge/scripts/smoke.py    # must print OK

bash demo/setup.sh            # builds two branches that merge cleanly
bash demo/run.sh              # seals Alice's intent, then checks Bob's PR
```

No dependencies on the default path — Python 3.9+ stdlib only.

## Backends

| `COGMERGE_BACKEND` | What runs | Needs |
|---|---|---|
| `cloud` (default) | Cognee Cloud REST API | `COGNEE_BASE_URL`, `COGNEE_API_KEY`, `COGNEE_TENANT_ID` |
| `qdrant` | `cognee` library writing into your own Qdrant cluster | `QDRANT_API_URL`, `QDRANT_API_KEY`, `LLM_API_KEY`, plus `pip install cognee cognee-community-vector-adapter-qdrant` |

Use `qdrant` when you want the collections visible in your own Qdrant dashboard.

## Layout

```
AGENTS.md                       the behavioural contract (CLAUDE.md points here)
.claude/agents/                 cogmerge-distiller, cogmerge-adjudicator
.claude/skills/cogmerge/
  SKILL.md                      when and how to seal / check
  reference/intent-record.md    the JSON contract the distiller emits
  scripts/backend.py            the only thing that talks to Cognee
  scripts/seal.py               write one intent record
  scripts/check.py              retrieve intent for a pending diff
  scripts/surfaces.py           git diff -> path / path:symbol
demo/                           two branches that merge cleanly and contradict
docs/                           PROBLEM, SOLUTION, PLAN
```

## Why not a markdown file

| | `DECISIONS.md` | Cogmerge |
|---|---|---|
| Retrieve by code surface | `grep` | graph traversal from a shared surface node |
| Bigger than a context window | breaks | top-k, only the relevant records load |
| Scoped by who may see what | impossible | `node_set` + Cognee datasets |
| Connects two people who never spoke | impossible | they share the surface node |
| Updated at merge time | never happens | it *is* the merge-time step |

Full reasoning in [`docs/PROBLEM.md`](docs/PROBLEM.md) and [`docs/SOLUTION.md`](docs/SOLUTION.md).
