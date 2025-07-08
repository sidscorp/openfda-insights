#!/usr/bin/env python3
"""
Task Management CLI for Enhanced FDA Explorer
Manages tasks in tasks.yaml for agentic workflows
"""
import click
import yaml
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class TaskManager:
    def __init__(self, tasks_file: str = "tasks.yaml"):
        self.tasks_file = Path(tasks_file)
        self.data = self.load_tasks()
    
    def load_tasks(self) -> Dict:
        """Load tasks from YAML file"""
        if not self.tasks_file.exists():
            return {"metadata": {}, "tasks": []}
        
        with open(self.tasks_file, 'r') as f:
            return yaml.safe_load(f) or {"metadata": {}, "tasks": []}
    
    def save_tasks(self):
        """Save tasks to YAML file"""
        # Update metadata
        if "metadata" not in self.data:
            self.data["metadata"] = {}
        
        self.data["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        
        with open(self.tasks_file, 'w') as f:
            yaml.dump(self.data, f, default_flow_style=False, sort_keys=False)
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get a task by ID"""
        for task in self.data.get("tasks", []):
            if task["id"] == task_id:
                return task
        return None
    
    def list_tasks(self, status: Optional[str] = None, priority: Optional[str] = None) -> List[Dict]:
        """List tasks with optional filtering"""
        tasks = self.data.get("tasks", [])
        
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        
        if priority:
            tasks = [t for t in tasks if t.get("priority") == priority]
        
        return tasks
    
    def update_task_status(self, task_id: str, status: str) -> bool:
        """Update task status"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        task["status"] = status
        self.save_tasks()
        return True
    
    def add_task(self, task_data: Dict) -> bool:
        """Add a new task"""
        if "tasks" not in self.data:
            self.data["tasks"] = []
        
        # Validate required fields
        required_fields = ["id", "title", "status", "priority"]
        for field in required_fields:
            if field not in task_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Check for duplicate ID
        if self.get_task(task_data["id"]):
            raise ValueError(f"Task ID {task_data['id']} already exists")
        
        self.data["tasks"].append(task_data)
        self.save_tasks()
        return True


@click.group()
@click.option('--tasks-file', default='tasks.yaml', help='Path to tasks.yaml file')
@click.pass_context
def cli(ctx, tasks_file):
    """Enhanced FDA Explorer Task Management CLI"""
    ctx.ensure_object(dict)
    ctx.obj['manager'] = TaskManager(tasks_file)


@cli.command()
@click.option('--status', help='Filter by status (todo, in_progress, completed, blocked)')
@click.option('--priority', help='Filter by priority (P1, P2, P3)')
@click.option('--format', 'output_format', default='table', type=click.Choice(['table', 'json', 'yaml']), help='Output format')
@click.pass_context
def list(ctx, status, priority, output_format):
    """List tasks"""
    manager = ctx.obj['manager']
    tasks = manager.list_tasks(status=status, priority=priority)
    
    if output_format == 'json':
        import json
        click.echo(json.dumps(tasks, indent=2))
        return
    elif output_format == 'yaml':
        click.echo(yaml.dump(tasks, default_flow_style=False))
        return
    
    # Table format
    if not tasks:
        click.echo("No tasks found.")
        return
    
    click.echo(f"{'ID':<12} {'Priority':<8} {'Status':<12} {'Title'}")
    click.echo("-" * 80)
    
    for task in tasks:
        status_color = {
            'todo': 'white',
            'in_progress': 'yellow',
            'completed': 'green',
            'blocked': 'red'
        }.get(task.get('status', 'todo'), 'white')
        
        click.echo(
            f"{task['id']:<12} "
            f"{task.get('priority', 'N/A'):<8} "
            f"{click.style(task.get('status', 'todo'):<12, fg=status_color)} "
            f"{task['title']}"
        )


@cli.command()
@click.argument('task_id')
@click.pass_context
def show(ctx, task_id):
    """Show detailed task information"""
    manager = ctx.obj['manager']
    task = manager.get_task(task_id)
    
    if not task:
        click.echo(f"Task {task_id} not found.", err=True)
        sys.exit(1)
    
    click.echo(f"ID: {task['id']}")
    click.echo(f"Title: {task['title']}")
    click.echo(f"Status: {click.style(task.get('status', 'todo'), fg='yellow')}")
    click.echo(f"Priority: {task.get('priority', 'N/A')}")
    click.echo(f"Category: {task.get('category', 'N/A')}")
    click.echo(f"Estimate: {task.get('estimate', 'N/A')}")
    
    if task.get('description'):
        click.echo(f"\nDescription:\n{task['description']}")
    
    if task.get('labels'):
        click.echo(f"\nLabels: {', '.join(task['labels'])}")
    
    if task.get('files'):
        click.echo(f"\nFiles: {', '.join(task['files'])}")


@cli.command()
@click.argument('task_id')
@click.argument('status', type=click.Choice(['todo', 'in_progress', 'completed', 'blocked', 'cancelled']))
@click.pass_context
def update(ctx, task_id, status):
    """Update task status"""
    manager = ctx.obj['manager']
    
    if manager.update_task_status(task_id, status):
        click.echo(f"✅ Updated {task_id} status to {status}")
    else:
        click.echo(f"❌ Task {task_id} not found.", err=True)
        sys.exit(1)


@cli.command()
@click.option('--id', 'task_id', required=True, help='Task ID')
@click.option('--title', required=True, help='Task title')
@click.option('--description', help='Task description')
@click.option('--status', default='todo', type=click.Choice(['todo', 'in_progress', 'completed', 'blocked']), help='Task status')
@click.option('--priority', default='P2', type=click.Choice(['P1', 'P2', 'P3']), help='Task priority')
@click.option('--category', help='Task category')
@click.option('--estimate', help='Time estimate')
@click.option('--labels', help='Comma-separated labels')
@click.option('--files', help='Comma-separated file paths')
@click.pass_context
def add(ctx, task_id, title, description, status, priority, category, estimate, labels, files):
    """Add a new task"""
    manager = ctx.obj['manager']
    
    task_data = {
        "id": task_id,
        "title": title,
        "status": status,
        "priority": priority
    }
    
    if description:
        task_data["description"] = description
    if category:
        task_data["category"] = category
    if estimate:
        task_data["estimate"] = estimate
    if labels:
        task_data["labels"] = [label.strip() for label in labels.split(',')]
    if files:
        task_data["files"] = [file.strip() for file in files.split(',')]
    
    try:
        manager.add_task(task_data)
        click.echo(f"✅ Added task {task_id}")
    except ValueError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def stats(ctx):
    """Show task statistics"""
    manager = ctx.obj['manager']
    tasks = manager.list_tasks()
    
    if not tasks:
        click.echo("No tasks found.")
        return
    
    # Status counts
    status_counts = {}
    priority_counts = {}
    category_counts = {}
    
    for task in tasks:
        status = task.get('status', 'todo')
        priority = task.get('priority', 'Unknown')
        category = task.get('category', 'Unknown')
        
        status_counts[status] = status_counts.get(status, 0) + 1
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1
    
    click.echo(f"Total tasks: {len(tasks)}")
    click.echo("\nBy Status:")
    for status, count in sorted(status_counts.items()):
        click.echo(f"  {status}: {count}")
    
    click.echo("\nBy Priority:")
    for priority, count in sorted(priority_counts.items()):
        click.echo(f"  {priority}: {count}")
    
    click.echo("\nBy Category:")
    for category, count in sorted(category_counts.items()):
        if category != 'Unknown':
            click.echo(f"  {category}: {count}")


@cli.command()
@click.option('--priority', type=click.Choice(['P1', 'P2', 'P3']), help='Filter by priority')
@click.option('--limit', default=10, help='Limit number of suggestions')
@click.pass_context
def suggest(ctx, priority, limit):
    """Suggest next tasks to work on"""
    manager = ctx.obj['manager']
    
    # Get todo tasks
    todo_tasks = manager.list_tasks(status='todo')
    
    if priority:
        todo_tasks = [t for t in todo_tasks if t.get('priority') == priority]
    
    # Sort by priority (P1 first) and then by order in file
    priority_order = {'P1': 1, 'P2': 2, 'P3': 3}
    todo_tasks.sort(key=lambda t: priority_order.get(t.get('priority', 'P3'), 4))
    
    suggested = todo_tasks[:limit]
    
    if not suggested:
        click.echo("No tasks to suggest.")
        return
    
    click.echo("Suggested next tasks:")
    for i, task in enumerate(suggested, 1):
        priority_color = {'P1': 'red', 'P2': 'yellow', 'P3': 'green'}.get(task.get('priority'), 'white')
        click.echo(
            f"{i}. {click.style(task['id'], fg='cyan')} "
            f"[{click.style(task.get('priority', 'P3'), fg=priority_color)}] "
            f"{task['title']}"
        )


if __name__ == '__main__':
    cli()