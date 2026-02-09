"""Timeline-related Pydantic models."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class TimelineDocument(BaseModel):
    """Document representation in timeline view."""

    id: str
    filename: str
    file_type: str
    title: str | None = None
    excerpt: str | None = None


class TimelineEntry(BaseModel):
    """A single entry in the timeline (one date)."""

    date: date
    document_count: int
    documents: list[TimelineDocument]


class DateRange(BaseModel):
    """Date range for timeline data."""

    earliest: date | None = None
    latest: date | None = None


class TimelineResponse(BaseModel):
    """Response containing timeline data."""

    timeline: list[TimelineEntry]
    date_range: DateRange
    total_documents: int


class TimelineQuery(BaseModel):
    """Query parameters for timeline endpoint."""

    start_date: date | None = None
    end_date: date | None = None
    aggregation: Literal["day", "week", "month"] = "day"


class UndatedDocuments(BaseModel):
    """Container for documents without extracted dates."""

    documents: list[TimelineDocument]
    count: int
