"""
Citation models for FDA data tracking

Ensures all findings are backed by specific FDA records.
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from pydantic import BaseModel, Field


class FDACitation(BaseModel):
    """Citation for a specific FDA record"""
    record_id: str = Field(..., description="FDA record identifier (e.g., MDR report number, recall number)")
    record_type: str = Field(..., description="Type of FDA record (event, recall, 510k, etc.)")
    date: str = Field(..., description="Date of the record")
    source_field: Optional[str] = Field(None, description="Specific field referenced")
    excerpt: Optional[str] = Field(None, description="Relevant excerpt from the record")
    
    def to_string(self) -> str:
        """Convert citation to readable string"""
        return f"{self.record_type} {self.record_id} ({self.date})"


class CitedFinding(BaseModel):
    """A finding with supporting FDA citations"""
    finding: str = Field(..., description="The finding or claim")
    citations: List[FDACitation] = Field(..., description="Supporting FDA records")
    confidence: str = Field(default="high", description="Confidence level based on data quality")
    
    def validate_citations(self) -> bool:
        """Ensure finding has at least one citation"""
        return len(self.citations) > 0


class DataQualityMetrics(BaseModel):
    """Metrics about data quality and coverage"""
    total_records_searched: int = Field(0, description="Total FDA records searched")
    total_records_found: int = Field(0, description="Total relevant records found")
    databases_searched: List[str] = Field(default_factory=list, description="FDA databases queried")
    search_strategies_used: List[str] = Field(default_factory=list, description="Search strategies attempted")
    data_completeness: str = Field("unknown", description="Assessment of data completeness")
    
    def has_sufficient_data(self) -> bool:
        """Check if enough data was found for analysis"""
        return self.total_records_found > 0


@dataclass
class CitationTracker:
    """Tracks citations throughout the analysis process"""
    
    def __init__(self):
        self.citations: Dict[str, List[FDACitation]] = {}
        self.findings: List[CitedFinding] = []
        self.data_quality = DataQualityMetrics()
    
    def add_event_citation(self, event: Dict[str, Any]) -> FDACitation:
        """Create citation from FDA event record"""
        return FDACitation(
            record_id=event.get("mdr_report_key", event.get("report_number", "unknown")),
            record_type="adverse_event",
            date=event.get("date_received", event.get("date_of_event", "")),
            source_field="event",
            excerpt=event.get("event_type", "")
        )
    
    def add_recall_citation(self, recall: Dict[str, Any]) -> FDACitation:
        """Create citation from FDA recall record"""
        return FDACitation(
            record_id=recall.get("recall_number", "unknown"),
            record_type="recall",
            date=recall.get("event_date_initiated", recall.get("center_classification_date", "")),
            source_field="recall",
            excerpt=f"Class {recall.get('classification', 'Unknown')} - {recall.get('reason_for_recall', '')[:100]}"
        )
    
    def add_clearance_citation(self, clearance: Dict[str, Any]) -> FDACitation:
        """Create citation from FDA 510(k) clearance"""
        return FDACitation(
            record_id=clearance.get("k_number", "unknown"),
            record_type="510k_clearance",
            date=clearance.get("date_received", clearance.get("decision_date", "")),
            source_field="clearance",
            excerpt=clearance.get("device_name", "")
        )
    
    def add_finding(self, finding: str, citations: List[FDACitation], 
                   confidence: str = "high") -> CitedFinding:
        """Add a finding with its supporting citations"""
        cited_finding = CitedFinding(
            finding=finding,
            citations=citations,
            confidence=confidence
        )
        
        if cited_finding.validate_citations():
            self.findings.append(cited_finding)
            return cited_finding
        else:
            raise ValueError(f"Finding must have citations: {finding}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of citations and findings"""
        return {
            "total_findings": len(self.findings),
            "total_citations": sum(len(f.citations) for f in self.findings),
            "data_quality": self.data_quality.dict(),
            "findings_summary": [
                {
                    "finding": f.finding,
                    "citation_count": len(f.citations),
                    "citations": [c.to_string() for c in f.citations[:3]]  # First 3
                }
                for f in self.findings
            ]
        }


def create_agent_citations(agent_result: Dict[str, Any]) -> List[FDACitation]:
    """Extract citations from agent result data"""
    citations = []
    
    # Extract from raw event data
    if "raw_events" in agent_result.get("raw_data", {}):
        for event in agent_result["raw_data"]["raw_events"][:10]:  # First 10
            citations.append(FDACitation(
                record_id=event.get("mdr_report_key", event.get("report_number", "")),
                record_type="adverse_event",
                date=event.get("date_received", ""),
                excerpt=f"{event.get('event_type', '')} - {event.get('device', [{}])[0].get('generic_name', '')}"
            ))
    
    # Extract from raw recall data
    if "raw_recalls" in agent_result.get("raw_data", {}):
        for recall in agent_result["raw_data"]["raw_recalls"][:10]:  # First 10
            citations.append(FDACitation(
                record_id=recall.get("recall_number", ""),
                record_type="recall",
                date=recall.get("event_date_initiated", ""),
                excerpt=f"Class {recall.get('classification', '')} - {recall.get('reason_for_recall', '')[:50]}"
            ))
    
    return citations