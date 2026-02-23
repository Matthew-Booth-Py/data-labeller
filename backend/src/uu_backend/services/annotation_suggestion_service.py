"""Service for generating AI annotation suggestions."""

import io
import logging
import re
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from uu_backend.config import get_settings
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
    
    def suggest_annotations(
        self,
        document_id: str,
        document_type: DocumentType
    ) -> list[AnnotationSuggestion]:
        """
        Generate AI annotation suggestions for a document.
        
        Uses retrieval-vision extraction to get field values and the relevant
        page numbers, then runs Azure DI on exactly those pages to get line-level
        bounding boxes for positioning the suggestion overlays.
        """
        logger.info(f"Generating annotation suggestions for document {document_id}")
        
        document = self.doc_repo.get_document(document_id)
        if not document:
            logger.error(f"Document not found: {document_id}")
            return []
        
        try:
            # Retrieval-vision finds the right pages, renders them, extracts values.
            # source_page_numbers tells us which PDF pages were actually used.
            extraction_result = self.extraction_service.extract_structured_with_retrieval_vision(
                document_id=document_id
            )
            
            logger.info(f"Extraction returned {len(extraction_result.fields)} fields")
            logger.info(f"Source pages from extraction: {extraction_result.source_page_numbers}")
            
            # Run Azure DI on the same pages the LLM saw
            azure_di_lines = self._get_azure_di_lines_for_pages(
                document_id=document_id,
                file_type=document.file_type,
                page_numbers=extraction_result.source_page_numbers,
            )
            logger.info(f"Got {len(azure_di_lines)} lines from Azure DI on pages {extraction_result.source_page_numbers}")
            
            # Convert extraction results to suggestions with locations
            suggestions = []
            
            # Flatten nested extraction results (e.g., line_items array)
            flat_fields = self._flatten_extraction_fields(extraction_result.fields)
            logger.info(f"Flattened to {len(flat_fields)} field values")
            
            # Track used line indices to avoid matching the same bbox twice
            used_line_indices: set[int] = set()
            
            for field_name, value, instance_num in flat_fields:
                if value is None or value == "":
                    continue
                    
                suggestion = self._create_suggestion(
                    document=document,
                    field_name=field_name,
                    value=str(value),
                    instance_num=instance_num,
                    azure_di_lines=azure_di_lines,
                    used_line_indices=used_line_indices
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
    
    def _get_azure_di_lines_for_pages(
        self,
        document_id: str,
        file_type: str,
        page_numbers: list[int],
    ) -> list[dict]:
        """
        Run Azure DI on specific PDF pages and return lines with percentage coordinates.
        
        We extract just the requested pages from the PDF (to avoid sending the whole
        document to Azure DI), analyze them, and convert inch coordinates to percentages
        so they match the percentage-based overlay positioning in the frontend.
        
        Page numbers in the returned lines reflect the original PDF page numbers,
        not the position within the extracted sub-document.
        """
        if not page_numbers or file_type.lower() != 'pdf':
            return []
        
        try:
            settings = get_settings()
            file_path = Path(f"{settings.file_storage_path}/{document_id}.{file_type.lower()}")
            if not file_path.exists():
                logger.error(f"PDF file not found: {file_path}")
                return []
            
            from pypdf import PdfReader, PdfWriter
            
            reader = PdfReader(str(file_path))
            total_pages = len(reader.pages)
            
            # Build a sub-PDF containing only the requested pages,
            # keeping a map from sub-doc page index → original page number
            writer = PdfWriter()
            sub_page_to_original: dict[int, int] = {}  # 1-indexed sub page → original page num
            
            for orig_page_num in sorted(set(page_numbers)):
                zero_idx = orig_page_num - 1
                if 0 <= zero_idx < total_pages:
                    writer.add_page(reader.pages[zero_idx])
                    sub_idx = len(writer.pages)  # 1-indexed position just added
                    sub_page_to_original[sub_idx] = orig_page_num
            
            if not sub_page_to_original:
                logger.warning(f"None of the requested pages {page_numbers} exist in PDF ({total_pages} pages)")
                return []
            
            # Write sub-PDF to a buffer and send to Azure DI
            buffer = io.BytesIO()
            writer.write(buffer)
            buffer.seek(0)
            
            logger.info(f"Sending {len(sub_page_to_original)} pages to Azure DI: {sorted(sub_page_to_original.values())}")
            
            poller = self.azure_di_service.client.begin_analyze_document(
                "prebuilt-read",
                document=buffer,
            )
            result = poller.result()
            
            lines = []
            for page in result.pages:
                # Map sub-doc page number back to original PDF page number
                orig_num = sub_page_to_original.get(page.page_number, page.page_number)
                page_w = page.width or 0
                page_h = page.height or 0
                
                if not page_w or not page_h:
                    continue
                
                for line in page.lines:
                    polygon = line.polygon or []
                    if not polygon:
                        continue
                    
                    x_coords = [p.x for p in polygon]
                    y_coords = [p.y for p in polygon]
                    
                    # Convert from inches to percentage of page dimensions
                    x_pct = (min(x_coords) / page_w) * 100
                    y_pct = (min(y_coords) / page_h) * 100
                    w_pct = ((max(x_coords) - min(x_coords)) / page_w) * 100
                    h_pct = ((max(y_coords) - min(y_coords)) / page_h) * 100
                    
                    lines.append({
                        "text": line.content,
                        "page": orig_num,
                        "x": x_pct,
                        "y": y_pct,
                        "width": w_pct,
                        "height": h_pct,
                    })
            
            logger.info(f"Azure DI returned {len(lines)} lines across {len(sub_page_to_original)} pages")
            return lines
            
        except Exception as e:
            logger.error(f"Error running Azure DI on pages {page_numbers}: {e}", exc_info=True)
            return []
    
    def _flatten_extraction_fields(self, fields: list) -> list[tuple[str, Any, int]]:
        """
        Flatten nested extraction fields into (field_name, value, instance_num) tuples.
        
        E.g., line_items: [{quantity: 1, description: "foo"}, {quantity: 2}]
        becomes: [("line_items.quantity", "1", 1), ("line_items.description", "foo", 1), 
                  ("line_items.quantity", "2", 2)]
        
        Also handles deeply nested structures like:
        policy_coverages_table[0].limits[0].amount
        """
        result = []
        
        for field in fields:
            field_name = field.field_name
            value = field.value
            self._flatten_value(field_name, value, 0, result)
        
        return result
    
    def _flatten_value(
        self, 
        prefix: str, 
        value: Any, 
        instance_num: int, 
        result: list[tuple[str, Any, int]]
    ) -> None:
        """Recursively flatten a value into field tuples."""
        if value is None or value == "":
            return
            
        if isinstance(value, list):
            # Array - iterate with instance numbers
            for idx, item in enumerate(value):
                item_instance = idx + 1
                if isinstance(item, dict):
                    # Array of objects - flatten each property
                    for key, val in item.items():
                        self._flatten_value(f"{prefix}.{key}", val, item_instance, result)
                else:
                    # Array of primitives
                    result.append((prefix, str(item), item_instance))
        elif isinstance(value, dict):
            # Object - flatten each property
            for key, val in value.items():
                self._flatten_value(f"{prefix}.{key}", val, instance_num, result)
        else:
            # Simple value - add to result
            result.append((prefix, str(value), instance_num))
    
    def _create_suggestion(
        self,
        document: Any,
        field_name: str,
        value: str,
        instance_num: int,
        azure_di_lines: list[dict],
        used_line_indices: set[int]
    ) -> Optional[AnnotationSuggestion]:
        """Create an annotation suggestion by finding the value in Azure DI lines."""
        try:
            # Find bounding box for this value, avoiding already-used lines
            bbox, line_idx = self._find_text_bbox(value, azure_di_lines, used_line_indices)
            
            if not bbox:
                logger.debug(f"Could not find bbox for '{value}' in field {field_name}")
                return None
            
            # Mark this line as used so it won't match again
            if line_idx is not None:
                used_line_indices.add(line_idx)
            
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
    
    def _find_text_bbox(
        self, 
        search_text: str, 
        lines: list[dict],
        used_line_indices: set[int]
    ) -> tuple[Optional[dict], Optional[int]]:
        """
        Find bounding box for text in Azure DI lines.
        
        Skips lines that have already been used (by index) to avoid
        matching the same physical location twice for repeated values.
        
        Returns:
            Tuple of (bbox_dict, line_index) or (None, None) if not found
        
        Strategies:
        1. Exact match on a single line
        2. Partial match (search text contained in line)
        3. Fuzzy match for numbers (ignore formatting differences)
        """
        if not search_text or not lines:
            return None, None
        
        search_lower = search_text.lower().strip()
        search_normalized = self._normalize_text(search_text)
        
        def make_bbox(line: dict) -> dict:
            return {
                "page": line["page"],
                "x": line["x"],
                "y": line["y"],
                "width": line["width"],
                "height": line["height"],
                "text": line["text"]
            }
        
        # Strategy 1: Exact match
        for idx, line in enumerate(lines):
            if idx in used_line_indices:
                continue
            if line["text"].lower().strip() == search_lower:
                return make_bbox(line), idx
        
        # Strategy 2: Search text is contained in a line
        for idx, line in enumerate(lines):
            if idx in used_line_indices:
                continue
            if search_lower in line["text"].lower():
                return make_bbox(line), idx
        
        # Strategy 3: Normalized match (good for numbers like "58,000" vs "58000")
        for idx, line in enumerate(lines):
            if idx in used_line_indices:
                continue
            if self._normalize_text(line["text"]) == search_normalized:
                return make_bbox(line), idx
        
        # Strategy 4: Partial normalized match
        for idx, line in enumerate(lines):
            if idx in used_line_indices:
                continue
            if search_normalized in self._normalize_text(line["text"]):
                return make_bbox(line), idx
        
        return None, None
    
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
