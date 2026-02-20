"""Extraction service for converting annotations into structured data."""

import json
import logging
import re
import base64
import io
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4
from pathlib import Path

from django.utils import timezone

from uu_backend.config import get_settings
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.llm.options import reasoning_options_for_model
from uu_backend.llm.openai_client import get_openai_client
from uu_backend.models.taxonomy import ExtractedField, ExtractionResult, SchemaField
from uu_backend.repositories import get_repository
from uu_backend.services.schema_generator import generate_pydantic_schema, schema_to_json_schema

try:
    from pdf2image import convert_from_path
    from PIL import Image
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

logger = logging.getLogger(__name__)


class ExtractionService:
    """Service for extracting structured data from document annotations."""

    def __init__(self):
        openai_client = get_openai_client()
        self.client = openai_client._client
        settings = get_settings()
        self.model = settings.openai_tagging_model or settings.openai_model
        self._raw_guardrails = (
            "Critical extraction rules:\n"
            "1) Extract values exactly as they appear in the document (RAW).\n"
            "2) Do NOT normalize, reformat, infer, or interpret values.\n"
            "3) For dates, return the exact source string (for example, keep 'February 3, 2024' if shown).\n"
            "4) Preserve punctuation, currency symbols, and separators exactly when present.\n"
            "5) If not found, return null."
        )

    def extract_structured(
        self,
        document_id: str,
        prompt_version_id: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract structured data directly from document using OpenAI structured output.
        
        This uses the schema fields to generate a Pydantic model and enforces
        structured output from the LLM, bypassing the need for annotations.
        
        Args:
            document_id: The document to extract from
            prompt_version_id: Optional prompt version to use
            
        Returns:
            ExtractionResult with extracted field values
        """
        repository = get_repository()
        document_repo = get_document_repository()
        
        # Get document
        document = document_repo.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Get classification
        classification = repository.get_classification(document_id)
        if not classification:
            raise ValueError(f"Document {document_id} is not classified. Please classify first.")
        
        # Get document type with schema
        doc_type = repository.get_document_type(classification.document_type_id)
        if not doc_type:
            raise ValueError(f"Document type {classification.document_type_id} not found")
        
        if not doc_type.schema_fields:
            raise ValueError(f"Document type '{doc_type.name}' has no schema fields defined")

        effective_schema_fields = self._apply_active_field_prompt_versions(
            doc_type.id,
            doc_type.schema_fields,
        )
        
        # Generate Pydantic schema from field definitions
        ExtractionModel = generate_pydantic_schema(
            effective_schema_fields,
            model_name=f"{doc_type.name.replace(' ', '')}Extraction"
        )
        json_schema = schema_to_json_schema(ExtractionModel)
        
        # Get prompt (use version if specified, otherwise default)
        system_prompt = doc_type.system_prompt or self._get_default_extraction_prompt(doc_type)
        system_prompt = f"{system_prompt}\n\n{self._raw_guardrails}"
        model_name = doc_type.extraction_model or self.model

        if prompt_version_id:
            prompt_version = repository.get_prompt_version(prompt_version_id)
            if prompt_version:
                system_prompt = f"{prompt_version.system_prompt}\n\n{self._raw_guardrails}"
        
        # Determine if we should use vision API based on file type
        use_vision = False
        image_data = None
        file_type = document.file_type.lower() if document.file_type else ""
        is_visual_document = file_type in ['pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'doc', 'docx']
        
        # Try to get the file for visual processing
        if is_visual_document:
            file_path_to_use = self._get_document_file_path(document)
            if file_path_to_use and file_path_to_use.exists():
                image_data = self._prepare_visual_content(file_path_to_use, file_type)
                if image_data:
                    use_vision = True
        
        # Prepare messages based on document type
        if use_vision and image_data:
            # Use vision API with image
            user_prompt_text = f"""Extract structured data from this document.

Document Type: {doc_type.name}
Filename: {document.filename}

Analyze the document image and extract all fields according to the schema. Return null for fields that cannot be found."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}"
                            }
                        }
                    ]
                }
            ]
        else:
            # Use text-only extraction
            content = document.content or ""
            if len(content) > 8000:
                content = content[:4000] + "\n...[truncated]...\n" + content[-4000:]
            
            user_prompt = f"""Extract structured data from the following document.

Document Type: {doc_type.name}

Document Content:
```
{content}
```

Extract all fields according to the schema. Return null for fields that cannot be found."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

        print(f"\n{'='*60}")
        print("STRUCTURED EXTRACTION")
        print(f"{'='*60}")
        print(f"Document: {document.filename}")
        print(f"File Type: {file_type}")
        print(f"Using Vision API: {use_vision}")
        print(f"Type: {doc_type.name}")
        print(f"Model: {model_name}")
        print(f"Fields: {[f.name for f in effective_schema_fields]}")
        print(f"{'='*60}\n")
        
        logger.info(f"Extraction started - Document: {document.filename}, Model: {model_name}, Vision: {use_vision}")

        try:
            response = self.client.beta.chat.completions.parse(
                model=model_name,
                messages=messages,
                response_format=ExtractionModel,
            )
            
            extracted_data = response.choices[0].message.parsed
            
            print(f"Extracted: {extracted_data.model_dump()}")
            
            # Convert to ExtractedField objects
            extracted_fields = []
            for field in effective_schema_fields:
                value = getattr(extracted_data, field.name, None)
                if value is not None:
                    # Convert Pydantic models to dicts for storage
                    if hasattr(value, 'model_dump'):
                        value = value.model_dump()
                    elif isinstance(value, list) and value and hasattr(value[0], 'model_dump'):
                        value = [item.model_dump() for item in value]
                    
                    extracted_fields.append(ExtractedField(
                        field_name=field.name,
                        value=value,
                        confidence=0.95,  # High confidence for structured output
                        source_text=None
                    ))
            
            result = ExtractionResult(
                document_id=document_id,
                document_type_id=doc_type.id,
                fields=extracted_fields,
                schema_version_id=doc_type.schema_version_id,
                prompt_version_id=prompt_version_id,
                extracted_at=timezone.now()
            )
            
            # Save extraction result
            self._save_extraction(result)
            
            return result
            
        except Exception as e:
            print(f"Structured extraction error: {e}")
            raise ValueError(f"Extraction failed: {str(e)}")

    def _get_default_extraction_prompt(self, doc_type) -> str:
        """Get default extraction prompt for a document type."""
        return f"""You are an expert at extracting structured data from {doc_type.name} documents.

Extract all fields accurately from the document. Pay special attention to:
- Tables: Extract all rows and columns
- Numbers: Keep exact source formatting from the document
- Dates: Keep exact source formatting from the document (no ISO conversion)
- Arrays: Include all items found in the document

If a field cannot be found, return null. Do not make up data."""

    def extract_structured_with_retrieval(
        self,
        document_id: str,
        prompt_version_id: Optional[str] = None,
        top_k_per_field: int = 5,
    ) -> ExtractionResult:
        """
        Extract structured data using per-field retrieval from the contextual index.
        
        For each schema field:
        1. Build a search query from field name + description + extraction_prompt
        2. Retrieve top-k relevant chunks from the document's index
        3. Use retrieved chunks as context for extraction
        
        Args:
            document_id: The document to extract from
            prompt_version_id: Optional prompt version to use
            top_k_per_field: Number of chunks to retrieve per field
            
        Returns:
            ExtractionResult with extracted field values
        """
        from uu_backend.services.contextual_retrieval import get_contextual_retrieval_service
        
        repository = get_repository()
        document_repo = get_document_repository()
        
        # Get document
        document = document_repo.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Get classification
        classification = repository.get_classification(document_id)
        if not classification:
            raise ValueError(f"Document {document_id} is not classified. Please classify first.")
        
        # Get document type with schema
        doc_type = repository.get_document_type(classification.document_type_id)
        if not doc_type:
            raise ValueError(f"Document type {classification.document_type_id} not found")
        
        if not doc_type.schema_fields:
            raise ValueError(f"Document type '{doc_type.name}' has no schema fields defined")

        effective_schema_fields = self._apply_active_field_prompt_versions(
            doc_type.id,
            doc_type.schema_fields,
        )
        
        # Generate Pydantic schema from field definitions
        ExtractionModel = generate_pydantic_schema(
            effective_schema_fields,
            model_name=f"{doc_type.name.replace(' ', '')}Extraction"
        )
        
        # Get retrieval service
        retrieval_service = get_contextual_retrieval_service()
        
        print(f"\n{'='*60}")
        print("CONTEXTUAL RETRIEVAL - FIELD-BY-FIELD SEARCH")
        print(f"{'='*60}")
        
        # Build search queries for each field and retrieve relevant chunks
        all_chunks = {}
        for field in effective_schema_fields:
            query = self._build_field_query(field)
            print(f"\n🔍 Field: {field.name}")
            print(f"   Query: {query[:100]}...")
            
            results = retrieval_service.search(
                query=query,
                top_k=top_k_per_field,
                filter_doc_id=document_id,
                use_reranking=True,
            )
            
            print(f"   Retrieved: {len(results)} chunks")
            if results:
                print(f"   Top score: {results[0].score:.4f}")
                print(f"   Preview: {results[0].original_text[:80]}...")
            
            all_chunks[field.name] = results
        
        print(f"\n{'='*60}")
        print("DEDUPLICATION & CONTEXT BUILDING")
        print(f"{'='*60}")
        
        # Deduplicate chunks and build context
        seen_chunk_ids = set()
        unique_chunks = []
        for field_name, results in all_chunks.items():
            for result in results:
                chunk_id = f"{result.doc_id}_{result.chunk_index}"
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    unique_chunks.append(result)
        
        print(f"Total chunks retrieved: {sum(len(r) for r in all_chunks.values())}")
        print(f"Unique chunks after dedup: {len(unique_chunks)}")
        
        # Sort by score and take top chunks
        unique_chunks.sort(key=lambda r: r.score, reverse=True)
        top_chunks = unique_chunks[:20]  # Limit total context
        
        print(f"Top chunks for context: {len(top_chunks)}")
        print(f"\nTop 3 chunks by score:")
        for i, chunk in enumerate(top_chunks[:3]):
            print(f"  {i+1}. Score: {chunk.score:.4f}, Page: {chunk.metadata.get('page_number', 'N/A')}")
            print(f"     Text: {chunk.original_text[:]}...")
        
        # Build context from retrieved chunks
        context_parts = []
        for i, chunk in enumerate(top_chunks):
            context_parts.append(f"[Source {i+1}]\n{chunk.original_text}")
        context = "\n\n".join(context_parts)
        
        print(f"\nTotal context length: {len(context)} chars")
        
        # Get prompt
        system_prompt = doc_type.system_prompt or self._get_default_extraction_prompt(doc_type)
        system_prompt = f"{system_prompt}\n\n{self._raw_guardrails}"
        model_name = doc_type.extraction_model or self.model

        if prompt_version_id:
            prompt_version = repository.get_prompt_version(prompt_version_id)
            if prompt_version:
                system_prompt = f"{prompt_version.system_prompt}\n\n{self._raw_guardrails}"
        
        user_prompt = f"""Extract structured data from the following document excerpts.

Document Type: {doc_type.name}
Filename: {document.filename}

Relevant Document Excerpts:
{context}

Extract all fields according to the schema. Return null for fields that cannot be found in the excerpts."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        print(f"\n{'='*60}")
        print("RETRIEVAL-AUGMENTED EXTRACTION")
        print(f"{'='*60}")
        print(f"Document: {document.filename}")
        print(f"Type: {doc_type.name}")
        print(f"Model: {model_name}")
        print(f"Fields: {[f.name for f in effective_schema_fields]}")
        print(f"Retrieved chunks: {len(top_chunks)}")
        print(f"Context length: {len(context)} chars")
        print(f"{'='*60}\n")
        
        logger.info(
            f"Retrieval extraction started - Document: {document.filename}, "
            f"Model: {model_name}, Chunks: {len(top_chunks)}"
        )

        try:
            response = self.client.beta.chat.completions.parse(
                model=model_name,
                messages=messages,
                response_format=ExtractionModel,
            )
            
            extracted_data = response.choices[0].message.parsed
            
            print(f"Extracted: {extracted_data.model_dump()}")
            
            # Convert to ExtractedField objects
            extracted_fields = []
            for field in effective_schema_fields:
                value = getattr(extracted_data, field.name, None)
                if value is not None:
                    if hasattr(value, 'model_dump'):
                        value = value.model_dump()
                    elif isinstance(value, list) and value and hasattr(value[0], 'model_dump'):
                        value = [item.model_dump() for item in value]
                    
                    # Find source text from retrieved chunks for this field
                    source_chunks = all_chunks.get(field.name, [])
                    source_text = source_chunks[0].original_text[:200] if source_chunks else None
                    
                    extracted_fields.append(ExtractedField(
                        field_name=field.name,
                        value=value,
                        confidence=0.90,  # Slightly lower than full-doc extraction
                        source_text=source_text
                    ))
            
            result = ExtractionResult(
                document_id=document_id,
                document_type_id=doc_type.id,
                fields=extracted_fields,
                schema_version_id=doc_type.schema_version_id,
                prompt_version_id=prompt_version_id,
                extracted_at=timezone.now()
            )
            
            # Save extraction result
            self._save_extraction(result)
            
            return result
            
        except Exception as e:
            print(f"Retrieval extraction error: {e}")
            raise ValueError(f"Extraction failed: {str(e)}")

    def _build_field_query(self, field: SchemaField) -> str:
        """Build a search query for a schema field."""
        parts = [field.name]
        
        if field.description:
            parts.append(field.description)
        
        if field.extraction_prompt:
            parts.append(field.extraction_prompt)
        
        return " ".join(parts)

    def extract_structured_from_snapshot(
        self,
        *,
        content: str,
        filename: str,
        document_type_name: str,
        schema_fields: list[SchemaField],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Extract structured data using a deployable schema/prompt snapshot.

        This does not require document ingestion, classification, or annotation persistence.
        """
        if not schema_fields:
            raise ValueError("Deployment snapshot has no schema fields")

        ExtractionModel = generate_pydantic_schema(
            schema_fields,
            model_name=f"{document_type_name.replace(' ', '')}DeploymentExtraction",
        )

        trimmed_content = content or ""
        if len(trimmed_content) > 8000:
            trimmed_content = trimmed_content[:4000] + "\n...[truncated]...\n" + trimmed_content[-4000:]

        effective_system_prompt = (
            system_prompt
            or f"You are an expert at extracting structured data from {document_type_name} documents."
        )
        effective_system_prompt = f"{effective_system_prompt}\n\n{self._raw_guardrails}"

        user_prompt = f"""Extract structured data from the following document.

Document Type: {document_type_name}
Filename: {filename}

Document Content:
```
{trimmed_content}
```

Extract all fields according to the schema. Return null for fields that cannot be found."""

        effective_model = model or self.model
        logger.info(f"Snapshot extraction - Filename: {filename}, Model: {effective_model}, Type: {document_type_name}")
        print(f"[Extraction] Model: {effective_model} | File: {filename} | Type: {document_type_name}")

        response = self.client.beta.chat.completions.parse(
            model=effective_model,
            messages=[
                {"role": "system", "content": effective_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ExtractionModel,
        )
        parsed = response.choices[0].message.parsed
        return parsed.model_dump() if parsed else {}


    def _get_document_file_path(self, document) -> Optional[Path]:
        """Get the file path for a document, reconstructing if necessary."""
        if document.file_path:
            return Path(document.file_path)
        
        # Try to reconstruct file path from document ID and file type
        settings = get_settings()
        file_ext = f".{document.file_type.lower()}" if document.file_type else ""
        potential_path = settings.file_storage_path / f"{document.id}{file_ext}"
        
        if potential_path.exists():
            logger.info(f"Reconstructed file path: {potential_path}")
            return potential_path
        
        return None
    
    def _prepare_visual_content(self, file_path: Path, file_type: str) -> Optional[str]:
        """
        Prepare visual content (PDF, image, Word) for vision API.
        Returns base64-encoded PNG image data.
        """
        try:
            if file_type == 'pdf':
                # Convert PDF first page to image
                if not PDF_SUPPORT:
                    logger.warning("pdf2image not available, cannot process PDF")
                    return None
                
                images = convert_from_path(str(file_path), first_page=1, last_page=1, dpi=150)
                if images:
                    img_byte_arr = io.BytesIO()
                    images[0].save(img_byte_arr, format='PNG')
                    image_bytes = img_byte_arr.getvalue()
                    return base64.b64encode(image_bytes).decode('utf-8')
                else:
                    logger.warning("Could not convert PDF to image")
                    return None
            
            elif file_type in ['doc', 'docx']:
                # For Word docs, we'd need python-docx or similar to extract text
                # For now, skip vision API for Word docs (they should have text content)
                logger.info("Word documents not yet supported for vision API")
                return None
            
            elif file_type in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                # Read image file directly
                with open(file_path, 'rb') as f:
                    image_bytes = f.read()
                    return base64.b64encode(image_bytes).decode('utf-8')
            
            return None
            
        except Exception as e:
            logger.error(f"Error preparing visual content: {e}", exc_info=True)
            return None

    def _apply_active_field_prompt_versions(
        self, document_type_id: str, schema_fields: list[SchemaField]
    ) -> list[SchemaField]:
        """Overlay active field prompt versions onto schema field definitions."""
        repository = get_repository()
        active_prompts = repository.list_active_field_prompt_versions(document_type_id)
        if not active_prompts:
            return schema_fields
        return [
            field.model_copy(update={"extraction_prompt": active_prompts.get(field.name, field.extraction_prompt)})
            for field in schema_fields
        ]


    def _save_extraction(self, result: ExtractionResult):
        """Save extraction result to database."""
        repository = get_repository()
        repository.save_extraction_result(result)


# Singleton instance
_extraction_service: Optional[ExtractionService] = None


def get_extraction_service() -> ExtractionService:
    """Get or create the extraction service singleton."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = ExtractionService()
    return _extraction_service
