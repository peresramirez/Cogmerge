#!/usr/bin/env bash
# Builds the demo repo: two branches that merge CLEANLY and still contradict.
# Run from the project root:  bash demo/setup.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)/payments-api"
rm -rf "$REPO"
mkdir -p "$REPO/src/webhooks"
cd "$REPO"

git init -q -b main
git config user.name "Alice"
git config user.email alice@example.com

cat > src/webhooks/stripe.py <<'PY'
import time

_last_call = 0.0
MIN_INTERVAL = 1.0 / 25


def debounce_webhook(handler):
    def wrapped(payload):
        global _last_call
        wait = MIN_INTERVAL - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        return handler(payload)

    return wrapped


@debounce_webhook
def handle_stripe_event(payload):
    return {"ok": True, "id": payload.get("id")}
PY

cat > test_stripe.py <<'PY'
from src.webhooks.stripe import handle_stripe_event


def test_handles_event():
    assert handle_stripe_event({"id": "evt_1"})["ok"] is True
PY

git add -A
git commit -qm "feat: debounce Stripe webhook delivery (#121)"

# --- Bob's branch: his agent sees an untested no-op wrapper and inlines it ---
git checkout -q -b refactor/webhook-cleanup
git config user.name "Bob"
git config user.email bob@example.com

cat > src/webhooks/stripe.py <<'PY'
def handle_stripe_event(payload):
    return {"ok": True, "id": payload.get("id")}
PY

git add -A
git commit -qm "refactor: drop unused debounce wrapper (#128)"
git checkout -q main

echo "Demo repo ready: $REPO"
echo
echo "Proof the premise holds:"
git merge --no-commit --no-ff refactor/webhook-cleanup >/dev/null 2>&1 \
  && echo "  git merge      -> CLEAN, no conflict" \
  || echo "  git merge      -> conflict (unexpected!)"
git merge --abort 2>/dev/null || true
python3 -m pytest -q >/dev/null 2>&1 \
  && echo "  tests          -> GREEN" \
  || echo "  tests          -> (pytest not installed; fine for the demo)"
echo "  a code reviewer -> 'LGTM, nice simplification'"
echo
echo "Now run:  bash demo/run.sh"
