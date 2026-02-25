#!/usr/bin/env bash
# =============================================================================
# ralph-loop.sh — The Ralph Loop: iterative agent execution with fresh context
# =============================================================================
# Named after the pattern by Geoffrey Huntley. Each iteration spawns a fresh
# agent (no context rot), reads tasks from a file, and works on the next one.
#
# Usage:
#   ./ralph-loop.sh [task-file] [max-iterations] [agent]
#
# Examples:
#   ./ralph-loop.sh TASKS.md 10 claude
#   ./ralph-loop.sh TASKS.md 5 codex
#
# The task file should use markdown checkboxes:
#   - [ ] Incomplete task
#   - [x] Completed task

set -uo pipefail

TASK_FILE="${1:-TASKS.md}"
MAX_ITERATIONS="${2:-10}"
AGENT="${3:-claude}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAWDBOT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$CLAWDBOT_DIR/.." && pwd)"
LOG_DIR="$CLAWDBOT_DIR/logs"

mkdir -p "$LOG_DIR"

# Resolve task file path
if [ ! -f "$TASK_FILE" ]; then
  TASK_FILE="$REPO_ROOT/$TASK_FILE"
fi
if [ ! -f "$TASK_FILE" ]; then
  echo "Error: Task file not found: $1"
  echo "Create one with: cp .openclaw/templates/TASKS.md ./TASKS.md"
  exit 1
fi

# Model defaults
case "$AGENT" in
  claude) MODEL="claude-sonnet-4-20250514" ;;
  codex)  MODEL="o4-mini" ;;
  *)      MODEL="$AGENT" ;;
esac

echo "============================================"
echo "  Ralph Loop"
echo "============================================"
echo "  Task file:      $TASK_FILE"
echo "  Agent:          $AGENT ($MODEL)"
echo "  Max iterations: $MAX_ITERATIONS"
echo "============================================"
echo ""

cd "$REPO_ROOT"

for i in $(seq 1 "$MAX_ITERATIONS"); do
  echo ""
  echo "=== Iteration $i / $MAX_ITERATIONS ==="
  echo "Time: $(date)"

  # Check for completion
  if [ -f "DONE" ]; then
    echo "DONE marker found! All tasks completed after $((i - 1)) iterations."
    rm -f "DONE"
    exit 0
  fi

  # Count remaining tasks
  REMAINING=$(grep -c '^\s*-\s*\[ \]' "$TASK_FILE" 2>/dev/null || echo "0")
  COMPLETED=$(grep -c '^\s*-\s*\[x\]' "$TASK_FILE" 2>/dev/null || echo "0")
  echo "Tasks: $COMPLETED completed, $REMAINING remaining"

  if [ "$REMAINING" -eq 0 ]; then
    echo "No remaining tasks found in $TASK_FILE."
    echo "All done!"
    exit 0
  fi

  # Build prompt for this iteration
  PROMPT="You are working through a task list in '$TASK_FILE'.

Instructions:
1. Read '$TASK_FILE' to find the next incomplete task (marked with [ ])
2. Implement ONLY that single task — do not skip ahead
3. Run any available tests (pytest, npm test, etc.)
4. If tests pass, mark the task as complete (change [ ] to [x]) in '$TASK_FILE'
5. Commit your changes with a descriptive message
6. If ALL tasks in the file are now complete, create a file called 'DONE'

Be thorough but focused. One task per iteration."

  LOG_FILE="$LOG_DIR/ralph-iter-${i}.log"

  # Run the agent with fresh context
  case "$AGENT" in
    claude*)
      claude --model "$MODEL" \
        --dangerously-skip-permissions \
        -p "$PROMPT" 2>&1 | tee "$LOG_FILE"
      EXIT_CODE=${PIPESTATUS[0]}
      ;;
    codex*)
      codex --model "$MODEL" \
        --full-auto \
        "$PROMPT" 2>&1 | tee "$LOG_FILE"
      EXIT_CODE=${PIPESTATUS[0]}
      ;;
    *)
      echo "Unknown agent: $AGENT"
      exit 1
      ;;
  esac

  echo ""
  echo "Agent exited with code: $EXIT_CODE"

  if [ $EXIT_CODE -ne 0 ]; then
    echo "Agent failed. Continuing with fresh context on next iteration..."
  fi

  # Brief pause to avoid rate limiting
  sleep 2
done

echo ""
echo "Reached max iterations ($MAX_ITERATIONS) without completing all tasks."
echo "Remaining tasks:"
grep '^\s*-\s*\[ \]' "$TASK_FILE" 2>/dev/null || echo "  (none found)"
echo ""
echo "Run again with: $0 $TASK_FILE $MAX_ITERATIONS $AGENT"
exit 1
