# PROBLEM.md — Intent dies at the branch boundary

> **Cogmerge** — Git remembers *what* changed. It has never remembered *why*.
> Now that agents write the code, forgetting the *why* is no longer a documentation
> problem. It is a correctness problem.

---

## 1. The setup

A team of 5 developers ships with AI agents. Each developer:

1. Opens a branch.
2. Spends 40–90 minutes in a rich conversation with their agent — Claude Code, Cursor,
   whatever. In that conversation they make **real engineering decisions**: they reject
   approaches, they discover constraints, they deliberately leave things undone, they
   explain to the agent *why* a piece of code must stay exactly as it is.
3. Squashes it into `fix: handle webhook retries (#128)`.
4. Opens a PR whose description was generated from the diff.
5. Closes the terminal. **The conversation is deleted.**

Five developers. Five isolated conversations. Five isolated agents. Zero shared memory.

## 2. What actually gets lost

The artifacts that survive a branch — commits, diffs, PR bodies, tests — are all
**records of what exists**. Every high-value piece of engineering context is a record of
what *doesn't* exist, and those have nowhere to live:

| Context type | Example | Where it survives today |
|---|---|---|
| **Rejected alternatives** | "We did *not* use a Redis queue — it adds a failure mode we can't monitor yet." | Nowhere |
| **Load-bearing weirdness** | "This wrapper looks like a no-op. It is not. It caps us at 25 req/s." | Nowhere |
| **Deliberate omissions** | "No test covers this on purpose — it needs a live rate limit." | Nowhere |
| **Hard invariants** | "Never call this outside the transaction, the outbox depends on it." | Nowhere |
| **Confidence level** | "I'm 60% sure about this; revisit after the Q3 migration." | Nowhere |
| **Expiry** | "This hack is correct *until* we upgrade to v4." | Nowhere |

A commit message can carry a sentence of this. A PR description can carry a paragraph.
Neither survives contact with a merge six days later, and neither is *retrievable* —
you can't ask a commit log "what did anyone decide about this function?"

## 3. Why this is now a correctness bug, not a culture problem

Before agents, lost intent produced a slow tax: someone eventually asks in Slack, someone
eventually remembers. The loop closed, slowly, through humans.

With agents, the loop doesn't close — it **closes wrong, fast, and with confidence.**

An agent asked to resolve a merge, review a PR, or refactor a module sees exactly what
Git shows it: the diff. It has no access to the other developer's reasoning, so it does
the only thing it can — it **infers intent from syntax**. Inferred intent is a
hallucination with a clean diff attached.

The canonical failure:

```
Alice, branch feat/stripe-debounce:
  Adds debounceWebhook() around the Stripe handler.
  Reason (stated to her agent, never written down anywhere):
    "Stripe rate-limits us at 25 req/s on this endpoint. I considered a Redis
     queue and rejected it — extra failure mode, no monitoring for it yet.
     There is no test because reproducing it needs a live rate limit.
     Do not remove this without adding the queue first."

Bob, branch refactor/webhook-cleanup (three days later):
  Asks his agent to "clean up the webhook module."
  His agent sees: a wrapper, no tests, no comment, no call-site depending on timing.
  Its honest conclusion: dead abstraction. It inlines it away.

Result:
  git merge      → clean. No textual conflict. Not even a nearby line.
  CI             → green. Nothing tested it, by design.
  AI code review → "LGTM, nice simplification."
  Production     → 429s from Stripe under load, next Tuesday.
```

Nothing in this chain is broken. Git did its job. CI did its job. Both agents behaved
reasonably given their inputs. **The system failed because the only input that mattered
was thrown away when Alice closed her terminal.**

This is a **silent semantic conflict**: two branches that are textually compatible and
semantically contradictory. Git is structurally incapable of detecting it — it diffs
*text*, and the conflict is in *intent*. There is no tool in the standard pipeline whose
job is to catch it.

## 4. Why the obvious fixes don't work

**"Write better commit messages."**
Asks every developer to predict, at commit time, which detail will matter to a stranger's
agent three weeks later. Nobody can. And it doesn't solve retrieval — you still can't
query a commit log semantically.

**"Let the AI read the commit history."**
The history contains what changed. The reasoning was never in it. Feeding an agent 400
commits also blows the context window and buries the two that matter.

**"Put it in `CLAUDE.md` / a decisions doc."**
This is the failure mode the hackathon named directly: *memory should not live in a
markdown file.* A markdown file cannot be scoped per-person or per-team, cannot exceed a
context window, has no retrieval, and grows monotonically until agents ignore it.
It is also **write-once**: nobody updates it at merge time, which is exactly when it's needed.

**"Longer context windows."**
Context length is not the bottleneck. **The data was never captured.** You cannot put
into context something that no longer exists.

**"PR review / AI reviewers."**
A reviewer — human or model — reads the diff. Same missing input, same blind spot. An AI
reviewer given no memory of Alice's reasoning will approve Bob's PR just as fast.

## 5. The actual shape of the problem

Three properties, all of which a file cannot satisfy and a vector+graph memory can:

1. **It must be captured automatically, at the moment of highest fidelity** — while the
   developer is still explaining themselves to their agent. Not reconstructed later from
   a diff.
2. **It must be retrievable by code surface, not by keyword** — "what has anyone ever
   decided about `src/webhooks/stripe.ts:debounceWebhook`?" That is a graph traversal
   joined to a semantic search, not a `grep`.
3. **It must be injected at merge time, into the agent, unprompted** — because the person
   who needs the context is precisely the person who doesn't know they need it.

## 6. What we are building

**Cogmerge** — a shared, queryable memory of *developer intent*, captured from agent
conversations and Slack, structured into a knowledge graph with Cognee, stored in Qdrant,
and served back to every agent on the team at the exact moment before a merge.

It answers one question that nothing else in the toolchain can answer:

> **"Before I merge this — what did someone else decide about the code I'm touching,
> and am I about to undo it?"**

See [`SOLUTION.md`](./SOLUTION.md) for the architecture and
[`PLAN.md`](./PLAN.md) for the build.
