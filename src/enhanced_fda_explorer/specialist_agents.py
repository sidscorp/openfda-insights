"""
Additional specialist agents for the FDA multi-agent system
"""

import logging
from typing import Dict, Optional, Counter
from collections import Counter
import requests
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import SystemMessage, HumanMessage

from .agents_v2 import BaseAgent, AgentRole, AgentTask, AgentResponse
from .fda_query_utils import FDAQueryNormalizer

logger = logging.getLogger(__name__)


class ClearancesSpecialistAgent(BaseAgent):
    """Specialist for 510(k) clearances data"""
    
    def __init__(self, llm: ChatOpenAI, fda_api_key: Optional[str] = None):
        super().__init__(AgentRole.CLEARANCES, llm)
        self.fda_api_key = fda_api_key
        self.response_parser = JsonOutputParser(pydantic_object=AgentResponse)
        
    def _get_system_prompt(self) -> str:
        return """You are a specialist agent for FDA 510(k) clearances.
        Your expertise includes:
        - Analyzing regulatory clearance pathways
        - Understanding substantial equivalence determinations
        - Tracking clearance timelines and trends
        - Identifying predicate devices
        - Assessing regulatory compliance
        
        Focus on:
        1. Clearance dates and timelines
        2. Predicate device relationships
        3. Applicant/manufacturer patterns
        4. Product codes and classifications
        5. Clearance statement summaries
        
        Output your analysis as JSON with key_findings, risk_indicators, and recommendations.
        """
        
    async def process_task(self, task: AgentTask) -> AgentTask:
        """Search and analyze 510(k) clearances"""
        try:
            clearance_data = await self._search_clearances(task.query, task.parameters)
            
            analysis_prompt = f"""
            Analyze these FDA 510(k) clearance data for {task.query}:
            
            Total clearances: {clearance_data['total']}
            Recent clearances: {len(clearance_data['recent_clearances'])}
            Top applicants: {clearance_data['top_applicants'][:5]}
            Product codes: {clearance_data['product_codes'][:5]}
            
            Recent clearance details:
            {clearance_data['recent_clearances'][:3]}
            
            Assess the regulatory pathway and clearance patterns.
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
                result_dict['data_points'] = clearance_data.get('analyzed_count', 0)
                
            except Exception as parse_error:
                logger.warning(f"Failed to parse clearance LLM response, using fallback: {parse_error}")
                # Fallback: Create basic response structure
                result_dict = {
                    "agent_role": self.role.value,
                    "data_points": clearance_data.get('analyzed_count', 0),
                    "key_findings": [
                        f"Found {clearance_data['total']} total clearances for {task.query}",
                        f"Top applicants: {', '.join([app[0] for app in clearance_data['top_applicants'][:3]])}",
                        f"Recent clearances: {len(clearance_data['recent_clearances'])}"
                    ],
                    "risk_indicators": {},
                    "recommendations": ["Review clearance details for regulatory compliance"]
                }
                
            result_dict['raw_data'] = clearance_data
            task.result = result_dict
            task.status = "completed"
            
        except Exception as e:
            logger.error(f"Clearances specialist error: {e}")
            task.error = str(e)
            task.status = "failed"
            
        return task
        
    async def _search_clearances(self, device_name: str, parameters: Dict) -> Dict:
        """Search FDA 510(k) API with pagination and manufacturer support"""
        url = "https://api.fda.gov/device/510k.json"
        
        # Determine search type
        search_type = parameters.get("search_type", "device")
        
        if search_type == "manufacturer":
            # For manufacturers, search by applicant field
            search_query = f"applicant:{device_name}"
        else:
            # For devices, use device_name field
            search_query = f"device_name:{device_name}"
        
        # Add date filter for temporal data (last 12 months)
        date_filter = FDAQueryNormalizer.create_date_filter(
            parameters.get("time_range_months", 12)
        )
        if date_filter:
            search_query += f" AND date_received:{date_filter}"
        
        all_clearances = []
        total_found = 0
        max_records = 500
        skip = 0
        batch_size = 100
        
        while len(all_clearances) < max_records:
            params = {
                "search": search_query,
                "limit": batch_size,
                "skip": skip,
                "sort": "date_received:desc"
            }
            
            if self.fda_api_key:
                params["api_key"] = self.fda_api_key
                
            try:
                logger.info(f"Clearances: Fetching batch skip={skip}, search_type={search_type}")
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                clearances = data.get("results", [])
                
                if not clearances:
                    break  # No more results
                    
                all_clearances.extend(clearances)
                
                if not total_found:
                    total_found = data.get("meta", {}).get("results", {}).get("total", 0)
                    logger.info(f"Found {total_found} total clearances for {search_type}: {device_name}")
                
                # Check if we've fetched all available
                if len(clearances) < batch_size or len(all_clearances) >= total_found:
                    break
                    
                skip += batch_size
                
            except Exception as e:
                logger.error(f"Clearances batch fetch error: {e}")
                break
        
        logger.info(f"Fetched {len(all_clearances)} clearances out of {total_found} total")
        
        # Analyze clearances
        applicants = Counter()
        product_codes = Counter()
        recent_clearances = []
        
        for clearance in all_clearances:
            applicant = clearance.get("applicant", "Unknown")
            applicants[applicant] += 1
            
            openfda = clearance.get("openfda", {})
            for code in openfda.get("fei_number", []):
                product_codes[code] += 1
                
            recent_clearances.append({
                "k_number": clearance.get("k_number", ""),
                "date": clearance.get("date_received", ""),
                "applicant": applicant,
                "device_name": clearance.get("device_name", ""),
                "decision": clearance.get("decision", ""),
                "statement": clearance.get("statement_or_summary", "")[:200]
            })
            
        return {
            "total": total_found,
            "analyzed_count": len(all_clearances),
            "top_applicants": applicants.most_common(),
            "product_codes": product_codes.most_common(),
            "recent_clearances": recent_clearances[:20],
            "raw_clearances": all_clearances
        }


class ClassificationsSpecialistAgent(BaseAgent):
    """Specialist for device classifications"""
    
    def __init__(self, llm: ChatOpenAI, fda_api_key: Optional[str] = None):
        super().__init__(AgentRole.CLASSIFICATIONS, llm)
        self.fda_api_key = fda_api_key
        self.response_parser = JsonOutputParser(pydantic_object=AgentResponse)
        
    def _get_system_prompt(self) -> str:
        return """You are a specialist agent for FDA device classifications.
        Your expertise includes:
        - Understanding device classes (I, II, III) and risk levels
        - Analyzing product codes and regulatory requirements
        - Identifying device panels and review pathways
        - Understanding premarket requirements
        
        Focus on:
        1. Device class and associated risk level
        2. Product code and regulation number
        3. Review panel assignment
        4. Premarket submission requirements
        5. Regulatory control levels
        
        Output your analysis as JSON with key_findings, risk_indicators, and recommendations.
        """
        
    async def process_task(self, task: AgentTask) -> AgentTask:
        """Search and analyze device classifications"""
        try:
            classification_data = await self._search_classifications(task.query, task.parameters)
            
            analysis_prompt = f"""
            Analyze these FDA device classification data for {task.query}:
            
            Total classifications found: {classification_data['total']}
            Device classes: {classification_data['device_classes']}
            Product codes: {classification_data['product_codes'][:5]}
            
            Classification details:
            {classification_data['classifications'][:3]}
            
            Assess the regulatory classification and requirements.
            """
            
            messages = self._create_messages(analysis_prompt)
            response = await self.llm.ainvoke(messages)
            
            agent_response = self.response_parser.parse(response.content)
            
            # Handle both dict and Pydantic object responses
            if hasattr(agent_response, 'dict'):
                result_dict = agent_response.dict()
            else:
                result_dict = agent_response
                
            result_dict['raw_data'] = classification_data
            task.result = result_dict
            task.status = "completed"
            
        except Exception as e:
            logger.error(f"Classifications specialist error: {e}")
            task.error = str(e)
            task.status = "failed"
            
        return task
        
    async def _search_classifications(self, device_name: str, parameters: Dict) -> Dict:
        """Search FDA classification database"""
        url = "https://api.fda.gov/device/classification.json"
        
        params = {
            "search": f"device_name:{device_name}",
            "limit": 100
        }
        
        if self.fda_api_key:
            params["api_key"] = self.fda_api_key
            
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            classifications = data.get("results", [])
            
            # Analyze classifications
            device_classes = Counter()
            product_codes = []
            classification_details = []
            
            for classification in classifications:
                device_class = classification.get("device_class", "Unknown")
                device_classes[device_class] += 1
                
                product_code = classification.get("product_code", "")
                if product_code:
                    product_codes.append(product_code)
                    
                classification_details.append({
                    "device_name": classification.get("device_name", ""),
                    "device_class": device_class,
                    "product_code": product_code,
                    "regulation_number": classification.get("regulation_number", ""),
                    "panel": classification.get("openfda", {}).get("medical_specialty_description", ["Unknown"])[0],
                    "submission_type": classification.get("submission_type_id", ""),
                    "definition": classification.get("definition", "")[:200]
                })
                
            return {
                "total": data.get("meta", {}).get("results", {}).get("total", 0),
                "device_classes": dict(device_classes),
                "product_codes": list(set(product_codes)),
                "classifications": classification_details[:20],
                "raw_classifications": classifications[:25]
            }
            
        except Exception as e:
            logger.error(f"FDA classification API error: {e}")
            return {
                "total": 0,
                "device_classes": {},
                "product_codes": [],
                "classifications": [],
                "raw_classifications": []
            }


class PMASpecialistAgent(BaseAgent):
    """Specialist for Premarket Approval (PMA) data"""
    
    def __init__(self, llm: ChatOpenAI, fda_api_key: Optional[str] = None):
        super().__init__(AgentRole.PMA, llm)
        self.fda_api_key = fda_api_key
        self.response_parser = JsonOutputParser(pydantic_object=AgentResponse)
        
    def _get_system_prompt(self) -> str:
        return """You are a specialist agent for FDA Premarket Approvals (PMA).
        Your expertise includes:
        - Analyzing PMA applications and approvals
        - Understanding clinical trial requirements
        - Tracking approval timelines
        - Assessing post-approval studies
        - Understanding supplements and amendments
        
        Focus on:
        1. Approval status and dates
        2. Clinical trial data requirements
        3. Post-approval study commitments
        4. Supplement history
        5. Advisory committee involvement
        
        Output your analysis as JSON with key_findings, risk_indicators, and recommendations.
        """
        
    async def process_task(self, task: AgentTask) -> AgentTask:
        """Search and analyze PMA data"""
        try:
            pma_data = await self._search_pma(task.query, task.parameters)
            
            analysis_prompt = f"""
            Analyze these FDA PMA data for {task.query}:
            
            Total PMAs: {pma_data['total']}
            Recent approvals: {len(pma_data['recent_approvals'])}
            Top applicants: {pma_data['top_applicants'][:5]}
            
            PMA details:
            {pma_data['recent_approvals'][:3]}
            
            Assess the PMA pathway and approval patterns.
            """
            
            messages = self._create_messages(analysis_prompt)
            response = await self.llm.ainvoke(messages)
            
            agent_response = self.response_parser.parse(response.content)
            
            # Handle both dict and Pydantic object responses
            if hasattr(agent_response, 'dict'):
                result_dict = agent_response.dict()
            else:
                result_dict = agent_response
                
            result_dict['raw_data'] = pma_data
            task.result = result_dict
            task.status = "completed"
            
        except Exception as e:
            logger.error(f"PMA specialist error: {e}")
            task.error = str(e)
            task.status = "failed"
            
        return task
        
    async def _search_pma(self, device_name: str, parameters: Dict) -> Dict:
        """Search FDA PMA database"""
        url = "https://api.fda.gov/device/pma.json"
        
        params = {
            "search": f"trade_name:{device_name} OR generic_name:{device_name}",
            "limit": 100,
            "sort": "decision_date:desc"
        }
        
        if self.fda_api_key:
            params["api_key"] = self.fda_api_key
            
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            pmas = data.get("results", [])
            
            # Analyze PMAs
            applicants = Counter()
            recent_approvals = []
            
            for pma in pmas:
                applicant = pma.get("applicant", "Unknown")
                applicants[applicant] += 1
                
                recent_approvals.append({
                    "pma_number": pma.get("pma_number", ""),
                    "decision_date": pma.get("decision_date", ""),
                    "applicant": applicant,
                    "trade_name": pma.get("trade_name", ""),
                    "generic_name": pma.get("generic_name", ""),
                    "decision": pma.get("decision_code", ""),
                    "advisory_committee": pma.get("openfda", {}).get("advisory_committee_description", ["N/A"])[0],
                    "supplements": len(pma.get("supplements", []))
                })
                
            return {
                "total": data.get("meta", {}).get("results", {}).get("total", 0),
                "top_applicants": applicants.most_common(),
                "recent_approvals": recent_approvals[:20],
                "raw_pmas": pmas[:25]
            }
            
        except Exception as e:
            logger.error(f"FDA PMA API error: {e}")
            return {
                "total": 0,
                "top_applicants": [],
                "recent_approvals": [],
                "raw_pmas": []
            }


class UDISpecialistAgent(BaseAgent):
    """Specialist for Unique Device Identifier (UDI) data"""
    
    def __init__(self, llm: ChatOpenAI, fda_api_key: Optional[str] = None):
        super().__init__(AgentRole.UDI, llm)
        self.fda_api_key = fda_api_key
        self.response_parser = JsonOutputParser(pydantic_object=AgentResponse)
        
    def _get_system_prompt(self) -> str:
        return """You are a specialist agent for FDA Unique Device Identifier (UDI) data.
        Your expertise includes:
        - Analyzing device identification and tracking
        - Understanding labeler information
        - Tracking device versions and models
        - Identifying MRI safety information
        - Assessing device characteristics
        
        Focus on:
        1. Device identifiers and versions
        2. Labeler/manufacturer information
        3. MRI safety status
        4. Storage and handling requirements
        5. Device size and packaging configurations
        
        Output your analysis as JSON with key_findings, risk_indicators, and recommendations.
        """
        
    async def process_task(self, task: AgentTask) -> AgentTask:
        """Search and analyze UDI data"""
        try:
            udi_data = await self._search_udi(task.query, task.parameters)
            
            analysis_prompt = f"""
            Analyze these FDA UDI data for {task.query}:
            
            Total devices: {udi_data['total']}
            Labelers: {len(udi_data['labelers'])}
            MRI safety info: {udi_data['mri_safety']}
            
            Device details:
            {udi_data['devices'][:3]}
            
            Assess device identification and characteristics.
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
                result_dict['data_points'] = udi_data.get('analyzed_count', 0)
                
            except Exception as parse_error:
                logger.warning(f"Failed to parse UDI LLM response, using fallback: {parse_error}")
                # Fallback: Create basic response structure
                result_dict = {
                    "agent_role": self.role.value,
                    "data_points": udi_data.get('analyzed_count', 0),
                    "key_findings": [
                        f"Found {udi_data['total']} total UDI records for {task.query}",
                        f"Top labelers: {', '.join([lab[0] for lab in udi_data['labelers'][:3]])}" if udi_data['labelers'] else "No labelers found",
                        f"MRI safety: {udi_data.get('mri_safety', {})}"
                    ],
                    "risk_indicators": {},
                    "recommendations": ["Review device identification data for safety compliance"]
                }
                
            result_dict['raw_data'] = udi_data
            task.result = result_dict
            task.status = "completed"
            
        except Exception as e:
            logger.error(f"UDI specialist error: {e}")
            task.error = str(e)
            task.status = "failed"
            
        return task
        
    async def _search_udi(self, device_name: str, parameters: Dict) -> Dict:
        """Search FDA UDI database with pagination and manufacturer support"""
        url = "https://api.fda.gov/device/udi.json"
        
        # Determine search type
        search_type = parameters.get("search_type", "device")
        
        if search_type == "manufacturer":
            # For manufacturers, search by company_name field
            search_query = f"company_name:{device_name}"
        else:
            # For devices, use brand_name and model fields
            search_query = f"brand_name:{device_name} OR version_or_model_number:{device_name}"
        
        all_devices = []
        total_found = 0
        max_records = 500
        skip = 0
        batch_size = 100
        
        while len(all_devices) < max_records:
            params = {
                "search": search_query,
                "limit": batch_size,
                "skip": skip
            }
            
            if self.fda_api_key:
                params["api_key"] = self.fda_api_key
                
            try:
                logger.info(f"UDI: Fetching batch skip={skip}, search_type={search_type}")
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                devices = data.get("results", [])
                
                if not devices:
                    break  # No more results
                    
                all_devices.extend(devices)
                
                if not total_found:
                    total_found = data.get("meta", {}).get("results", {}).get("total", 0)
                    logger.info(f"Found {total_found} total UDI records for {search_type}: {device_name}")
                
                # Check if we've fetched all available
                if len(devices) < batch_size or len(all_devices) >= total_found:
                    break
                    
                skip += batch_size
                
            except Exception as e:
                logger.error(f"UDI batch fetch error: {e}")
                break
        
        logger.info(f"Fetched {len(all_devices)} UDI records out of {total_found} total")
        
        # Analyze UDI data
        labelers = Counter()
        mri_safety = Counter()
        device_details = []
        
        for device in all_devices:
            labeler = device.get("company_name", "Unknown")
            labelers[labeler] += 1
            
            mri = device.get("mri_safety", "Unknown")
            mri_safety[mri] += 1
            
            device_details.append({
                "brand_name": device.get("brand_name", ""),
                "version_model": device.get("version_or_model_number", ""),
                "labeler": labeler,
                "mri_safety": mri,
                "device_sizes": device.get("device_sizes", []),
                "storage": device.get("storage_conditions", ""),
                "commercial_distribution_date": device.get("commercial_distribution_end_date", "")
            })
            
        return {
            "total": total_found,
            "analyzed_count": len(all_devices),
            "labelers": labelers.most_common(),
            "mri_safety": dict(mri_safety),
            "devices": device_details[:20],
            "raw_devices": all_devices
        }