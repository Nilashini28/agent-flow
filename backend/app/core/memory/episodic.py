"""Episodic memory: embedded Chroma collection of completed steps.

Runs embedded (no separate service) so it costs nothing to host and needs
no extra infra beyond a local persist directory.
"""
import chromadb

from app.config import get_settings

_settings = get_settings()
_client = chromadb.PersistentClient(path=_settings.chroma_persist_dir)
_collection = _client.get_or_create_collection("episodic_memory")


def add_step(run_id: str, step_id: str, text: str, metadata: dict | None = None) -> None:
    _collection.add(
        ids=[f"{run_id}:{step_id}"],
        documents=[text],
        metadatas=[{"run_id": run_id, **(metadata or {})}],
    )


def query_similar(text: str, n_results: int = 5) -> list[dict]:
    results = _collection.query(query_texts=[text], n_results=n_results)
    return results
