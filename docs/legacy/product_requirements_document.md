# FDA Device Analyst Agent — High-Level PRD (staged build)

**Goal**
Ship a reliable, auditable chatbot that answers FDA device questions by (1) calling the correct openFDA device endpoint(s), (2) verifying that results satisfy the question, and (3) optionally enriching explanations with vetted documentation via RAG. Final step adds agentic orchestration (router → tools → sufficiency check → answer) with guardrails.

---

## Phase 0 — Scope & Data

**Data surface (openFDA /device)**

* Registration & Listing — establishments + listed products. ([OpenFDA][1])
* Classification — product code ↔ class, regulation, panel. ([OpenFDA][2])
* 510(k) — clearances. ([OpenFDA][3])
* PMA — approvals/supplements. ([OpenFDA][4])
* Enforcement — device recalls. ([OpenFDA][5])
* Event — MAUDE adverse events. (listed under Device on openFDA) ([OpenFDA][5])
* UDI/GUDID — identifiers/labels. ([OpenFDA][5])

**API model**
Elasticsearch-style query params (`search`, `count`, `limit`, `skip`); each endpoint is queried separately. ([OpenFDA][6])

---

## Phase 1 — Tools (build and test individually)

**Principle**
Small, single-purpose tools with strict, typed args and documented returns; consistent `search`, `count`, pagination; no raw-URL construction by the model. (This aligns with agent best practices: simple, composable patterns; clear constraints.) ([Anthropic][7])

**Core endpoint tools (one per endpoint)**

* `rl_search(params)` → Registration & Listing. ([OpenFDA][1])
* `classify(product_code|reg_number)` → Classification. ([OpenFDA][2])
* `k510_search(params)` → 510(k). ([OpenFDA][3])
* `pma_search(params)` → PMA. ([OpenFDA][4])
* `recall_search(params)` → Enforcement. ([OpenFDA][5])
* `maude_search(params)` → Event. ([OpenFDA][5])
* `udi_search(params)` → UDI/GUDID. ([OpenFDA][5])

**Agent utilities**

* `probe_count(endpoint, filter)` → fast disambiguation via `count=`. ([OpenFDA][6])
* `paginate(endpoint, filter, limit=1000)` → safe paging wrapper (enforces caps). ([OpenFDA][6])
* `field_explorer(endpoint)` → returns searchable fields (from docs) to prevent guessing. ([OpenFDA][8])
* `freshness(endpoint)` → last-updated metadata (provenance). ([OpenFDA][5])
* `answer_assessor(question, results)` → deterministic checks (e.g., date/class filters present, non-empty, matches intent).

**Deliverables (Phase 1)**

* Pydantic (or dataclass) signatures for each tool; inline usage docs; unit tests with recorded responses.
* A thin CLI to smoke-test each tool (query, count, paginate).
* Success: >95% tool tests passing; latency envelopes documented; reproducible cassettes (e.g., VCR).

---

## Phase 2 — RAG (documentation & synonyms; *not* a data substitute)

**Purpose**
Ground explanations, resolve fuzzy user language (aliases, CFR vs product code), and cite official definitions; never replace live facts from the API. This mirrors guidance to keep agents simple and use docs to steer context. ([Anthropic][7])

**Corpus (seed)**

* openFDA device docs per endpoint (overview, how-to, field lists, examples). ([OpenFDA][5])
* Internal glossary: brand/firm aliases, common misspellings, product-code ↔ generic-name pairs.
* Routing cheatsheet (human-authored): “If product code → classification; if recalls → enforcement,” etc.

**Retrieval design**

* Shallow vector index (chunked pages + titles); metadata by endpoint; exact-match boost for product codes/CFR.
* Output: short, quoted snippets with links back to the doc page.

**Tests**

* Query-to-doc precision (top-k has the correct page/section) ≥ 0.9 on a labeled set.
* No hallucinated fields (spot check); explanations include a doc citation.

---

## Phase 3 — Agentic orchestration (router → tools → assessor)

**Framework choice**
Use **LangGraph** for the agent loop and stateful orchestration; LangChain remains the component library for models, tools, and retrieval.

* LangChain’s own docs recommend building *new agents* with **LangGraph** (stateful graphs, better control/guardrails). ([LangChain][9])
* LangGraph provides agent→tool→agent loops, retries, and concurrency control suited to multi-step, tool-driven tasks. ([LangChain][10])
* OpenAI’s and Anthropic’s agent guides emphasize simple, composable steps with clear stop conditions and guardrails—well matched to LangGraph graphs. ([OpenAI][11])

**Minimal graph**

* **Nodes**: `Router` (LLM), `Tools` (the 7 endpoint tools + utilities), `Assessor` (deterministic), `Answer`.
* **Edges**: `Router → Tool` (selected), `Tool → Assessor`, `Assessor → Router` (if insufficient) or `Assessor → Answer`.

**Routing policy (sketch)**

* Detect subject tokens: 3-letter **product code**, **CFR regulation**, **firm/establishment**, **510(k)/PMA IDs**, **UDI/DI**, **geo**, **timeframe**.
* Map intent → tool:

  * Product code/reg → `classify` ± `rl_search` / `recall_search` / `maude_search`.
  * “510(k)/Kxxxxx” → `k510_search`. “PMA/Pxxxxxx/Sxxxx” → `pma_search`.
  * “recall/Class I–III” → `recall_search`. “MAUDE/adverse events” → `maude_search`.
  * “establishment/FEI/state/city” → `rl_search`. “UDI/label/brand” → `udi_search`. ([OpenFDA][5])

**Verification loop**

1. `probe_count` to disambiguate ambiguous entities.
2. Run primary tool with minimal filters.
3. `answer_assessor` confirms the question was actually satisfied (e.g., date window honored for “since 2023”, class filter present).
4. If insufficient: widen time within bounds, or call the next logical tool (e.g., classification → enforcement for same code), then reassess.
5. Stop after ≤2 autonomous retries; else ask one precise clarifying question.

**System prompt (orchestrator)**

* Role: FDA Device Analyst Assistant, **use only tools** and documented fields.
* Rules: resolve subject first; ask **one** crisp follow-up only when needed; choose minimal endpoint(s); always verify with `answer_assessor`; include **provenance** (endpoint, filters, last_updated) in the final answer; never fabricate unsupported fields; stop once satisfied.
* Hints: routing table (as above), common field names per endpoint, pagination rules.
* Guardrails: allowed endpoints only; enforce date bounds and page limits; no PII.

**Outputs**

* Direct answer (one paragraph); compact table (top N rows); provenance block (endpoint, filters, last_updated link).
* For vague asks, a short disambiguation list ranked by `count`.

**Success criteria (Phase 3)**

* Routing accuracy on a labeled question set ≥ 0.9.
* “Sufficiency passes” (answers meet spec without follow-up) ≥ 0.85.
* Median end-to-end latency ≤ target (documented per endpoint).
* Reproducibility: same inputs → same tool calls/filters (logged).

---

## Non-functional requirements

* **Observability**: trace tool calls, inputs/outputs, and decision edges (use LangSmith or equivalent).
* **Testing**: unit tests per tool; integration tests per intent (router → tool → assessor); regression suite with recorded API responses.
* **Safety/Compliance**: read-only; respect openFDA rate limits; provenance always shown.
* **Performance**: pagination cap and backoff; caching of frequent classifications.
* **Versioning**: pin tool versions and doc snapshots; record model versions used.

---

## Milestones & Deliverables

**M1 — Tooling complete (2–3 weeks)**

* All 7 endpoint tools + utilities implemented, documented, and tested; CLI smoke tests; cassette fixtures.
* Deliver: tool docs + test report.

**M2 — RAG-lite (1–2 weeks)**

* Doc corpus indexed; retrieval API; explanation templates; precision eval.
* Deliver: retrieval service + eval metrics + example cited answers.

**M3 — Agent graph (2–3 weeks)**

* LangGraph router/assessor wired; system prompt finalized; labeled eval set; telemetry on.
* Deliver: working chatbot with provenance, routing accuracy report, latency profile.

---

## References (best practices & docs)

* **openFDA devices**: endpoints & “how-to” pages (Registration/Listing, Classification, 510(k), PMA, Enforcement, Device overview). ([OpenFDA][1])
* **API model**: openFDA API overview & query semantics. ([OpenFDA][6])
* **Agent design**: OpenAI *A Practical Guide to Building Agents*; Anthropic *Building Effective Agents*. ([OpenAI][11])
* **Orchestration**: LangGraph overview & agent reference; LangChain guidance to build new agents with LangGraph. ([LangChain][10])

---

### Notes for engineers

* Keep tools boring and typed; the agent gets smarter when its “hands” are simple.
* Use `count` as a fast probe before fetching big pages.
* Always attach provenance (endpoint, filters, last_updated) to answers—analysts trust what they can verify.
* Start with a single therapeutic area to keep eval labeling tractable; expand once routing accuracy stabilizes.


[1]: https://open.fda.gov/apis/device/registrationlisting/?utm_source=chatgpt.com "Device Registrations & Listings Overview"
[2]: https://open.fda.gov/apis/device/classification/?utm_source=chatgpt.com "Device Classification Overview"
[3]: https://open.fda.gov/apis/device/510k/?utm_source=chatgpt.com "Device 510(k) Overview"
[4]: https://open.fda.gov/apis/device/pma/?utm_source=chatgpt.com "Device Pre-market Approval Overview"
[5]: https://open.fda.gov/apis/device/?utm_source=chatgpt.com "Medical Device API Endpoints"
[6]: https://open.fda.gov/apis/?utm_source=chatgpt.com "About the openFDA API"
[7]: https://www.anthropic.com/research/building-effective-agents?utm_source=chatgpt.com "Building Effective AI Agents"
[8]: https://open.fda.gov/apis/device/registrationlisting/how-to-use-the-endpoint/?utm_source=chatgpt.com "How to use the API"
[9]: https://python.langchain.com/api_reference/core/agents.html?utm_source=chatgpt.com "agents — 🦜🔗 LangChain documentation"
[10]: https://www.langchain.com/langgraph?utm_source=chatgpt.com "LangGraph"
[11]: https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf?utm_source=chatgpt.com "A practical guide to building agents"
