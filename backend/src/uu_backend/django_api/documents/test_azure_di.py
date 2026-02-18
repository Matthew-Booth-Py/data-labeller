"""Test endpoint for Azure Document Intelligence."""

import logging
from pathlib import Path

from asgiref.sync import async_to_sync
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.config import get_settings
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.services.azure_di_service import get_azure_di_service

logger = logging.getLogger(__name__)


class TestAzureDIView(APIView):
    """Test Azure Document Intelligence on a document."""
    
    authentication_classes: list = []
    permission_classes: list = []
    
    def get(self, request, document_id: str):
        """Analyze a document with Azure DI and return results."""
        try:
            logger.info(f"Testing Azure DI on document {document_id}")
            
            # Get document
            doc_repo = get_document_repository()
            document = doc_repo.get_document(document_id)
            
            if not document:
                return Response(
                    {"detail": "Document not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get file path
            settings = get_settings()
            file_ext = f".{document.file_type}"
            file_path = settings.file_storage_path / f"{document_id}{file_ext}"
            
            if not file_path.exists():
                return Response(
                    {"detail": f"Document file not found at {file_path}"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            logger.info(f"File path: {file_path}")
            
            # Test Azure DI service
            try:
                azure_di = get_azure_di_service()
                logger.info("Azure DI service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Azure DI service: {e}")
                return Response(
                    {"detail": f"Azure DI initialization failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Analyze document
            try:
                logger.info("Starting document analysis...")
                analysis = async_to_sync(azure_di.analyze_document)(file_path)
                logger.info(f"Analysis complete. Found {len(analysis['pages'])} pages")
                
                # Format response
                response_data = {
                    "document_id": document_id,
                    "file_path": str(file_path),
                    "pages": []
                }
                
                for page in analysis["pages"]:
                    page_data = {
                        "page_number": page["page_number"],
                        "width": page["width"],
                        "height": page["height"],
                        "unit": page["unit"],
                        "line_count": len(page["lines"]),
                        "sample_lines": []
                    }
                    
                    # Include first 10 lines as samples
                    for line in page["lines"][:10]:
                        polygon = line["bbox"]
                        if polygon:
                            x_coords = [p.x for p in polygon]
                            y_coords = [p.y for p in polygon]
                            page_data["sample_lines"].append({
                                "text": line["text"],
                                "bbox": {
                                    "x": min(x_coords),
                                    "y": min(y_coords),
                                    "width": max(x_coords) - min(x_coords),
                                    "height": max(y_coords) - min(y_coords)
                                }
                            })
                    
                    response_data["pages"].append(page_data)
                
                return Response(response_data)
                
            except Exception as e:
                logger.error(f"Azure DI analysis failed: {e}")
                import traceback
                traceback.print_exc()
                return Response(
                    {"detail": f"Azure DI analysis failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        except Exception as e:
            logger.error(f"Test endpoint error: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
