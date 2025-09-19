"""
Hybrid Orchestrator for FDA Multi-Agent System

Combines AI-powered understanding with deterministic execution for reliable results.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .agents_v2 import (
    AgentRole, TaskType, AgentTask, QueryIntent,
    EventsSpecialistAgent, RecallsSpecialistAgent
)
from .specialist_agents import (
    ClearancesSpecialistAgent, ClassificationsSpecialistAgent,
    PMASpecialistAgent, UDISpecialistAgent
)
from .fda_query_utils import FDAQueryNormalizer

logger = logging.getLogger(__name__)


class QueryComplexity(Enum):
    """Complexity levels for queries"""
    SIMPLE = "simple"          # Single device, basic info
    MODERATE = "moderate"      # Multiple aspects or time-based
    COMPLEX = "complex"        # Comparison, trends, or multi-device


@dataclass
class EnhancedQueryIntent:
    """Enhanced query understanding with both AI and deterministic components"""
    # AI-extracted components
    primary_intent: str
    implicit_concerns: List[str]
    time_sensitivity: str
    
    # Deterministically extracted entities
    device_entities: List[Dict[str, str]]  # [{"name": "insulin pump", "variants": ["insulin_pump"]}]
    manufacturer_entities: List[Dict[str, str]]  # [{"name": "Medtronic", "variants": ["MEDTRONIC"]}]
    brand_entities: List[Dict[str, str]]  # [{"name": "MiniMed 780G", "variants": []}]
    fda_numbers: List[Dict[str, str]]  # [{"type": "510k", "number": "K123456"}]
    
    # Query metadata
    query_type: str  # "device" | "manufacturer" | "brand" | "mixed"
    explicit_timeframe: Optional[Dict[str, Any]]
    query_complexity: QueryComplexity
    required_agents: List[AgentRole]
    
    # Search optimization
    search_strategies: List[str]
    parallel_searches: bool


class HybridOrchestrator:
    """Orchestrator combining AI understanding with deterministic execution"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.normalizer = FDAQueryNormalizer()
        
        # Compile patterns for entity extraction
        self.device_patterns = self._compile_device_patterns()
        self.manufacturer_patterns = self._compile_manufacturer_patterns()
        self.fda_number_patterns = self._compile_fda_number_patterns()
        
        # Agent mapping for deterministic selection
        self.concern_to_agents = {
            "safety": [AgentRole.EVENTS, AgentRole.RECALLS],
            "regulatory": [AgentRole.CLEARANCES, AgentRole.CLASSIFICATIONS, AgentRole.PMA],
            "manufacturer": [AgentRole.UDI, AgentRole.EVENTS, AgentRole.RECALLS, AgentRole.CLEARANCES],
            "approval": [AgentRole.CLEARANCES, AgentRole.PMA],
            "recall": [AgentRole.RECALLS],
            "adverse": [AgentRole.EVENTS],
            "classification": [AgentRole.CLASSIFICATIONS],
            "identify": [AgentRole.UDI],
            "comprehensive": [AgentRole.EVENTS, AgentRole.RECALLS, AgentRole.CLEARANCES, 
                            AgentRole.CLASSIFICATIONS, AgentRole.PMA]
        }
    
    def _compile_device_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns for common device references"""
        return {
            "insulin_pump": re.compile(r'\b(insulin\s*pump|insulin\s*infusion|infusion\s*pump)s?\b', re.I),
            "pacemaker": re.compile(r'\b(pace\s*maker|cardiac\s*pacer|heart\s*pacer)s?\b', re.I),
            "defibrillator": re.compile(r'\b(defibrillator|icd|aicd)s?\b', re.I),
            "stent": re.compile(r'\b(stent|coronary\s*stent|drug[\s-]eluting)s?\b', re.I),
            "catheter": re.compile(r'\b(catheter|cath)s?\b', re.I),
            "ventilator": re.compile(r'\b(ventilator|respirator|breathing\s*machine)s?\b', re.I),
            "implant": re.compile(r'\b(implant|prosthes[ie]s)s?\b', re.I),
        }
    
    def _compile_manufacturer_patterns(self) -> Dict[str, re.Pattern]:
        """Compile patterns for manufacturer detection"""
        return {
            "company_suffix": re.compile(r'\b(\w+(?:\s+\w+)*)\s+(?:inc\.?|incorporated|corp\.?|corporation|company|co\.?|llc|ltd\.?|limited|medical|healthcare|technologies|systems|devices)\b', re.I),
            "capitalized_names": re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b')  # Detect capitalized company names
        }
    
    def _compile_fda_number_patterns(self) -> Dict[str, re.Pattern]:
        """Compile patterns for FDA number detection"""
        return {
            "510k": re.compile(r'\b[Kk]\d{6}\b'),
            "pma": re.compile(r'\b[Pp]\d{6}\b'),
            "de_novo": re.compile(r'\bDEN\d{6}\b', re.I),
            "recall": re.compile(r'\b[Zz]-\d{4}-\d{4}\b')
        }
    
    async def analyze_query(self, query: str) -> EnhancedQueryIntent:
        """Analyze query using hybrid approach"""
        
        # Phase 1: Deterministic extraction of all entity types
        device_entities = self._extract_devices(query)
        manufacturer_entities = self._extract_manufacturers(query)
        brand_entities = self._extract_brands(query)
        fda_numbers = self._extract_fda_numbers(query)
        explicit_timeframe = self._extract_timeframe(query)
        
        # Determine query type based on what was found
        query_type = self._determine_query_type(
            device_entities, manufacturer_entities, brand_entities, fda_numbers
        )
        
        # Assess complexity
        all_entities = len(device_entities) + len(manufacturer_entities) + len(brand_entities)
        complexity = self._assess_complexity(query, all_entities)
        
        # Phase 2: AI-powered understanding
        ai_intent = await self._ai_analyze_intent(query, {
            "devices": device_entities,
            "manufacturers": manufacturer_entities,
            "brands": brand_entities,
            "query_type": query_type
        })
        
        # Phase 3: Determine required agents based on query type
        required_agents = self._determine_required_agents_by_type(
            query_type, ai_intent, explicit_timeframe
        )
        
        search_strategies = self._plan_search_strategies(
            device_entities, manufacturer_entities, complexity, ai_intent
        )
        
        return EnhancedQueryIntent(
            primary_intent=ai_intent.get("primary_intent", "analyze"),
            implicit_concerns=ai_intent.get("implicit_concerns", []),
            time_sensitivity=ai_intent.get("time_sensitivity", "current"),
            device_entities=device_entities,
            manufacturer_entities=manufacturer_entities,
            brand_entities=brand_entities,
            fda_numbers=fda_numbers,
            query_type=query_type,
            explicit_timeframe=explicit_timeframe,
            query_complexity=complexity,
            required_agents=required_agents,
            search_strategies=search_strategies,
            parallel_searches=True  # Always search in parallel for comprehensive view
        )
    
    def _extract_devices(self, query: str) -> List[Dict[str, str]]:
        """Deterministically extract device mentions"""
        devices = []
        
        # Check against known patterns
        for device_type, pattern in self.device_patterns.items():
            if pattern.search(query):
                match = pattern.search(query)
                device_name = match.group(0)
                
                # Get normalized variants
                variants = self.normalizer.normalize_device_name(device_name)
                
                devices.append({
                    "name": device_name,
                    "type": device_type,
                    "variants": variants,
                    "position": match.start()
                })
        
        # If no known patterns, try to extract noun phrases
        if not devices:
            # Simple heuristic: look for capitalized phrases or phrases before keywords
            device_keywords = r'(?:for|with|of|about|regarding)\s+([A-Z][a-zA-Z\s]+?)(?:\s|$|[,.])'
            matches = re.finditer(device_keywords, query, re.I)
            
            for match in matches:
                device_name = match.group(1).strip()
                if 2 <= len(device_name.split()) <= 4:  # Reasonable device name length
                    devices.append({
                        "name": device_name,
                        "type": "unknown",
                        "variants": self.normalizer.normalize_device_name(device_name),
                        "position": match.start()
                    })
        
        # Sort by position to maintain query order
        return sorted(devices, key=lambda x: x["position"])
    
    def _extract_manufacturers(self, query: str) -> List[Dict[str, str]]:
        """Extract manufacturer names from query"""
        manufacturers = []
        found_names = set()
        
        # Check for known manufacturers
        for pattern_name, pattern in self.manufacturer_patterns.items():
            matches = pattern.finditer(query)
            for match in matches:
                manufacturer_name = match.group(1).strip()
                normalized_name = manufacturer_name.upper()
                
                if normalized_name not in found_names:
                    found_names.add(normalized_name)
                    manufacturers.append({
                        "name": manufacturer_name,
                        "variants": [normalized_name, manufacturer_name.lower()],
                        "position": match.start()
                    })
        
        return sorted(manufacturers, key=lambda x: x["position"])
    
    def _extract_brands(self, query: str) -> List[Dict[str, str]]:
        """Extract brand names (capitalized multi-word phrases)"""
        brands = []
        
        # Pattern for brand names: Multiple capitalized words or words with numbers
        brand_pattern = re.compile(r'\b([A-Z][a-zA-Z0-9]*(?:\s+[A-Z0-9][a-zA-Z0-9]*)+)\b')
        
        for match in brand_pattern.finditer(query):
            brand_name = match.group(1)
            # Filter out common words that aren't brands
            if brand_name not in ["FDA", "US", "USA", "API"]:
                brands.append({
                    "name": brand_name,
                    "variants": [brand_name.replace(" ", ""), brand_name.lower()],
                    "position": match.start()
                })
        
        return sorted(brands, key=lambda x: x["position"])
    
    def _extract_fda_numbers(self, query: str) -> List[Dict[str, str]]:
        """Extract FDA reference numbers"""
        fda_numbers = []
        
        for number_type, pattern in self.fda_number_patterns.items():
            matches = pattern.finditer(query)
            for match in matches:
                fda_numbers.append({
                    "type": number_type,
                    "number": match.group(0),
                    "position": match.start()
                })
        
        return sorted(fda_numbers, key=lambda x: x["position"])
    
    def _determine_query_type(self, devices, manufacturers, brands, fda_numbers) -> str:
        """Determine the primary type of query"""
        if fda_numbers:
            return "regulatory"
        elif manufacturers and not devices:
            return "manufacturer"
        elif brands and not devices:
            return "brand"
        elif devices and manufacturers:
            return "mixed"
        elif devices:
            return "device"
        else:
            return "general"
    
    def _extract_timeframe(self, query: str) -> Optional[Dict[str, Any]]:
        """Extract explicit time references"""
        timeframe = {}
        
        # Recent/current patterns - default to 12 months
        if re.search(r'\b(recent|lately|current|now|today)\b', query, re.I):
            timeframe["relative"] = "recent"
            timeframe["months_back"] = 12
        
        # Past year patterns
        elif re.search(r'\b(past|last)\s+(year|12\s*months)\b', query, re.I):
            timeframe["relative"] = "past_year"
            timeframe["months_back"] = 12
        
        # Specific year patterns
        year_match = re.search(r'\b(20\d{2})\b', query)
        if year_match:
            timeframe["year"] = int(year_match.group(1))
            current_year = datetime.now().year
            if timeframe["year"] < current_year:
                timeframe["months_back"] = (current_year - timeframe["year"]) * 12
        
        # Date range patterns
        range_match = re.search(r'from\s+(\w+)\s+to\s+(\w+)', query, re.I)
        if range_match:
            timeframe["range"] = {
                "start": range_match.group(1),
                "end": range_match.group(2)
            }
        
        return timeframe if timeframe else None
    
    def _assess_complexity(self, query: str, entity_count: int) -> QueryComplexity:
        """Assess query complexity"""
        
        # Multiple entities = at least moderate
        if entity_count > 1:
            return QueryComplexity.COMPLEX if "compar" in query.lower() else QueryComplexity.MODERATE
        
        # Comparison keywords
        if re.search(r'\b(compar|versus|vs\.?|between|differ)\b', query, re.I):
            return QueryComplexity.COMPLEX
        
        # Trend/timeline keywords
        if re.search(r'\b(trend|timeline|history|evolution|pattern)\b', query, re.I):
            return QueryComplexity.COMPLEX
        
        # Multiple aspects
        aspect_keywords = ['safety', 'efficacy', 'regulatory', 'manufacturer', 'recall', 'approval']
        aspect_count = sum(1 for keyword in aspect_keywords if keyword in query.lower())
        if aspect_count >= 2:
            return QueryComplexity.MODERATE
        
        return QueryComplexity.SIMPLE
    
    async def _ai_analyze_intent(self, query: str, entities: Dict[str, List]) -> Dict[str, Any]:
        """Use AI to understand implicit intent and concerns"""
        
        # Build context from all entity types
        context_parts = []
        if entities["devices"]:
            context_parts.append(f"Devices: {', '.join([d['name'] for d in entities['devices']])}")
        if entities["manufacturers"]:
            context_parts.append(f"Manufacturers: {', '.join([m['name'] for m in entities['manufacturers']])}")
        if entities["brands"]:
            context_parts.append(f"Brands: {', '.join([b['name'] for b in entities['brands']])}")
            
        context = "; ".join(context_parts) if context_parts else "No specific entities identified"
        
        prompt = f"""Analyze this medical device query for implicit intent and concerns.
        
        Query: "{query}"
        Identified entities: {context}
        Query type: {entities.get('query_type', 'unknown')}
        
        Provide:
        1. primary_intent: The main goal (search/analyze/compare/investigate/monitor/profile)
        2. implicit_concerns: List of concerns not explicitly stated but likely relevant
        3. time_sensitivity: How time-sensitive is this (immediate/recent/historical/ongoing)
        
        For manufacturer queries, consider: company reputation, product portfolio, safety record
        For device queries, consider: safety, effectiveness, regulatory status
        For brand queries, consider: specific model performance, recalls, comparisons
        
        Output as JSON."""
        
        messages = [
            SystemMessage(content="You are an expert at understanding medical device queries."),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            # Parse response - handle both string and dict responses
            import json
            if hasattr(response, 'content'):
                content = response.content
                # Try to extract JSON from the response
                if isinstance(content, str):
                    # Look for JSON pattern
                    json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                    else:
                        # Try parsing the whole content
                        return json.loads(content)
                elif isinstance(content, dict):
                    return content
            return {}
        except Exception as e:
            logger.warning(f"AI intent analysis failed: {e}")
            return {
                "primary_intent": "analyze",
                "implicit_concerns": [],
                "time_sensitivity": "current"
            }
    
    def _determine_required_agents(self, query: str, ai_intent: Dict, 
                                 devices: List[Dict]) -> List[AgentRole]:
        """Determine which agents to activate"""
        agents = set()
        
        # Check explicit keywords first
        query_lower = query.lower()
        for keyword, agent_list in self.concern_to_agents.items():
            if keyword in query_lower:
                agents.update(agent_list)
        
        # Add based on AI-identified concerns
        for concern in ai_intent.get("implicit_concerns", []):
            concern_lower = concern.lower()
            for keyword, agent_list in self.concern_to_agents.items():
                if keyword in concern_lower:
                    agents.update(agent_list)
        
        # Default agents based on primary intent
        intent = ai_intent.get("primary_intent", "analyze")
        if intent in ["analyze", "investigate"]:
            agents.update([AgentRole.EVENTS, AgentRole.RECALLS])
        elif intent == "compare":
            agents.update([AgentRole.EVENTS, AgentRole.RECALLS, AgentRole.CLEARANCES])
        elif intent == "monitor":
            agents.add(AgentRole.EVENTS)
        
        # Always include events for safety queries
        if any(word in query_lower for word in ["concern", "issue", "problem", "safety"]):
            agents.add(AgentRole.EVENTS)
            agents.add(AgentRole.RECALLS)
        
        # Limit to most relevant agents (max 3 for speed)
        if len(agents) > 3:
            # Prioritize events and recalls for most queries
            priority_agents = [AgentRole.EVENTS, AgentRole.RECALLS, AgentRole.CLEARANCES]
            agents = set([a for a in priority_agents if a in agents][:3])
        
        return list(agents)
    
    def _determine_required_agents_by_type(self, query_type: str, ai_intent: Dict, 
                                          timeframe: Optional[Dict]) -> List[AgentRole]:
        """Determine agents based on query type for comprehensive view"""
        
        # For comprehensive device intelligence, always use key agents
        if query_type == "manufacturer":
            # For manufacturer queries, get complete company profile
            return [
                AgentRole.EVENTS,      # Safety record
                AgentRole.RECALLS,     # Quality issues
                AgentRole.CLEARANCES,  # Product approvals
                AgentRole.UDI         # Device portfolio
            ]
        elif query_type == "device":
            # For device queries, focus on safety and regulatory
            return [
                AgentRole.EVENTS,
                AgentRole.RECALLS,
                AgentRole.CLEARANCES,
                AgentRole.CLASSIFICATIONS
            ]
        elif query_type == "brand":
            # For specific brand/model queries
            return [
                AgentRole.EVENTS,
                AgentRole.RECALLS,
                AgentRole.CLEARANCES,
                AgentRole.UDI
            ]
        elif query_type == "regulatory":
            # For FDA number queries
            return [
                AgentRole.CLEARANCES,
                AgentRole.PMA,
                AgentRole.RECALLS
            ]
        else:
            # Default comprehensive search
            return [
                AgentRole.EVENTS,
                AgentRole.RECALLS,
                AgentRole.CLEARANCES
            ]
    
    def _plan_search_strategies(self, devices: List[Dict], manufacturers: List[Dict], 
                              complexity: QueryComplexity,
                              ai_intent: Dict) -> List[str]:
        """Plan search strategies based on query analysis"""
        strategies = []
        
        if complexity == QueryComplexity.SIMPLE:
            strategies.append("exact_then_normalized")
        elif complexity == QueryComplexity.MODERATE:
            strategies.append("normalized_with_variants")
            strategies.append("wildcard_fallback")
        else:  # COMPLEX
            strategies.append("multi_variant_search")
            strategies.append("semantic_expansion")
            strategies.append("cross_reference")
        
        # Add time-based strategy if needed
        if ai_intent.get("time_sensitivity") in ["immediate", "recent"]:
            strategies.append("recent_first")
        
        return strategies
    
    def create_execution_plan(self, intent: EnhancedQueryIntent) -> List[AgentTask]:
        """Create concrete tasks based on analysis"""
        tasks = []
        task_id = 1
        
        # Create tasks based on query type
        if intent.query_type == "manufacturer":
            # For manufacturer queries, search by manufacturer name
            for manufacturer in intent.manufacturer_entities:
                for agent_role in intent.required_agents:
                    task = AgentTask(
                        id=f"task_{task_id}",
                        type=TaskType.SEARCH,
                        query=manufacturer["name"],
                        parameters={
                            "search_type": "manufacturer",
                            "variants": manufacturer["variants"],
                            "time_range_months": intent.explicit_timeframe.get("months_back") if intent.explicit_timeframe else 12,
                            "search_strategies": ["manufacturer_exact", "manufacturer_variants"],
                            "concerns": intent.implicit_concerns
                        },
                        assigned_to=agent_role
                    )
                    tasks.append(task)
                    task_id += 1
                    
        elif intent.query_type == "brand":
            # For brand queries, search by brand name
            for brand in intent.brand_entities:
                for agent_role in intent.required_agents:
                    task = AgentTask(
                        id=f"task_{task_id}",
                        type=TaskType.SEARCH,
                        query=brand["name"],
                        parameters={
                            "search_type": "brand",
                            "variants": brand["variants"],
                            "time_range_months": intent.explicit_timeframe.get("months_back") if intent.explicit_timeframe else 12,
                            "search_strategies": ["exact_match", "brand_variants"],
                            "concerns": intent.implicit_concerns
                        },
                        assigned_to=agent_role
                    )
                    tasks.append(task)
                    task_id += 1
                    
        else:
            # For device or mixed queries
            all_entities = intent.device_entities + intent.manufacturer_entities
            for entity in all_entities or [{"name": "general", "variants": []}]:
                for agent_role in intent.required_agents:
                    task = AgentTask(
                        id=f"task_{task_id}",
                        type=TaskType.SEARCH,
                        query=entity["name"],
                        parameters={
                            "search_type": "device" if entity in intent.device_entities else "manufacturer",
                            "variants": entity.get("variants", []),
                            "time_range_months": intent.explicit_timeframe.get("months_back") if intent.explicit_timeframe else 12,
                            "search_strategies": intent.search_strategies,
                            "concerns": intent.implicit_concerns
                        },
                        assigned_to=agent_role
                    )
                    tasks.append(task)
                    task_id += 1
        
        return tasks