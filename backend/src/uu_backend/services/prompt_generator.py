"""Image-aware prompt generator for schema field extraction."""

import base64
import json
import logging
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from uu_backend.config import get_settings
from uu_backend.llm.openai_client import get_openai_client
from uu_backend.llm.options import reasoning_options_for_model

logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    TABLE = "table"
    FORM = "form"
    LIST = "list"
    PARAGRAPH = "paragraph"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class RowHierarchy(BaseModel):
    has_hierarchy: bool = Field(..., description="Whether table has nested row structure")
    depth: int | None = Field(None, description="Maximum nesting depth (2-5)")
    example_paths: list[list[str]] | None = Field(
        None, description="Sample hierarchical paths from table"
    )
    structure_description: str | None = Field(
        None, description="How hierarchy is visually indicated"
    )


class VisualAnalysis(BaseModel):
    content_type: ContentType = Field(..., description="Detected content type")
    structure_description: str = Field(..., description="Description of the visual layout")
    extraction_guidance: str = Field(..., description="Specific instructions for extraction")
    distinguishing_features: list[str] = Field(
        default_factory=list, description="Visual features that distinguish this content"
    )
    column_headers: list[str] | None = Field(None, description="Detected column headers for tables")
    row_labels: list[str] | None = Field(None, description="Sample row labels for tables")
    data_types: list[str] | None = Field(
        None, description="Types of data observed (currency, percentage, dates, etc.)"
    )
    row_hierarchy: RowHierarchy | None = Field(
        None, description="Detected row hierarchy for nested tables"
    )


class ImageAwarePromptGenerator:
    ANALYSIS_PROMPT = (
        "Analyze this document image and describe its visual structure for data "
        "extraction.\n\n"
        "Focus on identifying:\n"
        "1. Content type: Is this a TABLE, FORM (labeled fields), LIST, PARAGRAPH, or MIXED?\n"
        "2. Structure: Describe the layout - columns, rows, sections, field labels\n"
        "3. Data types: What kinds of values are present? (currency, percentages, dates, "
        "text, numbers)\n"
        "4. Distinguishing features: What visual cues help identify this specific content?\n\n"
        "For TABLES specifically:\n"
        "- List the column headers if visible\n"
        "- Note sample row labels from the leftmost column\n"
        '- Describe the data format in cells (e.g., "$1,234", "(45.6)%", '
        '"Sep 28, 2024")\n'
        "- **HIERARCHY DETECTION**: Does the table have nested/indented row labels "
        "indicating a category hierarchy?\n"
        "  - If yes: How many hierarchy levels? (count the maximum depth)\n"
        "  - Provide 2-3 example row hierarchies showing the full path from top level "
        "to bottom level\n"
        "  - Describe how indentation/formatting indicates hierarchy (indent spaces, "
        "bold headers, different font sizes, etc.)\n\n"
        "Return a JSON object with these exact keys:\n"
        "{\n"
        '  "content_type": "table" | "form" | "list" | "paragraph" | "mixed",\n'
        '  "structure_description": "Detailed description of the visual layout",\n'
        '  "extraction_guidance": "Specific instructions for extracting data from this '
        'structure",\n'
        '  "distinguishing_features": ["feature1", "feature2", ...],\n'
        '  "column_headers": ["header1", "header2", ...] or null,\n'
        '  "row_labels": ["sample_label1", "sample_label2", ...] or null,\n'
        '  "data_types": ["currency", "percentage", "date", ...] or null,\n'
        '  "row_hierarchy": {\n'
        '    "has_hierarchy": true/false,\n'
        '    "depth": 2-5 (max nesting levels, only if has_hierarchy is true),\n'
        '    "example_paths": [\n'
        '      ["level1", "level2", "level3", "metric"],\n'
        '      ["level1", "level2", "metric"]\n'
        "    ] (only if has_hierarchy is true),\n"
        '    "structure_description": "Description of how hierarchy is visually indicated" '
        "(only if has_hierarchy is true)\n"
        "  } or null (if not a table or no hierarchy detected)\n"
        "}\n\n"
        "Be specific and practical - the extraction_guidance will be used directly "
        "in prompts."
    )

    def __init__(self, model: str | None = None):
        """Initialize the prompt generator.

        Args:
            model: Optional model override. Defaults to settings.effective_tagging_model.
        """
        self._openai_client = get_openai_client()
        settings = get_settings()
        self._model = model or settings.effective_tagging_model

    def analyze_image(self, image_base64: str) -> VisualAnalysis:
        logger.info(f"Analyzing image for visual structure using {self._model}")

        messages = [
            {
                "role": "system",
                "content": "You are an expert at analyzing document layouts for data extraction.",
            },
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

            row_hierarchy = None
            hierarchy_data = payload.get("row_hierarchy")
            if hierarchy_data and isinstance(hierarchy_data, dict):
                has_hierarchy = hierarchy_data.get("has_hierarchy", False)
                if has_hierarchy:
                    row_hierarchy = RowHierarchy(
                        has_hierarchy=has_hierarchy,
                        depth=hierarchy_data.get("depth"),
                        example_paths=hierarchy_data.get("example_paths"),
                        structure_description=hierarchy_data.get("structure_description"),
                    )
                    logger.info(
                        f"Detected hierarchical table: depth={row_hierarchy.depth}, "
                        f"examples={len(row_hierarchy.example_paths or [])}"
                    )

            return VisualAnalysis(
                content_type=ContentType(payload.get("content_type", "unknown").lower()),
                structure_description=payload.get("structure_description", ""),
                extraction_guidance=payload.get("extraction_guidance", ""),
                distinguishing_features=payload.get("distinguishing_features", []),
                column_headers=payload.get("column_headers"),
                row_labels=payload.get("row_labels"),
                data_types=payload.get("data_types"),
                row_hierarchy=row_hierarchy,
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
        field_description: str | None = None,
    ) -> str:
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
                "Extract values from labeled fields. Match each field label to its "
                "corresponding value."
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
        field_description: str | None = None,
    ) -> str:
        query_parts = []

        if field_description:
            query_parts.append(field_description)
        query_parts.append(field_name.replace("_", " "))

        if analysis.content_type == ContentType.TABLE:
            if analysis.structure_description:
                query_parts.append(analysis.structure_description)

            if analysis.column_headers:
                query_parts.extend(analysis.column_headers[:3])

            if analysis.row_labels:
                query_parts.extend(analysis.row_labels[:3])

            if analysis.data_types:
                for dt in analysis.data_types:
                    if dt == "currency":
                        query_parts.append("financial data amounts")
                    elif dt == "percentage":
                        query_parts.append("percentage rates")
                    elif dt == "date":
                        query_parts.append("time period dates")

        elif analysis.content_type == ContentType.FORM:
            if analysis.distinguishing_features:
                query_parts.extend(analysis.distinguishing_features[:3])

        return " ".join(query_parts)


_prompt_generator: ImageAwarePromptGenerator | None = None


def get_prompt_generator() -> ImageAwarePromptGenerator:
    global _prompt_generator
    if _prompt_generator is None:
        _prompt_generator = ImageAwarePromptGenerator()
    return _prompt_generator
