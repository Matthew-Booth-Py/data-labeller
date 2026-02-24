"""Service for generating AI annotation suggestions."""

import logging
import re
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from uu_backend.config import get_settings
from uu_backend.models.annotation import AnnotationSuggestion, AnnotationType
from uu_backend.models.taxonomy import DocumentType
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.services.extraction_service import get_extraction_service

logger = logging.getLogger(__name__)


class AnnotationSuggestionService:
    """Service for generating AI-powered annotation suggestions."""
    
    def __init__(self):
        self.extraction_service = get_extraction_service()
        self.doc_repo = get_document_repository()
    
    def suggest_annotations(
        self,
        document_id: str,
        document_type: DocumentType
    ) -> list[AnnotationSuggestion]:
        """
        Generate AI annotation suggestions for a document.
        
        Uses retrieval-vision extraction to get field values and the relevant
        page numbers, then uses pdfplumber on those pages to get word-level
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
            
            # Extract positioned words on the same pages the LLM saw.
            positioned_words = self._get_pdf_words_for_pages(
                document_id=document_id,
                file_type=document.file_type,
                page_numbers=extraction_result.source_page_numbers,
            )
            logger.info(f"Got {len(positioned_words)} positioned words on pages {extraction_result.source_page_numbers}")
            
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
                # Skip empty arrays
                if isinstance(value, list) and len(value) == 0:
                    continue
                    
                suggestion = self._create_suggestion(
                    document=document,
                    field_name=field_name,
                    value=value,  # Keep original type (string or array)
                    instance_num=instance_num,
                    positioned_words=positioned_words,
                    used_line_indices=used_line_indices
                )
                
                if suggestion:
                    suggestions.append(suggestion)
                    logger.debug(f"Created suggestion for {field_name} = '{value}'")
                else:
                    logger.debug(f"Could not create suggestion for {field_name} = '{value}'")
            
            logger.info(f"Generated {len(suggestions)} suggestions for document {document_id}")
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating suggestions for document {document_id}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_pdf_words_for_pages(
        self,
        document_id: str,
        file_type: str,
        page_numbers: list[int],
    ) -> list[dict]:
        """
        Extract word-level text and bounding boxes from selected PDF pages.
        """
        if not page_numbers or file_type.lower() != 'pdf':
            return []
        
        try:
            settings = get_settings()
            file_path = Path(f"{settings.file_storage_path}/{document_id}.{file_type.lower()}")
            if not file_path.exists():
                logger.error(f"PDF file not found: {file_path}")
                return []
            
            words = self._extract_with_pdfplumber(file_path, page_numbers)
            logger.info(f"Using pdfplumber results: {len(words)} words from {len(page_numbers)} pages")
            return words
            
        except Exception as e:
            logger.error(f"Error extracting text from pages {page_numbers}: {e}", exc_info=True)
            return []
    
    def _extract_with_pdfplumber(self, file_path: Path, page_numbers: list[int]) -> list[dict]:
        """Extract text + bounding boxes using pdfplumber (for selectable text PDFs).
        
        Returns word-level bounding boxes (not line-level) for more precise matching.
        """
        import pdfplumber
        
        all_words = []
        logger.info(f"Trying pdfplumber for {len(page_numbers)} pages: {sorted(set(page_numbers))}")
        
        with pdfplumber.open(str(file_path)) as pdf:
            total_pages = len(pdf.pages)
            
            for page_num in sorted(set(page_numbers)):
                zero_idx = page_num - 1
                if not (0 <= zero_idx < total_pages):
                    continue
                
                page = pdf.pages[zero_idx]
                page_w = float(page.width)
                page_h = float(page.height)
                
                # Extract words with individual bounding boxes
                words = page.extract_words(x_tolerance=3, y_tolerance=3)
                
                if not words:
                    continue
                
                # Keep each word as a separate "line" for precise matching
                for word in words:
                    all_words.append({
                        "text": word['text'],
                        "page": page_num,
                        "x": (word['x0'] / page_w) * 100,
                        "y": (word['top'] / page_h) * 100,
                        "width": ((word['x1'] - word['x0']) / page_w) * 100,
                        "height": ((word['bottom'] - word['top']) / page_h) * 100,
                    })
        
        logger.debug(f"pdfplumber extracted {len(all_words)} words from {len(page_numbers)} pages")
        return all_words
    
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
        result: list[tuple[str, Any, int]],
        is_row_item: bool = False
    ) -> None:
        """
        Recursively flatten a value into field tuples.
        
        Key distinction:
        - "Row arrays" (array of objects/dicts): Each item is a row, flatten into separate instances
        - "Leaf arrays" (array of primitives within a row): Keep as atomic value (e.g., hierarchy_path)
        
        Args:
            prefix: Field name prefix (e.g., "table.field")
            value: The value to flatten
            instance_num: Current instance/row number
            result: Output list of (field_name, value, instance_num) tuples
            is_row_item: True if we're processing fields within a row (changes array handling)
        """
        if value is None or value == "":
            return
            
        if isinstance(value, list):
            if not value:
                return
                
            # Check if this is an array of objects (row array) vs array of primitives (leaf array)
            first_item = value[0]
            is_row_array = isinstance(first_item, dict)
            
            if is_row_array:
                # Array of objects - each item is a row, flatten with instance numbers
                for idx, item in enumerate(value):
                    item_instance = idx + 1
                    for key, val in item.items():
                        # Process row fields with is_row_item=True so nested arrays are kept atomic
                        self._flatten_value(f"{prefix}.{key}", val, item_instance, result, is_row_item=True)
            elif is_row_item:
                # Leaf array within a row (e.g., hierarchy_path: ["Parent", "Child"])
                # Keep as atomic value - this is a single field value, not multiple rows
                result.append((prefix, value, instance_num))
            else:
                # Top-level array of primitives (rare case) - flatten as separate values
                for idx, item in enumerate(value):
                    result.append((prefix, str(item), idx + 1))
                    
        elif isinstance(value, dict):
            # Object - flatten each property
            for key, val in value.items():
                self._flatten_value(f"{prefix}.{key}", val, instance_num, result, is_row_item=is_row_item)
        else:
            # Simple value - add to result
            result.append((prefix, str(value), instance_num))
    
    def _create_suggestion(
        self,
        document: Any,
        field_name: str,
        value: Any,  # Can be string or list (for hierarchy_path etc.)
        instance_num: int,
        positioned_words: list[dict],
        used_line_indices: set[int]
    ) -> Optional[AnnotationSuggestion]:
        """
        Create an annotation suggestion by finding the value in positioned words.
        
        For array values (like hierarchy_path), uses the LEAF element (last in array)
        to find the bounding box, but stores the FULL array as the annotation value.
        This ensures ground truth matches the extraction schema exactly.
        """
        try:
            # Determine search text and stored value
            # For arrays, search using leaf element but store full array
            if isinstance(value, list):
                if not value:
                    return None
                search_text = str(value[-1])  # Use leaf (last element) for bbox search
                stored_value = value  # Store the full array
                text_snippet = " > ".join(str(v) for v in value)  # Display as path
            else:
                search_text = str(value)
                stored_value = value
                text_snippet = str(value)
            
            # Find bounding box for the search text, avoiding already-used lines
            bbox, line_idx = self._find_text_bbox(search_text, positioned_words, used_line_indices)
            
            if not bbox:
                logger.debug(f"Could not find bbox for '{search_text}' in field {field_name}")
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
                value=stored_value,  # Store original type (string or array)
                annotation_type=AnnotationType.BBOX,
                annotation_data=annotation_data,
                confidence=0.8,
                text_snippet=text_snippet
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
        Find bounding box for text, supporting both word-level and phrase matching.
        
        For multi-word search text, finds consecutive words and merges their bounding boxes.
        Skips words/phrases that have already been used to avoid duplicates.
        
        Returns:
            Tuple of (bbox_dict, line_index) or (None, None) if not found
        """
        if not search_text or not lines:
            return None, None
        
        search_lower = search_text.lower().strip()
        search_words = search_lower.split()
        search_normalized = self._normalize_text(search_text)
        
        def make_bbox(word: dict) -> dict:
            return {
                "page": word["page"],
                "x": word["x"],
                "y": word["y"],
                "width": word["width"],
                "height": word["height"],
                "text": word["text"]
            }
        
        def merge_word_bboxes(word_list: list[dict]) -> dict:
            """Merge multiple word bounding boxes into one."""
            if len(word_list) == 1:
                return make_bbox(word_list[0])
            
            # All words should be on same page
            page = word_list[0]["page"]
            
            # Calculate merged bounding box
            min_x = min(w["x"] for w in word_list)
            min_y = min(w["y"] for w in word_list)
            max_x = max(w["x"] + w["width"] for w in word_list)
            max_y = max(w["y"] + w["height"] for w in word_list)
            
            return {
                "page": page,
                "x": min_x,
                "y": min_y,
                "width": max_x - min_x,
                "height": max_y - min_y,
                "text": " ".join(w["text"] for w in word_list)
            }
        
        # Strategy 1: Single-word exact match
        if len(search_words) == 1:
            for idx, word in enumerate(lines):
                if idx in used_line_indices:
                    continue
                if word["text"].lower().strip() == search_lower:
                    return make_bbox(word), idx
        
        # Strategy 2: Multi-word consecutive match
        if len(search_words) > 1:
            for start_idx in range(len(lines) - len(search_words) + 1):
                if start_idx in used_line_indices:
                    continue
                
                # Check if consecutive words match
                consecutive_words = lines[start_idx:start_idx + len(search_words)]
                
                # Skip if any word in sequence is already used
                if any((start_idx + i) in used_line_indices for i in range(len(search_words))):
                    continue
                
                # Check if words are on same page and close together (same line)
                if len(set(w["page"] for w in consecutive_words)) > 1:
                    continue
                
                # Check if y-coordinates are similar (within 5% tolerance for same line)
                y_coords = [w["y"] for w in consecutive_words]
                if max(y_coords) - min(y_coords) > 5:
                    continue
                
                # Check text match
                consecutive_text = " ".join(w["text"].lower() for w in consecutive_words)
                if consecutive_text == search_lower:
                    return merge_word_bboxes(consecutive_words), start_idx
        
        # Strategy 3: Normalized single-word match
        if len(search_words) == 1:
            for idx, word in enumerate(lines):
                if idx in used_line_indices:
                    continue
                if self._normalize_text(word["text"]) == search_normalized:
                    return make_bbox(word), idx
        
        # Strategy 4: Partial match for short search text (fallback)
        for idx, word in enumerate(lines):
            if idx in used_line_indices:
                continue
            if search_lower in word["text"].lower():
                return make_bbox(word), idx
        
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
