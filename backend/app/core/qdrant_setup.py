"""
Qdrant collection for AARP EOC/SOB policy chunks — hybrid (dense + sparse) retrieval.

// DEMO-REAL: this is the actual retrieval backend for the AARP Medicare RAG agent.
"""
import os

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    SparseVectorParams,
    VectorParams,
)

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "aarp_policies"

DENSE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
DENSE_VECTOR_SIZE = 384
SPARSE_MODEL_NAME = "Qdrant/bm25"

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"

_dense_model: TextEmbedding | None = None
_sparse_model: SparseTextEmbedding | None = None
_qdrant_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    # Memoized like get_dense_model/get_sparse_model below (and llm_client.py's
    # provider clients) — every RAG-agent call otherwise opened a brand-new
    # QdrantClient/connection pool instead of reusing one for the process
    # lifetime.
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=QDRANT_URL)
    return _qdrant_client


def get_dense_model() -> TextEmbedding:
    global _dense_model
    if _dense_model is None:
        _dense_model = TextEmbedding(DENSE_MODEL_NAME)
    return _dense_model


def get_sparse_model() -> SparseTextEmbedding:
    global _sparse_model
    if _sparse_model is None:
        _sparse_model = SparseTextEmbedding(SPARSE_MODEL_NAME)
    return _sparse_model


def ensure_collection(client: QdrantClient | None = None) -> None:
    """Create the aarp_policies collection (dense + sparse named vectors) if it doesn't exist."""
    c = client or get_qdrant_client()
    if c.collection_exists(COLLECTION_NAME):
        return
    c.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            DENSE_VECTOR: VectorParams(size=DENSE_VECTOR_SIZE, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            SPARSE_VECTOR: SparseVectorParams(),
        },
    )
    # Index doc_type/page as payload fields so the RAG agent can filter
    # (e.g. restrict to a case's known plan doc, or a specific page range).
    c.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="doc_type",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    c.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="page",
        field_schema=PayloadSchemaType.INTEGER,
    )


if __name__ == "__main__":
    ensure_collection()
    print(f"Ensured Qdrant collection {COLLECTION_NAME!r} at {QDRANT_URL}")
