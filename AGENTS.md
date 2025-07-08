# AGENTS - Agent Workflow and CEO Approval Guide

This repository uses an agentic workflow under CEO oversight. Any automated agent (Codex CLI, CI bots, or human collaborators) must follow these rules:

1. **Read the Task Board**
   - Inspect `tasks.yaml` for pending tasks.  Always work from the highest-priority `todo` tasks.

2. **Pick and Lock a Task**
   - Before coding, update the task status to `in_progress`:
     ```bash
     python scripts/manage_tasks.py update <TASK_ID> in_progress
     ```

3. **Implement Exactly to Task**
   - Follow the task's `description`, `files`, and `estimate`.  Do not add unrelated changes.

4. **Run Tests and Lint**
   - Ensure new code passes existing tests and linters:
     ```bash
     pytest --maxfail=1 --disable-warnings -q
     pre-commit run --all-files
     ```

5. **Commit with Review Sign-off**
   - Use a Conventional Commit including the task ID and a CEO review header.  Example:
     ```text
     feat(P1-T010): scaffold orchestration module

     Reviewed-by: Claude <noreply@anthropic.com>
     ```
   - Commits without a `Reviewed-by:` header will be rejected by the pre-commit hook.

6. **Mark Task as Completed**
   - After merge, update the task status to `completed`:
     ```bash
     python scripts/manage_tasks.py update <TASK_ID> completed
     ```

7. **CEO Approval Required**
   - No code or documentation changes may be merged without the `Reviewed-by:` sign-off from the CEO agent.

8. **Codex CLI Integration**
   - By default, `codex` will load this `AGENTS.md` along with the repository context.  To skip, use `--no-project-doc`.

---
_End of agent workflow guide_