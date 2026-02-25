"""LLM-based document classification service."""

import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Literal

from asgiref.sync import sync_to_async
from openai import AsyncAzureOpenAI, AsyncOpenAI
from pydantic import BaseModel, Field

from uu_backend.config import get_settings
from uu_backend.llm.options import reasoning_options_for_model
from uu_backend.repositories import get_repository
from uu_backend.repositories.document_repository import get_document_repository

logger = logging.getLogger(__name__)

try:
    from pdf2image import convert_from_path
    from PIL import Image

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


class ClassificationService:
    """Service for auto-classifying documents using LLM."""

    def __init__(self):
        # Check if using Azure OpenAI or regular OpenAI
        use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"

        if use_azure:
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
            azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

            if not azure_endpoint or not azure_api_key:
                raise ValueError(
                    "Azure OpenAI enabled but missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY"
                )

            logger.info(f"Using Azure OpenAI for classification: {azure_endpoint}")
            self.client = AsyncAzureOpenAI(
                api_version=azure_api_version,
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
            )
        else:
            logger.info("Using OpenAI for classification")
            self.client = AsyncOpenAI()

        settings = get_settings()
        self.model = settings.effective_tagging_model

    async def classify_document(self, document_id: str, auto_save: bool = True) -> dict:
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
        repository = get_repository()
        document_repo = get_document_repository()

        # Get document (wrap sync call for async context)
        document = await sync_to_async(document_repo.get_document)(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Check if document has content OR is an image/PDF that we can process with vision API
        has_content = document.content and document.content.strip()
        is_visual_document = document.file_type.lower() in [
            "pdf",
            "png",
            "jpg",
            "jpeg",
            "gif",
            "webp",
        ]

        if not has_content and not is_visual_document:
            raise ValueError(
                f"Document {document_id} has no content and is not a visual document type. Try re-uploading the document."
            )

        # Get all document types (wrap sync call for async context)
        doc_types = await sync_to_async(repository.list_document_types)()
        if not doc_types:
            raise ValueError("No document types defined. Create document types first.")

        # Create a Pydantic schema for classification with document type as enum
        type_id_to_name = {dt.id: dt.name for dt in doc_types}
        type_ids = tuple(dt.id for dt in doc_types)

        # Build document type descriptions for the prompt
        type_descriptions = []
        for dt in doc_types:
            desc = f"### {dt.name} (ID: {dt.id})"
            if dt.description:
                desc += f"\n**Description:** {dt.description}"
            if dt.schema_fields:
                desc += f"\n**Expected Fields:** {', '.join(f.name for f in dt.schema_fields)}"
            type_descriptions.append(desc)

        types_text = "\n\n".join(type_descriptions)

        # Create Pydantic model for classification response with enum
        class ClassificationResponse(BaseModel):
            document_type_id: Literal[type_ids] = Field(
                description="The ID of the matching document type"
            )
            confidence: float = Field(
                description="Confidence score between 0.0 and 1.0", ge=0.0, le=1.0
            )
            reasoning: str = Field(
                description="Brief explanation of why this classification was chosen"
            )
            key_indicators: list[str] = Field(
                description="List of key indicators found in the document"
            )

        classification_schema = {
            "type": "object",
            "properties": {
                "document_type_id": {
                    "type": "string",
                    "enum": list(type_ids),
                    "description": "The ID of the matching document type",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Confidence score between 0.0 and 1.0",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of why this classification was chosen",
                },
                "key_indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of key indicators found in the document",
                },
            },
            "required": ["document_type_id", "confidence", "reasoning", "key_indicators"],
            "additionalProperties": False,
        }

        content = document.content or ""
        if len(content) > 8000:
            content = content[:4000] + "\n\n... [content truncated] ...\n\n" + content[-4000:]

        system_prompt = """You are a document classification expert. Your task is to analyze a document and classify it into one of the predefined document types.

Analyze the document's content, structure, and key characteristics to determine the most appropriate classification.

You must respond with a valid JSON object matching the provided schema. The document_type_id must be one of the valid IDs from the available document types.

If the document doesn't clearly match any type, choose the closest match but set a lower confidence score."""

        use_vision = False
        image_data = None
        file_path_to_use = None
        if document.file_path:
            file_path_to_use = Path(document.file_path)
        else:
            # Try to reconstruct file path from document ID and file type
            settings = get_settings()
            file_ext = f".{document.file_type.lower()}" if document.file_type else ""
            potential_path = settings.file_storage_path / f"{document.id}{file_ext}"
            if potential_path.exists():
                file_path_to_use = potential_path

        if file_path_to_use and file_path_to_use.exists():
            if document.file_type.lower() in ["pdf", "png", "jpg", "jpeg", "gif", "webp"]:
                use_vision = True
                try:
                    if document.file_type.lower() == "pdf":
                        if not PDF_SUPPORT:
                            logger.warning("pdf2image not available, cannot process PDF")
                            use_vision = False
                        else:
                            images = convert_from_path(
                                str(file_path_to_use), first_page=1, last_page=1, dpi=150
                            )
                            if images:
                                img_byte_arr = io.BytesIO()
                                images[0].save(img_byte_arr, format="PNG")
                                image_bytes = img_byte_arr.getvalue()
                                image_data = base64.b64encode(image_bytes).decode("utf-8")
                            else:
                                logger.warning("Could not convert PDF to image")
                                use_vision = False
                    else:
                        with open(file_path_to_use, "rb") as f:
                            image_bytes = f.read()
                            image_data = base64.b64encode(image_bytes).decode("utf-8")
                except Exception as e:
                    logger.warning(f"Could not read/convert file for vision API: {e}")
                    use_vision = False

        logger.info(
            f"Classifying document: {document.filename} (type={document.file_type}, vision={use_vision})"
        )

        # Build messages based on whether we're using vision
        if use_vision and image_data:
            user_prompt_text = f"""## Available Document Types

{types_text}

## Document to Classify

**Filename:** {document.filename}
**File Type:** {document.file_type}

Please analyze the document image and classify it into one of the available types based on its visual content, structure, and layout."""

            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{document.file_type};base64,{image_data}"
                            },
                        },
                    ],
                },
            ]
        else:
            user_prompt_text = f"""## Available Document Types

{types_text}

## Document to Classify

**Filename:** {document.filename}
**File Type:** {document.file_type}

**Content:**
```
{content}
```

Classify this document into one of the available types based on its content and structure."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt_text},
            ]

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "ClassificationResponse",
                        "schema": classification_schema,
                        "strict": True,
                    },
                },
                **reasoning_options_for_model(self.model),
            )

            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            validated = ClassificationResponse.model_validate(result)

            matched_type_id = validated.document_type_id
            matched_type = next((dt for dt in doc_types if dt.id == matched_type_id), None)

            if not matched_type:
                raise ValueError(f"LLM returned unknown document type ID: {matched_type_id}")

            result["document_type_name"] = matched_type.name

            if auto_save:
                classification = await sync_to_async(repository.classify_document)(
                    document_id=document_id,
                    document_type_id=matched_type.id,
                    confidence=result.get("confidence", 0.7),
                    labeled_by="auto-llm",
                )
                result["saved"] = True
            else:
                result["saved"] = False

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise ValueError(f"Failed to parse LLM response: {e}")
        except Exception as e:
            logger.error(f"Classification failed: {e}", exc_info=True)
            raise

    async def suggest_classification(self, document_id: str) -> dict:
        """
        Suggest a classification without saving it.

        This is useful for showing the user what the LLM thinks
        before they confirm.
        """
        return await self.classify_document(document_id, auto_save=False)


# Singleton instance
_classification_service: ClassificationService | None = None


def get_classification_service() -> ClassificationService:
    """Get or create the classification service singleton."""
    global _classification_service
    if _classification_service is None:
        _classification_service = ClassificationService()
    return _classification_service
