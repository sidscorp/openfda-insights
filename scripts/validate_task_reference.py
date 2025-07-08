#!/usr/bin/env python3
"""
Validate that commit messages reference valid task IDs from tasks.yaml
"""
import sys
import re
import yaml
from pathlib import Path


def load_tasks():
    """Load tasks from tasks.yaml"""
    tasks_file = Path("tasks.yaml")
    if not tasks_file.exists():
        return set()
    
    with open(tasks_file, 'r') as f:
        data = yaml.safe_load(f)
    
    return {task['id'] for task in data.get('tasks', [])}


def validate_commit_message(commit_msg_file):
    """Validate commit message contains valid task reference"""
    with open(commit_msg_file, 'r') as f:
        commit_msg = f.read().strip()
    
    # Skip merge commits and other special commits
    if (commit_msg.startswith('Merge') or 
        commit_msg.startswith('Revert') or
        commit_msg.startswith('Initial commit')):
        return True
    
    # Extract task ID from commit message
    # Pattern: type(task-id): subject or type: subject [task-id]
    patterns = [
        r'^[a-z]+\(([A-Z0-9]+-[A-Z0-9]+)\):',  # feat(P1-T001): subject
        r'\[([A-Z0-9]+-[A-Z0-9]+)\]',          # subject [P1-T001]
        r'#([A-Z0-9]+-[A-Z0-9]+)',             # subject #P1-T001
    ]
    
    task_ids = load_tasks()
    
    for pattern in patterns:
        match = re.search(pattern, commit_msg)
        if match:
            task_id = match.group(1)
            if task_id in task_ids:
                return True
            else:
                print(f"❌ Invalid task ID '{task_id}' in commit message")
                print(f"   Valid task IDs: {sorted(task_ids)}")
                return False
    
    # Allow commits without task references for certain types
    no_task_patterns = [
        r'^(docs|style|chore|ci)(?:\([^)]+\))?: ',
        r'^Initial commit',
        r'^Merge ',
        r'^Revert ',
    ]
    
    for pattern in no_task_patterns:
        if re.match(pattern, commit_msg):
            return True
    
    print("❌ Commit message must reference a valid task ID")
    print("   Format: type(task-id): subject")
    print("   Example: feat(P1-T001): add config validation")
    print(f"   Valid task IDs: {sorted(task_ids)}")
    return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(1)
    
    commit_msg_file = sys.argv[1]
    if not validate_commit_message(commit_msg_file):
        sys.exit(1)