"""Value matching service for comparing ground truth vs predicted values."""

import json
import logging
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Optional

from uu_backend.models.evaluation import MatchResult, MatchType
from uu_backend.models.taxonomy import FieldType
from uu_backend.llm.openai_client import get_openai_client

logger = logging.getLogger(__name__)


class ValueMatcher:
    """Service for comparing values with hybrid matching strategies."""
    
    def __init__(self):
        self.openai_client = get_openai_client()
        self._semantic_cache: dict[str, MatchResult] = {}
    
    def compare_values(
        self,
        ground_truth: Any,
        predicted: Any,
        field_type: Optional[FieldType] = None
    ) -> MatchResult:
        """
        Compare two values using hybrid matching strategy.
        
        Args:
            ground_truth: Ground truth value
            predicted: Predicted value
            field_type: Optional field type hint for better matching
            
        Returns:
            MatchResult with match status, type, and confidence
        """
        # Handle None/null cases
        if ground_truth is None and predicted is None:
            return MatchResult(
                is_match=True,
                match_type=MatchType.EXACT,
                confidence=1.0,
                reason="Both values are None"
            )
        
        if ground_truth is None or predicted is None:
            return MatchResult(
                is_match=False,
                match_type=MatchType.NO_MATCH,
                confidence=1.0,
                reason="One value is None"
            )
        
        # 1. Try exact match first (fastest)
        exact_result = self._exact_match(ground_truth, predicted)
        if exact_result.is_match:
            return exact_result
        
        # 2. Try normalized number match (detect numbers even without field type)
        gt_num = self._normalize_number(ground_truth)
        pred_num = self._normalize_number(predicted)
        if gt_num is not None and pred_num is not None:
            if abs(gt_num - pred_num) < 0.01:
                return MatchResult(
                    is_match=True,
                    match_type=MatchType.NORMALIZED,
                    confidence=1.0,
                    reason=f"Normalized numbers: {gt_num} vs {pred_num}"
                )
        
        # 3. Try normalized date match (detect dates even without field type)
        gt_date = self._normalize_date(ground_truth)
        pred_date = self._normalize_date(predicted)
        if gt_date is not None and pred_date is not None:
            if gt_date == pred_date:
                return MatchResult(
                    is_match=True,
                    match_type=MatchType.NORMALIZED,
                    confidence=1.0,
                    reason=f"Normalized dates: {gt_date} vs {pred_date}"
                )
        
        # 4. Try fuzzy match for strings
        if isinstance(ground_truth, str) or isinstance(predicted, str):
            fuzzy_result = self._fuzzy_match(ground_truth, predicted)
            # Accept fuzzy match at 0.85+ confidence
            if fuzzy_result.confidence >= 0.85:
                return fuzzy_result
            # For high-ish confidence (0.7+), don't bother with LLM
            if fuzzy_result.confidence >= 0.7:
                fuzzy_result.match_type = MatchType.FUZZY
                fuzzy_result.reason = f"Partial match: {fuzzy_result.confidence:.2f}"
                return fuzzy_result
        
        # 5. Fall back to LLM semantic match only for truly ambiguous cases
        # Skip LLM if values are very different (fuzzy < 0.3)
        if isinstance(ground_truth, str) and isinstance(predicted, str):
            quick_ratio = SequenceMatcher(None, str(ground_truth).lower(), str(predicted).lower()).ratio()
            if quick_ratio < 0.3:
                return MatchResult(
                    is_match=False,
                    match_type=MatchType.NO_MATCH,
                    confidence=quick_ratio,
                    reason="Values too different to be equivalent"
                )
        
        return self._semantic_match(ground_truth, predicted)
    
    def _exact_match(self, ground_truth: Any, predicted: Any) -> MatchResult:
        """Check for exact equality."""
        is_match = ground_truth == predicted
        return MatchResult(
            is_match=is_match,
            match_type=MatchType.EXACT if is_match else MatchType.NO_MATCH,
            confidence=1.0 if is_match else 0.0,
            reason="Exact match" if is_match else "Values differ"
        )
    
    def _normalized_match(
        self,
        ground_truth: Any,
        predicted: Any,
        field_type: FieldType
    ) -> MatchResult:
        """Match after normalization (currency, dates, etc.)."""
        try:
            if field_type == FieldType.NUMBER:
                gt_norm = self._normalize_number(ground_truth)
                pred_norm = self._normalize_number(predicted)
                
                if gt_norm is not None and pred_norm is not None:
                    # Allow small floating point differences
                    is_match = abs(gt_norm - pred_norm) < 0.01
                    return MatchResult(
                        is_match=is_match,
                        match_type=MatchType.NORMALIZED if is_match else MatchType.NO_MATCH,
                        confidence=1.0 if is_match else 0.0,
                        reason=f"Normalized numbers: {gt_norm} vs {pred_norm}"
                    )
            
            elif field_type == FieldType.DATE:
                gt_norm = self._normalize_date(ground_truth)
                pred_norm = self._normalize_date(predicted)
                
                if gt_norm is not None and pred_norm is not None:
                    is_match = gt_norm == pred_norm
                    return MatchResult(
                        is_match=is_match,
                        match_type=MatchType.NORMALIZED if is_match else MatchType.NO_MATCH,
                        confidence=1.0 if is_match else 0.0,
                        reason=f"Normalized dates: {gt_norm} vs {pred_norm}"
                    )
        
        except Exception as e:
            logger.warning(f"Normalization failed: {e}")
        
        return MatchResult(
            is_match=False,
            match_type=MatchType.NO_MATCH,
            confidence=0.0,
            reason="Normalization failed or values don't match"
        )
    
    def _normalize_number(self, value: Any) -> Optional[float]:
        """Normalize a number value (handle currency, commas, etc.)."""
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Remove currency symbols, commas, whitespace
            cleaned = re.sub(r'[$,\s€£¥]', '', value.strip())
            
            # Handle parentheses for negative numbers
            if cleaned.startswith('(') and cleaned.endswith(')'):
                cleaned = '-' + cleaned[1:-1]
            
            try:
                return float(cleaned)
            except ValueError:
                return None
        
        return None
    
    def _normalize_date(self, value: Any) -> Optional[str]:
        """Normalize a date value to ISO format."""
        if isinstance(value, datetime):
            return value.date().isoformat()
        
        if isinstance(value, str):
            # Try common date formats
            formats = [
                '%Y-%m-%d',
                '%m/%d/%Y',
                '%d/%m/%Y',
                '%m-%d-%Y',
                '%d-%m-%Y',
                '%Y/%m/%d',
                '%B %d, %Y',
                '%b %d, %Y',
                '%d %B %Y',
                '%d %b %Y',
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(value.strip(), fmt)
                    return dt.date().isoformat()
                except ValueError:
                    continue
        
        return None
    
    def _fuzzy_match(self, ground_truth: Any, predicted: Any) -> MatchResult:
        """Fuzzy string matching using similarity ratio."""
        gt_str = str(ground_truth).lower().strip()
        pred_str = str(predicted).lower().strip()
        
        # Calculate similarity ratio
        ratio = SequenceMatcher(None, gt_str, pred_str).ratio()
        
        # Also check token overlap for better matching
        gt_tokens = set(re.findall(r'\w+', gt_str))
        pred_tokens = set(re.findall(r'\w+', pred_str))
        
        if gt_tokens and pred_tokens:
            token_overlap = len(gt_tokens & pred_tokens) / len(gt_tokens | pred_tokens)
            # Use max of character similarity and token overlap
            confidence = max(ratio, token_overlap)
        else:
            confidence = ratio
        
        is_match = confidence >= 0.85
        
        return MatchResult(
            is_match=is_match,
            match_type=MatchType.FUZZY if is_match else MatchType.NO_MATCH,
            confidence=confidence,
            reason=f"Fuzzy match confidence: {confidence:.2f}"
        )
    
    def _semantic_match(self, ground_truth: Any, predicted: Any) -> MatchResult:
        """Use LLM to determine semantic equivalence."""
        # Create cache key
        cache_key = f"{str(ground_truth)}||{str(predicted)}"
        
        # Check cache
        if cache_key in self._semantic_cache:
            return self._semantic_cache[cache_key]
        
        try:
            prompt = f"""Compare these two values and determine if they are semantically equivalent.
Consider that they might be formatted differently but represent the same information.

Ground Truth: {ground_truth}
Predicted: {predicted}

Respond with a JSON object:
{{
    "is_match": true/false,
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}"""
            
            result_data = self.openai_client.complete_json(prompt=prompt, max_tokens=500)
            
            result = MatchResult(
                is_match=result_data.get("is_match", False),
                match_type=MatchType.SEMANTIC if result_data.get("is_match") else MatchType.NO_MATCH,
                confidence=result_data.get("confidence", 0.5),
                reason=result_data.get("reason", "LLM semantic comparison")
            )
            
            # Cache the result
            self._semantic_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Semantic matching failed: {e}")
            return MatchResult(
                is_match=False,
                match_type=MatchType.NO_MATCH,
                confidence=0.0,
                reason=f"Semantic matching error: {str(e)}"
            )


# Singleton instance
_value_matcher: Optional[ValueMatcher] = None


def get_value_matcher() -> ValueMatcher:
    """Get or create value matcher singleton."""
    global _value_matcher
    if _value_matcher is None:
        _value_matcher = ValueMatcher()
    return _value_matcher
