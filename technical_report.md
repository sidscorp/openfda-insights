# Technical Report: OpenFDA Agent Deployment

## Abstract
This report documents the evolution of the OpenFDA Agent from a prototype query helper into a multi-modal analysis platform capable of planning, executing, and explaining complex FDA device database investigations. The release combines deterministic parameter extraction, graph-based execution planning (via LangGraph, a library for building state-machine controllers), retrieval-augmented reasoning, and comprehensive safety workups across the openFDA device endpoints. We review the motivating requirements, architectural decisions, implementation details, and validation strategy that collectively deliver higher accuracy, traceability, and analyst usability.

## 1. Agentic System Overview
We model the OpenFDA deployment as an autonomous agent situated inside a probabilistic environment formed by the FDA’s device data services. Each endpoint—classification, 510(k), PMA, enforcement, MAUDE, UDI, and registration—exposes observable state through JSON payloads yet constrains interaction via rate limits, missing fields, and varying query semantics. Supporting documentation corpora (scraped field guides, routing hints) further enrich the environment with latent knowledge.

Within this setting the agent maintains distinct subsystems:
- **Perception**: natural-language requests are transformed into internal state through query analysis, structured parameter extraction, and optional RAG (retrieval-augmented generation) hints drawn from scraped documentation.
- **Policy**: a LangGraph controller (LangGraph is an orchestration library that wires language-model decisions into explicit state machines) plans action sequences, choosing tools, adjusting strategy on retry, and managing safety workflows.
- **Actuation**: `tools/*.py` wrappers issue HTTP actions, encapsulating retry policies, pagination logic, and field validation.
- **Memory**: the `AgentState` store captures tool history, extracted parameters, episodic safety aggregates, and provenance metadata that influence subsequent decisions.

By continuously sensing, deciding, acting, and updating, the agent exhibits autonomy rather than serving as a static workflow. The present work concentrates on hardening each subsystem to deliver reliable, explainable behavior.

## 2. Motivations and Requirements
Regulatory analysts must synthesize evidence from multiple endpoints to answer safety, market, and compliance questions. Manual pivoting across datasets is error-prone and incompatible with presidential-level briefings that demand full traceability. From internal CEO resolutions and PRD targets, we distilled the following phase objectives:
- **Deterministic routing and planning**: replace heuristic substring checks with LLM-assisted query classification plus execution plans.
- **Validated structured extraction**: normalize device classes, product codes, dates, and identifiers with auditable validators.
- **Cross-endpoint safety analysis**: coordinate recalls, MAUDE, and classification data when risk investigations are requested.
- **Documented provenance**: record Lucene queries, timestamps, and tool calls for FDA audit trails.
- **RAG-assisted disambiguation**: consult official documentation (retrieval-augmented generation) when field mappings are uncertain.
- **Operational tooling**: expose CLI, FastAPI dashboard, and tests for analyst workflows and regression control.

## 3. Environment Modeling
### 3.1 Observable State and Dynamics
The agent experiences the openFDA ecosystem as a partially observable environment. Each endpoint returns JSON payloads composed of two high-value channels: `results`, containing domain records, and `meta`, containing dataset-level signals such as `last_updated`, pagination offsets, and numerical aggregates. Errors (HTTP 4xx/5xx bodies, rate-limit headers) and empty result sets also form part of the observable state, informing subsequent decisions. Documentation corpora—`docs/corpus.json` plus routing hints—augment the environment with latent structural knowledge (field definitions, query syntax) that is retrieved on demand. Temporal drift (new recalls, updated MAUDE reports) renders the environment non-stationary, validating the need for continual observation and provenance tracking.

### 3.2 Action Space and Tool Contracts
Agent actions are expressed as calls to typed tool wrappers that encapsulate HTTP interactions with the environment. Each tool declares a schema of permissible parameters and applies environment-specific transformations before dispatching requests via the shared `OpenFDAClient`:

| Tool | Endpoint / Resource | Key Parameters | Returned Signals |
|------|--------------------|----------------|------------------|
| `classify` | `device/classification` | `product_code`, `device_class`, `device_name`, `regulation_number` | Classification metadata (device class, regulation, definitions) and `meta.last_updated` |
| `k510_search` | `device/510k` | `k_number`, `applicant`, `product_code`, decision-date range | Premarket notification clearances with pagination metadata |
| `pma_search` | `device/pma` | `pma_number`, `applicant`, `product_code`, decision-date range | PMA submissions and supplements; exposes approval chronology |
| `recall_search` | `device/enforcement` | `recall_number`, `classification`, `product_description`, `firm_name`, event-date range | Enforcement actions including reasons, firm names, and classification |
| `maude_search` | `device/event` | `device_name`, `product_code`, `event_type`, date range | Adverse event narratives and patient impact descriptors |
| `udi_search` | `device/udi` | `brand_name`, `company_name`, `product_codes.code` | GUDID device identifier records with packaging metadata |
| `rl_search` | `device/registrationlisting` | `firm_name`, `fei_number`, geography filters | Establishment registrations and associated product codes |
| `probe_count` | Any endpoint | `field`, optional `search` filter | Aggregated term counts for disambiguation |

Each tool enforces parameter validation, injects the FDA API key when present, and normalizes responses into `OpenFDAResponse`, exposing a uniform surface for downstream reasoning. Failures propagate as explicit error payloads, supplying the assessor with context for recovery actions.

### 3.3 Environment Feedback and Constraints
The environment imposes several constraints that the agent must accommodate: rate limiting (429 responses), sparsity of certain fields (e.g., recalls lacking product codes), and variability in available date ranges. `meta.results.total` and partial result lengths guide pagination, while absence of records triggers alternative exploration strategies. Provenance is anchored by the `meta.last_updated` and the generated Lucene query, enabling analysts to reconcile responses against the underlying environment state during audits.

## 4. Control Architecture and Orchestration
The policy layer is implemented with LangGraph—an orchestration framework that lets developers define state-machine controllers around language models (LLMs). LangGraph composes deterministic nodes into a directed graph. Four core nodes—`router`, `execute_tools`, `assessor`, and `answer`—coordinate the perception-action loop with a bounded retry budget of one (agent/graph.py:70). `AgentState` (agent/state.py:24) stores the evolving belief state: query analysis, selected strategy, tool call ledger, generated Lucene queries, and safety aggregates.

### 4.1 Perception-to-Plan Workflow
Upon receiving a question, the router first performs LLM-backed query analysis to identify intent, primary entities, temporal scope, and cross-reference requirements. Planning prompts then synthesize an explicit execution plan, choose an endpoint, and label the search strategy (`exact`, `category`, or `broad`). RAG hints (retrieved documentation excerpts) and prior assessor feedback are incorporated to refine subsequent attempts, while safety-triggered queries set flags that activate multi-endpoint routines.

### 4.2 Action Execution and Memory Updates
The `execute_tools` node consults the chosen strategy and invokes the corresponding tool with parameters emitted by the structured extractor. Confidence scores inform whether to augment perception with RAG field hints before re-extracting. Specialized flows—such as the safety dossier, recall/product-code crosswalk, and aggregation joins—compose multiple tool calls into higher-level actions. Results (or errors) are normalized, persisted inside `AgentState`, and fed into the assessor for evaluation.

### 4.3 Assessment and Policy Adjustment
The assessor inspects tool outcomes to decide on sufficiency. Safety workflows short-circuit to success once classification data is obtained, while cross-reference flows are deemed sufficient when synthesized tables are populated. Otherwise the assessor leverages the deterministic `answer_assessor` to ensure required filters (dates, classes) were applied. Failure reasons (e.g., rate limits, syntax errors, zero results) are stored and used by the router to adjust future prompts—removing over-specific filters, shrinking limits, or broadening dates. Sufficient states transition to the `answer` node, which formats the final response and records provenance before terminating the episode.

## 5. LLM-Orchestrated Query Planning
### 5.1 Query Type Analysis
Every user query is first categorized through a structured Claude prompt that elicits query type, primary entity, temporal bounds, and the need for cross-referencing (agent/graph.py:120). JSON decoding failures fall back to conservative defaults, ensuring resilience even under LLM disruptions (agent/graph.py:180).

### 5.2 Execution Planning
A second planning prompt synthesizes the routing decision, assigns a search strategy (`exact`, `category`, `broad`), and outlines an execution plan (agent/graph.py:232). The router stores the resulting plan and aligns endpoint selection via a deterministic mapping, with a fallback to the legacy tool-calling router when parsing fails (agent/graph.py:276). Retry attempts rewrite the question to relax overly specific filters or reduce limits based on assessors’ feedback, closing the loop between analysis and execution (agent/graph.py:258).

### 5.3 Count Detection
Aggregation intents automatically trigger the `probe_count` tool, allowing the agent to satisfy “how many” questions through count aggregations instead of row-level fetches (agent/graph.py:336).

## 6. Parameter Extraction and Validation
A dedicated `ParameterExtractor` now leverages Claude’s structured outputs (agent/extractor.py:364). Regex-based pre-extraction captures deterministic patterns (K-numbers, product codes) and assigns them high confidence scores before LLM invocation (agent/extractor.py:378). Pydantic validators normalize device classes, enforce three-letter product codes, and verify date formats (agent/extractor.py:25; agent/extractor.py:36; agent/extractor.py:49). Recall classes are uplifted to the “Class N” schema via post-processing (agent/extractor.py:349). Confidence heuristics expose low-certainty fields, enabling downstream RAG assistance (documentation lookups) when scores fall below 0.8 (agent/extractor.py:404). The extractor also emits human-readable filter strings for the assessor, creating a clear provenance trail (agent/extractor.py:150).

## 7. Cross-Endpoint Safety Reasoning
### 7.1 Comprehensive Safety Checks
When the query classifier identifies a safety intent tied to a specific product code, the agent executes a three-pronged safety review across recalls, MAUDE, and classification metadata, with optional related-device fallback if direct hits are absent (agent/graph.py:620). Results are collated into a structured safety dossier summarizing findings, risks, and recommended follow-up actions (agent/graph.py:1175).

### 7.2 Recall/Product-Code Crosswalks
Because enforcement records lack product codes, specialized handlers enrich recall data by first validating the code via classification, then using device descriptions to search the recall endpoint, handling temporal constraints and future-date requests gracefully (agent/graph.py:694). For aggregate requests—e.g., “which product codes have recalls this year?”—the agent mines recall descriptions, derives candidate device types, and resolves them back to product codes via classification lookups (agent/graph.py:803).

## 8. Retrieval-Augmented Guidance
Hybrid retrieval fuses BM25 and semantic similarity with endpoint-aware filtering to surface relevant documentation chunks for routing and extraction hints (rag/hybrid.py:17). Reciprocal rank fusion over BM25 and embedding scores keeps recall high while suppressing noise (rag/hybrid.py:155). Endpoint hints derived from alias dictionaries allow the retriever to concentrate on the most probable documentation slices (rag/hybrid.py:54). These hints are passed into the router whenever low-confidence extractions are detected, giving the LLM grounding material to resolve ambiguous fields (agent/graph.py:193).

## 9. Assessment, Error Recovery, and Provenance
The assessor short-circuits when safety reports succeed, ensuring complete multi-endpoint analyses register as sufficient (agent/graph.py:927). Otherwise it pipes validated filters into the legacy `answer_assessor`, capturing insufficiency reasons such as missing class filters or zero results without constraints (agent/graph.py:417). Error handling differentiates 404s, 429s, 400s, 500s, and timeouts, providing actionable retry instructions that propagate back into the router’s rewritten prompts (agent/graph.py:365). Successful runs record endpoint, Lucene query, record counts, and ISO 8601 timestamps to satisfy ALCOA+ auditability (agent/graph.py:466).

## 10. User Interfaces and Operations
The CLI adds `--dry-run` and `--explain` modes for reproducing routing and assessment decisions without hitting openFDA (agent/cli.py:45). A FastAPI dashboard maintains session state, query history, and streaming logs, allowing analysts to observe intermediate reasoning via WebSocket updates (dashboard/app.py:171). Operational scripts manage lifecycle (dashboard_control.py:12) and handle port conflicts or missing environment configuration gracefully, supporting deployment in analyst workstations.

## 11. Evaluation and Testing
### 11.1 Automated Checks
- **Unit & VCR tests** verify tool primitives under recorded HTTP interactions (tests/test_tools.py).
- **Integration tests** exercise routing accuracy, extraction completeness, and assessor guardrails using live LLM calls gated by environment flags (tests/integration/test_e2e.py:12).
- **Regression script** `test_improvements.py` demonstrates structured extraction, Lucene generation, and provenance stamping end-to-end for canonical prompts.

### 11.2 Observed Metrics
Local runs with live Anthropic access confirm low-confidence signaling for ambiguous fields and successful normalization of device classes and dates. Aggregation handlers now return structured product-code/recall join tables under recorded scenarios. Safety dossiers enumerate recall/adverse-event counts and related-device fallbacks, offering immediate situational awareness for analysts.

## 12. Limitations
- Confidence scoring remains heuristic; no second-pass calibration model backs the reported percentages (agent/extractor.py:404).
- Hybrid RAG (documentation retrieval) relies on pre-scraped content; coverage gaps or stale data may leave certain fields unresolved.
- Safety cross-references assume the classification endpoint returns the desired device information; missing device names limit recall enrichment (agent/graph.py:712).
- Integration tests require Anthropic credentials and will incur API costs, limiting CI suitability.

## 13. Future Work
Potential next steps include persistent audit logging (ALCOA+ storage), CFR Part 11 authentication, caching for high-latency endpoints, and deterministic mocks for LLM-dependent tests. Extending the hybrid retriever with vector databases and incorporating structured output for tool parameters would further reduce failure modes.

## 14. Conclusion
This release delivers a materially stronger FDA analysis agent by pairing structured LLM planning with validated parameterization, cross-endpoint safety synthesis, and explainable provenance. The system now provides actionable dashboards and CLIs for analysts while maintaining a clear pathway to regulatory-grade compliance as it matures.
