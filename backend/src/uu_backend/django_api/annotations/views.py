"""API views for ground truth annotations."""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.models.annotation import (
    ApproveAnnotationRequest,
    GroundTruthAnnotationCreate,
    GroundTruthAnnotationListResponse,
    GroundTruthAnnotationResponse,
    GroundTruthAnnotationUpdate,
)
from uu_backend.repositories.django_repo import DjangoORMRepository
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.services.annotation_suggestion_service import get_annotation_suggestion_service

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
            suggestions = suggestion_service.suggest_annotations(
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
