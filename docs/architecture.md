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
│  │               StateGraph with Checkpointer              ││
│  │  [User Question] → [Agent] ⟷ [Tools] → [Response]      ││
│  │         ↑                                               ││
│  │         └── ResolverContext (shared state) ◄────────────┘│
│  └─────────────────────────────────────────────────────────┘│
│                              │                               │
│  ┌───────────────────────────┼───────────────────────────┐  │
│  │              10 Agent Tools (Async-Enabled)            │  │
│  │                                                        │  │
│  │  RESOLVERS (populate shared context):                  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐               │  │
│  │  │ Device   │ │ Manufac. │ │ Location │               │  │
│  │  │ Resolver │ │ Resolver │ │ Resolver │               │  │
│  │  └──────────┘ └──────────┘ └──────────┘               │  │
│  │                                                        │  │
│  │  SEARCHERS (query FDA databases):                      │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│  │  │ Events   │ │ Recalls  │ │  510(k)  │ │   PMA    │  │  │
│  │  │ Search   │ │ Search   │ │  Search  │ │  Search  │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐               │  │
│  │  │  Class.  │ │   UDI    │ │ Regist.  │               │  │
│  │  │  Search  │ │  Search  │ │  Search  │               │  │
│  │  └──────────┘ └──────────┘ └──────────┘               │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
        │                              │
        ▼                              ▼
┌───────────────────┐    ┌────────────────────────────────────┐
│    LLM Factory    │    │           Data Sources              │
│ ┌───────────────┐ │    │ ┌──────────┐  ┌─────────────────┐  │
│ │  OpenRouter   │ │    │ │  GUDID   │  │   OpenFDA API   │  │
│ │    Bedrock    │ │    │ │ (SQLite) │  │  (7 endpoints)  │  │
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

### 5. Tool Design: Resolvers vs Searchers

**Decision**: Separate tools into two categories with distinct responsibilities.

**Why**:
- **Resolvers** translate user concepts into FDA-specific identifiers
- **Searchers** query FDA databases using those identifiers
- This separation enables the LLM to chain tools logically (resolve first, then search)
- Resolvers populate shared state that searchers can reference

**Tool Categories**:

| Category | Tool | Purpose | Data Source | Populates Context |
|----------|------|---------|-------------|-------------------|
| **Resolver** | `resolve_device` | Device names → product codes | GUDID (local) | ✅ `ResolvedEntities` |
| **Resolver** | `resolve_manufacturer` | Company names → FDA firm variations | OpenFDA | ✅ `ManufacturerInfo[]` |
| **Resolver** | `resolve_location` | Geographic location → manufacturers | OpenFDA | ✅ `LocationContext` |
| **Searcher** | `search_events` | Adverse events (MAUDE) | OpenFDA | ❌ |
| **Searcher** | `search_recalls` | Product recalls | OpenFDA | ✅ `RecallSearchResult` |
| **Searcher** | `search_510k` | 510(k) clearances | OpenFDA | ❌ |
| **Searcher** | `search_pma` | PMA approvals | OpenFDA | ❌ |
| **Searcher** | `search_classifications` | Device classifications | OpenFDA | ❌ |
| **Searcher** | `search_udi` | UDI records | OpenFDA | ❌ |
| **Searcher** | `search_registrations` | Establishment registrations | OpenFDA | ❌ |

**Resolver → Searcher Pattern**:
```
User: "What recalls are there for surgical masks?"

1. Agent calls resolve_device("surgical masks")
   → Returns product codes: FXX, MSH, OUK, etc.
   → Populates ResolverContext.devices

2. Agent calls search_recalls(query="surgical mask")
   → Uses natural language (recalls don't support product codes)
   → Returns recall records
```

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

## Shared State Architecture

### ResolverContext

**Decision**: Resolver tools populate a shared `ResolverContext` in the agent state.

**Why**:
- Resolvers extract structured data (product codes, manufacturer names, locations)
- This data should persist across the conversation for follow-up queries
- Search tools can potentially reference this context for auto-completion

**State Structure**:
```python
class ResolverContext(TypedDict, total=False):
    devices: Optional[ResolvedEntities]      # From resolve_device
    manufacturers: Optional[list[ManufacturerInfo]]  # From resolve_manufacturer
    location: Optional[LocationContext]      # From resolve_location

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    resolver_context: Annotated[ResolverContext, _merge_context]
    session_id: Optional[str]
```

**ContextAwareToolNode**:
After executing tools, the node extracts structured results from resolvers:
```python
def _extract_resolver_context(self) -> Optional[ResolverContext]:
    context = {}
    for tool_name, tool in self.resolver_tools.items():
        if hasattr(tool, 'get_last_structured_result'):
            result = tool.get_last_structured_result()
            if result:
                context[self._context_key(tool_name)] = result
    return context
```

### Session Persistence

**Decision**: Use LangGraph's `MemorySaver` checkpointer for multi-turn conversations.

**Why**:
- Chat UI needs state to persist across HTTP requests
- Follow-up questions should reference previous resolver results
- Session can be cleared when user starts a new topic

**Usage**:
```python
# With session persistence
response = agent.ask("What devices are made in China?", session_id="user-123")
# ... later ...
response = agent.ask("Any recalls for those?", session_id="user-123")
# Agent can reference the Chinese manufacturers from previous turn
```

## Error Handling Strategy

1. **Tool errors**: Caught and returned as tool output (agent can retry or explain)
2. **LLM errors**: Raised to caller with context
3. **API rate limits**: Exponential backoff with jitter
4. **Database errors**: Graceful degradation (skip tool, continue with others)

## Performance Considerations

- **Async HTTP with httpx**: All tools implement both sync (`_run`) and async (`_arun`) methods
- **Concurrent tool execution**: When the LLM requests multiple tools, `ContextAwareToolNode.ainvoke()` runs them in parallel via `asyncio.gather()`
- **Connection pooling**: Reuse HTTP connections to OpenFDA
- **Response caching**: Cache OpenFDA responses (configurable TTL)
- **Lazy loading**: Tools initialized only when needed
- **Streaming**: Don't buffer entire response before sending

### Async Architecture

**Decision**: Implement async HTTP in all tools using `httpx.AsyncClient`.

**Why**:
- When the LLM calls multiple tools (e.g., searching 5 manufacturers for recalls), sequential HTTP calls are slow
- Async execution runs all HTTP requests concurrently, reducing latency by 2-3x for multi-tool queries
- The `_arun` methods mirror `_run` but use non-blocking I/O

**Implementation**:
```python
# In ContextAwareToolNode.ainvoke():
tool_messages = await asyncio.gather(*[
    execute_tool(tc) for tc in last_message.tool_calls
])

# Each tool's _arun method:
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url, params=params)
```

**Agent methods**:
- `ask()` / `stream()` - Synchronous execution
- `ask_async()` / `stream_async()` - Async execution with concurrent tool calls

## Security

- **No credentials in code**: All secrets via environment variables
- **Input validation**: Pydantic models validate all inputs
- **SQL injection prevention**: Parameterized queries for GUDID
- **Rate limiting**: Configurable per-endpoint limits
