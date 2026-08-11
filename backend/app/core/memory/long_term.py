"""Long-term / cross-session semantic memory.

Uses a second Chroma collection by default (zero-cost). Swap the backend
for Pinecone at scale by implementing the same add_fact / query_facts
interface — nothing else in the app needs to change.
"""
import chromadb

from app.config import get_settings

_settings = get_settings()
_client = chromadb.PersistentClient(path=_settings.chroma_persist_dir)
_collection = _client.get_or_create_collection("long_term_memory")


def add_fact(fact_id: str, text: str, metadata: dict | None = None) -> None:
    _collection.add(ids=[fact_id], documents=[text], metadatas=[metadata or {}])


def query_facts(text: str, n_results: int = 5) -> list[dict]:
    return _collection.query(query_texts=[text], n_results=n_results)
