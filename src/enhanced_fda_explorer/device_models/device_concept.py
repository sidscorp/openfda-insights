"""
Device concept models for FDA Device Brain.
Maps GUDID fields to structured Pydantic models with validation.
"""
from typing import Optional, List, Dict, Any
from datetime import date
from enum import Enum
from pydantic import BaseModel, Field


class DeviceIdType(str, Enum):
    """Types of device identifiers in GUDID."""
    PRIMARY = "Primary"
    SECONDARY = "Secondary"
    DIRECT = "Direct"
    UNIT_OF_USE = "Unit of Use"
    PACKAGE = "Package"
    PREVIOUS = "Previous"  # Additional type found in data
    DIRECT_MARKING = "Direct Marking"  # Additional type found in data


class DeviceStatus(str, Enum):
    """Device commercial distribution status."""
    IN_COMMERCIAL_DISTRIBUTION = "In Commercial Distribution"
    NOT_IN_COMMERCIAL_DISTRIBUTION = "Not in Commercial Distribution"
    TRANSITIONAL = "Transitional"


class GMDNTerm(BaseModel):
    """Global Medical Device Nomenclature (GMDN) term."""
    gmdn_code: str = Field(alias="gmdnCode")
    gmdn_pt_name: str = Field(alias="gmdnPTName")
    gmdn_pt_definition: Optional[str] = Field(None, alias="gmdnPTDefinition")
    implantable: bool = False
    gmdn_code_status: Optional[str] = Field(None, alias="gmdnCodeStatus")


class FDAProductCode(BaseModel):
    """FDA product code classification."""
    product_code: str = Field(alias="productCode")
    product_code_name: str = Field(alias="productCodeName")


class DeviceIdentifier(BaseModel):
    """Device identifier (DI) information."""
    device_id: str = Field(alias="deviceId")
    device_id_type: DeviceIdType = Field(alias="deviceIdType")
    device_id_issuing_agency: str = Field(alias="deviceIdIssuingAgency")
    pkg_quantity: Optional[int] = Field(None, alias="pkgQuantity")
    pkg_type: Optional[str] = Field(None, alias="pkgType")


class DeviceConcept(BaseModel):
    """
    Core device concept model representing a medical device from GUDID.
    Links human-readable terms to FDA regulatory identifiers.
    """
    # Primary identifiers
    public_device_record_key: str = Field(alias="publicDeviceRecordKey")
    primary_di: Optional[str] = None  # Extracted from identifiers

    # Device naming and identification
    brand_name: Optional[str] = Field(None, alias="brandName")
    version_model_number: Optional[str] = Field(None, alias="versionModelNumber")
    catalog_number: Optional[str] = Field(None, alias="catalogNumber")
    device_description: Optional[str] = Field(None, alias="deviceDescription")

    # Company information
    company_name: Optional[str] = Field(None, alias="companyName")
    duns_number: Optional[str] = Field(None, alias="dunsNumber")

    # Classification
    gmdn_terms: List[GMDNTerm] = Field(default_factory=list, alias="gmdnTerms")
    product_codes: List[FDAProductCode] = Field(default_factory=list, alias="productCodes")

    # Device characteristics
    device_count: Optional[int] = Field(None, alias="deviceCount")
    is_combination_product: bool = Field(False, alias="deviceCombinationProduct")
    is_kit: bool = Field(False, alias="deviceKit")
    is_single_use: bool = Field(False, alias="singleUse")
    is_sterile: bool = Field(False, alias="deviceSterile")
    is_rx: bool = Field(False, alias="rx")
    is_otc: bool = Field(False, alias="otc")

    # Status and dates
    device_status: DeviceStatus = Field(alias="deviceCommDistributionStatus")
    device_publish_date: Optional[date] = Field(None, alias="devicePublishDate")

    # All device identifiers
    identifiers: List[DeviceIdentifier] = Field(default_factory=list)

    class Config:
        populate_by_name = True

    def get_primary_di(self) -> Optional[str]:
        """Extract primary DI from identifiers list."""
        for identifier in self.identifiers:
            if identifier.device_id_type == DeviceIdType.PRIMARY:
                return identifier.device_id
        return None

    def get_product_codes(self) -> List[str]:
        """Get list of FDA product codes."""
        return [pc.product_code for pc in self.product_codes]

    def get_gmdn_codes(self) -> List[str]:
        """Get list of GMDN codes."""
        return [gmdn.gmdn_code for gmdn in self.gmdn_terms]


class MatchType(str, Enum):
    """Type of match found during device resolution."""
    EXACT_BRAND = "exact_brand"
    EXACT_COMPANY = "exact_company"
    EXACT_PRODUCT_CODE = "exact_product_code"
    EXACT_GMDN = "exact_gmdn"
    EXACT_DI = "exact_di"
    FUZZY_BRAND = "fuzzy_brand"
    FUZZY_DESCRIPTION = "fuzzy_description"
    FUZZY_GMDN_NAME = "fuzzy_gmdn_name"
    FUZZY_COMPANY = "fuzzy_company"
    FUZZY_PRODUCT_CODE_NAME = "fuzzy_product_code_name"


class DeviceMatch(BaseModel):
    """
    Represents a device match result with context about how it was matched.
    """
    device: DeviceConcept
    match_type: MatchType
    match_field: str  # Which field matched (e.g., "brandName", "deviceDescription")
    match_value: str  # The actual value that matched
    match_query: str  # The query term that led to this match
    confidence: float = Field(ge=0.0, le=1.0)  # 0.0 to 1.0 confidence score

    class Config:
        populate_by_name = True


class ResolverResponse(BaseModel):
    """
    Response from the device resolver containing all matches and metadata.
    """
    query: str
    total_matches: int
    matches: List[DeviceMatch]
    search_fields: List[str]  # Which fields were searched
    execution_time_ms: Optional[float] = None

    def get_unique_product_codes(self) -> List[str]:
        """Get all unique product codes from matches."""
        codes = set()
        for match in self.matches:
            codes.update(match.device.get_product_codes())
        return sorted(list(codes))

    def get_unique_companies(self) -> List[str]:
        """Get all unique company names from matches."""
        companies = set()
        for match in self.matches:
            if match.device.company_name:
                companies.add(match.device.company_name)
        return sorted(list(companies))

    def filter_by_confidence(self, min_confidence: float = 0.8) -> List[DeviceMatch]:
        """Filter matches by minimum confidence score."""
        return [m for m in self.matches if m.confidence >= min_confidence]
