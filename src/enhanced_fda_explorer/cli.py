"""
Command Line Interface for Enhanced FDA Explorer
"""

import asyncio
import json
import sys
from typing import List, Optional
from pathlib import Path

import click
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.json import JSON

from .core import FDAExplorer
from .config import load_config, get_config


console = Console()


@click.group()
@click.option('--config', '-c', help='Configuration file path')
@click.option('--debug', '-d', is_flag=True, help='Enable debug mode')
@click.option('--api-key', help='FDA API key')
@click.pass_context
def cli(ctx, config, debug, api_key):
    """Enhanced FDA Explorer CLI - Comprehensive FDA data exploration tool"""
    ctx.ensure_object(dict)
    
    # Load configuration
    if config:
        ctx.obj['config'] = load_config(config)
    else:
        ctx.obj['config'] = get_config()
    
    # Override API key if provided
    if api_key:
        ctx.obj['config'].openfda.api_key = api_key
    
    # Set debug mode
    if debug:
        ctx.obj['config'].debug = True
    
    ctx.obj['explorer'] = None


@cli.command()
@click.argument('query')
@click.option('--type', '-t', default='device', help='Query type: device or manufacturer')
@click.option('--limit', '-l', default=100, help='Maximum results per endpoint')
@click.option('--endpoints', '-e', multiple=True, help='Specific endpoints to search')
@click.option('--output', '-o', help='Output file path (JSON)')
@click.option('--format', '-f', default='table', help='Output format: table, json, csv')
@click.option('--ai-analysis', is_flag=True, default=True, help='Include AI analysis')
@click.pass_context
def search(ctx, query, type, limit, endpoints, output, format, ai_analysis):
    """Search FDA data"""
    
    async def _search():
        explorer = FDAExplorer(ctx.obj['config'])
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Searching FDA data...", total=None)
                
                response = await explorer.search(
                    query=query,
                    query_type=type,
                    endpoints=list(endpoints) if endpoints else None,
                    limit=limit,
                    include_ai_analysis=ai_analysis
                )
                
                progress.update(task, completed=True)
            
            # Display results
            _display_search_results(response, format, output)
            
        finally:
            explorer.close()
    
    asyncio.run(_search())


@cli.command()
@click.argument('device_name')
@click.option('--lookback', '-l', default=12, help='Lookback period in months')
@click.option('--risk-assessment', is_flag=True, default=True, help='Include risk assessment')
@click.option('--output', '-o', help='Output file path (JSON)')
@click.option('--format', '-f', default='summary', help='Output format: summary, detailed, json')
@click.pass_context
def device(ctx, device_name, lookback, risk_assessment, output, format):
    """Get device intelligence"""
    
    async def _device():
        explorer = FDAExplorer(ctx.obj['config'])
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Analyzing device data...", total=None)
                
                intelligence = await explorer.get_device_intelligence(
                    device_name=device_name,
                    lookback_months=lookback,
                    include_risk_assessment=risk_assessment
                )
                
                progress.update(task, completed=True)
            
            # Display results
            _display_device_intelligence(intelligence, format, output)
            
        finally:
            explorer.close()
    
    asyncio.run(_device())


@cli.command()
@click.argument('device_names', nargs=-1, required=True)
@click.option('--lookback', '-l', default=12, help='Lookback period in months')
@click.option('--output', '-o', help='Output file path (JSON)')
@click.option('--format', '-f', default='comparison', help='Output format: comparison, detailed, json')
@click.pass_context
def compare(ctx, device_names, lookback, output, format):
    """Compare multiple devices"""
    
    if len(device_names) < 2:
        console.print("[red]Error: At least 2 devices required for comparison[/red]")
        sys.exit(1)
    
    async def _compare():
        explorer = FDAExplorer(ctx.obj['config'])
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Comparing devices...", total=None)
                
                comparison = await explorer.compare_devices(
                    device_names=list(device_names),
                    lookback_months=lookback
                )
                
                progress.update(task, completed=True)
            
            # Display results
            _display_device_comparison(comparison, format, output)
            
        finally:
            explorer.close()
    
    asyncio.run(_compare())


@cli.command()
@click.argument('manufacturer_name')
@click.option('--lookback', '-l', default=12, help='Lookback period in months')
@click.option('--output', '-o', help='Output file path (JSON)')
@click.option('--format', '-f', default='summary', help='Output format: summary, detailed, json')
@click.pass_context
def manufacturer(ctx, manufacturer_name, lookback, output, format):
    """Get manufacturer intelligence"""
    
    async def _manufacturer():
        explorer = FDAExplorer(ctx.obj['config'])
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Analyzing manufacturer data...", total=None)
                
                intelligence = await explorer.get_manufacturer_intelligence(
                    manufacturer_name=manufacturer_name,
                    lookback_months=lookback
                )
                
                progress.update(task, completed=True)
            
            # Display results
            _display_manufacturer_intelligence(intelligence, format, output)
            
        finally:
            explorer.close()
    
    asyncio.run(_manufacturer())


@cli.command()
@click.argument('query')
@click.option('--periods', '-p', multiple=True, help='Time periods (e.g., 6months, 1year)')
@click.option('--output', '-o', help='Output file path (JSON)')
@click.option('--format', '-f', default='trends', help='Output format: trends, detailed, json')
@click.pass_context
def trends(ctx, query, periods, output, format):
    """Analyze trends over time"""
    
    async def _trends():
        explorer = FDAExplorer(ctx.obj['config'])
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Analyzing trends...", total=None)
                
                trend_analysis = await explorer.get_trend_analysis(
                    query=query,
                    time_periods=list(periods) if periods else None
                )
                
                progress.update(task, completed=True)
            
            # Display results
            _display_trend_analysis(trend_analysis, format, output)
            
        finally:
            explorer.close()
    
    asyncio.run(_trends())


@cli.command()
@click.pass_context
def stats(ctx):
    """Get summary statistics"""
    
    async def _stats():
        explorer = FDAExplorer(ctx.obj['config'])
        
        try:
            stats = await explorer.get_summary_statistics()
            
            # Display statistics
            table = Table(title="Enhanced FDA Explorer Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Total Endpoints", str(stats["total_endpoints"]))
            table.add_row("Available Endpoints", ", ".join(stats["endpoints"]))
            table.add_row("API Status", stats["api_status"])
            table.add_row("Last Updated", stats["last_updated"])
            
            console.print(table)
            
        finally:
            explorer.close()
    
    asyncio.run(_stats())


@cli.command()
@click.option('--host', default='0.0.0.0', help='Server host')
@click.option('--port', default=8000, help='Server port')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
@click.pass_context
def serve(ctx, host, port, reload):
    """Start the API server"""
    import uvicorn
    from .api import create_app
    
    # Update configuration
    ctx.obj['config'].api.host = host
    ctx.obj['config'].api.port = port
    ctx.obj['config'].api.debug = reload
    
    console.print(f"[green]Starting Enhanced FDA Explorer API server on {host}:{port}[/green]")
    
    uvicorn.run(
        "enhanced_fda_explorer.api:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True
    )


@cli.command()
@click.option('--host', default='0.0.0.0', help='Server host')
@click.option('--port', default=8501, help='Server port')
@click.pass_context
def web(ctx, host, port):
    """Start the web interface"""
    import subprocess
    import sys
    
    # Update configuration
    ctx.obj['config'].webui.host = host
    ctx.obj['config'].webui.port = port
    
    console.print(f"[green]Starting Enhanced FDA Explorer web interface on {host}:{port}[/green]")
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            "enhanced_fda_explorer/web.py",
            "--server.address", host,
            "--server.port", str(port)
        ])
    except KeyboardInterrupt:
        console.print("\n[yellow]Web interface stopped[/yellow]")


def _display_search_results(response, format_type, output_file):
    """Display search results"""
    if format_type == 'json':
        results = {
            "query": response.query,
            "query_type": response.query_type,
            "total_results": response.total_results,
            "response_time": response.response_time,
            "results": {k: v.to_dict('records') for k, v in response.results.items()},
            "ai_analysis": response.ai_analysis
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
        else:
            console.print(JSON.from_data(results))
    
    elif format_type == 'table':
        # Display summary table
        table = Table(title=f"Search Results for '{response.query}'")
        table.add_column("Endpoint", style="cyan")
        table.add_column("Records", style="green")
        table.add_column("Date Range", style="yellow")
        
        for endpoint, df in response.results.items():
            if not df.empty:
                date_range = "N/A"
                # Try to get date range from DataFrame
                date_cols = [col for col in df.columns if 'date' in col.lower()]
                if date_cols:
                    try:
                        dates = pd.to_datetime(df[date_cols[0]], errors='coerce')
                        valid_dates = dates.dropna()
                        if len(valid_dates) > 0:
                            date_range = f"{valid_dates.min().strftime('%Y-%m-%d')} to {valid_dates.max().strftime('%Y-%m-%d')}"
                    except:
                        pass
                
                table.add_row(endpoint, str(len(df)), date_range)
        
        console.print(table)
        
        # Display AI analysis if available
        if response.ai_analysis:
            console.print("\n")
            console.print(Panel(
                response.ai_analysis.get('summary', 'No summary available'),
                title="AI Analysis Summary",
                border_style="blue"
            ))


def _display_device_intelligence(intelligence, format_type, output_file):
    """Display device intelligence"""
    if format_type == 'json':
        # Convert DataFrames to dict for JSON serialization
        serialized = intelligence.copy()
        serialized["data"] = {k: v.to_dict('records') for k, v in intelligence["data"].items()}
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(serialized, f, indent=2, default=str)
        else:
            console.print(JSON.from_data(serialized))
    
    else:
        # Display summary
        console.print(f"\n[bold green]Device Intelligence Report: {intelligence['device_name']}[/bold green]")
        
        # Data summary
        table = Table(title="Data Summary")
        table.add_column("Source", style="cyan")
        table.add_column("Records", style="green")
        
        for source, df in intelligence["data"].items():
            table.add_row(source, str(len(df)))
        
        console.print(table)
        
        # Risk assessment if available
        if intelligence.get("risk_assessment"):
            risk = intelligence["risk_assessment"]
            console.print("\n")
            console.print(Panel(
                f"Risk Score: {risk.overall_risk_score}/10\n"
                f"Severity: {risk.severity_level}\n"
                f"Confidence: {risk.confidence_score:.2f}",
                title="Risk Assessment",
                border_style="red" if risk.severity_level in ["HIGH", "CRITICAL"] else "yellow"
            ))


def _display_device_comparison(comparison, format_type, output_file):
    """Display device comparison"""
    if format_type == 'json':
        # Serialize for JSON
        serialized = comparison.copy()
        serialized_device_data = {}
        
        for device_name, device_info in comparison["device_data"].items():
            serialized_data = {k: v.to_dict('records') for k, v in device_info["data"].items()}
            serialized_device_data[device_name] = {
                **device_info,
                "data": serialized_data
            }
        
        serialized["device_data"] = serialized_device_data
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(serialized, f, indent=2, default=str)
        else:
            console.print(JSON.from_data(serialized))
    
    else:
        # Display comparison summary
        console.print(f"\n[bold green]Device Comparison: {', '.join(comparison['devices'])}[/bold green]")
        
        # Create comparison table
        table = Table(title="Device Comparison Summary")
        table.add_column("Device", style="cyan")
        table.add_column("Total Records", style="green")
        table.add_column("Risk Score", style="red")
        
        for device_name, device_info in comparison["device_data"].items():
            total_records = sum(len(df) for df in device_info["data"].values())
            risk_score = device_info.get("risk_assessment", {}).get("overall_risk_score", "N/A")
            
            table.add_row(device_name, str(total_records), str(risk_score))
        
        console.print(table)


def _display_manufacturer_intelligence(intelligence, format_type, output_file):
    """Display manufacturer intelligence"""
    if format_type == 'json':
        # Serialize for JSON
        serialized = intelligence.copy()
        serialized["search_response"]["results"] = {
            k: v.to_dict('records') for k, v in intelligence["search_response"]["results"].items()
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(serialized, f, indent=2, default=str)
        else:
            console.print(JSON.from_data(serialized))
    
    else:
        # Display summary
        console.print(f"\n[bold green]Manufacturer Intelligence: {intelligence['manufacturer_name']}[/bold green]")
        
        # Display search results summary
        response = intelligence["search_response"]
        table = Table(title="Data Summary")
        table.add_column("Source", style="cyan")
        table.add_column("Records", style="green")
        
        for source, df in response.results.items():
            table.add_row(source, str(len(df)))
        
        console.print(table)


def _display_trend_analysis(trend_analysis, format_type, output_file):
    """Display trend analysis"""
    if format_type == 'json':
        # Serialize for JSON
        serialized = trend_analysis.copy()
        serialized_trend_data = {}
        
        for period, data in trend_analysis["trend_data"].items():
            serialized_data = {k: v.to_dict('records') for k, v in data.items()}
            serialized_trend_data[period] = serialized_data
        
        serialized["trend_data"] = serialized_trend_data
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(serialized, f, indent=2, default=str)
        else:
            console.print(JSON.from_data(serialized))
    
    else:
        # Display trends summary
        console.print(f"\n[bold green]Trend Analysis: {trend_analysis['query']}[/bold green]")
        
        # Display trends table
        table = Table(title="Trend Summary")
        table.add_column("Time Period", style="cyan")
        table.add_column("Total Records", style="green")
        
        for period, data in trend_analysis["trend_data"].items():
            total_records = sum(len(df) for df in data.values())
            table.add_row(period, str(total_records))
        
        console.print(table)


def main():
    """Main entry point"""
    cli()


if __name__ == "__main__":
    main()