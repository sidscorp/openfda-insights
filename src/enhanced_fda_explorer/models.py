"""
Data models for Enhanced FDA Explorer
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
import pandas as pd


class SearchRequest(BaseModel):
    """Search request model"""
    query: str = Field(..., description="Search query")
    query_type: str = Field(default="device", description="Type of query: device, manufacturer")
    endpoints: List[str] = Field(
        default=["event", "recall", "510k", "pma", "classification", "udi"],
        description="FDA endpoints to search"
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum results per endpoint")
    date_range: Optional[Dict[str, Any]] = Field(None, description="Date range filter")
    sort: Optional[str] = Field(None, description="Sort parameter")
    include_ai_analysis: bool = Field(True, description="Include AI analysis in results")
    
    @validator("query_type")
    def validate_query_type(cls, v):
        if v not in ["device", "manufacturer"]:
            raise ValueError("query_type must be 'device' or 'manufacturer'")
        return v
    
    @validator("endpoints")
    def validate_endpoints(cls, v):
        valid_endpoints = ["event", "recall", "510k", "pma", "classification", "udi"]
        for endpoint in v:
            if endpoint not in valid_endpoints:
                raise ValueError(f"Invalid endpoint: {endpoint}")
        return v


class SearchResponse(BaseModel):
    """Search response model"""
    query: str
    query_type: str
    results: Dict[str, Any]  # Will contain DataFrames as dicts
    total_results: int
    response_time: float
    metadata: Dict[str, Any]
    ai_analysis: Optional[Dict[str, Any]] = None
    
    class Config:
        arbitrary_types_allowed = True


class DeviceEvent(BaseModel):
    """Device adverse event model"""
    mdr_report_key: Optional[str] = None
    event_type: Optional[str] = None
    date_received: Optional[datetime] = None
    date_of_event: Optional[datetime] = None
    adverse_event_flag: Optional[str] = None
    product_problem_flag: Optional[str] = None
    
    # Device information
    device_brand_name: Optional[str] = None
    device_generic_name: Optional[str] = None
    device_manufacturer: Optional[str] = None
    device_model_number: Optional[str] = None
    device_product_code: Optional[str] = None
    
    # Patient information
    patient_sequence_number: Optional[str] = None
    patient_outcomes: Optional[List[str]] = None
    
    # Event description
    event_description: Optional[str] = None
    manufacturer_narrative: Optional[str] = None
    
    # Metadata
    source: str = "EVENT"
    retrieved_at: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "DeviceEvent":
        """Create DeviceEvent from API response"""
        # Extract device information
        device_info = data.get("device", [{}])[0] if data.get("device") else {}
        
        # Extract patient information
        patient_info = data.get("patient", [{}])[0] if data.get("patient") else {}
        patient_outcomes = []
        if patient_info.get("sequence_number_outcome"):
            patient_outcomes = patient_info["sequence_number_outcome"]
        
        return cls(
            mdr_report_key=data.get("mdr_report_key"),
            event_type=data.get("event_type"),
            date_received=cls._parse_date(data.get("date_received")),
            date_of_event=cls._parse_date(data.get("date_of_event")),
            adverse_event_flag=data.get("adverse_event_flag"),
            product_problem_flag=data.get("product_problem_flag"),
            device_brand_name=device_info.get("brand_name"),
            device_generic_name=device_info.get("generic_name"),
            device_manufacturer=device_info.get("manufacturer_d_name"),
            device_model_number=device_info.get("model_number"),
            device_product_code=device_info.get("device_report_product_code"),
            patient_sequence_number=patient_info.get("sequence_number"),
            patient_outcomes=patient_outcomes,
            event_description=data.get("event_description"),
            manufacturer_narrative=data.get("manufacturer_narrative"),
            retrieved_at=datetime.now()
        )
    
    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except (ValueError, TypeError):
            return None


class DeviceClassification(BaseModel):
    """Device classification model"""
    device_name: Optional[str] = None
    medical_specialty_description: Optional[str] = None
    device_class: Optional[str] = None
    regulation_number: Optional[str] = None
    product_code: Optional[str] = None
    definition: Optional[str] = None
    intended_use: Optional[str] = None
    
    # Metadata
    source: str = "CLASSIFICATION"
    retrieved_at: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "DeviceClassification":
        """Create DeviceClassification from API response"""
        return cls(
            device_name=data.get("device_name"),
            medical_specialty_description=data.get("medical_specialty_description"),
            device_class=data.get("device_class"),
            regulation_number=data.get("regulation_number"),
            product_code=data.get("product_code"),
            definition=data.get("definition"),
            intended_use=data.get("intended_use"),
            retrieved_at=datetime.now()
        )


class DeviceRecall(BaseModel):
    """Device recall model"""
    recall_number: Optional[str] = None
    product_description: Optional[str] = None
    recalling_firm: Optional[str] = None
    recall_initiation_date: Optional[datetime] = None
    event_date_initiated: Optional[datetime] = None
    recall_status: Optional[str] = None
    classification: Optional[str] = None
    reason_for_recall: Optional[str] = None
    
    # Metadata
    source: str = "RECALL"
    retrieved_at: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "DeviceRecall":
        """Create DeviceRecall from API response"""
        return cls(
            recall_number=data.get("recall_number"),
            product_description=data.get("product_description"),
            recalling_firm=data.get("recalling_firm"),
            recall_initiation_date=cls._parse_date(data.get("recall_initiation_date")),
            event_date_initiated=cls._parse_date(data.get("event_date_initiated")),
            recall_status=data.get("status"),
            classification=data.get("classification"),
            reason_for_recall=data.get("reason_for_recall"),
            retrieved_at=datetime.now()
        )
    
    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None


class Device510K(BaseModel):
    """510(k) clearance model"""
    k_number: Optional[str] = None
    device_name: Optional[str] = None
    applicant: Optional[str] = None
    decision_date: Optional[datetime] = None
    date_received: Optional[datetime] = None
    decision: Optional[str] = None
    product_code: Optional[str] = None
    statement_or_summary: Optional[str] = None
    
    # Metadata
    source: str = "510K"
    retrieved_at: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Device510K":
        """Create Device510K from API response"""
        return cls(
            k_number=data.get("k_number"),
            device_name=data.get("device_name"),
            applicant=data.get("applicant"),
            decision_date=cls._parse_date(data.get("decision_date")),
            date_received=cls._parse_date(data.get("date_received")),
            decision=data.get("decision"),
            product_code=data.get("product_code"),
            statement_or_summary=data.get("statement_or_summary"),
            retrieved_at=datetime.now()
        )
    
    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None


class DevicePMA(BaseModel):
    """PMA approval model"""
    pma_number: Optional[str] = None
    supplement_number: Optional[str] = None
    trade_name: Optional[str] = None
    generic_name: Optional[str] = None
    applicant: Optional[str] = None
    decision_date: Optional[datetime] = None
    date_received: Optional[datetime] = None
    decision: Optional[str] = None
    product_code: Optional[str] = None
    
    # Metadata
    source: str = "PMA"
    retrieved_at: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "DevicePMA":
        """Create DevicePMA from API response"""
        return cls(
            pma_number=data.get("pma_number"),
            supplement_number=data.get("supplement_number"),
            trade_name=data.get("trade_name"),
            generic_name=data.get("generic_name"),
            applicant=data.get("applicant"),
            decision_date=cls._parse_date(data.get("decision_date")),
            date_received=cls._parse_date(data.get("date_received")),
            decision=data.get("decision"),
            product_code=data.get("product_code"),
            retrieved_at=datetime.now()
        )
    
    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None


class DeviceUDI(BaseModel):
    """UDI database model"""
    di: Optional[str] = None  # Device Identifier
    brand_name: Optional[str] = None
    device_description: Optional[str] = None
    company_name: Optional[str] = None
    device_count: Optional[int] = None
    commercial_distribution_status: Optional[str] = None
    date_commercial_distribution: Optional[datetime] = None
    
    # Metadata
    source: str = "UDI"
    retrieved_at: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "DeviceUDI":
        """Create DeviceUDI from API response"""
        return cls(
            di=data.get("di"),
            brand_name=data.get("brand_name"),
            device_description=data.get("device_description"),
            company_name=data.get("company_name"),
            device_count=data.get("device_count"),
            commercial_distribution_status=data.get("commercial_distribution_status"),
            date_commercial_distribution=cls._parse_date(data.get("date_commercial_distribution")),
            retrieved_at=datetime.now()
        )
    
    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None


class AIAnalysisRequest(BaseModel):
    """AI analysis request model"""
    data: Dict[str, Any]  # Data to analyze
    analysis_type: str  # Type of analysis requested
    query_context: Optional[str] = None
    custom_prompt: Optional[str] = None
    
    @validator("analysis_type")
    def validate_analysis_type(cls, v):
        valid_types = ["summary", "risk_assessment", "regulatory_timeline", "trend_analysis"]
        if v not in valid_types:
            raise ValueError(f"Invalid analysis type: {v}")
        return v


class AIAnalysisResponse(BaseModel):
    """AI analysis response model"""
    analysis_type: str
    summary: str
    key_findings: List[str]
    risk_score: Optional[float] = None
    recommendations: Optional[List[str]] = None
    confidence_score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskAssessment(BaseModel):
    """Risk assessment model"""
    overall_risk_score: float = Field(..., ge=0.0, le=10.0)
    risk_factors: List[str]
    severity_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    recommendations: List[str]
    
    @validator("severity_level")
    def validate_severity_level(cls, v):
        if v not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            raise ValueError("Invalid severity level")
        return v


class RegulatoryTimeline(BaseModel):
    """Regulatory timeline model"""
    events: List[Dict[str, Any]]
    key_milestones: List[str]
    regulatory_pathway: Optional[str] = None
    approval_status: Optional[str] = None
    timeline_analysis: Optional[str] = None