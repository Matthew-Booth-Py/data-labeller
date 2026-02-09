"""LLM-based document classification service."""

import json
from typing import Optional

from openai import AsyncOpenAI

from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.taxonomy import Classification, DocumentType


class ClassificationService:
    """Service for auto-classifying documents using LLM."""

    def __init__(self):
        self.client = AsyncOpenAI()
        self.model = "gpt-5-mini"

    async def classify_document(
        self, 
        document_id: str,
        auto_save: bool = True
    ) -> dict:
        """
        Classify a document using LLM.
        
        Args:
            document_id: The document to classify
            auto_save: If True, save the classification to database
            
        Returns:
            Dictionary with classification result including:
            - document_type_id: The assigned type ID
            - document_type_name: The assigned type name
            - confidence: Confidence score
            - reasoning: Explanation for the classification
        """
        sqlite_client = get_sqlite_client()
        vector_store = get_vector_store()
        
        # Get document
        document = vector_store.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Get all document types
        doc_types = sqlite_client.list_document_types()
        if not doc_types:
            raise ValueError("No document types defined. Create document types first.")
        
        # Build type descriptions for the prompt
        type_descriptions = []
        for dt in doc_types:
            desc = f"- **{dt.name}** (ID: {dt.id})"
            if dt.description:
                desc += f": {dt.description}"
            if dt.schema_fields:
                field_names = [f.name for f in dt.schema_fields[:5]]  # Show first 5 fields
                desc += f"\n  Typical fields: {', '.join(field_names)}"
            type_descriptions.append(desc)
        
        types_text = "\n".join(type_descriptions)
        
        # Prepare document content (truncate if too long)
        content = document.content or ""
        if len(content) > 8000:
            content = content[:4000] + "\n\n... [content truncated] ...\n\n" + content[-4000:]
        
        system_prompt = """You are a document classification expert. Your task is to analyze a document and classify it into one of the predefined document types.

Analyze the document's content, structure, and key characteristics to determine the most appropriate classification.

Respond in JSON format:
{
    "document_type_id": "the ID of the matching document type",
    "document_type_name": "the name of the matching document type",
    "confidence": 0.0-1.0 confidence score,
    "reasoning": "brief explanation of why this classification was chosen",
    "key_indicators": ["list", "of", "key", "indicators", "found"]
}

If the document doesn't clearly match any type, choose the closest match but set a lower confidence score.
"""

        user_prompt = f"""## Available Document Types

{types_text}

## Document to Classify

**Filename:** {document.filename}
**File Type:** {document.file_type}

**Content:**
```
{content}
```

Classify this document into one of the available types. Return your response as valid JSON."""

        print(f"\n{'='*60}")
        print("AUTO-CLASSIFICATION PROMPT")
        print(f"{'='*60}")
        print(f"Document: {document.filename}")
        print(f"Types available: {[t.name for t in doc_types]}")
        print(f"{'='*60}\n")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            print(f"Classification result: {result}")
            
            # Validate the document type exists
            matched_type = None
            for dt in doc_types:
                if dt.id == result.get("document_type_id") or dt.name.lower() == result.get("document_type_name", "").lower():
                    matched_type = dt
                    break
            
            if not matched_type:
                # Try fuzzy matching
                result_name = result.get("document_type_name", "").lower()
                for dt in doc_types:
                    if result_name in dt.name.lower() or dt.name.lower() in result_name:
                        matched_type = dt
                        break
            
            if not matched_type:
                raise ValueError(f"LLM returned unknown document type: {result.get('document_type_name')}")
            
            # Normalize result
            result["document_type_id"] = matched_type.id
            result["document_type_name"] = matched_type.name
            
            # Save classification if auto_save is enabled
            if auto_save:
                classification = sqlite_client.classify_document(
                    document_id=document_id,
                    document_type_id=matched_type.id,
                    confidence=result.get("confidence", 0.7),
                    labeled_by="auto-llm"
                )
                result["saved"] = True
            else:
                result["saved"] = False
            
            return result
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response: {e}")
        except Exception as e:
            print(f"Classification error: {e}")
            raise

    async def suggest_classification(self, document_id: str) -> dict:
        """
        Suggest a classification without saving it.
        
        This is useful for showing the user what the LLM thinks
        before they confirm.
        """
        return await self.classify_document(document_id, auto_save=False)


# Singleton instance
_classification_service: Optional[ClassificationService] = None


def get_classification_service() -> ClassificationService:
    """Get or create the classification service singleton."""
    global _classification_service
    if _classification_service is None:
        _classification_service = ClassificationService()
    return _classification_service
