"""Timeline data endpoints."""

from datetime import date

from fastapi import APIRouter, Query

from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.timeline import TimelineResponse

router = APIRouter()


@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(
    start_date: date | None = Query(
        None,
        description="Filter documents from this date (inclusive)",
    ),
    end_date: date | None = Query(
        None,
        description="Filter documents until this date (inclusive)",
    ),
):
    """
    Get documents grouped by date for timeline visualization.

    Returns documents organized by their extracted dates, suitable for
    rendering as a timeline. Documents without dates are excluded.

    Query parameters:
    - start_date: Optional ISO date to filter from
    - end_date: Optional ISO date to filter until
    """
    store = get_vector_store()

    return store.get_timeline(
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/timeline/range")
async def get_timeline_range():
    """
    Get the date range of all documents.

    Returns the earliest and latest dates found in the document corpus.
    Useful for initializing timeline controls.
    """
    store = get_vector_store()
    timeline = store.get_timeline()

    return {
        "earliest": timeline.date_range.earliest,
        "latest": timeline.date_range.latest,
        "total_documents": timeline.total_documents,
    }
