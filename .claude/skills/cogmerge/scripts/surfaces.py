"""Turn a git diff into a list of code surfaces: "path" and "path:symbol".

Surfaces are the join key. Alice's memory and Bob's diff meet here and nowhere
else, so this stays deliberately dumb and deterministic -- no LLM, no parsing
of whole files. Git already tells us the enclosing symbol in its hunk headers.
"""

import re
import subprocess

# @@ -12,3 +12,0 @@ def debounce_webhook(payload):
_HUNK = re.compile(r"^@@ .*? @@\s*(?P<ctx>.*)$")
_SYMBOL = re.compile(
    r"(?:def|class|func|function|fn)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?:const|let|var)\s+(?P<name2>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\("
)


def _git(args: list[str], cwd: str = ".") -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    ).stdout


def _symbol(text: str) -> str | None:
    m = _SYMBOL.search(text or "")
    if not m:
        return None
    return m.group("name") or m.group("name2")


def from_diff(base: str, head: str = "HEAD", cwd: str = ".") -> list[str]:
    """Surfaces touched by base..head. Returns ["path", "path:symbol", ...]."""
    diff = _git(["diff", "-U0", f"{base}...{head}"], cwd=cwd)
    surfaces: set[str] = set()
    path: str | None = None

    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            if path and path != "/dev/null":
                surfaces.add(path)
            continue
        if not path:
            continue

        hunk = _HUNK.match(line)
        if hunk:
            # git puts the enclosing function after the second @@
            if sym := _symbol(hunk.group("ctx")):
                surfaces.add(f"{path}:{sym}")
            continue

        # a definition added or removed *inside* the hunk body
        if line[:1] in "+-" and not line.startswith(("+++", "---")):
            if sym := _symbol(line[1:]):
                surfaces.add(f"{path}:{sym}")

    return sorted(surfaces)


def from_files(paths: list[str]) -> list[str]:
    return sorted(set(paths))


if __name__ == "__main__":
    import sys

    base = sys.argv[1] if len(sys.argv) > 1 else "main"
    head = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    for s in from_diff(base, head):
        print(s)
