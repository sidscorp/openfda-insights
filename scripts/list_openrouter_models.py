#!/usr/bin/env python3
"""
List OpenRouter model slugs with optional search/filtering.

Features:
- Filter by substring (case-insensitive)
- Optionally require tool-calling support
- Show pricing info (prompt/completion per 1M tokens) when available
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx


API_URL = "https://openrouter.ai/api/v1/models"


def load_api_key() -> str:
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("AI_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY or AI_API_KEY environment variable is required.")
    return api_key


def fetch_models(api_key: str) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=20, headers=headers) as client:
        resp = client.get(API_URL)
        resp.raise_for_status()
        data = resp.json()
    return data.get("data", []) or data.get("models", []) or []


def supports_tools(model: dict[str, Any]) -> bool:
    """
    Best-effort detection of tool/function calling support across OpenRouter payload shapes.
    Looks at known fields and any capability/spec keys that mention tool/function.
    """
    def has_toolish(obj: Any) -> bool:
        if isinstance(obj, bool):
            return obj
        if isinstance(obj, str):
            low = obj.lower()
            return "tool" in low or "function" in low
        if isinstance(obj, (list, tuple, set)):
            return any(has_toolish(item) for item in obj)
        if isinstance(obj, dict):
            return any(
                ("tool" in str(k).lower() or "function" in str(k).lower()) and has_toolish(v)
                for k, v in obj.items()
            )
        return False

    if has_toolish(model.get("capabilities")):
        return True
    if has_toolish(model.get("spec")):
        return True

    # Direct booleans some models expose
    for field in ["tools", "tool_calls", "function_calling", "functions", "tool_choice", "toolcalling"]:
        if has_toolish(model.get(field)):
            return True

    # Last resort: description hints
    desc = model.get("description") or ""
    if "tool" in desc.lower() or "function call" in desc.lower():
        return True

    return False


def format_pricing(model: dict[str, Any]) -> str:
    pricing = model.get("pricing", {})
    # Normalize common keys
    prompt = pricing.get("prompt") or pricing.get("input") or pricing.get("prompt_tokens")
    completion = pricing.get("completion") or pricing.get("output") or pricing.get("completion_tokens")

    def parse_num(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").strip()
            try:
                return float(cleaned)
            except Exception:
                return None
        return None

    def fmt(value: Any) -> str:
        num = parse_num(value)
        if num is None:
            return "-"
        if num == 0:
            return "free"
        per_m = num  # OpenRouter pricing is per 1M tokens
        per_100k = num / 10
        # Choose a readable format depending on magnitude
        if per_m >= 0.01:
            return f"${per_m:,.4f} per 1M"
        if per_m >= 0.0001:
            return f"${per_m:,.6f} per 1M"
        # Very small numbers: show per 1M and per 100k to avoid scientific notation
        return f"${per_m:,.8f} per 1M (${per_100k:,.6f} per 100k)"

    return f"in: {fmt(prompt)} | out: {fmt(completion)}"


def main() -> None:
    parser = argparse.ArgumentParser(description="List OpenRouter models/slugs.")
    parser.add_argument("search", nargs="?", default="", help="Substring to match against model id/name.")
    parser.add_argument("--tools-only", action="store_true", help="Only show models that support tool calling.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON for scripting.")
    args = parser.parse_args()

    api_key = load_api_key()
    try:
        models = fetch_models(api_key)
    except httpx.HTTPStatusError as exc:
        sys.exit(f"Failed to list models: HTTP {exc.response.status_code} - {exc.response.text}")
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Failed to list models: {exc}")

    needle = args.search.lower()
    filtered = []
    for m in models:
        mid = m.get("id", "")
        name = m.get("name", mid)
        text = f"{mid} {name}".lower()
        if needle and needle not in text:
            continue
        has_tools = supports_tools(m)
        if args.tools_only and not has_tools:
            continue
        filtered.append(
            {
                "id": mid,
                "name": name,
                "tools": has_tools,
                "pricing": m.get("pricing", {}),
                "formatted_pricing": format_pricing(m),
            }
        )

    filtered.sort(key=lambda x: x["id"])

    if args.json:
        print(json.dumps(filtered, indent=2))
        return

    if not filtered:
        print("No models matched your filters.")
        return

    print(f"Found {len(filtered)} models matching '{args.search}':\n")
    for item in filtered:
        tools_flag = "✅ tools" if item["tools"] else "❌ no-tools"
        print(f"- {item['id']}  ({tools_flag})")
        print(f"  name: {item['name']}")
        print(f"  pricing: {item['formatted_pricing']}")


if __name__ == "__main__":
    main()
