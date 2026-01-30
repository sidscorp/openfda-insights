"""
Structured response models for FDA Agent.

These models provide typed, structured data that can be:
1. Serialized to JSON for API responses
2. Used by frontends for drill-down navigation
3. Processed programmatically for analysis
"""
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ProductCodeInfo(BaseModel):
    code: str = Field(description="Three-letter FDA product code")
    name: str = Field(description="Product code name")
    device_count: int = Field(description="Number of devices with this code")
    device_class: Optional[str] = Field(default=None, description="FDA device class (1, 2, 3)")


class ManufacturerInfo(BaseModel):
    name: str = Field(description="Company/manufacturer name")
    device_count: int = Field(description="Number of devices from this manufacturer")
    variations: list[str] = Field(default_factory=list, description="Name variations found")
    top_product_codes: list["ProductCodeInfo"] = Field(default_factory=list, description="Top product codes for this manufacturer")


class DeviceInfo(BaseModel):
    brand_name: str
    company_name: str
    device_description: Optional[str] = None
    product_codes: list[str] = Field(default_factory=list)
    primary_di: Optional[str] = None
    confidence: float = Field(description="Match confidence 0.0-1.0")
    match_field: Optional[str] = Field(default=None, description="Field that matched the query")


class DeviceListRecord(BaseModel):
    brand_name: str = Field(description="Device brand name")
    company_name: str = Field(description="Manufacturer/company name")
    version_model_number: Optional[str] = Field(default=None, description="Model or version number")
    primary_di: Optional[str] = Field(default=None, description="Primary Device Identifier (UDI-DI)")
    device_description: Optional[str] = Field(default=None, description="Device description")
    product_codes: list[str] = Field(default_factory=list, description="FDA product codes")


class DeviceListResult(BaseModel):
    query: str = Field(description="Original query or product code")
    product_code: Optional[str] = Field(default=None, description="Specific product code searched")
    product_code_name: Optional[str] = Field(default=None, description="Name of the product code")
    device_class: Optional[str] = Field(default=None, description="FDA device class (1, 2, 3)")
    total_found: int = Field(description="Total devices matching the query")
    records: list[DeviceListRecord] = Field(default_factory=list, description="Device records")


class ResolvedEntities(BaseModel):
    """Entities resolved from user's natural language query."""
    query: str = Field(description="Original query")
    product_codes: list[ProductCodeInfo] = Field(default_factory=list)
    manufacturers: list[ManufacturerInfo] = Field(default_factory=list)
    devices: list[DeviceInfo] = Field(default_factory=list)
    total_devices_matched: int = 0
    resolution_time_ms: float = 0


class RecallRecord(BaseModel):
    recall_number: str
    event_id: Optional[str] = None
    recalling_firm: str
    product_description: str
    reason_for_recall: str
    classification: str = Field(description="Class I, II, or III")
    status: str
    recall_initiation_date: str
    voluntary_mandated: Optional[str] = None
    distribution_pattern: Optional[str] = None


class AggregationCount(BaseModel):
    term: str
    count: int


class RecallSearchResult(BaseModel):
    query: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    total_found: int
    records: list[RecallRecord] = Field(default_factory=list)
    aggregations: dict[str, list[AggregationCount]] = Field(
        default_factory=dict,
        description="Server-side aggregations from full dataset"
    )
    class_counts: dict[str, int] = Field(default_factory=dict, description="Deprecated: use aggregations")
    status_counts: dict[str, int] = Field(default_factory=dict, description="Deprecated: use aggregations")
    firm_counts: dict[str, int] = Field(default_factory=dict, description="Deprecated: use aggregations")


class AdverseEventRecord(BaseModel):
    mdr_report_key: Optional[str] = None
    event_type: str = Field(description="Malfunction, Injury, Death, Other")
    date_received: str
    brand_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    product_code: Optional[str] = None
    event_description: Optional[str] = None
    patient_outcome: Optional[list[str]] = None


class EventSearchResult(BaseModel):
    query: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    total_found: int
    records: list[AdverseEventRecord] = Field(default_factory=list)
    aggregations: dict[str, list[AggregationCount]] = Field(
        default_factory=dict,
        description="Server-side aggregations from full dataset"
    )
    event_type_counts: dict[str, int] = Field(default_factory=dict, description="Deprecated: use aggregations")
    manufacturer_counts: dict[str, int] = Field(default_factory=dict, description="Deprecated: use aggregations")


class Clearance510kRecord(BaseModel):
    k_number: str
    device_name: str
    applicant: str
    product_code: str
    decision_date: str
    decision_description: str
    statement_or_summary: Optional[str] = None
    clearance_type: Optional[str] = None


class Clearance510kSearchResult(BaseModel):
    query: str
    total_found: int
    records: list[Clearance510kRecord] = Field(default_factory=list)
    aggregations: dict[str, list[AggregationCount]] = Field(
        default_factory=dict,
        description="Server-side aggregations from full dataset"
    )
    applicant_counts: dict[str, int] = Field(default_factory=dict, description="Deprecated: use aggregations")
    product_code_counts: dict[str, int] = Field(default_factory=dict, description="Deprecated: use aggregations")


class ClassificationRecord(BaseModel):
    product_code: str
    device_name: str
    device_class: str
    regulation_number: Optional[str] = None
    submission_type: Optional[str] = None
    definition: Optional[str] = None
    medical_specialty: Optional[str] = None


class ClassificationSearchResult(BaseModel):
    query: str
    total_found: int
    records: list[ClassificationRecord] = Field(default_factory=list)
    aggregations: dict[str, list[AggregationCount]] = Field(
        default_factory=dict,
        description="Server-side aggregations from full dataset"
    )
    class_counts: dict[str, int] = Field(default_factory=dict, description="Deprecated: use aggregations")


class PMARecord(BaseModel):
    pma_number: str
    trade_name: Optional[str] = None
    generic_name: Optional[str] = None
    applicant: str
    decision_date: str
    decision_code: Optional[str] = None
    advisory_committee: Optional[str] = None
    supplement_number: Optional[str] = None
    product_code: Optional[str] = None


class PMASearchResult(BaseModel):
    query: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    total_found: int
    records: list[PMARecord] = Field(default_factory=list)
    aggregations: dict[str, list[AggregationCount]] = Field(
        default_factory=dict,
        description="Server-side aggregations from full dataset"
    )
    decision_counts: dict[str, int] = Field(default_factory=dict, description="Deprecated: use aggregations")


class UDIRecord(BaseModel):
    brand_name: Optional[str] = None
    company_name: Optional[str] = None
    version_model_number: Optional[str] = None
    primary_di: Optional[str] = None
    mri_safety: Optional[str] = None
    device_description: Optional[str] = None
    is_sterile: bool = False
    is_single_use: Optional[bool] = None
    device_count_in_base_package: Optional[int] = None


class UDISearchResult(BaseModel):
    query: str
    total_found: int
    records: list[UDIRecord] = Field(default_factory=list)
    aggregations: dict[str, list[AggregationCount]] = Field(
        default_factory=dict,
        description="Server-side aggregations from full dataset"
    )
    company_counts: dict[str, int] = Field(default_factory=dict, description="Deprecated: use aggregations")


class RegistrationRecord(BaseModel):
    registration_number: Optional[str] = None
    name: str
    city: Optional[str] = None
    state_code: Optional[str] = None
    country_code: str
    address_line_1: Optional[str] = None
    postal_code: Optional[str] = None
    proprietary_names: list[str] = Field(default_factory=list)


class RegistrationSearchResult(BaseModel):
    query: str
    total_found: int
    records: list[RegistrationRecord] = Field(default_factory=list)
    aggregations: dict[str, list[AggregationCount]] = Field(
        default_factory=dict,
        description="Server-side aggregations from full dataset"
    )
    country_counts: dict[str, int] = Field(default_factory=dict, description="Deprecated: use aggregations")
    state_counts: dict[str, int] = Field(default_factory=dict, description="Deprecated: use aggregations")


class LocationContext(BaseModel):
    """Context from location resolver for use by other tools."""
    location_type: str = Field(description="Type: 'country', 'region', or 'state'")
    location_name: str = Field(description="Human-readable name (e.g., 'China', 'Asia', 'California')")
    country_codes: list[str] = Field(default_factory=list, description="ISO country codes")
    state_code: Optional[str] = Field(default=None, description="US state code if applicable")
    total_establishments: int = Field(default=0, description="Total registered establishments")
    top_manufacturers: list[str] = Field(default_factory=list, description="Top manufacturer names")
    device_types_filter: Optional[str] = Field(default=None, description="Device type filter if applied")


class ToolExecution(BaseModel):
    tool_name: str
    arguments: dict
    result_type: str = Field(description="Type of result returned")
    execution_time_ms: float = 0
    success: bool = True
    error_message: Optional[str] = None


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: Optional[float] = None


class AgentResponse(BaseModel):
    """Complete structured response from FDA Agent."""
    summary: str = Field(description="Human-readable summary of findings")

    resolved_entities: Optional[ResolvedEntities] = Field(
        default=None,
        description="Entities resolved from the query (devices, manufacturers, product codes)"
    )

    recall_results: Optional[RecallSearchResult] = None
    event_results: Optional[EventSearchResult] = None
    clearance_results: Optional[Clearance510kSearchResult] = None
    classification_results: Optional[ClassificationSearchResult] = None

    tools_executed: list[ToolExecution] = Field(default_factory=list)

    model: str = ""
    token_usage: TokenUsage = Field(default_factory=TokenUsage)

    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def has_resolution(self) -> bool:
        return self.resolved_entities is not None and len(self.resolved_entities.product_codes) > 0

    @property
    def has_search_results(self) -> bool:
        return any([
            self.recall_results and self.recall_results.total_found > 0,
            self.event_results and self.event_results.total_found > 0,
            self.clearance_results and self.clearance_results.total_found > 0,
            self.classification_results and self.classification_results.total_found > 0,
        ])
