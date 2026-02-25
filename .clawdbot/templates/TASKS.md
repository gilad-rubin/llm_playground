# Task List (Ralph Loop Template)

Use this template with the Ralph Loop to work through tasks iteratively.
Each iteration, the agent picks the next `[ ]` task, implements it, tests it,
and marks it `[x]` complete.

## Tasks

- [ ] Task 1: Description of first task
- [ ] Task 2: Description of second task
- [ ] Task 3: Description of third task

## Notes

- One task per iteration keeps context focused
- Tests must pass before marking complete
- When all tasks are done, create a `DONE` file

## Example Usage

```bash
# Copy this template
cp .clawdbot/templates/TASKS.md ./TASKS.md

# Edit with your actual tasks
vim TASKS.md

# Run the Ralph Loop
python .clawdbot/orchestrator.py ralph TASKS.md --agent=claude --max-iterations=10
```
