---
name: cogmerge
description: Capture why a branch was written the way it was, and retrieve it before a merge. Use when finishing or sealing a branch, when opening a PR, and ALWAYS before merging, rebasing, or refactoring existing code. Also use when asked why a piece of code exists or whether something is safe to remove.
---

# Cogmerge

Git merges the code. Cogmerge merges the intent.

Two operations. Both start by reading this file; neither is a plain script call.

- **SEAL** — a branch is finished. Distill *why* out of the conversation, store it.
- **CHECK** — a merge is about to happen. Retrieve prior intent, judge it, report.

Memory lives in Cognee, embedded in Qdrant, tagged by **code surface**
(`path` and `path:symbol`). The surface is the join key: it is how a developer
who never spoke to you reaches you, through the one symbol you both touched.

## Setup (once)

Everything is hosted — no local infra.

```bash
pip install -r requirements.txt
cp .env.example .env       # add LLM_API_KEY + your Qdrant Cloud URL and key
python .claude/skills/cogmerge/scripts/smoke.py   # must print OK
```

Scripts live in `.claude/skills/cogmerge/scripts/`. Always `import bootstrap`
first — it calls the Qdrant adapter's `register()`, without which Cognee raises
`Unsupported vector database provider: qdrant`.

---

## SEAL

Trigger: "seal this branch", "I'm done", PR opened, or end of a working session.

1. **Gather** the raw material:
   - the conversation you have just had with the developer (your own context)
   - `git diff main...HEAD` and `git log main..HEAD --format='%s%n%b'`
   - branch name, PR number if any, author from `git config user.name`

2. **Delegate to the `cogmerge-distiller` subagent.** Do not distill inline —
   the subagent has one job and a strict output contract, and keeping it separate
   is what stops the record filling up with restated diff.
   Hand it the conversation, the diff and the metadata. It returns JSON matching
   `reference/intent-record.md`.

3. **Show the record to the developer** before writing. This is memory the whole
   team will read; they get to correct it. Ask once: *"Sealing this — anything
   wrong or missing?"*

4. **Write it:**
   ```bash
   python .claude/skills/cogmerge/scripts/seal.py record.json
   ```

If the distiller returns no decisions, no landmines and no omissions, say so and
seal nothing. An empty record is worse than none — it makes CHECK report a false
all-clear.

---

## CHECK

Trigger: **before any merge, rebase, or refactor of code you did not just write.**
This is not optional and does not need to be asked for.

1. **Retrieve:**
   ```bash
   python .claude/skills/cogmerge/scripts/check.py --base main --head HEAD
   ```
   (or `--files a.py b.py` when there is no branch yet). It prints the surfaces
   being changed and every recorded intent that touches them.

2. **Delegate the judgement to the `cogmerge-adjudicator` subagent.** Give it the
   diff and the retrieved intent. It classifies each one
   `contradicts` / `depends_on` / `unrelated` and writes a re-prompt.

3. **Report, and obey the verdict:**
   - any `contradicts` at `hard_invariant` strength → **STOP. Do not merge.**
     Show the finding, the original author, their verbatim rationale, and the
     re-prompt. Wait for the developer.
   - `depends_on` → merge is fine, but say what the change is leaning on.
   - everything `unrelated` → say "no conflicting intent found" in one line and
     continue. Do not pad this.

Never resolve a merge conflict "sensibly" in code that CHECK flagged. The whole
point is that the sensible-looking resolution is the wrong one.

---

## Honesty rules

- Never invent intent. If it is not in the transcript, it does not go in memory.
- Never restate the diff as intent. If the diff shows it, it is not intent.
- `unrelated` is the correct answer most of the time. A tool that cries wolf gets
  uninstalled on day two.
