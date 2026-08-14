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

  "open_questions": [
    "Does the 25 req/s cap apply per account or per endpoint? Assumed per account."
  ],

  "surfaces": ["src/webhooks/stripe.py"]
}
```

## Field notes

| Field | Why it exists |
|---|---|
| `rationale` | The whole product. Prefer the developer's own words. |
| `rejected_alternatives` | Stops the next agent re-proposing what was already ruled out. |
| `strength` | `hard_invariant` blocks a merge. `strong_preference` warns. `exploratory` is FYI. |
| `expires_when` | Intent has a shelf life. Without this, memory becomes dogma. |
| `touches` | The join key. Wrong path = invisible forever. |
| `what_breaks_if_removed` | Turns "don't touch" into a reason someone will accept. |
