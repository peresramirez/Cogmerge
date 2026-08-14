"""Write one intent record into Cogmerge memory.

    python seal.py demo/alice_intent.json
    cat record.json | python seal.py -

The record is produced by the cogmerge-distiller subagent, not by this script.
All this does is render it and store it with the right node_set tags -- those
tags are what make retrieval at merge time scoped and cheap instead of a
semantic scan over the repo's whole history.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import backend  # noqa: E402


def render(r: dict) -> str:
    """Markdown is what gets cognified. Dense on *why*, silent on *what*."""
    out = [
        f"# Intent: {r.get('branch', 'unknown-branch')}",
        "",
        f"- Repo: {r.get('repo')}",
        f"- Branch: {r.get('branch')}",
        f"- PR: {r.get('pr')}",
        f"- Author: {r.get('author')}",
        "",
        f"## Goal\n{(r.get('goal') or '').strip()}",
    ]

    for d in r.get("decisions") or []:
        out.append(f"\n## Decision: {d.get('statement')}")
        out.append(f"Rationale: {d.get('rationale')}")
        out.append(f"Strength: {d.get('strength', 'strong_preference')}")
        if alts := d.get("rejected_alternatives"):
            out.append("Rejected alternatives: " + "; ".join(alts))
        if exp := d.get("expires_when"):
            out.append(f"Expires when: {exp}")
        if t := d.get("touches"):
            out.append("Touches: " + ", ".join(t))

    for m in r.get("landmines") or []:
        out.append(f"\n## Landmine: {m.get('description')}")
        out.append(f"Why it looks wrong: {m.get('why_it_looks_wrong')}")
        out.append(f"What breaks if removed: {m.get('what_breaks_if_removed')}")
        if t := m.get("touches"):
            out.append("Touches: " + ", ".join(t))

    for o in r.get("omissions") or []:
        out.append(
            f"\n## Deliberate omission: {o.get('what_was_not_done')}\n"
            f"Why not: {o.get('why_not')}"
        )

    if q := r.get("open_questions"):
        out.append("\n## Open questions")
        out.extend(f"- {x}" for x in q)

    return "\n".join(out)


def surfaces_of(r: dict) -> list[str]:
    found: set[str] = set(r.get("surfaces") or [])
    for group in ("decisions", "landmines", "omissions"):
        for item in r.get(group) or []:
            found.update(item.get("touches") or [])
    return sorted(s for s in found if s)


def node_sets(r: dict, surfaces: list[str]) -> list[str]:
    tags = [f"repo:{r.get('repo', backend.REPO)}"]
    for key, prefix in (("branch", "branch"), ("pr", "pr"), ("author", "author")):
        if r.get(key):
            tags.append(f"{prefix}:{r[key]}")
    return tags + [f"surface:{s}" for s in surfaces]


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else "-"
    record = json.loads(sys.stdin.read() if src == "-" else Path(src).read_text())
    record.setdefault("repo", backend.REPO)

    if not any(record.get(k) for k in ("decisions", "landmines", "omissions")):
        print("Nothing worth sealing: no decisions, landmines or omissions.")
        print("An empty record is worse than none - it makes CHECK report a false all-clear.")
        sys.exit(1)

    surfaces = surfaces_of(record)
    tags = node_sets(record, surfaces)

    backend.banner()
    print(f"Sealing {record.get('branch')} ({len(surfaces)} surfaces)")
    for s in surfaces:
        print(f"  surface: {s}")

    be = backend.get()
    be.add(render(record), tags)
    be.cognify()
    print(f"Sealed via {be.name}. {len(tags)} node_set tags written.")


if __name__ == "__main__":
    main()
