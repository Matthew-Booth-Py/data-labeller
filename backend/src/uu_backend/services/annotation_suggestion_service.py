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
    
    def _get_azure_di_lines_for_pages(
        self,
        document_id: str,
        file_type: str,
        page_numbers: list[int],
    ) -> list[dict]:
        """
        Extract text and bounding boxes from PDF pages.
        
        Strategy:
        1. Try pdfplumber first (fast, free, works for selectable text)
        2. Fall back to Azure DI if pdfplumber returns insufficient results
        
        Returns lines with percentage coordinates for overlay positioning.
        """
        if not page_numbers or file_type.lower() != 'pdf':
            return []
        
        try:
            settings = get_settings()
            file_path = Path(f"{settings.file_storage_path}/{document_id}.{file_type.lower()}")
            if not file_path.exists():
                logger.error(f"PDF file not found: {file_path}")
                return []
            
            # Try pdfplumber first
            pdfplumber_words = self._extract_with_pdfplumber(file_path, page_numbers)
            
            # Check if we got good results (at least 20 words per page on average)
            if len(pdfplumber_words) >= len(page_numbers) * 20:
                print(f"✅ Using pdfplumber: {len(pdfplumber_words)} words from {len(page_numbers)} pages")
                logger.info(f"Using pdfplumber results: {len(pdfplumber_words)} words from {len(page_numbers)} pages")
                return pdfplumber_words
            
            # Fall back to Azure DI for scanned/image-based content
            print(f"⚠️  pdfplumber insufficient ({len(pdfplumber_words)} words), falling back to Azure Document Intelligence")
            logger.info(f"pdfplumber found insufficient text ({len(pdfplumber_words)} words), falling back to Azure DI")
            return self._extract_with_azure_di(file_path, page_numbers)
            
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
    
    def _extract_with_azure_di(self, file_path: Path, page_numbers: list[int]) -> list[dict]:
        """Extract text + bounding boxes using Azure DI (for scanned/image-based PDFs)."""
        from pypdf import PdfReader, PdfWriter
        
        reader = PdfReader(str(file_path))
        total_pages = len(reader.pages)
        
        # Process each page SEPARATELY to avoid Azure DI dropping pages
        all_lines = []
        logger.info(f"Sending {len(page_numbers)} pages to Azure DI (individually): {sorted(set(page_numbers))}")
        
        for orig_page_num in sorted(set(page_numbers)):
            zero_idx = orig_page_num - 1
            if not (0 <= zero_idx < total_pages):
                logger.warning(f"Page {orig_page_num} does not exist in PDF ({total_pages} pages)")
                continue
            
            # Create a single-page PDF
            writer = PdfWriter()
            writer.add_page(reader.pages[zero_idx])
            
            buffer = io.BytesIO()
            writer.write(buffer)
            buffer.seek(0)
            
            logger.debug(f"Sending page {orig_page_num} to Azure DI ({len(buffer.getvalue())} bytes)")
            
            # Send this single page to Azure DI
            poller = self.azure_di_service.client.begin_analyze_document(
                "prebuilt-read",
                document=buffer,
            )
            result = poller.result()
            
            if not result.pages:
                logger.warning(f"Azure DI returned no results for page {orig_page_num}")
                continue
            
            # Should only have 1 page in response (since we sent 1 page)
            page = result.pages[0]
            page_w = page.width or 0
            page_h = page.height or 0
            
            logger.debug(f"Page {orig_page_num}: got {len(page.lines) if page.lines else 0} lines")
            
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
                
                all_lines.append({
                    "text": line.content,
                    "page": orig_page_num,  # Use original page number
                    "x": x_pct,
                    "y": y_pct,
                    "width": w_pct,
                    "height": h_pct,
                })
        
        logger.info(f"Azure DI returned {len(all_lines)} total lines across {len(page_numbers)} pages")
        return all_lines
    
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
