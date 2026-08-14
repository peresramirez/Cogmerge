"""Write one intent record into Cogmerge memory.

    python seal.py demo/alice_intent.json
    cat record.json | python seal.py -

The record is produced by the cogmerge-distiller subagent, not by this script.
All this does is render it and store it with the right node_set tags -- those
tags are what make retrieval at merge time scoped and cheap instead of a
semantic scan over the repo's whole history.
"""

import argparse
import json
import subprocess
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

    # Asked-and-answered exchanges. Kept in Q/A shape rather than flattened into
    # a statement: the next agent hits the same ambiguity, and recognising the
    # question is what makes the answer findable.
    for c in r.get("clarifications") or []:
        out.append(f"\n## Clarification asked during the work")
        out.append(f"Q: {c.get('question')}")
        out.append(f"A: {c.get('answer')}")
        if t := c.get("touches"):
            out.append("Touches: " + ", ".join(t))

    if q := r.get("open_questions"):
        out.append("\n## Open questions")
        out.extend(f"- {x}" for x in q)

    if files := r.get("changed_files"):
        out.append("\n## Files changed in this branch")
        out.extend(f"- {f.get('status', '?')} {f.get('path')}" for f in files)

    return "\n".join(out)


def changed_files(base: str, head: str, cwd: str) -> list[dict]:
    """Ask git, don't ask the LLM. Deterministic, free, and always correct."""
    try:
        raw = subprocess.run(
            ["git", "diff", "--name-status", f"{base}...{head}"],
            cwd=cwd, capture_output=True, text=True, check=False,
        ).stdout
    except OSError:
        return []

    files = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            files.append({"status": parts[0][:1], "path": parts[-1]})
    return files


def surfaces_of(r: dict) -> list[str]:
    found: set[str] = set(r.get("surfaces") or [])
    for group in ("decisions", "landmines", "omissions", "clarifications"):
        for item in r.get(group) or []:
            found.update(item.get("touches") or [])
    # Every changed file is a surface too, so a later merge touching a file with
    # no symbol-level record still finds the branch that produced it.
    found.update(f["path"] for f in r.get("changed_files") or [] if f.get("path"))
    return sorted(s for s in found if s)


def node_sets(r: dict, surfaces: list[str]) -> list[str]:
    tags = [f"repo:{r.get('repo', backend.REPO)}"]
    for key, prefix in (("branch", "branch"), ("pr", "pr"), ("author", "author")):
        if r.get(key):
            tags.append(f"{prefix}:{r[key]}")
    return tags + [f"surface:{s}" for s in surfaces]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("record", nargs="?", default="-", help="JSON file, or - for stdin")
    ap.add_argument("--base", default="main", help="base ref for the file list")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--cwd", default=".", help="repo to read the file list from")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.record == "-" else Path(args.record).read_text()
    record = json.loads(raw)
    record.setdefault("repo", backend.REPO)

    if not any(
        record.get(k) for k in ("decisions", "landmines", "omissions", "clarifications")
    ):
        print("Nothing worth sealing: no decisions, landmines, omissions or clarifications.")
        print("An empty record is worse than none - it makes CHECK report a false all-clear.")
        sys.exit(1)

    # Derived, not authored. If the caller already supplied it, trust them.
    if not record.get("changed_files"):
        record["changed_files"] = changed_files(args.base, args.head, args.cwd)

    surfaces = surfaces_of(record)
    tags = node_sets(record, surfaces)

    backend.banner()
    print(f"Sealing {record.get('branch')} ({len(surfaces)} surfaces)")
    for s in surfaces:
        print(f"  surface: {s}")
    if files := record.get("changed_files"):
        print(f"  {len(files)} file(s) changed: " + ", ".join(
            f"{f['status']} {f['path']}" for f in files[:5]
        ) + (" ..." if len(files) > 5 else ""))
    if c := record.get("clarifications"):
        print(f"  {len(c)} clarification(s) captured")

    be = backend.get()
    be.add(render(record), tags)
    be.cognify()
    print(f"Sealed via {be.name}. {len(tags)} node_set tags written.")


if __name__ == "__main__":
    main()
