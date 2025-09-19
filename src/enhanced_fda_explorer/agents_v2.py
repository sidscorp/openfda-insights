"""
Advanced Multi-Agent System for FDA Device Intelligence
"""

import os
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Callable
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from enum import Enum
import logging
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import re
import statistics

import requests
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from .fda_query_utils import FDAQueryNormalizer
from .citation_models import FDACitation, CitedFinding, CitationTracker

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Enumeration of agent roles"""
    ORCHESTRATOR = "orchestrator"
    EVENTS = "events_specialist"
    RECALLS = "recalls_specialist"
    CLEARANCES = "clearances_specialist"
    CLASSIFICATIONS = "classifications_specialist"
    UDI = "udi_specialist"
    PMA = "pma_specialist"
    SYNTHESIZER = "synthesizer"


class TaskType(Enum):
    """Types of tasks agents can handle"""
    SEARCH = "search"
    ANALYZE = "analyze"
    COMPARE = "compare"
    TREND = "trend"
    REGULATORY_STATUS = "regulatory_status"
    MANUFACTURER_PROFILE = "manufacturer_profile"


@dataclass
class AgentTask:
    """Represents a task for an agent"""
    id: str
    type: TaskType
    query: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    assigned_to: Optional[AgentRole] = None
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class AgentMessage:
    """Message between agents"""
    from_agent: AgentRole
    to_agent: AgentRole
    task: Optional[AgentTask] = None
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class QueryIntent(BaseModel):
    """Structured query intent from orchestrator"""
    primary_intent: str = Field(description="Main intent: search, analyze, compare, trend, risk, regulatory, manufacturer")
    device_names: List[str] = Field(description="List of device names mentioned")
    time_range: Optional[str] = Field(description="Time range if specified")
    specific_concerns: List[str] = Field(description="Specific concerns or focus areas")
    required_agents: List[str] = Field(description="Which specialist agents are needed")
    
    
class AgentResponse(BaseModel):
    """Structured response from specialist agents"""
    agent_role: str = Field(description="Role of the responding agent")
    data_points: int = Field(description="Number of data points found")
    key_findings: List[str] = Field(description="Key findings from the data")
    data_citations: List[Dict[str, str]] = Field(description="FDA record citations for findings")
    recommendations: List[str] = Field(description="Agent-specific recommendations")
    raw_data: Optional[Dict] = Field(description="Raw data for further analysis", default=None)


class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, role: AgentRole, llm: ChatOpenAI):
        self.role = role
        self.llm = llm
        self.system_prompt = self._get_system_prompt()
        
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Get the system prompt for this agent"""
        pass
        
    @abstractmethod
    async def process_task(self, task: AgentTask) -> AgentTask:
        """Process a task and return the result"""
        pass
        
    def _create_messages(self, user_content: str) -> List:
        """Create messages for LLM"""
        return [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_content)
        ]


class OrchestratorAgent(BaseAgent):
    """Orchestrator agent that understands intent and delegates tasks"""
    
    def __init__(self, llm: ChatOpenAI):
        super().__init__(AgentRole.ORCHESTRATOR, llm)
        self.intent_parser = JsonOutputParser(pydantic_object=QueryIntent)
        
    def _get_system_prompt(self) -> str:
        return """You are the orchestrator agent for an FDA medical device intelligence system.
        Your role is to:
        1. Understand the user's query intent
        2. Identify which devices are being asked about
        3. Determine which specialist agents need to be involved
        4. Create a plan for fulfilling the request
        
        Available specialist agents:
        - events_specialist: Handles adverse event reports, injuries, deaths, malfunctions
        - recalls_specialist: Handles product recalls, safety alerts, recall classifications
        - clearances_specialist: Handles 510(k) clearances, substantial equivalence determinations
        - classifications_specialist: Handles device classifications (Class I, II, III), regulatory requirements
        - udi_specialist: Handles Unique Device Identifier data, labeler info, MRI safety
        - pma_specialist: Handles Premarket Approval data, clinical trials, supplements
        
        Analyze the query and output a JSON with:
        - primary_intent: main goal (search/analyze/compare/trend/risk/regulatory/manufacturer)
        - device_names: list of devices mentioned
        - time_range: if a time period is mentioned
        - specific_concerns: any specific issues or areas of focus
        - required_agents: which agents should be activated
        """
        
    async def process_task(self, task: AgentTask) -> AgentTask:
        """Analyze query and create execution plan"""
        try:
            messages = self._create_messages(
                f"Analyze this query and create an execution plan:\n{task.query}"
            )
            
            response = await self.llm.ainvoke(messages)
            
            # Parse the response - it might already be a dict or might be a Pydantic object
            try:
                intent = self.intent_parser.parse(response.content)
                intent_dict = intent.dict() if hasattr(intent, 'dict') else intent
            except Exception as e:
                # If parsing fails, try to extract JSON from the response
                import json
                intent_dict = json.loads(response.content)
                intent = QueryIntent(**intent_dict)
            
            task.result = {
                "intent": intent_dict,
                "execution_plan": self._create_execution_plan(intent)
            }
            task.status = "completed"
            
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            task.error = str(e)
            task.status = "failed"
            
        return task
        
    def _create_execution_plan(self, intent) -> List[AgentTask]:
        """Create tasks for specialist agents based on intent"""
        tasks = []
        task_id = 1
        
        # Handle both QueryIntent object and dict
        if isinstance(intent, dict):
            required_agents = intent.get('required_agents', [])
            device_names = intent.get('device_names', [])
            time_range = intent.get('time_range')
            specific_concerns = intent.get('specific_concerns', [])
        else:
            required_agents = intent.required_agents
            device_names = intent.device_names
            time_range = intent.time_range
            specific_concerns = intent.specific_concerns
        
        for agent_name in required_agents:
            for device in device_names:
                task = AgentTask(
                    id=f"task_{task_id}",
                    type=TaskType.SEARCH,
                    query=device,
                    parameters={
                        "time_range": time_range,
                        "concerns": specific_concerns
                    },
                    assigned_to=AgentRole(agent_name)
                )
                tasks.append(task)
                task_id += 1
                
        return tasks


class EventsSpecialistAgent(BaseAgent):
    """Specialist for adverse events data"""
    
    def __init__(self, llm: ChatOpenAI, fda_api_key: Optional[str] = None):
        super().__init__(AgentRole.EVENTS, llm)
        self.fda_api_key = fda_api_key
        self.response_parser = JsonOutputParser(pydantic_object=AgentResponse)
        
    def _get_system_prompt(self) -> str:
        return """You are a specialist agent for FDA adverse event reports.
        Your expertise includes:
        - Analyzing device adverse events (deaths, injuries, malfunctions)
        - Identifying patterns in event data
        - Assessing severity and frequency of events
        - Understanding patient outcomes and device problems
        
        When analyzing data:
        1. Focus on event types and their frequencies
        2. Identify serious events (deaths, injuries)
        3. Look for patterns in manufacturers or device models
        4. Assess temporal trends
        5. Cite specific FDA records for key findings
        
        Output your analysis as JSON with key_findings, data_citations, and recommendations.
        Each finding must reference specific FDA record IDs.
        """
        
    async def process_task(self, task: AgentTask) -> AgentTask:
        """Search and analyze adverse events"""
        try:
            # Search FDA API
            events_data = await self._search_events(task.query, task.parameters)
            
            # Create citations for serious events
            citation_tracker = CitationTracker()
            event_citations = []
            
            for event in events_data['serious_events'][:5]:  # Top 5 serious events
                if event.get('mdr_report_key') or event.get('report_number'):
                    citation = FDACitation(
                        record_id=event.get('mdr_report_key', event.get('report_number', '')),
                        record_type="adverse_event",
                        date=event.get('date', ''),
                        excerpt=f"{event.get('type', '')} - {event.get('manufacturer', '')}"
                    )
                    event_citations.append(citation.dict())
            
            # Analyze with LLM - include enhanced analysis if available
            if 'enhanced_analysis' in events_data:
                analysis_prompt = f"""
                Analyze these FDA adverse event data for {task.query}:
                
                Total events: {events_data['total']}
                Analyzed: {events_data['analyzed_count']}
                Event types: {json.dumps(events_data['event_types'], indent=2)}
                
                Key Analysis Findings:
                - Severity patterns: {json.dumps(events_data['enhanced_analysis'].get('severity_patterns', {}), indent=2)}
                - Common problems: {json.dumps(events_data['enhanced_analysis'].get('common_problems', {}), indent=2)}
                - Risk indicators: {json.dumps(events_data['enhanced_analysis'].get('risk_indicators', {}), indent=2)}
                - Temporal trends: Last 12 months show {events_data['aggregate_data'].get('temporal_trends', {})}
                
                Recent serious events: {json.dumps(events_data['serious_events'][:5], indent=2)}
                
                Provide insights focusing on:
                1. Most critical safety concerns
                2. Trending issues or patterns
                3. High-risk device models or lots
                4. Actionable recommendations
                """
            else:
                analysis_prompt = f"""
                Analyze these FDA adverse event data for {task.query}:
                
                Total events: {events_data['total']}
                Event types breakdown: {json.dumps(events_data['event_types'], indent=2)}
                Top manufacturers: {json.dumps(events_data['manufacturers'][:5], indent=2)}
                Recent serious events: {json.dumps(events_data['serious_events'][:10], indent=2)}
                
                Provide analysis focusing on factual patterns observed.
                Remember to cite specific FDA records when making claims.
                """
            
            messages = self._create_messages(analysis_prompt)
            response = await self.llm.ainvoke(messages)
            
            try:
                agent_response = self.response_parser.parse(response.content)
                
                # Handle both dict and Pydantic object responses
                if hasattr(agent_response, 'dict'):
                    result_dict = agent_response.dict()
                else:
                    result_dict = agent_response
                    
                # Ensure data_points is set correctly (actual analyzed count, not total)
                analyzed_count = len(events_data.get('raw_events', []))
                result_dict['data_points'] = analyzed_count
                
            except Exception as parse_error:
                logger.warning(f"Failed to parse LLM response, using fallback: {parse_error}")
                # Fallback: Create basic response structure
                analyzed_count = len(events_data.get('raw_events', []))
                result_dict = {
                    "agent_role": self.role.value,
                    "data_points": analyzed_count,
                    "key_findings": [
                        f"Found {events_data['total']} total events, analyzed {analyzed_count} for {task.query}",
                        f"Event types: {', '.join(list(events_data['event_types'].keys())[:3])}",
                        f"Top manufacturer: {events_data['manufacturers'][0][0] if events_data['manufacturers'] else 'Unknown'}"
                    ],
                    "data_citations": event_citations,
                    "recommendations": ["Review detailed event data for comprehensive analysis"]
                }
                
            result_dict['raw_data'] = events_data
            task.result = result_dict
            task.status = "completed"
            
        except Exception as e:
            logger.error(f"Events specialist error: {e}")
            task.error = str(e)
            task.status = "failed"
            
        return task
        
    async def _search_events(self, device_name: str, parameters: Dict) -> Dict:
        """Search FDA events API with comprehensive analysis"""
        # Use enhanced analyzer if available
        if parameters.get("use_enhanced_analysis", True):
            try:
                from .agents_v2_enhanced import EnhancedEventsAnalyzer
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
            except Exception as e:
                logger.warning(f"Enhanced analysis failed, falling back to simple analysis: {e}")
                # Fall back to simple analysis
                return await self._search_events_simple(device_name, parameters)
        else:
            return await self._search_events_simple(device_name, parameters)
    
    async def _search_events_simple(self, device_name: str, parameters: Dict) -> Dict:
        """Simple event search (fallback)"""
        url = "https://api.fda.gov/device/event.json"
        
        # Determine search type and fields
        search_type = parameters.get("search_type", "device")
        
        if search_type == "manufacturer":
            # Use manufacturer-specific search fields
            search_fields = FDAQueryNormalizer.get_manufacturer_search_fields("event")
            # Build custom search query for manufacturer
            date_filter = FDAQueryNormalizer.create_date_filter(
                parameters.get("time_range_months", 12)
            )
            base_query = FDAQueryNormalizer.build_search_query(
                [device_name] + parameters.get("variants", []),
                search_fields
            )
            search_query = f"({base_query})"
            if date_filter:
                search_query += f" AND date_received:{date_filter}"
            
            search_strategies = [{
                "strategy": "manufacturer_search",
                "query": search_query,
                "description": f"Manufacturer search for '{device_name}'"
            }]
        else:
            # Use standard device search
            search_strategies = FDAQueryNormalizer.build_enhanced_search_queries(
                device_name, "event", parameters.get("time_range_months")
            )
        
        # Simple fetch without pagination
        all_events = []
        total_found = 0
        successful_strategy = None
        
        # Try each search strategy
        for strategy in search_strategies:
            params = {
                "search": strategy["query"],
                "limit": 100,
                "sort": "date_received:desc"
            }
                
            if self.fda_api_key:
                params["api_key"] = self.fda_api_key
                
            try:
                logger.info(f"Simple fetch using strategy: {strategy['strategy']}")
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    events = data.get("results", [])
                    
                    if events:
                        all_events = events
                        total_found = data.get("meta", {}).get("results", {}).get("total", 0)
                        successful_strategy = strategy['strategy']
                        logger.info(f"Found {total_found} total events, fetched {len(events)}")
                        break
                        
            except Exception as e:
                logger.warning(f"Strategy {strategy['strategy']} failed: {e}")
                continue
        
        
        # Process results
        if not all_events:
            logger.warning(f"No events found for device: {device_name}")
            return {
                "total": 0,
                "event_types": {},
                "manufacturers": [],
                "serious_events": [],
                "raw_events": [],
                "search_strategy": None
            }
        
        # Analyze event types
        event_types = Counter()
        manufacturers = Counter()
        serious_events = []
        
        for event in all_events:
            event_type = event.get("event_type", "Unknown")
            event_types[event_type] += 1
            
            device = event.get("device", [{}])[0]
            mfr = device.get("manufacturer_d_name", "Unknown")
            manufacturers[mfr] += 1
            
            if event_type in ["Death", "Injury"]:
                serious_events.append({
                    "type": event_type,
                    "date": event.get("date_of_event", ""),
                    "description": event.get("event_description", "")[:200],
                    "manufacturer": mfr,
                    "mdr_report_key": event.get("mdr_report_key", ""),  # Add FDA record ID
                    "report_number": event.get("report_number", "")
                })
                
        return {
            "total": total_found,
            "analyzed_count": len(all_events),
            "event_types": dict(event_types),
            "manufacturers": manufacturers.most_common(),
            "serious_events": serious_events,
            "raw_events": all_events,  # Keep all fetched events for analysis
            "search_strategy": successful_strategy
        }


class RecallsSpecialistAgent(BaseAgent):
    """Specialist for recall data"""
    
    def __init__(self, llm: ChatOpenAI, fda_api_key: Optional[str] = None):
        super().__init__(AgentRole.RECALLS, llm)
        self.fda_api_key = fda_api_key
        self.response_parser = JsonOutputParser(pydantic_object=AgentResponse)
        
    def _get_system_prompt(self) -> str:
        return """You are a specialist agent for FDA device recalls.
        Your expertise includes:
        - Analyzing recall classifications (Class I, II, III)
        - Understanding recall reasons and root causes
        - Assessing recall scope and impact
        - Tracking recall effectiveness
        
        Focus on:
        1. Recall severity and classification
        2. Reasons for recalls
        3. Number of units affected
        4. Recall status and effectiveness
        5. Patterns in recall causes
        
        Output your analysis as JSON with key_findings, data_citations, and recommendations.
        Each finding must reference specific FDA recall numbers.
        """
        
    async def process_task(self, task: AgentTask) -> AgentTask:
        """Search and analyze recalls"""
        try:
            recalls_data = await self._search_recalls(task.query, task.parameters)
            
            # Create citations for recalls
            recall_citations = []
            for recall in recalls_data['recent_recalls'][:5]:  # Top 5 recalls
                if recall.get('recall_number'):
                    citation = FDACitation(
                        record_id=recall.get('recall_number', ''),
                        record_type="recall",
                        date=recall.get('date', ''),
                        excerpt=f"Class {recall.get('classification', '')} - {recall.get('reason', '')[:50]}"
                    )
                    recall_citations.append(citation.dict())
            
            analysis_prompt = f"""
            Analyze these FDA recall data for {task.query}:
            
            Total recalls: {recalls_data['total']}
            By classification: {json.dumps(recalls_data['classifications'], indent=2)}
            Recent recalls: {json.dumps(recalls_data['recent_recalls'][:5], indent=2)}
            Common reasons: {json.dumps(recalls_data['recall_reasons'][:5], indent=2)}
            
            Provide factual assessment of recall patterns.
            Remember to reference specific FDA recall numbers.
            """
            
            messages = self._create_messages(analysis_prompt)
            response = await self.llm.ainvoke(messages)
            
            try:
                agent_response = self.response_parser.parse(response.content)
                
                # Handle both dict and Pydantic object responses
                if hasattr(agent_response, 'dict'):
                    result_dict = agent_response.dict()
                else:
                    result_dict = agent_response
                    
                # Ensure data_points is set correctly
                result_dict['data_points'] = recalls_data['total']
                
            except Exception as parse_error:
                logger.warning(f"Failed to parse recall LLM response, using fallback: {parse_error}")
                # Fallback: Create basic response structure
                result_dict = {
                    "agent_role": self.role.value,
                    "data_points": recalls_data['total'],
                    "key_findings": [
                        f"Found {recalls_data['total']} total recalls for {task.query}",
                        f"Classifications: {', '.join([f'{k}:{v}' for k,v in list(recalls_data['classifications'].items())[:3]])}",
                        f"Most recent recall: {recalls_data['recent_recalls'][0]['date'] if recalls_data['recent_recalls'] else 'None'}"
                    ],
                    "data_citations": recall_citations,
                    "recommendations": ["Review recall details for safety implications"]
                }
                
            result_dict['raw_data'] = recalls_data
            task.result = result_dict
            task.status = "completed"
            
        except Exception as e:
            logger.error(f"Recalls specialist error: {e}")
            task.error = str(e)
            task.status = "failed"
            
        return task
        
    async def _search_recalls(self, device_name: str, parameters: Dict) -> Dict:
        """Search FDA recalls API with pagination"""
        url = "https://api.fda.gov/device/recall.json"
        
        # Determine search type and fields
        search_type = parameters.get("search_type", "device")
        
        if search_type == "manufacturer":
            # Use manufacturer-specific search fields
            search_fields = FDAQueryNormalizer.get_manufacturer_search_fields("recall")
            # Build custom search query for manufacturer
            date_filter = FDAQueryNormalizer.create_date_filter(
                parameters.get("time_range_months", 12)
            )
            base_query = FDAQueryNormalizer.build_search_query(
                [device_name] + parameters.get("variants", []),
                search_fields
            )
            search_query = f"({base_query})"
            if date_filter:
                search_query += f" AND event_date_initiated:{date_filter}"
            
            search_strategies = [{
                "strategy": "manufacturer_search",
                "query": search_query,
                "description": f"Manufacturer search for '{device_name}'"
            }]
        else:
            # Use standard device search
            search_strategies = FDAQueryNormalizer.build_enhanced_search_queries(
                device_name, "recall", parameters.get("time_range_months")
            )
        
        all_recalls = []
        total_found = 0
        successful_strategy = None
        max_records = 500  # Reasonable limit
        
        # Try each search strategy until we get results
        for strategy in search_strategies:
            skip = 0
            batch_size = 100
            strategy_recalls = []
            
            while len(strategy_recalls) < max_records:
                params = {
                    "search": strategy["query"],
                    "limit": batch_size,
                    "skip": skip,
                    "sort": "event_date_initiated:desc"
                }
                
                if self.fda_api_key:
                    params["api_key"] = self.fda_api_key
                    
                try:
                    logger.info(f"Recalls: Fetching batch skip={skip}, strategy={strategy['strategy']}")
                    response = requests.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        recalls = data.get("results", [])
                        
                        if not recalls:
                            break  # No more results
                            
                        strategy_recalls.extend(recalls)
                        
                        if not total_found:
                            total_found = data.get("meta", {}).get("results", {}).get("total", 0)
                            successful_strategy = strategy['strategy']
                            logger.info(f"Found {total_found} total recalls with {successful_strategy} strategy")
                        
                        # Check if we've fetched all available
                        if len(recalls) < batch_size or len(strategy_recalls) >= total_found:
                            break
                            
                        skip += batch_size
                        
                    else:
                        logger.warning(f"Recall API returned status {response.status_code}")
                        break
                        
                except Exception as e:
                    logger.warning(f"Recall batch fetch failed: {e}")
                    break
            
            if strategy_recalls:
                all_recalls = strategy_recalls[:max_records]
                logger.info(f"Fetched {len(all_recalls)} recalls out of {total_found} total")
                break
        
        # Process results
        if not all_recalls:
            logger.warning(f"No recalls found for device: {device_name}")
            return {
                "total": 0,
                "classifications": {},
                "recall_reasons": [],
                "recent_recalls": [],
                "raw_recalls": [],
                "search_strategy": None
            }
        
        # Analyze recalls
        classifications = Counter()
        recall_reasons = Counter()
        recent_recalls = []
        
        for recall in all_recalls:
            # Get device class from openfda section
            openfda = recall.get("openfda", {})
            device_class = openfda.get("device_class", "Unknown")
            # Convert numeric class to Roman numerals
            class_map = {"1": "I", "2": "II", "3": "III"}
            classification = f"Class {class_map.get(str(device_class), str(device_class))}"
            classifications[classification] += 1
            
            reason = recall.get("reason_for_recall", "")[:100]
            if reason:
                recall_reasons[reason] += 1
                
            recent_recalls.append({
                "date": recall.get("event_date_initiated", ""),
                "classification": classification,
                "reason": reason,
                "status": recall.get("recall_status", ""),
                "distribution": recall.get("distribution_pattern", ""),
                "recall_number": recall.get("product_res_number", recall.get("res_event_number", "")),  # FDA recall ID
                "firm_fei_number": recall.get("firm_fei_number", "")
            })
            
        return {
            "total": total_found,
            "analyzed_count": len(all_recalls),
            "classifications": dict(classifications),
            "recall_reasons": recall_reasons.most_common(),
            "recent_recalls": recent_recalls,
            "raw_recalls": all_recalls,  # Keep all fetched recalls
            "search_strategy": successful_strategy
        }


class SynthesizerAgent(BaseAgent):
    """Agent that synthesizes results from all specialist agents"""
    
    def __init__(self, llm: ChatOpenAI):
        super().__init__(AgentRole.SYNTHESIZER, llm)
        
    def _get_system_prompt(self) -> str:
        return """You are the synthesis agent responsible for combining insights from multiple specialist agents.
        Your role is to:
        1. Integrate findings from different data sources
        2. Identify cross-cutting patterns and correlations
        3. Provide factual summaries backed by FDA data
        4. Generate evidence-based recommendations
        5. Create an executive summary
        
        Important requirements:
        - ONLY make claims that are supported by the data provided
        - Cite specific FDA records when making statements
        - Clearly indicate when no data was found for a particular query
        - Distinguish between FDA data and interpretive analysis
        - Avoid speculation or unsupported conclusions
        
        Provide a factual, evidence-based narrative suitable for healthcare professionals and regulators.
        """
        
    async def process_task(self, task: AgentTask) -> AgentTask:
        """Synthesize results from multiple agents"""
        try:
            all_results = task.parameters.get("agent_results", {})
            
            # Prepare summarized results (include aggregate data from enhanced analysis)
            summarized_results = {}
            for agent_name, agent_data_list in all_results.items():
                summarized_results[agent_name] = []
                for agent_data in agent_data_list:
                    summary = {k: v for k, v in agent_data.items() if k != 'raw_data'}
                    
                    # Include aggregate data and enhanced analysis if available
                    if 'raw_data' in agent_data:
                        raw = agent_data['raw_data']
                        if 'aggregate_data' in raw:
                            summary['aggregate_data'] = raw['aggregate_data']
                        if 'enhanced_analysis' in raw:
                            # Include key parts of enhanced analysis
                            summary['enhanced_analysis_summary'] = {
                                'risk_indicators': raw['enhanced_analysis'].get('risk_indicators', {}),
                                'severity_patterns': {
                                    'deaths_total': raw['enhanced_analysis'].get('severity_patterns', {}).get('deaths', {}).get('total', 0),
                                    'injuries_total': raw['enhanced_analysis'].get('severity_patterns', {}).get('injuries', {}).get('total', 0)
                                },
                                'common_problems': raw['enhanced_analysis'].get('common_problems', {}).get('top_device_problems', [])[:5]
                            }
                    
                    summarized_results[agent_name].append(summary)
            
            synthesis_prompt = f"""
            Create a concise factual summary of FDA data for {task.query}:
            
            {json.dumps(summarized_results, indent=2)}
            
            Structure your response as:
            
            ## Summary
            [2-3 sentences on what the data shows. If aggregate_data is present, use the total_events from there, NOT the analyzed sample counts]
            
            ## Key Data Points
            - Total events: [Use aggregate_data.total_events if available, which shows ALL events in the time period]
            - Event breakdown: [Use aggregate_data.event_types if available]
            - Total recalls: Y (cite recall numbers)  
            - Top manufacturers: [Use aggregate_data.manufacturers if available]
            - Time period covered: Last 12 months
            
            ## Notable Findings
            - From the analyzed samples of deaths/injuries, highlight specific patterns
            - Include risk indicators from enhanced_analysis_summary if available
            - Reference specific FDA records from the serious_events
            - Note any trending problems or high-risk models
            
            ## Data Limitations
            - Note if any searches returned no results
            - Distinguish between total counts and analyzed samples
            
            IMPORTANT DISTINCTIONS:
            - aggregate_data.total_events = TOTAL events in FDA database for the time period
            - data_points/analyzed_count = number of events we analyzed in detail
            - serious_events = specific examples from our analysis sample
            
            Example: "FDA data shows 278,138 total events for Medtronic in the last 12 months. 
            From our analysis of 150 strategic samples (50 deaths, 100 injuries), we identified..."
            """
            
            messages = self._create_messages(synthesis_prompt)
            response = await self.llm.ainvoke(messages)
            
            task.result = {
                "narrative": response.content,
                "agent_role": self.role.value,
                "timestamp": datetime.now().isoformat()
            }
            task.status = "completed"
            
        except Exception as e:
            logger.error(f"Synthesizer error: {e}")
            task.error = str(e)
            task.status = "failed"
            
        return task


class FDAMultiAgentOrchestrator:
    """Main orchestrator for the multi-agent system"""
    
    def __init__(self):
        # Initialize LLM - use faster model
        self.llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("AI_API_KEY"),
            model="openai/gpt-3.5-turbo",  # Much faster!
            temperature=0.3
        )
        
        # Initialize agents
        fda_api_key = os.getenv("FDA_API_KEY")
        
        # Import additional specialist agents
        from .specialist_agents import (
            ClearancesSpecialistAgent,
            ClassificationsSpecialistAgent,
            PMASpecialistAgent,
            UDISpecialistAgent
        )
        
        # Import hybrid orchestrator
        from .hybrid_orchestrator import HybridOrchestrator
        
        self.hybrid_orchestrator = HybridOrchestrator(self.llm)
        
        self.agents = {
            AgentRole.ORCHESTRATOR: OrchestratorAgent(self.llm),
            AgentRole.EVENTS: EventsSpecialistAgent(self.llm, fda_api_key),
            AgentRole.RECALLS: RecallsSpecialistAgent(self.llm, fda_api_key),
            AgentRole.CLEARANCES: ClearancesSpecialistAgent(self.llm, fda_api_key),
            AgentRole.CLASSIFICATIONS: ClassificationsSpecialistAgent(self.llm, fda_api_key),
            AgentRole.PMA: PMASpecialistAgent(self.llm, fda_api_key),
            AgentRole.UDI: UDISpecialistAgent(self.llm, fda_api_key),
            AgentRole.SYNTHESIZER: SynthesizerAgent(self.llm)
        }
        
    async def process_query(self, query: str, progress_callback: Optional[Callable] = None) -> Dict:
        """Process a user query through the multi-agent system"""
        
        try:
            # Step 1: Use hybrid orchestrator for better analysis
            if progress_callback:
                await progress_callback(10, "🤔 Understanding your query...")
                
            # Use hybrid orchestrator
            enhanced_intent = await self.hybrid_orchestrator.analyze_query(query)
            execution_plan = self.hybrid_orchestrator.create_execution_plan(enhanced_intent)
            
            # Convert to legacy format for compatibility
            intent = {
                "primary_intent": enhanced_intent.primary_intent,
                "device_names": [d["name"] for d in enhanced_intent.device_entities],
                "time_range": enhanced_intent.explicit_timeframe.get("relative") if enhanced_intent.explicit_timeframe else None,
                "specific_concerns": enhanced_intent.implicit_concerns,
                "required_agents": [agent.value for agent in enhanced_intent.required_agents]
            }
            
            if progress_callback:
                agents_needed = len(intent["required_agents"])
                await progress_callback(20, f"📋 Activating {agents_needed} specialist agents...")
            
            # Step 2: Execute tasks with specialist agents
            agent_results = {}
            progress_per_agent = 50 / len(execution_plan) if execution_plan else 50
            current_progress = 20
            
            for task in execution_plan:
                if task.assigned_to in self.agents:
                    agent = self.agents[task.assigned_to]
                    
                    if progress_callback:
                        await progress_callback(
                            current_progress,
                            f"🔍 {task.assigned_to.value} analyzing {task.query}..."
                        )
                        
                    completed_task = await agent.process_task(task)
                    
                    if completed_task.status == "completed":
                        if task.assigned_to not in agent_results:
                            agent_results[task.assigned_to.value] = []
                        agent_results[task.assigned_to.value].append(completed_task.result)
                        
                    current_progress += progress_per_agent
                    
            # Step 3: Synthesize results
            if progress_callback:
                await progress_callback(80, "🧠 Synthesizing findings...")
                
            synthesis_task = AgentTask(
                id="synthesis_1",
                type=TaskType.ANALYZE,
                query=query,
                parameters={"agent_results": agent_results}
            )
            
            synthesizer = self.agents[AgentRole.SYNTHESIZER]
            synthesis_task = await synthesizer.process_task(synthesis_task)
            
            if progress_callback:
                await progress_callback(100, "✅ Analysis complete!")
                
            # Compile final response
            return {
                "success": True,
                "query": query,
                "intent": intent,
                "agent_results": agent_results,
                "synthesis": synthesis_task.result if synthesis_task.status == "completed" else None,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "timestamp": datetime.now().isoformat()
            }