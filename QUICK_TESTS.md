# Quick Test Commands

Copy-paste these commands to quickly verify components are working.

## 1. Quick RAG Test (No API Key Needed)

```python
from rag.retrieval import DocRetriever
r = DocRetriever("docs/corpus.json")
results = r.search("How do I search for Class II devices?", top_k=1)
print(f"Top result: {results[0].endpoint} - {results[0].section}")
# Expected: classification - Synthetic Howto
```

## 2. Quick Parameter Extraction Test (Requires ANTHROPIC_API_KEY)

```python
from agent.extractor import ParameterExtractor
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)
extractor = ParameterExtractor(llm)

# Test 1: Class extraction
params = extractor.extract("Show me 5 Class II devices")
print(f"device_class={params.device_class}, limit={params.limit}")
# Expected: device_class=2, limit=5

# Test 2: K-number regex extraction
params = extractor.extract("Show me K123456")
print(f"k_number={params.k_number}")
# Expected: k_number=K123456

# Test 3: Recall class normalization
params = extractor.extract("Any Class I recalls?")
print(f"recall_class={params.recall_class}")
# Expected: recall_class=Class I
```

## 3. Quick Router Test (Requires ANTHROPIC_API_KEY)

```python
from agent.router import route
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)

# Test different endpoint routing
queries = [
    "Show me Class II devices",
    "Find 510k clearances",
    "Any recalls?",
    "Show adverse events"
]

for q in queries:
    endpoint = route(q, llm)
    print(f"{q:30s} → {endpoint}")

# Expected:
# Show me Class II devices      → classification
# Find 510k clearances          → 510k
# Any recalls?                   → recall
# Show adverse events           → maude
```

## 4. Quick End-to-End Test (Requires ANTHROPIC_API_KEY)

```python
from agent.graph import FDAAgent

agent = FDAAgent()
result = agent.query("Show me 3 Class II devices")

print(f"Endpoint: {result['selected_endpoint']}")
print(f"Device Class: {result['extracted_params']['device_class']}")
print(f"Results: {result['provenance']['result_count']}")
print(f"Sufficient: {result['is_sufficient']}")

# Expected:
# Endpoint: classification
# Device Class: 2
# Results: 3
# Sufficient: True
```

## 5. Quick Assessor Test (No API Key Needed)

```python
from tools.utils import AnswerAssessorParams, answer_assessor

# Test 1: Missing class filter (should be insufficient)
assessment = answer_assessor(AnswerAssessorParams(
    question="Show me Class I recalls",
    search_query="firm_name:Medtronic",
    result_count=10,
    date_filter_present=False,
    class_filter_present=False
))
print(f"Test 1 - Missing filter: {assessment.sufficient} - {assessment.reason}")
# Expected: False - Question mentions device/recall class but no class filter was applied

# Test 2: Proper filters (should be sufficient)
assessment = answer_assessor(AnswerAssessorParams(
    question="Show me Class I recalls since 2023",
    search_query="recall_class:Class I AND date:[20230101 TO 20251231]",
    result_count=5,
    date_filter_present=True,
    class_filter_present=True
))
print(f"Test 2 - Proper filters: {assessment.sufficient} - {assessment.reason}")
# Expected: True - All requirements met
```

## 6. Quick CLI Test (Requires ANTHROPIC_API_KEY)

```bash
# Test with explain mode
python -m agent.cli "Show me 3 Class II devices" --explain

# Expected output should show:
# - [ROUTER] Selected endpoint: classification
# - [EXTRACTOR] device_class=2, limit=3
# - [ASSESSOR] Sufficient: True
# - Answer: Found 3 results
```

## 7. Run All Unit Tests

```bash
# All tests (should show 39 passed)
python -m pytest tests/ --ignore=tests/integration -v

# Just RAG tests
python -m pytest tests/rag/ -v

# Just tool tests
python -m pytest tests/test_tools.py -v
```

## 8. Check Corpus Stats

```python
import json
from pathlib import Path

corpus = json.loads(Path("docs/corpus.json").read_text())
print(f"Total chunks: {len(corpus)}")

# Count by endpoint
from collections import Counter
endpoints = Counter(c['endpoint'] for c in corpus)
for endpoint, count in sorted(endpoints.items()):
    print(f"  {endpoint:20s}: {count} chunks")

# Expected output:
# Total chunks: 41
#   510k                : 3 chunks (1 synthetic howto + 2 scraped)
#   classification      : 3 chunks
#   device_overview     : 2 chunks
#   enforcement         : 3 chunks
#   event               : 3 chunks
#   pma                 : 3 chunks
#   query_parameters    : 2 chunks
#   query_syntax        : 2 chunks
#   registrationlisting : 4 chunks
#   udi                 : 3 chunks
```

## 9. Check Hybrid Retrieval is Working

```python
from rag.retrieval import DocRetriever

retriever = DocRetriever("docs/corpus.json")
print(f"Using hybrid: {retriever.use_hybrid}")
print(f"Total docs: {len(retriever.docs)}")

# Test endpoint prefiltering
results = retriever.search("Show me 510k clearances", top_k=3)
print("\nTop 3 results for '510k clearances':")
for i, r in enumerate(results, 1):
    print(f"  {i}. {r.endpoint:20s} (score: {r.score:.4f})")

# Should show 510k endpoints at the top due to prefiltering
```

## 10. Full Sanity Check Script

```bash
# Run the comprehensive sanity checks
python sanity_checks.py

# Should output:
# ✓ All RAG queries correctly identify endpoints
# ✓ All parameter extractions work
# ✓ All end-to-end queries succeed
# ✓ All router selections correct
# ✓ All assessor validations correct
```

---

## Environment Setup

Make sure you have:
```bash
# 1. Activate venv
source .venv/bin/activate

# 2. Set API key (for tests that need it)
export ANTHROPIC_API_KEY="your-key-here"

# 3. Verify corpus exists
ls -lh docs/corpus.json
# Should show ~200KB file with 41 chunks
```

## Expected Performance

- **RAG Retrieval**: ~100-200ms per query
- **Parameter Extraction**: ~1-2s (Claude API call)
- **Router**: ~1-2s (Claude API call)
- **End-to-End Query**: ~3-5s total
- **Test Suite**: ~3s for all 39 tests
