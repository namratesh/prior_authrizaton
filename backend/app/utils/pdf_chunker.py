"""
PDF -> (chunk_text, page_num) extraction for policy ingestion.

// DEMO-REAL: pdfplumber only, no Azure Document Intelligence fallback (out of scope).
"""
from pathlib import Path
from typing import Iterator

import pdfplumber

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def _split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def extract_chunks(pdf_path: Path) -> Iterator[tuple[str, int]]:
    """Yield (chunk_text, page_num) for every non-empty chunk in the PDF. page_num is 1-indexed."""
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                continue
            for chunk in _split_text(text):
                if chunk.strip():
                    yield chunk, page_num
