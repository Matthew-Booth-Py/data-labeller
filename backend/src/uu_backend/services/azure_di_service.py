"""Azure Document Intelligence service for text extraction from bounding boxes."""

import base64
from pathlib import Path
from typing import Any

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

from uu_backend.config import get_settings


class AzureDocumentIntelligenceService:
    """Service for extracting text from documents using Azure Document Intelligence."""

    def __init__(self):
        """Initialize Azure Document Intelligence client."""
        settings = get_settings()
        self.endpoint = settings.azure_di_endpoint
        self.key = settings.azure_di_key
        
        if not self.key:
            raise ValueError("Azure Document Intelligence key not configured")
        
        self.client = DocumentAnalysisClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.key)
        )

    async def analyze_document(self, file_path: Path, first_page_only: bool = False) -> dict[str, Any]:
        """
        Analyze a document and extract all text with bounding boxes.
        
        Args:
            file_path: Path to the document file (PDF or image)
            first_page_only: If True, extract only the first page (for large PDFs)
            
        Returns:
            Dictionary containing pages with text and bounding box information
        """
        # For large PDFs, extract first page only to avoid Azure DI size limits
        if first_page_only and file_path.suffix.lower() == '.pdf':
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Extracting first page only from {file_path}")
            
            try:
                from pypdf import PdfReader, PdfWriter
                import io
                
                # Read the PDF and extract first page
                reader = PdfReader(file_path)
                writer = PdfWriter()
                writer.add_page(reader.pages[0])
                
                # Write to bytes buffer
                buffer = io.BytesIO()
                writer.write(buffer)
                buffer.seek(0)
                
                # Send first page to Azure DI
                poller = self.client.begin_analyze_document(
                    "prebuilt-read",
                    document=buffer
                )
                result = poller.result()
            except ImportError:
                logger.warning("pypdf not available, sending full PDF")
                with open(file_path, "rb") as f:
                    poller = self.client.begin_analyze_document(
                        "prebuilt-read",
                        document=f
                    )
                    result = poller.result()
        else:
            with open(file_path, "rb") as f:
                poller = self.client.begin_analyze_document(
                    "prebuilt-read",
                    document=f
                )
                result = poller.result()

        pages_data = []
        for page in result.pages:
            page_data = {
                "page_number": page.page_number,
                "width": page.width,
                "height": page.height,
                "unit": page.unit,
                "lines": []
            }
            
            for line in page.lines:
                # Convert Point objects to dicts for JSON serialization
                polygon_dicts = [{"x": p.x, "y": p.y} for p in line.polygon] if line.polygon else []
                line_data = {
                    "text": line.content,
                    "bbox": polygon_dicts,  # List of dicts with x, y coordinates
                }
                page_data["lines"].append(line_data)
            
            pages_data.append(page_data)

        return {
            "pages": pages_data,
            "content": result.content  # Full text content
        }

    async def extract_text_from_bbox(
        self,
        file_path: Path,
        page_number: int,
        bbox: dict[str, float],
        cached_analysis: dict[str, Any] | None = None
    ) -> str:
        """
        Extract text from a specific bounding box on a page.
        
        Args:
            file_path: Path to the document file
            page_number: Page number (1-indexed)
            bbox: Bounding box with keys: x, y, width, height
            cached_analysis: Pre-computed Azure DI analysis (optional, will analyze if not provided)
            
        Returns:
            Extracted text within the bounding box
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Extracting text from bbox: page={page_number}, bbox={bbox}")
        
        # Use cached analysis if available, otherwise analyze now
        if cached_analysis:
            print("Using cached Azure DI analysis")
            analysis = cached_analysis
        else:
            print("No cached analysis, analyzing document now...")
            analysis = await self.analyze_document(file_path)
        
        # Find the target page
        target_page = None
        for page in analysis["pages"]:
            if page["page_number"] == page_number:
                target_page = page
                break
        
        if not target_page:
            logger.warning(f"Page {page_number} not found in document")
            return ""
        
        page_width = target_page['width']
        page_height = target_page['height']
        unit = target_page['unit']
        
        print(f"Page dimensions: {page_width} x {page_height} {unit}")
        print(f"Found {len(target_page['lines'])} lines on page")
        
        # The bbox from frontend is in pixels from the rendered PDF
        # We need to convert to Azure DI's coordinate system (inches)
        # Assuming standard PDF DPI of 72 pixels per inch
        DPI = 72.0
        
        # Convert pixel coordinates to inches
        x1_inches = bbox["x"] / DPI
        y1_inches = bbox["y"] / DPI
        x2_inches = (bbox["x"] + bbox["width"]) / DPI
        y2_inches = (bbox["y"] + bbox["height"]) / DPI
        
        print(f"Input bbox (pixels): ({bbox['x']:.2f}, {bbox['y']:.2f}) size ({bbox['width']:.2f}, {bbox['height']:.2f})")
        print(f"Converted bbox (inches): ({x1_inches:.2f}, {y1_inches:.2f}) to ({x2_inches:.2f}, {y2_inches:.2f})")
        
        x1 = x1_inches
        y1 = y1_inches
        x2 = x2_inches
        y2 = y2_inches
        
        # Find all lines that overlap with the bounding box
        extracted_lines = []
        print(f"Checking {len(target_page['lines'])} lines for overlap...")
        for idx, line in enumerate(target_page["lines"]):
            # Azure returns polygon as list of Point objects with x, y attributes
            # Get bounding box of the line
            polygon = line["bbox"]
            if not polygon:
                continue
            
            # Calculate line bounding box from polygon
            # Handle multiple formats: Point objects, dicts, or lists
            line_x_coords = []
            line_y_coords = []
            
            for p in polygon:
                if isinstance(p, dict):
                    # Cached data: dict with 'x' and 'y' keys
                    line_x_coords.append(p['x'])
                    line_y_coords.append(p['y'])
                elif isinstance(p, list):
                    # Old cached data: list [x, y]
                    line_x_coords.append(p[0])
                    line_y_coords.append(p[1])
                else:
                    # Fresh API data: Point object with x, y attributes
                    line_x_coords.append(p.x)
                    line_y_coords.append(p.y)
            
            line_x1 = min(line_x_coords)
            line_y1 = min(line_y_coords)
            line_x2 = max(line_x_coords)
            line_y2 = max(line_y_coords)
            
            if idx < 3:  # Print first 3 lines for debugging
                print(f"Line {idx}: '{line['text']}' at ({line_x1:.2f}, {line_y1:.2f}) to ({line_x2:.2f}, {line_y2:.2f})")
            
            # Check if line overlaps with the target bbox
            if self._boxes_overlap(x1, y1, x2, y2, line_x1, line_y1, line_x2, line_y2):
                print(f"✓ MATCH: '{line['text']}' at ({line_x1:.2f}, {line_y1:.2f}) to ({line_x2:.2f}, {line_y2:.2f})")
                extracted_lines.append(line["text"])
        
        result = " ".join(extracted_lines)
        logger.info(f"Extracted text: '{result}'")
        return result

    def _boxes_overlap(
        self,
        x1_a: float, y1_a: float, x2_a: float, y2_a: float,
        x1_b: float, y1_b: float, x2_b: float, y2_b: float
    ) -> bool:
        """Check if two bounding boxes overlap."""
        return not (x2_a < x1_b or x2_b < x1_a or y2_a < y1_b or y2_b < y1_a)


# Singleton instance
_azure_di_service: AzureDocumentIntelligenceService | None = None


def get_azure_di_service() -> AzureDocumentIntelligenceService:
    """Get or create the Azure Document Intelligence service singleton."""
    global _azure_di_service
    if _azure_di_service is None:
        _azure_di_service = AzureDocumentIntelligenceService()
    return _azure_di_service
