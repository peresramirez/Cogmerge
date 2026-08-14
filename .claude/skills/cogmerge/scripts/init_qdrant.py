"""Create the payload index Cogmerge's scoped retrieval needs. Qdrant only.

    python3 .claude/skills/cogmerge/scripts/init_qdrant.py

Run once after the first seal, and again if cognee creates new collections.
Idempotent -- re-running is safe.

Why this exists
---------------
Cogmerge scopes every retrieval with a node_set filter, so a merge only pulls
intent about the surfaces it actually touches. cognee stores those tags in a
`belongs_to_set` payload field, and Qdrant refuses to filter on a payload field
that has no index:

    400 Bad Request: Index required but not found for "belongs_to_set"
    of one of the following types: [keyword]

The community adapter creates the collections but not this index, so the filter
fails on a fresh cluster. Worse, it fails *soft*: cognee logs the error, returns
an empty context, and the answer comes back "I don't see any triplets" -- which
reads like "no prior intent recorded" rather than "your filter is broken". A
false all-clear is the one failure mode Cogmerge must never have.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import backend  # noqa: E402  -- loads .env

FIELD = "belongs_to_set"


def _req(method: str, path: str, body: dict | None = None):
    url = os.environ["QDRANT_API_URL"].rstrip("/") + path
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body else None,
        headers={
            "api-key": os.environ["QDRANT_API_KEY"],
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode() or "null")


def main() -> None:
    if not os.getenv("QDRANT_API_URL") or not os.getenv("QDRANT_API_KEY"):
        raise SystemExit("QDRANT_API_URL / QDRANT_API_KEY missing from .env")

    collections = [c["name"] for c in _req("GET", "/collections")["result"]["collections"]]
    if not collections:
        raise SystemExit(
            "No collections yet. Seal one record first, then re-run this."
        )

    print(f"Indexing {FIELD} across {len(collections)} collection(s):")
    failed = 0
    for name in collections:
        try:
            _req(
                "PUT",
                f"/collections/{name}/index?wait=true",
                {"field_name": FIELD, "field_schema": "keyword"},
            )
            print(f"  ok    {name}")
        except urllib.error.HTTPError as exc:
            failed += 1
            print(f"  FAIL  {name}: {exc.code} {exc.read().decode()[:160]}")

    if failed:
        raise SystemExit(f"\n{failed} collection(s) failed — scoped retrieval will misfire.")
    print("\nDone. Scoped node_set retrieval will now work on Qdrant.")


if __name__ == "__main__":
    main()
