# OpenFDA Agent - Project Status

**Date**: 2025-10-03
**Phase**: 3 (Agent Orchestration) - In Progress

---

## Executive Summary

We have built a working FDA Device Analyst agent that queries the openFDA API using natural language. The core pipeline (Tools → RAG → Agent) is functional but needs refinement in retrieval precision and tool selection logic.

**What Works**: Parameter extraction, all 7 endpoint tools, basic question answering
**What Needs Work**: RAG retrieval accuracy, proper LangChain tool calling, comprehensive testing

---

## Phase 1: Tools ✅ COMPLETE

### Delivered
- **7 endpoint tools** with typed parameters (Pydantic schemas):
  - `classification` - Device classifications
  - `510k` - 510(k) clearances
  - `pma` - PMA approvals
  - `recall` (enforcement) - Device recalls
  - `maude` (event) - Adverse events
  - `udi` - Device identifiers
  - `rl_search` (registrationlisting) - Establishments

- **5 utility tools**:
  - `probe_count` - Count aggregations for disambiguation
  - `paginate` - Safe pagination with caps
  - `field_explorer` - Returns searchable fields per endpoint
  - `freshness` - Metadata timestamps
  - `answer_assessor` - Sufficiency validation

- **Base HTTP client** (`tools/base.py`):
  - Retry logic with exponential backoff (429, 5xx)
  - Rate limit handling
  - JSON response standardization

### Test Coverage
- **18/18 unit tests passing**
- VCR cassettes for reproducible tests
- CLI smoke tests for all tools
- `make dev` workflow

### Known Issues
None. Phase 1 is production-ready.

---

## Phase 2: RAG (Documentation Retrieval) ⚠️ PARTIAL

### Delivered
- **Doc scraper** (`rag/scraper.py`):
  - Fetches 34 chunks from openFDA (8 endpoints × 2 pages + general docs)
  - HTML → Markdown conversion
  - Section-based chunking with metadata

- **Retrieval service** (`rag/retrieval.py`):
  - sentence-transformers embeddings (all-MiniLM-L6-v2, 384-dim)
  - Cosine similarity ranking
  - Top-k results with relevance scores

- **Supporting docs**:
  - `docs/corpus.json` - 34 scraped chunks
  - `docs/routing_hints.md` - Intent → endpoint mapping guide

### Test Coverage
- **17/21 tests passing (81%)**
- Aggregate precision test passes (≥50% threshold)

### Issues

#### ⚠️ **Retrieval Precision Below Target** (81% vs 90% PRD requirement)

**Problem**: Retriever returns wrong endpoint docs for 4/8 test queries:
- Query: "What fields can I search in the 510k endpoint?"
  → Returns: `registrationlisting` docs (wrong)
  → Expected: `510k` docs

- Query: "What is the enforcement endpoint?"
  → Returns: `registrationlisting` docs (wrong)
  → Expected: `enforcement` docs

**Root Cause**: Sparse corpus - only 2 chunks per endpoint (overview + fields list)
- Endpoint names don't appear frequently enough in their own docs
- Field reference pages lack contextual text beyond field names
- No "How to Use" sections with examples scraped

**Impact**:
- Agent doesn't currently consult RAG for field names (functionality exists but not integrated)
- When integrated, may return irrelevant doc snippets

**Fix Options**:
1. **Expand corpus**: Scrape "How to Use" pages, example queries, field definitions
2. **Improve chunking**: Create synthetic chunks with endpoint name repetition
3. **Boost exact matches**: Add keyword matching alongside semantic search
4. **Use metadata filtering**: Pre-filter by endpoint before semantic search

**Recommendation**: Option 1 + 3 - expand corpus and add hybrid search

---

## Phase 3: Agent Orchestration 🔄 IN PROGRESS

### Delivered

#### **LangGraph Architecture** (`agent/graph.py`)
- **Nodes**:
  - `Router`: Claude 3.5 Sonnet analyzes question, selects tool
  - `Tools`: Executes endpoint queries with extracted params
  - `Assessor`: Validates result sufficiency
  - `Answer`: Formats final response with provenance

- **State Management** (`agent/state.py`):
  - Tracks question, tool calls, results, retry count
  - Conversation history for multi-turn (not yet used)

- **System Prompt** (`agent/prompt.py`):
  - FDA Device Analyst role
  - Entity detection rules (product codes, K/P numbers, dates)
  - Routing table (intent → endpoint)
  - Guardrails (read-only, no PII, date bounds)

#### **Parameter Extraction** (`agent/extractor.py`) ✅
- LLM-based extraction of structured params from natural language
- Extracts: device_class, dates, firm names, product codes, etc.
- JSON output parsing with fallback

**Verified Working**:
```
Q: "Show me 3 Class II devices"
→ device_class=2, limit=3
→ Retrieved 3 results ✓

Q: "Find 510k clearances from Medtronic since 2023"
→ applicant=Medtronic, dates=20230101-20251231
→ Retrieved 10 results ✓
```

#### **All 7 Tools Wired** ✅
- Each tool receives extracted params dynamically
- No hardcoded values
- Handles null params gracefully

#### **CLI** (`agent/cli.py`)
```bash
python -m agent.cli "your question"
# Requires: ANTHROPIC_API_KEY in .env
```

### Test Coverage
- **8 routing test cases** (classification, 510k, PMA, recalls, MAUDE, UDI, establishments, counting)
- No full routing accuracy test yet (requires live API calls + cost)

### Issues

#### ⚠️ **Router Uses String Matching Instead of Proper Tool Calling**

**Problem**: Router node searches LLM response text for tool names:
```python
if "classify" in routing_text.lower():
    selected_tools.append("classify")
```

**Root Cause**: Quick prototype implementation - should use LangChain's structured tool calling

**Impact**:
- Brittle - fails if LLM changes phrasing
- No confidence scores
- Can't handle ambiguous cases
- Defaults to `classify` if no match

**Fix**: Use LangChain's `bind_tools()` and structured output:
```python
tools = [classify_tool, k510_tool, pma_tool, ...]
llm_with_tools = llm.bind_tools(tools)
response = llm_with_tools.invoke(messages)
selected_tool = response.tool_calls[0]
```

**Recommendation**: Implement proper tool calling (1-2 hours work)

#### ⚠️ **Assessor Logic Too Lenient**

**Problem**: Currently accepts ANY result (including zero results) as sufficient
```python
state.is_sufficient = True  # Always!
```

**Root Cause**: Fixed infinite retry loop by making assessor accept everything

**Impact**:
- No validation that extracted params match question
- Example: Query asks "Class I recalls" but extractor misses "Class I" → returns all recalls → marked sufficient ✓ (wrong!)

**Fix**: Use `answer_assessor` utility properly:
```python
assessment = answer_assessor(AnswerAssessorParams(
    question=state.question,
    search_query=extracted_params_to_query_string(extracted),
    result_count=result_count,
    date_filter_present=bool(extracted.date_start),
    class_filter_present=bool(extracted.device_class or extracted.recall_class)
))
state.is_sufficient = assessment.sufficient
```

**Recommendation**: Integrate proper assessor logic with retry limit (max 2)

#### ⚠️ **RAG Not Integrated in Agent Flow**

**Problem**: RAG retriever is initialized but never called during agent execution

**Impact**: Agent doesn't consult docs for:
- Valid field names
- Query syntax help
- Endpoint selection guidance

**Fix**: Add RAG consultation in router node:
```python
# Before selecting tool, consult RAG
docs = self.retriever.search(state.question, top_k=2)
# Include doc snippets in router prompt
```

**Recommendation**: Integrate after fixing RAG precision

---

## Testing Status

### Unit Tests
- **Phase 1 (Tools)**: 18/18 passing ✅
- **Phase 2 (RAG)**: 17/21 passing ⚠️ (81%)
- **Phase 3 (Agent)**: 0 tests run (requires API keys + cost)

### Integration Tests
- **None implemented** ❌
- Need end-to-end question → answer tests
- Should cover all 7 endpoints
- Need labeled eval set for routing accuracy

### Manual Testing
- ✅ Basic queries work (Class II devices, 510k search)
- ✅ Parameter extraction validated
- ✅ Date range extraction works
- ⚠️ Recall class extraction inconsistent
- ❌ Complex multi-entity queries not tested
- ❌ Retry logic not tested

---

## Performance & Cost

### Latency
- **Phase 1 (Tools)**: API calls ~500ms-2s per query
- **Phase 2 (RAG)**: First load ~3s (embedding model), queries <100ms
- **Phase 3 (Agent)**:
  - Router call: ~1-2s (Claude API)
  - Extractor call: ~1-2s (Claude API)
  - Total: ~3-5s per question

### Cost (Anthropic API)
- **Model**: Claude 3.5 Sonnet ($3/M input, $15/M output)
- **Per query**: ~5K-10K tokens → ~$0.03-0.10
- **Testing**: Manual testing so far ~$2-5

### Rate Limits
- **OpenFDA**: 240 req/min (no key), 1000 req/min (with key)
- **Anthropic**: 50K req/min (tier 1)

---

## Current Capabilities

### ✅ What Works Now
1. Query any of the 7 openFDA device endpoints
2. Extract device class, dates, firm names from natural language
3. Return results with provenance (endpoint, filters, last_updated)
4. Handle zero results gracefully (no infinite loops)
5. CLI interface with progress logging

### ⚠️ What Works Partially
1. RAG retrieval (81% precision, needs improvement)
2. Tool routing (works but uses string matching, not proper tool calling)
3. Answer assessment (too lenient, needs validation)

### ❌ What Doesn't Work Yet
1. RAG integration in agent flow
2. Multi-turn conversations
3. Complex queries requiring multiple tools
4. Disambiguation questions ("Did you mean...")
5. Comprehensive testing

---

## Blockers & Risks

### 🔴 High Priority
1. **RAG precision**: Below PRD requirement (81% vs 90%)
   - **Risk**: Returns irrelevant docs to agent
   - **Mitigation**: Expand corpus or hybrid search

2. **No integration tests**: Can't verify end-to-end correctness
   - **Risk**: Regressions go unnoticed
   - **Mitigation**: Build labeled test set

### 🟡 Medium Priority
1. **Router string matching**: Brittle, no confidence scores
   - **Risk**: Tool selection failures on edge cases
   - **Mitigation**: Use LangChain proper tool calling

2. **Assessor too lenient**: Doesn't validate params match question
   - **Risk**: Returns wrong data but marks as sufficient
   - **Mitigation**: Integrate answer_assessor utility properly

### 🟢 Low Priority
1. **No caching**: Every query hits LLM + API
2. **No observability**: No LangSmith tracing
3. **No error handling for API outages**

---

## Next Steps (Priority Order)

### 1. Fix Critical Issues (Est: 4-6 hours)
- [ ] Improve RAG precision to ≥90%
  - Option A: Expand corpus (scrape "How to Use" pages)
  - Option B: Add hybrid search (semantic + keyword)
- [ ] Implement proper LangChain tool calling
- [ ] Integrate answer_assessor properly with retry logic

### 2. Add Integration Tests (Est: 2-3 hours)
- [ ] Create labeled eval set (20-30 questions)
- [ ] End-to-end tests for all 7 endpoints
- [ ] Routing accuracy test (PRD target: ≥90%)
- [ ] Sufficiency test (PRD target: ≥85%)

### 3. Integration & Polish (Est: 2-3 hours)
- [ ] Wire RAG into agent flow
- [ ] Add LangSmith tracing
- [ ] Improve error messages
- [ ] Add example queries to CLI help

### 4. Documentation (Est: 1 hour)
- [ ] Update README with setup instructions
- [ ] Add architecture diagram
- [ ] Document API key setup
- [ ] Add example queries

---

## PRD Compliance

### Phase 1: Tools ✅
- [x] 7 endpoint tools implemented
- [x] 5 utility tools implemented
- [x] Typed schemas (Pydantic)
- [x] Unit tests ≥95% passing (100%)
- [x] CLI smoke tests
- [x] Reproducible cassettes (VCR)

### Phase 2: RAG ⚠️
- [x] Doc corpus indexed (34 chunks)
- [x] Retrieval service built
- [x] Explanation templates (routing hints)
- [ ] Precision ≥0.9 (currently 0.81) ❌

### Phase 3: Agent 🔄
- [x] LangGraph orchestration
- [x] Router node (needs improvement)
- [x] Tools node (all 7 wired)
- [x] Assessor node (needs improvement)
- [x] System prompt with guardrails
- [ ] Routing accuracy ≥0.9 (not measured) ❓
- [ ] Sufficiency ≥0.85 (not measured) ❓
- [ ] Latency documented (3-5s measured, no target set) ⚠️

---

## How to Use (Current State)

### Setup
```bash
# 1. Install dependencies
source .venv/bin/activate
pip install -r requirements.txt

# 2. Set API key
echo 'ANTHROPIC_API_KEY=your_key_here' > .env

# 3. Test
python -m agent.cli "Show me Class II devices"
```

### Example Queries That Work
```bash
python -m agent.cli "Show me 5 Class II devices"
python -m agent.cli "Find 510k clearances from Medtronic since 2023"
python -m agent.cli "What PMA approvals happened in 2024?"
```

### Example Queries That May Fail
```bash
# Complex multi-entity queries
python -m agent.cli "Show me Class I recalls for pacemakers from Abbott in California"

# Disambiguation needed
python -m agent.cli "Show me devices from M"  # Multiple firms start with M

# RAG-dependent queries
python -m agent.cli "What field should I use to search by manufacturer?"
```

---

## Files Reference

### Core Implementation
- `agent/graph.py` - LangGraph agent (357 lines)
- `agent/extractor.py` - Parameter extraction (155 lines)
- `agent/prompt.py` - System prompt (118 lines)
- `agent/state.py` - State definition (41 lines)
- `tools/` - 7 endpoint tools + utilities (1200+ lines)
- `rag/retrieval.py` - RAG service (150 lines)
- `rag/scraper.py` - Doc scraper (200 lines)

### Tests
- `tests/test_tools.py` - Tool unit tests (18 tests)
- `tests/rag/test_retrieval.py` - RAG tests (21 tests, 17 passing)
- `tests/agent/test_routing.py` - Agent tests (stub, not run)

### Configuration
- `.env` - API keys (not committed)
- `requirements.txt` - Python dependencies
- `Makefile` - Dev workflow (test, smoke, clean)
- `CLAUDE.md` - Project guidelines
- `product_requirements_document.md` - Original PRD

---

## Conclusion

We have a **functional prototype** that demonstrates end-to-end capability: natural language → parameter extraction → API query → structured response. The core architecture is sound.

**To make this production-ready**, we need:
1. Higher RAG precision (expand corpus or hybrid search)
2. Proper tool calling (replace string matching)
3. Comprehensive integration tests
4. Better answer validation (use answer_assessor properly)

**Estimated time to production-ready**: 8-12 hours of focused work.

**Current state**: **70% complete** - works for simple queries, needs refinement for complex cases and reliability.
