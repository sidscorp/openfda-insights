"""
FDA Lookup module - Simple report-focused device and manufacturer lookup.
"""
from .input_detector import InputDetector, InputType
from .models import (
    IdentifyRequest,
    IdentifyResponse,
    LookupCandidate,
    DeviceReportResponse,
    ManufacturerReportResponse,
)
from .device_report import DeviceReportGenerator
from .manufacturer_report import ManufacturerReportGenerator
from .router import router as lookup_router

__all__ = [
    "InputDetector",
    "InputType",
    "IdentifyRequest",
    "IdentifyResponse",
    "LookupCandidate",
    "DeviceReportResponse",
    "ManufacturerReportResponse",
    "DeviceReportGenerator",
    "ManufacturerReportGenerator",
    "lookup_router",
]
