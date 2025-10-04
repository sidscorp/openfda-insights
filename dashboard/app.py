"""
FDA Device Query Assistant Dashboard - FastAPI Backend

Professional web interface for FDA analysts to interact with the openFDA agent.
"""
import asyncio
import json
import os
import uuid
import io
import re
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import redirect_stdout

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Import our agent
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.graph import FDAAgent
from dotenv import load_dotenv

load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="FDA Device Query Assistant",
    description="Professional interface for querying FDA device data",
    version="1.0.0"
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

# Store active sessions and query history
sessions: Dict[str, Dict] = {}
query_history: List[Dict] = []

# Initialize agent (singleton)
agent = None

def get_agent():
    """Get or create FDA agent instance."""
    global agent
    if agent is None:
        api_key = os.getenv("OPENFDA_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")
        agent = FDAAgent(api_key=api_key, anthropic_api_key=anthropic_key)
    return agent


class QueryRequest(BaseModel):
    """Query request model."""
    question: str
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    """Query response model."""
    session_id: str
    question: str
    answer: str
    provenance: Dict
    metadata: Dict


@app.get("/")
async def root():
    """Serve the main dashboard page."""
    return FileResponse("dashboard/static/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        agent = get_agent()
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "agent": "initialized" if agent else "not initialized"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.post("/query")
async def submit_query(request: QueryRequest) -> QueryResponse:
    """Submit a query to the FDA agent."""
    try:
        # Get or create session
        session_id = request.session_id or str(uuid.uuid4())
        if session_id not in sessions:
            sessions[session_id] = {
                "created": datetime.now().isoformat(),
                "queries": []
            }

        # Get agent and process query
        agent = get_agent()

        # Run query
        result = agent.query(request.question)

        # Store in history
        query_record = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "question": request.question,
            "answer": result.get("answer", ""),
            "provenance": result.get("provenance", {}),
            "metadata": {
                "endpoint": result.get("selected_endpoint"),
                "retry_count": result.get("retry_count", 0),
                "is_sufficient": result.get("is_sufficient", False)
            }
        }

        sessions[session_id]["queries"].append(query_record)
        query_history.append(query_record)

        # Keep only last 100 queries in memory
        if len(query_history) > 100:
            query_history.pop(0)

        return QueryResponse(
            session_id=session_id,
            question=request.question,
            answer=result.get("answer", ""),
            provenance=result.get("provenance", {}),
            metadata=query_record["metadata"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
async def get_history(session_id: Optional[str] = None, limit: int = 20):
    """Get query history."""
    if session_id and session_id in sessions:
        # Return specific session history
        queries = sessions[session_id]["queries"][-limit:]
    else:
        # Return recent queries across all sessions
        queries = query_history[-limit:]

    return {"queries": queries, "total": len(queries)}


async def process_query_with_updates(agent, question, websocket):
    """Process query while streaming intermediate steps in real-time."""

    import threading
    import queue
    import time

    # Queue for passing messages between threads
    message_queue = queue.Queue()
    result_holder = {'result': None, 'error': None}

    # Custom stream handler to capture output in real-time
    class StreamToQueue(io.StringIO):
        def __init__(self, queue, websocket_send_func):
            super().__init__()
            self.queue = queue
            self.websocket_send_func = websocket_send_func
            self.buffer = ""

        def write(self, text):
            self.buffer += text
            if '\n' in text:
                lines = self.buffer.split('\n')
                for line in lines[:-1]:
                    if line.strip():
                        self.queue.put(line)
                self.buffer = lines[-1]
            return len(text)

    # Function to run agent in thread
    def run_agent():
        try:
            stream = StreamToQueue(message_queue, None)
            with redirect_stdout(stream):
                result_holder['result'] = agent.query(question)
        except Exception as e:
            result_holder['error'] = str(e)
        finally:
            message_queue.put(None)  # Signal completion

    # Start agent in background thread
    agent_thread = threading.Thread(target=run_agent)
    agent_thread.start()

    # Send initial status
    await websocket.send_json({
        "type": "processing",
        "step": "parse",
        "message": "🔍 Analyzing your query...",
        "details": {"question": question}
    })
    await asyncio.sleep(0.3)  # Small delay for visual effect

    # Process messages from queue in real-time
    while True:
        try:
            # Check for new messages with timeout
            line = message_queue.get(timeout=0.1)

            if line is None:  # Completion signal
                break

            # Add small delay between messages for visual effect
            await asyncio.sleep(0.2)

            # Parse and send the line
            if '[Router]' in line:
                # Extract routing information
                if 'Selected endpoint:' in line:
                    endpoint = line.split('Selected endpoint:')[-1].strip()
                    await websocket.send_json({
                        "type": "processing",
                        "step": "route",
                        "message": f"🎯 Selected endpoint: {endpoint}",
                        "details": {"endpoint": endpoint}
                    })
                elif 'Strategy:' in line:
                    strategy = line.split('Strategy:')[-1].strip()
                    await websocket.send_json({
                        "type": "processing",
                        "step": "strategy",
                        "message": f"📋 Search strategy: {strategy}",
                        "details": {"strategy": strategy}
                    })
                elif 'Plan:' in line:
                    plan = line.split('Plan:')[-1].strip()
                    await websocket.send_json({
                        "type": "processing",
                        "step": "plan",
                        "message": f"📝 Plan: {plan}",
                        "details": {"plan": plan}
                    })

            elif '[Tools]' in line:
                if 'Extracting parameters' in line:
                    await websocket.send_json({
                        "type": "processing",
                        "step": "extract",
                        "message": "⚙️ Extracting search parameters...",
                        "details": {}
                    })
                elif 'Extracted params:' in line:
                    # Extract parameter details
                    params_str = line.split('Extracted params:')[-1].strip()
                    await websocket.send_json({
                        "type": "processing",
                        "step": "parameters",
                        "message": f"📊 Parameters: {params_str}",
                        "details": {"parameters": params_str}
                    })
                elif 'Retrieved' in line and 'results' in line:
                    # Extract result count
                    count = re.search(r'Retrieved (\d+) results', line)
                    if count:
                        await websocket.send_json({
                            "type": "processing",
                            "step": "results",
                            "message": f"✅ Found {count.group(1)} results",
                            "details": {"count": count.group(1)}
                        })

            elif '[Assessor]' in line:
                if 'Sufficient:' in line:
                    sufficient = 'True' in line
                    reason = line.split('-')[-1].strip() if '-' in line else ""
                    await websocket.send_json({
                        "type": "processing",
                        "step": "assess",
                        "message": f"🔍 Assessment: {'✅ Sufficient' if sufficient else '⚠️ Needs refinement'}",
                        "details": {"sufficient": sufficient, "reason": reason}
                    })

            elif '[Answer]' in line:
                await websocket.send_json({
                    "type": "processing",
                    "step": "format",
                    "message": "📝 Formatting response...",
                    "details": {}
                })

        except queue.Empty:
            # No new message, continue checking
            await asyncio.sleep(0.05)
            continue

    # Wait for thread to complete
    agent_thread.join(timeout=30)

    if result_holder['error']:
        raise Exception(result_holder['error'])

    return result_holder['result']


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time query processing with detailed updates."""
    await websocket.accept()
    session_id = str(uuid.uuid4())

    try:
        while True:
            # Receive query from client
            data = await websocket.receive_json()
            question = data.get("question", "")
            show_details = data.get("show_details", True)  # Option to show/hide details

            if not question:
                await websocket.send_json({"error": "No question provided"})
                continue

            try:
                agent = get_agent()

                # Process query with detailed updates
                if show_details:
                    result = await process_query_with_updates(agent, question, websocket)
                else:
                    # Simple mode - just show start and end
                    await websocket.send_json({
                        "type": "status",
                        "message": "Processing your query..."
                    })
                    result = agent.query(question)

                # Send formatted results
                await websocket.send_json({
                    "type": "complete",
                    "answer": result.get("answer", ""),
                    "provenance": result.get("provenance", {}),
                    "metadata": {
                        "endpoint": result.get("selected_endpoint"),
                        "retry_count": result.get("retry_count", 0),
                        "is_sufficient": result.get("is_sufficient", False),
                        "parameters": result.get("extracted_params", {}),
                        "lucene_query": result.get("provenance", {}).get("lucene_query", ""),
                        "assessment": result.get("assessor_reason", "")
                    }
                })

                # Store in history
                query_record = {
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "question": question,
                    "answer": result.get("answer", ""),
                    "provenance": result.get("provenance", {})
                }
                query_history.append(query_record)

            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error processing query: {str(e)}"
                })

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")


@app.get("/export/{format}")
async def export_results(format: str, session_id: Optional[str] = None):
    """Export query results in various formats."""
    if format not in ["json", "csv", "pdf"]:
        raise HTTPException(status_code=400, detail="Invalid format")

    # Get queries to export
    if session_id and session_id in sessions:
        queries = sessions[session_id]["queries"]
    else:
        queries = query_history[-50:]  # Last 50 queries

    if format == "json":
        return JSONResponse(
            content={"queries": queries},
            headers={
                "Content-Disposition": f"attachment; filename=fda_queries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            }
        )

    elif format == "csv":
        # Generate CSV
        import csv
        import io

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["timestamp", "question", "answer", "endpoint", "results_count"]
        )
        writer.writeheader()

        for query in queries:
            writer.writerow({
                "timestamp": query["timestamp"],
                "question": query["question"],
                "answer": query["answer"][:500],  # Truncate long answers
                "endpoint": query.get("metadata", {}).get("endpoint", ""),
                "results_count": query.get("provenance", {}).get("result_count", 0)
            })

        from fastapi.responses import Response
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=fda_queries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )

    else:  # PDF
        # For now, return a message - full PDF generation would require additional libraries
        return JSONResponse(
            content={
                "message": "PDF export requires additional setup with weasyprint or reportlab",
                "queries": len(queries)
            }
        )


@app.get("/templates")
async def get_query_templates():
    """Get predefined query templates for common searches."""
    templates = [
        {
            "category": "Recalls",
            "queries": [
                "Show me Class I recalls from this year",
                "Find recalls from {company} in the last 6 months",
                "How many Class II recalls were there in 2024?",
                "Show me cardiac device recalls"
            ]
        },
        {
            "category": "510(k) Clearances",
            "queries": [
                "Show me recent 510k clearances from Medtronic",
                "Find 510k clearances for orthopedic devices",
                "What 510k clearances were issued this month?",
                "Show me K{number}"
            ]
        },
        {
            "category": "PMA Approvals",
            "queries": [
                "Find PMA approvals from Abbott",
                "Show me P{number}",
                "Recent PMA approvals for cardiac devices",
                "How many PMAs were approved in 2024?"
            ]
        },
        {
            "category": "Adverse Events",
            "queries": [
                "Show adverse events for pacemakers",
                "Find serious injuries from insulin pumps",
                "Recent adverse events with patient deaths",
                "Malfunction reports for {device_type}"
            ]
        },
        {
            "category": "Device Classifications",
            "queries": [
                "Show me Class III cardiac devices",
                "Find Class II orthopedic implants",
                "What is the classification for product code {code}?",
                "List surgical devices by class"
            ]
        }
    ]
    return {"templates": templates}


if __name__ == "__main__":
    print("=" * 60)
    print("FDA Device Query Assistant Dashboard")
    print("=" * 60)
    print("\nStarting server at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop the server")
    print("-" * 60)

    # Use the app directly, not as a string, and disable reload for stability
    uvicorn.run(app, host="0.0.0.0", port=8000)