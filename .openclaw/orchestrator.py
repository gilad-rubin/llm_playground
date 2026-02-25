"""
Agent Swarm Orchestrator
========================
A Python-based orchestrator inspired by the OpenClaw + Codex/Claude Code agent
swarm pattern. Manages spawning, monitoring, reviewing, and cleaning up AI
coding agents running in isolated git worktrees with tmux sessions.

Usage:
    python orchestrator.py spawn <task-id> <agent> <description>
    python orchestrator.py status
    python orchestrator.py check
    python orchestrator.py review <pr-number>
    python orchestrator.py cleanup [--all]
    python orchestrator.py dashboard
    python orchestrator.py ralph <task-file> [--max-iterations=10] [--agent=claude]

Examples:
    python orchestrator.py spawn feat-auth claude "Implement OAuth2 flow"
    python orchestrator.py spawn fix-billing codex "Fix billing race condition"
    python orchestrator.py status
    python orchestrator.py ralph TASKS.md --agent=claude --max-iterations=5
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# -- Paths --
CLAWDBOT_DIR = Path(__file__).parent
REPO_ROOT = CLAWDBOT_DIR.parent
TASKS_FILE = CLAWDBOT_DIR / "active-tasks.json"
LOGS_DIR = CLAWDBOT_DIR / "logs"
SCRIPTS_DIR = CLAWDBOT_DIR / "scripts"
CONFIG_FILE = CLAWDBOT_DIR / "config.yaml"


def load_tasks() -> dict:
    """Load the task registry."""
    if TASKS_FILE.exists():
        return json.loads(TASKS_FILE.read_text())
    return {"tasks": [], "metadata": {"version": "1.0.0"}}


def save_tasks(data: dict):
    """Save the task registry."""
    data["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    TASKS_FILE.write_text(json.dumps(data, indent=2, default=str))


def run(cmd: str, capture: bool = True, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run a shell command."""
    return subprocess.run(
        cmd, shell=True, capture_output=capture, text=True,
        cwd=cwd or str(REPO_ROOT)
    )


def tmux_session_alive(session_name: str) -> bool:
    """Check if a tmux session is running."""
    result = run(f"tmux has-session -t {session_name} 2>/dev/null")
    return result.returncode == 0


def get_active_agent_count() -> int:
    """Count currently running agents."""
    data = load_tasks()
    return sum(1 for t in data["tasks"] if t["status"] == "running")


# ============================================================================
# Commands
# ============================================================================

def cmd_spawn(task_id: str, agent_type: str, description: str,
              model: str = "", effort: str = "medium"):
    """Spawn a new agent in an isolated worktree."""
    LOGS_DIR.mkdir(exist_ok=True)

    # Check concurrent limit
    active = get_active_agent_count()
    max_concurrent = 4  # default
    if active >= max_concurrent:
        print(f"Warning: {active} agents already running (max: {max_concurrent})")
        print("Proceeding anyway, but monitor RAM usage.")

    # Delegate to the shell script (it handles worktree, tmux, registry)
    spawn_script = SCRIPTS_DIR / "spawn-agent.sh"
    if not spawn_script.exists():
        print(f"Error: {spawn_script} not found.")
        sys.exit(1)

    cmd_parts = [
        "bash", str(spawn_script),
        task_id, agent_type, f'"{description}"',
    ]
    if model:
        cmd_parts.append(model)
    if effort != "medium":
        cmd_parts.append(effort)

    result = run(" ".join(cmd_parts), capture=False)
    return result.returncode


def cmd_status():
    """Show status of all tasks."""
    data = load_tasks()
    tasks = data["tasks"]

    if not tasks:
        print("No active tasks.")
        return

    # Status display
    print(f"\n{'='*70}")
    print(f"{'AGENT SWARM STATUS':^70}")
    print(f"{'='*70}")

    status_colors = {
        "running": "\033[33m",      # yellow
        "done": "\033[32m",         # green
        "failed": "\033[31m",       # red
        "ready_to_merge": "\033[36m",  # cyan
        "respawning": "\033[35m",   # magenta
    }
    reset = "\033[0m"

    for task in tasks:
        tid = task["id"]
        status = task["status"]
        agent = task["agent"]
        desc = task.get("description", "")[:40]
        pr = task.get("pr", "-")
        tmux = task.get("tmuxSession", "")
        color = status_colors.get(status, "")

        # Check tmux session
        tmux_live = "ALIVE" if tmux_session_alive(tmux) else "DEAD"

        # Check indicators
        checks = task.get("checks", {})
        pr_ok = "Y" if checks.get("prCreated") else "N"
        ci_ok = "Y" if checks.get("ciPassed") else "N"
        rv_ok = "Y" if checks.get("reviewPassed") else "N"

        print(f"\n  {tid}")
        print(f"    Agent:   {agent:8s} | Status: {color}{status:15s}{reset} | tmux: {tmux_live}")
        print(f"    PR: #{pr:<5} | Checks: PR={pr_ok} CI={ci_ok} Review={rv_ok}")
        print(f"    Desc:    {desc}")

    # Summary
    running = sum(1 for t in tasks if t["status"] == "running")
    done = sum(1 for t in tasks if t["status"] == "done")
    failed = sum(1 for t in tasks if t["status"] == "failed")
    ready = sum(1 for t in tasks if t["status"] == "ready_to_merge")

    print(f"\n{'='*70}")
    print(f"  Running: {running} | Done: {done} | Ready: {ready} | Failed: {failed}")
    print(f"{'='*70}\n")


def cmd_check():
    """Run the monitoring check (same as cron job)."""
    check_script = SCRIPTS_DIR / "check-agents.sh"
    if check_script.exists():
        run(f"bash {check_script}", capture=False)
    else:
        print(f"Error: {check_script} not found.")


def cmd_review(pr_number: str, reviewers: list[str] = None):
    """Trigger code review on a PR."""
    review_script = SCRIPTS_DIR / "review-pr.sh"
    if review_script.exists():
        reviewers_str = " ".join(reviewers) if reviewers else ""
        run(f"bash {review_script} {pr_number} {reviewers_str}", capture=False)
    else:
        print(f"Error: {review_script} not found.")


def cmd_cleanup(clean_all: bool = False):
    """Clean up completed tasks, worktrees, and branches."""
    cleanup_script = SCRIPTS_DIR / "cleanup.sh"
    if cleanup_script.exists():
        flag = "--all" if clean_all else ""
        run(f"bash {cleanup_script} {flag}", capture=False)
    else:
        print(f"Error: {cleanup_script} not found.")


def cmd_send(task_id: str, message: str):
    """Send a message to a running agent via tmux."""
    data = load_tasks()
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)

    if not task:
        print(f"Error: Task '{task_id}' not found.")
        return

    tmux_session = task["tmuxSession"]
    if not tmux_session_alive(tmux_session):
        print(f"Error: tmux session '{tmux_session}' is not running.")
        return

    # Send the message to the agent
    run(f"tmux send-keys -t {tmux_session} '{message}' Enter", capture=False)
    print(f"Message sent to {task_id}: {message}")


def cmd_ralph(task_file: str, max_iterations: int = 10, agent: str = "claude"):
    """
    Run the Ralph Loop: iteratively spawn agents to work through a task list.

    The Ralph Loop pattern:
    1. Read the task file
    2. Spawn an agent to work on the next incomplete task
    3. Agent implements, tests, commits
    4. Check results, loop back to step 1
    5. Each iteration gets a fresh context window (no context rot)
    """
    task_path = Path(task_file)
    if not task_path.exists():
        print(f"Error: Task file '{task_file}' not found.")
        print("Create a TASKS.md file with tasks marked as [ ] incomplete or [x] done.")
        sys.exit(1)

    LOGS_DIR.mkdir(exist_ok=True)

    print(f"\n{'='*60}")
    print(f"{'RALPH LOOP':^60}")
    print(f"{'='*60}")
    print(f"Task file:      {task_file}")
    print(f"Agent:          {agent}")
    print(f"Max iterations: {max_iterations}")
    print(f"{'='*60}\n")

    # Model defaults
    models = {
        "claude": "claude-sonnet-4-20250514",
        "codex": "o4-mini",
    }
    model = models.get(agent, agent)

    for i in range(1, max_iterations + 1):
        print(f"\n--- Iteration {i}/{max_iterations} ---")

        # Check for completion marker
        done_marker = REPO_ROOT / "DONE"
        if done_marker.exists():
            print(f"DONE marker found. All tasks completed after {i-1} iterations!")
            done_marker.unlink()
            return

        # Build the ralph loop prompt
        prompt = f"""Read the file '{task_file}'. Find the next incomplete task (marked with [ ] or similar).
Implement that single task. Run any available tests. If tests pass:
1. Mark the task as complete in '{task_file}' (change [ ] to [x])
2. Commit your changes with a descriptive message
3. If ALL tasks are now complete, create a file called DONE in the repo root.

Focus on ONE task only. Do not skip ahead. Be thorough but focused."""

        log_file = LOGS_DIR / f"ralph-{i}.log"

        # Run the agent
        if agent == "claude" or agent.startswith("claude"):
            cmd = f'claude --model {model} --dangerously-skip-permissions -p "{prompt}"'
        elif agent == "codex" or agent.startswith("codex"):
            cmd = f'codex --model {model} --full-auto "{prompt}"'
        else:
            print(f"Unknown agent: {agent}")
            sys.exit(1)

        print(f"Running {agent} (model: {model})...")
        result = run(cmd, capture=False, cwd=str(REPO_ROOT))

        if result.returncode != 0:
            print(f"Agent exited with code {result.returncode}")
            print("Continuing to next iteration (fresh context)...")

        # Brief pause between iterations
        time.sleep(2)

    # Final check
    done_marker = REPO_ROOT / "DONE"
    if done_marker.exists():
        print(f"\nAll tasks completed after {max_iterations} iterations!")
        done_marker.unlink()
    else:
        print(f"\nReached max iterations ({max_iterations}) without completing all tasks.")
        print("Run again with a higher --max-iterations value.")


def cmd_dashboard():
    """Interactive dashboard showing live agent status."""
    try:
        while True:
            os.system("clear" if os.name != "nt" else "cls")
            print(f"Agent Swarm Dashboard — {datetime.now().strftime('%H:%M:%S')}")
            print("(Press Ctrl+C to exit)\n")
            cmd_status()

            # Show tmux sessions
            result = run("tmux ls 2>/dev/null")
            if result.returncode == 0 and result.stdout.strip():
                print("Active tmux sessions:")
                for line in result.stdout.strip().split("\n"):
                    print(f"  {line}")
            print()

            time.sleep(5)
    except KeyboardInterrupt:
        print("\nDashboard closed.")


# ============================================================================
# CLI Entry Point
# ============================================================================

def print_usage():
    print(__doc__)


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "spawn":
        if len(sys.argv) < 5:
            print("Usage: orchestrator.py spawn <task-id> <agent> <description> [model] [effort]")
            sys.exit(1)
        cmd_spawn(
            task_id=sys.argv[2],
            agent_type=sys.argv[3],
            description=sys.argv[4],
            model=sys.argv[5] if len(sys.argv) > 5 else "",
            effort=sys.argv[6] if len(sys.argv) > 6 else "medium",
        )

    elif command == "status":
        cmd_status()

    elif command == "check":
        cmd_check()

    elif command == "review":
        if len(sys.argv) < 3:
            print("Usage: orchestrator.py review <pr-number> [reviewers...]")
            sys.exit(1)
        cmd_review(sys.argv[2], sys.argv[3:] if len(sys.argv) > 3 else None)

    elif command == "cleanup":
        cmd_cleanup(clean_all="--all" in sys.argv)

    elif command == "send":
        if len(sys.argv) < 4:
            print("Usage: orchestrator.py send <task-id> <message>")
            sys.exit(1)
        cmd_send(sys.argv[2], " ".join(sys.argv[3:]))

    elif command == "ralph":
        if len(sys.argv) < 3:
            print("Usage: orchestrator.py ralph <task-file> [--max-iterations=N] [--agent=claude|codex]")
            sys.exit(1)
        task_file = sys.argv[2]
        max_iter = 10
        agent = "claude"
        for arg in sys.argv[3:]:
            if arg.startswith("--max-iterations="):
                max_iter = int(arg.split("=")[1])
            elif arg.startswith("--agent="):
                agent = arg.split("=")[1]
        cmd_ralph(task_file, max_iter, agent)

    elif command == "dashboard":
        cmd_dashboard()

    elif command in ("help", "--help", "-h"):
        print_usage()

    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
