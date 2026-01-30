"""
FastAPI router for the FDA Lookup API.
"""
import logging
import re
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from pathlib import Path

from .models import (
    EntityType,
    IdentifierType,
    IdentifyRequest,
    IdentifyResponse,
    DeviceReportResponse,
    ManufacturerReportResponse,
)
from .input_detector import InputDetector
from .device_report import DeviceReportGenerator
from .manufacturer_report import ManufacturerReportGenerator
from ..llm_factory import LLMFactory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["lookup"])

# Global instances (lazily initialized)
_detector: Optional[InputDetector] = None
_device_generator: Optional[DeviceReportGenerator] = None
_manufacturer_generator: Optional[ManufacturerReportGenerator] = None
_llm = None


class SummaryRequest(BaseModel):
    entity_type: str
    identifier: str
    report_data: dict[str, Any]


class SummaryResponse(BaseModel):
    summary: str


class FollowupRequest(BaseModel):
    entity_type: str
    identifier: str
    report_summary: str
    question: str


class FollowupResponse(BaseModel):
    answer: str


def get_llm():
    global _llm
    if _llm is None:
        _llm = LLMFactory.create(provider="fireworks", temperature=0.3)
    return _llm


def _strip_thinking_tags(text: str) -> str:
    """Strip <think>...</think> tags from LLM output."""
    return re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL).strip()


def _get_db_path() -> str:
    """Get the path to the GUDID database."""
    return str(Path(__file__).parent.parent.parent.parent / "data" / "gudid.db")


def get_detector() -> InputDetector:
    """Get or create the input detector."""
    global _detector
    if _detector is None:
        _detector = InputDetector(_get_db_path())
    return _detector


def get_device_generator() -> DeviceReportGenerator:
    """Get or create the device report generator."""
    global _device_generator
    if _device_generator is None:
        _device_generator = DeviceReportGenerator(_get_db_path())
    return _device_generator


def get_manufacturer_generator() -> ManufacturerReportGenerator:
    """Get or create the manufacturer report generator."""
    global _manufacturer_generator
    if _manufacturer_generator is None:
        _manufacturer_generator = ManufacturerReportGenerator(_get_db_path())
    return _manufacturer_generator


@router.post("/identify", response_model=IdentifyResponse)
async def identify_input(request: IdentifyRequest) -> IdentifyResponse:
    """
    Identify the type of input and return matching candidates.

    For specific identifiers (product codes, K-numbers, etc.), returns
    a direct match. For generic text, returns disambiguation candidates.
    """
    if not request.input or not request.input.strip():
        raise HTTPException(status_code=400, detail="Input is required")

    try:
        detector = get_detector()
        result = await detector.identify(request.input.strip())
        return result
    except Exception as e:
        logger.exception(f"Error identifying input: {request.input}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/device/{identifier}", response_model=DeviceReportResponse)
async def get_device_report(
    identifier: str,
    type: str = Query(
        default="product_code",
        description="Type of identifier: product_code, primary_di, k_number, pma_number"
    ),
) -> DeviceReportResponse:
    """
    Get a comprehensive device report.

    Returns classification, adverse events, recalls, 510(k) clearances,
    UDI data, and top manufacturers for the device type.
    """
    # Map string type to enum
    type_map = {
        "product_code": IdentifierType.PRODUCT_CODE,
        "primary_di": IdentifierType.PRIMARY_DI,
        "k_number": IdentifierType.K_NUMBER,
        "pma_number": IdentifierType.PMA_NUMBER,
    }

    identifier_type = type_map.get(type.lower())
    if identifier_type is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type '{type}'. Must be one of: {', '.join(type_map.keys())}"
        )

    try:
        generator = get_device_generator()
        report = await generator.generate(identifier, identifier_type)
        return report
    except Exception as e:
        logger.exception(f"Error generating device report for {identifier}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/manufacturer/{identifier}", response_model=ManufacturerReportResponse)
async def get_manufacturer_report(
    identifier: str,
    type: str = Query(
        default="company_name",
        description="Type of identifier: company_name, fei_number"
    ),
) -> ManufacturerReportResponse:
    """
    Get a comprehensive manufacturer report.

    Returns company info, locations, product portfolio, adverse events,
    recalls, and regulatory history.
    """
    # Map string type to enum
    type_map = {
        "company_name": IdentifierType.COMPANY_NAME,
        "fei_number": IdentifierType.FEI_NUMBER,
    }

    identifier_type = type_map.get(type.lower())
    if identifier_type is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type '{type}'. Must be one of: {', '.join(type_map.keys())}"
        )

    try:
        generator = get_manufacturer_generator()
        report = await generator.generate(identifier, identifier_type)
        return report
    except Exception as e:
        logger.exception(f"Error generating manufacturer report for {identifier}")
        raise HTTPException(status_code=500, detail=str(e))


def _format_device_report_for_summary(report_data: dict) -> str:
    """Format device report data for LLM consumption."""
    parts = []
    parts.append(f"Product Code: {report_data.get('product_code', 'Unknown')}")
    parts.append(f"Device Name: {report_data.get('product_code_name', 'Unknown')}")

    if clf := report_data.get("classification"):
        parts.append(f"FDA Device Class: {clf.get('device_class', 'Unknown')}")
        if clf.get("medical_specialty"):
            parts.append(f"Medical Specialty: {clf['medical_specialty']}")
        if clf.get("definition"):
            parts.append(f"Definition: {clf['definition'][:200]}...")

    if events := report_data.get("events"):
        counts = events.get("event_type_counts", {})
        parts.append(f"Adverse Events: {events.get('total_count', 0):,} total")
        parts.append(f"  Deaths: {counts.get('death', 0):,}")
        parts.append(f"  Injuries: {counts.get('injury', 0):,}")
        parts.append(f"  Malfunctions: {counts.get('malfunction', 0):,}")

    if recalls := report_data.get("recalls"):
        class_counts = recalls.get("class_counts", {})
        parts.append(f"Recalls: {recalls.get('total_count', 0)} total")
        parts.append(f"  Class I (most serious): {class_counts.get('class_i', 0)}")
        parts.append(f"  Class II: {class_counts.get('class_ii', 0)}")
        parts.append(f"  Class III: {class_counts.get('class_iii', 0)}")

    if clearances := report_data.get("clearances"):
        parts.append(f"510(k) Clearances: {clearances.get('total_count', 0)}")

    if udi := report_data.get("udi"):
        parts.append(f"Registered Devices (UDI): {udi.get('total_count', 0)}")

    if mfrs := report_data.get("top_manufacturers"):
        names = [m.get("name", "") for m in mfrs[:5]]
        parts.append(f"Top Manufacturers: {', '.join(names)}")

    return "\n".join(parts)


def _format_manufacturer_report_for_summary(report_data: dict) -> str:
    """Format manufacturer report data for LLM consumption."""
    parts = []

    if info := report_data.get("company_info"):
        parts.append(f"Company: {info.get('name', 'Unknown')}")
        parts.append(f"Total Devices: {info.get('total_device_count', 0):,}")
        if variations := info.get("name_variations"):
            parts.append(f"Also known as: {', '.join(variations[:3])}")

    if locs := report_data.get("locations"):
        parts.append(f"Facilities: {locs.get('total_count', 0)} locations")
        if countries := locs.get("countries"):
            country_str = ", ".join(f"{k}: {v}" for k, v in list(countries.items())[:5])
            parts.append(f"Countries: {country_str}")

    if portfolio := report_data.get("portfolio"):
        parts.append(f"Product Codes: {portfolio.get('total_product_codes', 0)}")
        if codes := portfolio.get("product_codes"):
            top_codes = [f"{c['code']} ({c['name'][:30]})" for c in codes[:5]]
            parts.append(f"Top Products: {', '.join(top_codes)}")

    if events := report_data.get("events"):
        counts = events.get("event_type_counts", {})
        parts.append(f"Adverse Events: {events.get('total_count', 0):,} total")
        parts.append(f"  Deaths: {counts.get('death', 0):,}")
        parts.append(f"  Injuries: {counts.get('injury', 0):,}")
        parts.append(f"  Malfunctions: {counts.get('malfunction', 0):,}")

    if recalls := report_data.get("recalls"):
        class_counts = recalls.get("class_counts", {})
        parts.append(f"Recalls: {recalls.get('total_count', 0)} total")
        parts.append(f"  Class I: {class_counts.get('class_i', 0)}")
        parts.append(f"  Class II: {class_counts.get('class_ii', 0)}")

    if reg := report_data.get("regulatory"):
        parts.append(f"510(k) Clearances: {reg.get('total_510k', 0)}")
        parts.append(f"PMA Approvals: {reg.get('total_pma', 0)}")

    return "\n".join(parts)


@router.post("/summary", response_model=SummaryResponse)
async def generate_summary(request: SummaryRequest) -> SummaryResponse:
    """Generate an AI summary of a device or manufacturer report."""
    try:
        llm = get_llm()

        if request.entity_type == "device":
            formatted = _format_device_report_for_summary(request.report_data)
            prompt = f"""Summarize this FDA medical device report in 2-3 sentences.
Focus on: safety profile (deaths, injuries, recalls), regulatory status, and clinical significance.
Be factual and concise.

Device Report:
{formatted}

Summary:"""
        else:
            formatted = _format_manufacturer_report_for_summary(request.report_data)
            prompt = f"""Summarize this FDA manufacturer report in 2-3 sentences.
Focus on: company size/scope, product portfolio, and safety record.
Be factual and concise.

Manufacturer Report:
{formatted}

Summary:"""

        response = await llm.ainvoke(prompt)
        summary = _strip_thinking_tags(response.content)
        return SummaryResponse(summary=summary)

    except Exception as e:
        logger.exception("Error generating summary")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/followup", response_model=FollowupResponse)
async def answer_followup(request: FollowupRequest) -> FollowupResponse:
    """Answer a follow-up question about a device or manufacturer."""
    try:
        llm = get_llm()

        prompt = f"""You are an FDA data expert. Answer the following question about a {request.entity_type}.

Context:
- Viewing report for: {request.identifier}
- Report summary: {request.report_summary}

Question: {request.question}

Answer concisely based on your knowledge of FDA regulations and the provided context. If you don't have enough information, say so.

Answer:"""

        response = await llm.ainvoke(prompt)
        answer = _strip_thinking_tags(response.content)
        return FollowupResponse(answer=answer)

    except Exception as e:
        logger.exception("Error answering followup")
        raise HTTPException(status_code=500, detail=str(e))
