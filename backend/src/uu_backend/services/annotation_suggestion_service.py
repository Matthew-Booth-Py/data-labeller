"""Service for generating AI annotation suggestions."""

import json
import logging
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from uu_backend.models.annotation import AnnotationSuggestion, AnnotationType
from uu_backend.models.taxonomy import DocumentType, SchemaField
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.services.extraction_service import get_extraction_service
from uu_backend.services.azure_di_service import get_azure_di_service

logger = logging.getLogger(__name__)


class AnnotationSuggestionService:
    """Service for generating AI-powered annotation suggestions."""
    
    def __init__(self):
        self.extraction_service = get_extraction_service()
        self.azure_di_service = get_azure_di_service()
        self.doc_repo = get_document_repository()
    
    async def suggest_annotations(
        self,
        document_id: str,
        document_type: DocumentType
    ) -> list[AnnotationSuggestion]:
        """
        Generate AI annotation suggestions for a document.
        
        Args:
            document_id: Document ID
            document_type: Document type with schema
            
        Returns:
            List of annotation suggestions
        """
        logger.info(f"Generating annotation suggestions for document {document_id}")
        
        # Get document
        document = self.doc_repo.get_document(document_id)
        if not document:
            logger.error(f"Document not found: {document_id}")
            return []
        
        # Run extraction to get field values
        try:
            extraction_result = await self.extraction_service.extract_structured(
                document_id=document_id,
                document_type_id=document_type.id,
                schema_fields=document_type.schema_fields,
                system_prompt=document_type.system_prompt
            )
            
            # Get text with bounding boxes for PDFs using Azure DI
            text_with_bboxes = None
            if document.file_type.lower() == "pdf":
                from uu_backend.config import get_settings
                settings = get_settings()
                file_ext = f".{document.file_type}"
                file_path = settings.file_storage_path / f"{document_id}{file_ext}"
                
                if file_path.exists():
                    try:
                        # Analyze document with Azure DI
                        analysis = await self.azure_di_service.analyze_document(file_path)
                        # Convert Azure DI format to our text_with_bboxes format
                        text_with_bboxes = []
                        for page in analysis["pages"]:
                            for line in page["lines"]:
                                # Convert Azure polygon to our bbox format
                                polygon = line["bbox"]
                                if polygon:
                                    x_coords = [p.x for p in polygon]
                                    y_coords = [p.y for p in polygon]
                                    text_with_bboxes.append({
                                        "text": line["text"],
                                        "page": page["page_number"],
                                        "x": min(x_coords),
                                        "y": min(y_coords),
                                        "width": max(x_coords) - min(x_coords),
                                        "height": max(y_coords) - min(y_coords)
                                    })
                    except Exception as azure_error:
                        logger.error(f"Azure DI analysis error: {azure_error}")
                        text_with_bboxes = None
            
            # Convert extraction results to suggestions with locations
            suggestions = []
            
            for field in extraction_result.fields:
                suggestion = await self._create_suggestion_from_extraction(
                    document=document,
                    field_name=field.field_name,
                    value=field.value,
                    confidence=field.confidence or 0.8,
                    source_text=field.source_text,
                    text_with_bboxes=text_with_bboxes
                )
                
                if suggestion:
                    suggestions.append(suggestion)
            
            logger.info(f"Generated {len(suggestions)} suggestions for document {document_id}")
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating suggestions for document {document_id}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _create_suggestion_from_extraction(
        self,
        document: Any,
        field_name: str,
        value: Any,
        confidence: float,
        source_text: Optional[str],
        text_with_bboxes: Optional[dict]
    ) -> Optional[AnnotationSuggestion]:
        """
        Create an annotation suggestion from extraction result.
        
        Args:
            document: Document object
            field_name: Field name
            value: Extracted value
            confidence: Confidence score
            source_text: Source text from extraction
            text_with_bboxes: Text with bounding boxes from PDF
            
        Returns:
            AnnotationSuggestion or None
        """
        try:
            # Determine annotation type based on document type
            if document.file_type.lower() in ["txt", "docx"]:
                # Text span annotation
                annotation_type = AnnotationType.TEXT_SPAN
                annotation_data = self._find_text_span(
                    document.content,
                    source_text or str(value)
                )
            elif document.file_type.lower() == "pdf":
                # Bounding box annotation
                annotation_type = AnnotationType.BBOX
                annotation_data = self._find_bbox_in_pdf(
                    source_text or str(value),
                    text_with_bboxes
                )
            else:
                # Image - use full image bbox as placeholder
                annotation_type = AnnotationType.BBOX
                annotation_data = {
                    "page": 1,
                    "x": 0,
                    "y": 0,
                    "width": 100,
                    "height": 100,
                    "text": str(value)
                }
            
            if not annotation_data:
                logger.warning(f"Could not find location for field {field_name}")
                return None
            
            return AnnotationSuggestion(
                id=str(uuid4()),
                document_id=document.id,
                field_name=field_name,
                value=value,
                annotation_type=annotation_type,
                annotation_data=annotation_data,
                confidence=confidence,
                text_snippet=source_text or str(value)
            )
            
        except Exception as e:
            logger.error(f"Error creating suggestion for field {field_name}: {e}")
            return None
    
    def _find_text_span(self, content: str, search_text: str) -> Optional[dict]:
        """
        Find character offsets for text in document content.
        
        Args:
            content: Full document content
            search_text: Text to search for
            
        Returns:
            Dictionary with start, end, text or None
        """
        if not search_text or not content:
            return None
        
        # Simple substring search
        start = content.find(search_text)
        if start == -1:
            # Try case-insensitive search
            start = content.lower().find(search_text.lower())
            if start == -1:
                return None
        
        end = start + len(search_text)
        
        return {
            "start": start,
            "end": end,
            "text": content[start:end]
        }
    
    def _find_bbox_in_pdf(
        self,
        search_text: str,
        text_with_bboxes: Optional[dict]
    ) -> Optional[dict]:
        """
        Find bounding box for text in PDF using pdfplumber data.
        
        Args:
            search_text: Text to search for
            text_with_bboxes: PDF text with bounding boxes
            
        Returns:
            Dictionary with page, x, y, width, height or None
        """
        if not text_with_bboxes or not search_text:
            return None
        
        search_text_lower = search_text.lower().strip()
        
        for page_data in text_with_bboxes.get("pages", []):
            words = page_data.get("words", [])
            
            # Try to find matching word sequence
            for i, word in enumerate(words):
                # Check if this word starts the search text
                if search_text_lower.startswith(word["text"].lower()):
                    # Collect words that match the search text
                    matching_words = [word]
                    remaining_text = search_text_lower[len(word["text"]):].strip()
                    
                    j = i + 1
                    while remaining_text and j < len(words):
                        next_word = words[j]
                        if remaining_text.startswith(next_word["text"].lower()):
                            matching_words.append(next_word)
                            remaining_text = remaining_text[len(next_word["text"]):].strip()
                            j += 1
                        else:
                            break
                    
                    # If we matched enough of the text, return bbox
                    if len(remaining_text) < len(search_text_lower) * 0.3:  # 70% match
                        # Combine bounding boxes
                        x0 = min(w["x0"] for w in matching_words)
                        y0 = min(w["y0"] for w in matching_words)
                        x1 = max(w["x1"] for w in matching_words)
                        y1 = max(w["y1"] for w in matching_words)
                        
                        return {
                            "page": page_data["page"],
                            "x": x0,
                            "y": y0,
                            "width": x1 - x0,
                            "height": y1 - y0,
                            "text": search_text
                        }
        
        logger.warning(f"Could not find bbox for text: {search_text[:50]}...")
        return None


# Singleton instance
_suggestion_service: Optional[AnnotationSuggestionService] = None


def get_annotation_suggestion_service() -> AnnotationSuggestionService:
    """Get or create annotation suggestion service singleton."""
    global _suggestion_service
    if _suggestion_service is None:
        _suggestion_service = AnnotationSuggestionService()
    return _suggestion_service
