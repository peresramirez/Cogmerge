# Intent Record — the contract

The `cogmerge-distiller` subagent emits exactly this. `seal.py` consumes it.

Every field except `goal` is optional; emit only what the conversation supports.
`touches` entries are `path` or `path:symbol`, repo-relative, POSIX separators.

```json
{
  "repo": "acme/payments-api",
  "branch": "feat/stripe-debounce",
  "pr": 121,
  "author": "alice",
  "goal": "Stop Stripe 429s on the account webhook without adding infrastructure.",

  "decisions": [
    {
      "statement": "Debounce in-process instead of queueing webhook deliveries.",
      "rationale": "Stripe caps this endpoint at 25 req/s. A Redis queue would work but adds a failure mode we have no monitoring for yet, and we would be paging on it blind.",
      "rejected_alternatives": [
        "Redis-backed delivery queue — extra failure mode, no monitoring",
        "Raising the Stripe rate limit — support ticket, weeks of lead time"
      ],
      "strength": "hard_invariant",
      "expires_when": "we move to Stripe API v4, which lifts the per-account cap",
      "touches": ["src/webhooks/stripe.py:debounce_webhook"]
    }
  ],

  "landmines": [
    {
      "description": "debounce_webhook looks like a pointless pass-through wrapper.",
      "why_it_looks_wrong": "No test covers it, no caller depends on its timing, and it reads like a no-op.",
      "what_breaks_if_removed": "Stripe starts returning 429 under load. Silent in dev, only shows up at production traffic.",
      "touches": ["src/webhooks/stripe.py:debounce_webhook"]
    }
  ],

  "omissions": [
    {
      "what_was_not_done": "No unit test for the debounce timing.",
      "why_not": "Reproducing it needs a live rate limit; a mocked clock would pass while the real behaviour regressed, which is worse than no test."
    }
  ],

  "clarifications": [
    {
      "question": "Should the debounce be per-account or global across all tenants?",
      "answer": "Per-account. Stripe's cap is per-account, and a global debounce would throttle tenants who are nowhere near the limit.",
      "touches": ["src/webhooks/stripe.py:debounce_webhook"]
    }
  ],

  "open_questions": [
    "Does the 25 req/s cap apply per account or per endpoint? Assumed per account."
  ],

  "surfaces": ["src/webhooks/stripe.py"],

  "changed_files": [
    {"status": "M", "path": "src/webhooks/stripe.py"},
    {"status": "A", "path": "src/webhooks/__init__.py"}
  ]
}
```

`changed_files` is **not written by the distiller** — `seal.py` derives it from
`git diff --name-status` at seal time. Do not hand-author it; anything the LLM
transcribes here would be a worse copy of something git already knows exactly.

## Field notes

| Field | Why it exists |
|---|---|
| `rationale` | The whole product. Prefer the developer's own words. |
| `rejected_alternatives` | Stops the next agent re-proposing what was already ruled out. |
| `strength` | `hard_invariant` blocks a merge. `strong_preference` warns. `exploratory` is FYI. |
| `expires_when` | Intent has a shelf life. Without this, memory becomes dogma. |
| `touches` | The join key. Wrong path = invisible forever. |
| `what_breaks_if_removed` | Turns "don't touch" into a reason someone will accept. |
| `clarifications` | The highest-signal field after `rationale` — see below. |
| `changed_files` | Blast radius, for review. Machine-derived, never authored. |

### Why `clarifications` matter more than they look

When an agent stops and asks the developer a question, that question marks a
**proven ambiguity**: the code and the task were not clear enough to proceed.
The developer's answer resolves it.

The next agent to touch that code will hit the *same* ambiguity — that is what
makes it structural rather than incidental. Storing the exchange pre-answers a
question that is otherwise guaranteed to be asked again, and asked at the worst
possible moment: mid-merge, by someone with no context.

Capture the question as it was asked and the answer in the developer's own
words. Do not summarise the answer into a decision — the decision may already be
in `decisions`, but the *shape of the confusion* is what makes this reusable.
