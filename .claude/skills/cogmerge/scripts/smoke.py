"""Run this FIRST. Proves the backend works before you build on it.

    python .claude/skills/cogmerge/scripts/smoke.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import backend  # noqa: E402

TEXT = (
    "The debounce wrapper around the Stripe handler enforces a 25 req/s cap. "
    "A Redis queue was rejected because it adds an unmonitored failure mode."
)

be = backend.get()
backend.banner()
print(f"backend: {be.name}")

be.add(TEXT, ["repo:smoke", "surface:smoke.py:debounce"])
be.cognify()
results = be.search("what was rejected and why?", ["surface:smoke.py:debounce"])

for r in results:
    print(" ", r)
print("\nOK" if results else "\nFAIL: no results")
