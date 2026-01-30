#!/usr/bin/env python3
"""
Model Comparison Test for Tool Calling Quality

Tests different LLM models on their ability to:
1. Select the correct tool for a given query
2. Use proper function calling (not XML text output)
3. Response time
"""
import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

MODELS_TO_TEST = [
    "xiaomi/mimo-v2-flash:free",
    "google/gemini-2.5-flash",
    "google/gemini-2.5-flash-lite",
    "x-ai/grok-4.1-fast",
]

TEST_CASES = [
    {
        "name": "Direct product code query",
        "query": "What devices are product code MSH?",
        "expected_tool": "list_devices",
        "description": "Should use list_devices, NOT resolve_device"
    },
    {
        "name": "Natural language device search",
        "query": "Find surgical masks in the FDA database",
        "expected_tool": "resolve_device",
        "description": "Should use resolve_device for NL search"
    },
    {
        "name": "Manufacturer query",
        "query": "What devices does 3M manufacture?",
        "expected_tool": "resolve_manufacturer",
        "description": "Should use resolve_manufacturer"
    },
]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_devices",
            "description": """REQUIRED when user asks "What devices are [product code]?" or wants to see specific device examples.
Returns actual device records with brand names, company names, model numbers, and UDI identifiers.

USE THIS TOOL when:
- User asks about specific devices for a product code (e.g., "What devices are MSH?")
- User wants brand names, UDIs, or device examples
- You already know the 3-letter product code

DO NOT use resolve_device for these queries - use list_devices instead.
Input: 3-letter FDA product code (e.g., 'MSH', 'DXN', 'QAB').""",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_code": {
                        "type": "string",
                        "description": "FDA 3-letter product code (e.g., 'MSH', 'DXN')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum devices to return (default 25)",
                        "default": 25
                    }
                },
                "required": ["product_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_device",
            "description": """Find FDA product codes for a device type using natural language search.
Returns product code COUNTS and top manufacturers - NOT individual device records.

USE THIS TOOL when:
- User searches by device type name (e.g., "surgical mask", "ventilator", "pacemaker")
- You need to find which product codes match a concept
- User asks for product code counts or manufacturer rankings

NOTE: If user already has a product code and wants to see SPECIFIC DEVICES,
use list_devices instead - resolve_device only returns aggregated counts.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Device name, brand, company, or product code to search for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 500
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_manufacturer",
            "description": """Look up a manufacturer/company in the GUDID database.
Returns list of matching companies with device counts and top product codes.

USE THIS TOOL when:
- User asks about a specific company's devices
- User wants to know what a manufacturer makes
- Query mentions company/manufacturer names""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Company or manufacturer name to search for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results",
                        "default": 20
                    }
                },
                "required": ["query"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are an FDA regulatory intelligence assistant. You have access to tools for querying FDA medical device databases.

CRITICAL: When you need to call a tool, use the function calling mechanism.
NEVER output tool calls as XML text like <tool_call> or <function=...>.
Your response should ONLY contain analysis text, NOT tool invocation syntax."""


def test_model(model_name: str):
    """Test a single model on all test cases."""
    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print('='*60)

    api_key = os.getenv("AI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: No API key found")
        return None

    try:
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.1,
            max_tokens=500,
        )
        llm_with_tools = llm.bind_tools(TOOLS)
    except Exception as e:
        print(f"ERROR creating LLM: {e}")
        return None

    results = {
        "model": model_name,
        "tests": [],
        "total_time": 0,
        "correct_tool_selection": 0,
        "proper_function_calling": 0,
    }

    for test in TEST_CASES:
        print(f"\n  Test: {test['name']}")
        print(f"  Query: {test['query']}")
        print(f"  Expected: {test['expected_tool']}")

        start = time.time()
        try:
            response = llm_with_tools.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=test['query'])
            ])
            elapsed = time.time() - start

            # Check for tool calls
            tool_calls = getattr(response, 'tool_calls', [])
            content = getattr(response, 'content', '')

            # Check if XML was output instead of proper tool calling
            has_xml = '<tool_call>' in content or '<function=' in content

            selected_tool = None
            if tool_calls:
                selected_tool = tool_calls[0].get('name')

            correct = selected_tool == test['expected_tool']
            proper_fc = not has_xml and (tool_calls is not None)

            result = {
                "test_name": test['name'],
                "expected": test['expected_tool'],
                "selected": selected_tool,
                "correct": correct,
                "proper_function_calling": proper_fc,
                "has_xml_in_content": has_xml,
                "time_seconds": elapsed,
                "content_preview": content[:100] if content else ""
            }
            results["tests"].append(result)
            results["total_time"] += elapsed

            if correct:
                results["correct_tool_selection"] += 1
            if proper_fc:
                results["proper_function_calling"] += 1

            status = "✓" if correct else "✗"
            fc_status = "✓ proper FC" if proper_fc else "✗ XML output"
            print(f"  Result: {status} Selected: {selected_tool} | {fc_status} | {elapsed:.2f}s")

            if has_xml:
                print(f"  WARNING: XML in content: {content[:80]}...")

        except Exception as e:
            print(f"  ERROR: {e}")
            results["tests"].append({
                "test_name": test['name'],
                "error": str(e)
            })

    # Summary
    total_tests = len(TEST_CASES)
    print(f"\n  Summary for {model_name}:")
    print(f"    Tool Selection: {results['correct_tool_selection']}/{total_tests}")
    print(f"    Proper Function Calling: {results['proper_function_calling']}/{total_tests}")
    print(f"    Total Time: {results['total_time']:.2f}s")

    return results


def main():
    print("Model Comparison Test for FDA Agent Tool Calling")
    print("="*60)

    all_results = []

    for model in MODELS_TO_TEST:
        result = test_model(model)
        if result:
            all_results.append(result)

    # Final comparison
    print("\n" + "="*60)
    print("FINAL COMPARISON")
    print("="*60)
    print(f"{'Model':<40} {'Tool Select':>12} {'Proper FC':>12} {'Time':>8}")
    print("-"*72)

    for r in all_results:
        total = len(TEST_CASES)
        print(f"{r['model']:<40} {r['correct_tool_selection']}/{total:>10} {r['proper_function_calling']}/{total:>10} {r['total_time']:>6.1f}s")

    # Save results
    with open('/tmp/model_comparison_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    print("\nDetailed results saved to /tmp/model_comparison_results.json")


if __name__ == "__main__":
    main()
