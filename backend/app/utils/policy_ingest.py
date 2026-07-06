"""
Ingest AARP EOC/SOB policy PDFs into the aarp_policies Qdrant collection.

// DEMO-REAL: real pdfplumber extraction + fastembed dense/sparse encoding of the
provided policy PDFs, not a mocked/stubbed index.
"""
from pathlib import Path

from qdrant_client.models import PointStruct, SparseVector

from app.core.qdrant_setup import (
    DENSE_VECTOR,
    SPARSE_VECTOR,
    COLLECTION_NAME,
    ensure_collection,
    get_dense_model,
    get_qdrant_client,
    get_sparse_model,
)
from app.utils.pdf_chunker import extract_chunks

DEFAULT_POLICIES_DIR = Path(__file__).resolve().parents[3] / "aarp_policies"

BATCH_SIZE = 64


def _doc_type(pdf_path: Path) -> str:
    return "EOC" if "EOC" in pdf_path.name else "SOB"


def ingest_policies(folder: Path = DEFAULT_POLICIES_DIR) -> int:
    """Chunk + embed + upsert every PDF in `folder` into aarp_policies. Returns point count."""
    client = get_qdrant_client()
    ensure_collection(client)
    dense_model = get_dense_model()
    sparse_model = get_sparse_model()

    pdf_paths = sorted(folder.glob("*.pdf"))
    if not pdf_paths:
        raise FileNotFoundError(f"No PDFs found in {folder}")

    total = 0
    point_id = 0
    for pdf_path in pdf_paths:
        doc_type = _doc_type(pdf_path)
        texts: list[str] = []
        pages: list[int] = []
        for chunk, page_num in extract_chunks(pdf_path):
            texts.append(chunk)
            pages.append(page_num)

        if not texts:
            continue

        for batch_start in range(0, len(texts), BATCH_SIZE):
            batch_texts = texts[batch_start : batch_start + BATCH_SIZE]
            batch_pages = pages[batch_start : batch_start + BATCH_SIZE]

            dense_vecs = list(dense_model.embed(batch_texts))
            sparse_vecs = list(sparse_model.embed(batch_texts))

            points = []
            for text, page_num, dense_vec, sparse_vec in zip(
                batch_texts, batch_pages, dense_vecs, sparse_vecs
            ):
                points.append(
                    PointStruct(
                        id=point_id,
                        vector={
                            DENSE_VECTOR: dense_vec.tolist(),
                            SPARSE_VECTOR: SparseVector(
                                indices=sparse_vec.indices.tolist(),
                                values=sparse_vec.values.tolist(),
                            ),
                        },
                        payload={
                            "text": text,
                            "source": pdf_path.name,
                            "doc_type": doc_type,
                            "page": page_num,
                        },
                    )
                )
                point_id += 1

            client.upsert(collection_name=COLLECTION_NAME, points=points)
            total += len(points)

    return total


if __name__ == "__main__":
    count = ingest_policies()
    print(f"Ingested {count} chunks into {COLLECTION_NAME!r}")
