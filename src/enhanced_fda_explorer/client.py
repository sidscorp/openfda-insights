"""
Enhanced FDA Client - Integration of OpenFDA-Client with FDA-Devices functionality
"""

import time
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import pandas as pd
import logging

# Import OpenFDA-Client functionality (integrated inline for now)
# Note: In production, this would import from the actual openfda-client package
# For now, we'll implement a simplified version inline

import requests
from urllib.parse import urljoin

from .config import get_config
from .models import (
    SearchRequest,
    SearchResponse,
    DeviceEvent,
    DeviceClassification,
    DeviceRecall,
    Device510K,
    DevicePMA,
    DeviceUDI,
)


class SimpleOpenFDAClient:
    """Simplified OpenFDA client for testing purposes"""
    
    def __init__(self, api_key=None, config=None):
        self.api_key = api_key
        self.base_url = "https://api.fda.gov/"
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
    
    def search(self, endpoint, search=None, limit=None, **kwargs):
        """Simple search implementation"""
        try:
            url = urljoin(self.base_url, f"device/{endpoint}.json")
            params = {}
            
            if search:
                params['search'] = search
            if limit:
                params['limit'] = min(limit, 1000)
            if self.api_key:
                params['api_key'] = self.api_key
            
            params.update(kwargs)
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"OpenFDA API request failed: {e}")
            return {"results": [], "meta": {"results": {"total": 0}}}
    
    def close(self):
        """Close the session"""
        self.session.close()


class EnhancedFDAClient:
    """
    Enhanced FDA Client that combines OpenFDA-Client reliability 
    with FDA-Devices intelligent analysis capabilities.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Enhanced FDA Client.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = get_config() if config is None else config
        self.logger = logging.getLogger(__name__)
        
        # Initialize the base OpenFDA client
        self.base_client = SimpleOpenFDAClient(
            api_key=self.config.openfda.api_key,
            config=self.config.get_openfda_client_config()
        )
        
        # Enhanced search capabilities
        self.search_strategies = SearchStrategies()
        self.data_processor = DataProcessor()
        
    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Enhanced search with intelligent query processing.
        
        Args:
            request: Search request with parameters
            
        Returns:
            Comprehensive search response
        """
        start_time = time.time()
        
        try:
            # Process and enhance the query
            enhanced_queries = self.search_strategies.build_enhanced_queries(
                request.query, request.query_type
            )
            
            # Execute searches across relevant endpoints
            all_results = {}
            
            for endpoint in request.endpoints:
                endpoint_results = await self._search_endpoint(
                    endpoint, enhanced_queries, request
                )
                if endpoint_results:
                    all_results[endpoint] = endpoint_results
            
            # Process and validate results
            processed_results = self.data_processor.process_results(
                all_results, request.query_type
            )
            
            response_time = time.time() - start_time
            
            return SearchResponse(
                query=request.query,
                query_type=request.query_type,
                results=processed_results,
                total_results=sum(len(df) for df in processed_results.values()),
                response_time=response_time,
                metadata={
                    "endpoints_searched": list(all_results.keys()),
                    "search_strategies": len(enhanced_queries),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            raise
    
    async def _search_endpoint(self, endpoint: str, queries: List[str], 
                             request: SearchRequest) -> Optional[pd.DataFrame]:
        """
        Search a specific endpoint with multiple query strategies.
        
        Args:
            endpoint: FDA endpoint name
            queries: List of query strings to try
            request: Original search request
            
        Returns:
            Combined results DataFrame
        """
        all_results = []
        
        for query in queries:
            try:
                # Use the base client for robust API calls
                response = self.base_client.search(
                    endpoint=endpoint,
                    search=query,
                    limit=min(request.limit, 1000),
                    sort=self._get_sort_for_endpoint(endpoint),
                )
                
                if response.get("results"):
                    all_results.extend(response["results"])
                    
                    # If we have enough results, break
                    if len(all_results) >= request.limit:
                        break
                        
            except Exception as e:
                self.logger.warning(f"Query failed for {endpoint}: {e}")
                continue
        
        if not all_results:
            return None
        
        # Convert to DataFrame and process
        df = pd.json_normalize(all_results)
        df = self.data_processor.standardize_dataframe(df, endpoint)
        
        # Apply date filtering if specified
        if request.date_range:
            df = self._filter_by_date_range(df, endpoint, request.date_range)
        
        return df.head(request.limit)
    
    def _get_sort_for_endpoint(self, endpoint: str) -> Optional[str]:
        """Get appropriate sort parameter for endpoint."""
        sort_map = {
            "event": "date_received:desc",
            "recall": "event_date_initiated:desc",
            "510k": "decision_date:desc",
            "pma": "decision_date:desc",
            "classification": None,
            "udi": None,
        }
        return sort_map.get(endpoint.lower())
    
    def _filter_by_date_range(self, df: pd.DataFrame, endpoint: str, 
                            date_range: Dict[str, Any]) -> pd.DataFrame:
        """Filter DataFrame by date range."""
        date_field_map = {
            "event": "date_received",
            "recall": "event_date_initiated", 
            "510k": "decision_date",
            "pma": "decision_date",
        }
        
        date_field = date_field_map.get(endpoint.lower())
        if not date_field or date_field not in df.columns:
            return df
        
        # Convert date column to datetime
        df[date_field] = pd.to_datetime(df[date_field], errors='coerce')
        
        # Apply date filters
        if date_range.get("start_date"):
            start_date = pd.to_datetime(date_range["start_date"])
            df = df[df[date_field] >= start_date]
        
        if date_range.get("end_date"):
            end_date = pd.to_datetime(date_range["end_date"])
            df = df[df[date_field] <= end_date]
        
        return df
    
    def get_device_events(self, device_name: str, limit: int = 100) -> List[DeviceEvent]:
        """Get device adverse events with structured data."""
        try:
            response = self.base_client.search(
                endpoint="event",
                search=f"device.brand_name:{device_name} OR device.generic_name:{device_name}",
                limit=limit,
                sort="date_received:desc"
            )
            
            events = []
            for result in response.get("results", []):
                events.append(DeviceEvent.from_api_response(result))
            
            return events
            
        except Exception as e:
            self.logger.error(f"Failed to get device events: {e}")
            return []
    
    def get_device_classifications(self, device_name: str, 
                                 limit: int = 100) -> List[DeviceClassification]:
        """Get device classifications with structured data."""
        try:
            response = self.base_client.search(
                endpoint="classification",
                search=f"device_name:{device_name}",
                limit=limit
            )
            
            classifications = []
            for result in response.get("results", []):
                classifications.append(DeviceClassification.from_api_response(result))
            
            return classifications
            
        except Exception as e:
            self.logger.error(f"Failed to get device classifications: {e}")
            return []
    
    def get_device_recalls(self, device_name: str, limit: int = 100) -> List[DeviceRecall]:
        """Get device recalls with structured data."""
        try:
            response = self.base_client.search(
                endpoint="recall",
                search=f"product_description:{device_name}",
                limit=limit,
                sort="event_date_initiated:desc"
            )
            
            recalls = []
            for result in response.get("results", []):
                recalls.append(DeviceRecall.from_api_response(result))
            
            return recalls
            
        except Exception as e:
            self.logger.error(f"Failed to get device recalls: {e}")
            return []
    
    def get_comprehensive_device_data(self, device_name: str, 
                                   lookback_months: int = 12) -> Dict[str, pd.DataFrame]:
        """
        Get comprehensive device data across all endpoints.
        
        Args:
            device_name: Device name to search for
            lookback_months: Number of months to look back
            
        Returns:
            Dictionary of DataFrames by endpoint
        """
        request = SearchRequest(
            query=device_name,
            query_type="device",
            endpoints=["event", "recall", "510k", "pma", "classification", "udi"],
            limit=500,
            date_range={
                "start_date": datetime.now() - timedelta(days=lookback_months * 30),
                "end_date": datetime.now()
            }
        )
        
        # Run the search synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(self.search(request))
            return response.results
        finally:
            loop.close()
    
    def close(self):
        """Close the client and clean up resources."""
        if hasattr(self.base_client, 'close'):
            self.base_client.close()


class SearchStrategies:
    """Enhanced search strategies for intelligent query processing."""
    
    def build_enhanced_queries(self, query: str, query_type: str) -> List[str]:
        """
        Build multiple search strategies for comprehensive results.
        
        Args:
            query: Original search query
            query_type: Type of query (device, manufacturer)
            
        Returns:
            List of enhanced query strings
        """
        queries = []
        words = query.strip().lower().split()
        
        # Strategy 1: Exact phrase search
        if len(words) > 1:
            queries.append(f'"{query}"')
        
        # Strategy 2: AND search for multi-word queries
        if len(words) > 1:
            and_query = " AND ".join(words)
            queries.append(and_query)
        
        # Strategy 3: OR search for broader results
        if len(words) > 1:
            or_query = " OR ".join(words)
            queries.append(or_query)
        
        # Strategy 4: Individual word searches
        for word in words:
            if len(word) > 2:  # Skip short words
                queries.append(word)
        
        # Strategy 5: Wildcard searches
        for word in words:
            if len(word) > 3:
                queries.append(f"{word}*")
        
        return queries[:5]  # Limit to 5 strategies


class DataProcessor:
    """Enhanced data processing for FDA results."""
    
    def process_results(self, results: Dict[str, pd.DataFrame], 
                       query_type: str) -> Dict[str, pd.DataFrame]:
        """
        Process and enhance raw FDA results.
        
        Args:
            results: Raw results by endpoint
            query_type: Type of query for context
            
        Returns:
            Processed results
        """
        processed = {}
        
        for endpoint, df in results.items():
            if not df.empty:
                # Standardize the DataFrame
                df = self.standardize_dataframe(df, endpoint)
                
                # Add derived fields
                df = self.add_derived_fields(df, endpoint)
                
                # Sort by relevance/date
                df = self.sort_by_relevance(df, endpoint)
                
                processed[endpoint] = df
        
        return processed
    
    def standardize_dataframe(self, df: pd.DataFrame, endpoint: str) -> pd.DataFrame:
        """Standardize DataFrame structure and data types."""
        # Add source information
        df["source"] = endpoint.upper()
        df["retrieved_at"] = datetime.now()
        
        # Standardize date columns
        date_columns = self._get_date_columns(endpoint)
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        return df
    
    def add_derived_fields(self, df: pd.DataFrame, endpoint: str) -> pd.DataFrame:
        """Add derived fields for enhanced analysis."""
        # Add risk score (placeholder for now)
        df["risk_score"] = 0.0
        
        # Add categorization
        df["category"] = self._categorize_records(df, endpoint)
        
        return df
    
    def sort_by_relevance(self, df: pd.DataFrame, endpoint: str) -> pd.DataFrame:
        """Sort DataFrame by relevance and recency."""
        # Primary sort by date (most recent first)
        date_columns = self._get_date_columns(endpoint)
        sort_column = None
        
        for col in date_columns:
            if col in df.columns:
                sort_column = col
                break
        
        if sort_column:
            df = df.sort_values(sort_column, ascending=False)
        
        return df
    
    def _get_date_columns(self, endpoint: str) -> List[str]:
        """Get relevant date columns for an endpoint."""
        date_columns_map = {
            "event": ["date_received", "date_of_event"],
            "recall": ["event_date_initiated", "recall_initiation_date"],
            "510k": ["decision_date", "date_received"],
            "pma": ["decision_date", "date_received"],
            "classification": [],
            "udi": [],
        }
        return date_columns_map.get(endpoint.lower(), [])
    
    def _categorize_records(self, df: pd.DataFrame, endpoint: str) -> List[str]:
        """Categorize records for enhanced analysis."""
        # Simple categorization logic (can be enhanced with ML)
        categories = []
        
        for _, row in df.iterrows():
            if endpoint.lower() == "event":
                categories.append("adverse_event")
            elif endpoint.lower() == "recall":
                categories.append("recall")
            elif endpoint.lower() == "510k":
                categories.append("clearance")
            elif endpoint.lower() == "pma":
                categories.append("approval")
            else:
                categories.append("regulatory")
        
        return categories