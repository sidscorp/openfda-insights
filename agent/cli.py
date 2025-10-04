"""
CLI for FDA Device Analyst agent.

Usage: python -m agent.cli "your question"
"""
import argparse
import json
import os
import sys

from agent.graph import FDAAgent


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="FDA Device Analyst Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agent.cli "Show me Class II devices"
  python -m agent.cli "How many 510k clearances since 2023?"

Environment:
  ANTHROPIC_API_KEY - Required for Claude LLM
  OPENFDA_API_KEY - Optional for higher rate limits
        """,
    )
    parser.add_argument("question", help="Your question about FDA device data")
    parser.add_argument("--api-key", help="openFDA API key")
    parser.add_argument(
        "--anthropic-key",
        default=os.getenv("ANTHROPIC_API_KEY"),
        help="Anthropic API key (default: from ANTHROPIC_API_KEY env)",
    )
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run router and extractor without calling APIs (for testing)",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Show detailed routing, RAG, and assessor decisions",
    )
    parser.add_argument("--config", help="Path to config file (unused, reserved)")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )

    args = parser.parse_args()

    # Check for Anthropic API key
    if not args.anthropic_key:
        print(
            "Error: ANTHROPIC_API_KEY required (set env var or use --anthropic-key)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Initialize agent
    try:
        agent = FDAAgent(api_key=args.api_key, anthropic_api_key=args.anthropic_key)
    except Exception as e:
        print(f"Error initializing agent: {e}", file=sys.stderr)
        sys.exit(1)

    # Run query
    try:
        result = agent.query(args.question, dry_run=args.dry_run)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Show explain output if requested
    if args.explain:
        print(f"\n{'='*60}")
        print("EXPLAIN MODE - Detailed Execution Trace")
        print(f"{'='*60}\n")
        print(f"[ROUTER] Selected endpoint: {result.get('selected_endpoint')}")
        print(f"[EXTRACTOR] Extracted params: {result.get('extracted_params', {})}")
        print(f"[ASSESSOR] Sufficient: {result.get('is_sufficient')} - {result.get('assessor_reason', 'N/A')}")
        print()

    # Output
    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"Question: {result['question']}")
        print(f"{'='*60}\n")
        if args.dry_run:
            print(f"DRY RUN - No API call made\n")
            print(f"Would query endpoint: {result.get('selected_endpoint')}")
            print(f"With params: {result.get('extracted_params', {})}")
        else:
            print(f"Answer: {result['answer']}\n")
            print("Provenance:")
            print(f"  Endpoint: {result['provenance'].get('endpoint')}")
            print(f"  Last Updated: {result['provenance'].get('last_updated')}")
            print(f"  Results: {result['provenance'].get('result_count')}")
            print(f"\nRetries: {result['retry_count']}")
            print(f"Sufficient: {result['is_sufficient']}")


if __name__ == "__main__":
    main()
