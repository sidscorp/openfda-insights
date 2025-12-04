"""
Command Line Interface for Enhanced FDA Explorer
"""

import json
import logging
import sys
import uuid
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON

from .config import load_config, get_config, print_config_validation

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("numexpr").setLevel(logging.WARNING)
logging.getLogger("fda_agent").setLevel(logging.WARNING)

console = Console()
stderr_console = Console(stderr=True)


class StatusHandler(logging.Handler):
    """Logging handler that updates a Rich status spinner."""
    def __init__(self, status=None):
        super().__init__()
        self.status = status
        self.setLevel(logging.INFO)

    def emit(self, record):
        if self.status:
            self.status.update(f"[bold green]{record.getMessage()}[/bold green]")


def get_console(ctx):
    """Get appropriate console - stderr if JSON mode, stdout otherwise."""
    if ctx.obj.get('json_mode'):
        return stderr_console
    return console


@click.group()
@click.option('--config', '-c', help='Configuration file path')
@click.option('--debug', '-d', is_flag=True, help='Enable debug mode')
@click.option('--api-key', help='FDA API key')
@click.option('--validate-config', is_flag=True, help='Validate configuration and exit')
@click.option('--skip-validation', is_flag=True, help='Skip startup validation')
@click.pass_context
def cli(ctx, config, debug, api_key, validate_config, skip_validation):
    """Enhanced FDA Explorer CLI - AI-powered FDA data exploration"""
    ctx.ensure_object(dict)
    ctx.obj['json_mode'] = '--json' in sys.argv

    try:
        validate_startup = not skip_validation
        out = get_console(ctx)

        if config:
            ctx.obj['config'] = load_config(config, validate_startup=validate_startup)
        else:
            ctx.obj['config'] = get_config(validate_startup=validate_startup)

        if api_key:
            ctx.obj['config'].openfda.api_key = api_key

        if debug:
            ctx.obj['config'].debug = True

        if validate_config:
            out.print("\n[bold blue]Configuration Validation Report[/bold blue]\n")
            print_config_validation()
            sys.exit(0)

        if not skip_validation:
            summary = ctx.obj['config'].get_validation_summary()
            if summary["warnings"] or summary["info"]:
                out.print("\n[yellow]Configuration Validation Warnings:[/yellow]")
                for warning in summary["warnings"]:
                    out.print(f"  [yellow]Warning:[/yellow] {warning}")
                for info in summary["info"]:
                    out.print(f"  [dim]Info:[/dim] {info}")
                out.print()

    except ValueError as e:
        console.print(f"\n[red]Configuration Error:[/red] {e}")
        console.print("\nUse --validate-config to see detailed validation report.")
        console.print("Use --skip-validation to bypass validation (not recommended).")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Unexpected Error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument('question')
@click.option('--provider', '-p',
              type=click.Choice(['openrouter', 'bedrock', 'ollama']),
              default='openrouter',
              help='LLM provider to use')
@click.option('--model', '-m', default=None, help='Model to use (provider-specific)')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output including tool calls')
@click.option('--raw', '-r', is_flag=True, help='Show raw tool results without LLM summarization')
@click.option('--json', 'as_json', is_flag=True, help='Output full structured response as JSON')
@click.option('--session-id', help='Session ID for multi-turn conversations (reuse to continue)')
@click.pass_context
def ask(ctx, question, provider, model, verbose, raw, as_json, session_id):
    """Ask the FDA Intelligence Agent a question.

    The agent uses tools to search FDA databases and synthesize answers.
    It can resolve devices, search adverse events, recalls, 510(k) clearances,
    PMA approvals, classifications, and UDI records.

    Examples:
        fda ask "What adverse events have been reported for surgical masks?"
        fda ask "Has 3M had any device recalls in the past year?"
        fda ask --provider bedrock "What is the regulatory classification for N95 respirators?"
    """
    from .agent import FDAAgent
    from langchain_core.messages import AIMessage, ToolMessage

    try:
        agent = FDAAgent(provider=provider, model=model)

        if as_json:
            stderr_console = Console(stderr=True)
            with stderr_console.status("[bold green]Thinking...[/bold green]"):
                response = agent.ask(question, session_id=session_id)

            if response.structured:
                print(response.structured.model_dump_json(indent=2))
            else:
                output = {
                    "summary": response.content,
                    "model": response.model,
                    "token_usage": {
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "total_tokens": response.total_tokens,
                        "cost_usd": response.cost
                    }
                }
                print(json.dumps(output, indent=2))
            return

        if not verbose and not raw:
            # Simple default mode - just show the final answer
            final_response = None
            all_ai_messages = []
            tool_count = 0

            with console.status("[bold green]Thinking...[/bold green]") as status:
                for event in agent.stream(question, session_id=session_id):
                    node_name = list(event.keys())[0] if event else "unknown"
                    messages = event.get(node_name, {}).get("messages", [])

                    for msg in messages:
                        if isinstance(msg, AIMessage):
                            all_ai_messages.append(msg)
                            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    tool_count += 1
                                    tool_name = tool_call.get('name', 'unknown')
                                    status.update(f"[bold green]Calling {tool_name}...[/bold green]")
                            elif msg.content:
                                final_response = msg

            if final_response:
                console.print(Panel(
                    final_response.content,
                    title="FDA Agent Response",
                    border_style="green"
                ))

                total_input = 0
                total_output = 0
                total_cost = 0.0
                model_name = ""
                for msg in all_ai_messages:
                    if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                        total_input += msg.usage_metadata.get("input_tokens", 0)
                        total_output += msg.usage_metadata.get("output_tokens", 0)
                    if hasattr(msg, 'response_metadata') and msg.response_metadata:
                        model_name = msg.response_metadata.get("model_name", model_name)
                        token_usage = msg.response_metadata.get("token_usage", {})
                        if token_usage.get("cost"):
                            total_cost += token_usage["cost"]

                stats_parts = []
                if model_name:
                    stats_parts.append(f"Model: {model_name}")
                if total_input or total_output:
                    stats_parts.append(f"Tokens: {total_input:,} in / {total_output:,} out")
                if total_cost > 0:
                    stats_parts.append(f"Cost: ${total_cost:.4f}")
                stats_parts.append(f"Tool calls: {tool_count}")
                if stats_parts:
                    console.print(f"[dim]{' | '.join(stats_parts)}[/dim]")
            else:
                console.print("[yellow]No response generated[/yellow]")
            return

        if verbose or raw:
            console.print(f"[dim]Provider: {provider} | Model: {model or 'default'}[/dim]\n")
            console.print(Panel(question, title="Question", border_style="cyan"))
            console.print()

            final_response = None
            tool_calls_made = []
            tool_results = []
            all_ai_messages = []

            status = console.status("[bold green]Thinking...[/bold green]")
            status_handler = StatusHandler(status)
            fda_logger = logging.getLogger("fda_agent")
            fda_logger.addHandler(status_handler)
            fda_logger.setLevel(logging.INFO)
            fda_logger.propagate = False

            status.start()
            try:
                for event in agent.stream(question, session_id=session_id):
                    node_name = list(event.keys())[0] if event else "unknown"
                    messages = event.get(node_name, {}).get("messages", [])

                    for msg in messages:
                        if isinstance(msg, AIMessage):
                            all_ai_messages.append(msg)
                            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    tool_calls_made.append(tool_call)
                                    tool_name = tool_call.get('name', 'unknown')
                                    status.update(f"[bold green]Calling {tool_name}...[/bold green]")
                            elif msg.content:
                                final_response = msg

                        elif isinstance(msg, ToolMessage):
                            tool_results.append({
                                "tool_call_id": msg.tool_call_id,
                                "content": msg.content
                            })
                            status.update(f"[bold green]Processing results ({len(tool_results)} tool calls complete)...[/bold green]")
            finally:
                fda_logger.removeHandler(status_handler)
                fda_logger.propagate = True
                status.stop()

            if verbose:
                for i, tool_call in enumerate(tool_calls_made):
                    console.print(Panel(
                        f"[bold]{tool_call['name']}[/bold]\n\n"
                        f"[dim]Arguments:[/dim]\n{json.dumps(tool_call['args'], indent=2)}",
                        title=f"Tool Call {i+1}",
                        border_style="blue"
                    ))

                    if i < len(tool_results):
                        result = tool_results[i]
                        console.print(Panel(
                            result["content"],
                            title=f"Tool Result {i+1}",
                            border_style="green"
                        ))
                    console.print()

            if raw:
                console.print(Panel(
                    "\n\n".join([r["content"] for r in tool_results]),
                    title="Complete Tool Results",
                    border_style="green"
                ))
                stats_parts = [f"Tool calls: {len(tool_calls_made)}"]
                console.print(f"[dim]{' | '.join(stats_parts)}[/dim]")
            elif final_response:
                console.print(Panel(
                    final_response.content,
                    title="FDA Agent Response",
                    border_style="green"
                ))

                total_input = 0
                total_output = 0
                total_cost = 0.0
                model_name = ""
                for msg in all_ai_messages:
                    if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                        total_input += msg.usage_metadata.get("input_tokens", 0)
                        total_output += msg.usage_metadata.get("output_tokens", 0)
                    if hasattr(msg, 'response_metadata') and msg.response_metadata:
                        model_name = msg.response_metadata.get("model_name", model_name)
                        token_usage = msg.response_metadata.get("token_usage", {})
                        if token_usage.get("cost"):
                            total_cost += token_usage["cost"]

                stats_parts = []
                if model_name:
                    stats_parts.append(f"Model: {model_name}")
                if total_input or total_output:
                    stats_parts.append(f"Tokens: {total_input:,} in / {total_output:,} out ({total_input + total_output:,} total)")
                if total_cost > 0:
                    stats_parts.append(f"Cost: ${total_cost:.4f}")
                stats_parts.append(f"Tool calls: {len(tool_calls_made)}")
                if stats_parts:
                    console.print(f"[dim]{' | '.join(stats_parts)}[/dim]")
            else:
                console.print("[yellow]No response generated[/yellow]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        if ctx.obj.get('config') and hasattr(ctx.obj['config'], 'debug') and ctx.obj['config'].debug:
            import traceback
            console.print(traceback.format_exc())


@cli.command()
@click.option('--provider', '-p',
              type=click.Choice(['openrouter', 'bedrock', 'ollama']),
              default='openrouter',
              help='LLM provider to use')
@click.option('--model', '-m', default=None, help='Model to use (provider-specific)')
@click.option('--session-id', help='Session ID for the chat (reuse to continue)')
@click.pass_context
def chat(ctx, provider, model, session_id):
    """Interactive multi-turn chat with the FDA agent."""
    from .agent import FDAAgent
    from langchain_core.messages import AIMessage, ToolMessage

    sid = session_id or str(uuid.uuid4())
    console.print(f"[dim]Provider: {provider} | Model: {model or 'default'} | Session: {sid}[/dim]\n")
    console.print("[cyan]Type your question. Enter /exit or Ctrl+C to quit.[/cyan]\n")

    agent = FDAAgent(provider=provider, model=model)

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Ending chat.[/dim]")
                break

            if not user_input:
                continue
            if user_input.lower() in {"/exit", "exit", "quit", "/quit"}:
                console.print("[dim]Ending chat.[/dim]")
                break

            final_response = None
            all_ai_messages = []
            tool_count = 0

            status = console.status("[bold green]Thinking...[/bold green]")
            status_handler = StatusHandler(status)
            fda_logger = logging.getLogger("fda_agent")
            fda_logger.addHandler(status_handler)
            fda_logger.setLevel(logging.INFO)
            fda_logger.propagate = False

            status.start()
            try:
                for event in agent.stream(user_input, session_id=sid):
                    node_name = list(event.keys())[0] if event else "unknown"
                    messages = event.get(node_name, {}).get("messages", [])

                    for msg in messages:
                        if isinstance(msg, AIMessage):
                            all_ai_messages.append(msg)
                            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    tool_count += 1
                                    tool_name = tool_call.get('name', 'unknown')
                                    status.update(f"[bold green]Calling {tool_name}...[/bold green]")
                            elif msg.content:
                                final_response = msg
                        elif isinstance(msg, ToolMessage):
                            status.update(f"[bold green]Processing ({tool_count} tools called)...[/bold green]")
            finally:
                fda_logger.removeHandler(status_handler)
                fda_logger.propagate = True
                status.stop()

            if final_response:
                console.print(Panel(
                    final_response.content,
                    title="FDA Agent Response",
                    border_style="green"
                ))

                total_input = 0
                total_output = 0
                total_cost = 0.0
                model_name = ""
                for msg in all_ai_messages:
                    if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                        total_input += msg.usage_metadata.get("input_tokens", 0)
                        total_output += msg.usage_metadata.get("output_tokens", 0)
                    if hasattr(msg, 'response_metadata') and msg.response_metadata:
                        model_name = msg.response_metadata.get("model_name", model_name)
                        token_usage = msg.response_metadata.get("token_usage", {})
                        if token_usage.get("cost"):
                            total_cost += token_usage["cost"]

                stats_parts = []
                if model_name:
                    stats_parts.append(f"Model: {model_name}")
                if total_input or total_output:
                    stats_parts.append(f"Tokens: {total_input:,} in / {total_output:,} out ({total_input + total_output:,} total)")
                if total_cost > 0:
                    stats_parts.append(f"Cost: ${total_cost:.4f}")
                stats_parts.append(f"Tool calls: {tool_count}")
                if stats_parts:
                    console.print(f"[dim]{' | '.join(stats_parts)}[/dim]")
            else:
                console.print("[yellow]No response generated[/yellow]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        if ctx.obj.get('config') and hasattr(ctx.obj['config'], 'debug') and ctx.obj['config'].debug:
            import traceback
            console.print(traceback.format_exc())


@cli.command()
@click.argument('query')
@click.option('--limit', '-l', default=20, help='Maximum results to show')
@click.option('--fuzzy/--exact', default=True, help='Enable/disable fuzzy matching')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
@click.option('--confidence', '-c', default=0.7, help='Minimum confidence threshold (0.0-1.0)')
@click.pass_context
def resolve(ctx, query, limit, fuzzy, as_json, confidence):
    """Resolve device query to FDA regulatory identifiers.

    Searches GUDID database for devices matching the query and returns
    FDA product codes, GMDN terms, and device identifiers.

    Examples:
        fda resolve "mask"
        fda resolve "3M" --limit 50
        fda resolve "insulin pump" --json
    """
    from .tools import DeviceResolver

    config = ctx.obj['config']

    with console.status(f"[bold green]Searching devices for '{query}'...[/bold green]"):
        resolver = DeviceResolver(db_path=config.gudid_db_path)
        try:
            response = resolver.resolve(
                query=query,
                limit=limit,
                fuzzy=fuzzy,
                min_confidence=confidence
            )
        finally:
            resolver.close()

    if response.total_matches == 0:
        console.print(f"[yellow]No devices found matching '{query}'[/yellow]")
        return

    if as_json:
        console.print(JSON(response.model_dump_json(indent=2)))
        return

    table = Table(title=f"Device Resolution: '{query}'")
    table.add_column("Brand Name", style="cyan", max_width=40)
    table.add_column("Company", style="green", max_width=30)
    table.add_column("Product Codes", style="yellow")
    table.add_column("Match Type", style="blue")
    table.add_column("Confidence", style="magenta")

    for match in response.matches[:limit]:
        brand = match.device.brand_name or "[dim]N/A[/dim]"
        if len(brand) > 40:
            brand = brand[:37] + "..."

        company = match.device.company_name or "[dim]N/A[/dim]"
        if len(company) > 30:
            company = company[:27] + "..."

        codes = ", ".join(match.device.get_product_codes()[:3])
        if len(match.device.get_product_codes()) > 3:
            codes += f" (+{len(match.device.get_product_codes()) - 3})"

        table.add_row(
            brand,
            company,
            codes or "[dim]None[/dim]",
            match.match_type.value,
            f"{match.confidence:.2f}"
        )

    console.print(table)

    console.print(Panel(
        f"[bold]Summary[/bold]\n"
        f"Total matches: {response.total_matches}\n"
        f"Unique product codes: {len(response.get_unique_product_codes())}\n"
        f"Unique companies: {len(response.get_unique_companies())}\n"
        f"Search time: {response.execution_time_ms:.0f}ms",
        title="Results",
        border_style="dim"
    ))

    if response.get_unique_product_codes():
        codes_list = ", ".join(response.get_unique_product_codes()[:10])
        if len(response.get_unique_product_codes()) > 10:
            codes_list += f" (+{len(response.get_unique_product_codes()) - 10} more)"
        console.print(f"\n[bold]Product Codes Found:[/bold] {codes_list}")


@cli.command()
@click.option('--host', default='0.0.0.0', help='Server host')
@click.option('--port', default=8001, help='Server port')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
@click.pass_context
def serve(ctx, host, port, reload):
    """Start the API server"""
    import uvicorn

    console.print(f"[green]Starting FDA Explorer API on {host}:{port}[/green]")
    console.print(f"[dim]API docs: http://{host}:{port}/docs[/dim]")

    uvicorn.run(
        "src.enhanced_fda_explorer.api_endpoints:app",
        host=host,
        port=port,
        reload=reload,
    )


@cli.command('validate-config')
@click.option('--config', '-c', help='Configuration file path to validate')
@click.option('--strict', is_flag=True, help='Treat warnings as errors')
@click.pass_context
def validate_config_cmd(ctx, config, strict):
    """Validate configuration and display comprehensive report"""
    try:
        if config:
            cfg = load_config(config, validate_startup=False)
        else:
            cfg = get_config(validate_startup=False)

        console.print("\n[bold blue]Configuration Validation Report[/bold blue]\n")

        summary = cfg.get_validation_summary()

        if summary["critical"]:
            console.print("[red]CRITICAL ISSUES:[/red]")
            for issue in summary["critical"]:
                console.print(f"  {issue}")
            console.print()

        if summary["errors"]:
            console.print("[red]ERRORS:[/red]")
            for issue in summary["errors"]:
                console.print(f"  {issue}")
            console.print()

        if summary["warnings"]:
            console.print("[yellow]WARNINGS:[/yellow]")
            for issue in summary["warnings"]:
                console.print(f"  {issue}")
            console.print()

        if summary["info"]:
            console.print("[cyan]INFO:[/cyan]")
            for issue in summary["info"]:
                console.print(f"  {issue}")
            console.print()

        if not any(summary.values()):
            console.print("[green]Configuration validation passed with no issues![/green]")

        has_critical_or_errors = summary["critical"] or summary["errors"]
        has_warnings = summary["warnings"]

        if has_critical_or_errors:
            console.print(f"\n[red]Validation failed with {len(summary['critical']) + len(summary['errors'])} critical issues.[/red]")
            sys.exit(1)
        elif strict and has_warnings:
            console.print(f"\n[yellow]Validation failed in strict mode with {len(summary['warnings'])} warnings.[/yellow]")
            sys.exit(1)
        else:
            console.print(f"\n[green]Validation passed.[/green]")
            sys.exit(0)

    except Exception as e:
        console.print(f"\n[red]Configuration validation failed:[/red] {e}")
        sys.exit(1)


@cli.command('build-gudid')
@click.argument('release_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--output', '-o', default=None, help='Output database path (default: data/gudid.db)')
@click.pass_context
def build_gudid(ctx, release_dir, output):
    """Build GUDID database from FDA release files.

    RELEASE_DIR is the path to the GUDID full release directory containing XML files.

    Examples:
        fda build-gudid ~/Downloads/gudid_full_release_20250902
        fda build-gudid /path/to/release --output /custom/path/gudid.db
    """
    from pathlib import Path
    from .data.gudid_indexer import GUDIDIndexer

    # Default output path - relative to project root
    if output is None:
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        output = str(data_dir / "gudid.db")

    console.print(f"[bold blue]Building GUDID Database[/bold blue]\n")
    console.print(f"  Source: {release_dir}")
    console.print(f"  Output: {output}\n")

    # Check for XML files
    xml_files = list(Path(release_dir).glob("*.xml"))
    if not xml_files:
        console.print(f"[red]Error: No XML files found in {release_dir}[/red]")
        sys.exit(1)

    console.print(f"Found {len(xml_files)} XML files to index\n")

    try:
        indexer = GUDIDIndexer(output)
        indexer.index_directory(release_dir)
        indexer.verify_index()
        indexer.close()

        console.print(f"\n[green]Database built successfully![/green]")
        console.print(f"\nTo use this database, set the environment variable:")
        console.print(f"  [cyan]export GUDID_DB_PATH={output}[/cyan]")
        console.print(f"\nOr add it to your ~/.zshrc for persistence.")

    except Exception as e:
        console.print(f"[red]Error building database:[/red] {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    cli()


if __name__ == "__main__":
    main()
