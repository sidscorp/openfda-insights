"""
FastAPI endpoints for FDA Intelligence Agent with SSE support
"""

import json
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from .tools import DeviceResolver
from .config import get_config
from .agent import FDAAgent

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
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


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

            yield f"data: {json.dumps({'type': 'start', 'question': question})}\n\n"

            for event in agent.stream(question, session_id=session_id):
                node_name = list(event.keys())[0] if event else "unknown"
                messages = event.get(node_name, {}).get("messages", [])

                if messages:
                    last_message = messages[-1]

                    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                        for tool_call in last_message.tool_calls:
                            yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_call['name'], 'args': tool_call['args']})}\n\n"

                    elif hasattr(last_message, 'content') and last_message.content:
                        if node_name == "tools":
                            yield f"data: {json.dumps({'type': 'tool_result', 'content': last_message.content[:500]})}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'thinking', 'content': last_message.content[:200]})}\n\n"

            final_result = agent.ask(question, session_id=session_id)
            yield f"data: {json.dumps({'type': 'complete', 'answer': final_result.content, 'model': final_result.model, 'tokens': final_result.total_tokens})}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
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
