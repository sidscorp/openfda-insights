#!/usr/bin/env python3
"""
Command-line interface for testing the multi-agent FDA system
"""

import asyncio
import sys
import os
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich import print as rprint
import click
from dotenv import load_dotenv
import logging
import json

# Add src to path
sys.path.insert(0, 'src')

from enhanced_fda_explorer.agents_v2 import FDAMultiAgentOrchestrator

# Load environment variables
load_dotenv()

console = Console()


class AgentCLI:
    """CLI for interacting with FDA agents"""
    
    def __init__(self, debug=False):
        self.debug = debug
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            console.print("[yellow]Debug mode enabled[/yellow]")
        self.orchestrator = FDAMultiAgentOrchestrator()
        
    async def process_with_progress(self, query: str):
        """Process query with progress indicator"""
        progress_messages = []
        
        async def progress_callback(percentage: int, message: str):
            progress_messages.append((percentage, message))
            
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing query...", total=100)
            
            # Start the query processing
            result_future = asyncio.create_task(
                self.orchestrator.process_query(query, progress_callback)
            )
            
            # Update progress bar
            last_percentage = 0
            while not result_future.done():
                # Check for new progress messages
                for percentage, message in progress_messages:
                    if percentage > last_percentage:
                        progress.update(task, completed=percentage, description=message)
                        last_percentage = percentage
                
                await asyncio.sleep(0.1)
            
            # Get the result
            result = await result_future
            progress.update(task, completed=100, description="✅ Complete!")
            
        return result
    
    def display_results(self, result: dict):
        """Display results in a formatted way"""
        if not result.get("success"):
            console.print(f"[red]Error: {result.get('error', 'Unknown error')}[/red]")
            return
            
        # Display intent analysis
        intent = result.get("intent", {})
        console.print("\n[bold cyan]Query Analysis:[/bold cyan]")
        intent_table = Table(show_header=False, box=None)
        intent_table.add_column("Field", style="bright_blue")
        intent_table.add_column("Value")
        
        intent_table.add_row("Primary Intent", intent.get("primary_intent", "N/A"))
        intent_table.add_row("Devices", ", ".join(intent.get("device_names", [])))
        intent_table.add_row("Time Range", intent.get("time_range", "Not specified"))
        intent_table.add_row("Agents Used", ", ".join(intent.get("required_agents", [])))
        
        console.print(intent_table)
        
        # Display agent findings
        agent_results = result.get("agent_results", {})
        if agent_results:
            console.print("\n[bold cyan]Agent Findings:[/bold cyan]")
            
            for agent_name, results in agent_results.items():
                console.print(f"\n[bold yellow]{agent_name}:[/bold yellow]")
                
                for agent_result in results:
                    if not isinstance(agent_result, dict):
                        console.print(f"  [red]Invalid result format: {type(agent_result)}[/red]")
                        if self.debug:
                            console.print(f"  [dim]Debug: {agent_result}[/dim]")
                        continue
                        
                    # Debug output
                    if self.debug:
                        console.print(f"  [dim]Debug - Keys: {list(agent_result.keys())}[/dim]")
                    
                    # Key findings
                    findings = agent_result.get("key_findings", [])
                    if findings and isinstance(findings, list):
                        console.print("  [green]Key Findings:[/green]")
                        for finding in findings[:3]:  # Show top 3
                            if isinstance(finding, dict):
                                console.print(f"    • {finding.get('finding', finding)}")
                            else:
                                console.print(f"    • {finding}")
                    elif not findings:
                        console.print("  [dim]No findings reported[/dim]")
                    
                    # Data citations
                    citations = agent_result.get("data_citations", [])
                    if citations and isinstance(citations, list):
                        console.print("  [blue]Data Sources:[/blue]")
                        for citation in citations[:3]:  # Show top 3
                            console.print(f"    📄 {citation}")
                    
                    # Data points
                    data_points = agent_result.get("data_points", 0)
                    console.print(f"  [dim]Data points analyzed: {data_points}[/dim]")
                    
                    # Search strategy (if available in raw data)
                    if self.debug and "raw_data" in agent_result:
                        raw_data = agent_result["raw_data"]
                        if "search_strategy" in raw_data and raw_data["search_strategy"]:
                            console.print(f"  [dim]Search strategy: {raw_data['search_strategy']}[/dim]")
                    
                    # Show raw data summary in debug
                    if self.debug and "raw_data" in agent_result:
                        raw = agent_result["raw_data"]
                        console.print(f"  [dim]Raw data - Total: {raw.get('total', 0)}[/dim]")
        
        # Display synthesis
        synthesis = result.get("synthesis", {})
        if synthesis and synthesis.get("narrative"):
            console.print("\n[bold cyan]Synthesized Analysis:[/bold cyan]")
            console.print(Panel(
                Markdown(synthesis["narrative"]),
                title="[bold]FDA Device Intelligence Report[/bold]",
                border_style="cyan"
            ))
    
    async def interactive_mode(self):
        """Run in interactive mode"""
        console.print("[bold green]FDA Multi-Agent Intelligence System[/bold green]")
        console.print("Type your queries about medical devices. Type 'exit' to quit.\n")
        
        while True:
            try:
                query = console.input("[bold cyan]Query>[/bold cyan] ").strip()
                
                if query.lower() in ['exit', 'quit', 'q']:
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                    
                if not query:
                    continue
                    
                # Process the query
                result = await self.process_with_progress(query)
                
                # Display results
                self.display_results(result)
                console.print("\n" + "="*80 + "\n")
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                if self.debug:
                    import traceback
                    console.print("[dim]" + traceback.format_exc() + "[/dim]")


@click.command()
@click.option('--query', '-q', help='Single query to process')
@click.option('--interactive', '-i', is_flag=True, help='Run in interactive mode')
@click.option('--debug', '-d', is_flag=True, help='Enable debug output')
def main(query: Optional[str], interactive: bool, debug: bool):
    """FDA Multi-Agent Intelligence System CLI"""
    
    # Check for API keys
    if not os.getenv("AI_API_KEY"):
        console.print("[red]Error: AI_API_KEY not found in environment[/red]")
        console.print("Please set your OpenRouter API key in .env file")
        return
        
    cli = AgentCLI(debug=debug)
    
    if interactive or not query:
        # Run interactive mode
        asyncio.run(cli.interactive_mode())
    else:
        # Process single query
        result = asyncio.run(cli.process_with_progress(query))
        cli.display_results(result)


if __name__ == "__main__":
    main()