"""Document repository - replaces vector store with Django ORM."""

from datetime import datetime

from uu_backend.django_data.models import DocumentModel
from uu_backend.models.document import Document, DocumentMetadata, DocumentSummary


class DocumentRepository:
    """Repository for document storage using Django ORM."""

    def add_document(self, document: Document) -> None:
        """
        Add a document to the database.

        Args:
            document: The document to add
        """
        DocumentModel.objects.update_or_create(
            id=document.id,
            defaults={
                "filename": document.filename,
                "file_type": document.file_type,
                "content": document.content,
                "date_extracted": document.date_extracted,
                "created_at": document.created_at or datetime.utcnow(),
                "file_path": document.file_path,
                "page_count": (document.metadata.page_count if document.metadata else None),
                "word_count": len(document.content.split()) if document.content else 0,
            },
        )

    def get_document(self, document_id: str) -> Document | None:
        """
        Retrieve a document by ID.

        Args:
            document_id: The document ID

        Returns:
            The document or None if not found
        """
        try:
            doc = DocumentModel.objects.get(id=document_id)
            return self._model_to_document(doc)
        except DocumentModel.DoesNotExist:
            return None

    def get_all_documents(self) -> list[DocumentSummary]:
        """
        Get all documents.

        Returns:
            List of all document summaries
        """
        docs = DocumentModel.objects.all().order_by("-created_at")
        return [self._model_to_summary(doc) for doc in docs]

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document by ID.

        Args:
            document_id: The document ID to delete

        Returns:
            True if deleted, False if not found
        """
        deleted_count, _ = DocumentModel.objects.filter(id=document_id).delete()
        return deleted_count > 0

    def count(self) -> int:
        """
        Count total documents.

        Returns:
            Total number of documents
        """
        return DocumentModel.objects.count()

    def search(
        self,
        query: str | None = None,
        file_types: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[DocumentSummary]:
        """
        Search documents by filters.

        Args:
            query: Text search query (searches filename and content)
            file_types: Filter by file types
            start_date: Filter by minimum date
            end_date: Filter by maximum date
            limit: Maximum number of results

        Returns:
            List of document summaries
        """
        queryset = DocumentModel.objects.all()

        if query:
            from django.db.models import Q

            queryset = queryset.filter(Q(filename__icontains=query) | Q(content__icontains=query))

        if file_types:
            queryset = queryset.filter(file_type__in=file_types)

        if start_date:
            queryset = queryset.filter(date_extracted__gte=start_date)

        if end_date:
            queryset = queryset.filter(date_extracted__lte=end_date)

        queryset = queryset.order_by("-created_at")[:limit]

        return [self._model_to_summary(doc) for doc in queryset]

    def _model_to_document(self, doc: DocumentModel) -> Document:
        """Convert Django model to Document."""
        metadata = DocumentMetadata(
            filename=doc.filename,
            file_type=doc.file_type,
            page_count=doc.page_count,
            date_extracted=doc.date_extracted,
        )

        return Document(
            id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            content=doc.content,
            date_extracted=doc.date_extracted,
            created_at=doc.created_at,
            metadata=metadata,
            file_path=doc.file_path,
            retrieval_index_status=doc.retrieval_index_status,
            retrieval_chunks_count=doc.retrieval_chunks_count,
            retrieval_index_progress=doc.retrieval_index_progress,
            retrieval_index_total=doc.retrieval_index_total,
            retrieval_index_backend=doc.retrieval_index_backend,
        )

    def _model_to_summary(self, doc: DocumentModel) -> DocumentSummary:
        """Convert Django model to DocumentSummary."""
        return DocumentSummary(
            id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            date_extracted=doc.date_extracted,
            created_at=doc.created_at,
            retrieval_index_status=doc.retrieval_index_status,
            retrieval_chunks_count=doc.retrieval_chunks_count,
            retrieval_index_progress=doc.retrieval_index_progress,
            retrieval_index_total=doc.retrieval_index_total,
            retrieval_index_backend=doc.retrieval_index_backend,
        )

    def update_ocr_status(
        self,
        document_id: str,
        ocr_status: str,
        ocr_file_path: str | None = None,
        has_text_layer: bool | None = None,
    ) -> bool:
        """
        Update OCR processing status for a document.

        Args:
            document_id: The document ID
            ocr_status: Status: pending, processing, completed, failed
            ocr_file_path: Path to OCR'd PDF (if completed)
            has_text_layer: Whether PDF has text layer

        Returns:
            True if updated, False if document not found
        """
        try:
            doc = DocumentModel.objects.get(id=document_id)
            doc.ocr_status = ocr_status  # type: ignore

            update_fields = ["ocr_status"]

            if ocr_file_path is not None:
                doc.ocr_file_path = ocr_file_path  # type: ignore
                update_fields.append("ocr_file_path")

            if has_text_layer is not None:
                doc.has_text_layer = has_text_layer  # type: ignore
                update_fields.append("has_text_layer")

            doc.save(update_fields=update_fields)  # type: ignore
            return True
        except DocumentModel.DoesNotExist:
            return False


# Singleton instance
_repository: DocumentRepository | None = None


def get_document_repository() -> DocumentRepository:
    """Get or create document repository singleton."""
    global _repository
    if _repository is None:
        _repository = DocumentRepository()
    return _repository
