# SOLUTION.md — Cogmerge

> Capture *why* while the developer is still explaining it. Structure it as a graph keyed
> by code surface. Retrieve it automatically at merge time, into the agent.

**Stack:** Cognee (memory engine + graph) · Qdrant (vector store) · Claude subagents
(distiller + adjudicator) · MCP (agent-facing) · Slack (human-facing) · Git hooks (trigger)

---

## 0. The name, and how to describe it

**Cogmerge** does triple duty, and every reading is true:

- **Cog**nee — the memory engine underneath.
- **Cog**nition — the merge finally *knows* something. Merge awareness.
- **Cog**, a gear tooth — two gears only mesh if their teeth line up. Two branches can
  merge cleanly in Git and still fail to mesh in intent.

**Tagline (primary):**
> **Git merges the code. Cogmerge merges the intent.**

Alternates, by mood: *"Merge with awareness."* · *"Git is merge-capable. Cogmerge is
merge-aware."* · *"Clean merge ≠ correct merge."* · *"Your branches merged. Did their
reasoning?"*

**One-liner (README subtitle, Devpost tagline, Slack app description):**
> Cogmerge gives every merge a memory — it captures *why* developers and their agents made
> the decisions they made, and warns you before a branch silently undoes them.

**Short description (~55 words — the elevator, the submission blurb):**
> Cogmerge is merge-time memory for teams building with AI agents. When a developer
> finishes a branch, a subagent distills the *why* out of their agent conversation — the
> rejected alternatives, the deliberate omissions, the code that looks dead but isn't — and
> stores it in a Cognee knowledge graph on Qdrant, keyed to the exact files and symbols.
> Before the next merge, Cogmerge retrieves it and blocks changes that silently contradict it.

**Spoken pitch (~40 seconds, three beats — this is what you say to a judge):**
> 1. *"Every developer's agent conversation is deleted when they close the terminal. That
>    conversation held the only record of **why** — the alternatives they rejected, the
>    thing that looks like dead code but is actually a rate limit."*
> 2. *"So when a teammate's agent touches that code three days later, it infers intent from
>    syntax and gets it wrong. Clean merge. Green CI. AI reviewer says LGTM. Production
>    breaks Tuesday."*
> 3. *"Cogmerge captures the why at branch-end, stores it in a graph keyed by code symbol,
>    and hands it back to the merging agent. Two developers who never spoke get connected
>    through the one node they both touched — and the agent refuses the merge."*

**The category, in one sentence** (useful when someone asks "so what is it, a linter?"):
> Git is *merge-capable* — it can combine two texts. Cogmerge is *merge-aware* — it knows
> what the two texts were **for**.

---

## 1. One-line thesis

Git indexes code by *file*. Cogmerge indexes **reasoning by code surface**, so that
the moment an agent touches `src/webhooks/stripe.ts:debounceWebhook`, every decision anyone
has ever made about that exact symbol — including the ones they decided *against* — is
retrievable in one hop.

The unit of memory is not a document. It is an **Intent Record**, and the join key between
two developers who never spoke to each other is a **CodeSurface node** they both touched.

## 2. The pipeline

```
┌─ CAPTURE ─────────────────────────────────────────────────────────────────────┐
│  Claude Code SessionEnd hook  ──┐                                             │
│  `cogmerge seal` (manual / git hook)  ├──▶  raw bundle:                             │
│  Slack: /cognee-remember, ⋯     │       · agent transcript (jsonl)            │
│  GitHub: PR opened webhook    ──┘       · git diff + hunk symbols             │
│                                          · branch / PR / author metadata      │
└───────────────────────────────────────────────┬───────────────────────────────┘
                                                ▼
┌─ DISTILL (subagent #1: Claude Sonnet) ────────────────────────────────────────┐
│  Reads the raw bundle. Emits a typed IntentRecord.                            │
│  Mandate: extract the NEGATIVE SPACE — rejected alternatives, deliberate       │
│  omissions, load-bearing weirdness, invariants, confidence, expiry.           │
│  Never restates the diff. If the diff says it, it is not intent.              │
└───────────────────────────────────────────────┬───────────────────────────────┘
                                                ▼
┌─ REMEMBER (Cognee → Qdrant) ──────────────────────────────────────────────────┐
│  cognee.add(record, node_set=[repo:…, branch:…, pr:…, author:…, surface:…])   │
│  cognee.cognify(graph_model=BranchIntent, custom_prompt=INTENT_PROMPT)        │
│                                                                               │
│  CodeSurface nodes use identity_fields=["path","symbol"]  ← THE WHOLE TRICK.  │
│  Alice's node and Bob's node for the same symbol are ONE node. The graph      │
│  links two developers who never met, through the code they both touched.      │
│  Embeddings + payload land in Qdrant; graph edges in Kuzu.                    │
└───────────────────────────────────────────────┬───────────────────────────────┘
                                                ▼
┌─ RETRIEVE (pre-merge, two-stage) ─────────────────────────────────────────────┐
│  Stage 1 — deterministic: incoming diff ▶ surface list ▶ node_set filter      │
│            (Qdrant payload filter: search only intents on THESE symbols)      │
│  Stage 2 — semantic + graph: SearchType.GRAPH_COMPLETION, response_model=…    │
│            1-hop traversal off each surface → every decision that touches it  │
└───────────────────────────────────────────────┬───────────────────────────────┘
                                                ▼
┌─ ADJUDICATE (subagent #2: Claude Sonnet) ─────────────────────────────────────┐
│  Input: incoming hunks + retrieved intent. Output: typed ConflictReport.      │
│  Not "is there a conflict in the text" — "does this change CONTRADICT a       │
│  stated intent, and with what evidence?"  Emits a paste-ready RE-PROMPT.      │
└───────────────────────────────────────────────┬───────────────────────────────┘
                                                ▼
┌─ DELIVER ─────────────────────────────────────────────────────────────────────┐
│  → agents:  MCP tool  cogmerge_check()  (Claude Code, Cursor, …)          │
│  → humans:  Slack card in the PR thread, with Copy-re-prompt block            │
│  → CI:      `cogmerge check --exit-code` in the PR job / pre-merge-commit hook      │
└───────────────────────────────────────────────────────────────────────────────┘
```

## 3. The data model (this is the depth of the stack)

A generic `cognee.add(text)` would give us RAG over conversation logs. That is not enough
to detect a semantic conflict. We define a **custom Cognee graph model** so extraction is
constrained *before* the LLM runs, and so nodes **merge deterministically across branches**.

```python
# cogmerge/graph.py
from typing import List, Literal, Optional
from cognee.low_level import DataPoint

class CodeSurface(DataPoint):
    """A file or symbol. The join key between isolated developers."""
    path: str                      # "src/webhooks/stripe.ts"
    symbol: Optional[str] = None   # "debounceWebhook"
    metadata: dict = {
        "index_fields":    ["path", "symbol"],
        # identity_fields ⇒ deterministic node id ⇒ Alice's node IS Bob's node.
        "identity_fields": ["path", "symbol"],
    }

class Decision(DataPoint):
    statement: str                          # what was decided
    rationale: str                          # WHY — the part Git never stores
    rejected_alternatives: List[str] = []   # the negative space
    strength: Literal["hard_invariant", "strong_preference", "exploratory"]
    expires_when: Optional[str] = None      # "when we move to Stripe API v4"
    touches: List[CodeSurface] = []
    metadata: dict = {"index_fields": ["statement", "rationale"]}

class Landmine(DataPoint):
    """Looks removable. Is not. The #1 source of agent-caused regressions."""
    description: str
    why_it_looks_wrong: str
    what_breaks_if_removed: str
    touches: List[CodeSurface] = []
    metadata: dict = {"index_fields": ["description", "what_breaks_if_removed"]}

class DeliberateOmission(DataPoint):
    what_was_not_done: str
    why_not: str
    metadata: dict = {"index_fields": ["what_was_not_done", "why_not"]}

class BranchIntent(DataPoint):          # ← passed as graph_model=
    repo: str
    branch: str
    pr: Optional[int] = None
    author: str
    goal: str
    decisions: List[Decision] = []
    landmines: List[Landmine] = []
    omissions: List[DeliberateOmission] = []
    open_questions: List[str] = []
    metadata: dict = {
        "index_fields":    ["goal"],
        "identity_fields": ["repo", "branch"],
    }
```

The resulting graph:

```
 (Alice) ──authored──▶ [BranchIntent feat/stripe-debounce  PR#121]
                              │ landmines
                              ▼
                       [Landmine "wrapper is load-bearing"]
                              │ touches
                              ▼
                  ╔═══════════════════════════════════════╗
                  ║ CodeSurface                           ║   ← ONE shared node.
                  ║ src/webhooks/stripe.ts:debounceWebhook║      This edge is the
                  ╚═══════════════════════════════════════╝      product.
                              ▲ touches
                              │
                       [Decision "inline it, it's dead"]
                              ▲ decisions
 (Bob) ──authored──▶ [BranchIntent refactor/webhook-cleanup PR#128]
```

Two developers. Two isolated agents. Zero communication. **One shared node** — and a
1-hop traversal that surfaces the contradiction.

## 4. Retrieval: why two stages

Cheap deterministic filtering first, expensive reasoning second.

```python
# cogmerge/retrieve.py
import cognee
from cognee import SearchType

async def intents_touching(surfaces: list[str], repo: str, exclude_branch: str):
    # Stage 1 — Qdrant payload filter. Search only the slice of memory that
    # touches these exact symbols. Sub-100ms, no LLM, scales past the repo.
    node_sets = [f"surface:{s}" for s in surfaces] + [f"repo:{repo}"]

    # Stage 2 — semantic seeds + 1-hop graph traversal + structured completion.
    return await cognee.search(
        query_text=(
            f"What decisions, invariants, landmines or deliberate omissions exist "
            f"for: {', '.join(surfaces)}? Exclude branch {exclude_branch}."
        ),
        query_type=SearchType.GRAPH_COMPLETION,
        node_name=node_sets,
        node_name_filter_operator="OR",
        response_model=RetrievedIntent,   # structured, not prose
        top_k=12,
    )
```

`node_set` is written at ingest (`cognee.add(..., node_set=[...])`) and filtered at query
time via `node_name` — this is the Qdrant-level scoping that makes the whole thing viable
on a real repo instead of a demo repo. It is also the **permission boundary**: scope by
`repo:`, `team:`, or `visibility:` and a developer only ever retrieves intent they are
allowed to see. (The hackathon's own framing: *scoped by who is allowed to see what.*)

## 5. The two subagents

**#1 Distiller** — runs at branch-seal. Sonnet. System prompt in one line:

> You are extracting what Git cannot store. Never restate the diff. If a fact is visible
> in the diff, it is not intent. Extract only: decisions with their rationale, alternatives
> the developer *rejected*, things that look wrong but are load-bearing, things deliberately
> left undone, and invariants with their blast radius. Attach every item to concrete
> `path:symbol` surfaces. Output nothing you cannot ground in the transcript.

**#2 Adjudicator** — runs at pre-merge. Sonnet. Input: incoming hunks + retrieved intent.

> For each retrieved intent, decide: does this change **contradict** it, **depend on** it,
> or is it **unrelated**? Unrelated is the correct answer most of the time — say so.
> For contradictions, cite the exact hunk and the exact stated rationale, and write a
> re-prompt the developer can paste directly into their coding agent.

Output is a typed `ConflictReport` (severity, evidence, source PR, re-prompt), not prose —
so the CLI, the MCP tool, the Slack card and the CI gate all render the same object.

## 6. Surfaces — how it actually reaches people

| Surface | Trigger | Who it serves |
|---|---|---|
| `cogmerge seal` | Claude Code `SessionEnd` hook, or manual, or on PR open | capture, invisible |
| `cogmerge check` | `pre-merge-commit` / `pre-rebase` git hook; CI job on PR | the merger |
| **MCP `cogmerge_check`** | the agent calls it itself, before resolving a merge | **the agent** |
| **MCP `cogmerge_search`** | agent asks "why does this exist?" mid-task | the agent |
| **Slack `/cogmerge why <file\|pr>`** | human curiosity | the team |
| **Slack conflict card** | posted to the PR thread automatically on 🔴/🟠 | the team |

And the line that makes every agent on the team compliant — dropped into `CLAUDE.md`:

```markdown
## Before any merge, rebase, or refactor of existing code
Call `cogmerge_check` (MCP: cogmerge) with the files you are about to change.
If it returns any finding of severity HIGH, STOP. Do not resolve the merge.
Surface the finding and its re-prompt to the user and wait.
Cogmerge knows things this repository does not contain.
```

## 7. The demo (90 seconds, rehearsed, pre-seeded)

Repo: `acme/payments-api`. Two branches, already sealed into Cogmerge.

1. **Show the graph.** Cognee's `visualize_graph` — two branches, two authors, converging
   on one `CodeSurface` node. *"They never spoke. The graph connected them."*
2. **Merge Bob's PR the normal way.** `git merge` → clean. `pytest` → green.
   Ask a plain agent to review → *"LGTM, nice simplification."* **This is the money shot:
   every existing tool says yes.**
3. **Run `cogmerge check`.**
   ```
   🔴 HIGH — Contradicts a hard invariant from PR #121 (@alice, 3 days ago)

     You remove:  debounceWebhook()  → src/webhooks/stripe.ts:41
     She wrote:   "Stripe caps this endpoint at 25 req/s. Wrapper is NOT dead —
                   it is the rate limit. I rejected the Redis queue on purpose:
                   extra failure mode, no monitoring. No test covers it because
                   reproducing it needs a live rate limit."
     Strength:    hard_invariant · no expiry
     Evidence:    cogmerge://acme/payments-api/feat-stripe-debounce#landmine-1

     ▸ Re-prompt for your agent:
       "debounceWebhook is load-bearing: it enforces Stripe's 25 req/s cap.
        Restore it, add the comment explaining why, and do not replace it with
        a queue — that alternative was explicitly rejected in PR #121."
   ```
4. **Slack card lands in the PR thread.** Alice sees it, thumbs up. Bob pastes the
   re-prompt into Claude Code. The agent restores the wrapper — **with the reasoning
   attached this time**, which the seal then feeds back into Cogmerge.

Closing line: *"Git merged it. CI passed it. The AI reviewer approved it. The only thing
that caught it was memory of a conversation that used to be deleted."*

## 8. Why Cognee + Qdrant specifically (not a folder of markdown)

| Requirement | Markdown file | Cogmerge |
|---|---|---|
| Retrieve by code surface | `grep` | graph traversal off a shared `CodeSurface` node |
| Bigger than a context window | breaks | top-k retrieval, only the 3 relevant intents load |
| Scoped by who may see what | impossible | `node_set` + Cognee multi-user datasets |
| Connect two people who never spoke | impossible | deterministic node identity merges their nodes |
| Updated at merge time | never happens | it *is* the merge-time step |
| Contradiction detection | none | adjudicator over retrieved graph context |

Qdrant does the fast scoped ANN over `surface:`/`repo:`/`author:` payload filters; Cognee
does ingestion, the typed graph, and the hybrid graph+vector retrieval. Neither alone is
sufficient: vector search alone can't express "same symbol, different branch, contradicting
strength", and a graph alone can't match "debounce wrapper" to "rate limiter" semantically.

## 9. Scoring against the judging criteria

| Criterion | How we hit it |
|---|---|
| **Runs & ready Monday (5)** | `docker compose up` + `cogmerge seal` / `cogmerge check` + MCP + Slack app. Seeded demo repo, rehearsed script, recorded fallback. |
| **Depth, not breadth (0–5)** | One problem, all the way down: custom `DataPoint` graph model, `identity_fields` node merging, `node_set`→Qdrant payload filtering, two-stage retrieval, structured `response_model` output. Not `cognee.add(text)`. |
| **Complexity (0–5)** | 2 Claude subagents (distiller, adjudicator) + custom MCP server + Claude Code lifecycle hook + git hooks + Slack app + Qdrant community adapter + Cognee custom graph. |
| **Novel application (0–5)** | Not another "chat with your docs" bot. Memory targeted at a failure mode that only exists *because* agents write code — and that no tool in the pipeline currently detects. |

## 10. Non-goals (say these out loud before a judge asks)

- Not a merge-conflict resolver. It **blocks and explains**; humans and their agents fix.
- Not a linter or a test replacement. It catches exactly what those two structurally cannot.
- Not automatic surveillance of every keystroke — sealing is explicit and reviewable, and
  the developer sees the distilled record before it is stored.
- Not a replacement for `CLAUDE.md` — it is what `CLAUDE.md` should have been once memory
  outgrew a file.
