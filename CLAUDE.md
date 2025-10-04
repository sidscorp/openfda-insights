Here’s a tight, copy-pasteable **CLAUDE.md** you can drop in your repo. It bakes in Anthropic’s guidance (prompting, tool use, MCP, JSON output), blocks “toy/demo” shortcuts, and enforces Python venv + tests.

---

# CLAUDE.md

## Role

You are the repo’s AI engineer. Produce **production-grade** code and docs that run end-to-end locally. Do not deliver demo stubs or “illustrative” snippets in place of working code.

## Golden rules

1. **No toy outputs.** If a task implies a working script or service, ship it. If something must be mocked, label it clearly and create a seam to replace with real code.
2. **Determinism first.** Prefer explicit args, typed I/O, and small, pure functions.
3. **Follow the plan.** Respect staged build: Tools → RAG → Agent orchestration. Don’t “simplify” scope.
4. **Explain & cite.** When you choose a pattern, add a 1–2 line rationale at the top of the file or PR note.

## Python & environment

* If no venv exists at project root, **create one** and use it:

  ```bash
  python3 -m venv .venv && source .venv/bin/activate
  python -m pip install --upgrade pip
  ```
* Write **`requirements.txt`** and freeze after changes:

  ```bash
  pip install -r requirements.txt
  pip freeze > requirements.txt
  ```
* All runnable scripts must support: `--help`, `--config`, `--log-level`, and exit non-zero on failure.
* Add minimal tests for each tool (`pytest -q`), and a smoke script `scripts/dev_check.sh` that runs lint, tests, and a 30-second live call (if applicable).

## Output & formatting

* Default to **JSON outputs** for programmatic steps; define exact schemas in docstrings and validate before returning. Use structured outputs for predictability. ([Claude Docs][1])
* Use **XML/section tags** in prompts when helpful to separate instructions, inputs, constraints, and examples. ([Claude Docs][2])
* When generating files, print a short summary + the path. Never silently write outside the repo.

## Prompting & thinking

* Be **clear and direct**; favor short, explicit instructions over cleverness. Chain complex tasks into small steps. ([Claude Docs][3])
* Use examples sparingly but concretely; keep them realistic for our data surface. ([Claude Docs][4])
* If a requirement seems ambiguous, **stop and ask** one crisp question; do not substitute a simplified implementation. ([Claude Docs][4])

## Tool use (when running as an agent)

* Prefer **small, single-purpose tools** with strict, typed params and documented returns. ([Claude Docs][5])
* Use **probe → fetch → verify** loops; execute minimal queries first, then paginate. Parallelize when safe. ([Claude Docs][6])
* Always return **provenance**: which tool, which params, and any limits (paging, time window).

## MCP (optional, for portability)

* If exposing tools to external clients (e.g., Claude Desktop/Code), wrap them as **MCP servers** with typed schemas and permissions; don’t re-invent adapters. ([Claude Docs][7])

## Local dev & CI expectations

* Provide a `make dev` target that: creates/activates venv, installs deps, runs `pre-commit`, `pytest`, and the smoke test.
* For long-running or external calls, add a **recorded-responses** mode (e.g., VCR) and a `--offline` flag.

## What to deliver per stage

**Phase 1 — Tools**

* Implement each tool with: docstring (purpose, params, example), type hints, retries/backoff, unit tests, CLI `--help`.
* CLI smoke: `python -m tools.<name> --help` and one real call with sanitized params.

**Phase 2 — RAG (docs + synonyms; not a DB)**

* Index only authoritative docs and our glossary. Cite snippet+URL in explanations. Do **not** replace live facts with RAG text. ([Claude Docs][3])

**Phase 3 — Agent (LangGraph)**

* Orchestrate router → tool(s) → sufficiency-checker → answer with clear **stop conditions** and guardrails (max retries, time windows). Prefer **LangGraph** for stateful control; use LangChain components under the hood.

## Execution controls

* Use **headless/JSON** modes for programmatic runs and stream when iterating. Handle non-zero exits and log errors. ([Claude Docs][8])
* When output needs strict formatting, **prefill** skeletons (e.g., JSON keys) to enforce structure. ([Claude Docs][9])

## Don’ts

* Don’t ship placeholder code as final.
* Don’t invent undocumented fields or endpoints.
* Don’t bypass venvs or write global installs.
* Don’t commit secrets; use `.env` and sample templates.



[1]: https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency?utm_source=chatgpt.com "Increase output consistency (JSON mode)"
[2]: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags?utm_source=chatgpt.com "Use XML tags to structure your prompts"
[3]: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview?utm_source=chatgpt.com "Prompt engineering overview - Claude Docs"
[4]: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices?utm_source=chatgpt.com "Claude 4 prompt engineering best practices"
[5]: https://docs.anthropic.com/en/docs/build-with-claude/tool-use?utm_source=chatgpt.com "Tool use with Claude"
[6]: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use?utm_source=chatgpt.com "How to implement tool use"
[7]: https://docs.anthropic.com/en/docs/agents-and-tools/mcp?utm_source=chatgpt.com "Model Context Protocol (MCP) - Claude Docs"
[8]: https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-headless?utm_source=chatgpt.com "Headless mode - Claude Docs"
[9]: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prefill-claudes-response?utm_source=chatgpt.com "Prefill Claude's response for greater output control"
