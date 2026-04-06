"""Date extraction from document content."""

import re
from datetime import datetime
from typing import NamedTuple

from dateutil import parser as date_parser
from dateutil.parser import ParserError


class ExtractedDate(NamedTuple):
    """A date extracted from text with its context."""

    date: datetime
    original_text: str
    position: int
    confidence: float


class DateExtractor:
    """Extract dates from document content."""

    # Common date patterns
    DATE_PATTERNS = [
        # ISO format: 2024-01-15, 2024/01/15
        r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b",
        # US format: 01/15/2024, 1/15/24
        r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",
        # European format: 15-01-2024, 15.01.2024
        r"\b(\d{1,2}[-\.]\d{1,2}[-\.]\d{2,4})\b",
        # Written format: January 15, 2024 or Jan 15, 2024
        r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})\b",
        # Written format: 15 January 2024
        r"\b(\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})\b",
        # Month Year: January 2024
        r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{4})\b",
    ]

    def __init__(self):
        """Initialize the date extractor."""
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.DATE_PATTERNS
        ]

    def extract_all(self, content: str) -> list[ExtractedDate]:
        """Extract all dates from content.

        Parameters
        ----------
        content : str
            The text to extract dates from.

        Returns
        -------
        list[ExtractedDate]
            List of ExtractedDate objects, sorted by position.
        """
        dates: list[ExtractedDate] = []
        seen_positions: set[int] = set()

        for pattern_idx, pattern in enumerate(self._compiled_patterns):
            for match in pattern.finditer(content):
                position = match.start()

                # Skip if we've already found a date at this position
                if any(abs(position - seen) < 5 for seen in seen_positions):
                    continue

                original_text = match.group(1)

                try:
                    parsed_date = date_parser.parse(
                        original_text,
                        fuzzy=True,
                        dayfirst=pattern_idx == 2,  # European format
                    )

                    # Validate the date is reasonable (not too far in past/future)
                    if self._is_reasonable_date(parsed_date):
                        # Earlier patterns are more specific, higher confidence
                        confidence = 1.0 - (pattern_idx * 0.1)

                        dates.append(
                            ExtractedDate(
                                date=parsed_date,
                                original_text=original_text,
                                position=position,
                                confidence=max(0.5, confidence),
                            )
                        )
                        seen_positions.add(position)

                except (ParserError, ValueError, OverflowError):
                    continue

        # Sort by position in document
        return sorted(dates, key=lambda d: d.position)

    def extract_primary(self, content: str) -> datetime | None:
        """Extract the primary (most relevant) date from content.

        Prefers dates near the start of the document and higher-confidence formats.

        Parameters
        ----------
        content : str
            The text to extract dates from.

        Returns
        -------
        datetime or None
            The primary date, or None if no dates found.
        """
        dates = self.extract_all(content)

        if not dates:
            return None

        # Score each date based on position and confidence
        scored_dates: list[tuple[float, ExtractedDate]] = []

        for extracted in dates:
            # Position score: earlier is better (normalize to 0-1)
            position_score = 1.0 - min(extracted.position / 1000, 1.0)

            # Combined score
            score = (extracted.confidence * 0.6) + (position_score * 0.4)

            scored_dates.append((score, extracted))

        # Return the highest-scoring date
        scored_dates.sort(key=lambda x: x[0], reverse=True)
        return scored_dates[0][1].date

    def _is_reasonable_date(self, date: datetime) -> bool:
        now = datetime.now()

        # Accept dates from 1900 to 10 years in the future
        min_date = datetime(1900, 1, 1)
        max_date = datetime(now.year + 10, 12, 31)

        return min_date <= date <= max_date


# Module-level instance
_extractor: DateExtractor | None = None


def get_date_extractor() -> DateExtractor:
    """Get or create a DateExtractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = DateExtractor()
    return _extractor


def extract_date(content: str) -> datetime | None:
    """Convenience function to extract the primary date from content."""
    return get_date_extractor().extract_primary(content)
