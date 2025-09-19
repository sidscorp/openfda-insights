"""
FDA API Query Utilities

Provides query normalization and search strategy generation for FDA API endpoints.
"""

import re
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FDAQueryNormalizer:
    """Normalize and enhance queries for FDA API"""
    
    # Common device name variations and abbreviations
    DEVICE_SYNONYMS = {
        "insulin pump": ["insulin_pump", "insulin infusion pump", "infusion pump"],
        "pacemaker": ["cardiac pacemaker", "implantable pacemaker", "heart pacemaker"],
        "defibrillator": ["icd", "implantable cardioverter defibrillator", "aicd"],
        "stent": ["coronary stent", "vascular stent", "drug eluting stent"],
        "catheter": ["catheter", "cath"],
        "ventilator": ["mechanical ventilator", "respirator", "breathing machine"],
        "glucose monitor": ["cgm", "continuous glucose monitor", "blood glucose monitor"],
        "hip implant": ["hip prosthesis", "total hip replacement", "hip joint"],
        "knee implant": ["knee prosthesis", "total knee replacement", "knee joint"],
    }
    
    @classmethod
    def normalize_device_name(cls, device_name: str) -> List[str]:
        """
        Generate normalized variations of a device name for FDA search.
        
        Args:
            device_name: Original device name
            
        Returns:
            List of normalized search terms
        """
        normalized_terms = []
        device_lower = device_name.lower().strip()
        
        # Original term
        normalized_terms.append(device_name)
        
        # Replace spaces with underscores
        underscore_version = device_name.replace(" ", "_")
        if underscore_version != device_name:
            normalized_terms.append(underscore_version)
        
        # Remove spaces entirely
        no_space_version = device_name.replace(" ", "")
        if no_space_version not in normalized_terms:
            normalized_terms.append(no_space_version)
        
        # Check for known synonyms
        if device_lower in cls.DEVICE_SYNONYMS:
            normalized_terms.extend(cls.DEVICE_SYNONYMS[device_lower])
        
        # Handle plurals
        if device_name.endswith("s") and not device_name.endswith("ss"):
            singular = device_name[:-1]
            normalized_terms.append(singular)
        elif not device_name.endswith("s"):
            plural = device_name + "s"
            normalized_terms.append(plural)
        
        # Create wildcard versions for multi-word terms
        if " " in device_name:
            words = device_name.split()
            # First word with wildcard
            normalized_terms.append(f"{words[0]}*")
            # Last word with wildcard
            normalized_terms.append(f"*{words[-1]}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in normalized_terms:
            if term.lower() not in seen:
                seen.add(term.lower())
                unique_terms.append(term)
        
        return unique_terms
    
    @classmethod
    def build_search_query(cls, terms: List[str], field_names: List[str]) -> str:
        """
        Build an OR query across multiple terms and fields.
        
        Args:
            terms: List of search terms
            field_names: List of FDA field names to search
            
        Returns:
            FDA API search query string
        """
        query_parts = []
        
        for term in terms:
            for field in field_names:
                # Quote terms with spaces or special characters
                if " " in term or "-" in term:
                    query_parts.append(f'{field}:"{term}"')
                else:
                    query_parts.append(f'{field}:{term}')
        
        return " OR ".join(query_parts)
    
    @classmethod
    def get_endpoint_search_fields(cls, endpoint: str) -> List[str]:
        """
        Get the appropriate search fields for each FDA endpoint.
        
        Args:
            endpoint: FDA API endpoint name
            
        Returns:
            List of field names to search
        """
        field_map = {
            "event": ["device.generic_name", "device.brand_name"],
            "recall": ["product_description", "product_code"],
            "510k": ["device_name", "statement_or_summary"],
            "pma": ["trade_name", "generic_name"],
            "classification": ["device_name", "device_class"],
            "udi": ["brand_name", "version_or_model_number"],
        }
        
        return field_map.get(endpoint.lower(), ["device_name"])
    
    @classmethod
    def get_manufacturer_search_fields(cls, endpoint: str) -> List[str]:
        """Get manufacturer-specific search fields for each endpoint"""
        manufacturer_fields = {
            "event": ["device.manufacturer_d_name", "device.manufacturer_d_country"],
            "recall": ["recalling_firm", "firm_fei_number"],
            "510k": ["applicant"],
            "pma": ["applicant"],
            "classification": ["owner_operator_name"],
            "udi": ["company_name"],
        }
        return manufacturer_fields.get(endpoint.lower(), ["applicant"])
    
    @classmethod
    def create_date_filter(cls, months_back: Optional[int] = None) -> Optional[str]:
        """
        Create a date filter for FDA queries.
        
        Args:
            months_back: Number of months to look back
            
        Returns:
            Date filter string or None
        """
        if not months_back:
            return None
            
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months_back * 30)
        
        # Format dates for FDA API (YYYYMMDD)
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        return f"[{start_str} TO {end_str}]"
    
    @classmethod
    def build_enhanced_search_queries(cls, device_name: str, endpoint: str,
                                    date_range_months: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Build multiple search strategies for comprehensive results.
        
        Args:
            device_name: Device to search for
            endpoint: FDA API endpoint
            date_range_months: Optional date range filter
            
        Returns:
            List of search query dictionaries with strategy names
        """
        # Get normalized terms
        search_terms = cls.normalize_device_name(device_name)
        
        # Get appropriate fields for this endpoint
        search_fields = cls.get_endpoint_search_fields(endpoint)
        
        # Build queries with different strategies
        queries = []
        
        # Strategy 1: Try singular form first if plural
        if device_name.endswith('s') and not device_name.endswith('ss'):
            singular_term = device_name[:-1]
            singular_query = cls.build_search_query([singular_term], search_fields)
            queries.append({
                "strategy": "singular_first",
                "query": singular_query,
                "description": f"Singular form of '{device_name}'"
            })
        
        # Strategy 2: Exact match on original term
        exact_query = cls.build_search_query([device_name], search_fields)
        queries.append({
            "strategy": "exact",
            "query": exact_query,
            "description": f"Exact match for '{device_name}'"
        })
        
        # Strategy 2: All normalized variations
        if len(search_terms) > 1:
            normalized_query = cls.build_search_query(search_terms[:3], search_fields)  # Limit to avoid too long queries
            queries.append({
                "strategy": "normalized",
                "query": normalized_query,
                "description": f"Normalized variations of '{device_name}'"
            })
        
        # Strategy 3: Wildcard search for multi-word terms
        if " " in device_name:
            # Try wildcards for the complete phrase variations
            wildcard_terms = []
            # Wildcard around the whole phrase
            wildcard_terms.append(f"*{device_name}*")
            # Replace spaces with wildcard
            wildcard_terms.append("*".join(device_name.split()))
            # First word + wildcard
            first_word = device_name.split()[0]
            if len(first_word) > 3:
                wildcard_terms.append(f"{first_word}*")
            
            wildcard_query = cls.build_search_query(wildcard_terms[:2], search_fields)
            queries.append({
                "strategy": "wildcard",
                "query": wildcard_query,
                "description": f"Wildcard search for '{device_name}'"
            })
        
        # Add date filter if specified
        date_filter = cls.create_date_filter(date_range_months)
        if date_filter:
            # Add date field based on endpoint
            date_fields = {
                "event": "date_received",
                "recall": "event_date_initiated",
                "510k": "date_received",
                "pma": "decision_date"
            }
            date_field = date_fields.get(endpoint.lower())
            
            if date_field:
                for query in queries:
                    query["query"] = f'({query["query"]}) AND {date_field}:{date_filter}'
        
        return queries