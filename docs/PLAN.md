# PLAN.md — Implementation

> **Superseded for the hackathon by the 2-hour path.** The build shipped as a Claude Code
> **skill + two subagents + `AGENTS.md`**, not a CLI/MCP/Slack stack: the agent harness is
> the runtime, so the only code is three scripts that talk to Cognee. No MCP server, no
> Slack app, no LLM SDK, no local infra (Qdrant Cloud). See [`../AGENTS.md`](../AGENTS.md)
> and [`../.claude/skills/cogmerge/SKILL.md`](../.claude/skills/cogmerge/SKILL.md).
> Everything below stays as the full-scope design and the risk register — both still apply.

Build order is chosen so that **there is a demoable artifact at every hour mark**. If the
night ends early, you still demo. Nothing is built that the 90-second demo doesn't touch.

**Golden rule:** the demo runs on **pre-seeded memory**. You never call `cognify()` live
on stage — it's an LLM pipeline and it takes 30–90s. Seal happens before the demo; only
`cogmerge check` runs live.

---

## Phase 0 — Pre-flight (30 min, do this before anything else)

Get the two integration risks out of the way first. Both have known failure modes.

```bash
mkdir -p ~/QD && cd ~/QD
uv init && uv add "cognee>=1.5.0.dev1" --prerelease=allow
uv add cognee-community-vector-adapter-qdrant anthropic slack-bolt gitpython typer rich mcp

docker run -d -p 6333:6333 -p 6334:6334 \
  -v "$(pwd)/qdrant_storage:/qdrant/storage:z" --name qdrant qdrant/qdrant
open http://localhost:6333/dashboard   # must render
```

`.env`:
```dotenv
LLM_API_KEY=sk-...
VECTOR_DB_PROVIDER=qdrant
VECTOR_DB_URL=http://localhost:6333
VECTOR_DB_KEY=
VECTOR_DATASET_DATABASE_HANDLER=qdrant
```

**Smoke test — the one that kills hackathons.** The Qdrant adapter is a *community*
package: setting `VECTOR_DB_PROVIDER=qdrant` alone raises
`OSError: Unsupported vector database provider: qdrant`. You must **call** `register()`
in the same process, before any cognee call.

```python
# cogmerge/bootstrap.py  — imported first, everywhere
from cognee_community_vector_adapter_qdrant import register
register()                       # CALL it. Importing is not enough.
```

```python
# scripts/smoke.py
import asyncio, cognee
from cogmerge.bootstrap import register  # noqa: F401 — side effect

async def main():
    await cognee.add("The debounce wrapper enforces a 25 req/s cap.")
    await cognee.cognify()
    print(await cognee.search("what does the debounce wrapper do?"))

asyncio.run(main())
```

✅ **Gate:** collections appear in the Qdrant dashboard and the search answers.
If this doesn't pass in 30 minutes, fall back to `VECTOR_DB_PROVIDER=lancedb` to unblock
development and return to Qdrant at H+5. *(Qdrant is a sponsor — do not ship the fallback.)*

---

## H+0 → H+1 · Fixtures & the demo repo

The demo is the spec. Build it first so every later stage has real input.

```
fixtures/
  repo/                         # tiny FastAPI-ish "acme/payments-api", git-init'd
    src/webhooks/stripe.py      # contains debounce_webhook()
  transcripts/
    alice_121.jsonl             # her agent conversation — WRITE THIS BY HAND
    bob_128.jsonl               # his agent conversation
  diffs/
    bob_128.patch               # removes debounce_webhook, textually clean
```

Alice's transcript must contain, in natural conversational form, the four things the
distiller has to find and the diff cannot: the rate-limit rationale, the **rejected Redis
queue**, the **deliberate absence of a test**, and the "do not remove" invariant.

Two branches must merge **cleanly** with `git merge` and pass tests. Verify this now —
it is the entire dramatic premise.

✅ **Gate:** `git merge` clean + tests green on the fixture repo.

---

## H+1 → H+2 · Subagent #1: the Distiller

`cogmerge/distill.py` — Anthropic SDK, `claude-sonnet-5`, tool-forced structured output
against the `BranchIntent` shape in [`SOLUTION.md` §3](./SOLUTION.md).

Input bundle: transcript + `git diff` + `git diff -U0` hunk headers (for `path:symbol`) +
branch/PR/author. Prompt mandate: **never restate the diff; extract the negative space.**

```bash
cogmerge distill fixtures/transcripts/alice_121.jsonl --pretty
```

✅ **Gate:** Alice's record contains `rejected_alternatives: ["Redis queue — extra failure
mode, no monitoring"]` and a `Landmine` on `src/webhooks/stripe.py:debounce_webhook`.
Iterate the prompt until this is reliable across 3 runs. **This is the highest-leverage
hour of the night** — everything downstream is only as good as this extraction.

---

## H+2 → H+3 · Memory layer: Cognee + custom graph model + Qdrant

`cogmerge/graph.py` (the `DataPoint` models) and `cogmerge/seal.py`:

```python
await cognee.add(
    record.as_markdown(),
    dataset_name=f"cogmerge_{repo.replace('/', '_')}",
    node_set=[f"repo:{repo}", f"branch:{branch}", f"pr:{pr}", f"author:{author}",
              *[f"surface:{s}" for s in record.surfaces()]],
)
await cognee.cognify(graph_model=BranchIntent, custom_prompt=INTENT_EXTRACTION_PROMPT)
```

Two things to verify explicitly, because they are the technical claims you're making:

1. **Node merging.** Seal Alice, then Bob. Confirm in the graph that
   `src/webhooks/stripe.py:debounce_webhook` is **one** node with edges from both branches.
   That's `identity_fields=["path","symbol"]` doing its job. If you get two nodes, the
   distiller is emitting inconsistent paths — normalize to repo-relative POSIX paths
   *before* ingest.
2. **Qdrant is really being used.** Show the collections in the dashboard. Screenshot it
   for the demo.

```bash
cogmerge seal --transcript fixtures/transcripts/alice_121.jsonl --branch feat/stripe-debounce --pr 121
```

✅ **Gate:** `visualize_graph()` renders both branches converging on one surface node.
**Screenshot this. It is demo slide #1.**

---

## H+3 → H+4 · Retrieval + Subagent #2: the Adjudicator

`cogmerge/retrieve.py` — two-stage as in [`SOLUTION.md` §4](./SOLUTION.md): surfaces from the
incoming diff → `node_name` filter → `SearchType.GRAPH_COMPLETION` with a
`response_model`. Always pass `exclude_branch` or you retrieve your own intent.

`cogmerge/adjudicate.py` — Sonnet, typed `ConflictReport`. Force it to classify each retrieved
intent as `contradicts | depends_on | unrelated` **with the hunk cited**. Bias it toward
`unrelated`: a tool that cries wolf gets uninstalled on day two, and a judge will ask you
about false positives.

`cogmerge/cli.py` — `cogmerge check` with `rich` output (severity colour, source PR + author,
verbatim rationale, evidence URI, re-prompt block). Non-zero exit on HIGH.

✅ **Gate — this is the whole product:**
```bash
cogmerge check --branch refactor/webhook-cleanup --base main
# → 🔴 HIGH, cites PR #121, quotes Alice's rationale, prints the re-prompt
```
**If the night ends here, you have a demo.** Everything after this is score, not survival.

---

## H+4 → H+5 · MCP server — agents call it themselves

`cogmerge/mcp_server.py` (`mcp` SDK, stdio) exposing:
- `cogmerge_check(files: list[str], base: str)` → ConflictReport
- `cogmerge_search(query: str, surfaces: list[str])` → retrieved intents
- `cogmerge_seal(branch: str)` → seals the current branch

```bash
claude mcp add cogmerge -s project -- uv --directory ~/QD run cogmerge-mcp
```

Then the `CLAUDE.md` block from [`SOLUTION.md` §6](./SOLUTION.md), committed into the
fixture repo.

✅ **Gate — the best 20 seconds of the demo:** in the fixture repo, ask Claude Code
*"merge refactor/webhook-cleanup into main"*. It calls `cogmerge_check` **on its own**,
gets the HIGH finding, and **refuses to merge**. An agent stopping itself is far more
convincing than a CLI printing red text.

---

## H+5 → H+6 · Slack

Two paths. **Decide at H+5 based on the clock, and do not switch back.**

**Path A — Cognee's Slack integration (preferred, sponsor-aligned).**
Needs `cognee>=1.5.0.dev1` (pre-release — `pip install cognee` will NOT have
`/cognee-remember`), a public HTTPS URL, and a Slack app created from Cognee's manifest.
```bash
ngrok http 8000 --domain=<your-reserved>.ngrok-free.app   # reserve it, free tier randomizes
```
Create the app at api.slack.com/apps → From an app manifest → paste Cognee's manifest with
your ngrok host → copy Client ID / Client Secret / Signing Secret into `.env` → install →
each dev runs `/cognee-link` once. Gives you `/cognee-ask` and `/cognee-remember` for free.

**Path B — your own Bolt app (30 min, zero unknowns).** A `slack-bolt` app with one slash
command `/cogmerge why <file|pr>` calling your retrieval directly, plus `post_conflict_card()`
that `cogmerge check` calls on HIGH/MEDIUM. **Path B is what the demo actually needs** — the
auto-posted conflict card, which Path A does not provide.

**Recommendation: build Path B first (it's on the demo path), then add Path A if time
remains.** Path A alone will not produce the card that makes the story land.

The card: severity, source PR + @author, verbatim rationale, and a code block with the
re-prompt. Mention Alice so she's notified — *that* is the "developers are aware" loop.

✅ **Gate:** `cogmerge check` on Bob's branch posts a card into `#eng-payments` that @-mentions
Alice.

---

## H+6 → H+7 · Capture automation

Closes the loop from "we typed the fixtures" to "this captures itself."

1. **Claude Code `SessionEnd` hook** → `cogmerge seal --auto`. Reads the session transcript from
   `~/.claude/projects/<slug>/*.jsonl`, distills, shows the record for confirmation, seals.
   *(Cognee's own `cognee-memory` plugin hooks the same lifecycle — mention it as the
   productized path: `claude plugin marketplace add topoteretes/cognee-integrations`.)*
2. **Git `post-checkout`** → if leaving a branch unsealed, nudge.
3. **Stretch: GitHub Action** — `cogmerge check` on `pull_request`, comment on the PR.

Run one real seal on your own actual work today. **"This memory came from my real session
two hours ago"** is worth more to a judge than any fixture.

✅ **Gate:** one genuine, non-fixture intent record in Cogmerge's memory.

---

## H+7 → H+8 · Harden, rehearse, record

- `docker-compose.yml`: qdrant + cognee backend + your service. `make demo` seeds
  everything from zero in one command — **this is judging criterion #1** ("runs and is
  ready to use on Monday"). Test it by wiping `qdrant_storage/` and running it clean.
- `make reset && make seed` so you can re-run the demo repeatedly without state drift.
- README: the problem in 3 lines, the architecture diagram, `make demo`, a GIF.
- **Record the full demo as a video.** If the wifi, the LLM API, or ngrok dies at judging
  time, you play the recording and talk over it. Non-optional.
- Rehearse the 90 seconds **out loud, three times.** The two beats that must land:
  *"clean merge, green CI, AI reviewer says LGTM"* → *"and here's what it missed."*

---

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Qdrant adapter not registered → `Unsupported vector database provider` | **High** | `register()` **called** in `bootstrap.py`, imported everywhere. Settled in Phase 0. |
| Cognee Slack integration is pre-release (`1.5.0.dev1`) | **High** | Path B (own Bolt app) is on the critical path; Path A is a bonus. |
| `cognify()` too slow to run live | **High** | Pre-seed. Never cognify on stage. `make seed` beforehand. |
| Distiller invents intent not in the transcript | Medium | "Ground every item in the transcript or omit it." Judges will probe this — have the answer ready. |
| Adjudicator false positives | Medium | Bias to `unrelated`; require a cited hunk; show a clean PR returning "no findings" in the demo. |
| `EMBEDDING_DIMENSIONS` mismatch after model change | Medium | `prune.prune_system(metadata=True)` and re-seed. Don't change models mid-build. |
| Kuzu file-locking under concurrent writers | Low (demo) | Single-writer seal service. Mention Neo4j as the multi-agent production path. |
| Surface paths inconsistent → node merging fails | Medium | Normalize to repo-relative POSIX paths before ingest. Assert in a test. |
| ngrok free-tier host changes on restart | Medium | Reserve a domain: `ngrok http 8000 --domain=…`. |

## Cut lines (in order, if behind)

1. GitHub Action → cut. `cogmerge check` locally is enough.
2. Cognee Slack integration (Path A) → cut. Keep the Bolt card.
3. Claude Code `SessionEnd` hook → cut, run `cogmerge seal` manually on stage (still reads a
   real transcript, so the story is intact).
4. `cogmerge_search` MCP tool → cut. Keep `cogmerge_check` — the agent refusing to merge
   is the single best moment in the demo.

**Never cut:** the custom `DataPoint` graph model, the shared `CodeSurface` node, `cogmerge check`,
Qdrant. Those *are* the submission — depth of stack and the sponsors' technology.

## Definition of done (Monday)

- [ ] `git clone && cp .env.example .env && make demo` works on a clean machine.
- [ ] Qdrant dashboard shows populated collections. Screenshot in the README.
- [ ] `visualize_graph` output shows two branches converging on one `CodeSurface` node.
- [ ] `cogmerge check` prints the HIGH finding with Alice's verbatim rationale + re-prompt.
- [ ] Claude Code refuses the merge on its own via MCP.
- [ ] Slack card posts to a real workspace, @-mentioning the other developer.
- [ ] At least one intent record distilled from a **real** session, not a fixture.
- [ ] 90-second demo video recorded as the offline fallback.
- [ ] README states the problem in three lines above the fold.
