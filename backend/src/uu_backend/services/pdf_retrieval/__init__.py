"""PDF-only intelligent retrieval subsystem."""

from .service import PDF_RETRIEVAL_BACKEND, PDFRetrievalService, get_pdf_retrieval_service

__all__ = [
    "PDF_RETRIEVAL_BACKEND",
    "PDFRetrievalService",
    "get_pdf_retrieval_service",
]
