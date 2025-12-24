"""
FastAPI endpoints for FDA Intelligence Agent with SSE support
"""

import json
import os
import time
from collections import Counter
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from langgraph.checkpoint.memory import MemorySaver

from .tools import DeviceResolver
from .config import get_config
from .agent import FDAAgent, QueryRouter
from .llm_factory import LLMFactory
from .openfda_client import OpenFDAClient
from .models.responses import AgentResponse as StructuredAgentResponse
from .usage_tracker import get_usage_tracker, UsageTracker

logger = logging.getLogger(__name__)

USAGE_EXTEND_SECRET = os.environ.get("FDA_USAGE_EXTEND_SECRET", "changeme")
USAGE_USER_PASSPHRASE = os.environ.get("FDA_USAGE_PASSPHRASE", "")
USAGE_PASSPHRASE_EXTENSION = float(os.environ.get("FDA_USAGE_PASSPHRASE_EXTENSION", "5.0"))

# Global instances
router = QueryRouter()
shared_checkpointer = MemorySaver()


def get_client_ip(request: Request) -> str:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


app = FastAPI(
    title="FDA Intelligence API",
    description="AI-powered FDA regulatory data analysis",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def usage_limit_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/agent/") and not path.startswith("/api/agent/providers"):
        try:
            tracker = get_usage_tracker()
            ip = get_client_ip(request)
            allowed, used, limit = tracker.check_limit(ip)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "usage_limit_exceeded",
                        "used": round(used, 4),
                        "limit": round(limit, 2),
                        "message": "You have exceeded your usage limit. Contact the developer to extend your quota.",
                        "contact": "Contact developer to extend limit"
                    }
                )
        except Exception as e:
            logger.warning(f"Usage check failed: {e}")
    return await call_next(request)


@app.get("/api/health")
async def health_check(
    llm: bool = Query(default=False, description="Check LLM reachability"),
    provider: str = Query(default="openrouter"),
    model: Optional[str] = Query(default=None),
):
    status = {"status": "healthy", "timestamp": datetime.now().isoformat()}

    if not llm:
        return status

    llm_status: Dict[str, Any] = {
        "provider": provider,
        "model": model,
        "reachable": False,
        "checked": True,
    }

    try:
        client = LLMFactory.create(provider=provider, model=model, temperature=0.0, max_tokens=1)
        client.invoke("ping")
        llm_status["reachable"] = True
    except Exception as e:
        llm_status["error"] = str(e)

    status["llm"] = llm_status
    return status


def _map_recalls_to_events(recalls: list[dict]) -> list[dict]:
    mapped = []
    for recall in recalls:
        mapped.append({
            "report_number": recall.get("recall_number") or recall.get("event_id"),
            "date_received": recall.get("recall_initiation_date"),
            "event_type": "Recall",
            "device": [{
                "brand_name": recall.get("product_description"),
                "generic_name": recall.get("product_description"),
                "manufacturer_d_name": recall.get("recalling_firm"),
                "manufacturer_name": recall.get("recalling_firm"),
            }],
            "recall": recall,
        })
    return mapped


def _compute_event_stats(events: list[dict]) -> tuple[Counter, Counter, list[str], str]:
    event_types = Counter()
    manufacturers = Counter()
    dates = []

    for event in events:
        event_types[event.get("event_type", "Other")] += 1
        devices = event.get("device") or []
        if devices:
            mfr = devices[0].get("manufacturer_d_name") or devices[0].get("manufacturer_name")
            if mfr:
                manufacturers[mfr] += 1
        date_received = event.get("date_received")
        if date_received:
            dates.append(date_received)

    top_manufacturers = [name for name, _ in manufacturers.most_common(3)]
    date_range = "N/A"
    if dates:
        date_range = f"{min(dates)} to {max(dates)}"

    return event_types, manufacturers, top_manufacturers, date_range


def _risk_assessment(event_types: Counter) -> tuple[float, str]:
    deaths = event_types.get("Death", 0)
    injuries = event_types.get("Injury", 0)
    malfunctions = event_types.get("Malfunction", 0)
    other = sum(event_types.values()) - deaths - injuries - malfunctions
    total = max(1, sum(event_types.values()))

    weighted = deaths * 3 + injuries * 2 + malfunctions + other * 0.5
    score = min(10.0, (weighted / total) * 10.0)

    if score >= 7:
        level = "High"
    elif score >= 4:
        level = "Moderate"
    else:
        level = "Low"

    return score, level


def _build_device_narrative_response(
    device_name: str,
    events: list[dict],
    recalls: list[dict],
    elapsed_ms: float,
) -> "DeviceNarrativeResponse":
    event_types, manufacturers, top_manufacturers, date_range = _compute_event_stats(events)
    score, level = _risk_assessment(event_types)

    by_month: Dict[str, int] = {}
    for event in events:
        date_received = event.get("date_received")
        if date_received and len(date_received) >= 6:
            key = f"{date_received[:4]}-{date_received[4:6]}"
            by_month[key] = by_month.get(key, 0) + 1

    temporal_patterns = [
        {"period": month, "event_count": count}
        for month, count in sorted(by_month.items())
    ]

    sections = {
        "Overview": (
            f"{device_name} has {len(events)} adverse event reports in this dataset "
            f"with {len(recalls)} related recalls."
        ),
        "Risk Signals": (
            f"Risk score {score:.1f}/10 ({level}). "
            f"Deaths: {event_types.get('Death', 0)}, "
            f"Injuries: {event_types.get('Injury', 0)}, "
            f"Malfunctions: {event_types.get('Malfunction', 0)}."
        ),
        "Manufacturer Concentration": (
            f"Top manufacturers include {', '.join(top_manufacturers) or 'N/A'}."
        ),
        "Recall Activity": (
            "Recent recalls mention issues like "
            f"{recalls[0].get('reason_for_recall', 'N/A') if recalls else 'no recall details available'}."
        ),
    }

    return DeviceNarrativeResponse(
        device_name=device_name,
        summary=DeviceNarrativeSummary(
            total_events=len(events),
            date_range=date_range,
            risk_level=level,
            risk_score=round(score, 1),
            top_manufacturer=top_manufacturers,
            total_recalls=len(recalls),
        ),
        analysis=DeviceNarrativeAnalysis(
            event_types={k: int(v) for k, v in event_types.items()},
            temporal_patterns=temporal_patterns,
            manufacturer_analysis=dict(manufacturers.most_common(10)),
        ),
        narrative=DeviceNarrativeContent(sections=sections),
        metadata=DeviceNarrativeMetadata(
            generation_time=elapsed_ms,
            data_sources=["OpenFDA events", "OpenFDA recalls"],
        ),
    )


# Device Resolution Endpoints

class DeviceResolveRequest(BaseModel):
    query: str = Field(..., description="Search term for devices")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum results")
    fuzzy: bool = Field(default=True, description="Enable fuzzy matching")
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence score")


class DeviceMatchResponse(BaseModel):
    brand_name: Optional[str]
    company_name: Optional[str]
    product_codes: List[str]
    gmdn_terms: List[str]
    primary_di: Optional[str]
    match_type: str
    confidence: float


class DeviceResolveResponse(BaseModel):
    query: str
    total_matches: int
    matches: List[DeviceMatchResponse]
    unique_product_codes: List[str]
    unique_companies: List[str]
    execution_time_ms: float


@app.post("/api/devices/resolve", response_model=DeviceResolveResponse)
async def resolve_device_post(request: DeviceResolveRequest):
    """
    Resolve device query to FDA regulatory identifiers.
    Uses GUDID database for comprehensive device matching.
    """
    config = get_config()
    resolver = DeviceResolver(db_path=config.gudid_db_path)
    try:
        response = resolver.resolve(
            query=request.query,
            limit=request.limit,
            fuzzy=request.fuzzy,
            min_confidence=request.min_confidence
        )
        return DeviceResolveResponse(
            query=response.query,
            total_matches=response.total_matches,
            matches=[
                DeviceMatchResponse(
                    brand_name=m.device.brand_name,
                    company_name=m.device.company_name,
                    product_codes=m.device.get_product_codes(),
                    gmdn_terms=[t.gmdn_pt_name for t in m.device.gmdn_terms],
                    primary_di=m.device.get_primary_di(),
                    match_type=m.match_type.value,
                    confidence=m.confidence
                )
                for m in response.matches[:request.limit]
            ],
            unique_product_codes=response.get_unique_product_codes(),
            unique_companies=response.get_unique_companies(),
            execution_time_ms=response.execution_time_ms or 0.0
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"GUDID database not found: {str(e)}")
    except Exception as e:
        logger.error(f"Device resolution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        resolver.close()


@app.get("/api/devices/resolve/{query}")
async def resolve_device_get(
    query: str,
    limit: int = Query(default=100, ge=1, le=1000),
    fuzzy: bool = Query(default=True)
):
    """GET endpoint for simple device resolution queries."""
    request = DeviceResolveRequest(query=query, limit=limit, fuzzy=fuzzy)
    return await resolve_device_post(request)


# FDA Agent Endpoints

class AgentAskRequest(BaseModel):
    question: str = Field(..., description="Question to ask the FDA agent")
    provider: str = Field(default="openrouter", description="LLM provider (openrouter, bedrock, ollama)")
    model: Optional[str] = Field(default=None, description="Model to use (defaults to provider default)")
    session_id: Optional[str] = Field(default=None, description="Session ID for multi-turn conversations")


class AgentAskResponse(BaseModel):
    question: str
    answer: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: Optional[float]


class AgentAskStructuredResponse(BaseModel):
    question: str
    answer: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: Optional[float]
    structured: Optional[StructuredAgentResponse] = None


@app.post("/api/agent/ask", response_model=AgentAskResponse)
async def agent_ask(request: AgentAskRequest):
    """
    Ask the FDA Intelligence Agent a question.
    The agent uses a two-stage router to filter tools for faster responses.
    """
    try:
        # Stage 1: Route query to determine required tools
        allowed_tools = await router.route_async(request.question)
        logger.info(f"Router selected {len(allowed_tools)} tools for query: {allowed_tools}")

        # Stage 2: Execute with filtered tools
        agent = FDAAgent(
            provider=request.provider,
            model=request.model,
            allowed_tools=allowed_tools
        )
        response = await agent.ask_async(request.question, session_id=request.session_id)
        return AgentAskResponse(
            question=request.question,
            answer=response.content,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            cost=response.cost
        )
    except Exception as e:
        logger.error(f"Agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent/ask")
async def agent_ask_query(
    question: str = Query(..., description="Question to ask the FDA agent"),
    provider: str = Query(default="openrouter"),
    model: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
):
    """GET endpoint using query params to avoid path encoding."""
    return await agent_ask(AgentAskRequest(
        question=question,
        provider=provider,
        model=model,
        session_id=session_id,
    ))


@app.post("/api/agent/ask/structured", response_model=AgentAskStructuredResponse)
async def agent_ask_structured(request: AgentAskRequest):
    """Return full structured response for agent answers with routed tools."""
    try:
        # Stage 1: Route query to determine required tools
        allowed_tools = await router.route_async(request.question)

        # Stage 2: Execute with filtered tools
        agent = FDAAgent(
            provider=request.provider,
            model=request.model,
            allowed_tools=allowed_tools
        )
        response = await agent.ask_async(request.question, session_id=request.session_id)
        return AgentAskStructuredResponse(
            question=request.question,
            answer=response.content,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            cost=response.cost,
            structured=response.structured,
        )
    except Exception as e:
        logger.error(f"Agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent/ask/structured")
async def agent_ask_structured_query(
    question: str = Query(..., description="Question to ask the FDA agent"),
    provider: str = Query(default="openrouter"),
    model: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
):
    """GET endpoint for structured response using query params."""
    return await agent_ask_structured(AgentAskRequest(
        question=question,
        provider=provider,
        model=model,
        session_id=session_id,
    ))


@app.get("/api/agent/ask/{question}")
async def agent_ask_get(
    question: str,
    provider: str = Query(default="openrouter"),
    model: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None)
):
    """GET endpoint for simple agent questions."""
    return await agent_ask(AgentAskRequest(question=question, provider=provider, model=model, session_id=session_id))


@app.get("/api/agent/stream/{question}")
async def agent_stream(
    request: Request,
    question: str,
    provider: str = Query(default="openrouter"),
    model: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None)
):
    """Stream FDA agent responses using SSE with token-level streaming for final response."""
    client_ip = get_client_ip(request)

    async def generate_events():
        try:
            allowed_tools = await router.route_async(question)
            agent = FDAAgent(provider=provider, model=model, allowed_tools=allowed_tools, checkpointer=shared_checkpointer)
            accumulated_answer = ""
            in_final_response = False
            total_input_tokens = 0
            total_output_tokens = 0
            used_model = model or provider

            yield f"data: {json.dumps({'type': 'start', 'question': question})}\n\n"

            async for event in agent.stream_tokens_async(question, session_id=session_id):
                event_type = event.get("type")

                if event_type == "clear":
                    accumulated_answer = ""
                    yield f"data: {json.dumps({'type': 'clear'})}\n\n"

                elif event_type == "tool_call":
                    in_final_response = False
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': event['tool'], 'args': event['args']})}\n\n"

                elif event_type == "tool_result":
                    yield f"data: {json.dumps({'type': 'tool_result', 'content': event['content']})}\n\n"

                elif event_type == "token":
                    in_final_response = True
                    content = event.get("content", "")
                    if content:
                        accumulated_answer += content
                        yield f"data: {json.dumps({'type': 'delta', 'content': content})}\n\n"

                elif event_type == "usage":
                    total_input_tokens += event.get("input_tokens", 0)
                    total_output_tokens += event.get("output_tokens", 0)
                    if event.get("model"):
                        used_model = event["model"]

                elif event_type == "message_complete":
                    in_final_response = False

            structured_data = {}
            if hasattr(agent, '_recalls_tool') and agent._recalls_tool:
                recall_result = agent._recalls_tool.get_last_structured_result()
                if recall_result:
                    structured_data["recalls"] = recall_result.model_dump() if hasattr(recall_result, 'model_dump') else recall_result
            if hasattr(agent, '_device_resolver') and agent._device_resolver:
                device_result = agent._device_resolver.get_last_structured_result()
                if device_result:
                    structured_data["devices"] = device_result.model_dump() if hasattr(device_result, 'model_dump') else device_result
            if hasattr(agent, '_events_tool') and agent._events_tool:
                events_result = agent._events_tool.get_last_structured_result()
                if events_result:
                    structured_data["events"] = events_result.model_dump() if hasattr(events_result, 'model_dump') else events_result

            cost_estimates = {
                "openrouter": {"input": 2.0, "output": 6.0},
                "openai": {"input": 5.0, "output": 15.0},
                "anthropic": {"input": 15.0, "output": 75.0},
                "gemini": {"input": 0.125, "output": 0.375},
            }
            total_cost = 0.0
            provider_key = provider.lower()
            if provider_key == "openrouter" and model:
                if "flash" in model.lower():
                    provider_key = "gemini"
            if provider_key in cost_estimates and total_input_tokens > 0:
                rates = cost_estimates[provider_key]
                total_cost = (
                    (total_input_tokens / 1_000_000) * rates["input"] +
                    (total_output_tokens / 1_000_000) * rates["output"]
                )

            try:
                tracker = get_usage_tracker()
                tracker.record_usage(
                    ip_address=client_ip,
                    session_id=session_id,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    cost_usd=total_cost,
                    model=used_model
                )
            except Exception as usage_err:
                logger.warning(f"Failed to record usage: {usage_err}")

            complete_payload = {
                "type": "complete",
                "answer": accumulated_answer,
                "model": used_model,
                "tokens": total_input_tokens + total_output_tokens,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "cost": total_cost if total_cost > 0 else None,
                "structured_data": structured_data if structured_data else None,
            }
            yield f"data: {json.dumps(complete_payload)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            import traceback
            logger.error(f"Stream error: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search term")
    query_type: str = Field(default="device", description="device, manufacturer, or recall")
    limit: int = Field(default=10, ge=1, le=500)
    include_ai_analysis: bool = Field(default=False)


class SearchResponse(BaseModel):
    status: str
    query: str
    query_type: str
    total_results: int
    results_count: int
    results: List[Dict[str, Any]]
    ai_analysis: Optional[dict] = None
    metadata: Optional[dict] = None


class DeviceNarrativeSummary(BaseModel):
    total_events: int
    date_range: str
    risk_level: str
    risk_score: float
    top_manufacturer: List[str]
    total_recalls: int


class DeviceNarrativeAnalysis(BaseModel):
    event_types: Dict[str, int]
    temporal_patterns: List[Dict[str, Any]]
    manufacturer_analysis: Dict[str, int]


class DeviceNarrativeContent(BaseModel):
    sections: Dict[str, str]


class DeviceNarrativeMetadata(BaseModel):
    generation_time: float
    data_sources: List[str]


class DeviceNarrativeResponse(BaseModel):
    device_name: str
    summary: DeviceNarrativeSummary
    analysis: DeviceNarrativeAnalysis
    narrative: DeviceNarrativeContent
    metadata: DeviceNarrativeMetadata


class DeviceIntelligenceRequest(BaseModel):
    device_name: str
    lookback_months: int = Field(default=12, ge=1, le=120)
    include_risk_assessment: bool = Field(default=True)


class DeviceIntelligenceResponse(BaseModel):
    device_name: str
    total_events: int
    manufacturer_distribution: Dict[str, int]
    temporal_trends: List[Dict[str, Any]]
    risk_assessment: Optional[dict] = None


class DeviceNarrativeRequest(BaseModel):
    device_name: str


class DeviceCompareRequest(BaseModel):
    device_names: List[str]
    lookback_months: int = Field(default=12, ge=1, le=120)


class MultiAgentIntent(BaseModel):
    primary_intent: str
    device_names: List[str]
    time_range: Optional[str]
    specific_concerns: List[str]
    required_agents: List[str]


class MultiAgentResult(BaseModel):
    success: bool
    query: str
    intent: MultiAgentIntent
    agent_results: Dict[str, Any]
    timestamp: str


@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search FDA data using the intelligent agent.
    The agent automatically resolves device names to product codes for precise searching.
    """
    start_time = time.perf_counter()
    query_type = request.query_type.lower()

    try:
        # Build agent question based on query type
        if query_type == "recall":
            question = f"Find recalls for {request.query}. Limit to {request.limit} results."
        elif query_type == "manufacturer":
            question = f"Find adverse events from manufacturer {request.query}. Limit to {request.limit} results."
        else:  # device
            question = f"Find adverse events for {request.query}. Limit to {request.limit} results."

        # Stage 1: Route query to determine required tools
        allowed_tools = await router.route_async(question)

        # Stage 2: Execute with filtered tools
        agent = FDAAgent(
            provider="openrouter", 
            model="xiaomi/mimo-v2-flash:free",
            allowed_tools=allowed_tools
        )
        response = await agent.ask_async(question)

        # Extract structured data from agent response
        events = []
        recalls = []
        total = 0

        if response.structured and response.structured.recall_results:
            # Agent found recalls
            recalls = [
                {
                    "recall_number": r.recall_number,
                    "recalling_firm": r.recalling_firm,
                    "product_description": r.product_description,
                    "reason_for_recall": r.reason_for_recall,
                    "classification": r.classification,
                    "status": r.status,
                    "recall_initiation_date": r.recall_initiation_date,
                }
                for r in response.structured.recall_results.records[:request.limit]
            ]
            total = response.structured.recall_results.total_found
            # Map recalls to event format for consistency
            events = _map_recalls_to_events(recalls)

        # Build AI analysis from agent's summary if requested
        ai_analysis = None
        if request.include_ai_analysis and response.structured:
            ai_analysis = {
                "summary": response.structured.summary,
                "key_insights": [response.structured.summary],  # Agent provides synthesis
                "risk_assessment": None  # Could be enhanced later
            }

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return SearchResponse(
            status="ok",
            query=request.query,
            query_type=query_type,
            total_results=total,
            results_count=len(events),
            results=events,
            ai_analysis=ai_analysis,
            metadata={
                "search_time": elapsed_ms,
                "processing_time": elapsed_ms,
                "agent_used": True,
                "model": response.model,
                "tokens": response.total_tokens
            },
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/device/intelligence", response_model=DeviceIntelligenceResponse)
async def device_intelligence(payload: DeviceIntelligenceRequest):
    """
    Get device intelligence using product code resolution for precise results.

    IMPROVED: Now resolves device names to product codes before searching,
    resulting in 3-5x more comprehensive results.
    """
    device_name = payload.device_name
    lookback_months = payload.lookback_months

    # IMPROVEMENT: Resolve device to product codes first
    from .tools import DeviceResolver
    config = get_config()
    resolver = DeviceResolver(db_path=config.gudid_db_path)
    resolved = resolver.get_product_codes_fast(device_name, limit=100)

    # Extract top product codes
    product_codes = [pc["code"] for pc in resolved.get("product_codes", [])][:5]

    # Search using product codes (precise) or fallback to text
    client = OpenFDAClient()
    if product_codes:
        # BUILD PRECISE SEARCH using product codes
        code_queries = [f'device.device_report_product_code:"{code}"' for code in product_codes]
        search = f'({" OR ".join(code_queries)})'
    else:
        # Fallback to text search
        safe_query = device_name.replace('"', '\\"')
        search = f'(device.brand_name:"{safe_query}" OR device.generic_name:"{safe_query}")'

    data = client.get_paginated(
        "device/event.json",
        params={"search": search},
        limit=min(500, lookback_months * 50),
        sort="date_received:desc"
    )
    events = data.get("results", [])

    # Compute stats from events
    event_types, manufacturers, _, _ = _compute_event_stats(events)
    score, level = _risk_assessment(event_types)

    # Build temporal trends
    by_month: Dict[str, int] = {}
    for event in events:
        date_received = event.get("date_received")
        if date_received and len(date_received) >= 6:
            key = f"{date_received[:4]}-{date_received[4:6]}"
            by_month[key] = by_month.get(key, 0) + 1

    temporal_trends = [
        {"period": month, "event_count": count}
        for month, count in sorted(by_month.items())
    ]

    return DeviceIntelligenceResponse(
        device_name=device_name,
        total_events=len(events),
        manufacturer_distribution=dict(manufacturers.most_common(10)),
        temporal_trends=temporal_trends,
        risk_assessment={
            "level": level,
            "score": round(score, 1),
            "factors": [
                f"Deaths: {event_types.get('Death', 0)}",
                f"Injuries: {event_types.get('Injury', 0)}",
                f"Using product codes: {', '.join(product_codes) if product_codes else 'text search'}",
            ],
        } if payload.include_risk_assessment else None,
    )


@app.post("/api/device/compare")
async def device_compare(request: DeviceCompareRequest):
    """
    Compare multiple devices using product code resolution.

    IMPROVED: Now resolves device names to product codes before searching,
    providing more accurate comparisons.
    """
    from .tools import DeviceResolver
    config = get_config()
    resolver = DeviceResolver(db_path=config.gudid_db_path)
    client = OpenFDAClient()

    devices = []
    for name in request.device_names:
        # Resolve to product codes
        resolved = resolver.get_product_codes_fast(name, limit=100)
        product_codes = [pc["code"] for pc in resolved.get("product_codes", [])][:5]

        # Search using product codes (precise) or fallback to text
        if product_codes:
            code_queries = [f'device.device_report_product_code:"{code}"' for code in product_codes]
            search = f'({" OR ".join(code_queries)})'
        else:
            safe_query = name.replace('"', '\\"')
            search = f'(device.brand_name:"{safe_query}" OR device.generic_name:"{safe_query}")'

        data = client.get_paginated(
            "device/event.json",
            params={"search": search},
            limit=100,
            sort="date_received:desc"
        )
        events = data.get("results", [])

        event_types, _, _, _ = _compute_event_stats(events)
        score, level = _risk_assessment(event_types)

        devices.append({
            "device_name": name,
            "total_events": len(events),
            "risk_score": round(score, 1),
            "risk_level": level,
            "product_codes": product_codes if product_codes else None,
        })

    return {"devices": devices, "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/device/narrative", response_model=DeviceNarrativeResponse)
async def device_narrative(payload: DeviceNarrativeRequest):
    """
    Generate device narrative using product code resolution.

    IMPROVED: Now resolves device names to product codes before searching,
    providing more accurate and complete event and recall data.
    """
    device_name = payload.device_name
    start_time = time.perf_counter()

    # Resolve device to product codes
    from .tools import DeviceResolver
    config = get_config()
    resolver = DeviceResolver(db_path=config.gudid_db_path)
    resolved = resolver.get_product_codes_fast(device_name, limit=100)
    product_codes = [pc["code"] for pc in resolved.get("product_codes", [])][:5]

    # Fetch events using product codes (precise) or fallback to text
    client = OpenFDAClient()
    if product_codes:
        code_queries = [f'device.device_report_product_code:"{code}"' for code in product_codes]
        events_search = f'({" OR ".join(code_queries)})'
    else:
        safe_query = device_name.replace('"', '\\"')
        events_search = f'(device.brand_name:"{safe_query}" OR device.generic_name:"{safe_query}")'

    events_data = client.get_paginated(
        "device/event.json",
        params={"search": events_search},
        limit=200,
        sort="date_received:desc"
    )
    events = events_data.get("results", [])

    # Fetch recalls using device name (enforcement API doesn't support product_code field)
    safe_query = device_name.replace('"', '\\"')
    recalls_search = f'product_description:"{safe_query}"'

    recalls_data = client.get_paginated(
        "device/enforcement.json",
        params={"search": recalls_search},
        limit=100,
        sort="report_date:desc"
    )
    recalls = recalls_data.get("results", [])

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    return _build_device_narrative_response(device_name, events, recalls, elapsed_ms)


@app.get("/api/device/narrative/stream/{device_name}")
async def device_narrative_stream(device_name: str):
    """
    Stream device narrative generation with product code resolution.

    IMPROVED: Now resolves device names to product codes before searching.
    """
    async def generate_events():
        try:
            start_time = time.perf_counter()
            yield f"data: {json.dumps({'event': 'progress', 'data': {'percentage': 10, 'message': 'Resolving device...'}})}\n\n"

            # Resolve device to product codes
            from .tools import DeviceResolver
            config = get_config()
            resolver = DeviceResolver(db_path=config.gudid_db_path)
            resolved = resolver.get_product_codes_fast(device_name, limit=100)
            product_codes = [pc["code"] for pc in resolved.get("product_codes", [])][:5]

            yield f"data: {json.dumps({'event': 'progress', 'data': {'percentage': 30, 'message': 'Fetching events...'}})}\n\n"

            # Fetch events using product codes
            client = OpenFDAClient()
            if product_codes:
                code_queries = [f'device.device_report_product_code:"{code}"' for code in product_codes]
                events_search = f'({" OR ".join(code_queries)})'
            else:
                safe_query = device_name.replace('"', '\\"')
                events_search = f'(device.brand_name:"{safe_query}" OR device.generic_name:"{safe_query}")'

            events_data = client.get_paginated(
                "device/event.json",
                params={"search": events_search},
                limit=200,
                sort="date_received:desc"
            )

            yield f"data: {json.dumps({'event': 'progress', 'data': {'percentage': 60, 'message': 'Fetching recalls...'}})}\n\n"

            # Fetch recalls using device name (enforcement API doesn't support product_code field)
            safe_query = device_name.replace('"', '\\"')
            recalls_search = f'product_description:"{safe_query}"'

            recalls_data = client.get_paginated(
                "device/enforcement.json",
                params={"search": recalls_search},
                limit=100,
                sort="report_date:desc"
            )

            yield f"data: {json.dumps({'event': 'progress', 'data': {'percentage': 80, 'message': 'Analyzing patterns...'}})}\n\n"

            events = events_data.get("results", [])
            recalls = recalls_data.get("results", [])
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            narrative = _build_device_narrative_response(device_name, events, recalls, elapsed_ms)
            yield f"data: {json.dumps({'event': 'complete', 'data': narrative.model_dump()})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/agents/analyze", response_model=MultiAgentResult)
async def agents_analyze(payload: dict):
    """
    Multi-agent analysis using product code resolution.

    IMPROVED: Now resolves device names to product codes before searching.
    """
    query = payload.get("query", "")

    # Resolve device to product codes
    from .tools import DeviceResolver
    config = get_config()
    resolver = DeviceResolver(db_path=config.gudid_db_path)
    resolved = resolver.get_product_codes_fast(query, limit=100)
    product_codes = [pc["code"] for pc in resolved.get("product_codes", [])][:5]

    # Fetch events using product codes
    client = OpenFDAClient()
    if product_codes:
        code_queries = [f'device.device_report_product_code:"{code}"' for code in product_codes]
        events_search = f'({" OR ".join(code_queries)})'
    else:
        safe_query = query.replace('"', '\\"')
        events_search = f'(device.brand_name:"{safe_query}" OR device.generic_name:"{safe_query}")'

    events_data = client.get_paginated(
        "device/event.json",
        params={"search": events_search},
        limit=200,
        sort="date_received:desc"
    )
    events = events_data.get("results", [])

    # Fetch recalls using device name (enforcement API doesn't support product_code field)
    safe_query = query.replace('"', '\\"')
    recalls_search = f'product_description:"{safe_query}"'

    recalls_data = client.get_paginated(
        "device/enforcement.json",
        params={"search": recalls_search},
        limit=100,
        sort="report_date:desc"
    )
    recalls = recalls_data.get("results", [])

    event_types, manufacturers, top_manufacturers, _ = _compute_event_stats(events)
    score, level = _risk_assessment(event_types)

    agent_results = {
        "collector": [{
            "data_points": len(events),
            "key_findings": [
                f"Collected {len(events)} adverse event records.",
                f"Collected {len(recalls)} recall records.",
            ],
            "raw_data": {
                "events": events[:5],
                "recalls": recalls[:5],
            },
        }],
        "analyzer": [{
            "data_points": len(events),
            "key_findings": [
                f"Risk score {score:.1f}/10 ({level}).",
                f"Top event type: {event_types.most_common(1)[0][0] if event_types else 'Unknown'}.",
            ],
            "recommendations": [
                "Review recent injury and death reports for common failure modes.",
                "Prioritize monitoring top manufacturers by event volume.",
            ],
            "raw_data": {
                "event_types": dict(event_types),
                "manufacturers": dict(manufacturers.most_common(5)),
            },
        }],
        "writer": [{
            "data_points": len(events),
            "key_findings": [
                f"Summary: {query} has {len(events)} events and {len(recalls)} recalls in this snapshot.",
                f"Top manufacturers: {', '.join(top_manufacturers) or 'N/A'}.",
            ],
            "recommendations": [
                "Validate findings against FDA sources before action.",
            ],
        }],
    }

    return MultiAgentResult(
        success=True,
        query=query,
        intent=MultiAgentIntent(
            primary_intent="device_risk_analysis",
            device_names=[query] if query else [],
            time_range=None,
            specific_concerns=[],
            required_agents=["collector", "analyzer", "writer"],
        ),
        agent_results=agent_results,
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/api/agents/capabilities")
async def agents_capabilities():
    return {
        "agents": [
            {
                "id": "collector",
                "name": "Collector",
                "icon": "🔍",
                "description": "Fetches events, recalls, and manufacturer data.",
                "capabilities": ["OpenFDA events", "OpenFDA recalls"],
                "color": "#4ecdc4",
            },
            {
                "id": "analyzer",
                "name": "Analyzer",
                "icon": "📊",
                "description": "Scores risk and detects patterns.",
                "capabilities": ["Risk scoring", "Trend detection"],
                "color": "#ff6b6b",
            },
            {
                "id": "writer",
                "name": "Writer",
                "icon": "📝",
                "description": "Summarizes findings into an executive brief.",
                "capabilities": ["Executive summary", "Recommendations"],
                "color": "#ffe66d",
            },
        ]
    }


@app.get("/api/agents/analyze/stream/{query}")
async def agents_analyze_stream(query: str):
    async def generate_events():
        try:
            base_state = {
                "orchestrator": {
                    "agent_id": "orchestrator",
                    "agent_name": "Orchestrator",
                    "status": "running",
                    "progress": 10,
                    "message": "Planning analysis",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "collector": {
                    "agent_id": "collector",
                    "agent_name": "Collector",
                    "status": "waiting",
                    "progress": 0,
                    "message": "Waiting",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "analyzer": {
                    "agent_id": "analyzer",
                    "agent_name": "Analyzer",
                    "status": "waiting",
                    "progress": 0,
                    "message": "Waiting",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "writer": {
                    "agent_id": "writer",
                    "agent_name": "Writer",
                    "status": "waiting",
                    "progress": 0,
                    "message": "Waiting",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }
            yield f"data: {json.dumps({'type': 'agent_states', 'data': base_state})}\n\n"

            yield f"data: {json.dumps({'type': 'progress', 'data': {'percentage': 15, 'message': 'Collecting FDA data...'}})}\n\n"
            collector_state = {
                "collector": {
                    "agent_id": "collector",
                    "agent_name": "Collector",
                    "status": "running",
                    "progress": 30,
                    "message": "Resolving device and fetching data",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            }
            yield f"data: {json.dumps({'type': 'agent_update', 'data': collector_state})}\n\n"

            # Resolve device to product codes
            from .tools import DeviceResolver
            config = get_config()
            resolver = DeviceResolver(db_path=config.gudid_db_path)
            resolved = resolver.get_product_codes_fast(query, limit=100)
            product_codes = [pc["code"] for pc in resolved.get("product_codes", [])][:5]

            # Fetch events using product codes
            client = OpenFDAClient()
            if product_codes:
                code_queries = [f'device.device_report_product_code:"{code}"' for code in product_codes]
                events_search = f'({" OR ".join(code_queries)})'
            else:
                safe_query = query.replace('"', '\\"')
                events_search = f'(device.brand_name:"{safe_query}" OR device.generic_name:"{safe_query}")'

            events_data = client.get_paginated(
                "device/event.json",
                params={"search": events_search},
                limit=200,
                sort="date_received:desc"
            )
            events = events_data.get("results", [])

            # Fetch recalls using device name (enforcement API doesn't support product_code field)
            safe_query = query.replace('"', '\\"')
            recalls_search = f'product_description:"{safe_query}"'

            recalls_data = client.get_paginated(
                "device/enforcement.json",
                params={"search": recalls_search},
                limit=100,
                sort="report_date:desc"
            )
            recalls = recalls_data.get("results", [])

            collector_done = {
                "collector": {
                    "agent_id": "collector",
                    "agent_name": "Collector",
                    "status": "completed",
                    "progress": 100,
                    "message": "Data collection complete",
                    "data_points": len(events) + len(recalls),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            }
            yield f"data: {json.dumps({'type': 'agent_update', 'data': collector_done})}\n\n"

            yield f"data: {json.dumps({'type': 'progress', 'data': {'percentage': 55, 'message': 'Analyzing risk signals...'}})}\n\n"
            analyzer_state = {
                "analyzer": {
                    "agent_id": "analyzer",
                    "agent_name": "Analyzer",
                    "status": "running",
                    "progress": 60,
                    "message": "Scoring risk",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            }
            yield f"data: {json.dumps({'type': 'agent_update', 'data': analyzer_state})}\n\n"

            event_types, manufacturers, top_manufacturers, _ = _compute_event_stats(events)
            score, level = _risk_assessment(event_types)

            analyzer_done = {
                "analyzer": {
                    "agent_id": "analyzer",
                    "agent_name": "Analyzer",
                    "status": "completed",
                    "progress": 100,
                    "message": f"Risk {level} ({score:.1f}/10)",
                    "data_points": len(events),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            }
            yield f"data: {json.dumps({'type': 'agent_update', 'data': analyzer_done})}\n\n"

            yield f"data: {json.dumps({'type': 'progress', 'data': {'percentage': 80, 'message': 'Drafting summary...'}})}\n\n"
            writer_state = {
                "writer": {
                    "agent_id": "writer",
                    "agent_name": "Writer",
                    "status": "running",
                    "progress": 70,
                    "message": "Compiling summary",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            }
            yield f"data: {json.dumps({'type': 'agent_update', 'data': writer_state})}\n\n"

            result = await agents_analyze({"query": query})

            writer_done = {
                "writer": {
                    "agent_id": "writer",
                    "agent_name": "Writer",
                    "status": "completed",
                    "progress": 100,
                    "message": "Summary ready",
                    "data_points": len(events),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            }
            yield f"data: {json.dumps({'type': 'agent_update', 'data': writer_done})}\n\n"
            yield f"data: {json.dumps({'type': 'progress', 'data': {'percentage': 100, 'message': 'Complete'}})}\n\n"
            yield f"data: {json.dumps({'type': 'complete', 'data': result.model_dump()})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/agent/providers")
async def list_providers():
    """List available LLM providers and their default models."""
    from .llm_factory import LLMFactory
    return {
        "providers": LLMFactory.list_providers(),
        "defaults": LLMFactory.PROVIDER_DEFAULTS
    }


@app.get("/api/usage")
async def get_usage(request: Request):
    """Get usage statistics for the current IP address."""
    try:
        ip = get_client_ip(request)
        tracker = get_usage_tracker()
        stats = tracker.get_stats(ip)
        return {
            "ip_address": stats.ip_address,
            "total_cost_usd": round(stats.total_cost_usd, 6),
            "limit_usd": stats.limit_usd,
            "remaining_usd": round(stats.limit_usd - stats.total_cost_usd, 6),
            "total_input_tokens": stats.total_input_tokens,
            "total_output_tokens": stats.total_output_tokens,
            "request_count": stats.request_count,
            "first_request": stats.first_request,
            "last_request": stats.last_request,
        }
    except Exception as e:
        logger.error(f"Usage stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ExtendLimitRequest(BaseModel):
    ip_address: Optional[str] = Field(None, description="IP address to extend limit for (admin only)")
    new_limit: Optional[float] = Field(None, description="New limit in USD (admin only)")
    secret: Optional[str] = Field(None, description="Admin secret key")
    passphrase: Optional[str] = Field(None, description="User passphrase for self-service extension")


@app.post("/api/usage/extend")
async def extend_usage_limit(request: ExtendLimitRequest, req: Request):
    """Extend usage limit. Supports admin secret or user passphrase."""
    tracker = get_usage_tracker()
    client_ip = get_client_ip(req)

    # Admin mode: requires secret, ip_address, and new_limit
    if request.secret:
        if request.secret != USAGE_EXTEND_SECRET:
            raise HTTPException(status_code=403, detail="Invalid secret")
        if not request.ip_address or not request.new_limit:
            raise HTTPException(status_code=400, detail="Admin mode requires ip_address and new_limit")
        try:
            tracker.extend_limit(request.ip_address, request.new_limit, extended_by="admin")
            return {
                "success": True,
                "ip_address": request.ip_address,
                "new_limit": request.new_limit,
            }
        except Exception as e:
            logger.error(f"Extend limit error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # User passphrase mode: extends own limit by configured amount
    if request.passphrase:
        if not USAGE_USER_PASSPHRASE:
            raise HTTPException(status_code=403, detail="Passphrase extension not configured")
        if request.passphrase != USAGE_USER_PASSPHRASE:
            raise HTTPException(status_code=403, detail="Invalid passphrase")
        try:
            stats = tracker.get_stats(client_ip)
            current_limit = stats.get("limit_usd", 1.50)
            new_limit = current_limit + USAGE_PASSPHRASE_EXTENSION
            tracker.extend_limit(client_ip, new_limit, extended_by="passphrase")
            return {
                "success": True,
                "new_limit": new_limit,
            }
        except Exception as e:
            logger.error(f"Passphrase extend error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=400, detail="Must provide either secret or passphrase")


class GenerateTitleRequest(BaseModel):
    first_user_message: str = Field(..., description="First user message in session")
    first_assistant_response: str = Field(..., description="First assistant response")


@app.post("/api/sessions/generate-title")
async def generate_session_title(request: GenerateTitleRequest):
    """Generate a short title for a session based on first exchange."""
    try:
        llm = LLMFactory.create(provider="openrouter", temperature=0.3, max_tokens=30)
        prompt = f"""Generate a very short title (3-5 words, no quotes) summarizing this FDA research conversation:

User: {request.first_user_message[:200]}
Assistant: {request.first_assistant_response[:300]}

Title:"""
        response = llm.invoke(prompt)
        title = response.content.strip().strip('"').strip("'")
        if len(title) > 50:
            title = title[:47] + "..."
        return {"title": title}
    except Exception as e:
        logger.error(f"Title generation error: {e}")
        return {"title": "New Chat"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
