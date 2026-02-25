#!/usr/bin/env bash
# =============================================================================
# check-agents.sh — Monitor all running agents (cron-friendly)
# =============================================================================
# Checks tmux sessions, CI status, PR status, and respawns failed agents.
# Designed to run every 10 minutes via cron:
#   */10 * * * * /path/to/.clawdbot/scripts/check-agents.sh >> /path/to/.clawdbot/logs/monitor.log 2>&1
#
# This script is 100% deterministic — no LLM calls, pure shell logic.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAWDBOT_DIR="$(dirname "$SCRIPT_DIR")"
TASKS_FILE="$CLAWDBOT_DIR/active-tasks.json"
LOG_FILE="$CLAWDBOT_DIR/logs/monitor.log"
MAX_RETRIES=3

mkdir -p "$(dirname "$LOG_FILE")"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# -- Notification helpers --
notify_terminal() {
  local msg="$1"
  # Use wall if available, otherwise just log
  if command -v wall >/dev/null 2>&1; then
    echo "$msg" | wall 2>/dev/null || true
  fi
  log "NOTIFY: $msg"
}

notify_telegram() {
  local msg="$1"
  local token chat_id
  token=$(yq -r '.monitoring.telegram_bot_token // ""' "$CLAWDBOT_DIR/config.yaml" 2>/dev/null || echo "")
  chat_id=$(yq -r '.monitoring.telegram_chat_id // ""' "$CLAWDBOT_DIR/config.yaml" 2>/dev/null || echo "")
  if [ -n "$token" ] && [ -n "$chat_id" ]; then
    curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
      -d "chat_id=${chat_id}" -d "text=${msg}" -d "parse_mode=Markdown" >/dev/null 2>&1 || true
  fi
}

notify() {
  local msg="$1"
  notify_terminal "$msg"
  notify_telegram "$msg"
}

# -- Preflight --
if [ ! -f "$TASKS_FILE" ]; then
  log "No tasks file found. Nothing to check."
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  log "Error: jq is required but not installed."
  exit 1
fi

TASK_COUNT=$(jq '.tasks | length' "$TASKS_FILE")
if [ "$TASK_COUNT" -eq 0 ]; then
  log "No active tasks. All clear."
  exit 0
fi

log "=== Agent Health Check ==="
log "Checking $TASK_COUNT task(s)..."

NEEDS_ATTENTION=0
SUMMARY=""

# -- Check each task --
jq -c '.tasks[]' "$TASKS_FILE" | while IFS= read -r task; do
  TASK_ID=$(echo "$task" | jq -r '.id')
  TMUX_SESSION=$(echo "$task" | jq -r '.tmuxSession')
  STATUS=$(echo "$task" | jq -r '.status')
  BRANCH=$(echo "$task" | jq -r '.branch')
  AGENT_TYPE=$(echo "$task" | jq -r '.agent')
  RETRIES=$(echo "$task" | jq -r '.retries // 0')
  DESCRIPTION=$(echo "$task" | jq -r '.description')

  log "--- Task: $TASK_ID (status: $STATUS) ---"

  # Skip completed/merged tasks
  if [ "$STATUS" = "done" ] || [ "$STATUS" = "merged" ]; then
    log "  Skipping: already $STATUS"
    continue
  fi

  # 1. Check if tmux session is alive
  TMUX_ALIVE=false
  if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    TMUX_ALIVE=true
    log "  tmux session: ALIVE"
  else
    log "  tmux session: DEAD"
  fi

  # 2. Check for open PR on the branch
  PR_NUMBER=""
  PR_STATE=""
  if command -v gh >/dev/null 2>&1; then
    PR_NUMBER=$(gh pr list --head "$BRANCH" --json number,state --jq '.[0].number' 2>/dev/null || echo "")
    PR_STATE=$(gh pr list --head "$BRANCH" --json number,state --jq '.[0].state' 2>/dev/null || echo "")
  fi

  if [ -n "$PR_NUMBER" ] && [ "$PR_NUMBER" != "null" ]; then
    log "  PR #$PR_NUMBER: $PR_STATE"

    # Update task with PR info
    jq --arg id "$TASK_ID" --argjson pr "$PR_NUMBER" \
      '(.tasks[] | select(.id == $id)) |= (.pr = $pr | .checks.prCreated = true)' \
      "$TASKS_FILE" > "${TASKS_FILE}.tmp" && mv "${TASKS_FILE}.tmp" "$TASKS_FILE"

    # 3. Check CI status on the PR
    if command -v gh >/dev/null 2>&1; then
      CI_STATUS=$(gh pr checks "$PR_NUMBER" --json name,state --jq '[.[] | .state] | unique | join(",")' 2>/dev/null || echo "unknown")
      log "  CI status: $CI_STATUS"

      if echo "$CI_STATUS" | grep -q "SUCCESS"; then
        jq --arg id "$TASK_ID" \
          '(.tasks[] | select(.id == $id)) |= (.checks.ciPassed = true)' \
          "$TASKS_FILE" > "${TASKS_FILE}.tmp" && mv "${TASKS_FILE}.tmp" "$TASKS_FILE"
      fi

      if echo "$CI_STATUS" | grep -q "FAILURE"; then
        log "  WARNING: CI failed for $TASK_ID"
        jq --arg id "$TASK_ID" \
          '(.tasks[] | select(.id == $id)) |= (.checks.ciPassed = false)' \
          "$TASKS_FILE" > "${TASKS_FILE}.tmp" && mv "${TASKS_FILE}.tmp" "$TASKS_FILE"
      fi
    fi

    # 4. Check review status
    if command -v gh >/dev/null 2>&1; then
      REVIEW_STATE=$(gh pr view "$PR_NUMBER" --json reviewDecision --jq '.reviewDecision' 2>/dev/null || echo "")
      if [ "$REVIEW_STATE" = "APPROVED" ]; then
        log "  Reviews: APPROVED"
        jq --arg id "$TASK_ID" \
          '(.tasks[] | select(.id == $id)) |= (.checks.reviewPassed = true)' \
          "$TASKS_FILE" > "${TASKS_FILE}.tmp" && mv "${TASKS_FILE}.tmp" "$TASKS_FILE"
      fi
    fi

    # 5. Check if all checks passed -> ready to merge
    ALL_CHECKS=$(jq --arg id "$TASK_ID" \
      '.tasks[] | select(.id == $id) | .checks | (.prCreated and .ciPassed)' \
      "$TASKS_FILE" 2>/dev/null)

    if [ "$ALL_CHECKS" = "true" ]; then
      jq --arg id "$TASK_ID" \
        '(.tasks[] | select(.id == $id)) |= (.status = "ready_to_merge" | .note = "All checks passed. Ready to merge.")' \
        "$TASKS_FILE" > "${TASKS_FILE}.tmp" && mv "${TASKS_FILE}.tmp" "$TASKS_FILE"

      notify "PR #$PR_NUMBER ($TASK_ID) ready for review: $DESCRIPTION"
    fi
  fi

  # 6. Handle dead agents
  if [ "$TMUX_ALIVE" = "false" ] && [ "$STATUS" = "running" ]; then
    if [ "$RETRIES" -lt "$MAX_RETRIES" ]; then
      NEW_RETRIES=$((RETRIES + 1))
      log "  Respawning agent (attempt $NEW_RETRIES/$MAX_RETRIES)..."

      jq --arg id "$TASK_ID" --argjson retries "$NEW_RETRIES" \
        '(.tasks[] | select(.id == $id)) |= (.retries = $retries | .status = "respawning")' \
        "$TASKS_FILE" > "${TASKS_FILE}.tmp" && mv "${TASKS_FILE}.tmp" "$TASKS_FILE"

      # Respawn the agent
      WORKTREE=$(echo "$task" | jq -r '.worktree')
      MODEL=$(echo "$task" | jq -r '.model')
      PROMPT_FILE="$CLAWDBOT_DIR/logs/${TASK_ID}-prompt.txt"
      AGENT_LOG="$CLAWDBOT_DIR/logs/${TASK_ID}.log"

      if [ -f "$PROMPT_FILE" ] && [ -d "$WORKTREE" ]; then
        tmux new-session -d -s "$TMUX_SESSION" -c "$WORKTREE" \
          "bash $SCRIPT_DIR/run-agent.sh '$TASK_ID' '$AGENT_TYPE' '$MODEL' '$PROMPT_FILE' '$AGENT_LOG' '$TASKS_FILE'; bash"
        log "  Respawned successfully."
      else
        log "  Cannot respawn: missing prompt file or worktree."
        jq --arg id "$TASK_ID" \
          '(.tasks[] | select(.id == $id)) |= (.status = "failed" | .note = "Cannot respawn: missing files")' \
          "$TASKS_FILE" > "${TASKS_FILE}.tmp" && mv "${TASKS_FILE}.tmp" "$TASKS_FILE"
        notify "FAILED: Task $TASK_ID could not be respawned. Manual intervention needed."
      fi
    else
      log "  Max retries reached. Marking as failed."
      jq --arg id "$TASK_ID" \
        '(.tasks[] | select(.id == $id)) |= (.status = "failed" | .note = "Max retries exceeded")' \
        "$TASKS_FILE" > "${TASKS_FILE}.tmp" && mv "${TASKS_FILE}.tmp" "$TASKS_FILE"
      notify "FAILED: Task $TASK_ID exceeded max retries ($MAX_RETRIES). Needs human attention."
    fi
  fi
done

# -- Summary --
RUNNING=$(jq '[.tasks[] | select(.status == "running")] | length' "$TASKS_FILE")
DONE=$(jq '[.tasks[] | select(.status == "done")] | length' "$TASKS_FILE")
FAILED=$(jq '[.tasks[] | select(.status == "failed")] | length' "$TASKS_FILE")
READY=$(jq '[.tasks[] | select(.status == "ready_to_merge")] | length' "$TASKS_FILE")

log ""
log "=== Summary ==="
log "Running: $RUNNING | Done: $DONE | Ready to merge: $READY | Failed: $FAILED"
log "================"
