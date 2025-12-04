# FDA Intelligence Agent System Narrative

This guide is written for readers without a software or AI background. It explains, in plain language, what happens to your question, why each stage exists, and how the system avoids making things up.

---

## The journey of a question (step by step)

1) **Your words become “state.”**  
   The agent wraps your question and any conversation history into a small package:  
   - The messages so far  
   - What we already know (resolved devices, manufacturers, locations)  
   - An optional session ID so we can pick up later  
   If a system reminder is missing, the agent adds one: resolve devices first, list all product codes, use correct dates, do not guess.

2) **The brain decides whether to fetch data (`agent` node).**  
   A large language model (LLM) sees the state and a menu of tools. It chooses:  
   - “I can answer now,” or  
   - “I need data, call these tools” (e.g., “find mask product codes,” “count registrations by country”).

3) **Tools go get the facts (`tools` node).**  
   The requested tools run against real sources (FDA APIs or the local GUDID database) and return results as tool messages. Resolver tools also stash structured context (devices, manufacturers, locations) so follow-up questions can reuse it without re-querying.

4) **Loop if needed, otherwise move on.**  
   If tools were called, the LLM looks at the new results and either asks for more tools or drafts an answer. If no tools are needed, the draft goes to the guardrail.

5) **Quality gate (`guard` node).**  
   A second, smaller LLM pass checks the draft answer against the tool outputs:  
   - If claims are unsupported, it rewrites to match the data or says “not available.”  
   - It never returns an empty reply. If the guard output is blank or obviously truncated, the original answer is kept.

6) **Packaging the reply.**  
   The final answer is returned along with token usage, cost (when available), and structured fields (resolved entities, recall results, tool executions).

**Shape of the flow:** `agent → tools → agent → guard → END`, with the agent/tools part looping only when the model explicitly asks for more tool data.

---

## Why these pieces exist (plain reasons)

- **Resolve first, then search.** Broad terms like “mask” map to many FDA product codes. Resolving first finds all relevant codes so searches are accurate and complete.
- **Keep and reuse context.** Once devices or manufacturers are resolved, they are saved so follow-up questions (“those manufacturers”) do not repeat the work.
- **Guardrail at the end.** One final pass keeps the answer grounded and non-empty. No multiple guard loops, so costs stay predictable.
- **Count instead of crawl.** For aggregations (e.g., masks by country), the system uses the FDA `count` endpoint (one aggregated call) rather than iterating over thousands of records.
- **Pick your provider.** OpenRouter is the default, but Bedrock or local Ollama work too. The guard can use a cheaper model to save money.

---

## What each tool does (in everyday terms)

Resolvers (translate your words into FDA identifiers and context):
- **`resolve_device`**: Looks up device terms/brands in GUDID; returns all product codes, device counts, and top manufacturers.
- **`resolve_manufacturer`**: Normalizes company names to FDA variants.
- **`resolve_location`**: Finds manufacturers by country/region/state and top device types there.

Searchers (pull evidence from FDA APIs):
- **`search_events`**: Adverse events (MAUDE), filterable by product code and country.  
- **`search_recalls`**: Recalls/enforcement actions, with product and country filters.  
- **`search_510k`**, **`search_pma`**, **`search_classifications`**, **`search_udi`**, **`search_registrations`**: Other FDA device datasets.

Aggregations:
- **`aggregate_registrations`**: Country counts for a device term, and (optionally) per product code; can include a short list of establishments. Uses `count` (no per-record loops).

---

## Prompts, models, and saving conversations

- **System prompt**: Date-aware, enforces resolve-before-search, insists on listing all codes, and bans empty/“null” searches.  
- **LLM Factory**: Provides defaults (OpenRouter `openai/gpt-4o`, Bedrock `claude-3-haiku`, Ollama `llama3.1`) and lets you override per call. The guard can run on a different/cheaper model.  
- **Persistence**: Optional checkpointing keeps conversation state by session ID for multi-turn work.

---

## Guardrail specifics

- Checks the draft answer against tool outputs and saved context.  
- If something is unsupported, it rewrites to match the data or states that the data is not available.  
- Never returns empty; if the guard output is blank or much shorter than the original, the original answer is kept.  
- Single pass (no loops) for predictable latency and cost.

---

## How to extend (non-engineer guidance)

- **Add a new data source**:  
  1) Define clear inputs (what the user can ask for).  
  2) Make one focused call (avoid looping over many pages).  
  3) Return concise facts or structured data.  
  Then register the tool in the tools init file and in the agent’s tool list.
- **Add new shared context**: If a tool produces structured results you want to reuse, add a `get_last_structured_result` so the agent can store it in `resolver_context`.
- **Adjust the guard**: Swap the guard model for cost/reliability, or tighten the guard prompt rules, without changing the graph shape.

---

## Operations

- **Keys**: FDA key reduces rate limits; OpenRouter/AI key is required for hosted LLMs; Bedrock needs AWS credentials; Ollama needs a local server.  
- **Costs**: Token and cost usage are reported when the provider supports it; the guard can run on a cheaper model.  
- **Failures**: Tool errors appear in tool messages; HTTP retries/backoff are handled in `OpenFDAClient`. The guard does not retry tools.  
- **Completeness & honesty**: The system prompt and guard require listing all product codes found and saying plainly when data is unavailable.

---

## Quick mental model

Think of the agent as a careful research assistant with two habits:  
1) It always looks up the exact FDA identifiers (product codes, firms, locations) before searching.  
2) It double-checks its final write-up against the data it just pulled and refuses to pad or guess.  

Everything else—tool menus, saved context, and a small audit pass—exists to make those two habits reliable.
