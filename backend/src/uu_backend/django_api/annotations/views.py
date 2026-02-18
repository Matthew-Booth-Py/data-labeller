"""API views for ground truth annotations."""

import logging
from typing import Any

from asgiref.sync import async_to_sync
from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.models.annotation import (
    ApproveAnnotationRequest,
    BoundingBoxData,
    GroundTruthAnnotationCreate,
    GroundTruthAnnotationListResponse,
    GroundTruthAnnotationResponse,
    GroundTruthAnnotationUpdate,
)
from uu_backend.repositories.django_repo import DjangoORMRepository
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.services.annotation_suggestion_service import get_annotation_suggestion_service
from uu_backend.services.azure_di_service import get_azure_di_service

logger = logging.getLogger(__name__)


class GroundTruthAnnotationListView(APIView):
    """List and create ground truth annotations for a document."""
    
    def get(self, request, document_id: str):
        """Get all ground truth annotations for a document."""
        try:
            repo = DjangoORMRepository()
            annotations = repo.get_ground_truth_annotations(document_id)
            
            response = GroundTruthAnnotationListResponse(
                annotations=annotations,
                total=len(annotations)
            )
            
            return Response(response.model_dump(mode="json"))
            
        except Exception as e:
            logger.error(f"Error fetching annotations for document {document_id}: {e}")
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, document_id: str):
        """Create a new ground truth annotation."""
        print(f"\n\n=== POST /ground-truth called for document {document_id} ===")
        print(f"Request data: {request.data}")
        try:
            # Validate request data
            annotation_create = GroundTruthAnnotationCreate(**request.data)
            print(f"Annotation created: type={annotation_create.annotation_type}, value='{annotation_create.value}'")
            
            # Ensure document_id matches
            if annotation_create.document_id != document_id:
                return Response(
                    {"detail": "Document ID mismatch"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # If annotation type is bbox and value is empty, extract text using Azure DI
            print(f"Checking condition: type={annotation_create.annotation_type}, value='{annotation_create.value}', is_bbox={annotation_create.annotation_type == 'bbox'}, is_empty={not annotation_create.value}")
            if annotation_create.annotation_type == "bbox" and not annotation_create.value:
                print("=== STARTING AZURE DI TEXT EXTRACTION ===")
                try:
                    # Get document file path
                    print("Getting document repository...")
                    doc_repo = get_document_repository()
                    print("Getting document...")
                    document = doc_repo.get_document(document_id)
                    print(f"Document found: {document.id if document else 'None'}")
                    
                    if not document:
                        return Response(
                            {"detail": "Document not found"},
                            status=status.HTTP_404_NOT_FOUND
                        )
                    
                    # Get file path
                    from pathlib import Path
                    from uu_backend.config import get_settings
                    settings = get_settings()
                    file_ext = f".{document.file_type}"
                    file_path = settings.file_storage_path / f"{document_id}{file_ext}"
                    
                    if not file_path.exists():
                        return Response(
                            {"detail": "Document file not found"},
                            status=status.HTTP_404_NOT_FOUND
                        )
                    
                    # Extract text from bounding box using Azure DI
                    print("Getting Azure DI service...")
                    azure_di = get_azure_di_service()
                    print("Azure DI service initialized")
                    
                    bbox_data = annotation_create.annotation_data
                    print(f"Bbox data type: {type(bbox_data)}, value: {bbox_data}")
                    
                    if isinstance(bbox_data, dict):
                        bbox_data = BoundingBoxData(**bbox_data)
                    
                    # Check if we have cached Azure DI analysis
                    cached_analysis = document.azure_di_analysis if hasattr(document, 'azure_di_analysis') else None
                    
                    # If no cache, analyze the document now and cache it
                    if not cached_analysis:
                        print("No cached analysis - analyzing document and caching results...")
                        cached_analysis = async_to_sync(azure_di.analyze_document)(file_path)
                        
                        # Cache the results in the database
                        from uu_backend.django_data.models import DocumentModel
                        doc_model = DocumentModel.objects.get(id=document_id)
                        doc_model.azure_di_analysis = cached_analysis
                        doc_model.azure_di_status = "completed"
                        doc_model.save()
                        print(f"Cached Azure DI analysis: {len(cached_analysis.get('pages', []))} pages")
                    else:
                        print(f"Using cached Azure DI analysis: {len(cached_analysis.get('pages', []))} pages")
                    
                    print(f"Calling extract_text_from_bbox with page={bbox_data.page}, bbox=({bbox_data.x}, {bbox_data.y}, {bbox_data.width}, {bbox_data.height})")
                    extracted_text = async_to_sync(azure_di.extract_text_from_bbox)(
                        file_path,
                        bbox_data.page,
                        {
                            "x": bbox_data.x,
                            "y": bbox_data.y,
                            "width": bbox_data.width,
                            "height": bbox_data.height,
                        },
                        cached_analysis=cached_analysis
                    )
                    
                    print(f"Extracted text: '{extracted_text}'")
                    # Update annotation with extracted text
                    annotation_create.value = extracted_text
                    
                    # Update bbox data with extracted text
                    if isinstance(bbox_data, BoundingBoxData):
                        bbox_data.text = extracted_text
                        annotation_create.annotation_data = bbox_data
                    
                except Exception as azure_error:
                    print(f"!!! AZURE DI EXTRACTION ERROR: {azure_error}")
                    import traceback
                    traceback.print_exc()
                    # Continue with empty value if extraction fails
            
            # Save annotation
            repo = DjangoORMRepository()
            annotation_data = annotation_create.model_dump(mode="json")
            annotation_id = repo.save_ground_truth_annotation(annotation_data)
            
            # Fetch and return created annotation
            annotation = repo.get_ground_truth_annotation(annotation_id)
            
            response = GroundTruthAnnotationResponse(annotation=annotation)
            return Response(
                response.model_dump(mode="json"),
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Error creating annotation: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class GroundTruthAnnotationDetailView(APIView):
    """Retrieve, update, or delete a specific ground truth annotation."""
    
    def get(self, request, annotation_id: str):
        """Get a specific annotation."""
        try:
            repo = DjangoORMRepository()
            annotation = repo.get_ground_truth_annotation(annotation_id)
            
            if not annotation:
                return Response(
                    {"detail": "Annotation not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            response = GroundTruthAnnotationResponse(annotation=annotation)
            return Response(response.model_dump(mode="json"))
            
        except Exception as e:
            logger.error(f"Error fetching annotation {annotation_id}: {e}")
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def patch(self, request, annotation_id: str):
        """Update an annotation."""
        try:
            # Validate update data
            annotation_update = GroundTruthAnnotationUpdate(**request.data)
            
            # Update annotation
            repo = DjangoORMRepository()
            updates = annotation_update.model_dump(mode="json", exclude_none=True)
            success = repo.update_ground_truth_annotation(annotation_id, updates)
            
            if not success:
                return Response(
                    {"detail": "Annotation not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Fetch and return updated annotation
            annotation = repo.get_ground_truth_annotation(annotation_id)
            response = GroundTruthAnnotationResponse(annotation=annotation)
            return Response(response.model_dump(mode="json"))
            
        except Exception as e:
            logger.error(f"Error updating annotation {annotation_id}: {e}")
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def delete(self, request, annotation_id: str):
        """Delete an annotation."""
        try:
            repo = DjangoORMRepository()
            success = repo.delete_ground_truth_annotation(annotation_id)
            
            if not success:
                return Response(
                    {"detail": "Annotation not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response(
                {"status": "deleted", "annotation_id": annotation_id},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error deleting annotation {annotation_id}: {e}")
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnnotationSuggestionView(APIView):
    """Generate AI annotation suggestions for a document."""
    
    def post(self, request, document_id: str):
        """Generate annotation suggestions."""
        try:
            # Get document and document type
            doc_repo = get_document_repository()
            document = doc_repo.get_document(document_id)
            
            if not document:
                return Response(
                    {"detail": "Document not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get document type from classification
            from uu_backend.repositories.django_repo import DjangoORMRepository
            repo = DjangoORMRepository()
            classification = repo.get_classification(document_id)
            
            if not classification:
                return Response(
                    {"detail": "Document not classified. Please classify the document first."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            document_type = repo.get_document_type(classification.document_type_id)
            
            if not document_type or not document_type.schema_fields:
                return Response(
                    {"detail": "Document type has no schema fields defined"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate suggestions
            suggestion_service = get_annotation_suggestion_service()
            suggestions = async_to_sync(suggestion_service.suggest_annotations)(
                document_id,
                document_type
            )
            
            from uu_backend.models.annotation import AnnotationSuggestionResponse
            response = AnnotationSuggestionResponse(
                suggestions=suggestions,
                total=len(suggestions)
            )
            
            return Response(response.model_dump(mode="json"))
            
        except Exception as e:
            logger.error(f"Error generating suggestions for document {document_id}: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ApproveAnnotationView(APIView):
    """Approve an AI suggestion and convert to ground truth."""
    
    def post(self, request, annotation_id: str):
        """Approve an annotation suggestion."""
        try:
            # Parse request
            approve_request = ApproveAnnotationRequest(**request.data)
            
            # Approve annotation
            repo = DjangoORMRepository()
            success = repo.approve_annotation(
                annotation_id,
                edited_value=approve_request.edited_value
            )
            
            if not success:
                return Response(
                    {"detail": "Annotation not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Fetch and return approved annotation
            annotation = repo.get_ground_truth_annotation(annotation_id)
            response = GroundTruthAnnotationResponse(annotation=annotation)
            return Response(response.model_dump(mode="json"))
            
        except Exception as e:
            logger.error(f"Error approving annotation {annotation_id}: {e}")
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class RejectAnnotationView(APIView):
    """Reject an AI suggestion."""
    
    def post(self, request, annotation_id: str):
        """Reject an annotation suggestion (delete it)."""
        try:
            repo = DjangoORMRepository()
            success = repo.delete_ground_truth_annotation(annotation_id)
            
            if not success:
                return Response(
                    {"detail": "Annotation not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response(
                {"status": "rejected", "annotation_id": annotation_id},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error rejecting annotation {annotation_id}: {e}")
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
