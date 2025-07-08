"""
AI Analysis Engine for Enhanced FDA Explorer
"""

import json
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from .config import get_config
from .models import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    RiskAssessment,
    RegulatoryTimeline,
)


class AIAnalysisEngine:
    """
    AI-powered analysis engine for FDA data with domain expertise.
    
    This engine provides intelligent analysis of FDA data including:
    - Risk assessment and scoring
    - Regulatory timeline construction
    - Pattern recognition and trends
    - Comparative analysis
    - Regulatory insights
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the AI Analysis Engine.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = get_config() if config is None else config
        self.logger = logging.getLogger(__name__)
        
        # Initialize AI client based on configuration
        self.ai_client = self._setup_ai_client()
        
        # Domain knowledge and templates
        self.domain_knowledge = DomainKnowledge()
        self.prompt_templates = PromptTemplates()
        
        self.logger.info("AI Analysis Engine initialized successfully")
    
    def _setup_ai_client(self):
        """Setup AI client based on configuration."""
        ai_config = self.config.get_ai_config()
        
        if ai_config["provider"] == "openai":
            return OpenAIClient(ai_config)
        elif ai_config["provider"] == "openrouter":
            return OpenRouterClient(ai_config)
        elif ai_config["provider"] == "anthropic":
            return AnthropicClient(ai_config)
        else:
            raise ValueError(f"Unsupported AI provider: {ai_config['provider']}")
    
    async def analyze_search_results(self, results: Dict[str, pd.DataFrame],
                                   query: str, query_type: str) -> Dict[str, Any]:
        """
        Analyze search results and provide comprehensive insights.
        
        Args:
            results: Search results by endpoint
            query: Original search query
            query_type: Type of query (device, manufacturer)
            
        Returns:
            Comprehensive analysis results
        """
        try:
            # Prepare data summary
            data_summary = self._prepare_data_summary(results)
            
            # Generate analysis prompt
            prompt = self.prompt_templates.get_search_analysis_prompt(
                query, query_type, data_summary
            )
            
            # Get AI analysis
            ai_response = await self.ai_client.generate_analysis(prompt)
            
            # Parse and structure the response
            analysis = self._parse_ai_response(ai_response, "search_analysis")
            
            # Add quantitative metrics
            analysis["metrics"] = self._calculate_search_metrics(results)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Search analysis failed: {e}")
            return {"error": str(e)}
    
    async def analyze_device_data(self, device_data: Dict[str, pd.DataFrame],
                                device_name: str) -> Dict[str, Any]:
        """
        Analyze comprehensive device data.
        
        Args:
            device_data: Device data by endpoint
            device_name: Name of the device
            
        Returns:
            Comprehensive device analysis
        """
        try:
            # Prepare device-specific analysis
            device_summary = self._prepare_device_summary(device_data, device_name)
            
            # Generate analysis prompt
            prompt = self.prompt_templates.get_device_analysis_prompt(
                device_name, device_summary
            )
            
            # Get AI analysis
            ai_response = await self.ai_client.generate_analysis(prompt)
            
            # Parse and structure the response
            analysis = self._parse_ai_response(ai_response, "device_analysis")
            
            # Add device-specific metrics
            analysis["device_metrics"] = self._calculate_device_metrics(device_data)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Device analysis failed: {e}")
            return {"error": str(e)}
    
    async def generate_risk_assessment(self, data: Dict[str, pd.DataFrame],
                                     context: str) -> RiskAssessment:
        """
        Generate comprehensive risk assessment.
        
        Args:
            data: FDA data for analysis
            context: Context for risk assessment (device name, etc.)
            
        Returns:
            Structured risk assessment
        """
        try:
            # Calculate risk factors
            risk_factors = self._calculate_risk_factors(data)
            
            # Generate risk assessment prompt
            prompt = self.prompt_templates.get_risk_assessment_prompt(
                context, risk_factors
            )
            
            # Get AI analysis
            ai_response = await self.ai_client.generate_analysis(prompt)
            
            # Parse risk assessment
            risk_data = self._parse_risk_assessment(ai_response, risk_factors)
            
            return RiskAssessment(
                overall_risk_score=risk_data["overall_risk_score"],
                risk_factors=risk_data["risk_factors"],
                severity_level=risk_data["severity_level"],
                confidence_score=risk_data["confidence_score"],
                recommendations=risk_data["recommendations"]
            )
            
        except Exception as e:
            self.logger.error(f"Risk assessment failed: {e}")
            return RiskAssessment(
                overall_risk_score=0.0,
                risk_factors=["Error in risk assessment"],
                severity_level="LOW",
                confidence_score=0.0,
                recommendations=["Manual review required"]
            )
    
    async def create_regulatory_timeline(self, data: Dict[str, pd.DataFrame],
                                       context: str) -> RegulatoryTimeline:
        """
        Create regulatory timeline from FDA data.
        
        Args:
            data: FDA data for timeline construction
            context: Context for timeline (device name, etc.)
            
        Returns:
            Structured regulatory timeline
        """
        try:
            # Extract timeline events
            timeline_events = self._extract_timeline_events(data)
            
            # Generate timeline analysis prompt
            prompt = self.prompt_templates.get_timeline_prompt(
                context, timeline_events
            )
            
            # Get AI analysis
            ai_response = await self.ai_client.generate_analysis(prompt)
            
            # Parse timeline
            timeline_data = self._parse_timeline(ai_response, timeline_events)
            
            return RegulatoryTimeline(
                events=timeline_data["events"],
                key_milestones=timeline_data["key_milestones"],
                regulatory_pathway=timeline_data.get("regulatory_pathway"),
                approval_status=timeline_data.get("approval_status"),
                timeline_analysis=timeline_data.get("timeline_analysis")
            )
            
        except Exception as e:
            self.logger.error(f"Timeline creation failed: {e}")
            return RegulatoryTimeline(
                events=[],
                key_milestones=["Error in timeline creation"],
                timeline_analysis="Timeline analysis failed"
            )
    
    async def analyze_manufacturer_data(self, data: Dict[str, pd.DataFrame],
                                      manufacturer_name: str) -> Dict[str, Any]:
        """
        Analyze manufacturer-specific data.
        
        Args:
            data: Manufacturer data by endpoint
            manufacturer_name: Name of the manufacturer
            
        Returns:
            Manufacturer analysis
        """
        try:
            # Prepare manufacturer summary
            manufacturer_summary = self._prepare_manufacturer_summary(data, manufacturer_name)
            
            # Generate analysis prompt
            prompt = self.prompt_templates.get_manufacturer_analysis_prompt(
                manufacturer_name, manufacturer_summary
            )
            
            # Get AI analysis
            ai_response = await self.ai_client.generate_analysis(prompt)
            
            # Parse and structure the response
            analysis = self._parse_ai_response(ai_response, "manufacturer_analysis")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Manufacturer analysis failed: {e}")
            return {"error": str(e)}
    
    async def compare_devices(self, device_data: Dict[str, Any],
                            device_names: List[str]) -> Dict[str, Any]:
        """
        Compare multiple devices across various metrics.
        
        Args:
            device_data: Data for all devices
            device_names: List of device names
            
        Returns:
            Comparative analysis
        """
        try:
            # Prepare comparison data
            comparison_data = self._prepare_comparison_data(device_data, device_names)
            
            # Generate comparison prompt
            prompt = self.prompt_templates.get_device_comparison_prompt(
                device_names, comparison_data
            )
            
            # Get AI analysis
            ai_response = await self.ai_client.generate_analysis(prompt)
            
            # Parse comparison
            comparison = self._parse_ai_response(ai_response, "device_comparison")
            
            return comparison
            
        except Exception as e:
            self.logger.error(f"Device comparison failed: {e}")
            return {"error": str(e)}
    
    async def generate_regulatory_insights(self, data: Dict[str, pd.DataFrame],
                                         query: str, analysis_type: str) -> Dict[str, Any]:
        """
        Generate regulatory insights for specific analysis type.
        
        Args:
            data: FDA data for analysis
            query: Original query
            analysis_type: Type of analysis requested
            
        Returns:
            Regulatory insights
        """
        try:
            # Prepare insights data
            insights_data = self._prepare_insights_data(data, analysis_type)
            
            # Generate insights prompt
            prompt = self.prompt_templates.get_regulatory_insights_prompt(
                query, analysis_type, insights_data
            )
            
            # Get AI analysis
            ai_response = await self.ai_client.generate_analysis(prompt)
            
            # Parse insights
            insights = self._parse_ai_response(ai_response, "regulatory_insights")
            
            return insights
            
        except Exception as e:
            self.logger.error(f"Regulatory insights failed: {e}")
            return {"error": str(e)}
    
    async def analyze_trends(self, trend_data: Dict[str, Any],
                           query: str, time_periods: List[str]) -> Dict[str, Any]:
        """
        Analyze trends over time periods.
        
        Args:
            trend_data: Data for different time periods
            query: Original query
            time_periods: List of time periods
            
        Returns:
            Trend analysis
        """
        try:
            # Prepare trend analysis data
            trend_summary = self._prepare_trend_data(trend_data, time_periods)
            
            # Generate trend analysis prompt
            prompt = self.prompt_templates.get_trend_analysis_prompt(
                query, time_periods, trend_summary
            )
            
            # Get AI analysis
            ai_response = await self.ai_client.generate_analysis(prompt)
            
            # Parse trend analysis
            trend_analysis = self._parse_ai_response(ai_response, "trend_analysis")
            
            return trend_analysis
            
        except Exception as e:
            self.logger.error(f"Trend analysis failed: {e}")
            return {"error": str(e)}
    
    def _prepare_data_summary(self, results: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Prepare data summary for AI analysis."""
        summary = {}
        
        for endpoint, df in results.items():
            if df.empty:
                continue
                
            summary[endpoint] = {
                "total_records": len(df),
                "date_range": self._get_date_range(df, endpoint),
                "key_fields": list(df.columns[:10]),  # First 10 columns
                "sample_data": df.head(3).to_dict('records') if len(df) > 0 else []
            }
        
        return summary
    
    def _prepare_device_summary(self, data: Dict[str, pd.DataFrame], device_name: str) -> Dict[str, Any]:
        """Prepare device-specific summary."""
        summary = {
            "device_name": device_name,
            "data_sources": list(data.keys()),
            "total_records": sum(len(df) for df in data.values()),
            "endpoints": {}
        }
        
        for endpoint, df in data.items():
            if df.empty:
                continue
                
            summary["endpoints"][endpoint] = {
                "record_count": len(df),
                "date_range": self._get_date_range(df, endpoint),
                "key_insights": self._extract_key_insights(df, endpoint)
            }
        
        return summary
    
    def _calculate_risk_factors(self, data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Calculate risk factors from FDA data."""
        risk_factors = {
            "adverse_events": 0,
            "recalls": 0,
            "severity_indicators": [],
            "frequency_trends": {},
            "regulatory_actions": 0
        }
        
        # Count adverse events
        if "EVENT" in data and not data["EVENT"].empty:
            risk_factors["adverse_events"] = len(data["EVENT"])
        
        # Count recalls
        if "RECALL" in data and not data["RECALL"].empty:
            risk_factors["recalls"] = len(data["RECALL"])
        
        # Calculate regulatory actions
        regulatory_endpoints = ["510K", "PMA", "CLASSIFICATION"]
        for endpoint in regulatory_endpoints:
            if endpoint in data and not data[endpoint].empty:
                risk_factors["regulatory_actions"] += len(data[endpoint])
        
        return risk_factors
    
    def _extract_timeline_events(self, data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """Extract timeline events from FDA data."""
        events = []
        
        # Extract events from each endpoint
        for endpoint, df in data.items():
            if df.empty:
                continue
                
            date_columns = self._get_date_columns(endpoint)
            for _, row in df.iterrows():
                for date_col in date_columns:
                    if date_col in row and pd.notna(row[date_col]):
                        events.append({
                            "date": row[date_col],
                            "event_type": endpoint,
                            "description": self._get_event_description(row, endpoint),
                            "source": endpoint
                        })
        
        # Sort by date
        events.sort(key=lambda x: x["date"])
        
        return events
    
    def _get_date_range(self, df: pd.DataFrame, endpoint: str) -> Dict[str, Any]:
        """Get date range for a DataFrame."""
        date_columns = self._get_date_columns(endpoint)
        
        for date_col in date_columns:
            if date_col in df.columns:
                dates = pd.to_datetime(df[date_col], errors='coerce')
                valid_dates = dates.dropna()
                
                if len(valid_dates) > 0:
                    return {
                        "start_date": valid_dates.min().isoformat(),
                        "end_date": valid_dates.max().isoformat(),
                        "date_column": date_col
                    }
        
        return {"start_date": None, "end_date": None, "date_column": None}
    
    def _get_date_columns(self, endpoint: str) -> List[str]:
        """Get relevant date columns for an endpoint."""
        date_columns_map = {
            "EVENT": ["date_received", "date_of_event"],
            "RECALL": ["event_date_initiated", "recall_initiation_date"],
            "510K": ["decision_date", "date_received"],
            "PMA": ["decision_date", "date_received"],
            "CLASSIFICATION": [],
            "UDI": ["date_commercial_distribution"],
        }
        return date_columns_map.get(endpoint.upper(), [])
    
    def _parse_ai_response(self, response: str, analysis_type: str) -> Dict[str, Any]:
        """Parse AI response into structured format."""
        try:
            # Try to parse as JSON first
            return json.loads(response)
        except json.JSONDecodeError:
            # If not JSON, parse as structured text
            return {
                "summary": response,
                "analysis_type": analysis_type,
                "parsed_at": datetime.now().isoformat()
            }
    
    def close(self):
        """Close the AI engine and clean up resources."""
        if hasattr(self.ai_client, 'close'):
            self.ai_client.close()


class DomainKnowledge:
    """Domain knowledge for FDA regulatory intelligence."""
    
    def __init__(self):
        self.device_classifications = {
            "I": "Low Risk",
            "II": "Moderate Risk", 
            "III": "High Risk"
        }
        
        self.regulatory_pathways = {
            "510k": "Premarket Notification",
            "PMA": "Premarket Approval",
            "De Novo": "De Novo Classification"
        }
        
        self.risk_indicators = [
            "death", "serious injury", "malfunction", "recall",
            "class i recall", "class ii recall", "class iii recall"
        ]


class PromptTemplates:
    """AI prompt templates for different analysis types."""
    
    def get_search_analysis_prompt(self, query: str, query_type: str, data_summary: Dict[str, Any]) -> str:
        """Get prompt for search analysis."""
        return f"""
        Analyze the following FDA data search results for {query_type}: "{query}"
        
        Data Summary:
        {json.dumps(data_summary, indent=2)}
        
        Please provide a comprehensive analysis including:
        1. Executive Summary
        2. Key Findings
        3. Risk Assessment
        4. Regulatory Status
        5. Recommendations
        
        Format your response as a structured JSON with the following fields:
        - summary: Executive summary
        - key_findings: List of key findings
        - risk_level: Overall risk level (LOW/MEDIUM/HIGH/CRITICAL)
        - regulatory_status: Current regulatory status
        - recommendations: List of recommendations
        - confidence_score: Confidence in analysis (0-1)
        """
    
    def get_device_analysis_prompt(self, device_name: str, device_summary: Dict[str, Any]) -> str:
        """Get prompt for device analysis."""
        return f"""
        Analyze comprehensive FDA data for device: "{device_name}"
        
        Device Data Summary:
        {json.dumps(device_summary, indent=2)}
        
        Please provide detailed device analysis including:
        1. Device Overview
        2. Safety Profile
        3. Regulatory History
        4. Market Performance
        5. Risk Assessment
        6. Recommendations
        
        Focus on regulatory compliance, safety trends, and market insights.
        """
    
    def get_risk_assessment_prompt(self, context: str, risk_factors: Dict[str, Any]) -> str:
        """Get prompt for risk assessment."""
        return f"""
        Generate a comprehensive risk assessment for: "{context}"
        
        Risk Factors Data:
        {json.dumps(risk_factors, indent=2)}
        
        Please provide:
        1. Overall Risk Score (0-10)
        2. Risk Factors (list)
        3. Severity Level (LOW/MEDIUM/HIGH/CRITICAL)
        4. Confidence Score (0-1)
        5. Recommendations (list)
        
        Consider FDA regulatory context and medical device safety standards.
        """
    
    def get_timeline_prompt(self, context: str, events: List[Dict[str, Any]]) -> str:
        """Get prompt for timeline analysis."""
        return f"""
        Create a regulatory timeline for: "{context}"
        
        Timeline Events:
        {json.dumps(events, indent=2, default=str)}
        
        Please provide:
        1. Chronological events list
        2. Key milestones
        3. Regulatory pathway
        4. Approval status
        5. Timeline analysis
        
        Focus on regulatory milestones and compliance history.
        """


class BaseAIClient:
    """Base class for AI clients."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    async def generate_analysis(self, prompt: str) -> str:
        """Generate AI analysis from prompt."""
        raise NotImplementedError


class OpenAIClient(BaseAIClient):
    """OpenAI client for AI analysis."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            import openai
            self.client = openai.OpenAI(api_key=config["api_key"])
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")
    
    async def generate_analysis(self, prompt: str) -> str:
        """Generate analysis using OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model=self.config["model"],
                messages=[
                    {"role": "system", "content": "You are an FDA regulatory intelligence expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config["temperature"],
                max_tokens=self.config["max_tokens"]
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenAI analysis failed: {e}")
            return f"Analysis failed: {str(e)}"


class OpenRouterClient(BaseAIClient):
    """OpenRouter client for AI analysis."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            import openai
            self.client = openai.OpenAI(
                base_url=config["base_url"] or "https://openrouter.ai/api/v1",
                api_key=config["api_key"]
            )
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")
    
    async def generate_analysis(self, prompt: str) -> str:
        """Generate analysis using OpenRouter."""
        try:
            response = self.client.chat.completions.create(
                model=self.config["model"],
                messages=[
                    {"role": "system", "content": "You are an FDA regulatory intelligence expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config["temperature"],
                max_tokens=self.config["max_tokens"]
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenRouter analysis failed: {e}")
            return f"Analysis failed: {str(e)}"


class AnthropicClient(BaseAIClient):
    """Anthropic client for AI analysis."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=config["api_key"])
        except ImportError:
            raise ImportError("Anthropic package not installed. Install with: pip install anthropic")
    
    async def generate_analysis(self, prompt: str) -> str:
        """Generate analysis using Anthropic."""
        try:
            response = self.client.messages.create(
                model=self.config["model"],
                max_tokens=self.config["max_tokens"],
                temperature=self.config["temperature"],
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            self.logger.error(f"Anthropic analysis failed: {e}")
            return f"Analysis failed: {str(e)}"