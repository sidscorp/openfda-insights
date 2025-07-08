"""
Core Enhanced FDA Explorer - Main integration module
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import pandas as pd

from .client import EnhancedFDAClient
from .ai import AIAnalysisEngine
from .config import get_config
from .models import (
    SearchRequest,
    SearchResponse,
    AIAnalysisRequest,
    AIAnalysisResponse,
    RiskAssessment,
    RegulatoryTimeline,
)


class FDAExplorer:
    """
    Main Enhanced FDA Explorer class that orchestrates all components.
    
    This class provides a unified interface for FDA data exploration,
    combining reliable data access, intelligent analysis, and comprehensive insights.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Enhanced FDA Explorer.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = get_config() if config is None else config
        self.logger = logging.getLogger(__name__)
        
        # Initialize core components
        self.client = EnhancedFDAClient(config)
        self.ai_engine = AIAnalysisEngine(config)
        
        self.logger.info("Enhanced FDA Explorer initialized successfully")
    
    async def search(self, query: str, 
                    query_type: str = "device",
                    endpoints: Optional[List[str]] = None,
                    limit: int = 100,
                    include_ai_analysis: bool = True,
                    **kwargs) -> SearchResponse:
        """
        Perform comprehensive FDA data search with optional AI analysis.
        
        Args:
            query: Search query string
            query_type: Type of query (device, manufacturer)
            endpoints: List of endpoints to search
            limit: Maximum results per endpoint
            include_ai_analysis: Whether to include AI analysis
            **kwargs: Additional search parameters
            
        Returns:
            Comprehensive search response with optional AI insights
        """
        # Default endpoints if not specified
        if endpoints is None:
            endpoints = ["event", "recall", "510k", "pma", "classification", "udi"]
        
        # Create search request
        request = SearchRequest(
            query=query,
            query_type=query_type,
            endpoints=endpoints,
            limit=limit,
            include_ai_analysis=include_ai_analysis,
            **kwargs
        )
        
        # Execute search
        response = await self.client.search(request)
        
        # Add AI analysis if requested
        if include_ai_analysis and response.results:
            ai_analysis = await self.ai_engine.analyze_search_results(
                response.results, query, query_type
            )
            response.ai_analysis = ai_analysis
        
        return response
    
    async def get_device_intelligence(self, device_name: str,
                                   lookback_months: int = 12,
                                   include_risk_assessment: bool = True) -> Dict[str, Any]:
        """
        Get comprehensive device intelligence including risk assessment.
        
        Args:
            device_name: Name of the device
            lookback_months: Number of months to look back
            include_risk_assessment: Whether to include risk assessment
            
        Returns:
            Comprehensive device intelligence report
        """
        # Get comprehensive device data
        device_data = self.client.get_comprehensive_device_data(
            device_name, lookback_months
        )
        
        # Perform AI analysis
        ai_analysis = await self.ai_engine.analyze_device_data(
            device_data, device_name
        )
        
        # Generate risk assessment if requested
        risk_assessment = None
        if include_risk_assessment:
            risk_assessment = await self.ai_engine.generate_risk_assessment(
                device_data, device_name
            )
        
        # Create regulatory timeline
        regulatory_timeline = await self.ai_engine.create_regulatory_timeline(
            device_data, device_name
        )
        
        return {
            "device_name": device_name,
            "data": device_data,
            "ai_analysis": ai_analysis,
            "risk_assessment": risk_assessment,
            "regulatory_timeline": regulatory_timeline,
            "metadata": {
                "lookback_months": lookback_months,
                "generated_at": datetime.now().isoformat(),
                "total_records": sum(len(df) for df in device_data.values()),
            }
        }
    
    async def get_manufacturer_intelligence(self, manufacturer_name: str,
                                         lookback_months: int = 12) -> Dict[str, Any]:
        """
        Get comprehensive manufacturer intelligence.
        
        Args:
            manufacturer_name: Name of the manufacturer
            lookback_months: Number of months to look back
            
        Returns:
            Comprehensive manufacturer intelligence report
        """
        # Search for manufacturer data
        response = await self.search(
            query=manufacturer_name,
            query_type="manufacturer",
            limit=500,
            include_ai_analysis=True,
            date_range={
                "start_date": datetime.now() - timedelta(days=lookback_months * 30),
                "end_date": datetime.now()
            }
        )
        
        # Additional manufacturer-specific analysis
        manufacturer_analysis = await self.ai_engine.analyze_manufacturer_data(
            response.results, manufacturer_name
        )
        
        return {
            "manufacturer_name": manufacturer_name,
            "search_response": response,
            "manufacturer_analysis": manufacturer_analysis,
            "metadata": {
                "lookback_months": lookback_months,
                "generated_at": datetime.now().isoformat(),
            }
        }
    
    async def compare_devices(self, device_names: List[str],
                            lookback_months: int = 12) -> Dict[str, Any]:
        """
        Compare multiple devices across various metrics.
        
        Args:
            device_names: List of device names to compare
            lookback_months: Number of months to look back
            
        Returns:
            Comprehensive device comparison report
        """
        device_data = {}
        
        # Get data for each device
        for device_name in device_names:
            device_data[device_name] = await self.get_device_intelligence(
                device_name, lookback_months, include_risk_assessment=True
            )
        
        # Perform comparative analysis
        comparison_analysis = await self.ai_engine.compare_devices(
            device_data, device_names
        )
        
        return {
            "devices": device_names,
            "device_data": device_data,
            "comparison_analysis": comparison_analysis,
            "metadata": {
                "lookback_months": lookback_months,
                "generated_at": datetime.now().isoformat(),
            }
        }
    
    async def get_regulatory_insights(self, query: str,
                                    analysis_type: str = "summary") -> Dict[str, Any]:
        """
        Get regulatory insights for a specific query.
        
        Args:
            query: Search query
            analysis_type: Type of analysis (summary, risk_assessment, timeline)
            
        Returns:
            Regulatory insights report
        """
        # Get comprehensive data
        response = await self.search(
            query=query,
            include_ai_analysis=True,
            limit=200
        )
        
        # Generate specific insights
        insights = await self.ai_engine.generate_regulatory_insights(
            response.results, query, analysis_type
        )
        
        return {
            "query": query,
            "analysis_type": analysis_type,
            "search_response": response,
            "insights": insights,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
            }
        }
    
    async def get_trend_analysis(self, query: str,
                               time_periods: List[str] = None) -> Dict[str, Any]:
        """
        Get trend analysis for a specific query over time.
        
        Args:
            query: Search query
            time_periods: List of time periods to analyze
            
        Returns:
            Trend analysis report
        """
        if time_periods is None:
            time_periods = ["6months", "1year", "2years"]
        
        trend_data = {}
        
        # Get data for each time period
        for period in time_periods:
            months = self._parse_time_period(period)
            
            response = await self.search(
                query=query,
                include_ai_analysis=False,
                limit=500,
                date_range={
                    "start_date": datetime.now() - timedelta(days=months * 30),
                    "end_date": datetime.now()
                }
            )
            
            trend_data[period] = response.results
        
        # Perform trend analysis
        trend_analysis = await self.ai_engine.analyze_trends(
            trend_data, query, time_periods
        )
        
        return {
            "query": query,
            "time_periods": time_periods,
            "trend_data": trend_data,
            "trend_analysis": trend_analysis,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
            }
        }
    
    def _parse_time_period(self, period: str) -> int:
        """Parse time period string to months."""
        if "month" in period.lower():
            return int(period.lower().replace("months", "").replace("month", ""))
        elif "year" in period.lower():
            return int(period.lower().replace("years", "").replace("year", "")) * 12
        else:
            return 12  # Default to 1 year
    
    async def get_summary_statistics(self) -> Dict[str, Any]:
        """
        Get summary statistics about the FDA data.
        
        Returns:
            Summary statistics
        """
        # This would typically query the database for statistics
        # For now, return placeholder data
        return {
            "total_endpoints": 6,
            "endpoints": ["event", "recall", "510k", "pma", "classification", "udi"],
            "last_updated": datetime.now().isoformat(),
            "api_status": "operational",
            "features": {
                "ai_analysis": True,
                "risk_assessment": True,
                "trend_analysis": True,
                "multi_interface": True,
            }
        }
    
    def close(self):
        """Close the explorer and clean up resources."""
        if hasattr(self.client, 'close'):
            self.client.close()
        if hasattr(self.ai_engine, 'close'):
            self.ai_engine.close()


# Convenience functions for common operations
async def search_devices(query: str, limit: int = 100, **kwargs) -> SearchResponse:
    """Convenience function to search for devices."""
    explorer = FDAExplorer()
    try:
        return await explorer.search(query, query_type="device", limit=limit, **kwargs)
    finally:
        explorer.close()


async def search_manufacturers(query: str, limit: int = 100, **kwargs) -> SearchResponse:
    """Convenience function to search for manufacturers."""
    explorer = FDAExplorer()
    try:
        return await explorer.search(query, query_type="manufacturer", limit=limit, **kwargs)
    finally:
        explorer.close()


async def get_device_risk_assessment(device_name: str, **kwargs) -> Dict[str, Any]:
    """Convenience function to get device risk assessment."""
    explorer = FDAExplorer()
    try:
        return await explorer.get_device_intelligence(
            device_name, include_risk_assessment=True, **kwargs
        )
    finally:
        explorer.close()


# Context manager for proper resource cleanup
class FDAExplorerContext:
    """Context manager for FDA Explorer."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config
        self.explorer = None
    
    async def __aenter__(self):
        self.explorer = FDAExplorer(self.config)
        return self.explorer
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.explorer:
            self.explorer.close()