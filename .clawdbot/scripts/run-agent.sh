#!/usr/bin/env bash
# =============================================================================
# run-agent.sh — Execute an AI agent with logging and status tracking
# =============================================================================
# Called by spawn-agent.sh inside a tmux session. Do not call directly.
#
# Arguments:
#   $1  task-id
#   $2  agent-type (claude | codex)
#   $3  model
#   $4  prompt-file path
#   $5  log-file path
#   $6  tasks-file path

set -uo pipefail

TASK_ID="$1"
AGENT_TYPE="$2"
MODEL="$3"
PROMPT_FILE="$4"
LOG_FILE="$5"
TASKS_FILE="$6"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# -- Helper: update task status in registry --
update_task_status() {
  local status="$1"
  local note="${2:-}"

  if [ -f "$TASKS_FILE" ] && command -v jq >/dev/null 2>&1; then
    jq --arg id "$TASK_ID" --arg status "$status" --arg note "$note" \
      '(.tasks[] | select(.id == $id)) |= (
        .status = $status |
        if $note != "" then .note = $note else . end |
        if $status == "done" or $status == "failed" then .completedAt = now else . end
      )' "$TASKS_FILE" > "${TASKS_FILE}.tmp" 2>/dev/null && \
      mv "${TASKS_FILE}.tmp" "$TASKS_FILE"
  fi
}

# -- Helper: check if PR was created --
check_pr_created() {
  if command -v gh >/dev/null 2>&1; then
    local branch
    branch=$(jq -r --arg id "$TASK_ID" '.tasks[] | select(.id == $id) | .branch' "$TASKS_FILE" 2>/dev/null)
    if [ -n "$branch" ]; then
      local pr_number
      pr_number=$(gh pr list --head "$branch" --json number --jq '.[0].number' 2>/dev/null)
      if [ -n "$pr_number" ] && [ "$pr_number" != "null" ]; then
        jq --arg id "$TASK_ID" --argjson pr "$pr_number" \
          '(.tasks[] | select(.id == $id)) |= (.pr = $pr | .checks.prCreated = true)' \
          "$TASKS_FILE" > "${TASKS_FILE}.tmp" 2>/dev/null && \
          mv "${TASKS_FILE}.tmp" "$TASKS_FILE"
        return 0
      fi
    fi
  fi
  return 1
}

# -- Start --
echo "=== Agent Runner ===" | tee "$LOG_FILE"
echo "Task:  $TASK_ID" | tee -a "$LOG_FILE"
echo "Agent: $AGENT_TYPE ($MODEL)" | tee -a "$LOG_FILE"
echo "Time:  $(date)" | tee -a "$LOG_FILE"
echo "---" | tee -a "$LOG_FILE"

PROMPT_CONTENT="$(cat "$PROMPT_FILE")"

# -- Execute agent --
EXIT_CODE=0
case "$AGENT_TYPE" in
  claude)
    echo "[$(date '+%H:%M:%S')] Starting Claude Code agent..." | tee -a "$LOG_FILE"
    claude --model "$MODEL" \
      --dangerously-skip-permissions \
      -p "$PROMPT_CONTENT" 2>&1 | tee -a "$LOG_FILE"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;
  codex)
    echo "[$(date '+%H:%M:%S')] Starting Codex agent..." | tee -a "$LOG_FILE"
    codex --model "$MODEL" \
      --full-auto \
      "$PROMPT_CONTENT" 2>&1 | tee -a "$LOG_FILE"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;
  *)
    echo "Error: Unknown agent type '$AGENT_TYPE'" | tee -a "$LOG_FILE"
    update_task_status "failed" "Unknown agent type"
    exit 1
    ;;
esac

echo "" | tee -a "$LOG_FILE"
echo "---" | tee -a "$LOG_FILE"
echo "[$(date '+%H:%M:%S')] Agent exited with code: $EXIT_CODE" | tee -a "$LOG_FILE"

# -- Post-execution checks --
if [ $EXIT_CODE -eq 0 ]; then
  # Check if the agent created the done marker
  if [ -f ".clawdbot-done" ]; then
    echo "[$(date '+%H:%M:%S')] Agent marked task as done." | tee -a "$LOG_FILE"
    rm -f ".clawdbot-done"
  fi

  # Check for PR
  if check_pr_created; then
    echo "[$(date '+%H:%M:%S')] PR created successfully." | tee -a "$LOG_FILE"
  fi

  update_task_status "done" "Agent completed successfully"
  echo "[$(date '+%H:%M:%S')] Task status: DONE" | tee -a "$LOG_FILE"
else
  update_task_status "failed" "Agent exited with code $EXIT_CODE"
  echo "[$(date '+%H:%M:%S')] Task status: FAILED" | tee -a "$LOG_FILE"
fi

echo ""
echo "=== Agent session ended. Press Enter or Ctrl+D to close. ==="
