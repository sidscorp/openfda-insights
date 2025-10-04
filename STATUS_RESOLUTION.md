Got it—no pep talk, just the shortest path from “nice prototype” to “reliable agent.” Here’s the cut-through plan with drop-in patches you can paste into your repo today.

# 0) The goalpost

Make routing correct, retrieval precise, and answers validated. Concretely:

* Routing: structured tool calls, not string hacks.
* Retrieval: hybrid + endpoint prefilter; enrich corpus.
* Validation: an assessor that can say “nope—retry.”

---

# 1) Replace the router’s string-matching with real tool calling

**agent/router.py**

```python
# drop-in: use Anthropic or OpenAI tool-calling via LangChain
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool

# 1) declare tool "selectors" (not the HTTP tools themselves)
@tool
def select_classification(query: str) -> str: """Use for device class queries."""; return ""
@tool
def select_510k(query: str) -> str: """Use for 510(k) clearances."""; return ""
@tool
def select_pma(query: str) -> str: """Use for PMAs."""; return ""
@tool
def select_recall(query: str) -> str: """Use for enforcement/recalls."""; return ""
@tool
def select_maude(query: str) -> str: """Use for adverse events (MAUDE).""" ; return ""
@tool
def select_udi(query: str) -> str: """Use for UDI/device identifiers.""" ; return ""
@tool
def select_rl(query: str) -> str: """Use for registration & listing establishments.""" ; return ""

SELECTORS = [select_classification, select_510k, select_pma, select_recall, select_maude, select_udi, select_rl]

llm = ChatAnthropic(model="claude-3-5-sonnet-20240620").bind_tools(SELECTORS)

SYSTEM = """You are the Router. Choose exactly ONE tool that best answers the user question.
If ambiguous, pick the MOST LIKELY and include a brief rationale in the tool call arguments.
Do not invent tools. Use the semantics of endpoints, not keywords alone."""

def route(question: str, rag_hints: str | None = None) -> str:
    messages = [{"role":"system","content":SYSTEM}]
    if rag_hints:
        messages.append({"role":"user","content": f"Routing hints:\n{rag_hints}"})
    messages.append({"role":"user","content": question})
    resp = llm.invoke(messages)
    if not getattr(resp, "tool_calls", None):
        # safe fallback: ask for disambiguation
        return "disambiguate"
    name = resp.tool_calls[0]["name"]
    return {
        "select_classification":"classification",
        "select_510k":"510k",
        "select_pma":"pma",
        "select_recall":"recall",
        "select_maude":"maude",
        "select_udi":"udi",
        "select_rl":"rl_search",
    }[name]
```

**agent/graph.py** – swap your `Router` node to call `route()` and branch.

---

# 2) Make RAG precise: endpoint prefilter + hybrid (BM25 + embeddings)

## 2a) Expand metadata and add endpoint prefilter

Ensure each chunk carries `metadata={"endpoint": "...", "kind":"fields|howto|examples"}`.

In your retriever, gate by endpoint *when the query strongly implies it*.

**rag/retrieval.py**

```python
import re
from typing import List, Dict
from collections import defaultdict

ENDPOINT_ALIASES = {
  "510k": ["510k","k-number","k number","kxxxxx","k-"],
  "pma": ["pma","p-number","p number","p-"],
  "classification": ["class i","class ii","class iii","classification","regulation number"],
  "recall": ["recall","enforcement","class i recall","recall class"],
  "maude": ["maude","adverse event","event report","foi"],
  "udi": ["udi","gudid","device identifier","di","pi"],
  "rl_search": ["registration","listing","establishment","owner/operator","fei","duns"]
}

def infer_endpoint_hint(q: str) -> List[str]:
    s = q.lower()
    hits = []
    for ep, kws in ENDPOINT_ALIASES.items():
        if any(k in s for k in kws):
            hits.append(ep)
    return hits

class HybridRetriever:
    def __init__(self, bm25_index, emb_index):
        self.bm25 = bm25_index        # any simple BM25 impl (e.g., rank_bm25)
        self.emb = emb_index          # faiss or sentence-transformers + faiss
        self.docs = emb_index.docs    # list of {text, metadata}

    def search(self, query: str, top_k=6) -> List[Dict]:
        hints = set(infer_endpoint_hint(query))
        # 1) candidate pool: metadata prefilter if hints present
        candidates = range(len(self.docs))
        if hints:
            candidates = [i for i, d in enumerate(self.docs)
                          if d["metadata"].get("endpoint") in hints]
            if not candidates:  # fallback if overly strict
                candidates = range(len(self.docs))
        # 2) get BM25 and embedding scores over candidate ids
        bm25_hits = self.bm25.search(query, candidates, top_k=50)  # returns [(id, score)]
        emb_hits  = self.emb.search(query, candidates, top_k=50)   # returns [(id, score)]
        # 3) reciprocal rank fusion (RRF) for stability
        ranks = defaultdict(float)
        for rank,(i,_) in enumerate(bm25_hits): ranks[i] += 1.0/(60+rank)
        for rank,(i,_) in enumerate(emb_hits):  ranks[i] += 1.0/(60+rank)
        fused = sorted(ranks.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [{"text": self.docs[i]["text"], "metadata": self.docs[i]["metadata"]} for i,_ in fused]
```

Wire this `HybridRetriever.search()` into the router (as `rag_hints`) and into an optional “help the extractor” step when it struggles with field names.

## 2b) Add keyword boosting for endpoint names inside chunks

When you build your embeddings text, **repeat** the endpoint name and canonical field names at the head of each chunk:

**rag/scraper.py (when constructing chunk text)**

```python
def synth_header(endpoint: str, field_names: list[str]):
    head = f"[ENDPOINT]: {endpoint}\n[FIELDS]: " + ", ".join(sorted(set(field_names))) + "\n"
    return head

chunk_text = synth_header(endpoint, fields) + markdown_section_text
```

Cheap, but moves your “510k” and “enforcement” surface forms from 0-1 occurrences to 2-3+.

---

# 3) Wire RAG into the Router prompt (so routing stops guessing)

**agent/graph.py (Router node call)**

```python
hints_docs = retriever.search(state.question, top_k=2)
hints = "\n\n".join([d["text"][:800] for d in hints_docs])
selected = route(state.question, rag_hints=hints)
state.selected_tool = selected
```

---

# 4) Make the assessor actually assess

**tools/answer_assessor.py** (use your existing utility but wire these rules)

```python
from dataclasses import dataclass

@dataclass
class AssessmentInputs:
    question: str
    params_str: str
    result_count: int
    required_filters: dict   # e.g. {"recall_class": ["i","ii","iii"], "device_class":[1,2,3]}

def assess(x: AssessmentInputs) -> dict:
    q = x.question.lower()
    want_count = any(k in q for k in ["how many","count"])
    has_zero = x.result_count == 0
    # 1) if user demanded a class and params missed it → insufficient
    for key, tokens in x.required_filters.items():
        if any(tok in q for tok in tokens):
            if key not in x.params_str.lower():
                return {"sufficient": False, "reason": f"Missing filter '{key}' implied by question"}
    # 2) zero results with no explicit allowance → insufficient (ask to relax filters)
    if has_zero and not any(k in q for k in ["zero","none ok","if any"]):
        return {"sufficient": False, "reason": "Zero results; try relaxing filters or confirming intent"}
    # 3) if user asked for count but we returned full records → still okay, but suggest count
    return {"sufficient": True, "reason": "Looks good"}
```

**agent/graph.py (after tool call)**

```python
params_str = extracted_params_to_query_string(extracted)
need_tokens = {"recall_class":["class i","class ii","class iii"],
               "device_class":["class i","class ii","class iii","class 1","class 2","class 3"]}
decision = assess(AssessmentInputs(state.question, params_str, len(results), need_tokens))
state.is_sufficient = decision["sufficient"]
state.assessor_reason = decision["reason"]
if not state.is_sufficient and state.retries < 2:
    # simple policy: re-run extractor with a stronger “hint” prompt or ask a disambiguation follow-up
    state.retries += 1
    state.next = "Extractor"
```

---

# 5) Corpus quick win: add real “How to use” + examples (no bikeshedding)

Extend your scraper to grab:

* Endpoint overview pages
* Field reference pages
* Example query pages (any “search examples”, “FAQ”, “Tutorials”)
* Your **own** mini-howtos per endpoint: 150–250 words with 3 canonical queries

**docs/synthetic_howtos/*.md** – create one per endpoint; include:

* What this endpoint is for
* 3 example queries (plain English + openFDA filter string)
* List of 6–12 canonical field names (firm name, k_number, product_code, etc.)

Index those alongside scraped docs. This alone often pushes precision over 0.9 because you’ve added discriminative language.

---

# 6) Minimal end-to-end integration tests (pytest)

**tests/integration/test_e2e.py**

```python
import pytest
from agent.cli import ask

@pytest.mark.parametrize("q,expect_tool", [
    ("List Class II devices", "classification"),
    ("510k clearances from Medtronic since 2023", "510k"),
    ("Show PMA approvals in 2024", "pma"),
    ("Any Class I recalls for syringes", "recall"),
    ("Adverse events for pacemakers", "maude"),
    ("Find this device UDI 00819320201234", "udi"),
    ("Show establishments in Minnesota", "rl_search"),
])
def test_routing(q, expect_tool):
    ans = ask(q, dry_run=True)  # make ask() return routing + params without hitting HTTP if dry_run
    assert ans["selected_tool"] == expect_tool

def test_sufficiency_missing_class_triggers_retry():
    ans = ask("Show recalls in 2024", simulate_missing_param="recall_class")
    assert ans["meta"]["retries"] >= 1
    assert ans["meta"]["assessor_reason"].lower().startswith("missing filter")
```

Add a `dry_run` mode to skip live API but still exercise router + extractor + assessor.

---

# 7) Field-name sanity: RAG-assisted extraction when the extractor hesitates

If the extractor doesn’t resolve a firm/manufacturer field correctly, ask RAG for the **canonical field names** for the selected endpoint and provide them as a *constrained options list*.

**agent/extractor.py (before final parse)**

```python
if not extracted.get("field_name") and state.selected_tool in {"510k","pma","recall","maude","rl_search"}:
    docs = retriever.search(f"Which fields are searchable in {state.selected_tool}?", top_k=1)
    # parse out a candidate list from the [FIELDS] header you injected
    fields = []
    for d in docs:
        lines = d["text"].splitlines()
        for ln in lines[:3]:
            if ln.startswith("[FIELDS]:"):
                fields = [f.strip() for f in ln.split(":",1)[1].split(",")]
    prompt = f"Pick the best field from this list for '{state.question}'. Options: {fields}"
    # one-call constrained classification with your LLM
    extracted["field_name"] = classify_field(prompt, fields)
```

---

# 8) CLI friction fixes (fast)

* Add `--explain` to show router choice, RAG hits, and assessor verdict.
* Add `--dry-run` for integration tests.
* Add 10 example queries to `--help`.

**agent/cli.py (sketch)**

```python
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--explain", action="store_true")
# ...
res = run_agent(q, dry_run=args.dry_run)
if args.explain:
    print("\n[ROUTER]", res["selected_tool"])
    print("[RAG]", *[r["metadata"].get("endpoint") for r in res.get("rag_docs",[])])
    print("[ASSESSOR]", res["meta"]["assessor_reason"])
```

---

# 9) Guardrails that pay off fast

* Casing normalizer for “Class I/II/III” and “Class 1/2/3”.
* Product-code regex: `r'\b[A-Z0-9]{3}\b'` but **only** if preceded by “product code”.
* K-Number regex: `r'\bK\d{6}\b'`.
* P-Number regex: `r'\bP\d{6}\b'`.

Add them to `agent/prompt.py` and the extractor to reduce LLM wiggle.

---

# 10) One command to prove progress

Add a smoke target that runs routing + assessor + hybrid RAG without hitting APIs:

**Makefile**

```
smoke:
\tpytest -q tests/integration/test_e2e.py -k routing
```

---

## Where this gets you

* Router becomes deterministic and inspectable.
* RAG stops being a semantic shrug; endpoint hints + hybrid + synthetic howtos make it sharp.
* Assessor can block garbage and trigger a retry with a reason.
* You get a runnable integration suite that fails loudly when routing or sufficiency regresses.