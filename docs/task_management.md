# Task Management

Enhanced FDA Explorer uses a centralized task management system designed for both human and agentic workflows. This system provides a single source of truth for all development activities through a machine-readable `tasks.yaml` file.

## Overview

The task management system consists of:

- **`tasks.yaml`**: Machine-readable task list at the project root
- **`scripts/manage_tasks.py`**: CLI utility for task management
- **Conventional commits**: Linking commits to specific tasks
- **Pre-commit hooks**: Automated task reference validation

## Task Structure

Each task in `tasks.yaml` follows this structure:

```yaml
- id: P1-T001
  title: "Add Pydantic BaseSettings for config validation"
  description: "Enforce schema validation for all environment variables"
  status: todo
  priority: P1
  category: config
  labels: [config, validation, pydantic]
  estimate: "3 days"
  files: ["src/enhanced_fda_explorer/config.py"]
```

### Fields

- **`id`**: Unique task identifier (format: `P{priority}-T{number}`)
- **`title`**: Brief, descriptive task title
- **`description`**: Detailed task description
- **`status`**: Current status (`todo`, `in_progress`, `completed`, `blocked`, `cancelled`)
- **`priority`**: Priority level (`P1`, `P2`, `P3`)
- **`category`**: Task category (e.g., `config`, `testing`, `documentation`)
- **`labels`**: Array of descriptive labels
- **`estimate`**: Time estimate for completion
- **`files`**: Array of files this task affects

## Using the Task Management CLI

The `scripts/manage_tasks.py` script provides a comprehensive CLI for task management:

### List Tasks

```bash
# List all tasks
python scripts/manage_tasks.py list

# Filter by status
python scripts/manage_tasks.py list --status todo

# Filter by priority
python scripts/manage_tasks.py list --priority P1

# JSON output
python scripts/manage_tasks.py list --format json
```

### Show Task Details

```bash
python scripts/manage_tasks.py show P1-T001
```

### Update Task Status

```bash
# Mark task as in progress
python scripts/manage_tasks.py update P1-T001 in_progress

# Mark task as completed
python scripts/manage_tasks.py update P1-T001 completed
```

### Add New Tasks

```bash
python scripts/manage_tasks.py add \
  --id P2-T010 \
  --title "Add new feature" \
  --description "Detailed description" \
  --priority P2 \
  --category feature \
  --labels "api,enhancement" \
  --estimate "2 days"
```

### Task Statistics

```bash
python scripts/manage_tasks.py stats
```

### Get Task Suggestions

```bash
# Suggest next tasks to work on
python scripts/manage_tasks.py suggest

# Filter by priority
python scripts/manage_tasks.py suggest --priority P1
```

## Commit Message Integration

All commits should reference a task ID using conventional commit format:

```
feat(P1-T001): add Pydantic BaseSettings for config validation

Implement schema validation for environment variables and config keys.
Validates presence and format at startup.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Commit Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes
- **refactor**: Code refactoring
- **test**: Adding or updating tests
- **chore**: Maintenance tasks
- **ci**: CI/CD changes

## Agentic Workflow Integration

The task management system is designed to work seamlessly with LLM agents:

### For Agents

1. **Read `tasks.yaml`** to understand current work
2. **Pick a task** from `todo` status
3. **Update status** to `in_progress` before starting
4. **Complete the work** according to task requirements
5. **Commit changes** with proper task reference
6. **Update status** to `completed` when done

### Example Agent Workflow

```python
# Pseudo-code for agent workflow
task_manager = TaskManager()

# Get next task
todo_tasks = task_manager.list_tasks(status='todo', priority='P1')
task = todo_tasks[0] if todo_tasks else None

if task:
    # Start working on task
    task_manager.update_task_status(task['id'], 'in_progress')
    
    # Do the work...
    implement_feature(task)
    
    # Commit with task reference
    git_commit(f"feat({task['id']}): {task['title']}")
    
    # Mark as completed
    task_manager.update_task_status(task['id'], 'completed')
```

## Priority Levels

### P1 (High Priority)
- Core functionality issues
- Security vulnerabilities
- Critical bugs
- Blocking issues

### P2 (Medium Priority)
- Important enhancements
- Performance improvements
- Non-critical bugs
- Feature additions

### P3 (Low Priority)
- Nice-to-have features
- Documentation improvements
- Code cleanup
- Future enhancements

## Task Categories

- **config**: Configuration and settings
- **testing**: Test coverage and quality
- **performance**: Performance optimization
- **security**: Security improvements
- **documentation**: Documentation updates
- **ux**: User experience improvements
- **monitoring**: Logging and observability
- **ci**: Continuous integration
- **api**: API changes
- **orchestrator**: Conversational intent-to-API orchestration (Phase 1)
- **ui**: User interface changes

## Integration with GitHub

The task system integrates with GitHub through:

- **Issue templates** that reference task IDs
- **PR templates** that require task linking
- **CI workflows** that validate task references
- **Milestone tracking** aligned with priorities

## Best Practices

### For Humans

1. Always reference a task ID in commit messages
2. Keep task descriptions clear and actionable
3. Update task status regularly
4. Break large tasks into smaller, manageable pieces
5. Use descriptive labels for better organization

### For Agents

1. Always check task status before starting work
2. Update status to `in_progress` immediately when starting
3. Follow task requirements exactly
4. Include proper commit message formatting
5. Mark tasks as `completed` only when fully done

### Task Creation

1. Use descriptive, action-oriented titles
2. Include clear acceptance criteria
3. Estimate time realistically
4. Tag with relevant labels
5. Link to affected files when possible

## Monitoring and Reporting

Use the CLI tools to monitor progress:

```bash
# Daily standup report
python scripts/manage_tasks.py stats
python scripts/manage_tasks.py list --status in_progress

# Sprint planning
python scripts/manage_tasks.py suggest --priority P1

# Release planning
python scripts/manage_tasks.py list --priority P1 --status todo
```

This task management system ensures that both human developers and AI agents can work together effectively, maintaining clear visibility into project progress and priorities.