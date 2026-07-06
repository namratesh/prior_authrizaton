"""
Hybrid (dense + sparse, RRF-fused) search over the aarp_policies Qdrant collection.

// DEMO-REAL: this is the actual retrieval call used by the AARP Medicare RAG agent.
"""
from qdrant_client.models import (
    FusionQuery,
    Fusion,
    Prefetch,
    SparseVector,
)

from app.core.qdrant_setup import (
    DENSE_VECTOR,
    SPARSE_VECTOR,
    COLLECTION_NAME,
    get_dense_model,
    get_qdrant_client,
    get_sparse_model,
)

PREFETCH_LIMIT = 20


def hybrid_search(query: str, top_k: int = 3) -> list[dict]:
    """Hybrid dense+sparse search over aarp_policies.

    Retrieves candidates from both a dense (semantic) and sparse (BM25 keyword)
    search, fuses them with Reciprocal Rank Fusion, then reports each result's
    dense cosine similarity as its `score` (the RRF fusion score itself isn't a
    similarity and isn't comparable to a 0-1 confidence threshold).

    Returns a list of up to `top_k` dicts: {text, source, doc_type, page, score}.
    """
    client = get_qdrant_client()
    dense_model = get_dense_model()
    sparse_model = get_sparse_model()

    dense_vec = next(iter(dense_model.embed([query]))).tolist()
    sparse_embedding = next(iter(sparse_model.embed([query])))
    sparse_vec = SparseVector(
        indices=sparse_embedding.indices.tolist(),
        values=sparse_embedding.values.tolist(),
    )

    fused = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            Prefetch(query=dense_vec, using=DENSE_VECTOR, limit=PREFETCH_LIMIT),
            Prefetch(query=sparse_vec, using=SPARSE_VECTOR, limit=PREFETCH_LIMIT),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=max(top_k * 3, PREFETCH_LIMIT),
        with_payload=True,
    ).points

    dense_only = client.query_points(
        collection_name=COLLECTION_NAME,
        query=dense_vec,
        using=DENSE_VECTOR,
        limit=PREFETCH_LIMIT * 2,
        with_payload=False,
    ).points
    dense_scores = {p.id: p.score for p in dense_only}

    results = [
        {
            "text": p.payload["text"],
            "source": p.payload["source"],
            "doc_type": p.payload["doc_type"],
            "page": p.payload["page"],
            "score": dense_scores.get(p.id, p.score),
        }
        for p in fused
    ]
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "step therapy prior authorization requirement"
    for r in hybrid_search(q):
        print(f"[{r['score']:.3f}] {r['source']} ({r['doc_type']}) p.{r['page']} — {r['text'][:120]!r}")
