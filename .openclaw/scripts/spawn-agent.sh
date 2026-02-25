#!/usr/bin/env bash
# =============================================================================
# spawn-agent.sh — Create a worktree, launch an AI agent in a tmux session
# =============================================================================
# Usage:
#   ./spawn-agent.sh <task-id> <agent-type> <description> [model] [effort]
#
# Examples:
#   ./spawn-agent.sh feat-auth claude "Implement OAuth2 flow"
#   ./spawn-agent.sh fix-billing codex "Fix billing race condition" o4-mini high
#   ./spawn-agent.sh ui-redesign claude "Redesign dashboard" claude-sonnet-4-20250514
#
# Arguments:
#   task-id      Unique identifier (used for branch, worktree, tmux session)
#   agent-type   claude | codex
#   description  What the agent should do (passed as the prompt)
#   model        (optional) Model override
#   effort       (optional) Reasoning effort: low | medium | high (codex only)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAWDBOT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$CLAWDBOT_DIR/.." && pwd)"
TASKS_FILE="$CLAWDBOT_DIR/active-tasks.json"
LOGS_DIR="$CLAWDBOT_DIR/logs"

# -- Parse arguments --
TASK_ID="${1:?Usage: spawn-agent.sh <task-id> <agent-type> <description> [model] [effort]}"
AGENT_TYPE="${2:?Specify agent type: claude or codex}"
DESCRIPTION="${3:?Provide a task description}"
MODEL="${4:-}"
EFFORT="${5:-medium}"

# -- Defaults per agent type --
case "$AGENT_TYPE" in
  claude)
    MODEL="${MODEL:-claude-sonnet-4-20250514}"
    ;;
  codex)
    MODEL="${MODEL:-o4-mini}"
    ;;
  *)
    echo "Error: Unknown agent type '$AGENT_TYPE'. Use 'claude' or 'codex'."
    exit 1
    ;;
esac

# -- Derived paths --
REPO_NAME="$(basename "$REPO_ROOT")"
WORKTREE_BASE="$(cd "$REPO_ROOT/.." && pwd)/${REPO_NAME}-worktrees"
WORKTREE_PATH="$WORKTREE_BASE/$TASK_ID"
BRANCH_NAME="feat/$TASK_ID"
TMUX_SESSION="agent-$TASK_ID"
LOG_FILE="$LOGS_DIR/${TASK_ID}.log"

echo "=== Agent Spawner ==="
echo "Task ID:     $TASK_ID"
echo "Agent:       $AGENT_TYPE"
echo "Model:       $MODEL"
echo "Branch:      $BRANCH_NAME"
echo "Worktree:    $WORKTREE_PATH"
echo "tmux:        $TMUX_SESSION"
echo "Description: $DESCRIPTION"
echo ""

# -- Preflight checks --
command -v tmux >/dev/null 2>&1 || { echo "Error: tmux is not installed."; exit 1; }
command -v git >/dev/null 2>&1 || { echo "Error: git is not installed."; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "Error: jq is not installed."; exit 1; }

if [ "$AGENT_TYPE" = "claude" ]; then
  command -v claude >/dev/null 2>&1 || { echo "Error: claude CLI is not installed. Run: npm i -g @anthropic-ai/claude-code"; exit 1; }
elif [ "$AGENT_TYPE" = "codex" ]; then
  command -v codex >/dev/null 2>&1 || { echo "Error: codex CLI is not installed. Run: npm i -g @openai/codex"; exit 1; }
fi

# Check if tmux session already exists
if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
  echo "Error: tmux session '$TMUX_SESSION' already exists."
  echo "Use: tmux attach -t $TMUX_SESSION"
  exit 1
fi

# -- Create worktree --
mkdir -p "$WORKTREE_BASE"
mkdir -p "$LOGS_DIR"

cd "$REPO_ROOT"

# Fetch latest from remote
git fetch origin main 2>/dev/null || git fetch origin master 2>/dev/null || true

# Determine base branch
BASE_BRANCH="main"
if ! git rev-parse --verify "origin/main" >/dev/null 2>&1; then
  BASE_BRANCH="master"
fi

# Create worktree with new branch
if [ -d "$WORKTREE_PATH" ]; then
  echo "Worktree already exists at $WORKTREE_PATH, reusing..."
else
  echo "Creating worktree..."
  git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME" "origin/$BASE_BRANCH" 2>/dev/null || \
    git worktree add "$WORKTREE_PATH" "$BRANCH_NAME" 2>/dev/null || \
    { echo "Error: Failed to create worktree."; exit 1; }
fi

# -- Install dependencies if needed --
cd "$WORKTREE_PATH"
if [ -f "package.json" ]; then
  echo "Installing npm dependencies..."
  npm install --silent 2>/dev/null || true
fi
if [ -f "requirements.txt" ]; then
  echo "Installing Python dependencies..."
  pip install -q -r requirements.txt 2>/dev/null || true
fi

# -- Build the agent command --
PROMPT_FILE="$CLAWDBOT_DIR/logs/${TASK_ID}-prompt.txt"
cat > "$PROMPT_FILE" << PROMPT_EOF
You are working on task: $TASK_ID
Branch: $BRANCH_NAME

## Task Description
$DESCRIPTION

## Instructions
1. Read any relevant files to understand the codebase
2. Implement the requested changes
3. Run any available tests (pytest, npm test, etc.)
4. If tests pass, commit your changes with a descriptive message
5. Push to the remote branch: git push -u origin $BRANCH_NAME
6. Create a PR using: gh pr create --title "$TASK_ID" --body "Automated PR for: $DESCRIPTION" --base $BASE_BRANCH
7. When done, create a file called .openclaw-done in the repo root
PROMPT_EOF

case "$AGENT_TYPE" in
  claude)
    AGENT_CMD="claude --model $MODEL --dangerously-skip-permissions -p \"\$(cat $PROMPT_FILE)\""
    ;;
  codex)
    AGENT_CMD="codex --model $MODEL --full-auto \"\$(cat $PROMPT_FILE)\""
    ;;
esac

# -- Register the task --
TIMESTAMP=$(date +%s%3N 2>/dev/null || date +%s)
TASK_JSON=$(cat <<EOF
{
  "id": "$TASK_ID",
  "tmuxSession": "$TMUX_SESSION",
  "agent": "$AGENT_TYPE",
  "model": "$MODEL",
  "description": "$DESCRIPTION",
  "repo": "$REPO_NAME",
  "worktree": "$WORKTREE_PATH",
  "branch": "$BRANCH_NAME",
  "startedAt": $TIMESTAMP,
  "status": "running",
  "retries": 0,
  "notifyOnComplete": true,
  "checks": {
    "prCreated": false,
    "ciPassed": false,
    "reviewPassed": false
  }
}
EOF
)

# Add task to registry
if [ -f "$TASKS_FILE" ]; then
  jq --argjson task "$TASK_JSON" '.tasks += [$task] | .metadata.last_updated = now' "$TASKS_FILE" > "${TASKS_FILE}.tmp" && \
    mv "${TASKS_FILE}.tmp" "$TASKS_FILE"
else
  echo "{\"tasks\": [$TASK_JSON], \"metadata\": {\"last_updated\": \"$(date -Iseconds)\", \"version\": \"1.0.0\"}}" > "$TASKS_FILE"
fi

# -- Launch tmux session with the agent --
RUNNER_SCRIPT="$CLAWDBOT_DIR/scripts/run-agent.sh"

tmux new-session -d -s "$TMUX_SESSION" -c "$WORKTREE_PATH" \
  "bash $RUNNER_SCRIPT '$TASK_ID' '$AGENT_TYPE' '$MODEL' '$PROMPT_FILE' '$LOG_FILE' '$TASKS_FILE'; bash"

echo ""
echo "=== Agent Spawned Successfully ==="
echo ""
echo "Monitor:     tmux attach -t $TMUX_SESSION"
echo "Logs:        tail -f $LOG_FILE"
echo "All agents:  tmux ls"
echo "Send msg:    tmux send-keys -t $TMUX_SESSION 'your message here' Enter"
echo "Task file:   $TASKS_FILE"
echo ""
