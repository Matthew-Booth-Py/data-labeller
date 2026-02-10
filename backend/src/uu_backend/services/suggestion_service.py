"""Service for generating annotation suggestions using hybrid LLM + ML approach."""

import json
import logging
import re
from typing import Optional

from openai import OpenAI

from uu_backend.config import get_settings
from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.suggestion import SuggestedAnnotation, SuggestionResponse
from uu_backend.services.ml_service import get_ml_service
from uu_backend.services.label_suggestion_service import GLOBAL_FIELD_LIBRARY

logger = logging.getLogger(__name__)


class SuggestionService:
    """Service for generating label suggestions using hybrid LLM + ML approach."""

    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.model = self.settings.openai_model
        self.sqlite = get_sqlite_client()
        self._ml_service = None

    @property
    def ml_service(self):
        """Lazy load ML service."""
        if self._ml_service is None:
            self._ml_service = get_ml_service()
        return self._ml_service
    
    def get_few_shot_examples(
        self, 
        label_ids: Optional[list[str]] = None,
        limit_per_label: int = 5
    ) -> list[dict]:
        """Get existing annotations as few-shot examples."""
        # Get all labels
        labels = self.sqlite.list_labels()
        if label_ids:
            labels = [l for l in labels if l.id in label_ids]
        
        examples = []
        for label in labels:
            # Get annotations for this label
            # We'll query all annotations and filter
            all_annotations = []
            
            # Get annotations across all documents
            # This is a simplified approach - in production you might want pagination
            try:
                # Get documents from vector store
                vector_store = get_vector_store()
                docs = vector_store.get_all_documents()
                
                for doc in docs:
                    doc_annotations = self.sqlite.list_annotations(
                        document_id=doc.id,
                        label_id=label.id
                    )
                    for ann in doc_annotations:
                        if ann.text:
                            all_annotations.append({
                                "label_name": label.name,
                                "label_id": label.id,
                                "text": ann.text,
                                "color": label.color,
                            })
                            if len(all_annotations) >= limit_per_label:
                                break
                    if len([a for a in all_annotations if a["label_id"] == label.id]) >= limit_per_label:
                        break
            except Exception as e:
                logger.warning(f"Error getting examples for label {label.name}: {e}")
                continue
            
            examples.extend(all_annotations[:limit_per_label])
        
        return examples
    
    def _extract_candidate_spans(
        self,
        document_content: str,
        max_spans: int = 100,
    ) -> list[dict]:
        """Extract candidate text spans from document for ML prediction."""
        spans = []

        # Extract named entities using simple patterns
        # Names (capitalized words)
        name_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b'
        for match in re.finditer(name_pattern, document_content):
            spans.append({
                "text": match.group(),
                "start_offset": match.start(),
                "end_offset": match.end(),
            })

        # Dates
        date_pattern = r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
        for match in re.finditer(date_pattern, document_content):
            spans.append({
                "text": match.group(),
                "start_offset": match.start(),
                "end_offset": match.end(),
            })

        # Money amounts
        money_pattern = r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|thousand))?'
        for match in re.finditer(money_pattern, document_content, re.IGNORECASE):
            spans.append({
                "text": match.group(),
                "start_offset": match.start(),
                "end_offset": match.end(),
            })

        # Percentages
        percent_pattern = r'\d+(?:\.\d+)?%'
        for match in re.finditer(percent_pattern, document_content):
            spans.append({
                "text": match.group(),
                "start_offset": match.start(),
                "end_offset": match.end(),
            })

        # Organizations (common patterns)
        org_pattern = r'\b[A-Z][a-z]*(?:\s+[A-Z][a-z]*)*(?:\s+(?:Inc|Corp|LLC|Ltd|Company|Corporation|Group|International))\b\.?'
        for match in re.finditer(org_pattern, document_content):
            spans.append({
                "text": match.group(),
                "start_offset": match.start(),
                "end_offset": match.end(),
            })

        # Remove duplicates and limit
        seen = set()
        unique_spans = []
        for span in spans:
            key = (span["start_offset"], span["end_offset"])
            if key not in seen:
                seen.add(key)
                unique_spans.append(span)

        return unique_spans[:max_spans]

    def generate_suggestions_ml(
        self,
        document_id: str,
        document_content: str,
        label_ids: Optional[list[str]] = None,
        max_suggestions: int = 20,
        min_confidence: float = 0.5,
    ) -> SuggestionResponse:
        """Generate suggestions using local ML model."""
        labels = self.sqlite.list_labels()
        label_map = {l.id: l for l in labels}

        if label_ids:
            labels = [l for l in labels if l.id in label_ids]

        # Extract candidate spans
        candidate_spans = self._extract_candidate_spans(document_content)

        if not candidate_spans:
            return SuggestionResponse(
                document_id=document_id,
                suggestions=[],
                examples_used=0,
                model="lightgbm-local",
            )

        # Get predictions for each span
        texts = [span["text"] for span in candidate_spans]
        predictions = self.ml_service.predict(texts, min_confidence=min_confidence)

        suggestions = []
        for pred in predictions:
            # Find the matching span
            span = next(
                (s for s in candidate_spans if s["text"] == pred["text"]),
                None
            )
            if not span:
                continue

            label = label_map.get(pred["label_id"])
            if not label:
                continue

            # Filter by label_ids if specified
            if label_ids and pred["label_id"] not in label_ids:
                continue

            # ML model doesn't provide key metadata yet
            suggestions.append(SuggestedAnnotation(
                label_id=pred["label_id"],
                label_name=label.name,
                text=pred["text"],
                start_offset=span["start_offset"],
                end_offset=span["end_offset"],
                confidence=pred["confidence"],
                reasoning="Predicted by local ML model",
                metadata=None,
            ))

        # Sort by confidence
        suggestions.sort(key=lambda x: x.confidence, reverse=True)

        return SuggestionResponse(
            document_id=document_id,
            suggestions=suggestions[:max_suggestions],
            examples_used=0,
            model="lightgbm-local",
        )

    def _overlaps_with_annotation(
        self,
        suggestion_start: int,
        suggestion_end: int,
        existing_annotations: list,
    ) -> bool:
        """Check if a suggestion overlaps with any existing annotation."""
        for ann in existing_annotations:
            ann_start = ann.start_offset
            ann_end = ann.end_offset
            if ann_start is None or ann_end is None:
                continue
            # Check for overlap: two ranges overlap if one starts before the other ends
            if suggestion_start < ann_end and suggestion_end > ann_start:
                return True
        return False

    def _filter_existing_annotations(
        self,
        response: SuggestionResponse,
        document_id: str,
    ) -> SuggestionResponse:
        """Filter out suggestions that overlap with existing annotations."""
        # Get existing annotations for this document
        existing_annotations = self.sqlite.list_annotations(document_id=document_id)
        
        if not existing_annotations:
            return response
        
        # Filter suggestions
        filtered_suggestions = [
            sug for sug in response.suggestions
            if not self._overlaps_with_annotation(
                sug.start_offset,
                sug.end_offset,
                existing_annotations,
            )
        ]
        
        filtered_count = len(response.suggestions) - len(filtered_suggestions)
        if filtered_count > 0:
            logger.info(f"Filtered out {filtered_count} suggestions that overlap with existing annotations")
        
        return SuggestionResponse(
            document_id=response.document_id,
            suggestions=filtered_suggestions,
            examples_used=response.examples_used,
            model=response.model,
        )

    def generate_suggestions(
        self,
        document_id: str,
        document_content: str,
        label_ids: Optional[list[str]] = None,
        max_suggestions: int = 20,
        min_confidence: float = 0.5,
        force_llm: bool = False,
    ) -> SuggestionResponse:
        """Generate annotation suggestions using hybrid approach.

        Uses local ML model when trained, falls back to LLM otherwise.
        """
        # Check if we can use local model
        if not force_llm and self.ml_service.should_use_local_model():
            logger.info("Using local ML model for suggestions")
            response = self.generate_suggestions_ml(
                document_id=document_id,
                document_content=document_content,
                label_ids=label_ids,
                max_suggestions=max_suggestions,
                min_confidence=min_confidence,
            )
        else:
            logger.info("Using LLM for suggestions (local model not ready)")
            response = self.generate_suggestions_llm(
                document_id=document_id,
                document_content=document_content,
                label_ids=label_ids,
                max_suggestions=max_suggestions,
                min_confidence=min_confidence,
            )
        
        # Filter out suggestions that already exist as annotations
        return self._filter_existing_annotations(response, document_id)

    def generate_suggestions_llm(
        self,
        document_id: str,
        document_content: str,
        label_ids: Optional[list[str]] = None,
        max_suggestions: int = 20,
        min_confidence: float = 0.5,
    ) -> SuggestionResponse:
        """Generate annotation suggestions using LLM."""

        # Get document classification and type for schema context
        classification = self.sqlite.get_classification(document_id)
        doc_type = None
        if classification:
            doc_type = self.sqlite.get_document_type(classification.document_type_id)
        
        # Get available labels
        labels = self.sqlite.list_labels()
        if label_ids:
            labels = [l for l in labels if l.id in label_ids]

        if not labels:
            return SuggestionResponse(
                document_id=document_id,
                suggestions=[],
                examples_used=0,
                model=self.model,
            )

        # Get few-shot examples
        examples = self.get_few_shot_examples(label_ids, limit_per_label=5)

        # Build the prompt with schema information
        labels_description_parts = []
        for label in labels:
            desc = f"- **{label.name}** (id: `{label.id}`): {label.description or 'Use this label for ' + label.name.lower() + ' entities'}"
            
            # Add property information for array fields
            if doc_type and doc_type.schema_fields:
                matching_field = next((f for f in doc_type.schema_fields if f.name == label.name), None)
                if matching_field and matching_field.type == "array" and matching_field.items and matching_field.items.type == "object":
                    props = matching_field.items.properties or {}
                    if props:
                        prop_names = ", ".join(props.keys())
                        desc += f"\n  → This is a TABLE field. For each value, specify the 'key' property: {prop_names}"
            
            labels_description_parts.append(desc)
        
        labels_description = "\n".join(labels_description_parts)
        
        # Build examples section grouped by label
        examples_text = ""
        if examples:
            examples_text = "\n## Examples of previously labeled text (learn from these patterns):\n"
            # Group by label
            by_label: dict[str, list[str]] = {}
            for ex in examples[:20]:  # Limit examples
                label_name = ex["label_name"]
                if label_name not in by_label:
                    by_label[label_name] = []
                by_label[label_name].append(ex["text"])
            
            for label_name, texts in by_label.items():
                examples_text += f'\n**{label_name}** examples:\n'
                for text in texts[:5]:
                    # Truncate long examples
                    display_text = text[:100] + "..." if len(text) > 100 else text
                    examples_text += f'  - "{display_text}"\n'
        else:
            examples_text = "\n## No existing annotations yet - use your best judgment based on label names.\n"
        
        # Build global field library reference
        field_library_text = "\n## Global Field Library (extraction patterns reference):\n"
        for field in GLOBAL_FIELD_LIBRARY:
            field_library_text += f"- **{field['name']}** ({field['type']}): \"{field['prompt']}\"\n"
        
        system_prompt = f"""You are an expert document annotator. Your task is to identify and extract text spans that match specific label categories.

## Available Labels (YOU MUST USE THESE EXACT LABEL IDs):
{labels_description}

{examples_text}

{field_library_text}
Use the Global Field Library above as a reference for common extraction patterns and field types you might encounter.

## Instructions:
1. Read the document carefully
2. Find text spans that match the label definitions above
3. Learn from the examples to understand what types of text belong to each label
4. Extract the EXACT text from the document (copy it precisely, including punctuation)
5. Only suggest annotations you are confident about (>= {min_confidence} confidence)

## Output Format:
Return a JSON object with an array of suggestions. Each suggestion must have:
- "text": The exact text copied from the document
- "label_id": One of the label IDs listed above (use the exact ID in backticks)
- "label_name": The human-readable label name
- "confidence": A number from 0.0 to 1.0
- "reasoning": Brief explanation of why this text matches the label
- "key": (OPTIONAL) For table/array labels, specify which property this value belongs to (e.g., "claim_item", "claim_amount")

```json
{{
  "suggestions": [
    {{
      "text": "exact text from document",
      "label_id": "use-exact-id-from-above",
      "label_name": "Label Name",
      "confidence": 0.85,
      "reasoning": "This matches because..."
    }}
  ]
}}
```

Provide up to {max_suggestions} high-quality suggestions."""

        user_prompt = f"""## Document to Analyze:

{document_content[:10000]}

---

Find all text spans in the document above that should be labeled with the labels I defined. Use the examples I provided to understand what kinds of text belong to each label category. Return your suggestions as JSON."""

        print(f"\n{'='*60}")
        print(f"LLM SUGGESTION REQUEST: {len(labels)} labels, {len(examples)} examples")
        print(f"{'='*60}")
        print(f"\n=== SYSTEM PROMPT ===\n{system_prompt}\n=== END SYSTEM PROMPT ===")
        print(f"\n=== USER PROMPT (first 2000 chars) ===\n{user_prompt[:2000]}...\n=== END USER PROMPT ===\n")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            suggestions = []
            for item in result.get("suggestions", []):
                # Find the text in the document to get offsets
                text = item.get("text", "")
                start_offset = document_content.find(text)
                
                if start_offset == -1:
                    # Try case-insensitive search
                    start_offset = document_content.lower().find(text.lower())
                    if start_offset != -1:
                        # Use the actual text from document
                        text = document_content[start_offset:start_offset + len(text)]
                
                if start_offset == -1:
                    logger.warning(f"Could not find suggested text in document: {text[:50]}...")
                    continue
                
                # Validate label exists
                label_id = item.get("label_id")
                label = next((l for l in labels if l.id == label_id), None)
                if not label:
                    # Try to find by name
                    label_name = item.get("label_name", "")
                    label = next((l for l in labels if l.name.lower() == label_name.lower()), None)
                
                if not label:
                    logger.warning(f"Unknown label: {label_id}")
                    continue
                
                confidence = float(item.get("confidence", 0.5))
                if confidence < min_confidence:
                    continue
                
                # Extract key if provided (for array/table fields)
                metadata = None
                if "key" in item and item["key"]:
                    metadata = {
                        "key": item["key"],
                        "value": text
                    }
                
                suggestions.append(SuggestedAnnotation(
                    label_id=label.id,
                    label_name=label.name,
                    text=text,
                    start_offset=start_offset,
                    end_offset=start_offset + len(text),
                    confidence=confidence,
                    reasoning=item.get("reasoning"),
                    metadata=metadata,
                ))
            
            # Sort by confidence descending
            suggestions.sort(key=lambda x: x.confidence, reverse=True)
            
            return SuggestionResponse(
                document_id=document_id,
                suggestions=suggestions[:max_suggestions],
                examples_used=len(examples),
                model=self.model,
            )
            
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            raise


# Singleton instance
_suggestion_service: Optional[SuggestionService] = None


def get_suggestion_service() -> SuggestionService:
    """Get or create the suggestion service singleton."""
    global _suggestion_service
    if _suggestion_service is None:
        _suggestion_service = SuggestionService()
    return _suggestion_service
