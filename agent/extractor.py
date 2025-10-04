"""
Parameter extraction from natural language questions.

Uses Claude's structured output for deterministic parameter extraction.
Rationale: CEO resolution #2 - Replace JSON parsing with function-calling schema.
Implements validation, confidence scoring, and ALCOA+ compliance.
"""
import json
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, validator


class ExtractedParams(BaseModel):
    """Structured parameters extracted from a question with validation."""

    # Common filters
    device_class: Optional[str] = Field(None, description="Device class: 1, 2, or 3")
    product_code: Optional[str] = Field(None, description="3-letter product code (e.g., LZG)")

    @validator('device_class')
    def validate_device_class(cls, v):
        """Ensure device class is 1, 2, or 3."""
        if v and str(v) not in ['1', '2', '3']:
            # Try to normalize roman numerals
            mapping = {'I': '1', 'II': '2', 'III': '3'}
            v = mapping.get(v.upper(), v)
            if str(v) not in ['1', '2', '3']:
                raise ValueError(f"Device class must be 1, 2, or 3, got: {v}")
        return str(v) if v else None

    @validator('product_code')
    def validate_product_code(cls, v):
        """Ensure product code is 3 uppercase letters."""
        if v:
            v = v.upper().strip()
            if not re.match(r'^[A-Z]{3}$', v):
                raise ValueError(f"Product code must be 3 letters, got: {v}")
        return v

    # Date ranges
    date_start: Optional[str] = Field(None, description="Start date in YYYYMMDD format")
    date_end: Optional[str] = Field(None, description="End date in YYYYMMDD format")

    @validator('date_start', 'date_end')
    def validate_date_format(cls, v):
        """Ensure dates are in YYYYMMDD format."""
        if v:
            # Remove any hyphens or slashes
            v = v.replace('-', '').replace('/', '')
            if not re.match(r'^\d{8}$', v):
                raise ValueError(f"Date must be YYYYMMDD format, got: {v}")
            # Validate it's a real date
            try:
                datetime.strptime(v, '%Y%m%d')
            except ValueError:
                raise ValueError(f"Invalid date: {v}")
        return v

    # Identifiers
    k_number: Optional[str] = Field(None, description="510(k) number (e.g., K123456)")
    pma_number: Optional[str] = Field(None, description="PMA number (e.g., P123456)")
    recall_number: Optional[str] = Field(None, description="Recall number")
    fei_number: Optional[str] = Field(None, description="FEI establishment number")

    # Names/text filters
    firm_name: Optional[str] = Field(None, description="Company/firm name")
    device_name: Optional[str] = Field(None, description="Device name or brand")
    applicant: Optional[str] = Field(None, description="Applicant/sponsor name")

    # Location
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, description="US state code (e.g., CA)")
    country: Optional[str] = Field(None, description="Country code (e.g., US)")

    # Classification
    recall_class: Optional[str] = Field(None, description="Recall class: 'Class I', 'Class II', or 'Class III'")
    event_type: Optional[str] = Field(None, description="Event type: Malfunction, Injury, Death")

    # Aggregation
    count_field: Optional[str] = Field(None, description="Field to count/aggregate by")

    # Limits
    limit: int = Field(10, description="Number of results to return")


EXTRACTION_PROMPT = """You are a parameter extraction assistant for the openFDA API.

Extract structured parameters from the user's question. Return ONLY a JSON object with the extracted values.

Rules:
1. Extract dates in YYYYMMDD format (e.g., "since 2023" → date_start: "20230101")
2. Device class should be "1", "2", or "3" (not "I", "II", "III")
3. Recall class should be "Class I", "Class II", or "Class III" (include "Class ")
4. Product codes are ALWAYS 3-letter codes (e.g., NBE, LZG, DQA) - NEVER confuse with device class
5. If no date is mentioned, leave date_start/date_end null
6. For "how many" questions, set count_field to the appropriate field
7. If user says "last year", calculate from current date (2025)
8. Use limit=10 by default, unless user specifies different number
9. Extract company/firm names as applicant or firm_name
10. Extract device types (like "insulin pumps", "orthopedic implants") as device_name
11. Extract state names and convert to 2-letter codes (California → CA)

Examples:

Q: "Show me Class II devices"
A: {{"device_class": "2", "limit": 10}}

Q: "Find 510k clearances from Medtronic since 2023"
A: {{"applicant": "Medtronic", "date_start": "20230101", "date_end": "20251231", "limit": 10}}

Q: "What Class I recalls happened last year?"
A: {{"recall_class": "Class I", "date_start": "20240101", "date_end": "20241231", "limit": 10}}

Q: "How many adverse events for pacemakers?"
A: {{"device_name": "pacemaker", "count_field": "device.generic_name", "limit": 100}}

Q: "Show me the first 20 establishments in California"
A: {{"state": "CA", "limit": 20}}

Q: "How many Class III devices have product code NBE?"
A: {{"device_class": "3", "product_code": "NBE", "count_field": "product_code", "limit": 100}}

Q: "PMA approvals from Abbott Laboratories"
A: {{"applicant": "Abbott Laboratories", "limit": 10}}

Q: "Adverse events for insulin pumps"
A: {{"device_name": "insulin pump", "limit": 10}}

Now extract parameters from this question:
"""


def extracted_params_to_query_string(params: ExtractedParams) -> str:
    """
    Convert ExtractedParams to a human-readable query string for assessor validation.

    Args:
        params: Extracted parameters

    Returns:
        String representation of filters applied
    """
    parts = []

    if params.device_class:
        parts.append(f"device_class:{params.device_class}")
    if params.product_code:
        parts.append(f"product_code:{params.product_code}")
    if params.date_start or params.date_end:
        date_range = f"{params.date_start or 'start'} TO {params.date_end or 'end'}"
        parts.append(f"date_range:[{date_range}]")
    if params.k_number:
        parts.append(f"k_number:{params.k_number}")
    if params.pma_number:
        parts.append(f"pma_number:{params.pma_number}")
    if params.recall_number:
        parts.append(f"recall_number:{params.recall_number}")
    if params.recall_class:
        parts.append(f"recall_class:{params.recall_class}")
    if params.firm_name:
        parts.append(f"firm_name:{params.firm_name}")
    if params.applicant:
        parts.append(f"applicant:{params.applicant}")
    if params.device_name:
        parts.append(f"device_name:{params.device_name}")
    if params.city:
        parts.append(f"city:{params.city}")
    if params.state:
        parts.append(f"state:{params.state}")
    if params.country:
        parts.append(f"country:{params.country}")
    if params.event_type:
        parts.append(f"event_type:{params.event_type}")

    return " AND ".join(parts) if parts else "no filters"


def generate_lucene_query(params: ExtractedParams, endpoint: str) -> str:
    """
    Generate proper Lucene query string for openFDA API.

    CEO Resolution #4: Create actual Lucene queries for provenance and audit trail.
    Maps parameters to endpoint-specific field names as per openFDA documentation.

    Args:
        params: Extracted parameters
        endpoint: Target endpoint name (classification, 510k, pma, recall, maude, udi, rl_search)

    Returns:
        Lucene query string ready for openFDA API
    """
    parts = []

    # Endpoint-specific field mappings
    if endpoint == "classification":
        if params.product_code:
            parts.append(f'product_code:"{params.product_code}"')
        if params.device_class:
            parts.append(f'device_class:"{params.device_class}"')
        if params.device_name:
            parts.append(f'device_name:"{params.device_name}"')

    elif endpoint == "510k":
        if params.k_number:
            parts.append(f'k_number:"{params.k_number}"')
        if params.applicant:
            parts.append(f'applicant:"{params.applicant}"')
        if params.product_code:
            parts.append(f'product_code:"{params.product_code}"')
        if params.device_name:
            parts.append(f'device_name:"{params.device_name}"')
        if params.date_start or params.date_end:
            start = params.date_start or "19760101"
            end = params.date_end or datetime.now().strftime("%Y%m%d")
            parts.append(f'decision_date:[{start} TO {end}]')

    elif endpoint == "pma":
        if params.pma_number:
            parts.append(f'pma_number:"{params.pma_number}"')
        if params.applicant:
            parts.append(f'applicant:"{params.applicant}"')
        if params.product_code:
            parts.append(f'product_code:"{params.product_code}"')
        if params.device_name:
            parts.append(f'trade_name:"{params.device_name}"')
        if params.date_start or params.date_end:
            start = params.date_start or "19760101"
            end = params.date_end or datetime.now().strftime("%Y%m%d")
            parts.append(f'decision_date:[{start} TO {end}]')

    elif endpoint == "recall":
        if params.recall_number:
            parts.append(f'recall_number:"{params.recall_number}"')
        if params.recall_class:
            # Map "Class I" to "Class I", etc.
            parts.append(f'classification:"{params.recall_class}"')
        if params.firm_name:
            parts.append(f'recalling_firm:"{params.firm_name}"')
        if params.product_code:
            parts.append(f'product_code:"{params.product_code}"')
        if params.date_start or params.date_end:
            start = params.date_start or "20040101"
            end = params.date_end or datetime.now().strftime("%Y%m%d")
            parts.append(f'recall_initiation_date:[{start} TO {end}]')

    elif endpoint == "maude":
        if params.device_name:
            parts.append(f'device.generic_name:"{params.device_name}"')
        if params.product_code:
            parts.append(f'device.openfda.product_code:"{params.product_code}"')
        if params.event_type:
            parts.append(f'event_type:"{params.event_type}"')
        if params.date_start or params.date_end:
            start = params.date_start or "19910101"
            end = params.date_end or datetime.now().strftime("%Y%m%d")
            parts.append(f'date_received:[{start} TO {end}]')

    elif endpoint == "udi":
        if params.device_name:
            parts.append(f'brand_name:"{params.device_name}"')
        if params.firm_name:
            parts.append(f'company_name:"{params.firm_name}"')
        if params.product_code:
            parts.append(f'product_codes.code:"{params.product_code}"')

    elif endpoint == "rl_search":
        if params.firm_name:
            parts.append(f'proprietary_name:"{params.firm_name}"')
        if params.fei_number:
            parts.append(f'registration.fei_number:"{params.fei_number}"')
        if params.city:
            parts.append(f'registration.address.city:"{params.city}"')
        if params.state:
            parts.append(f'registration.address.state_code:"{params.state}"')
        if params.country:
            parts.append(f'registration.address.iso_country_code:"{params.country}"')
        if params.product_code:
            parts.append(f'products.product_code:"{params.product_code}"')

    return " AND ".join(parts) if parts else ""


class ParameterExtractor:
    """Extracts structured parameters from natural language questions."""

    # Regex patterns for precise extraction
    PRODUCT_CODE_PATTERN = r'\b([A-Z]{3})\b'
    K_NUMBER_PATTERN = r'\b(K\d{6})\b'
    P_NUMBER_PATTERN = r'\b(P\d{6})\b'

    def __init__(self, llm: ChatAnthropic):
        """
        Initialize extractor.

        Args:
            llm: Claude LLM instance
        """
        self.llm = llm

    def _apply_regex_extraction(self, question: str) -> Dict[str, Any]:
        """
        Apply regex patterns to extract obvious entities before LLM call.

        Rationale: CEO resolution #9 - reduce LLM wiggle with regex.
        """
        pre_extracted = {}

        # K-number
        k_match = re.search(self.K_NUMBER_PATTERN, question)
        if k_match:
            pre_extracted["k_number"] = k_match.group(1)

        # P-number
        p_match = re.search(self.P_NUMBER_PATTERN, question)
        if p_match:
            pre_extracted["pma_number"] = p_match.group(1)

        # Product code (handle "product code", "procode", or just "code")
        if re.search(r'product\s+code|procode|code\s+[A-Z]{3}\b', question, re.IGNORECASE):
            code_match = re.search(self.PRODUCT_CODE_PATTERN, question)
            if code_match:
                pre_extracted["product_code"] = code_match.group(1)

        return pre_extracted

    def _normalize_class(self, params_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize class fields to standard format.

        Device class: 1, 2, or 3 (numeric)
        Recall class: "Class I", "Class II", "Class III" (with "Class " prefix)
        """
        # Device class normalization (roman → numeric)
        if params_dict.get("device_class"):
            dc = str(params_dict["device_class"]).upper().strip()
            if dc in ["I", "1"]:
                params_dict["device_class"] = "1"
            elif dc in ["II", "2"]:
                params_dict["device_class"] = "2"
            elif dc in ["III", "3"]:
                params_dict["device_class"] = "3"

        # Recall class normalization (ensure "Class " prefix)
        if params_dict.get("recall_class"):
            rc = str(params_dict["recall_class"]).strip()
            # Normalize roman numerals
            if rc.upper() == "I" or rc == "1":
                params_dict["recall_class"] = "Class I"
            elif rc.upper() == "II" or rc == "2":
                params_dict["recall_class"] = "Class II"
            elif rc.upper() == "III" or rc == "3":
                params_dict["recall_class"] = "Class III"
            # Ensure "Class " prefix if missing
            elif not rc.startswith("Class"):
                params_dict["recall_class"] = f"Class {rc}"

        return params_dict

    def extract_with_confidence(self, question: str, confidence_threshold: float = 0.8) -> Tuple[ExtractedParams, Dict[str, float]]:
        """
        Extract parameters from question using structured outputs.

        CEO Resolution #2: Uses Claude's function-calling for deterministic extraction.
        Includes confidence scoring for each field.

        Args:
            question: User's natural language question
            confidence_threshold: Minimum confidence for extraction (triggers RAG if below)

        Returns:
            Tuple of (ExtractedParams, confidence_scores dict)
        """
        # Step 1: Apply regex extraction for obvious patterns (high confidence)
        pre_extracted = self._apply_regex_extraction(question)
        confidence_scores = {k: 1.0 for k in pre_extracted.keys()}  # Regex matches have high confidence

        # Step 2: Use structured output with LLM
        try:
            # Create LLM with structured output
            structured_llm = self.llm.with_structured_output(ExtractedParams)

            # Create prompt with examples
            messages = [
                SystemMessage(content=EXTRACTION_PROMPT),
                HumanMessage(content=question),
            ]

            # Get structured response directly
            extracted_params = structured_llm.invoke(messages)

            # Merge regex results (prefer regex over LLM for these fields)
            for field, value in pre_extracted.items():
                setattr(extracted_params, field, value)

            # Step 3: Calculate confidence scores for LLM-extracted fields
            # (In production, this would use a separate confidence model)
            for field_name, field_value in extracted_params.model_dump().items():
                if field_value and field_name not in confidence_scores:
                    # Simple heuristic: longer values and specific patterns have higher confidence
                    if field_name in ['k_number', 'pma_number', 'product_code']:
                        confidence_scores[field_name] = 0.95  # Structured format
                    elif field_name in ['date_start', 'date_end']:
                        confidence_scores[field_name] = 0.9  # Date patterns
                    elif field_name in ['device_class', 'recall_class']:
                        confidence_scores[field_name] = 0.85  # Enumerated values
                    else:
                        confidence_scores[field_name] = 0.7  # Free text fields

            return extracted_params, confidence_scores

        except Exception as e:
            # Fallback with logging (for audit trail)
            print(f"[Extractor] Structured output failed: {e}")
            print(f"[Extractor] Falling back to regex results")

            # Return regex-only results with high confidence
            fallback_params = ExtractedParams(**pre_extracted) if pre_extracted else ExtractedParams()
            return fallback_params, confidence_scores

    def extract(self, question: str) -> ExtractedParams:
        """
        Backward-compatible extraction method.

        Args:
            question: User's natural language question

        Returns:
            ExtractedParams with structured fields
        """
        params, _ = self.extract_with_confidence(question)
        return params
