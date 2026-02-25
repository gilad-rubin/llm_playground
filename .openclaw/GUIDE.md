# Agent Swarm Orchestration Guide

A local-first agent orchestration system that manages multiple AI coding agents
(Claude Code, Codex) running in parallel on isolated git worktrees.

Based on the OpenClaw + Codex/Claude Code Agent Swarm pattern.

## Architecture

```
You (human)
  │
  ▼
orchestrator.py ─── config.yaml
  │
  ├── spawn-agent.sh ──► git worktree + tmux session
  │     │
  │     ├── Claude Code agent (frontend, quick fixes)
  │     └── Codex agent (backend, complex logic)
  │
  ├── check-agents.sh ──► cron (every 10 min)
  │     │
  │     ├── tmux alive?
  │     ├── PR created?
  │     ├── CI passing?
  │     └── respawn if failed
  │
  ├── review-pr.sh ──► multi-model code review
  │     │
  │     ├── Claude review
  │     ├── Codex review
  │     └── Gemini Code Assist (GitHub App)
  │
  ├── cleanup.sh ──► daily cron
  │     │
  │     ├── remove merged worktrees
  │     ├── delete remote branches
  │     └── prune old logs
  │
  └── ralph-loop.sh ──► iterative task execution
        │
        └── fresh context each iteration (no context rot)
```

## Quick Start

```bash
# 1. Run setup to verify dependencies
bash .openclaw/scripts/setup.sh

# 2. Spawn an agent
python3 .openclaw/orchestrator.py spawn fix-bug claude "Fix the auth bug in login.py"

# 3. Check status
python3 .openclaw/orchestrator.py status

# 4. Watch the dashboard
python3 .openclaw/orchestrator.py dashboard
```

## Prerequisites

### Required
- **git** (2.5+ for worktree support)
- **tmux** (terminal multiplexer)
- **jq** (JSON processor)
- **Python 3.10+**

### AI Agent CLIs (install at least one)
```bash
# Claude Code
npm i -g @anthropic-ai/claude-code
export ANTHROPIC_API_KEY="sk-ant-..."

# OpenAI Codex
npm i -g @openai/codex
export OPENAI_API_KEY="sk-..."
```

### Optional
- **gh** CLI (GitHub PR management): https://cli.github.com/
- **yq** (YAML parsing): `pip install yq`
- **OpenClaw** (advanced orchestration): `npm i -g openclaw@latest`

## Commands

### Spawn an Agent

```bash
python3 .openclaw/orchestrator.py spawn <task-id> <agent> "<description>" [model]
```

This will:
1. Create a git worktree at `../llm_playground-worktrees/<task-id>/`
2. Create a new branch `feat/<task-id>`
3. Launch a tmux session `agent-<task-id>`
4. Register the task in `active-tasks.json`
5. Start the AI agent with your description as the prompt

**Examples:**
```bash
# Claude for frontend work
python3 .openclaw/orchestrator.py spawn ui-redesign claude "Redesign the settings page"

# Codex for backend logic
python3 .openclaw/orchestrator.py spawn fix-billing codex "Fix the billing race condition"

# Custom model
python3 .openclaw/orchestrator.py spawn feat-auth claude "Add OAuth2" claude-opus-4-20250514
```

### Monitor Agents

```bash
# Quick status
python3 .openclaw/orchestrator.py status

# Live dashboard (updates every 5s)
python3 .openclaw/orchestrator.py dashboard

# Run health check (same as cron)
python3 .openclaw/orchestrator.py check
```

### Talk to a Running Agent

The killer feature of tmux — redirect agents mid-task:

```bash
# Via orchestrator
python3 .openclaw/orchestrator.py send fix-bug "Stop. Focus on the API layer first."

# Via tmux directly
tmux send-keys -t agent-fix-bug "The schema is in src/types/user.ts. Use that." Enter

# Attach to watch the agent work
tmux attach -t agent-fix-bug
```

### Code Review

```bash
# Review a PR with all available reviewers
python3 .openclaw/orchestrator.py review 42

# Specific reviewers
python3 .openclaw/orchestrator.py review 42 claude codex
```

### Ralph Loop (Iterative Execution)

The Ralph Loop runs an agent repeatedly with fresh context, working through
a task list one item at a time. No context rot.

```bash
# 1. Create your task list
cp .openclaw/templates/TASKS.md ./TASKS.md
# Edit TASKS.md with your actual tasks

# 2. Run the loop
python3 .openclaw/orchestrator.py ralph TASKS.md --agent=claude --max-iterations=10

# Or use the bash script directly
bash .openclaw/scripts/ralph-loop.sh TASKS.md 10 claude
```

### Cleanup

```bash
# Clean completed/merged tasks
python3 .openclaw/orchestrator.py cleanup

# Clean everything including failed tasks
python3 .openclaw/orchestrator.py cleanup --all
```

## Automated Monitoring (Cron)

```bash
crontab -e

# Check agents every 10 minutes
*/10 * * * * bash /path/to/.openclaw/scripts/check-agents.sh >> /path/to/.openclaw/logs/monitor.log 2>&1

# Daily cleanup at 3 AM
0 3 * * * bash /path/to/.openclaw/scripts/cleanup.sh >> /path/to/.openclaw/logs/cleanup.log 2>&1
```

## Gemini Code Assist (Free PR Reviews)

1. Install the GitHub App: https://github.com/apps/gemini-code-assist
2. Config is at `.gemini/config.yaml`
3. Style guide is at `.gemini/styleguide.md`
4. Reviews happen automatically on every PR

Trigger manually: comment `/gemini review` on any PR.

## OpenClaw Integration (Advanced)

For the full "Zoe" experience — an AI orchestrator that proactively finds work,
spawns agents, and notifies you via Telegram/Slack:

```bash
# Install OpenClaw
npm i -g openclaw@latest
openclaw onboard

# Key ecosystem tools:
# - Mission Control: task dashboard — github.com/abhi1693/openclaw-mission-control
# - Antfarm: multi-agent teams — github.com/snarktank/antfarm
# - Claw Empire: autonomous agents — github.com/GreenSheep01201/claw-empire
```

## Choosing the Right Agent

| Task Type | Best Agent | Why |
|-----------|-----------|-----|
| Frontend / UI | Claude Code | Faster, better at HTML/CSS/React |
| Backend logic | Codex | Stronger reasoning, fewer errors |
| Complex bugs | Codex | Better at multi-file analysis |
| Git operations | Claude Code | Fewer permission issues |
| Quick fixes | Claude Code | Faster iteration |
| Multi-file refactor | Codex | Better at maintaining consistency |
| Code review | All three | Different models catch different issues |

## File Structure

```
.openclaw/
├── config.yaml              # Main configuration
├── orchestrator.py           # Python CLI orchestrator
├── active-tasks.json         # Task registry (gitignored)
├── GUIDE.md                  # This file
├── scripts/
│   ├── setup.sh              # One-time setup verification
│   ├── spawn-agent.sh        # Create worktree + launch agent
│   ├── run-agent.sh          # Execute agent with logging
│   ├── check-agents.sh       # Health monitoring (cron)
│   ├── review-pr.sh          # Multi-model PR review
│   ├── ralph-loop.sh         # Iterative task execution
│   └── cleanup.sh            # Worktree/branch cleanup
├── templates/
│   └── TASKS.md              # Ralph Loop task template
└── logs/                     # Agent logs (gitignored)

.gemini/
├── config.yaml               # Gemini Code Assist config
└── styleguide.md             # Review style guide
```

## Resource Considerations

Each agent with its worktree uses ~2-4GB RAM. Plan accordingly:

| RAM | Comfortable Agents | Max Agents |
|-----|-------------------|------------|
| 8GB | 1-2 | 2 |
| 16GB | 3-4 | 5 |
| 32GB | 5-8 | 10 |
| 64GB | 10-15 | 20 |
| 128GB | 20+ | 30+ |

## Costs

| Tool | Approximate Cost |
|------|-----------------|
| Claude Code (Sonnet) | ~$0.50-2/task |
| Claude Code (Opus) | ~$2-10/task |
| Codex (o4-mini) | Included with ChatGPT Plus ($20/mo) |
| Gemini Code Assist | Free |
| OpenClaw | Free (open source) |
