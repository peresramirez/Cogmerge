"""Retrieve every intent anyone recorded about the code you are about to merge.

    python check.py --base main --head HEAD
    python check.py --files src/webhooks/stripe.py

This does NOT decide whether there is a conflict -- it retrieves, and the
cogmerge-adjudicator subagent judges. Two stages:

  1. deterministic: diff -> surfaces -> node_set filter (no LLM, stays scoped
     as the repo grows)
  2. semantic + graph: GRAPH_COMPLETION over that scoped slice
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import backend  # noqa: E402
import surfaces as surf  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="main")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--files", nargs="*", default=None)
    ap.add_argument("--exclude-branch", default=None)
    ap.add_argument("--cwd", default=".")
    args = ap.parse_args()

    found = (
        surf.from_files(args.files)
        if args.files
        else surf.from_diff(args.base, args.head, cwd=args.cwd)
    )

    backend.banner()
    if not found:
        print("No surfaces in this diff. Nothing to check.")
        return

    print(f"## Surfaces being changed ({len(found)})\n")
    for s in found:
        print(f"- {s}")

    question = (
        "What decisions, invariants, landmines or deliberate omissions has anyone "
        f"recorded about these code surfaces: {', '.join(found)}? "
        "Quote the rationale and any rejected alternatives verbatim, and name the "
        "branch, PR and author they came from."
        + (f" Ignore anything from branch {args.exclude_branch}." if args.exclude_branch else "")
    )

    be = backend.get()
    tags = [f"surface:{s}" for s in found] + [f"repo:{backend.REPO}"]
    results = be.search(question, tags)

    # A scoped miss must not read as an all-clear -- retry unscoped before
    # reporting nothing.
    if not results:
        print("\n_(no node_set hits; retrying unscoped)_", file=sys.stderr)
        results = be.search(question, None)

    print("\n## Recorded intent touching these surfaces\n")
    if not results:
        print("_No prior intent recorded for these surfaces._")
        return
    for r in results:
        print(r)
        print()

    print(
        "---\n"
        "ADJUDICATE THIS with the cogmerge-adjudicator subagent. For each record "
        "above decide contradicts / depends_on / unrelated, citing the hunk and "
        "the stated rationale. Most will be unrelated -- say so plainly."
    )


if __name__ == "__main__":
    main()
