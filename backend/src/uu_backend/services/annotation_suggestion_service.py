"""Service for generating AI annotation suggestions."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from asgiref.sync import sync_to_async

from uu_backend.models.annotation import AnnotationSuggestion, AnnotationType
from uu_backend.models.taxonomy import DocumentType, SchemaField
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.services.extraction_service import get_extraction_service
from uu_backend.services.azure_di_service import get_azure_di_service
from uu_backend.django_data.models import DocumentModel

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
        
        Uses extraction to predict field values, then maps predictions
        to bounding boxes using cached Azure DI analysis.
        
        Args:
            document_id: Document ID
            document_type: Document type with schema
            
        Returns:
            List of annotation suggestions
        """
        logger.info(f"Generating annotation suggestions for document {document_id}")
        
        # Get document (wrap sync ORM call)
        document = await sync_to_async(self.doc_repo.get_document)(document_id)
        if not document:
            logger.error(f"Document not found: {document_id}")
            return []
        
        # Run extraction to get field values
        try:
            # Wrap sync extraction in sync_to_async
            extraction_result = await sync_to_async(self.extraction_service.extract_structured)(
                document_id=document_id
            )
            
            logger.info(f"Extraction returned {len(extraction_result.fields)} fields")
            
            # Get Azure DI analysis (prefer cached) - wrap sync ORM call
            azure_di_lines = await sync_to_async(self._get_azure_di_lines)(document_id, document.file_type)
            logger.info(f"Got {len(azure_di_lines)} lines from Azure DI")
            
            # Convert extraction results to suggestions with locations
            suggestions = []
            
            # Flatten nested extraction results (e.g., line_items array)
            flat_fields = self._flatten_extraction_fields(extraction_result.fields)
            logger.info(f"Flattened to {len(flat_fields)} field values")
            
            for field_name, value, instance_num in flat_fields:
                if value is None or value == "":
                    continue
                    
                suggestion = self._create_suggestion(
                    document=document,
                    field_name=field_name,
                    value=str(value),
                    instance_num=instance_num,
                    azure_di_lines=azure_di_lines
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
    
    def _get_azure_di_lines(self, document_id: str, file_type: str) -> list[dict]:
        """Get Azure DI lines from cached analysis or run fresh analysis.
        
        Azure DI returns coordinates in inches. We convert to pixels using 72 DPI
        to match the PDF rendering coordinate system.
        """
        # Standard PDF DPI - Azure DI returns inches, we need pixels
        DPI = 72.0
        
        try:
            # Try to get cached analysis from database
            doc_model = DocumentModel.objects.filter(id=document_id).first()
            if doc_model and doc_model.azure_di_analysis:
                lines = []
                for page in doc_model.azure_di_analysis.get("pages", []):
                    page_num = page.get("page_number", 1)
                    for line in page.get("lines", []):
                        polygon = line.get("bbox", [])
                        if polygon:
                            # Handle dict format from cache
                            x_coords = [p["x"] if isinstance(p, dict) else p[0] for p in polygon]
                            y_coords = [p["y"] if isinstance(p, dict) else p[1] for p in polygon]
                            
                            # Convert from inches to pixels (72 DPI standard)
                            x_min = min(x_coords) * DPI
                            y_min = min(y_coords) * DPI
                            width = (max(x_coords) - min(x_coords)) * DPI
                            height = (max(y_coords) - min(y_coords)) * DPI
                            
                            lines.append({
                                "text": line.get("text", ""),
                                "page": page_num,
                                "x": x_min,
                                "y": y_min,
                                "width": width,
                                "height": height
                            })
                return lines
        except Exception as e:
            logger.error(f"Error getting cached Azure DI analysis: {e}")
        
        return []
    
    def _flatten_extraction_fields(self, fields: list) -> list[tuple[str, Any, int]]:
        """
        Flatten nested extraction fields into (field_name, value, instance_num) tuples.
        
        E.g., line_items: [{quantity: 1, description: "foo"}, {quantity: 2}]
        becomes: [("line_items.quantity", "1", 1), ("line_items.description", "foo", 1), 
                  ("line_items.quantity", "2", 2)]
        """
        result = []
        
        for field in fields:
            field_name = field.field_name
            value = field.value
            
            if isinstance(value, list):
                # Array field - iterate with instance numbers
                for idx, item in enumerate(value):
                    instance_num = idx + 1
                    if isinstance(item, dict):
                        # Array of objects
                        for key, val in item.items():
                            result.append((f"{field_name}.{key}", val, instance_num))
                    else:
                        # Array of primitives
                        result.append((field_name, item, instance_num))
            elif isinstance(value, dict):
                # Object field
                for key, val in value.items():
                    result.append((f"{field_name}.{key}", val, 1))
            else:
                # Simple field
                result.append((field_name, value, 0))
        
        return result
    
    def _create_suggestion(
        self,
        document: Any,
        field_name: str,
        value: str,
        instance_num: int,
        azure_di_lines: list[dict]
    ) -> Optional[AnnotationSuggestion]:
        """Create an annotation suggestion by finding the value in Azure DI lines."""
        try:
            # Find bounding box for this value
            bbox = self._find_text_bbox(value, azure_di_lines)
            
            if not bbox:
                logger.debug(f"Could not find bbox for '{value}' in field {field_name}")
                return None
            
            # Add instance_num to annotation_data
            annotation_data = {
                **bbox,
                "instance_num": instance_num
            } if instance_num > 0 else bbox
            
            return AnnotationSuggestion(
                id=str(uuid4()),
                document_id=document.id,
                field_name=field_name,
                value=value,
                annotation_type=AnnotationType.BBOX,
                annotation_data=annotation_data,
                confidence=0.8,
                text_snippet=value
            )
            
        except Exception as e:
            logger.error(f"Error creating suggestion for field {field_name}: {e}")
            return None
    
    def _find_text_bbox(self, search_text: str, lines: list[dict]) -> Optional[dict]:
        """
        Find bounding box for text in Azure DI lines.
        
        Strategies:
        1. Exact match on a single line
        2. Partial match (search text contained in line)
        3. Fuzzy match for numbers (ignore formatting differences)
        """
        if not search_text or not lines:
            return None
        
        search_lower = search_text.lower().strip()
        search_normalized = self._normalize_text(search_text)
        
        # Strategy 1: Exact match
        for line in lines:
            if line["text"].lower().strip() == search_lower:
                return {
                    "page": line["page"],
                    "x": line["x"],
                    "y": line["y"],
                    "width": line["width"],
                    "height": line["height"],
                    "text": line["text"]
                }
        
        # Strategy 2: Search text is contained in a line
        for line in lines:
            if search_lower in line["text"].lower():
                return {
                    "page": line["page"],
                    "x": line["x"],
                    "y": line["y"],
                    "width": line["width"],
                    "height": line["height"],
                    "text": line["text"]
                }
        
        # Strategy 3: Normalized match (good for numbers like "58,000" vs "58000")
        for line in lines:
            if self._normalize_text(line["text"]) == search_normalized:
                return {
                    "page": line["page"],
                    "x": line["x"],
                    "y": line["y"],
                    "width": line["width"],
                    "height": line["height"],
                    "text": line["text"]
                }
        
        # Strategy 4: Partial normalized match
        for line in lines:
            if search_normalized in self._normalize_text(line["text"]):
                return {
                    "page": line["page"],
                    "x": line["x"],
                    "y": line["y"],
                    "width": line["width"],
                    "height": line["height"],
                    "text": line["text"]
                }
        
        return None
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (remove punctuation, lowercase)."""
        return re.sub(r'[^\w]', '', text.lower())


# Singleton instance
_suggestion_service: Optional[AnnotationSuggestionService] = None


def get_annotation_suggestion_service() -> AnnotationSuggestionService:
    """Get or create annotation suggestion service singleton."""
    global _suggestion_service
    if _suggestion_service is None:
        _suggestion_service = AnnotationSuggestionService()
    return _suggestion_service
