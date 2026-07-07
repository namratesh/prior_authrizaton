"""
Whole-document text extraction for uploaded PA request PDFs (as opposed to
pdf_chunker.py, which chunks EOC/SOB policy PDFs for ingestion into Qdrant).

// DEMO-REAL: pdfplumber only, no Azure Document Intelligence fallback (out of scope).
"""
import io

import pdfplumber


def extract_full_text(pdf_bytes: bytes) -> str:
    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()
