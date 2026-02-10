"""Service for suggesting labels based on document analysis."""

import json
import logging
import uuid
from typing import Optional

from openai import OpenAI

from uu_backend.config import get_settings
from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.label_suggestion import (
    LabelSuggestion,
    LabelSuggestionRequest,
    LabelSuggestionResponse,
)

logger = logging.getLogger(__name__)

# Predefined colors for suggested labels
SUGGESTED_COLORS = [
    "#ef4444", "#f97316", "#f59e0b", "#eab308", "#84cc16",
    "#22c55e", "#10b981", "#14b8a6", "#06b6d4", "#0ea5e9",
    "#3b82f6", "#6366f1", "#8b5cf6", "#a855f7", "#d946ef",
    "#ec4899", "#f43f5e",
]

# Global Field Library - reusable extraction field definitions
GLOBAL_FIELD_LIBRARY = [
    {
        "name": "invoice_number",
        "type": "string",
        "prompt": "Extract the unique invoice identifier precisely as shown.",
    },
    {
        "name": "total_amount",
        "type": "number",
        "prompt": "The final payable amount including all taxes and fees.",
    },
    {
        "name": "vendor_tax_id",
        "type": "string",
        "prompt": "VAT or Tax Registration number of the issuing vendor.",
    },
    {
        "name": "due_date",
        "type": "date",
        "prompt": "The date by which the payment must be received.",
    },
    {
        "name": "line_items",
        "type": "array",
        "prompt": "List of all items purchased including description and quantity.",
    },
    {
        "name": "vendor_address",
        "type": "string",
        "prompt": "Full physical address of the vendor.",
    },
]


class LabelSuggestionService:
    """Service for analyzing documents and suggesting label types."""

    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.model = self.settings.openai_model
        self.sqlite = get_sqlite_client()
        self._color_index = 0

    def _get_next_color(self) -> str:
        """Get the next color from the palette."""
        color = SUGGESTED_COLORS[self._color_index % len(SUGGESTED_COLORS)]
        self._color_index += 1
        return color

    def suggest_labels(
        self,
        request: LabelSuggestionRequest,
    ) -> LabelSuggestionResponse:
        """Analyze documents and suggest relevant label types."""
        
        # Get sample documents
        vector_store = get_vector_store()
        all_doc_summaries = vector_store.get_all_documents()
        
        print(f"\n{'='*60}")
        print("LABEL SUGGESTION REQUEST")
        print(f"{'='*60}")
        print(f"Total documents in vector store: {len(all_doc_summaries)}")
        print(f"Document IDs filter: {request.document_ids}")
        print(f"Sample size: {request.sample_size}")
        
        # Filter by document_ids if provided (for project-specific suggestions)
        if request.document_ids:
            all_doc_summaries = [
                doc for doc in all_doc_summaries 
                if doc.id in request.document_ids
            ]
            print(f"After filtering: {len(all_doc_summaries)} documents")
            print(f"Filtered document names: {[doc.filename for doc in all_doc_summaries]}")
        
        if not all_doc_summaries:
            return LabelSuggestionResponse(
                suggestions=[],
                documents_analyzed=0,
                model=self.model,
            )
        
        # Sample document summaries
        sample_summaries = all_doc_summaries[:request.sample_size]
        print(f"Analyzing documents: {[doc.filename for doc in sample_summaries]}")
        print(f"{'='*60}\n")
        
        # Get existing labels to avoid duplicates
        existing_labels = []
        if request.existing_labels:
            existing_labels = self.sqlite.list_labels()
        
        existing_label_names = [l.name.lower() for l in existing_labels]
        
        # Build document content for analysis by fetching full documents
        doc_contents = []
        for summary in sample_summaries:
            full_doc = vector_store.get_document(summary.id)
            if full_doc:
                content = full_doc.content or ""
                # Truncate to avoid token limits
                if len(content) > 3000:
                    content = content[:3000] + "..."
                doc_contents.append({
                    "name": full_doc.filename,
                    "content": content,
                })
        
        # Check if we have any documents with content
        if not doc_contents:
            return LabelSuggestionResponse(
                suggestions=[],
                documents_analyzed=0,
                model=self.model,
            )
        
        # Build the prompt
        existing_labels_text = ""
        if existing_labels:
            existing_labels_text = "\n\nExisting labels (do NOT suggest these again):\n"
            for label in existing_labels:
                existing_labels_text += f"- {label.name}"
                if label.description:
                    existing_labels_text += f": {label.description}"
                existing_labels_text += "\n"
        
        # Build global field library context
        field_library_text = "\n\nGlobal Field Library (reference for field naming conventions and extraction patterns):\n"
        for field in GLOBAL_FIELD_LIBRARY:
            field_library_text += f"- {field['name']} ({field['type']}): \"{field['prompt']}\"\n"
        
        system_prompt = f"""You are an expert at analyzing documents and identifying what types of entities, data, and information should be labeled/extracted.

Your task is to analyze the provided documents and suggest label types that would be useful for annotation and data extraction.
{existing_labels_text}
{field_library_text}

Use the Global Field Library above as reference for:
- Naming conventions (snake_case for field names)
- How to write clear, actionable extraction prompts
- Common field types used in document processing

For each suggested label, provide:
1. A clear, concise name (e.g., "Person", "Date", "Amount", "Organization", "Address")
2. A description explaining what text should be labeled with this type (similar style to the field library prompts)
3. Reasoning for why this label is useful for these documents
4. 2-3 example text snippets from the documents that would match this label
5. A confidence score (0.0 to 1.0) based on how frequently this type appears

Focus on:
- Named entities (people, organizations, locations)
- Dates and times
- Monetary amounts and numbers
- Document-specific fields (invoice numbers, case IDs, etc.)
- Key terminology specific to the document domain

Return your suggestions as JSON:
{{
  "suggestions": [
    {{
      "name": "Label Name",
      "description": "What this label is for",
      "reasoning": "Why this label is useful",
      "examples": ["example 1", "example 2"],
      "confidence": 0.85
    }}
  ]
}}

Suggest 5-10 labels that would be most useful for these documents."""

        user_prompt = "Analyze these documents and suggest label types:\n\n"
        for i, doc in enumerate(doc_contents, 1):
            user_prompt += f"--- Document {i}: {doc['name']} ---\n{doc['content']}\n\n"

        print(f"\n{'='*60}")
        print(f"LABEL SUGGESTION REQUEST: Analyzing {len(doc_contents)} documents")
        print(f"{'='*60}")

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
                name = item.get("name", "").strip()
                
                # Skip if name matches existing label
                if name.lower() in existing_label_names:
                    continue
                
                # Skip empty names
                if not name:
                    continue

                suggestions.append(LabelSuggestion(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=item.get("description", ""),
                    reasoning=item.get("reasoning", ""),
                    confidence=float(item.get("confidence", 0.7)),
                    source_examples=item.get("examples", [])[:5],
                    suggested_color=self._get_next_color(),
                ))

            print(f"Generated {len(suggestions)} label suggestions")

            return LabelSuggestionResponse(
                suggestions=suggestions,
                documents_analyzed=len(doc_contents),
                model=self.model,
            )

        except Exception as e:
            logger.error(f"Error generating label suggestions: {e}")
            print(f"Error generating label suggestions: {e}")
            return LabelSuggestionResponse(
                suggestions=[],
                documents_analyzed=len(doc_contents),
                model=self.model,
            )

    def accept_suggestion(
        self,
        suggestion: LabelSuggestion,
        color_override: Optional[str] = None,
        name_override: Optional[str] = None,
        description_override: Optional[str] = None,
    ):
        """Accept a suggestion and create a label from it."""
        from uu_backend.models.annotation import LabelCreate
        
        label_data = LabelCreate(
            name=name_override or suggestion.name,
            color=color_override or suggestion.suggested_color,
            description=description_override or suggestion.description,
        )
        
        return self.sqlite.create_label(label_data)


# Singleton instance
_label_suggestion_service: Optional[LabelSuggestionService] = None


def get_label_suggestion_service() -> LabelSuggestionService:
    """Get or create the label suggestion service singleton."""
    global _label_suggestion_service
    if _label_suggestion_service is None:
        _label_suggestion_service = LabelSuggestionService()
    return _label_suggestion_service
