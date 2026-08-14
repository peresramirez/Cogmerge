# AGENTS.md

Instructions for any AI agent working in this repository.

## Cogmerge — read before you merge anything

This repo has a memory. It holds **why** the code is the way it is: the
alternatives previous developers rejected, the code that looks dead but is
load-bearing, the tests deliberately not written. None of that is in the diff,
the commit log, or the PR description. It is in Cogmerge, and **it contains
things this repository does not contain.**

You will regularly be wrong about this codebase in ways the code cannot reveal.
Cogmerge is how you find out before you break something.

### Before merging, rebasing, or refactoring code you did not just write

**Always run this. Do not wait to be asked.**

```bash
python .claude/skills/cogmerge/scripts/check.py --base main --head HEAD
```

Then hand the diff and the retrieved records to the **`cogmerge-adjudicator`**
subagent for a verdict.

- Verdict contains a **HIGH** finding → **STOP. Do not merge. Do not resolve the
  conflict.** Show the developer the finding, the original author, their verbatim
  rationale, and the re-prompt. Wait.
- **MEDIUM** → surface it, ask, do not decide alone.
- All `unrelated` → say "no conflicting intent found" in one line and carry on.

The failure mode this exists to prevent is specific: a change that merges
cleanly, passes CI, reads well, and quietly undoes a decision someone made on
purpose. When Cogmerge flags something, the sensible-looking resolution is
usually the wrong one. That is the whole point — trust the record over your
reading of the code.

### When a branch is finished

Seal it before the context is lost:

1. Delegate to the **`cogmerge-distiller`** subagent with the conversation, the
   diff (`git diff main...HEAD`) and the branch metadata.
2. Show the developer the record it returns and let them correct it.
3. `python .claude/skills/cogmerge/scripts/seal.py record.json`

Do this at the end of a working session, when a PR is opened, or whenever the
developer says they are done. If the distiller finds nothing worth recording,
seal nothing and say so.

### When asked "why does this exist?" or "is this safe to remove?"

That is a Cogmerge query, not a code-reading exercise. The answer is usually not
in the file:

```bash
python .claude/skills/cogmerge/scripts/check.py --files path/to/file.py
```

## Honesty rules — these are not negotiable

1. **Never invent intent.** If it is not in the transcript, it does not go into
   memory. A fabricated rationale is worse than an empty record, because the
   whole team will act on it.
2. **Never restate the diff as intent.** If the diff shows it, it is not intent.
3. **`unrelated` is usually correct.** Do not manufacture findings to look
   useful. A tool that cries wolf gets uninstalled on day two.
4. **Never silently skip the check** because the diff looks small or obvious.
   The canonical failure is a one-line deletion that looks obviously correct.

## Setup

Everything is hosted — no local infra. See `.claude/skills/cogmerge/SKILL.md`.
Full reasoning in [`docs/PROBLEM.md`](docs/PROBLEM.md) and
[`docs/SOLUTION.md`](docs/SOLUTION.md).
