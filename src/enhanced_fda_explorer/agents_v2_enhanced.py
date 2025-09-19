"""
Enhanced Events Search with Three Analysis Approaches
"""

import re
import statistics
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Dict, List, Any, Optional
import logging
import requests

logger = logging.getLogger(__name__)


class EnhancedEventsAnalyzer:
    """Enhanced analyzer for FDA events with multiple analysis approaches"""
    
    def __init__(self, fda_api_key: Optional[str] = None):
        self.fda_api_key = fda_api_key
        self.base_url = "https://api.fda.gov/device/event.json"
    
    async def analyze_events_comprehensive(self, device_name: str, parameters: Dict) -> Dict:
        """Comprehensive event analysis using three approaches"""
        
        # Determine search type and build query
        search_type = parameters.get("search_type", "device")
        search_query = self._build_search_query(device_name, parameters, search_type)
        
        # Approach 1: Use FDA's aggregation API for counts
        logger.info(f"Step 1: Getting aggregate counts for {device_name}")
        aggregate_data = await self._get_aggregate_counts(search_query)
        
        # Approach 2: Strategic sampling
        logger.info(f"Step 2: Fetching strategic samples for {device_name}")
        samples = await self._fetch_strategic_samples(search_query)
        
        # Approach 3: Deep analysis on samples
        logger.info(f"Step 3: Performing deep analysis on samples")
        analysis_results = self._perform_deep_analysis(samples)
        
        # Combine all results
        return {
            "total": aggregate_data["total_events"],
            "aggregate_data": aggregate_data,
            "samples": samples,
            "analysis": analysis_results,
            "search_query": search_query
        }
    
    def _build_search_query(self, device_name: str, parameters: Dict, search_type: str) -> str:
        """Build search query based on type"""
        from .fda_query_utils import FDAQueryNormalizer
        
        if search_type == "manufacturer":
            search_fields = FDAQueryNormalizer.get_manufacturer_search_fields("event")
            base_query = FDAQueryNormalizer.build_search_query(
                [device_name] + parameters.get("variants", []),
                search_fields
            )
        else:
            search_strategies = FDAQueryNormalizer.build_enhanced_search_queries(
                device_name, "event", parameters.get("time_range_months")
            )
            base_query = search_strategies[0]["query"] if search_strategies else f"device.generic_name:{device_name}"
        
        # Add time filter
        date_filter = FDAQueryNormalizer.create_date_filter(
            parameters.get("time_range_months", 12)
        )
        
        if date_filter and " AND date_received:" not in base_query:
            return f"({base_query}) AND date_received:{date_filter}"
        
        return base_query
    
    async def _get_aggregate_counts(self, search_query: str) -> Dict:
        """Use FDA's count API to get aggregated statistics"""
        aggregate_data = {
            "total_events": 0,
            "event_types": {},
            "manufacturers": {},
            "device_problems": {},
            "temporal_trends": {}
        }
        
        # Get total count
        params = {
            "search": search_query,
            "limit": 1
        }
        if self.fda_api_key:
            params["api_key"] = self.fda_api_key
        
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            if response.status_code == 200:
                aggregate_data["total_events"] = response.json()["meta"]["results"]["total"]
        except Exception as e:
            logger.error(f"Failed to get total count: {e}")
        
        # Get event type distribution
        count_params = {
            "search": search_query,
            "count": "event_type",
            "limit": 10
        }
        if self.fda_api_key:
            count_params["api_key"] = self.fda_api_key
            
        try:
            response = requests.get(self.base_url, params=count_params, timeout=10)
            if response.status_code == 200:
                results = response.json().get("results", [])
                aggregate_data["event_types"] = {
                    item["term"]: item["count"] for item in results
                }
        except Exception as e:
            logger.error(f"Failed to get event type counts: {e}")
        
        # Get manufacturer distribution
        count_params["count"] = "device.manufacturer_d_name.exact"
        try:
            response = requests.get(self.base_url, params=count_params, timeout=10)
            if response.status_code == 200:
                results = response.json().get("results", [])
                aggregate_data["manufacturers"] = {
                    item["term"]: item["count"] for item in results[:10]
                }
        except Exception as e:
            logger.error(f"Failed to get manufacturer counts: {e}")
        
        # Get temporal distribution (by month)
        count_params["count"] = "date_received"
        count_params["limit"] = 24  # Last 24 months
        try:
            response = requests.get(self.base_url, params=count_params, timeout=10)
            if response.status_code == 200:
                results = response.json().get("results", [])
                # Convert to month-year format
                monthly_counts = defaultdict(int)
                for item in results:
                    date_str = item["time"]
                    try:
                        date = datetime.strptime(date_str, "%Y-%m-%d")
                        month_key = date.strftime("%Y-%m")
                        monthly_counts[month_key] += item["count"]
                    except:
                        pass
                aggregate_data["temporal_trends"] = dict(monthly_counts)
        except Exception as e:
            logger.error(f"Failed to get temporal trends: {e}")
        
        return aggregate_data
    
    async def _fetch_strategic_samples(self, search_query: str) -> Dict[str, List]:
        """Fetch strategic samples for detailed analysis"""
        samples = {
            "recent_deaths": [],
            "recent_injuries": [],
            "recent_malfunctions": [],
            "random_sample": []
        }
        
        # Fetch recent deaths (up to 50)
        death_params = {
            "search": f"({search_query}) AND event_type:Death",
            "limit": 50,
            "sort": "date_received:desc"
        }
        if self.fda_api_key:
            death_params["api_key"] = self.fda_api_key
            
        try:
            response = requests.get(self.base_url, params=death_params, timeout=10)
            if response.status_code == 200:
                samples["recent_deaths"] = response.json().get("results", [])
        except Exception as e:
            logger.error(f"Failed to fetch deaths: {e}")
        
        # Fetch recent injuries (up to 100)
        injury_params = {
            "search": f"({search_query}) AND event_type:Injury",
            "limit": 100,
            "sort": "date_received:desc"
        }
        if self.fda_api_key:
            injury_params["api_key"] = self.fda_api_key
            
        try:
            response = requests.get(self.base_url, params=injury_params, timeout=10)
            if response.status_code == 200:
                samples["recent_injuries"] = response.json().get("results", [])
        except Exception as e:
            logger.error(f"Failed to fetch injuries: {e}")
        
        # Fetch recent malfunctions (up to 100)
        malfunction_params = {
            "search": f"({search_query}) AND event_type:Malfunction",
            "limit": 100,
            "sort": "date_received:desc"
        }
        if self.fda_api_key:
            malfunction_params["api_key"] = self.fda_api_key
            
        try:
            response = requests.get(self.base_url, params=malfunction_params, timeout=10)
            if response.status_code == 200:
                samples["recent_malfunctions"] = response.json().get("results", [])
        except Exception as e:
            logger.error(f"Failed to fetch malfunctions: {e}")
        
        # Get a random sample across all event types (different time periods)
        # Sample from different months to get temporal diversity
        for months_ago in [0, 3, 6, 9]:
            date = datetime.now() - timedelta(days=months_ago * 30)
            date_str = date.strftime("%Y%m%d")
            
            sample_params = {
                "search": f"({search_query}) AND date_received:{date_str}",
                "limit": 25
            }
            if self.fda_api_key:
                sample_params["api_key"] = self.fda_api_key
                
            try:
                response = requests.get(self.base_url, params=sample_params, timeout=10)
                if response.status_code == 200:
                    samples["random_sample"].extend(response.json().get("results", []))
            except Exception as e:
                logger.warning(f"Failed to fetch sample for {date_str}: {e}")
        
        return samples
    
    def _perform_deep_analysis(self, samples: Dict[str, List]) -> Dict:
        """Perform deep analysis on the samples"""
        analysis = {
            "severity_patterns": {},
            "common_problems": {},
            "device_patterns": {},
            "narrative_insights": {},
            "risk_indicators": {},
            "temporal_patterns": {}
        }
        
        # Analyze death events
        if samples["recent_deaths"]:
            death_analysis = self._analyze_serious_events(samples["recent_deaths"], "Death")
            analysis["severity_patterns"]["deaths"] = death_analysis
        
        # Analyze injury events
        if samples["recent_injuries"]:
            injury_analysis = self._analyze_serious_events(samples["recent_injuries"], "Injury")
            analysis["severity_patterns"]["injuries"] = injury_analysis
        
        # Analyze malfunctions for patterns
        if samples["recent_malfunctions"]:
            malfunction_analysis = self._analyze_malfunctions(samples["recent_malfunctions"])
            analysis["common_problems"] = malfunction_analysis
        
        # Device-specific patterns
        all_samples = []
        for sample_list in samples.values():
            all_samples.extend(sample_list)
        
        if all_samples:
            analysis["device_patterns"] = self._analyze_device_patterns(all_samples)
            analysis["narrative_insights"] = self._extract_narrative_patterns(all_samples)
            analysis["temporal_patterns"] = self._analyze_temporal_patterns(all_samples)
        
        # Calculate risk indicators
        analysis["risk_indicators"] = self._calculate_risk_indicators(analysis, samples)
        
        return analysis
    
    def _analyze_serious_events(self, events: List[Dict], event_type: str) -> Dict:
        """Analyze serious events (deaths/injuries) for patterns"""
        analysis = {
            "total": len(events),
            "common_causes": Counter(),
            "device_models": Counter(),
            "patient_problems": Counter(),
            "time_to_event": []
        }
        
        for event in events:
            # Extract device info
            device = event.get("device", [{}])[0]
            model = device.get("model_number", "Unknown")
            analysis["device_models"][model] += 1
            
            # Extract patient problems
            patient_data = event.get("patient", [])
            if patient_data:
                for patient in patient_data:
                    if isinstance(patient, dict):
                        for problem_code in patient.get("patient_problems", []):
                            if isinstance(problem_code, dict):
                                problem_text = problem_code.get("text", "Unknown")
                            else:
                                problem_text = str(problem_code)
                            analysis["patient_problems"][problem_text] += 1
            
            # Extract event description patterns
            description = event.get("event_description", "")
            if description:
                # Look for common patterns in descriptions
                patterns = self._extract_description_patterns(description)
                for pattern in patterns:
                    analysis["common_causes"][pattern] += 1
            
            # Calculate time from implant to event (if available)
            if device.get("date_of_implant") and event.get("date_of_event"):
                try:
                    implant_date = datetime.strptime(device["date_of_implant"], "%Y-%m-%d")
                    event_date = datetime.strptime(event["date_of_event"], "%Y-%m-%d")
                    days_to_event = (event_date - implant_date).days
                    if days_to_event >= 0:
                        analysis["time_to_event"].append(days_to_event)
                except:
                    pass
        
        # Calculate statistics for time to event
        if analysis["time_to_event"]:
            analysis["time_to_event_stats"] = {
                "mean_days": statistics.mean(analysis["time_to_event"]),
                "median_days": statistics.median(analysis["time_to_event"]),
                "min_days": min(analysis["time_to_event"]),
                "max_days": max(analysis["time_to_event"])
            }
        
        # Convert counters to sorted lists
        analysis["common_causes"] = analysis["common_causes"].most_common(10)
        analysis["device_models"] = analysis["device_models"].most_common(10)
        analysis["patient_problems"] = analysis["patient_problems"].most_common(10)
        
        return analysis
    
    def _analyze_malfunctions(self, events: List[Dict]) -> Dict:
        """Analyze malfunction patterns"""
        device_problems = Counter()
        problem_codes = Counter()
        
        for event in events:
            # Extract device problems
            for problem in event.get("device", [{}])[0].get("device_problems", []):
                problem_text = problem.get("text", "Unknown")
                problem_code = problem.get("code", "Unknown")
                device_problems[problem_text] += 1
                problem_codes[problem_code] += 1
        
        return {
            "top_device_problems": device_problems.most_common(15),
            "problem_codes": problem_codes.most_common(10)
        }
    
    def _analyze_device_patterns(self, events: List[Dict]) -> Dict:
        """Analyze patterns across device models and manufacturers"""
        patterns = {
            "models_by_events": Counter(),
            "lot_numbers": Counter(),
            "catalog_numbers": Counter()
        }
        
        for event in events:
            device = event.get("device", [{}])[0]
            
            model = device.get("model_number", "")
            if model:
                patterns["models_by_events"][model] += 1
            
            lot = device.get("lot_number", "")
            if lot:
                patterns["lot_numbers"][lot] += 1
                
            catalog = device.get("catalog_number", "")
            if catalog:
                patterns["catalog_numbers"][catalog] += 1
        
        # Convert to sorted lists
        patterns["models_by_events"] = patterns["models_by_events"].most_common(20)
        patterns["lot_numbers"] = patterns["lot_numbers"].most_common(10)
        patterns["catalog_numbers"] = patterns["catalog_numbers"].most_common(10)
        
        return patterns
    
    def _extract_description_patterns(self, description: str) -> List[str]:
        """Extract common patterns from event descriptions"""
        patterns = []
        description_lower = description.lower()
        
        # Common failure modes
        failure_patterns = [
            "battery", "software", "alarm", "failure", "malfunction",
            "error", "defect", "break", "crack", "leak", "disconnect",
            "infection", "migration", "dislodg", "fracture"
        ]
        
        for pattern in failure_patterns:
            if pattern in description_lower:
                patterns.append(pattern)
        
        # Extract specific error codes or messages
        error_matches = re.findall(r'error\s+(?:code\s+)?([A-Z0-9]+)', description, re.I)
        for match in error_matches:
            patterns.append(f"error_{match}")
        
        return patterns
    
    def _extract_narrative_patterns(self, events: List[Dict]) -> Dict:
        """Extract insights from narrative text"""
        insights = {
            "common_keywords": Counter(),
            "error_codes": Counter(),
            "failure_modes": []
        }
        
        for event in events[:100]:  # Analyze first 100 for performance
            description = event.get("event_description", "")
            if not description:
                continue
                
            # Extract keywords
            words = re.findall(r'\b\w{4,}\b', description.lower())
            for word in words:
                if word not in ['device', 'patient', 'event', 'reported', 'medical']:
                    insights["common_keywords"][word] += 1
            
            # Extract error codes
            error_codes = re.findall(r'\b(?:error|code|alarm)\s*[:#]?\s*([A-Z0-9]{2,})\b', description, re.I)
            for code in error_codes:
                insights["error_codes"][code.upper()] += 1
        
        insights["common_keywords"] = insights["common_keywords"].most_common(20)
        insights["error_codes"] = insights["error_codes"].most_common(10)
        
        return insights
    
    def _analyze_temporal_patterns(self, events: List[Dict]) -> Dict:
        """Analyze temporal patterns in events"""
        patterns = {
            "events_by_month": defaultdict(int),
            "events_by_day_of_week": defaultdict(int),
            "reporting_delay": []
        }
        
        for event in events:
            # Events by month
            date_received = event.get("date_received", "")
            if date_received:
                try:
                    date = datetime.strptime(date_received[:10], "%Y-%m-%d")
                    month_key = date.strftime("%Y-%m")
                    patterns["events_by_month"][month_key] += 1
                    patterns["events_by_day_of_week"][date.strftime("%A")] += 1
                except:
                    pass
            
            # Reporting delay
            event_date = event.get("date_of_event", "")
            if event_date and date_received:
                try:
                    event_dt = datetime.strptime(event_date, "%Y-%m-%d")
                    received_dt = datetime.strptime(date_received[:10], "%Y-%m-%d")
                    delay_days = (received_dt - event_dt).days
                    if 0 <= delay_days <= 365:  # Reasonable delays only
                        patterns["reporting_delay"].append(delay_days)
                except:
                    pass
        
        # Calculate reporting delay statistics
        if patterns["reporting_delay"]:
            patterns["reporting_delay_stats"] = {
                "mean_days": statistics.mean(patterns["reporting_delay"]),
                "median_days": statistics.median(patterns["reporting_delay"]),
                "percentile_90": sorted(patterns["reporting_delay"])[int(len(patterns["reporting_delay"]) * 0.9)]
            }
        
        patterns["events_by_month"] = dict(sorted(patterns["events_by_month"].items()))
        patterns["events_by_day_of_week"] = dict(patterns["events_by_day_of_week"])
        
        return patterns
    
    def _calculate_risk_indicators(self, analysis: Dict, samples: Dict) -> Dict:
        """Calculate risk indicators based on analysis"""
        total_samples = sum(len(v) for v in samples.values())
        total_serious = len(samples["recent_deaths"]) + len(samples["recent_injuries"])
        
        indicators = {
            "severity_ratio": total_serious / total_samples if total_samples > 0 else 0,
            "death_rate": len(samples["recent_deaths"]) / total_samples if total_samples > 0 else 0,
            "trending_problems": [],
            "high_risk_models": [],
            "quality_indicators": {}
        }
        
        # Identify trending problems
        if "temporal_patterns" in analysis:
            months = sorted(analysis["temporal_patterns"].get("events_by_month", {}).items())
            if len(months) >= 3:
                # Check if last 3 months show increasing trend
                recent_counts = [count for month, count in months[-3:]]
                if recent_counts == sorted(recent_counts):
                    indicators["trending_problems"].append("Increasing event trend in recent months")
        
        # Identify high-risk models
        if "device_patterns" in analysis:
            for model, count in analysis["device_patterns"].get("models_by_events", [])[:5]:
                if count > 10:
                    indicators["high_risk_models"].append({"model": model, "events": count})
        
        # Quality indicators
        if "temporal_patterns" in analysis and "reporting_delay_stats" in analysis["temporal_patterns"]:
            delay_stats = analysis["temporal_patterns"]["reporting_delay_stats"]
            indicators["quality_indicators"]["mean_reporting_delay"] = delay_stats.get("mean_days", 0)
            indicators["quality_indicators"]["reporting_compliance"] = "Good" if delay_stats.get("median_days", 0) < 30 else "Needs Improvement"
        
        return indicators


# Example integration with existing EventsSpecialistAgent
async def enhanced_search_events(self, device_name: str, parameters: Dict) -> Dict:
    """Enhanced search with comprehensive analysis"""
    analyzer = EnhancedEventsAnalyzer(self.fda_api_key)
    
    # Get comprehensive analysis
    analysis_results = await analyzer.analyze_events_comprehensive(device_name, parameters)
    
    # Format for existing system compatibility
    return {
        "total": analysis_results["aggregate_data"]["total_events"],
        "analyzed_count": sum(len(v) for v in analysis_results["samples"].values()),
        "event_types": analysis_results["aggregate_data"]["event_types"],
        "manufacturers": list(analysis_results["aggregate_data"]["manufacturers"].items()),
        "serious_events": [
            {
                "type": event.get("event_type"),
                "date": event.get("date_of_event", ""),
                "description": event.get("event_description", "")[:200],
                "manufacturer": event.get("device", [{}])[0].get("manufacturer_d_name", "Unknown"),
                "mdr_report_key": event.get("mdr_report_key", ""),
                "report_number": event.get("report_number", "")
            }
            for event in (analysis_results["samples"]["recent_deaths"][:5] + 
                         analysis_results["samples"]["recent_injuries"][:5])
        ],
        "raw_events": analysis_results["samples"]["recent_deaths"][:10] + 
                     analysis_results["samples"]["recent_injuries"][:40],
        "enhanced_analysis": analysis_results["analysis"],
        "aggregate_data": analysis_results["aggregate_data"],
        "search_strategy": "comprehensive_analysis"
    }