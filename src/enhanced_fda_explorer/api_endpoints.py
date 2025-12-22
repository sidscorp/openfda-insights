"""
FastAPI endpoints for FDA Intelligence Agent with SSE support
"""

import json
import time
from collections import Counter
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from .tools import DeviceResolver
from .config import get_config
from .agent import FDAAgent
from .llm_factory import LLMFactory
from .openfda_client import OpenFDAClient
from .models.responses import AgentResponse as StructuredAgentResponse

logger = logging.getLogger(__name__)

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


def _safe_query(query: str) -> str:
    return query.replace('"', '\\"').strip()


def _event_search_query(query: str, query_type: str) -> str:
    safe_query = _safe_query(query)
    if query_type == "manufacturer":
        return f'device.manufacturer_d_name:"{safe_query}"'
    return f'(device.brand_name:"{safe_query}" OR device.generic_name:"{safe_query}")'


def _fetch_events(query: str, query_type: str, limit: int) -> dict:
    client = OpenFDAClient()
    search = _event_search_query(query, query_type)
    return client.get_paginated(
        "device/event.json",
        params={"search": search},
        limit=limit,
        sort="date_received:desc",
    )


def _fetch_recalls(query: str, limit: int) -> dict:
    client = OpenFDAClient()
    safe_query = _safe_query(query)
    search = f'(product_description:"{safe_query}" OR recalling_firm:"{safe_query}")'
    return client.get_paginated(
        "device/enforcement.json",
        params={"search": search},
        limit=limit,
        sort="recall_initiation_date:desc",
    )


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


def _build_ai_analysis(query: str, events: list[dict], recalls: list[dict]) -> dict:
    event_types, _, top_manufacturers, _ = _compute_event_stats(events)
    score, level = _risk_assessment(event_types)
    total_events = len(events)
    total_recalls = len(recalls)

    key_insights = [
        f"{total_events} adverse events found for '{query}'.",
        f"Top event type: {event_types.most_common(1)[0][0] if event_types else 'Unknown'}.",
        f"Recalls matching query: {total_recalls}.",
    ]
    if top_manufacturers:
        key_insights.append(f"Top manufacturer: {top_manufacturers[0]}.")

    return {
        "summary": f"Found {total_events} events and {total_recalls} recalls for '{query}'.",
        "key_insights": key_insights,
        "risk_assessment": {
            "level": level,
            "score": round(score, 1),
            "factors": [
                f"Deaths: {event_types.get('Death', 0)}",
                f"Injuries: {event_types.get('Injury', 0)}",
                f"Malfunctions: {event_types.get('Malfunction', 0)}",
                f"Recalls: {total_recalls}",
            ],
        },
    }


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
    The agent uses tools to search FDA databases and synthesize answers.
    """
    try:
        agent = FDAAgent(provider=request.provider, model=request.model)
        response = agent.ask(request.question, session_id=request.session_id)
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
    """Return full structured response for agent answers."""
    try:
        agent = FDAAgent(provider=request.provider, model=request.model)
        response = agent.ask(request.question, session_id=request.session_id)
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
    question: str,
    provider: str = Query(default="openrouter"),
    model: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None)
):
    """Stream FDA agent responses using SSE for real-time updates."""
    async def generate_events():
        try:
            agent = FDAAgent(provider=provider, model=model)
            accumulated_answer = ""
            # Track stats incrementally
            total_input_tokens = 0
            total_output_tokens = 0
            total_cost = 0.0
            used_model = model or provider
            
            # Cost estimation per 1M tokens (rough estimates)
            cost_estimates = {
                "openrouter": {"input": 2.0, "output": 6.0},  # Average for popular models
                "openai": {"input": 5.0, "output": 15.0},     # GPT-4 pricing
                "anthropic": {"input": 15.0, "output": 75.0}, # Claude pricing
                "cohere": {"input": 1.0, "output": 2.0},      # Command pricing
                "gemini": {"input": 0.125, "output": 0.375},  # Gemini 1.5 Flash
                "xiaomi": {"input": 0.0, "output": 0.0},      # Free tier
            }

            yield f"data: {json.dumps({'type': 'start', 'question': question})}\n\n"

            for event in agent.stream(question, session_id=session_id):
                node_name = list(event.keys())[0] if event else "unknown"
                messages = event.get(node_name, {}).get("messages", [])

                for msg in messages:
                    # Extract usage/model info from AIMessages (completed steps)
                    if isinstance(msg, AIMessage):
                        if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                            total_input_tokens += msg.usage_metadata.get("input_tokens", 0)
                            total_output_tokens += msg.usage_metadata.get("output_tokens", 0)
                        
                        if hasattr(msg, 'response_metadata') and msg.response_metadata:
                            meta = msg.response_metadata
                            if meta.get("model_name"):
                                used_model = meta["model_name"]
                            
                            # Try to extract cost if available (provider dependent)
                            token_usage = meta.get("token_usage", {})
                            if token_usage.get("cost"):
                                total_cost += token_usage["cost"]

                    if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                        for tool_call in msg.tool_calls:
                            yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_call['name'], 'args': tool_call['args']})}\n\n"
                        continue

                    if isinstance(msg, ToolMessage):
                        if msg.content:
                            yield f"data: {json.dumps({'type': 'tool_result', 'content': msg.content[:500]})}\n\n"
                        continue

                    if isinstance(msg, (AIMessage, AIMessageChunk)) and msg.content:
                        if node_name != "tools":
                            accumulated_answer += msg.content
                            yield f"data: {json.dumps({'type': 'delta', 'content': msg.content})}\n\n"

            # Calculate cost if not provided
            if total_cost <= 0 and total_input_tokens > 0:
                # Try to estimate cost based on provider
                provider_key = provider.lower()
                if provider_key == "openrouter":
                    # Try to get more specific model pricing
                    if "flash" in (model or "").lower():
                        provider_key = "gemini"
                    elif "command" in (model or "").lower():
                        provider_key = "cohere"
                
                if provider_key in cost_estimates:
                    rates = cost_estimates[provider_key]
                    total_cost = (
                        (total_input_tokens / 1_000_000) * rates["input"] +
                        (total_output_tokens / 1_000_000) * rates["output"]
                    )
            
            # Use accumulated stats
            complete_payload = {
                "type": "complete",
                "answer": accumulated_answer,
                "model": used_model,
                "tokens": total_input_tokens + total_output_tokens,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "cost": total_cost if total_cost > 0 else None,
                "structured_data": None,
            }
            yield f"data: {json.dumps(complete_payload)}\n\n"

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
    start_time = time.perf_counter()
    query_type = request.query_type.lower()

    try:
        if query_type == "recall":
            recall_data = _fetch_recalls(request.query, request.limit)
            recalls = recall_data.get("results", [])
            events = _map_recalls_to_events(recalls)
            total = recall_data.get("meta", {}).get("results", {}).get("total", 0)
        else:
            data = _fetch_events(request.query, query_type, request.limit)
            events = data.get("results", [])
            total = data.get("meta", {}).get("results", {}).get("total", 0)
            recalls = []

        ai_analysis = None
        if request.include_ai_analysis:
            if not recalls:
                recall_data = _fetch_recalls(request.query, min(100, request.limit))
                recalls = recall_data.get("results", [])
            ai_analysis = _build_ai_analysis(request.query, events, recalls)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return SearchResponse(
            status="ok",
            query=request.query,
            query_type=query_type,
            total_results=total,
            results_count=len(events),
            results=events,
            ai_analysis=ai_analysis,
            metadata={"search_time": elapsed_ms, "processing_time": elapsed_ms},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/device/intelligence", response_model=DeviceIntelligenceResponse)
async def device_intelligence(payload: DeviceIntelligenceRequest):
    device_name = payload.device_name
    lookback_months = payload.lookback_months

    data = _fetch_events(device_name, "device", min(500, lookback_months * 50))
    events = data.get("results", [])

    event_types, manufacturers, _, _ = _compute_event_stats(events)
    score, level = _risk_assessment(event_types)

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
            ],
        } if payload.include_risk_assessment else None,
    )


@app.post("/api/device/compare")
async def device_compare(request: DeviceCompareRequest):
    devices = []
    for name in request.device_names:
        data = _fetch_events(name, "device", 100)
        events = data.get("results", [])
        event_types, _, _, _ = _compute_event_stats(events)
        score, level = _risk_assessment(event_types)
        devices.append({
            "device_name": name,
            "total_events": len(events),
            "risk_score": round(score, 1),
            "risk_level": level,
        })

    return {"devices": devices, "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/device/narrative", response_model=DeviceNarrativeResponse)
async def device_narrative(payload: DeviceNarrativeRequest):
    device_name = payload.device_name
    start_time = time.perf_counter()

    events_data = _fetch_events(device_name, "device", 200)
    events = events_data.get("results", [])

    recalls_data = _fetch_recalls(device_name, 100)
    recalls = recalls_data.get("results", [])

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    return _build_device_narrative_response(device_name, events, recalls, elapsed_ms)


@app.get("/api/device/narrative/stream/{device_name}")
async def device_narrative_stream(device_name: str):
    async def generate_events():
        try:
            start_time = time.perf_counter()
            yield f"data: {json.dumps({'event': 'progress', 'data': {'percentage': 10, 'message': 'Fetching events...'}})}\n\n"
            events_data = _fetch_events(device_name, "device", 200)
            yield f"data: {json.dumps({'event': 'progress', 'data': {'percentage': 50, 'message': 'Fetching recalls...'}})}\n\n"
            recalls_data = _fetch_recalls(device_name, 100)
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
    query = payload.get("query", "")
    events_data = _fetch_events(query, "device", 200)
    events = events_data.get("results", [])
    recalls_data = _fetch_recalls(query, 100)
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
                    "message": "Fetching events and recalls",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            }
            yield f"data: {json.dumps({'type': 'agent_update', 'data': collector_state})}\n\n"

            events_data = _fetch_events(query, "device", 200)
            recalls_data = _fetch_recalls(query, 100)
            events = events_data.get("results", [])
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
