"""Image-aware prompt generator for schema field extraction."""

import base64
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from uu_backend.config import get_settings
from uu_backend.llm.openai_client import get_openai_client
from uu_backend.llm.options import reasoning_options_for_model

logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    """Detected content type from visual analysis."""
    
    TABLE = "table"
    FORM = "form"
    LIST = "list"
    PARAGRAPH = "paragraph"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class VisualAnalysis(BaseModel):
    """Result of visual structure analysis."""
    
    content_type: ContentType = Field(..., description="Detected content type")
    structure_description: str = Field(..., description="Description of the visual layout")
    extraction_guidance: str = Field(..., description="Specific instructions for extraction")
    distinguishing_features: list[str] = Field(
        default_factory=list,
        description="Visual features that distinguish this content"
    )
    column_headers: Optional[list[str]] = Field(
        None, description="Detected column headers for tables"
    )
    row_labels: Optional[list[str]] = Field(
        None, description="Sample row labels for tables"
    )
    data_types: Optional[list[str]] = Field(
        None, description="Types of data observed (currency, percentage, dates, etc.)"
    )


class ImageAwarePromptGenerator:
    """Analyze reference images to generate structure-aware extraction prompts."""

    ANALYSIS_PROMPT = """Analyze this document image and describe its visual structure for data extraction.

Focus on identifying:
1. Content type: Is this a TABLE, FORM (labeled fields), LIST, PARAGRAPH, or MIXED?
2. Structure: Describe the layout - columns, rows, sections, field labels
3. Data types: What kinds of values are present? (currency, percentages, dates, text, numbers)
4. Distinguishing features: What visual cues help identify this specific content?

For TABLES specifically:
- List the column headers if visible
- Note sample row labels from the leftmost column
- Describe the data format in cells (e.g., "$1,234", "(45.6)%", "Sep 28, 2024")

Return a JSON object with these exact keys:
{
  "content_type": "table" | "form" | "list" | "paragraph" | "mixed",
  "structure_description": "Detailed description of the visual layout",
  "extraction_guidance": "Specific instructions for extracting data from this structure",
  "distinguishing_features": ["feature1", "feature2", ...],
  "column_headers": ["header1", "header2", ...] or null,
  "row_labels": ["sample_label1", "sample_label2", ...] or null,
  "data_types": ["currency", "percentage", "date", ...] or null
}

Be specific and practical - the extraction_guidance will be used directly in prompts."""

    def __init__(self, model: Optional[str] = None):
        """Initialize the prompt generator.
        
        Args:
            model: Optional model override. Defaults to settings.openai_tagging_model.
        """
        self._openai_client = get_openai_client()
        settings = get_settings()
        self._model = model or settings.openai_tagging_model or settings.openai_model

    def analyze_image(self, image_base64: str) -> VisualAnalysis:
        """Analyze a base64-encoded image and return visual structure analysis.
        
        Args:
            image_base64: Base64-encoded image data (PNG, JPG, etc.)
            
        Returns:
            VisualAnalysis with content type and extraction guidance
        """
        logger.info(f"Analyzing image for visual structure using {self._model}")
        
        messages = [
            {"role": "system", "content": "You are an expert at analyzing document layouts for data extraction."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": self.ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ]

        try:
            response = self._openai_client._client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={"type": "json_object"},
                **reasoning_options_for_model(self._model),
            )
            
            content = response.choices[0].message.content or "{}"
            payload = json.loads(content)
            
            logger.info(f"Visual analysis complete: content_type={payload.get('content_type')}")
            
            return VisualAnalysis(
                content_type=ContentType(payload.get("content_type", "unknown").lower()),
                structure_description=payload.get("structure_description", ""),
                extraction_guidance=payload.get("extraction_guidance", ""),
                distinguishing_features=payload.get("distinguishing_features", []),
                column_headers=payload.get("column_headers"),
                row_labels=payload.get("row_labels"),
                data_types=payload.get("data_types"),
            )
            
        except Exception as e:
            logger.error(f"Visual analysis failed: {e}", exc_info=True)
            return VisualAnalysis(
                content_type=ContentType.UNKNOWN,
                structure_description="Analysis failed",
                extraction_guidance="",
                distinguishing_features=[],
            )

    def analyze_image_file(self, image_path: str | Path) -> VisualAnalysis:
        """Analyze an image file and return visual structure analysis.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            VisualAnalysis with content type and extraction guidance
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")
        
        with open(path, "rb") as f:
            image_bytes = f.read()
        
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        return self.analyze_image(image_base64)

    def generate_extraction_prompt(
        self,
        analysis: VisualAnalysis,
        field_name: str,
        field_description: Optional[str] = None,
    ) -> str:
        """Generate an extraction prompt based on visual analysis.
        
        Args:
            analysis: VisualAnalysis from analyze_image
            field_name: Name of the schema field
            field_description: Optional field description for context
            
        Returns:
            Generated extraction prompt string
        """
        field_label = field_name.replace("_", " ")
        
        if analysis.content_type == ContentType.TABLE:
            prompt_parts = [
                f"Extract data from the TABLE structure for '{field_label}'.",
            ]
            
            if analysis.structure_description:
                prompt_parts.append(f"Look for: {analysis.structure_description}")
            
            if analysis.column_headers:
                prompt_parts.append(f"Column headers: {', '.join(analysis.column_headers)}")
            
            if analysis.data_types:
                prompt_parts.append(f"Expected data formats: {', '.join(analysis.data_types)}")
            
            if analysis.distinguishing_features:
                prompt_parts.append(f"Visual cues: {', '.join(analysis.distinguishing_features)}")
            
            if analysis.extraction_guidance:
                prompt_parts.append(analysis.extraction_guidance)
            
            prompt_parts.append(
                "DO NOT extract from prose/paragraph sections or explanatory text - "
                "only from the tabular data with the identified column structure."
            )
            
            return "\n".join(prompt_parts)
        
        elif analysis.content_type == ContentType.FORM:
            prompt_parts = [
                f"Extract data from the FORM fields for '{field_label}'.",
            ]
            
            if analysis.structure_description:
                prompt_parts.append(f"Look for: {analysis.structure_description}")
            
            if analysis.extraction_guidance:
                prompt_parts.append(analysis.extraction_guidance)
            
            prompt_parts.append(
                "Extract values from labeled fields. Match each field label to its corresponding value."
            )
            
            return "\n".join(prompt_parts)
        
        elif analysis.content_type == ContentType.LIST:
            prompt_parts = [
                f"Extract data from the LIST structure for '{field_label}'.",
            ]
            
            if analysis.structure_description:
                prompt_parts.append(f"Look for: {analysis.structure_description}")
            
            if analysis.extraction_guidance:
                prompt_parts.append(analysis.extraction_guidance)
            
            return "\n".join(prompt_parts)
        
        else:
            # PARAGRAPH, MIXED, or UNKNOWN
            prompt_parts = [
                f"Extract '{field_label}' from the document.",
            ]
            
            if field_description:
                prompt_parts.append(f"Description: {field_description}")
            
            if analysis.extraction_guidance:
                prompt_parts.append(analysis.extraction_guidance)
            
            return "\n".join(prompt_parts)

    def generate_retrieval_query(
        self,
        analysis: VisualAnalysis,
        field_name: str,
        field_description: Optional[str] = None,
    ) -> str:
        """Generate a retrieval query optimized for finding the right content.
        
        This generates a query for semantic search that is more likely to
        match the actual content rather than explanatory text.
        
        Args:
            analysis: VisualAnalysis from analyze_image
            field_name: Name of the schema field
            field_description: Optional field description
            
        Returns:
            Query string for retrieval
        """
        query_parts = [field_name.replace("_", " ")]
        
        if analysis.content_type == ContentType.TABLE:
            # For tables, include column headers and sample row labels
            # These are more likely to appear in the actual table than in prose
            if analysis.column_headers:
                query_parts.extend(analysis.column_headers)
            
            if analysis.row_labels:
                query_parts.extend(analysis.row_labels[:5])  # Limit to 5 samples
            
            # Add data type indicators
            if analysis.data_types:
                for dt in analysis.data_types:
                    if dt == "currency":
                        query_parts.append("$ dollar amount")
                    elif dt == "percentage":
                        query_parts.append("% percent")
                    elif dt == "date":
                        query_parts.append("date period")
        
        elif analysis.content_type == ContentType.FORM:
            # For forms, the field labels are good search terms
            if analysis.distinguishing_features:
                query_parts.extend(analysis.distinguishing_features[:3])
        
        if field_description:
            query_parts.append(field_description)
        
        return " ".join(query_parts)


# Singleton instance
_prompt_generator: Optional[ImageAwarePromptGenerator] = None


def get_prompt_generator() -> ImageAwarePromptGenerator:
    """Get or create the prompt generator singleton."""
    global _prompt_generator
    if _prompt_generator is None:
        _prompt_generator = ImageAwarePromptGenerator()
    return _prompt_generator
