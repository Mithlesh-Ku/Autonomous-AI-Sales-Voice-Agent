"""Knowledge base ingestion and semantic retrieval via ChromaDB with lightweight pure-Python fallback."""

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from app.config import settings

KB_DIR = Path(__file__).resolve().parent / "knowledge_base"
COLLECTION_NAME = "novaflow_sales_kb"
FALLBACK_STORE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "local_kb_store.json"


def _embed_text(text: str, dims: int = 384) -> list[float]:
    """Deterministic zero-network 384-dim word + trigram embedding vector."""
    vec = [0.0] * dims
    tokens = re.findall(r"[a-z0-9\u0900-\u097f]+", text.lower())
    features: list[tuple[str, float]] = [(t, 1.5) for t in tokens]
    for i in range(len(tokens) - 1):
        features.append((f"{tokens[i]}_{tokens[i + 1]}", 1.2))
    for t in tokens:
        if len(t) >= 4:
            for j in range(len(t) - 2):
                features.append((t[j : j + 3], 0.4))

    for feat, weight in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % dims
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _chunk_markdown(file_path: Path) -> list[dict[str, str]]:
    """Split a markdown document by level-2/3 headings into self-contained chunks."""
    text = file_path.read_text(encoding="utf-8")
    sections = re.split(r"\n(?=##+ )", text)
    chunks: list[dict[str, str]] = []
    for idx, sec in enumerate(sections):
        cleaned = sec.strip()
        if not cleaned:
            continue
        first_line = cleaned.splitlines()[0].lstrip("#").strip()
        chunks.append(
            {
                "id": f"{file_path.stem}__chunk_{idx}",
                "text": cleaned,
                "source": file_path.name,
                "section": first_line[:120],
            }
        )
    return chunks


def _load_all_chunks() -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for md_file in sorted(KB_DIR.glob("*.md")):
        chunks.extend(_chunk_markdown(md_file))
    return chunks


def _get_chroma_collection():
    """Lazily initialize ChromaDB (after OPENBLAS_NUM_THREADS=1 is set) or raise on memory limits."""
    import chromadb
    from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
    from chromadb.config import Settings as ChromaSettings

    class LocalHashingEmbeddingFunction(EmbeddingFunction[Documents]):
        def __init__(self, dims: int = 384) -> None:
            self.dims = dims

        @staticmethod
        def name() -> str:
            return "local_hashing"

        def get_config(self) -> dict[str, Any]:
            return {"dims": self.dims}

        @staticmethod
        def build_from_config(config: dict[str, Any]) -> "LocalHashingEmbeddingFunction":
            return LocalHashingEmbeddingFunction(dims=int(config.get("dims", 384)))

        def __call__(self, input: Documents) -> Embeddings:
            return [_embed_text(doc, self.dims) for doc in input]

    if settings.embedding_provider == "openai" and settings.openai_api_key.strip():
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        embed_fn: EmbeddingFunction[Documents] = OpenAIEmbeddingFunction(
            api_key=settings.openai_api_key,
            model_name="text-embedding-3-small",
        )
    else:
        embed_fn = LocalHashingEmbeddingFunction()

    persist_path = Path(settings.chroma_persist_dir)
    persist_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(persist_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )


def _ingest_fallback_store(force: bool = False) -> int:
    FALLBACK_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not force and FALLBACK_STORE_PATH.exists():
        data = json.loads(FALLBACK_STORE_PATH.read_text(encoding="utf-8"))
        if data:
            return len(data)
    chunks = _load_all_chunks()
    records = [{**c, "vector": _embed_text(c["text"])} for c in chunks]
    FALLBACK_STORE_PATH.write_text(json.dumps(records), encoding="utf-8")
    return len(records)


def _query_fallback_store(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    if not FALLBACK_STORE_PATH.exists():
        _ingest_fallback_store(force=True)
    records = json.loads(FALLBACK_STORE_PATH.read_text(encoding="utf-8"))
    q_vec = _embed_text(query)
    scored: list[dict[str, Any]] = []
    for rec in records:
        sim = sum(a * b for a, b in zip(q_vec, rec["vector"]))
        scored.append(
            {
                "source": rec["source"],
                "section": rec["section"],
                "content": rec["text"],
                "score": round(max(0.0, sim), 3),
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def ingest_knowledge_base(force: bool = False) -> int:
    """Ingest all markdown knowledge docs into ChromaDB, with pure-Python fallback on low RAM."""
    if settings.rag_backend == "local":
        return _ingest_fallback_store(force=force)
    try:
        collection = _get_chroma_collection()
        if not force and collection.count() > 0:
            return collection.count()

        all_chunks = _load_all_chunks()
        if not all_chunks:
            return 0

        collection.upsert(
            ids=[c["id"] for c in all_chunks],
            documents=[c["text"] for c in all_chunks],
            metadatas=[{"source": c["source"], "section": c["section"]} for c in all_chunks],
        )
        return len(all_chunks)
    except (MemoryError, OSError, RuntimeError):
        return _ingest_fallback_store(force=force)


def query_knowledge_base(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Retrieve the top-k most relevant knowledge chunks for a prospect query."""
    if settings.rag_backend == "local":
        return _query_fallback_store(query, top_k=top_k)
    try:
        collection = _get_chroma_collection()
        if collection.count() == 0:
            ingest_knowledge_base(force=True)

        results = collection.query(query_texts=[query], n_results=min(top_k, max(1, collection.count())))
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[]])[0]

        matches: list[dict[str, Any]] = []
        for doc, meta, dist in zip(docs, metas, dists):
            matches.append(
                {
                    "source": meta.get("source", "unknown.md"),
                    "section": meta.get("section", "General"),
                    "content": doc,
                    "score": round(max(0.0, 1.0 - float(dist)), 3),
                }
            )
        return matches
    except (MemoryError, OSError, RuntimeError):
        return _query_fallback_store(query, top_k=top_k)
