"""
Pydantic models for the FDA Lookup API.
"""
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class EntityType(str, Enum):
    """Types of entities that can be looked up."""
    DEVICE = "device"
    MANUFACTURER = "manufacturer"


class IdentifierType(str, Enum):
    """Types of identifiers."""
    PRODUCT_CODE = "product_code"
    PRIMARY_DI = "primary_di"
    FEI_NUMBER = "fei_number"
    K_NUMBER = "k_number"
    PMA_NUMBER = "pma_number"
    COMPANY_NAME = "company_name"
    DEVICE_NAME = "device_name"


class IdentifyRequest(BaseModel):
    """Request to identify an input string."""
    input: str = Field(..., description="User input to identify")


class LookupCandidate(BaseModel):
    """A candidate entity that matches the input."""
    entity_type: EntityType
    identifier: str
    identifier_type: IdentifierType
    display_name: str
    description: Optional[str] = None
    device_count: Optional[int] = None
    device_class: Optional[str] = None  # "1", "2", or "3" for FDA device classification


class IdentifyResponse(BaseModel):
    """Response from input identification."""
    input: str
    needs_disambiguation: bool
    entity_type: Optional[EntityType] = None
    identifier: Optional[str] = None
    identifier_type: Optional[IdentifierType] = None
    candidates: list[LookupCandidate] = Field(default_factory=list)


# Report sections

class ClassificationSection(BaseModel):
    """Device classification information."""
    device_class: Optional[str] = None
    device_name: Optional[str] = None
    regulation_number: Optional[str] = None
    submission_type: Optional[str] = None
    definition: Optional[str] = None
    medical_specialty: Optional[str] = None


class EventTypeCounts(BaseModel):
    """Breakdown of adverse events by type."""
    death: int = 0
    injury: int = 0
    malfunction: int = 0
    other: int = 0


class EventsSection(BaseModel):
    """Adverse events summary."""
    total_count: int = 0
    event_type_counts: EventTypeCounts = Field(default_factory=EventTypeCounts)
    top_manufacturers: list[dict] = Field(default_factory=list)
    recent_events: list[dict] = Field(default_factory=list)


class RecallClassCounts(BaseModel):
    """Breakdown of recalls by class."""
    class_i: int = 0
    class_ii: int = 0
    class_iii: int = 0


class RecallsSection(BaseModel):
    """Recalls summary."""
    total_count: int = 0
    class_counts: RecallClassCounts = Field(default_factory=RecallClassCounts)
    status_counts: dict[str, int] = Field(default_factory=dict)
    recent_recalls: list[dict] = Field(default_factory=list)


class ClearancesSection(BaseModel):
    """510(k) clearances summary."""
    total_count: int = 0
    top_applicants: list[dict] = Field(default_factory=list)
    recent_clearances: list[dict] = Field(default_factory=list)


class MRISafetyCounts(BaseModel):
    """MRI safety breakdown."""
    mr_safe: int = 0
    mr_conditional: int = 0
    mr_unsafe: int = 0
    not_specified: int = 0


class UDISection(BaseModel):
    """UDI database summary."""
    total_count: int = 0
    mri_safety: MRISafetyCounts = Field(default_factory=MRISafetyCounts)
    sterile_count: int = 0
    single_use_count: int = 0
    sample_devices: list[dict] = Field(default_factory=list)


class ManufacturerSummary(BaseModel):
    """Summary of a manufacturer for device reports."""
    name: str
    device_count: int


class DeviceReportResponse(BaseModel):
    """Complete device report response."""
    identifier: str
    identifier_type: IdentifierType
    product_code: Optional[str] = None
    product_code_name: Optional[str] = None

    classification: Optional[ClassificationSection] = None
    events: Optional[EventsSection] = None
    recalls: Optional[RecallsSection] = None
    clearances: Optional[ClearancesSection] = None
    udi: Optional[UDISection] = None
    top_manufacturers: list[ManufacturerSummary] = Field(default_factory=list)


# Manufacturer report sections

class CompanyInfoSection(BaseModel):
    """Company information."""
    name: str
    name_variations: list[str] = Field(default_factory=list)
    total_device_count: int = 0


class LocationRecord(BaseModel):
    """A single establishment location."""
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: str
    address: Optional[str] = None


class LocationsSection(BaseModel):
    """Manufacturer locations summary."""
    total_count: int = 0
    countries: dict[str, int] = Field(default_factory=dict)
    us_states: dict[str, int] = Field(default_factory=dict)
    locations: list[LocationRecord] = Field(default_factory=list)


class ProductCodeSummary(BaseModel):
    """Summary of a product code."""
    code: str
    name: str
    device_count: int


class PortfolioSection(BaseModel):
    """Product portfolio summary."""
    total_product_codes: int = 0
    product_codes: list[ProductCodeSummary] = Field(default_factory=list)


class RegulatorySection(BaseModel):
    """Regulatory history summary."""
    total_510k: int = 0
    total_pma: int = 0
    recent_510k: list[dict] = Field(default_factory=list)
    recent_pma: list[dict] = Field(default_factory=list)


class ManufacturerReportResponse(BaseModel):
    """Complete manufacturer report response."""
    identifier: str
    identifier_type: IdentifierType

    company_info: Optional[CompanyInfoSection] = None
    locations: Optional[LocationsSection] = None
    portfolio: Optional[PortfolioSection] = None
    events: Optional[EventsSection] = None
    recalls: Optional[RecallsSection] = None
    regulatory: Optional[RegulatorySection] = None
