# Architecture & Design Decisions

This document explains the engineering choices behind the FDA Explorer system.

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        User Interfaces                       │
│  ┌─────────┐  ┌─────────────┐  ┌──────────────────────────┐ │
│  │   CLI   │  │  REST API   │  │   Web UI (Future)        │ │
│  │ (Click) │  │  (FastAPI)  │  │   (Next.js planned)      │ │
│  └────┬────┘  └──────┬──────┘  └────────────┬─────────────┘ │
└───────┼──────────────┼──────────────────────┼───────────────┘
        │              │                      │
        ▼              ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                      FDA Agent (LangGraph)                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    StateGraph Workflow                  ││
│  │  [User Question] → [Agent] ⟷ [Tools] → [Response]      ││
│  └─────────────────────────────────────────────────────────┘│
│                              │                               │
│  ┌───────────────────────────┼───────────────────────────┐  │
│  │                     7 Agent Tools                      │  │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │  │
│  │ │ Device   │ │ Events   │ │ Recalls  │ │  510(k)  │   │  │
│  │ │ Resolver │ │ Search   │ │ Search   │ │  Search  │   │  │
│  │ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │  │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────┐                │  │
│  │ │   PMA    │ │  Class.  │ │   UDI    │                │  │
│  │ │  Search  │ │  Search  │ │  Search  │                │  │
│  │ └──────────┘ └──────────┘ └──────────┘                │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
        │                              │
        ▼                              ▼
┌───────────────────┐    ┌────────────────────────────────────┐
│    LLM Factory    │    │           Data Sources              │
│ ┌───────────────┐ │    │ ┌──────────┐  ┌─────────────────┐  │
│ │  OpenRouter   │ │    │ │  GUDID   │  │   OpenFDA API   │  │
│ │    Bedrock    │ │    │ │ (SQLite) │  │  (6 endpoints)  │  │
│ │    Ollama     │ │    │ └──────────┘  └─────────────────┘  │
│ └───────────────┘ │    └────────────────────────────────────┘
└───────────────────┘
```

## Key Design Decisions

### 1. Single Agent Architecture (Not Multi-Agent)

**Decision**: Use one LangGraph agent with multiple tools instead of specialized sub-agents.

**Why**:
- **Simplicity**: One agent is easier to debug, test, and maintain
- **Context sharing**: Single agent maintains full conversation context
- **Lower latency**: No agent-to-agent communication overhead
- **Cost efficiency**: Fewer LLM calls than multi-agent orchestration

**Trade-off**: Less parallelization of complex queries, but FDA queries are typically sequential (resolve device → search events → analyze).

### 2. LangGraph over Raw LangChain

**Decision**: Use LangGraph's StateGraph for agent orchestration.

**Why**:
- **Explicit control flow**: Clear agent → tools → agent cycle
- **State management**: TypedDict state with message history
- **Debuggability**: Can inspect state at each node
- **Streaming**: Built-in support for streaming responses

**Alternative considered**: LangChain's AgentExecutor - rejected due to less visibility into execution flow.

### 3. Multi-Provider LLM Factory

**Decision**: Central `LLMFactory` class that abstracts provider differences.

**Why**:
- **Flexibility**: Switch providers without changing agent code
- **Cost optimization**: Use cheaper models for simple queries
- **Resilience**: Fall back to different providers if one fails
- **Local development**: Use Ollama locally, cloud in production

**Implementation**:
```python
LLMFactory.create(provider="bedrock", model="anthropic.claude-3-haiku")
LLMFactory.create(provider="openrouter", model="anthropic/claude-3-haiku")
LLMFactory.create(provider="ollama", model="llama3.1")
```

### 4. GUDID as Local SQLite Database

**Decision**: Download and query GUDID locally rather than API calls.

**Why**:
- **Speed**: Local queries are 10-100x faster than API calls
- **Fuzzy matching**: Full-text search with custom scoring
- **No rate limits**: Unlimited queries
- **Offline capability**: Works without internet

**Trade-off**: Requires periodic database updates (monthly GUDID releases).

**Schema design**: Denormalized for query speed over storage efficiency.

### 5. Tool Design: Focused Single-Purpose Tools

**Decision**: Each tool does one thing well with structured output.

**Why**:
- **LLM understanding**: Simpler tool descriptions = better tool selection
- **Composability**: Agent can combine tools for complex queries
- **Testability**: Each tool can be unit tested independently
- **Error isolation**: Tool failures don't cascade

**The 7 tools**:
| Tool | Purpose | Data Source |
|------|---------|-------------|
| `DeviceResolverTool` | Map names → FDA codes | GUDID (local) |
| `SearchEventsTool` | Adverse events | OpenFDA |
| `SearchRecallsTool` | Product recalls | OpenFDA |
| `Search510kTool` | 510(k) clearances | OpenFDA |
| `SearchPMATool` | PMA approvals | OpenFDA |
| `SearchClassificationsTool` | Device classifications | OpenFDA |
| `SearchUDITool` | UDI records | OpenFDA |

### 6. FastAPI with SSE Streaming

**Decision**: Server-Sent Events for real-time agent responses.

**Why**:
- **User experience**: Show thinking/tool calls as they happen
- **Simplicity**: SSE is simpler than WebSockets for one-way streaming
- **Compatibility**: Works with standard HTTP infrastructure
- **Resumability**: Can reconnect and continue stream

**Implementation**: `/api/agent/stream/{question}` endpoint yields events as agent executes.

### 7. Configuration via Pydantic Settings

**Decision**: Use `pydantic-settings` for configuration management.

**Why**:
- **Type safety**: Validated configuration at startup
- **Environment variables**: 12-factor app compliance
- **Defaults**: Sensible defaults with override capability
- **Documentation**: Self-documenting configuration schema

**Hierarchy** (highest to lowest priority):
1. CLI arguments
2. Environment variables
3. `.env` file
4. `config/config.yaml`
5. Code defaults

### 8. Click + Rich for CLI

**Decision**: Click framework with Rich for terminal output.

**Why**:
- **Click**: Composable commands, automatic help, type conversion
- **Rich**: Formatted tables, panels, progress bars, syntax highlighting
- **Pipeline-friendly**: `--json` flag for machine-readable output

## Data Flow

### Agent Query Flow

```
1. User asks: "What recalls has Medtronic had for pacemakers?"

2. Agent receives question, decides to:
   a. Resolve "pacemaker" → product codes
   b. Search recalls with manufacturer filter

3. Tool execution:
   DeviceResolverTool("pacemaker") → ["DXY", "DTB", ...]
   SearchRecallsTool(product_codes=["DXY"], manufacturer="Medtronic") → [recalls...]

4. Agent synthesizes results into natural language response

5. Response returned with token usage and cost (if available)
```

### Device Resolution Flow

```
1. Query: "surgical mask"

2. GUDID SQLite search:
   - Exact match on brand_name
   - Fuzzy match on brand_name (Levenshtein)
   - Full-text search on description
   - Company name search

3. Score and rank matches by confidence

4. Return:
   - Matched devices with product codes
   - GMDN terms
   - Primary DI (device identifier)
   - Match type and confidence score
```

## Error Handling Strategy

1. **Tool errors**: Caught and returned as tool output (agent can retry or explain)
2. **LLM errors**: Raised to caller with context
3. **API rate limits**: Exponential backoff with jitter
4. **Database errors**: Graceful degradation (skip tool, continue with others)

## Performance Considerations

- **Connection pooling**: Reuse HTTP connections to OpenFDA
- **Response caching**: Cache OpenFDA responses (configurable TTL)
- **Lazy loading**: Tools initialized only when needed
- **Streaming**: Don't buffer entire response before sending

## Security

- **No credentials in code**: All secrets via environment variables
- **Input validation**: Pydantic models validate all inputs
- **SQL injection prevention**: Parameterized queries for GUDID
- **Rate limiting**: Configurable per-endpoint limits
