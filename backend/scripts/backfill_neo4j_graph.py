"""Backfill Neo4j knowledge graph from already-ingested documents.

Usage examples:
    python scripts/backfill_neo4j_graph.py --dry-run
    python scripts/backfill_neo4j_graph.py --wipe-existing --batch-size 25
    python scripts/backfill_neo4j_graph.py --max-docs 100
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

# Allow script execution from backend root.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uu_backend.config import get_settings
from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.services.graph_ingestion_service import get_graph_ingestion_service

logger = logging.getLogger("graph_backfill")


@dataclass
class BackfillStats:
    """Aggregated backfill counters."""

    documents_seen: int = 0
    documents_processed: int = 0
    documents_failed: int = 0
    entities_seen: int = 0
    entities_written: int = 0
    relationships_seen: int = 0
    relationships_written: int = 0


def parse_args() -> argparse.Namespace:
    """Parse command line args."""
    parser = argparse.ArgumentParser(description="Backfill Neo4j graph from vector store documents")
    parser.add_argument(
        "--wipe-existing",
        action="store_true",
        help="Delete all current Neo4j nodes/relationships before backfill",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Number of documents per processing batch (default: 25)",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Optional max number of documents to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would run without writing to Neo4j",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser.parse_args()


def chunked(items: list, batch_size: int):
    """Yield list slices."""
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def resolve_original_file_path(document_id: str, file_type: str) -> str | None:
    """Resolve stored source file path for a document id."""
    settings = get_settings()
    storage_path = settings.file_storage_path

    candidate = storage_path / f"{document_id}.{(file_type or '').lower()}"
    if candidate.exists():
        return str(candidate)

    for match in storage_path.glob(f"{document_id}.*"):
        if match.is_file():
            return str(match)
    return None


def main() -> int:
    """Run backfill job."""
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.batch_size <= 0:
        logger.error("batch_size_must_be_positive")
        return 2

    vector_store = get_vector_store()
    neo4j_client = get_neo4j_client()
    graph_service = get_graph_ingestion_service()

    all_docs = vector_store.get_all_documents()
    all_docs.sort(key=lambda doc: doc.created_at)
    if args.max_docs is not None:
        all_docs = all_docs[: args.max_docs]

    logger.info(
        "backfill_start",
        extra={
            "documents": len(all_docs),
            "wipe_existing": args.wipe_existing,
            "dry_run": args.dry_run,
            "batch_size": args.batch_size,
        },
    )

    if args.dry_run:
        logger.info("dry_run_selected_no_writes")
    elif args.wipe_existing:
        wipe_summary = neo4j_client.clear_all_data()
        logger.info("graph_wiped", extra=wipe_summary)

    stats = BackfillStats(documents_seen=len(all_docs))

    for batch_index, batch in enumerate(chunked(all_docs, args.batch_size), start=1):
        logger.info(
            "processing_batch",
            extra={"batch_index": batch_index, "batch_size": len(batch)},
        )

        for doc_summary in batch:
            try:
                document = vector_store.get_document(doc_summary.id)
                if document is None:
                    raise ValueError("document_not_found_in_vector_store")

                if args.dry_run:
                    stats.documents_processed += 1
                    continue

                graph_service.upsert_document(
                    doc_id=document.id,
                    filename=document.filename,
                    file_type=document.file_type,
                    date_extracted=document.date_extracted,
                    created_at=document.created_at,
                )
                summary = graph_service.extract_and_store_entities(
                    doc_id=document.id,
                    content=document.content,
                    document_date=document.date_extracted,
                    filename=document.filename,
                    file_type=document.file_type,
                    file_path=resolve_original_file_path(document.id, document.file_type),
                    created_at=document.created_at,
                )

                stats.documents_processed += 1
                stats.entities_seen += summary.entities_seen
                stats.entities_written += summary.entities_written
                stats.relationships_seen += summary.relationships_seen
                stats.relationships_written += summary.relationships_written

            except Exception:
                stats.documents_failed += 1
                logger.exception(
                    "backfill_document_failed",
                    extra={"document_id": doc_summary.id, "filename": doc_summary.filename},
                )

    logger.info(
        "backfill_complete",
        extra={
            "documents_seen": stats.documents_seen,
            "documents_processed": stats.documents_processed,
            "documents_failed": stats.documents_failed,
            "entities_seen": stats.entities_seen,
            "entities_written": stats.entities_written,
            "relationships_seen": stats.relationships_seen,
            "relationships_written": stats.relationships_written,
            "dry_run": args.dry_run,
        },
    )

    return 0 if stats.documents_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
