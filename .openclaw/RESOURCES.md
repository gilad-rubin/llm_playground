# Agent Swarm Ecosystem — Tools & Resources

A curated list of tools, frameworks, and patterns for running AI coding
agent swarms. Star counts are approximate as of Feb 2026.

---

## Orchestration Platforms

### OpenClaw (228k stars)
> Your own personal AI assistant. Any OS. Any Platform.

The most popular open-source AI agent framework. Runs locally as a gateway
process, connects to messaging platforms (Telegram, Slack, Discord, WhatsApp),
and routes messages through LLM-powered agents that can take real-world actions.
Over 100 community-built AgentSkills (plugins) available.

- **Repo**: https://github.com/openclaw/openclaw
- **Site**: https://openclaw.ai/
- **Install**: `npm install -g openclaw@latest && openclaw onboard`
- **Best for**: High-level task orchestration, proactive agent spawning, notifications

### claude-flow (14.5k stars)
> Agent orchestration platform for Claude with multi-agent swarms via MCP.

Deploys intelligent multi-agent swarms, coordinates autonomous workflows.
Native Claude Code support via MCP protocol. Supports hierarchical
(queen/workers) and mesh (peer-to-peer) agent patterns.

- **Repo**: https://github.com/ruvnet/claude-flow
- **Install**: `npm install -g claude-flow`
- **Best for**: Claude-native multi-agent swarms, MCP integration

### Agent Orchestrator by Composio (1.9k stars)
> Manages fleets of AI coding agents working in parallel.

Each agent gets its own git worktree, branch, and PR. When CI fails, the
agent fixes it. Reviewer requests changes — agent addresses them. Supports
swappable plugins for different agents (Claude Code, Codex, Aider), runtimes
(tmux, Docker), and trackers (GitHub, Linear).

- **Repo**: https://github.com/ComposioHQ/agent-orchestrator
- **Install**: `npx agent-orchestrator init`
- **Best for**: Production-grade agent fleet management with CI auto-fix

### GasTown by Steve Yegge (10.3k stars)
> "Kubernetes for agents." Multi-agent orchestration with persistent work tracking.

Talk to the "Mayor" (primary coordinator), which manages "Rigs" (project
containers), "Crew" (per-rig coding agents in git worktrees), and "Beads"
(atomic work units tracked in JSON/git).

- **Repo**: https://github.com/steveyegge/gastown
- **Install**: `brew install gastown` or `npm install -g @gastown/gt`
- **Best for**: Experienced users running 10+ agents simultaneously

---

## Multi-Agent Claude Code Tools

### Claude Code Native Agent Teams (Official)
> Built-in multi-agent support from Anthropic.

Claude Code now supports coordinating multiple instances working together.
One session acts as team lead, coordinating work and assigning tasks.
Teammates work independently in their own context windows.

- **Docs**: https://code.claude.com/docs/en/agent-teams
- **Enable**: Add `"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"` to settings.json
- **Requires**: tmux or iTerm2 for split panes
- **Best for**: Simple multi-agent workflows within Claude Code itself

### Overstory (521 stars)
> Project-agnostic swarm system for Claude Code agent orchestration.

Turns a single Claude Code session into a multi-agent team. Spawns workers
in git worktrees via tmux, coordinates through SQLite mail system, merges
with tiered conflict resolution. Includes a watchdog daemon for health monitoring.

- **Repo**: https://github.com/jayminwest/overstory
- **Install**: `npm install -g overstory`
- **Best for**: Claude Code power users wanting swarm capabilities

### claude_code_agent_farm (664 stars)
> Run 20+ Claude Code agents in parallel with real-time tmux monitoring.

Automated bug fixing, best-practices sweeps, lock-based coordination.
Smart monitoring dashboard with context warnings, heartbeat tracking,
and auto-recovery.

- **Repo**: https://github.com/Dicklesworthstone/claude_code_agent_farm
- **Best for**: Large-scale parallel agent runs, automated code sweeps

### ccswarm (111 stars)
> Workflow automation for coordinating specialized AI agents via Claude Code CLI.

Specialized agent pools (Frontend, Backend, DevOps, QA) in worktree-isolated
environments. Template-based scaffolding and task delegation infrastructure.

- **Repo**: https://github.com/nwiizo/ccswarm
- **Best for**: Team-structured agent workflows with role specialization

### claude-swarm (Hackathon Winner)
> Task decomposition into dependency graphs with parallel agent spawning.

Built with Claude Agent SDK. Opus 4.6 decomposes tasks, spawns parallel agents,
detects file conflicts, enforces budgets. Includes htop-style terminal dashboard.

- **Repo**: https://github.com/affaan-m/claude-swarm
- **Best for**: Dependency-aware parallel task execution

---

## tmux Agent Managers

### Claude Squad
> Manage multiple AI terminal agents using tmux sessions and git worktrees.

Supports Claude Code, Aider, Codex, OpenCode, Amp. Single CLI for session
lifecycle management.

- **Repo**: https://github.com/smtg-ai/claude-squad
- **Install**: `curl -fsSL https://raw.githubusercontent.com/smtg-ai/claude-squad/main/install.sh | bash`

### Maestro (2.1k stars)
> Cross-platform desktop app for orchestrating fleets of AI agents.

Supports Claude Code, Codex, OpenCode, Factory Droid. Auto Run mode
(24hr continuous runtime), Group Chat (multi-agent conversations),
Mobile Remote Control via QR code.

- **Repo**: https://github.com/pedramamini/Maestro
- **Site**: https://runmaestro.ai/

---

## Git Worktree Management

### workmux (816 stars)
> git worktrees + tmux windows for zero-friction parallel dev.

Written in Rust. Supports multiple terminal multiplexers (tmux, Kitty, WezTerm,
Zellij). Built-in agent detection for claude, gemini, codex, opencode with
automatic prompt injection. Clean worktree checkouts with configurable file
copying/symlinking.

- **Repo**: https://github.com/raine/workmux
- **Install**: `cargo install workmux` or download from releases
- **Best for**: Developers who want tmux-native worktree management

### worktrunk (2.3k stars)
> CLI for git worktree management, designed for parallel AI agent workflows.

Three core commands: `wt switch`, `wt list`, `wt remove`. Workflow automation
through hooks, LLM-generated commit messages, Claude Code integration.
81 releases, very actively maintained.

- **Repo**: https://github.com/max-sixty/worktrunk
- **Install**: `cargo install worktrunk`
- **Best for**: Lightweight worktree management with AI-friendly defaults

### git-worktree-runner by CodeRabbit (1.4k stars)
> Portable, cross-platform CLI for managing git worktrees.

Automates per-branch worktree creation, config copying, dependency install,
and workspace setup. Editor integration (Cursor, VS Code, Zed) and AI tool
support (Claude, Aider).

- **Repo**: https://github.com/coderabbitai/git-worktree-runner
- **Install**: Download from releases (bash-based, no compilation needed)
- **Best for**: Cross-platform worktree management with editor integration

### agent-worktree (116 stars)
> Worktree workflow tool for AI coding agents with snap mode.

Create → run → merge → cleanup workflows. TOML configuration.
Written in Rust.

- **Repo**: https://github.com/nekocode/agent-worktree
- **Install**: `cargo install agent-worktree`
- **Best for**: Quick disposable agent worktree lifecycles

---

## The Ralph Loop

### Ralph Pattern (Original)
> "A Bash loop that feeds an AI's output back into itself until it dreams up the correct answer."

Created by Geoffrey Huntley. The core insight: fresh context each iteration
prevents context rot. Memory persists via git history and progress files.

- **Writeup**: https://ghuntley.com/loop/
- **Core script**: `while :; do cat PROMPT.md | claude -p ; done`

### snarktank/ralph (11.2k stars)
> The canonical Ralph implementation. Autonomous AI agent loop using Amp or Claude Code.

Runs repeatedly until all PRD items are complete. Each iteration gets fresh
context. Memory persists through git history, progress.txt, and prd.json.

- **Repo**: https://github.com/snarktank/ralph
- **Install**: Clone and run

### frankbria/ralph-claude-code (7.3k stars)
> Ralph implementation with intelligent exit detection and rate limiting.

Built-in safeguards: circuit breakers for API limits, smart loop termination
when tasks complete, bash compatibility. 566 passing tests.

- **Repo**: https://github.com/frankbria/ralph-claude-code
- **Install**: Clone and run
- **Best for**: Production-safe Ralph loops with guardrails

### Antfarm (OpenClaw Pipelines)
> Deterministic YAML workflows with specialized agents on top of OpenClaw.

Bundled pipelines for feature development, security fixes, bug fixes.
SQLite + cron, zero external infrastructure. By Ryan Carson (also created Ralph).

- **Repo**: https://github.com/snarktank/antfarm
- **Site**: https://www.antfarm.cool/
- **Requires**: Node.js >= 22, OpenClaw v2026.2.9+, `gh` CLI

---

## Multi-Agent Desktop Apps

### Parallel Code (255 stars)
> GUI app to run Claude Code, Codex CLI, and Gemini CLI side by side.

Electron-based desktop app. Automatic worktree isolation. Switch between
agents per task or run all three simultaneously. QR code for remote
monitoring from your phone.

- **Repo**: https://github.com/johannesjo/parallel-code
- **Platforms**: macOS, Linux
- **Best for**: Visual multi-agent management without terminal wrestling

---

## Free Code Review

### Gemini Code Assist (Free)
> Google's AI code review bot for GitHub PRs. Completely free.

Automatic PR summaries and in-depth code reviews. Identifies bugs, style
issues, security problems. Interactive via `/gemini` commands in PR comments.
180,000 code completions/month on the free tier.

- **Install**: https://github.com/apps/gemini-code-assist
- **Docs**: https://developers.google.com/gemini-code-assist/docs/set-up-code-assist-github
- **Commands**: `/gemini review`, `/gemini summary`
- **Best for**: Free automated code review on every PR

### CodeRabbit (Free for OSS)
> AI-powered line-by-line code review with committable suggestions.

179,000+ installs. One-click fix suggestions, codebase impact analysis.
Free for open-source repos.

- **Install**: https://github.com/marketplace/coderabbitai
- **Config**: `.github/coderabbit.yaml`

---

## Other Terminal AI Agents (Swarm-Compatible)

These agents can be plugged into any of the orchestrators above:

| Agent | Repo | Best For |
|-------|------|----------|
| **Claude Code** | https://github.com/anthropics/claude-code | Frontend, git ops, quick fixes |
| **Codex CLI** | https://github.com/openai/codex | Backend logic, complex reasoning |
| **Gemini CLI** | https://github.com/google-gemini/gemini-cli | Free (60 req/min), design |
| **Aider** (40.9k stars) | https://github.com/Aider-AI/aider | Multi-model pair programming |
| **OpenCode** (100k+ stars) | https://github.com/opencode-ai/opencode | Provider-agnostic TUI |

---

## Claude Code Ecosystem

| Tool | What It Does |
|------|-------------|
| **Agent Teams** (Official) | Built-in multi-agent: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` |
| **awesome-claude-code** | Curated list of everything: https://github.com/hesreallyhim/awesome-claude-code |
| **Claude Code SDK (Python)** | Programmatic control: `pip install claude-code-sdk` |
| **claude-code-hooks** | Ready-to-use hooks: https://github.com/karanb192/claude-code-hooks |

---

## Recommended Stack

For a solo developer running an agent swarm, here's a practical stack:

| Layer | Tool | Cost |
|-------|------|------|
| **Orchestrator** | OpenClaw or Agent Orchestrator | Free |
| **Worktree mgmt** | workmux or worktrunk | Free |
| **Agent: Backend** | Codex CLI (o4-mini) | ~$20/mo (ChatGPT Plus) |
| **Agent: Frontend** | Claude Code (Sonnet) | ~$20-100/mo |
| **Ralph Loop** | ralph-claude-code | Free |
| **Code Review** | Gemini Code Assist | Free |
| **Monitoring** | Built-in scripts (this repo) | Free |
| **Notifications** | OpenClaw → Telegram/Slack | Free |

**Total**: ~$40-120/month for a full AI dev team.

---

## Further Reading

- [LLM Codegen go Brrr – Parallelization with Git Worktrees and Tmux](https://dev.to/skeptrune/llm-codegen-go-brrr-parallelization-with-git-worktrees-and-tmux-2gop)
- [Git worktrees for parallel AI coding agents (Upsun)](https://devcenter.upsun.com/posts/git-worktrees-for-parallel-ai-coding-agents/)
- [The Ralph Wiggum Approach: Running AI Agents for Hours](https://dev.to/sivarampg/the-ralph-wiggum-approach-running-ai-coding-agents-for-hours-not-minutes-57c1)
- [How OpenClaw Works (Medium)](https://bibek-poudel.medium.com/how-openclaw-works-understanding-ai-agents-through-a-real-architecture-5d59cc7a4764)
- [Inventing the Ralph Wiggum Loop (Dev Interrupted)](https://devinterrupted.substack.com/p/inventing-the-ralph-wiggum-loop-creator)
- [Claude Code Swarms: Multi-Agent AI Coding](https://addyosmani.com/blog/claude-code-agent-teams/)
- [Open-Sourcing Agent Orchestrator (Composio)](https://pkarnal.com/blog/open-sourcing-agent-orchestrator)
