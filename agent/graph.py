"""
LangGraph agent implementation.

Architecture: Router (LLM) → Tools → Assessor → Answer
Rationale: Stateful orchestration with guardrails per PRD Phase 3
"""
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

# Silence tokenizers warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

# Load environment variables from .env file
load_dotenv()

from agent.extractor import ParameterExtractor, extracted_params_to_query_string, generate_lucene_query
from agent.prompt import SYSTEM_PROMPT
from agent.router import route
from agent.state import AgentState, ToolCall
from rag.retrieval import DocRetriever
from tools.classification import ClassifyParams, classify
from tools.k510 import K510SearchParams, k510_search
from tools.maude import MAUDESearchParams, maude_search
from tools.pma import PMASearchParams, pma_search
from tools.recall import RecallSearchParams, recall_search
from tools.registration_listing import RLSearchParams, rl_search
from tools.udi import UDISearchParams, udi_search
from tools.utils import (
    AnswerAssessorParams,
    ProbeCountParams,
    answer_assessor,
    field_explorer,
    probe_count,
)


class FDAAgent:
    """FDA Device Analyst agent with LangGraph orchestration."""

    MAX_RETRIES = 1  # Reduce to avoid infinite loops

    def __init__(self, api_key: Optional[str] = None, anthropic_api_key: Optional[str] = None):
        """
        Initialize agent.

        Args:
            api_key: openFDA API key (optional)
            anthropic_api_key: Anthropic API key for Claude (required)
        """
        self.openfda_api_key = api_key
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY required (env var or parameter)")

        # Initialize LLM
        self.llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            api_key=self.anthropic_api_key,
            temperature=0,
        )

        # Initialize RAG retriever
        self.retriever = DocRetriever(corpus_path="docs/corpus.json")

        # Initialize parameter extractor
        self.extractor = ParameterExtractor(llm=self.llm)

        # Build graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Construct LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("router", self._router_node)
        workflow.add_node("execute_tools", self._execute_tools_node)
        workflow.add_node("assessor", self._assessor_node)
        workflow.add_node("answer", self._answer_node)

        # Define edges
        workflow.set_entry_point("router")
        workflow.add_edge("router", "execute_tools")
        workflow.add_edge("execute_tools", "assessor")

        # Conditional edge from assessor
        workflow.add_conditional_edges(
            "assessor",
            self._should_retry,
            {
                "retry": "router",  # Retry with updated state
                "answer": "answer",  # Proceed to answer
            },
        )

        workflow.add_edge("answer", END)

        # Compile graph with recursion limit to prevent infinite loops
        compiled = workflow.compile()
        return compiled

    def _is_safety_query(self, question: str) -> bool:
        """Check if this is a comprehensive safety-related query."""
        safety_keywords = [
            'safety', 'recall', 'adverse event', 'maude', 'problem',
            'issue', 'defect', 'risk', 'hazard', 'injury', 'death',
            'malfunction', 'failure', 'complaint', 'investigation'
        ]
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in safety_keywords)

    def _analyze_query_type(self, question: str) -> dict:
        """Use LLM to intelligently analyze the query type and intent."""
        # Use format() instead of f-string to avoid brace issues
        analysis_prompt = """Analyze this FDA device query to understand what the user is asking for:

Query: "{}"

Determine the following:

1. Query Type:
   - AGGREGATION: Asking for a list/group of items (which, what, list all, show me all)
   - SEARCH: Looking for specific items that match criteria
   - COUNT: Asking for numerical totals (how many, total, count)
   - SAFETY_CHECK: Comprehensive safety analysis needed
   - LOOKUP: Finding a specific item by ID

2. Primary Entity (what they want to know about):
   - product_codes
   - devices
   - recalls
   - companies
   - adverse_events
   - approvals

3. Grouping Needed (if aggregation):
   - by_product_code
   - by_company
   - by_date
   - by_classification
   - none

4. Time Constraints:
   - specific_year: (e.g., 2025)
   - date_range: (start and end)
   - none

5. Data Availability Issues:
   - Does this query ask for data that might not exist in a single endpoint?
   - Example: "product codes with recalls" (recalls don't contain product codes)

Return ONLY valid JSON (no other text):
{{
  "query_type": "AGGREGATION|SEARCH|COUNT|SAFETY_CHECK|LOOKUP",
  "primary_entity": "product_codes|devices|recalls|companies|adverse_events|approvals",
  "grouping": "by_product_code|by_company|by_date|by_classification|none",
  "time_constraints": {{"year": 2024, "start": null, "end": null}},
  "needs_cross_reference": true,
  "explanation": "Brief explanation"
}}""".format(question)

        messages = [
            SystemMessage(content="You are an expert at understanding FDA database queries."),
            HumanMessage(content=analysis_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            import json
            analysis = json.loads(response.content)
            print(f"[Router] Query analysis: {analysis.get('query_type', 'unknown')} - {analysis.get('explanation', 'no explanation')}")
            return analysis
        except Exception as e:
            print(f"[Router] Analysis failed, using fallback: {e}")
            # Fallback to simple pattern matching
            return {
                "query_type": "SEARCH",
                "primary_entity": "devices",
                "grouping": "none",
                "time_constraints": {},
                "needs_cross_reference": False,
                "explanation": "Default search query"
            }

    def _router_node(self, state: AgentState) -> AgentState:
        """
        Router node: Create execution plan and select strategy.

        Plans HOW to answer the question, not just which tool to use.
        """
        print(f"\n[Router] Planning approach (attempt {state.retry_count + 1})...")

        # Analyze query type using LLM intelligence
        query_analysis = self._analyze_query_type(state.question)
        state.query_analysis = query_analysis

        # Check if this is a safety-related query that needs comprehensive analysis
        # Only do safety check if asking about a SPECIFIC product code's safety
        if query_analysis.get("query_type") == "SAFETY_CHECK":
            # Extract product code to see if we have one
            extracted = self.extractor.extract(state.question)
            if extracted.product_code:
                print("[Router] Detected safety query for specific product code - will check multiple endpoints")
                state.is_safety_check = True
            else:
                print("[Router] Safety query but no specific product code - will route normally")

        # Get RAG hints for routing
        rag_docs = self.retriever.search(state.question, top_k=2)
        rag_hints = "\n\n".join([d.content[:800] for d in rag_docs]) if rag_docs else None

        if rag_hints:
            print(f"[Router] Using RAG hints from {len(rag_docs)} docs")

        # Create planning prompt
        planning_prompt = f"""Analyze this FDA device query and create an execution plan.

Question: {state.question}

Determine:
1. Is this asking for a SPECIFIC item (exact device/company) or a CATEGORY (type of devices)?
2. What's the best search strategy?
3. What should we do if initial search fails?

Examples:
- "orthopedic implants" = CATEGORY (search broadly, filter results)
- "Abbott Laboratories" = SPECIFIC (exact company match)
- "insulin pumps" = CATEGORY (device type, search by keywords)
- "K123456" = SPECIFIC (exact ID)

For categories, DO NOT use exact device_name matching.

Output JSON:
{{
  "endpoint": "classification|510k|pma|recall|maude|udi|rl_search",
  "strategy": "exact|category|broad",
  "plan": ["Step 1", "Step 2", "Step 3"],
  "reasoning": "Why this approach"
}}"""

        # Add context from previous attempts if retrying
        question = state.question
        if state.retry_count > 0:
            print(f"[Router] Retry reason: {state.assessment_reason}")

            # Modify question to force different parameters
            if "not found" in state.assessment_reason.lower() and state.extracted_params:
                # Remove most specific filter
                if state.extracted_params.get('product_code'):
                    question = f"{state.question}\n\nDo NOT filter by product code."
                elif state.extracted_params.get('applicant'):
                    question = f"{state.question}\n\nDo NOT filter by company/applicant name."
                elif state.extracted_params.get('device_name'):
                    question = f"{state.question}\n\nSearch more broadly without specific device names."
                else:
                    # Broaden date range if that's all we have
                    question = f"{state.question}\n\nExpand the date range or remove date filters."
            elif "rate limit" in state.assessment_reason.lower():
                question = f"{state.question}\n\nRate limited. Use limit=5."
            elif "invalid query" in state.assessment_reason.lower():
                question = f"{state.question}\n\nQuery syntax error. Remove all filters except date."
            else:
                question = f"{state.question}\n\nPrevious attempt failed. Remove the most specific filter and try again."

        # Get plan from LLM
        messages = [
            SystemMessage(content=planning_prompt),
            HumanMessage(content=f"Question: {question}\n\nRAG context:\n{rag_hints if rag_hints else 'None'}")
        ]

        plan_response = self.llm.invoke(messages)

        # Parse planning response
        import json
        try:
            plan_text = plan_response.content
            # Extract JSON from response
            if "```json" in plan_text:
                plan_text = plan_text.split("```json")[1].split("```")[0]
            elif "{" in plan_text:
                plan_text = plan_text[plan_text.find("{"):plan_text.rfind("}")+1]

            plan_data = json.loads(plan_text)

            # Store plan in state
            endpoint = plan_data.get("endpoint", "classification")
            state.search_strategy = plan_data.get("strategy", "exact")
            state.plan = plan_data.get("plan", ["Search with extracted parameters"])

            print(f"[Router] Selected endpoint: {endpoint}")
            print(f"[Router] Strategy: {state.search_strategy}")
            print(f"[Router] Plan: {state.plan[0] if state.plan else 'None'}")

            # Map endpoint to tool name
            endpoint_to_tool = {
                "classification": "classify",
                "510k": "k510_search",
                "pma": "pma_search",
                "recall": "recall_search",
                "maude": "maude_search",
                "udi": "udi_search",
                "rl_search": "rl_search",
            }

            tool_name = endpoint_to_tool.get(endpoint, "classify")
            state.selected_tools = [tool_name]

        except (json.JSONDecodeError, KeyError) as e:
            # Fallback to old behavior
            print(f"[Router] Planning failed, using fallback: {e}")
            selected_endpoint = route(question, self.llm, rag_hints=rag_hints)

            # Handle disambiguation
            if selected_endpoint == "disambiguate":
                print("[Router] Unclear question - defaulting to classification")
                selected_endpoint = "classification"

            # Map endpoint to tool name
            endpoint_to_tool = {
                "classification": "classify",
                "510k": "k510_search",
                "pma": "pma_search",
                "recall": "recall_search",
                "maude": "maude_search",
                "udi": "udi_search",
                "rl_search": "rl_search",
            }

            tool_name = endpoint_to_tool.get(selected_endpoint, "classify")
            state.selected_tools = [tool_name]
            state.search_strategy = "exact"
            state.plan = ["Execute standard search"]

        return state

    def _execute_tools_node(self, state: AgentState) -> AgentState:
        """Execute selected tools with extracted parameters."""
        if not state.selected_tools:
            return state

        # Check if this is a comprehensive safety check
        if state.is_safety_check and not state.safety_results:
            return self._execute_safety_check(state)

        tool_name = state.selected_tools[0]

        # Use query analysis to determine tool selection intelligently
        query_type = state.query_analysis.get("query_type", "")
        primary_entity = state.query_analysis.get("primary_entity", "")
        needs_cross_ref = state.query_analysis.get("needs_cross_reference", False)

        # Check if this needs cross-reference FIRST (regardless of query type)
        if needs_cross_ref:
            # Check if asking about product codes in recalls
            if "product" in state.question.lower() and "recall" in state.question.lower():
                print(f"\n[Tools] Detected cross-reference needed - product codes in recalls")
                return self._handle_product_code_in_recalls(state)

        # Handle different query types
        if query_type in ["COUNT", "AGGREGATION"]:
            # Use probe_count for aggregation
            tool_name = "probe_count"
            print(f"\n[Tools] Detected {query_type} query, using probe_count")
        else:
            print(f"\n[Tools] Executing: {tool_name} for {query_type} query")

        # Extract parameters from question using LLM with confidence scoring
        print(f"[Tools] Extracting parameters...")
        print(f"[Tools] Using strategy: {state.search_strategy}")

        # Map tool to endpoint for field exploration
        endpoint_map = {
            "classify": "classification",
            "k510_search": "510k",
            "pma_search": "pma",
            "recall_search": "recall",
            "maude_search": "maude",
            "udi_search": "udi",
            "rl_search": "rl_search",
        }

        # CEO Resolution #3: RAG-driven field discovery for uncertain extractions
        if hasattr(self.extractor, 'extract_with_confidence'):
            extracted, confidence_scores = self.extractor.extract_with_confidence(state.question)

            # Check for low confidence fields
            low_confidence_fields = [field for field, score in confidence_scores.items()
                                    if score < 0.8 and score > 0]

            if low_confidence_fields:
                print(f"[Tools] Low confidence on fields: {low_confidence_fields}")

                # Use field_explorer and RAG to clarify uncertain fields
                endpoint_name = endpoint_map.get(tool_name, tool_name)
                available_fields = field_explorer(endpoint_name)

                if available_fields:
                    print(f"[Tools] Available fields for {endpoint_name}: {available_fields[:5]}...")

                    # Query RAG for field clarification
                    field_hints = []
                    for uncertain_field in low_confidence_fields:
                        rag_query = f"What field in {endpoint_name} endpoint corresponds to {uncertain_field}?"
                        rag_results = self.retriever.search(rag_query, top_k=1)
                        if rag_results:
                            field_hints.append(rag_results[0].content[:200])

                    if field_hints:
                        print(f"[Tools] RAG clarification: {field_hints[0][:100]}...")

                        # Re-extract with enhanced context (limit to 1 retry)
                        if state.rag_retry_count < 1:
                            enhanced_question = f"{state.question}\n\nField hints: {' '.join(field_hints)}"
                            re_extracted, re_confidence = self.extractor.extract_with_confidence(enhanced_question)

                            # Only update fields that were low confidence AND improved
                            for field in low_confidence_fields:
                                old_conf = confidence_scores.get(field, 0)
                                new_conf = re_confidence.get(field, 0)
                                if new_conf > old_conf:
                                    setattr(extracted, field, getattr(re_extracted, field))
                                    print(f"[Tools] Updated {field} (confidence: {old_conf:.2f} → {new_conf:.2f})")

                            state.rag_retry_count += 1
                            print(f"[Tools] Enhanced extraction complete")
        else:
            # Fallback to regular extraction
            extracted = self.extractor.extract(state.question)

        print(f"[Tools] Extracted params: device_class={extracted.device_class}, recall_class={extracted.recall_class}, dates={extracted.date_start}-{extracted.date_end}, limit={extracted.limit}")

        # Store extracted params in state for assessor
        state.extracted_params = extracted.model_dump()

        # Handle category searches differently
        if state.search_strategy == "category":
            print(f"[Tools] Category search detected")
            # For categories like "orthopedic implants", use partial matching
            # The API will handle partial matches if we pass the category term
            if extracted.device_name:
                print(f"[Tools] Using '{extracted.device_name}' as category search term")

        # Generate Lucene query for provenance
        endpoint_name = endpoint_map.get(tool_name, tool_name)
        lucene_query = generate_lucene_query(extracted, endpoint_name)
        state.lucene_query = lucene_query  # Store for provenance

        result = None
        error = None

        try:
            if tool_name == "classify":
                params = ClassifyParams(
                    product_code=extracted.product_code,
                    device_class=extracted.device_class,
                    device_name=extracted.device_name,
                    limit=extracted.limit,
                )
                result = classify(params, api_key=self.openfda_api_key)

            elif tool_name == "k510_search":
                params = K510SearchParams(
                    k_number=extracted.k_number,
                    applicant=extracted.applicant,
                    device_name=extracted.device_name,
                    product_code=extracted.product_code,
                    decision_date_start=extracted.date_start,
                    decision_date_end=extracted.date_end,
                    limit=extracted.limit,
                )
                result = k510_search(params, api_key=self.openfda_api_key)

            elif tool_name == "pma_search":
                params = PMASearchParams(
                    pma_number=extracted.pma_number,
                    applicant=extracted.applicant,
                    trade_name=extracted.device_name,
                    product_code=extracted.product_code,
                    decision_date_start=extracted.date_start,
                    decision_date_end=extracted.date_end,
                    limit=extracted.limit,
                )
                result = pma_search(params, api_key=self.openfda_api_key)

            elif tool_name == "recall_search":
                params = RecallSearchParams(
                    recall_number=extracted.recall_number,
                    classification=extracted.recall_class,
                    firm_name=extracted.firm_name,
                    product_code=extracted.product_code,
                    event_date_start=extracted.date_start,
                    event_date_end=extracted.date_end,
                    limit=extracted.limit,
                )
                result = recall_search(params, api_key=self.openfda_api_key)

            elif tool_name == "maude_search":
                params = MAUDESearchParams(
                    device_name=extracted.device_name,
                    brand_name=extracted.device_name,
                    product_code=extracted.product_code,
                    event_type=extracted.event_type,
                    date_received_start=extracted.date_start,
                    date_received_end=extracted.date_end,
                    limit=extracted.limit,
                )
                result = maude_search(params, api_key=self.openfda_api_key)

            elif tool_name == "udi_search":
                params = UDISearchParams(
                    brand_name=extracted.device_name,
                    company_name=extracted.firm_name,
                    product_code=extracted.product_code,
                    limit=extracted.limit,
                )
                result = udi_search(params, api_key=self.openfda_api_key)

            elif tool_name == "rl_search":
                params = RLSearchParams(
                    firm_name=extracted.firm_name,
                    fei_number=extracted.fei_number,
                    city=extracted.city,
                    state=extracted.state,
                    country=extracted.country,
                    product_code=extracted.product_code,
                    limit=extracted.limit,
                )
                result = rl_search(params, api_key=self.openfda_api_key)

            elif tool_name == "probe_count":
                # For count queries - determine endpoint based on what we're counting
                # If we have recall_class, use recall endpoint
                if extracted.recall_class:
                    endpoint_name = "enforcement"  # Recall endpoint in API
                elif extracted.device_class:
                    endpoint_name = "classification"
                else:
                    # Fall back to original selected tool if available
                    original_tool = state.selected_tools[0] if state.selected_tools else "classification"
                    endpoint_name = endpoint_map.get(original_tool, "classification")

                # Build search query from extracted params
                filters = []
                if extracted.device_class:
                    filters.append(f'device_class:{extracted.device_class}')
                if extracted.product_code:
                    filters.append(f'product_code:{extracted.product_code}')
                if extracted.recall_class:
                    filters.append(f'classification:"{extracted.recall_class}"')
                if extracted.date_start and extracted.date_end:
                    # Add date filter for enforcement/recall queries
                    if endpoint_name in ["enforcement", "recall"]:
                        filters.append(f'recall_initiation_date:[{extracted.date_start} TO {extracted.date_end}]')
                    else:
                        filters.append(f'date:[{extracted.date_start} TO {extracted.date_end}]')

                search_query = " AND ".join(filters) if filters else None

                # Use appropriate field for counting based on endpoint
                # Note: Use .exact fields for text aggregations
                # Don't trust extracted.count_field as it doesn't know the correct API field names
                if endpoint_name == "classification":
                    count_field = "device_class"
                elif endpoint_name == "enforcement":
                    # Use .exact field for aggregation
                    count_field = "classification.exact"
                elif endpoint_name == "recall":
                    # Recall is actually the enforcement endpoint
                    count_field = "classification.exact"
                else:
                    count_field = "openfda.product_code.exact"

                print(f"[Tools] Count endpoint_name: {endpoint_name}, using field: {count_field}")

                params = ProbeCountParams(
                    endpoint=endpoint_name,
                    field=count_field,
                    search=search_query,
                    limit=extracted.limit or 100,
                )
                print(f"[Tools] Count query: endpoint={endpoint_name}, field={count_field}, search={search_query}")
                count_result = probe_count(params, api_key=self.openfda_api_key)
                print(f"[Tools] Count result: {count_result}")

                # Convert count result to OpenFDAResponse format
                result = type('obj', (object,), {
                    'model_dump': lambda self: count_result,
                    'error': count_result.get('error')
                })()

            else:
                error = f"Unknown tool: {tool_name}"

        except Exception as e:
            error = str(e)
            print(f"[Tools] Error: {error}")

        # Record tool call
        tool_call = ToolCall(
            tool_name=tool_name,
            params={"info": "params extracted from question"},
            result=result.model_dump() if result else None,
            error=error,
        )
        state.tool_calls.append(tool_call)
        state.current_result = result.model_dump() if result else {"error": error}

        result_count = len(state.current_result.get("results", [])) if state.current_result else 0
        print(f"[Tools] Retrieved {result_count} results")

        return state

    def _execute_safety_check(self, state: AgentState) -> AgentState:
        """Execute comprehensive safety check across multiple endpoints."""
        print("\n[Tools] Executing comprehensive safety check...")

        # Extract parameters once
        extracted = self.extractor.extract(state.question)
        product_code = extracted.product_code

        if not product_code:
            print("[Tools] No product code found for safety check")
            state.current_result = {"error": "Product code required for safety check"}
            return state

        print(f"[Tools] Checking safety data for product code: {product_code}")

        # Import tools
        from tools.recall import RecallSearchParams, recall_search
        from tools.maude import MAUDESearchParams, maude_search
        from tools.classification import ClassifyParams, classify

        # 1. Check recalls
        print("[Tools] Checking recalls...")
        recall_params = RecallSearchParams(
            product_code=product_code,
            limit=10
        )
        recall_result = recall_search(recall_params, api_key=self.openfda_api_key)
        state.safety_results["recalls"] = recall_result.model_dump()

        # 2. Check MAUDE adverse events
        print("[Tools] Checking adverse events...")
        maude_params = MAUDESearchParams(
            product_code=product_code,
            limit=10
        )
        maude_result = maude_search(maude_params, api_key=self.openfda_api_key)
        state.safety_results["adverse_events"] = maude_result.model_dump()

        # 3. Get classification details
        print("[Tools] Getting device classification...")
        classify_params = ClassifyParams(
            product_code=product_code,
            limit=1
        )
        classify_result = classify(classify_params, api_key=self.openfda_api_key)
        state.safety_results["classification"] = classify_result.model_dump()

        # 4. Check for similar product codes if no results
        recall_count = len(state.safety_results["recalls"].get("results", []))
        maude_count = len(state.safety_results["adverse_events"].get("results", []))

        if recall_count == 0 and maude_count == 0:
            print("[Tools] No direct results, checking related devices...")
            # Get device type from classification
            class_results = state.safety_results["classification"].get("results", [])
            if class_results:
                device_name = class_results[0].get("device_name", "")
                # Search for recalls by device type
                recall_params_broad = RecallSearchParams(
                    product_description=device_name[:30],  # Use first part of device name
                    limit=5
                )
                related_recalls = recall_search(recall_params_broad, api_key=self.openfda_api_key)
                state.safety_results["related_recalls"] = related_recalls.model_dump()

        # Combine results for assessment
        state.current_result = {
            "results": state.safety_results,
            "meta": {"safety_check": True}
        }

        print(f"[Tools] Safety check complete - Recalls: {recall_count}, Events: {maude_count}")
        return state

    def _handle_product_code_in_recalls(self, state: AgentState) -> AgentState:
        """
        Handle queries asking about specific product code in recalls.
        Since recalls don't contain product codes, check if the product code exists
        and then search for recalls by device type.
        """
        print("\n[Tools] Handling product code search in recalls...")

        # Extract product code
        extracted = self.extractor.extract(state.question)
        product_code = extracted.product_code

        if not product_code:
            state.current_result = {"error": "No product code found in query"}
            return state

        print(f"[Tools] Checking product code: {product_code}")

        # Import tools
        from tools.classification import ClassifyParams, classify
        from tools.recall import RecallSearchParams, recall_search

        # First, check if product code exists and get device info
        classify_params = ClassifyParams(
            product_code=product_code,
            limit=1
        )
        classify_result = classify(classify_params, api_key=self.openfda_api_key)

        if classify_result.error or not classify_result.results:
            state.current_result = {
                "error": f"Product code {product_code} not found in FDA database",
                "results": []
            }
            return state

        # Get device info
        device_info = classify_result.results[0]
        device_name = device_info.get("device_name", "")
        device_class = device_info.get("device_class", "")

        print(f"[Tools] Found device: {device_name} (Class {device_class})")

        # Search for recalls by device description
        # Extract year if specified
        year = state.query_analysis.get("time_constraints", {}).get("year")
        if year and str(year).isdigit() and int(year) >= 2025:
            # No recalls in 2025 yet
            state.current_result = {
                "results": [],
                "meta": {
                    "product_code": product_code,
                    "device_name": device_name,
                    "device_class": device_class,
                    "message": f"No recalls have been reported in {year} yet (as of January 2025). Showing recent recalls instead."
                }
            }
            year = 2024

        # Search for recalls
        if year:
            event_start = f"{year}0101"
            event_end = f"{year}1231"
        else:
            # Default to last 2 years
            event_start = "20230101"
            event_end = "20241231"

        # Search by device name (first part)
        search_term = device_name[:30] if device_name else None
        if search_term:
            recall_params = RecallSearchParams(
                product_description=search_term,
                event_date_start=event_start,
                event_date_end=event_end,
                limit=10
            )
            recall_result = recall_search(recall_params, api_key=self.openfda_api_key)

            if not recall_result.error and recall_result.results:
                state.current_result = {
                    "results": recall_result.results,
                    "meta": {
                        "product_code": product_code,
                        "device_name": device_name,
                        "device_class": device_class,
                        "search_method": "device_name_match",
                        "time_period": f"{event_start} to {event_end}",
                        "note": f"Showing recalls for devices matching '{device_name}' (Product Code {product_code})"
                    }
                }
            else:
                state.current_result = {
                    "results": [],
                    "meta": {
                        "product_code": product_code,
                        "device_name": device_name,
                        "device_class": device_class,
                        "message": f"No recalls found for {device_name} (Product Code {product_code}) in the specified time period"
                    }
                }
        else:
            state.current_result = {
                "error": "Could not search for recalls - device name not available",
                "results": []
            }

        return state

    def _handle_product_code_aggregation(self, state: AgentState) -> AgentState:
        """
        Handle queries asking for product codes with recalls.

        This is impossible directly because recalls don't contain product codes.
        Solution: Get recalls first, then look up product codes from classification.
        """
        print("\n[Tools] Handling product code aggregation with cross-reference...")

        # Extract time constraints from query analysis
        time_constraints = state.query_analysis.get("time_constraints", {})
        year = time_constraints.get("year")

        # Build explanation for user
        explanation = []

        # Check if asking for future data
        if year and str(year).isdigit() and int(year) >= 2025:
            explanation.append(f"Note: No recalls have been reported in {year} yet (current data as of January 2025).")
            explanation.append("Showing recent recalls from 2024 instead.")
            year = 2024

        # Import tools
        from tools.recall import RecallSearchParams, recall_search
        from tools.classification import ClassifyParams, classify

        # Get recalls for the time period
        if year:
            event_start = f"{year}0101"
            event_end = f"{year}1231"
        else:
            # Default to last 2 years
            event_start = "20230101"
            event_end = "20241231"

        print(f"[Tools] Searching recalls from {event_start} to {event_end}...")
        recall_params = RecallSearchParams(
            event_date_start=event_start,
            event_date_end=event_end,
            limit=100  # Get more to find patterns
        )
        recall_result = recall_search(recall_params, api_key=self.openfda_api_key)

        if recall_result.error or not recall_result.results:
            state.current_result = {
                "error": f"No recalls found for the specified time period ({event_start} to {event_end})",
                "explanation": explanation
            }
            return state

        print(f"[Tools] Found {len(recall_result.results)} recalls")

        # Extract device types from product descriptions
        device_types = set()
        for recall in recall_result.results:
            desc = recall.get("product_description", "")
            # Extract first meaningful part of description
            if desc:
                # Take first 30 chars or until comma/semicolon
                device_type = desc[:30].split(',')[0].split(';')[0].strip()
                device_types.add(device_type)

        print(f"[Tools] Extracted {len(device_types)} unique device types")

        # Look up product codes for these device types
        product_codes_found = {}
        for device_type in list(device_types)[:20]:  # Limit to avoid too many API calls
            classify_params = ClassifyParams(
                device_name=device_type,
                limit=1
            )
            classify_result = classify(classify_params, api_key=self.openfda_api_key)

            if not classify_result.error and classify_result.results:
                for result in classify_result.results:
                    pc = result.get("product_code")
                    if pc:
                        if pc not in product_codes_found:
                            product_codes_found[pc] = {
                                "device_name": result.get("device_name", "Unknown"),
                                "device_class": result.get("device_class", "Unknown"),
                                "count": 0
                            }
                        product_codes_found[pc]["count"] += 1

        print(f"[Tools] Found {len(product_codes_found)} product codes")

        # Format results
        if product_codes_found:
            results_list = []
            for pc, info in product_codes_found.items():
                results_list.append({
                    "product_code": pc,
                    "device_name": info["device_name"],
                    "device_class": info["device_class"],
                    "recall_count": info["count"]
                })

            state.current_result = {
                "results": results_list,
                "meta": {
                    "total_recalls": len(recall_result.results),
                    "product_codes_found": len(product_codes_found),
                    "time_period": f"{event_start} to {event_end}",
                    "explanation": explanation
                }
            }
        else:
            state.current_result = {
                "error": "Could not determine product codes from recall descriptions",
                "explanation": explanation
            }

        return state

    def _assessor_node(self, state: AgentState) -> AgentState:
        """
        Assess if current results satisfy the question.

        CEO Resolution #5: Intelligent error recovery with actionable retry messages.
        Uses answer_assessor utility to validate params match question intent.
        """
        print(f"\n[Assessor] Checking answer sufficiency...")

        # Handle safety check results specially
        if state.is_safety_check and state.safety_results:
            # Safety check is always sufficient if we got classification data
            class_results = state.safety_results.get("classification", {}).get("results", [])
            if class_results:
                state.is_sufficient = True
                state.assessment_reason = "Comprehensive safety check completed"
                print(f"[Assessor] Safety check sufficient")
                return state

        # Handle cross-reference aggregation results
        if state.query_analysis.get("needs_cross_reference"):
            if state.current_result and not state.current_result.get("error"):
                state.is_sufficient = True
                state.assessment_reason = "Cross-reference query completed"
                print(f"[Assessor] Cross-reference sufficient")
                return state

        # Check for errors first with intelligent recovery suggestions
        if state.current_result and state.current_result.get("error"):
            error_msg = str(state.current_result['error']).lower()

            # Provide actionable recovery suggestions based on error type
            if "404" in error_msg or "not found" in error_msg:
                # Entity not found - suggest broader search
                if state.extracted_params:
                    specific_fields = [k for k, v in state.extracted_params.items()
                                     if v and k in ['k_number', 'pma_number', 'product_code']]
                    if specific_fields:
                        state.assessment_reason = (
                            f"Specific identifier not found ({specific_fields[0]}). "
                            "Try removing the identifier or using a broader search term."
                        )
                    else:
                        state.assessment_reason = "No results found. Try broader search terms or different date ranges."
                else:
                    state.assessment_reason = "No results found. Try rephrasing the question."

            elif "429" in error_msg or "rate limit" in error_msg:
                state.assessment_reason = "API rate limit exceeded. Waiting before retry..."
                # In production, implement exponential backoff here

            elif "500" in error_msg or "internal server" in error_msg:
                state.assessment_reason = "FDA server error. Trying alternative endpoint or cached results..."

            elif "400" in error_msg or "bad request" in error_msg:
                # Invalid query syntax
                state.assessment_reason = (
                    f"Invalid query syntax. Simplifying search parameters... "
                    f"(Query: {state.lucene_query})"
                )

            elif "timeout" in error_msg:
                state.assessment_reason = "Request timeout. Reducing result limit and retrying..."

            else:
                # Generic error
                state.assessment_reason = f"API error: {state.current_result['error']}. Trying alternative approach..."

            state.is_sufficient = False
            print(f"[Assessor] Error detected: {state.assessment_reason}")
            return state

        result_count = len(state.current_result.get("results", [])) if state.current_result else 0

        # Check plan progress
        if state.plan and len(state.plan) > 0:
            current_step = state.plan[state.current_plan_step] if state.current_plan_step < len(state.plan) else "Complete"
            print(f"[Assessor] Plan step {state.current_plan_step + 1}/{len(state.plan)}: {current_step}")

        # For category searches, be more lenient with results
        if state.search_strategy == "category" and result_count > 0:
            state.is_sufficient = True
            state.assessment_reason = f"Category search returned {result_count} results"
            print(f"[Assessor] Category search successful with {result_count} results")
        elif state.extracted_params:
            # Use answer_assessor to validate params match question
            from agent.extractor import ExtractedParams

            extracted = ExtractedParams(**state.extracted_params)
            params_str = extracted_params_to_query_string(extracted)

            # Prepare assessment parameters
            from tools.utils import AnswerAssessorParams, answer_assessor

            assessment_params = AnswerAssessorParams(
                question=state.question,
                search_query=params_str,
                result_count=result_count,
                date_filter_present=bool(extracted.date_start or extracted.date_end),
                class_filter_present=bool(extracted.device_class or extracted.recall_class),
            )

            assessment = answer_assessor(assessment_params)
            state.is_sufficient = assessment.sufficient
            state.assessment_reason = assessment.reason

            # Check if we should try next plan step
            if not state.is_sufficient and state.plan and state.current_plan_step < len(state.plan) - 1:
                state.current_plan_step += 1
                state.assessment_reason = f"Moving to plan step {state.current_plan_step + 1}: {state.plan[state.current_plan_step]}"
                print(f"[Assessor] Advancing to next plan step")
        else:
            # Fallback: accept if no errors
            state.is_sufficient = True
            state.assessment_reason = f"Retrieved {result_count} results (no param validation)"

        print(f"[Assessor] Sufficient: {state.is_sufficient} - {state.assessment_reason}")

        return state

    def _should_retry(self, state: AgentState) -> str:
        """Decide whether to retry or proceed to answer."""
        if state.is_sufficient:
            return "answer"

        # Check for impossible queries early
        query_analysis = state.query_analysis or {}
        if query_analysis.get("needs_cross_reference") and state.retry_count > 0:
            print("[Assessor] Impossible direct query detected - providing explanation")
            return "answer"

        # Don't retry if we've detected a future date with no data
        if state.current_result and "No recalls have been reported" in str(state.current_result.get("explanation", [])):
            print("[Assessor] Future date with no data - providing explanation")
            return "answer"

        # Check if we're stuck on the same error
        if state.retry_count > 1 and state.assessment_reason:
            # If we keep getting the same error, stop
            if "not found" in state.assessment_reason.lower():
                print("[Assessor] Persistent not found error - stopping retries")
                return "answer"

        if state.retry_count >= self.MAX_RETRIES:
            print(f"[Assessor] Max retries ({self.MAX_RETRIES}) reached")
            return "answer"  # Give up, return what we have

        # Increment retry count BEFORE returning retry
        state.retry_count += 1
        return "retry"

    def _answer_node(self, state: AgentState) -> AgentState:
        """Generate final answer with actual FDA data formatted for analysts."""
        print(f"\n[Answer] Generating final response...")

        # Handle comprehensive safety check results
        if state.is_safety_check and state.safety_results:
            state.answer = self._format_safety_check_results(state.safety_results, state.question)
            state.provenance = {
                "endpoints": ["classification", "recall", "maude"],
                "product_code": self.extractor.extract(state.question).product_code,
                "timestamp": datetime.now().isoformat(),
                "safety_check": True
            }
            return state

        # Handle cross-reference aggregation results
        if state.query_analysis.get("needs_cross_reference") and state.current_result:
            state.answer = self._format_cross_reference_results(state.current_result, state.question)
            state.provenance = {
                "endpoints": ["recall", "classification"],
                "timestamp": datetime.now().isoformat(),
                "cross_reference": True
            }
            return state

        if not state.current_result or state.current_result.get("error"):
            state.answer = f"Unable to retrieve data: {state.current_result.get('error', 'Unknown error')}"
            return state

        results = state.current_result.get("results", [])
        meta = state.current_result.get("meta", {})
        endpoint = state.selected_tools[0] if state.selected_tools else "unknown"

        # Check if this is a count query result
        is_count_query = (results and
                         len(results) > 0 and
                         isinstance(results[0], dict) and
                         'count' in results[0])

        # Build formatted answer based on endpoint
        if not results:
            state.answer = "No results found for this query."
        elif is_count_query:
            state.answer = self._format_count_results(results, state.question)
        elif endpoint == "recall_search":
            state.answer = self._format_recalls(results)
        elif endpoint == "k510_search":
            state.answer = self._format_510k(results)
        elif endpoint == "pma_search":
            state.answer = self._format_pma(results)
        elif endpoint == "maude_search":
            state.answer = self._format_maude(results)
        elif endpoint == "classify":
            state.answer = self._format_classification(results)
        elif endpoint == "rl_search":
            state.answer = self._format_registration(results)
        else:
            state.answer = f"Found {len(results)} results."

        # Add provenance (CEO Resolution #4: Include actual Lucene query)
        state.provenance = {
            "endpoint": state.selected_tools[0] if state.selected_tools else "unknown",
            "filters": "auto-generated",
            "lucene_query": state.lucene_query,  # Actual query used
            "last_updated": meta.get("last_updated", "unknown"),
            "result_count": len(results),
            "timestamp": datetime.now().isoformat(),  # ALCOA+ compliance
        }

        print(f"[Answer] Complete!")

        return state

    def _format_count_results(self, results: List[Dict], question: str) -> str:
        """Format count/aggregation results for FDA analyst review."""
        total = sum(r.get('count', 0) for r in results)

        # Determine what was being counted from the question
        if "recall" in question.lower():
            item_type = "recalls"
        elif "510k" in question.lower():
            item_type = "510(k) clearances"
        elif "pma" in question.lower():
            item_type = "PMA approvals"
        elif "adverse" in question.lower() or "maude" in question.lower():
            item_type = "adverse events"
        elif "device" in question.lower():
            item_type = "devices"
        else:
            item_type = "records"

        output = f"Total count: {total:,} {item_type}\n\n"

        # Show breakdown if there are multiple categories
        if len(results) > 1:
            output += "Breakdown by category:\n"
            for r in results[:10]:  # Show top 10
                term = r.get('term', 'Unknown')
                count = r.get('count', 0)
                output += f"  • {term}: {count:,}\n"

            if len(results) > 10:
                output += f"  ... and {len(results) - 10} more categories\n"

        return output

    def _format_safety_check_results(self, safety_results: Dict, question: str) -> str:
        """Format comprehensive safety check results for FDA analyst review."""
        product_code = self.extractor.extract(question).product_code

        # Get classification info
        class_results = safety_results.get("classification", {}).get("results", [])
        device_info = class_results[0] if class_results else {}
        device_name = device_info.get("device_name", "Unknown Device")
        device_class = device_info.get("device_class", "Unknown")
        regulation = device_info.get("regulation_number", "N/A")

        # Count results
        recall_results = safety_results.get("recalls", {}).get("results", [])
        maude_results = safety_results.get("adverse_events", {}).get("results", [])
        related_recalls = safety_results.get("related_recalls", {}).get("results", [])

        output = f"""## FDA Safety Analysis Report for Product Code: {product_code}

### Executive Summary
Product Code {product_code} corresponds to **{device_name}** (Class {device_class}, Regulation {regulation}).

**Safety Findings:**
- Direct Recalls: {len(recall_results)} found
- Adverse Events (MAUDE): {len(maude_results)} found
- Related Device Recalls: {len(related_recalls)} found

### 1. Device Classification Details
- **Product Code:** {product_code}
- **Device Name:** {device_name}
- **Device Class:** {device_class}
- **Regulation Number:** {regulation}
- **Medical Specialty:** {device_info.get("medical_specialty_description", "N/A")}
- **Review Panel:** {device_info.get("review_panel", "N/A")}

### 2. Recall History
"""

        if recall_results:
            output += f"Found {len(recall_results)} recall(s) for product code {product_code}:\n\n"
            for i, recall in enumerate(recall_results[:5], 1):
                output += f"{i}. **Recall {recall.get('recall_number', 'N/A')}**\n"
                output += f"   - Classification: {recall.get('classification', 'N/A')}\n"
                output += f"   - Firm: {recall.get('recalling_firm', 'N/A')}\n"
                output += f"   - Product: {recall.get('product_description', 'N/A')[:100]}\n"
                output += f"   - Reason: {recall.get('reason_for_recall', 'N/A')[:100]}\n"
                output += f"   - Date Initiated: {recall.get('recall_initiation_date', 'N/A')}\n\n"
        else:
            output += f"**No recalls found** for product code {product_code}.\n\n"

        output += "### 3. Adverse Event Reports (MAUDE)\n"
        if maude_results:
            output += f"Found {len(maude_results)} adverse event(s):\n\n"
            for i, event in enumerate(maude_results[:5], 1):
                output += f"{i}. **Event {event.get('report_number', 'N/A')}**\n"
                output += f"   - Date: {event.get('date_received', 'N/A')}\n"
                output += f"   - Event Type: {event.get('event_type', 'N/A')}\n"
                output += f"   - Manufacturer: {event.get('manufacturer_name', 'N/A')}\n\n"
        else:
            output += f"**No adverse events found** in MAUDE database for product code {product_code}.\n\n"

        # 4. Related Device Analysis
        if not recall_results and not maude_results and related_recalls:
            output += f"\n### Related Devices (Similar Category)\n"
            output += f"While no direct issues found for {product_code}, "
            output += f"found {len(related_recalls)} recall(s) for similar {device_name} devices:\n\n"
            for i, recall in enumerate(related_recalls[:3], 1):
                output += f"{i}. {recall.get('product_description', 'N/A')[:80]}\n"
                output += f"   - Classification: {recall.get('classification', 'N/A')}\n"
                output += f"   - Firm: {recall.get('recalling_firm', 'N/A')}\n\n"

        # 5. Recommendations
        output += "\n### Recommendations for Further Investigation\n"

        if not recall_results and not maude_results:
            output += f"✅ **Low Risk Profile:** No direct safety issues identified for {product_code}.\n"
            output += "- Consider routine monitoring of MAUDE database for emerging issues\n"
            output += "- Review manufacturer quality systems during next inspection\n"
        else:
            output += f"⚠️ **Elevated Risk Profile:** Safety issues identified for {product_code}.\n"
            output += "- Review all recalled units for compliance with corrective actions\n"
            output += "- Analyze adverse event trends for patterns\n"
            output += "- Consider focused inspection of manufacturing facilities\n"

        output += f"\n### Search Methodology\n"
        output += f"- **Databases Searched:** FDA Recalls (Enforcement), MAUDE (Adverse Events), Device Classification\n"
        output += f"- **Search Parameter:** product_code:{product_code}\n"
        output += f"- **Date Range:** All available records\n"
        output += f"- **Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"

        return output

    def _format_cross_reference_results(self, result: Dict, question: str) -> str:
        """Format cross-reference aggregation results for FDA analyst review."""
        if result.get("error"):
            explanation = result.get("explanation", [])
            if explanation:
                return "\n".join(explanation) + f"\n\n{result['error']}"
            return result['error']

        results_list = result.get("results", [])
        meta = result.get("meta", {})
        explanation = meta.get("explanation", [])

        output = "## Product Codes with Recalls\n\n"

        # Add any explanations (like year adjustments)
        if explanation:
            for note in explanation:
                output += f"**{note}**\n"
            output += "\n"

        if results_list:
            output += f"Found {len(results_list)} product codes associated with recalls "
            output += f"({meta.get('time_period', 'recent period')}):\n\n"

            for item in results_list:
                output += f"### {item['product_code']} - Class {item['device_class']}\n"
                output += f"- **Device:** {item['device_name']}\n"
                output += f"- **Associated Recalls:** {item['recall_count']}\n\n"

            output += f"\n**Summary:**\n"
            output += f"- Total recalls analyzed: {meta.get('total_recalls', 'N/A')}\n"
            output += f"- Product codes identified: {meta.get('product_codes_found', len(results_list))}\n"
            output += f"- Time period: {meta.get('time_period', 'N/A')}\n"
        else:
            output += "No product codes could be determined from the recall data.\n"
            output += "This may indicate that no recalls occurred in the specified time period.\n"

        output += f"\n**Note:** Product codes are determined by cross-referencing recall descriptions "
        output += "with the device classification database, as recall records do not directly contain product codes.\n"

        return output

    def _format_recalls(self, results: List[Dict]) -> str:
        """Format recall results for FDA analyst review."""
        count = len(results)
        output = f"Found {count} recall{'s' if count != 1 else ''}:\n\n"

        for i, r in enumerate(results[:10], 1):  # Show up to 10 results
            output += f"{i}. Recall {r.get('recall_number', 'N/A')} - {r.get('classification', 'N/A')}\n"
            output += f"   Company: {r.get('recalling_firm', 'N/A')}\n"
            output += f"   Product: {r.get('product_description', 'N/A')[:200]}...\n" if len(r.get('product_description', '')) > 200 else f"   Product: {r.get('product_description', 'N/A')}\n"
            output += f"   Reason: {r.get('reason_for_recall', 'N/A')[:150]}...\n" if len(r.get('reason_for_recall', '')) > 150 else f"   Reason: {r.get('reason_for_recall', 'N/A')}\n"
            output += f"   Date Initiated: {r.get('recall_initiation_date', 'N/A')}\n"
            output += f"   Status: {r.get('status', 'N/A')}\n\n"

        if count > 10:
            output += f"... and {count - 10} more recalls.\n"

        return output

    def _format_510k(self, results: List[Dict]) -> str:
        """Format 510k clearance results for FDA analyst review."""
        count = len(results)
        output = f"Found {count} 510(k) clearance{'s' if count != 1 else ''}:\n\n"

        for i, r in enumerate(results[:10], 1):
            output += f"{i}. {r.get('k_number', 'N/A')} - {r.get('applicant', 'N/A')}\n"
            output += f"   Device: {r.get('device_name', 'N/A')}\n"
            output += f"   Product Code: {r.get('product_code', 'N/A')}\n"
            output += f"   Review Panel: {r.get('review_panel', 'N/A')}\n"
            output += f"   Decision Date: {r.get('decision_date', 'N/A')}\n"
            output += f"   Clearance Type: {r.get('clearance_type', 'N/A')}\n\n"

        if count > 10:
            output += f"... and {count - 10} more 510(k) clearances.\n"

        return output

    def _format_pma(self, results: List[Dict]) -> str:
        """Format PMA approval results for FDA analyst review."""
        count = len(results)
        output = f"Found {count} PMA approval{'s' if count != 1 else ''}:\n\n"

        for i, r in enumerate(results[:10], 1):
            output += f"{i}. {r.get('pma_number', 'N/A')} - {r.get('applicant', 'N/A')}\n"
            output += f"   Trade Name: {r.get('trade_name', 'N/A')}\n"
            output += f"   Generic Name: {r.get('generic_name', 'N/A')}\n"
            output += f"   Product Code: {r.get('product_code', 'N/A')}\n"
            output += f"   Advisory Committee: {r.get('advisory_committee', 'N/A')}\n"
            output += f"   Decision Date: {r.get('decision_date', 'N/A')}\n"
            output += f"   Decision Code: {r.get('decision_code', 'N/A')}\n\n"

        if count > 10:
            output += f"... and {count - 10} more PMA approvals.\n"

        return output

    def _format_maude(self, results: List[Dict]) -> str:
        """Format adverse event results for FDA analyst review."""
        count = len(results)
        output = f"Found {count} adverse event report{'s' if count != 1 else ''}:\n\n"

        for i, r in enumerate(results[:10], 1):
            output += f"{i}. Report #{r.get('mdr_report_key', 'N/A')} - {r.get('date_of_event', 'N/A')}\n"
            output += f"   Manufacturer: {r.get('manufacturer_d_name', 'N/A')}\n"
            output += f"   Device: {r.get('device', [{}])[0].get('brand_name', 'N/A') if r.get('device') else 'N/A'}\n"
            output += f"   Event Type: {r.get('event_type', 'N/A')}\n"

            # Patient outcomes (if any)
            patient = r.get('patient', [{}])[0] if r.get('patient') else {}
            outcomes = []
            if patient.get('patient_outcome'):
                outcomes = patient['patient_outcome']
            if outcomes:
                output += f"   Patient Outcome: {', '.join(outcomes)}\n"

            # Event description (truncated)
            for text in r.get('mdr_text', []):
                if text.get('text_type_code') == 'Description of Event or Problem':
                    desc = text.get('text', 'N/A')[:200]
                    output += f"   Description: {desc}...\n" if len(desc) >= 200 else f"   Description: {desc}\n"
                    break

            output += "\n"

        if count > 10:
            output += f"... and {count - 10} more adverse event reports.\n"

        return output

    def _format_classification(self, results: List[Dict]) -> str:
        """Format device classification results for FDA analyst review."""
        count = len(results)
        output = f"Found {count} device classification{'s' if count != 1 else ''}:\n\n"

        for i, r in enumerate(results[:10], 1):
            output += f"{i}. {r.get('product_code', 'N/A')} - Class {r.get('device_class', 'N/A')}\n"
            output += f"   Device Name: {r.get('device_name', 'N/A')}\n"
            output += f"   Regulation Number: {r.get('regulation_number', 'N/A')}\n"
            output += f"   Medical Specialty: {r.get('medical_specialty_description', 'N/A')}\n"
            output += f"   Review Panel: {r.get('review_panel', 'N/A')}\n"

            # Premarket requirements
            if r.get('submission_type_id'):
                sub_types = []
                for st in str(r.get('submission_type_id', '')).split(','):
                    st = st.strip()
                    if st == '1':
                        sub_types.append('510(k)')
                    elif st == '2':
                        sub_types.append('510(k) Exempt')
                    elif st == '3':
                        sub_types.append('PMA')
                    elif st == '4':
                        sub_types.append('PDP')
                    elif st == '5':
                        sub_types.append('HDE')
                if sub_types:
                    output += f"   Premarket Submission: {', '.join(sub_types)}\n"

            output += "\n"

        if count > 10:
            output += f"... and {count - 10} more device classifications.\n"

        return output

    def _format_registration(self, results: List[Dict]) -> str:
        """Format registration and listing results for FDA analyst review."""
        count = len(results)
        output = f"Found {count} registration/listing{'s' if count != 1 else ''}:\n\n"

        for i, r in enumerate(results[:10], 1):
            # Registration info
            reg = r.get('registration', {})
            output += f"{i}. {reg.get('name', 'N/A')}\n"
            output += f"   Registration Number: {reg.get('registration_number', 'N/A')}\n"
            output += f"   Owner/Operator: {reg.get('owner_operator_name', 'N/A')}\n"
            output += f"   Status: {reg.get('status_code', 'N/A')}\n"

            # Address
            address = reg.get('address', {})
            if address:
                output += f"   Location: {address.get('city', '')}, {address.get('state', '')} {address.get('country', '')}\n"

            # Product codes if available
            products = r.get('products', [])
            if products:
                codes = [p.get('product_code', '') for p in products[:3] if p.get('product_code')]
                if codes:
                    output += f"   Product Codes: {', '.join(codes)}"
                    if len(products) > 3:
                        output += f" (and {len(products) - 3} more)"
                    output += "\n"

            output += "\n"

        if count > 10:
            output += f"... and {count - 10} more registrations.\n"

        return output

    def query(self, question: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run agent on a question.

        Args:
            question: User question
            dry_run: If True, skip API calls (placeholder for future implementation)

        Returns:
            Dict with answer, provenance, and execution details
        """
        initial_state = AgentState(question=question)
        final_state_dict = self.graph.invoke(
            initial_state.model_dump(),
            {"recursion_limit": 10}
        )

        # LangGraph returns dict, convert back to AgentState for easier access
        final_state = AgentState(**final_state_dict)

        # Determine selected endpoint for explain mode
        endpoint_map = {
            "classify": "classification",
            "k510_search": "510k",
            "pma_search": "pma",
            "recall_search": "recall",
            "maude_search": "maude",
            "udi_search": "udi",
            "rl_search": "rl_search",
        }
        selected_tool = final_state.selected_tools[0] if final_state.selected_tools else "unknown"
        selected_endpoint = endpoint_map.get(selected_tool, selected_tool)

        return {
            "question": final_state.question,
            "answer": final_state.answer,
            "provenance": final_state.provenance,
            "tool_calls": [tc if isinstance(tc, dict) else tc.model_dump() for tc in final_state.tool_calls],
            "retry_count": final_state.retry_count,
            "is_sufficient": final_state.is_sufficient,
            # Explain mode metadata
            "selected_endpoint": selected_endpoint,
            "extracted_params": final_state.extracted_params,
            "assessor_reason": final_state.assessment_reason,
            # Note: RAG docs not currently tracked in state, would need to add to state
            "rag_docs": [],  # Placeholder - would need to add to state
        }
