#!/usr/bin/env bash
# =============================================================================
# cleanup.sh — Clean up completed/merged agent worktrees and task registry
# =============================================================================
# Usage:
#   ./cleanup.sh              # clean up done/merged tasks
#   ./cleanup.sh --all        # clean up everything including failed tasks
#   ./cleanup.sh --dry-run    # show what would be cleaned without doing it
#
# Recommended: run daily via cron
#   0 3 * * * /path/to/.clawdbot/scripts/cleanup.sh >> /path/to/.clawdbot/logs/cleanup.log 2>&1

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAWDBOT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$CLAWDBOT_DIR/.." && pwd)"
TASKS_FILE="$CLAWDBOT_DIR/active-tasks.json"
LOG_DIR="$CLAWDBOT_DIR/logs"
KEEP_LOGS_DAYS=7

DRY_RUN=false
CLEAN_ALL=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --all) CLEAN_ALL=true ;;
  esac
done

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

if [ ! -f "$TASKS_FILE" ]; then
  log "No tasks file found. Nothing to clean."
  exit 0
fi

log "=== Cleanup ==="
[ "$DRY_RUN" = "true" ] && log "(DRY RUN — no changes will be made)"

CLEANED=0

# -- Determine which statuses to clean --
if [ "$CLEAN_ALL" = "true" ]; then
  STATUSES='["done", "merged", "failed", "ready_to_merge"]'
else
  STATUSES='["done", "merged"]'
fi

# -- Clean up tasks --
jq -c '.tasks[]' "$TASKS_FILE" | while IFS= read -r task; do
  TASK_ID=$(echo "$task" | jq -r '.id')
  STATUS=$(echo "$task" | jq -r '.status')
  WORKTREE=$(echo "$task" | jq -r '.worktree')
  TMUX_SESSION=$(echo "$task" | jq -r '.tmuxSession')
  BRANCH=$(echo "$task" | jq -r '.branch')

  # Check if status matches cleanup criteria
  SHOULD_CLEAN=$(echo "$task" | jq --argjson statuses "$STATUSES" \
    'any($statuses[]; . == .status)')

  if [ "$SHOULD_CLEAN" != "true" ]; then
    continue
  fi

  log "Cleaning: $TASK_ID (status: $STATUS)"

  # 1. Kill tmux session if still alive
  if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    if [ "$DRY_RUN" = "true" ]; then
      log "  Would kill tmux session: $TMUX_SESSION"
    else
      tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
      log "  Killed tmux session: $TMUX_SESSION"
    fi
  fi

  # 2. Remove worktree
  if [ -d "$WORKTREE" ]; then
    if [ "$DRY_RUN" = "true" ]; then
      log "  Would remove worktree: $WORKTREE"
    else
      cd "$REPO_ROOT"
      git worktree remove "$WORKTREE" --force 2>/dev/null || {
        log "  Warning: Could not remove worktree via git, removing directory..."
        rm -rf "$WORKTREE" 2>/dev/null || true
      }
      log "  Removed worktree: $WORKTREE"
    fi
  fi

  # 3. Delete remote branch if PR is merged
  if [ "$STATUS" = "merged" ] || [ "$STATUS" = "done" ]; then
    if [ "$DRY_RUN" = "true" ]; then
      log "  Would delete remote branch: $BRANCH"
    else
      cd "$REPO_ROOT"
      git push origin --delete "$BRANCH" 2>/dev/null || true
      git branch -D "$BRANCH" 2>/dev/null || true
      log "  Deleted branch: $BRANCH"
    fi
  fi

  CLEANED=$((CLEANED + 1))
done

# -- Remove cleaned tasks from registry --
if [ "$DRY_RUN" = "false" ] && [ "$CLEANED" -gt 0 ]; then
  jq --argjson statuses "$STATUSES" \
    '.tasks |= [.[] | select(any($statuses[]; . == .status) | not)] | .metadata.last_updated = now' \
    "$TASKS_FILE" > "${TASKS_FILE}.tmp" && mv "${TASKS_FILE}.tmp" "$TASKS_FILE"
fi

# -- Prune stale worktree metadata --
if [ "$DRY_RUN" = "false" ]; then
  cd "$REPO_ROOT"
  git worktree prune 2>/dev/null || true
fi

# -- Clean old logs --
if [ -d "$LOG_DIR" ]; then
  OLD_LOGS=$(find "$LOG_DIR" -name "*.log" -mtime +$KEEP_LOGS_DAYS 2>/dev/null | wc -l)
  if [ "$OLD_LOGS" -gt 0 ]; then
    if [ "$DRY_RUN" = "true" ]; then
      log "Would delete $OLD_LOGS log files older than $KEEP_LOGS_DAYS days"
    else
      find "$LOG_DIR" -name "*.log" -mtime +$KEEP_LOGS_DAYS -delete 2>/dev/null || true
      log "Deleted $OLD_LOGS old log files"
    fi
  fi
fi

log "Cleaned $CLEANED task(s)."
log "=== Cleanup Complete ==="
