#!/usr/bin/env bash
# =============================================================================
# setup.sh — One-time setup for the Agent Swarm Orchestration System
# =============================================================================
# Run this script to verify all dependencies and configure your environment.
#
# Usage:
#   bash .openclaw/scripts/setup.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAWDBOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "  Agent Swarm Setup"
echo "============================================"
echo ""

ERRORS=0
WARNINGS=0

check_cmd() {
  local cmd="$1"
  local install_hint="$2"
  local required="${3:-true}"

  if command -v "$cmd" >/dev/null 2>&1; then
    local version
    version=$($cmd --version 2>/dev/null | head -1 || echo "installed")
    echo "  [OK]  $cmd — $version"
    return 0
  else
    if [ "$required" = "true" ]; then
      echo "  [ERR] $cmd — NOT FOUND"
      echo "        Install: $install_hint"
      ERRORS=$((ERRORS + 1))
    else
      echo "  [OPT] $cmd — not installed (optional)"
      echo "        Install: $install_hint"
      WARNINGS=$((WARNINGS + 1))
    fi
    return 1
  fi
}

# -- Required Tools --
echo "Required tools:"
check_cmd "git"    "https://git-scm.com/downloads"
check_cmd "tmux"   "apt install tmux / brew install tmux"
check_cmd "jq"     "apt install jq / brew install jq"
check_cmd "python3" "https://python.org/downloads"
echo ""

# -- AI Agent CLIs --
echo "AI Agent CLIs:"
check_cmd "claude" "npm i -g @anthropic-ai/claude-code" "false"
check_cmd "codex"  "npm i -g @openai/codex" "false"
echo ""

# -- Optional Tools --
echo "Optional tools:"
check_cmd "gh"     "https://cli.github.com/ (for PR management)" "false"
check_cmd "yq"     "pip install yq / brew install yq (for YAML config parsing)" "false"
echo ""

# -- Check API Keys --
echo "API Keys:"
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "  [OK]  ANTHROPIC_API_KEY is set"
else
  echo "  [OPT] ANTHROPIC_API_KEY not set (needed for Claude Code)"
  WARNINGS=$((WARNINGS + 1))
fi
if [ -n "${OPENAI_API_KEY:-}" ]; then
  echo "  [OK]  OPENAI_API_KEY is set"
else
  echo "  [OPT] OPENAI_API_KEY not set (needed for Codex)"
  WARNINGS=$((WARNINGS + 1))
fi
echo ""

# -- Make scripts executable --
echo "Making scripts executable..."
chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null
echo "  Done."
echo ""

# -- Directory structure --
echo "Directory structure:"
mkdir -p "$CLAWDBOT_DIR/logs"
mkdir -p "$CLAWDBOT_DIR/templates"
echo "  [OK] .openclaw/logs/"
echo "  [OK] .openclaw/templates/"
echo "  [OK] .openclaw/scripts/"
echo ""

# -- Git worktree support --
echo "Git worktree support:"
GIT_VERSION=$(git --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1)
if [ -n "$GIT_VERSION" ]; then
  MAJOR=$(echo "$GIT_VERSION" | cut -d. -f1)
  MINOR=$(echo "$GIT_VERSION" | cut -d. -f2)
  if [ "$MAJOR" -gt 2 ] || ([ "$MAJOR" -eq 2 ] && [ "$MINOR" -ge 5 ]); then
    echo "  [OK]  Git $GIT_VERSION supports worktrees (requires 2.5+)"
  else
    echo "  [ERR] Git $GIT_VERSION does NOT support worktrees. Upgrade to 2.5+"
    ERRORS=$((ERRORS + 1))
  fi
fi
echo ""

# -- Cron setup hint --
echo "Cron monitoring (optional):"
CRON_CMD="*/10 * * * * bash $SCRIPT_DIR/check-agents.sh >> $CLAWDBOT_DIR/logs/monitor.log 2>&1"
echo "  To enable automated monitoring, add this to your crontab:"
echo "  crontab -e"
echo "  $CRON_CMD"
echo ""
echo "  Daily cleanup:"
CLEANUP_CMD="0 3 * * * bash $SCRIPT_DIR/cleanup.sh >> $CLAWDBOT_DIR/logs/cleanup.log 2>&1"
echo "  $CLEANUP_CMD"
echo ""

# -- Gemini Code Assist --
echo "Gemini Code Assist (free automated PR reviews):"
echo "  Install the GitHub App: https://github.com/apps/gemini-code-assist"
echo "  Config file created at: .gemini/config.yaml"
echo ""

# -- OpenClaw (optional orchestration layer) --
echo "OpenClaw (optional advanced orchestration):"
echo "  Install: npm install -g openclaw@latest"
echo "  Setup:   openclaw onboard"
echo "  Docs:    https://github.com/openclaw/openclaw"
echo ""

# -- Summary --
echo "============================================"
if [ $ERRORS -eq 0 ]; then
  echo "  Setup complete! ($WARNINGS warnings)"
  echo ""
  echo "  Quick start:"
  echo "    python3 .openclaw/orchestrator.py spawn my-task claude 'Fix the bug in auth.py'"
  echo "    python3 .openclaw/orchestrator.py status"
  echo "    python3 .openclaw/orchestrator.py dashboard"
else
  echo "  Setup has $ERRORS error(s) and $WARNINGS warning(s)."
  echo "  Fix the errors above before using the agent swarm."
fi
echo "============================================"
