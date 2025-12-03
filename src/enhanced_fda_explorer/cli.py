"""
Command Line Interface for Enhanced FDA Explorer
"""

import json
import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON

from .config import load_config, get_config, print_config_validation


console = Console()


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

    try:
        validate_startup = not skip_validation

        if config:
            ctx.obj['config'] = load_config(config, validate_startup=validate_startup)
        else:
            ctx.obj['config'] = get_config(validate_startup=validate_startup)

        if api_key:
            ctx.obj['config'].openfda.api_key = api_key

        if debug:
            ctx.obj['config'].debug = True

        if validate_config:
            console.print("\n[bold blue]Configuration Validation Report[/bold blue]\n")
            print_config_validation()
            sys.exit(0)

        if not skip_validation:
            summary = ctx.obj['config'].get_validation_summary()
            if summary["warnings"] or summary["info"]:
                console.print("\n[yellow]Configuration Validation Warnings:[/yellow]")
                for warning in summary["warnings"]:
                    console.print(f"  ⚠️  {warning}")
                for info in summary["info"]:
                    console.print(f"  ℹ️  {info}")
                console.print()

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
@click.pass_context
def ask(ctx, question, provider, model, verbose):
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

    with console.status("[bold green]Thinking...[/bold green]") as status:
        try:
            agent = FDAAgent(provider=provider, model=model)

            if verbose:
                console.print(f"[dim]Provider: {provider} | Model: {model or 'default'}[/dim]\n")

                for event in agent.stream(question):
                    node_name = list(event.keys())[0] if event else "unknown"
                    messages = event.get(node_name, {}).get("messages", [])

                    if messages:
                        last_message = messages[-1]

                        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                            for tool_call in last_message.tool_calls:
                                console.print(f"[blue]Tool:[/blue] {tool_call['name']}")
                                console.print(f"[dim]{tool_call['args']}[/dim]\n")

                        elif hasattr(last_message, 'content') and last_message.content:
                            if node_name == "tools":
                                content_preview = last_message.content[:300]
                                if len(last_message.content) > 300:
                                    content_preview += "..."
                                console.print(f"[green]Result:[/green] {content_preview}\n")

            response = agent.ask(question)

        except Exception as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            if ctx.obj.get('config') and hasattr(ctx.obj['config'], 'debug') and ctx.obj['config'].debug:
                import traceback
                console.print(traceback.format_exc())
            return

    console.print(Panel(
        response.content,
        title="FDA Agent Response",
        border_style="green"
    ))

    stats_parts = []
    if response.model:
        stats_parts.append(f"Model: {response.model}")
    if response.total_tokens > 0:
        stats_parts.append(f"Tokens: {response.input_tokens:,} in / {response.output_tokens:,} out ({response.total_tokens:,} total)")
    if response.cost is not None:
        stats_parts.append(f"Cost: ${response.cost:.4f}")
    if stats_parts:
        console.print(f"[dim]{' | '.join(stats_parts)}[/dim]")


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


def main():
    """Main entry point"""
    cli()


if __name__ == "__main__":
    main()
