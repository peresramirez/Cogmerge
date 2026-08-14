"""The only thing that talks to Cognee. Two interchangeable backends.

    COGMERGE_BACKEND=cloud    Cognee Cloud REST API      (default, zero install)
    COGMERGE_BACKEND=qdrant   cognee library -> Qdrant Cloud (your own cluster)

Both expose the same three calls, so seal.py / check.py never know which is live.

Why two: Cognee Cloud manages its own vector tier, so it is the fastest path but
your Qdrant dashboard stays empty. The qdrant backend runs the cognee library
locally and writes embeddings into a Qdrant cluster you own and can show.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _load_dotenv() -> None:
    """Stdlib only, on purpose: no pip, no venv, nothing to install on Monday."""
    for parent in [Path.cwd(), *Path(__file__).resolve().parents]:
        env = parent / ".env"
        if not env.exists():
            continue
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))
        return


_load_dotenv()

MODE = os.getenv("COGMERGE_BACKEND", "cloud").lower()
REPO = os.getenv("COGMERGE_REPO", "local/repo")
DATASET = "cogmerge_" + REPO.replace("/", "_").replace("-", "_")


def banner() -> None:
    print(f"[cogmerge] backend={MODE} repo={REPO} dataset={DATASET}", file=sys.stderr)


# --------------------------------------------------------------------------
# Cognee Cloud (REST)
# --------------------------------------------------------------------------
class _Cloud:
    name = "cognee-cloud"

    def __init__(self) -> None:
        try:
            self.base = os.environ["COGNEE_BASE_URL"].rstrip("/")
            self._headers = {
                "X-Api-Key": os.environ["COGNEE_API_KEY"],
                "X-Tenant-Id": os.environ["COGNEE_TENANT_ID"],
                "Content-Type": "application/json",
            }
        except KeyError as missing:
            raise SystemExit(
                f"Missing {missing} in .env — copy .env.example and fill it in."
            ) from None

    def _post(self, path: str, payload: dict, timeout: int = 300):
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=json.dumps(payload).encode(),
            headers=self._headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode() or "null")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"{path} -> {exc.code}: {exc.read().decode()[:400]}"
            ) from None

    def add(self, text: str, node_set: list[str]) -> None:
        self._post(
            "/api/v1/add_text",
            {"textData": [text], "datasetName": DATASET, "nodeSet": node_set},
        )

    def cognify(self) -> None:
        self._post("/api/v1/cognify", {"datasets": [DATASET], "runInBackground": False})

    def search(self, query: str, node_name: list[str] | None, top_k: int = 12) -> list[str]:
        payload = {
            "query": query,
            "searchType": "GRAPH_COMPLETION",
            "datasets": [DATASET],
            "topK": top_k,
        }
        if node_name:
            payload["nodeName"] = node_name
        out: list[str] = []
        for row in self._post("/api/v1/search", payload, timeout=180) or []:
            res = row.get("search_result") if isinstance(row, dict) else row
            if isinstance(res, list):
                out.extend(str(x) for x in res)
            elif res:
                out.append(str(res))
        return out


# --------------------------------------------------------------------------
# cognee library -> Qdrant Cloud
# --------------------------------------------------------------------------
class _Qdrant:
    name = "cognee-lib+qdrant"

    def __init__(self) -> None:
        # Registers the provider. Must happen before any cognee call, or cognee
        # silently stays on LanceDB / raises Unsupported provider.
        #
        # Version-dependent: in adapter 0.4.0 `register` is a MODULE and the
        # import itself is the side-effect; other versions export a callable.
        # Handle both rather than pinning.
        from cognee_community_vector_adapter_qdrant import register  # noqa: F401

        if callable(register):
            register()
        import cognee

        self.cognee = cognee
        cognee.config.set_vector_db_config(
            {
                "vector_db_provider": "qdrant",
                "vector_db_url": os.environ["QDRANT_API_URL"],
                "vector_db_key": os.environ["QDRANT_API_KEY"],
                "vector_dataset_database_handler": "qdrant",
            }
        )

    def _run(self, coro):
        # One loop for the process. asyncio.run() per call would give cognee a
        # fresh loop each time and strand its connection pools; get_event_loop()
        # is deprecated on 3.12+.
        import asyncio

        if getattr(self, "_loop", None) is None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop.run_until_complete(coro)

    def add(self, text: str, node_set: list[str]) -> None:
        self._run(self.cognee.add(text, dataset_name=DATASET, node_set=node_set))

    def cognify(self) -> None:
        self._run(self.cognee.cognify(datasets=[DATASET]))

    def search(self, query: str, node_name: list[str] | None, top_k: int = 12) -> list[str]:
        from cognee import SearchType

        kw = {
            "query_text": query,
            "query_type": SearchType.GRAPH_COMPLETION,
            "datasets": [DATASET],
            "top_k": top_k,
        }
        if node_name:
            kw["node_name"] = node_name
            kw["node_name_filter_operator"] = "OR"
        results = self._run(self.cognee.search(**kw))
        return [str(getattr(r, "search_result", r)) for r in results or []]


def get():
    return _Qdrant() if MODE == "qdrant" else _Cloud()
