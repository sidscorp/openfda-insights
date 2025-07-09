"""
Mock FDA API response fixtures for testing
"""

from datetime import datetime
from typing import Dict, Any, List

# Mock FDA API responses for different endpoints
MOCK_FDA_RESPONSES = {
    "event": {
        "meta": {
            "disclaimer": "Test disclaimer",
            "terms": "Test terms",
            "license": "Test license",
            "last_updated": "2023-12-01",
            "results": {
                "skip": 0,
                "limit": 100,
                "total": 1247
            }
        },
        "results": [
            {
                "mdr_report_key": "12345678",
                "event_type": "Malfunction",
                "date_received": "20231201",
                "date_of_event": "20231125",
                "adverse_event_flag": "Y",
                "product_problem_flag": "Y",
                "device": [{
                    "brand_name": "Test Pacemaker Model X",
                    "generic_name": "Cardiac Pacemaker",
                    "manufacturer_d_name": "Test Medical Devices Inc",
                    "model_number": "PM-X200",
                    "device_report_product_code": "DXX"
                }],
                "patient": [{
                    "sequence_number": "1",
                    "sequence_number_outcome": ["Required Intervention"]
                }],
                "event_description": "Device battery unexpectedly depleted causing loss of pacing function",
                "manufacturer_narrative": "Investigation revealed potential manufacturing defect in battery assembly"
            },
            {
                "mdr_report_key": "12345679",
                "event_type": "Injury",
                "date_received": "20231130",
                "date_of_event": "20231120",
                "adverse_event_flag": "Y",
                "product_problem_flag": "Y",
                "device": [{
                    "brand_name": "Test Defibrillator Pro",
                    "generic_name": "Automated External Defibrillator",
                    "manufacturer_d_name": "Test Cardiac Solutions Corp",
                    "model_number": "AED-Pro500",
                    "device_report_product_code": "DXY"
                }],
                "patient": [{
                    "sequence_number": "1",
                    "sequence_number_outcome": ["Hospitalization"]
                }],
                "event_description": "Device failed to charge properly during emergency use",
                "manufacturer_narrative": "Analysis showed software timing issue affecting charge cycle"
            }
        ]
    },
    
    "recall": {
        "meta": {
            "disclaimer": "Test disclaimer",
            "terms": "Test terms",
            "license": "Test license",
            "last_updated": "2023-12-01",
            "results": {
                "skip": 0,
                "limit": 100,
                "total": 423
            }
        },
        "results": [
            {
                "recall_number": "Z-1234-2023",
                "product_description": "Test Insulin Pump Model A with integrated glucose monitor",
                "recalling_firm": "Test Diabetes Tech Inc",
                "recall_initiation_date": "2023-11-15",
                "event_date_initiated": "2023-11-15",
                "status": "Ongoing",
                "classification": "Class II",
                "reason_for_recall": "Software defect could cause incorrect insulin dosing calculations under specific conditions"
            },
            {
                "recall_number": "Z-1235-2023",
                "product_description": "Test Blood Pressure Monitor Series B",
                "recalling_firm": "Test Monitoring Solutions LLC",
                "recall_initiation_date": "2023-10-20",
                "event_date_initiated": "2023-10-20",
                "status": "Completed",
                "classification": "Class I",
                "reason_for_recall": "Cuff inflation mechanism may fail causing inaccurate readings"
            }
        ]
    },
    
    "510k": {
        "meta": {
            "disclaimer": "Test disclaimer",
            "terms": "Test terms",
            "license": "Test license",
            "last_updated": "2023-12-01",
            "results": {
                "skip": 0,
                "limit": 100,
                "total": 876
            }
        },
        "results": [
            {
                "k_number": "K230001",
                "device_name": "Test Cardiac Stent System",
                "applicant": "Test Vascular Devices Inc",
                "decision_date": "2023-11-30",
                "date_received": "2023-08-15",
                "decision": "Substantially Equivalent",
                "product_code": "DXZ",
                "statement_or_summary": "This device is substantially equivalent to previously cleared cardiac stent systems"
            },
            {
                "k_number": "K230002",
                "device_name": "Test Orthopedic Implant System",
                "applicant": "Test Orthopedic Solutions Corp",
                "decision_date": "2023-11-25",
                "date_received": "2023-09-10",
                "decision": "Substantially Equivalent",
                "product_code": "DXW",
                "statement_or_summary": "Hip replacement system with enhanced biocompatible coating"
            }
        ]
    },
    
    "pma": {
        "meta": {
            "disclaimer": "Test disclaimer",
            "terms": "Test terms",
            "license": "Test license",
            "last_updated": "2023-12-01",
            "results": {
                "skip": 0,
                "limit": 100,
                "total": 156
            }
        },
        "results": [
            {
                "pma_number": "P230001",
                "supplement_number": "",
                "trade_name": "Test AI Diagnostic Platform",
                "generic_name": "Computer-Aided Diagnostic Software",
                "applicant": "Test AI Medical Inc",
                "decision_date": "2023-11-20",
                "date_received": "2023-02-15",
                "decision": "Approved",
                "product_code": "DXV"
            },
            {
                "pma_number": "P230002",
                "supplement_number": "S001",
                "trade_name": "Test Robotic Surgical System",
                "generic_name": "Robotic Surgery Platform",
                "applicant": "Test Surgical Robotics Corp",
                "decision_date": "2023-10-15",
                "date_received": "2023-01-30",
                "decision": "Approved",
                "product_code": "DXU"
            }
        ]
    },
    
    "classification": {
        "meta": {
            "disclaimer": "Test disclaimer",
            "terms": "Test terms",
            "license": "Test license",
            "last_updated": "2023-12-01",
            "results": {
                "skip": 0,
                "limit": 100,
                "total": 2341
            }
        },
        "results": [
            {
                "device_name": "Cardiac Pacemaker",
                "medical_specialty_description": "Cardiovascular",
                "device_class": "3",
                "regulation_number": "21CFR870.3610",
                "product_code": "DXX",
                "definition": "An implantable cardiac pacemaker is a device that has a power source and electronic circuits that produce a periodic electrical pulse to stimulate the heart",
                "intended_use": "For treatment of bradycardia and other cardiac rhythm disorders"
            },
            {
                "device_name": "Blood Glucose Monitor",
                "medical_specialty_description": "Clinical Chemistry",
                "device_class": "2",
                "regulation_number": "21CFR862.1345",
                "product_code": "NBW",
                "definition": "A glucose meter is a device used to measure glucose concentration in blood",
                "intended_use": "For quantitative measurement of glucose in capillary whole blood"
            }
        ]
    },
    
    "udi": {
        "meta": {
            "disclaimer": "Test disclaimer",
            "terms": "Test terms",
            "license": "Test license",
            "last_updated": "2023-12-01",
            "results": {
                "skip": 0,
                "limit": 100,
                "total": 1567
            }
        },
        "results": [
            {
                "di": "00123456789012",
                "brand_name": "Test Surgical Instrument Set",
                "device_description": "Comprehensive surgical instrument set for general surgery procedures",
                "company_name": "Test Surgical Instruments Inc",
                "device_count": 12,
                "commercial_distribution_status": "In Commercial Distribution",
                "date_commercial_distribution": "2023-01-15"
            },
            {
                "di": "00123456789013",
                "brand_name": "Test Diagnostic Kit",
                "device_description": "Rapid diagnostic test kit for infectious disease detection",
                "company_name": "Test Diagnostics Corp",
                "device_count": 1,
                "commercial_distribution_status": "In Commercial Distribution",
                "date_commercial_distribution": "2023-03-20"
            }
        ]
    }
}

# Mock AI Analysis responses
MOCK_AI_RESPONSES = {
    "summary": {
        "analysis_type": "summary",
        "summary": "Analysis of the provided FDA data reveals important safety trends and regulatory patterns. The data shows increased reporting of device malfunctions and recalls, particularly in cardiovascular and diabetes management devices.",
        "key_findings": [
            "15% increase in adverse event reports compared to previous period",
            "Software-related issues account for 32% of recent recalls",
            "Class II recalls dominate, indicating moderate risk level",
            "Cardiovascular devices show highest reporting frequency"
        ],
        "confidence_score": 0.87,
        "metadata": {
            "analysis_date": "2023-12-01T10:00:00Z",
            "data_sources": ["events", "recalls", "510k"],
            "model_version": "test-model-v1.0"
        }
    },
    
    "risk_assessment": {
        "analysis_type": "risk_assessment",
        "summary": "Risk assessment indicates elevated concern levels due to recent patterns in device failures and recall trends.",
        "key_findings": [
            "Battery-related failures in cardiac devices pose significant risk",
            "Software defects in insulin pumps require immediate attention",
            "Trend analysis shows increasing complexity in device failures"
        ],
        "risk_score": 7.2,
        "recommendations": [
            "Enhanced post-market surveillance for cardiac devices",
            "Accelerated software validation protocols",
            "Increased manufacturer reporting requirements"
        ],
        "confidence_score": 0.82,
        "metadata": {
            "risk_factors": ["device_complexity", "software_defects", "critical_device_type"],
            "analysis_date": "2023-12-01T10:00:00Z"
        }
    },
    
    "trend_analysis": {
        "analysis_type": "trend_analysis", 
        "summary": "Trend analysis reveals concerning patterns in device safety reporting over the past 12 months.",
        "key_findings": [
            "Quarterly adverse event reports increased by 23%",
            "Software-related recalls doubled in the last 6 months",
            "Geographic clustering of events in urban healthcare systems",
            "Seasonal patterns in device failure rates"
        ],
        "confidence_score": 0.78,
        "recommendations": [
            "Implement predictive monitoring systems",
            "Develop seasonal maintenance protocols",
            "Establish regional safety monitoring networks"
        ],
        "metadata": {
            "trend_period": "12_months",
            "analysis_date": "2023-12-01T10:00:00Z",
            "statistical_significance": 0.95
        }
    }
}

# Mock error responses
MOCK_ERROR_RESPONSES = {
    "api_error": {
        "error": {
            "code": "INVALID_SEARCH_PARAMETER",
            "message": "Invalid search parameter: search term too broad"
        }
    },
    
    "rate_limit_error": {
        "error": {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "API rate limit exceeded. Please try again later."
        }
    },
    
    "not_found": {
        "error": {
            "code": "NOT_FOUND",
            "message": "No results found for the specified search criteria"
        }
    },
    
    "timeout_error": {
        "error": {
            "code": "REQUEST_TIMEOUT",
            "message": "Request timeout - please try again"
        }
    }
}

# Mock statistics response
MOCK_STATS_RESPONSE = {
    "total_endpoints": 6,
    "endpoints": ["event", "recall", "510k", "pma", "classification", "udi"],
    "api_status": "operational",
    "last_updated": "2023-12-01T10:00:00Z",
    "endpoint_stats": {
        "event": {"total_records": 1247, "last_updated": "2023-12-01"},
        "recall": {"total_records": 423, "last_updated": "2023-12-01"},
        "510k": {"total_records": 876, "last_updated": "2023-12-01"},
        "pma": {"total_records": 156, "last_updated": "2023-12-01"},
        "classification": {"total_records": 2341, "last_updated": "2023-12-01"},
        "udi": {"total_records": 1567, "last_updated": "2023-12-01"}
    }
}

# Mock device intelligence response
MOCK_DEVICE_INTELLIGENCE = {
    "device_name": "pacemaker",
    "data": {
        "events": [
            {
                "mdr_report_key": "12345678",
                "event_type": "Malfunction",
                "date_received": "2023-12-01",
                "device_brand_name": "Test Pacemaker Model X"
            }
        ],
        "recalls": [
            {
                "recall_number": "Z-1236-2023",
                "product_description": "Test Pacemaker System",
                "classification": "Class II"
            }
        ],
        "510k": [
            {
                "k_number": "K230003",
                "device_name": "Test Pacemaker System Advanced",
                "decision": "Substantially Equivalent"
            }
        ]
    },
    "risk_assessment": {
        "overall_risk_score": 6.5,
        "risk_factors": ["Battery failure", "Software defects", "Manufacturing issues"],
        "severity_level": "MEDIUM",
        "confidence_score": 0.83,
        "recommendations": [
            "Enhanced battery monitoring protocols",
            "Software validation improvements",
            "Manufacturing quality control review"
        ]
    }
}

# Mock comparison response
MOCK_DEVICE_COMPARISON = {
    "devices": ["pacemaker", "defibrillator"],
    "device_data": {
        "pacemaker": {
            "device_name": "pacemaker",
            "data": {
                "events": [{"mdr_report_key": "12345678", "event_type": "Malfunction"}],
                "recalls": [{"recall_number": "Z-1236-2023", "classification": "Class II"}]
            },
            "risk_assessment": {
                "overall_risk_score": 6.5,
                "severity_level": "MEDIUM",
                "confidence_score": 0.83
            }
        },
        "defibrillator": {
            "device_name": "defibrillator", 
            "data": {
                "events": [{"mdr_report_key": "12345679", "event_type": "Injury"}],
                "recalls": [{"recall_number": "Z-1237-2023", "classification": "Class I"}]
            },
            "risk_assessment": {
                "overall_risk_score": 8.2,
                "severity_level": "HIGH",
                "confidence_score": 0.89
            }
        }
    }
}

# Mock manufacturer intelligence response
MOCK_MANUFACTURER_INTELLIGENCE = {
    "manufacturer_name": "Test Medical Inc",
    "search_response": {
        "query": "Test Medical Inc",
        "query_type": "manufacturer",
        "results": {
            "events": [
                {
                    "mdr_report_key": "12345678",
                    "device_manufacturer": "Test Medical Inc",
                    "event_type": "Malfunction"
                }
            ],
            "recalls": [
                {
                    "recall_number": "Z-1234-2023",
                    "recalling_firm": "Test Medical Inc",
                    "classification": "Class II"
                }
            ]
        },
        "total_results": 89,
        "response_time": 1.23
    }
}

# Mock trend analysis response
MOCK_TREND_ANALYSIS = {
    "query": "pacemaker",
    "trend_data": {
        "6_months": {
            "events": [
                {"date_received": "2023-11-01", "event_type": "Malfunction"},
                {"date_received": "2023-10-15", "event_type": "Injury"}
            ],
            "recalls": [
                {"recall_initiation_date": "2023-11-15", "classification": "Class II"}
            ]
        },
        "12_months": {
            "events": [
                {"date_received": "2023-06-01", "event_type": "Malfunction"},
                {"date_received": "2023-05-15", "event_type": "Injury"}
            ],
            "recalls": [
                {"recall_initiation_date": "2023-05-20", "classification": "Class I"}
            ]
        }
    }
}


def get_mock_response(endpoint: str, query: str = None, error_type: str = None) -> Dict[str, Any]:
    """
    Get mock response for testing
    
    Args:
        endpoint: FDA endpoint (event, recall, 510k, pma, classification, udi)
        query: Search query (optional)
        error_type: Error type to simulate (optional)
        
    Returns:
        Mock response dictionary
    """
    if error_type:
        return MOCK_ERROR_RESPONSES.get(error_type, MOCK_ERROR_RESPONSES["api_error"])
    
    if endpoint == "stats":
        return MOCK_STATS_RESPONSE
    
    if endpoint == "device_intelligence":
        return MOCK_DEVICE_INTELLIGENCE
    
    if endpoint == "device_comparison":
        return MOCK_DEVICE_COMPARISON
    
    if endpoint == "manufacturer_intelligence":
        return MOCK_MANUFACTURER_INTELLIGENCE
    
    if endpoint == "trend_analysis":
        return MOCK_TREND_ANALYSIS
    
    return MOCK_FDA_RESPONSES.get(endpoint, MOCK_FDA_RESPONSES["event"])


def get_mock_ai_response(analysis_type: str = "summary") -> Dict[str, Any]:
    """
    Get mock AI analysis response
    
    Args:
        analysis_type: Type of analysis (summary, risk_assessment, trend_analysis)
        
    Returns:
        Mock AI response dictionary
    """
    return MOCK_AI_RESPONSES.get(analysis_type, MOCK_AI_RESPONSES["summary"])