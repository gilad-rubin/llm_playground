#!/usr/bin/env python3
"""azure_nanocode - agentic coding assistant for Azure OpenAI (GPT 5.2)

A single-file agentic coding assistant that enables end-to-end coding workflows
using Azure OpenAI's GPT 5.2 model with function calling.

Key insights from recent research on agentic coding (2025):
- "An agent is an LLM running tools in a loop to achieve a goal" - Simon Willison
- Minimal tool sets work better than many tools (ghuntley.com/agent)
- Plan before action improves results significantly
- Leave mistakes in context - models learn from them
- Clear context between unrelated tasks

Usage:
    pip install rich
    export AZURE_OPENAI_API_KEY="your-key"
    export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
    export AZURE_OPENAI_DEPLOYMENT="gpt-52"
    python azure_nanocode.py

Commands:
    /c      - Clear conversation history
    /q      - Quit (or 'exit')
    /tokens - Show token usage stats
    /help   - Show available commands
"""

import glob as globlib
import json
import os
import re
import subprocess
import urllib.request
import ssl
import time
from datetime import datetime

# Rich imports for beautiful terminal output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt
    from rich.text import Text
    from rich.rule import Rule
    from rich.live import Live
    from rich.status import Status
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: 'rich' library not installed. Install with: pip install rich")
    print("Falling back to basic output.\n")

# Initialize Rich console
console = Console() if RICH_AVAILABLE else None

# Azure OpenAI Configuration
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-52")
AZURE_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")

# Token tracking
token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


# --- Tool implementations (5 core primitives + extras) ---


def read(args: dict) -> str:
    """Read file contents with line numbers."""
    path = args["path"]
    if not os.path.isfile(path):
        return f"error: '{path}' is not a file or does not exist"
    try:
        with open(path, "r", errors="replace") as f:
            lines = f.readlines()
        offset = args.get("offset") or 0
        limit = args.get("limit") or len(lines)
        selected = lines[offset : offset + limit]
        result = "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))
        if len(lines) > offset + limit:
            result += f"\n... ({len(lines) - offset - limit} more lines)"
        return result or "(empty file)"
    except Exception as e:
        return f"error: {e}"


def write(args: dict) -> str:
    """Write content to a file."""
    path = args["path"]
    content = args["content"]
    # Create parent directories if needed
    parent_dir = os.path.dirname(path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return f"ok - wrote {len(content)} bytes to {path}"


def edit(args: dict) -> str:
    """Replace old string with new string in file."""
    path = args["path"]
    if not os.path.isfile(path):
        return f"error: '{path}' does not exist"
    with open(path, "r", errors="replace") as f:
        text = f.read()
    old, new = args["old"], args["new"]
    if old not in text:
        return "error: old_string not found in file. Read the file first to see exact content."
    count = text.count(old)
    replace_all = args.get("all") or False
    if not replace_all and count > 1:
        return f"error: old_string appears {count} times, must be unique (set all=true to replace all)"
    replacement = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    with open(path, "w") as f:
        f.write(replacement)
    return f"ok - replaced {'all ' + str(count) + ' occurrences' if replace_all else '1 occurrence'}"


def glob(args: dict) -> str:
    """Find files matching a glob pattern."""
    base_path = args.get("path") or "."
    pattern = (base_path + "/" + args["pattern"]).replace("//", "/")
    files = globlib.glob(pattern, recursive=True)
    # Filter out directories and sort by modification time
    files = [f for f in files if os.path.isfile(f)]
    files = sorted(files, key=lambda f: os.path.getmtime(f), reverse=True)
    if not files:
        return "no files found"
    result = "\n".join(files[:100])
    if len(files) > 100:
        result += f"\n... and {len(files) - 100} more files"
    return result


def grep(args: dict) -> str:
    """Search files for a regex pattern (like ripgrep)."""
    try:
        pattern = re.compile(args["pattern"])
    except re.error as e:
        return f"error: invalid regex - {e}"
    base_path = args.get("path") or "."
    hits = []
    file_count = 0
    for filepath in globlib.glob(base_path + "/**", recursive=True):
        if not os.path.isfile(filepath):
            continue
        # Skip binary files and common non-text
        if any(filepath.endswith(ext) for ext in ['.pyc', '.so', '.o', '.a', '.bin', '.exe', '.dll', '.png', '.jpg', '.gif', '.pdf', '.zip', '.tar', '.gz']):
            continue
        file_count += 1
        try:
            with open(filepath, "r", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    if pattern.search(line):
                        hits.append(f"{filepath}:{line_num}:{line.rstrip()[:200]}")
                        if len(hits) >= 50:
                            break
        except Exception:
            pass
        if len(hits) >= 50:
            break
    if not hits:
        return f"no matches found (searched {file_count} files)"
    result = "\n".join(hits)
    if len(hits) == 50:
        result += "\n... (truncated at 50 matches)"
    return result


def bash(args: dict) -> str:
    """Execute a shell command."""
    cmd = args["command"]
    timeout = args.get("timeout") or 60
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=os.getcwd()
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        output = stdout
        if stderr:
            output = f"{stdout}\n[stderr]: {stderr}" if stdout else f"[stderr]: {stderr}"
        if result.returncode != 0:
            output = f"[exit code {result.returncode}]\n{output}"
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return f"error: command timed out after {timeout}s"
    except Exception as e:
        return f"error: {e}"


def ls(args: dict) -> str:
    """List directory contents with details."""
    path = args.get("path") or "."
    if not os.path.exists(path):
        return f"error: '{path}' does not exist"
    if not os.path.isdir(path):
        # If it's a file, show file info
        stat = os.stat(path)
        return f"{path} - {stat.st_size} bytes, modified {datetime.fromtimestamp(stat.st_mtime)}"
    try:
        entries = os.listdir(path)
        result = []
        for entry in sorted(entries):
            full_path = os.path.join(path, entry)
            try:
                if os.path.isdir(full_path):
                    result.append(f"  {entry}/")
                else:
                    size = os.path.getsize(full_path)
                    result.append(f"  {entry} ({size:,} bytes)")
            except OSError:
                result.append(f"  {entry} (access denied)")
        return "\n".join(result) if result else "(empty directory)"
    except Exception as e:
        return f"error: {e}"


# --- Tool definitions with OpenAI strict mode compliance ---
# Following OpenAI best practices: strict mode, clear descriptions, explicit boundaries

TOOLS = {
    "read": {
        "description": "Read a file's contents with line numbers. ALWAYS use this before editing a file to see its current content. Supports partial reads with offset/limit for large files.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read (relative or absolute)"},
                "offset": {"type": ["integer", "null"], "description": "Starting line number, 0-indexed. Default: 0"},
                "limit": {"type": ["integer", "null"], "description": "Max lines to read. Default: entire file"},
            },
            "required": ["path", "offset", "limit"],
            "additionalProperties": False,
        },
        "fn": read,
        "strict": True,
    },
    "write": {
        "description": "Create a new file or completely overwrite an existing file. Use 'edit' for partial modifications. Creates parent directories automatically.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path where file will be created/overwritten"},
                "content": {"type": "string", "description": "Complete content to write to the file"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        "fn": write,
        "strict": True,
    },
    "edit": {
        "description": "Replace a specific string in a file. The old_string must exactly match file content (including whitespace). Read the file first to see exact content. String must be unique unless using all=true.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to edit"},
                "old": {"type": "string", "description": "Exact string to find (must match file content precisely)"},
                "new": {"type": "string", "description": "String to replace it with"},
                "all": {"type": ["boolean", "null"], "description": "Replace all occurrences? Default: false (requires unique match)"},
            },
            "required": ["path", "old", "new", "all"],
            "additionalProperties": False,
        },
        "fn": edit,
        "strict": True,
    },
    "glob": {
        "description": "Find files matching a glob pattern. Use '**/' for recursive search. Examples: '**/*.py', 'src/**/*.ts', '*.json'. Results sorted by modification time (newest first).",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g., '**/*.py' for all Python files)"},
                "path": {"type": ["string", "null"], "description": "Base directory to search from. Default: current directory"},
            },
            "required": ["pattern", "path"],
            "additionalProperties": False,
        },
        "fn": glob,
        "strict": True,
    },
    "grep": {
        "description": "Search file contents using regex pattern (like ripgrep). Returns matching lines with file:line:content format. Use for finding function definitions, imports, usages, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for (e.g., 'def \\w+', 'import.*torch')"},
                "path": {"type": ["string", "null"], "description": "Directory to search in. Default: current directory"},
            },
            "required": ["pattern", "path"],
            "additionalProperties": False,
        },
        "fn": grep,
        "strict": True,
    },
    "bash": {
        "description": "Execute a shell command. Use for: running tests, git operations, installing packages, building projects, checking system state. Commands run in current working directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": ["integer", "null"], "description": "Timeout in seconds. Default: 60"},
            },
            "required": ["command", "timeout"],
            "additionalProperties": False,
        },
        "fn": bash,
        "strict": True,
    },
    "ls": {
        "description": "List directory contents with file sizes. Use to explore project structure. Prefer 'glob' for finding specific file types.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": ["string", "null"], "description": "Directory to list. Default: current directory"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "fn": ls,
        "strict": True,
    },
}


def run_tool(name: str, args: dict) -> str:
    """Execute a tool by name with given arguments."""
    if name not in TOOLS:
        return f"error: unknown tool '{name}'"
    try:
        return TOOLS[name]["fn"](args)
    except Exception as err:
        return f"error: {type(err).__name__}: {err}"


def make_openai_tools_schema() -> list:
    """Generate OpenAI function calling schema with strict mode."""
    result = []
    for name, tool_def in TOOLS.items():
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": tool_def["description"],
                "parameters": tool_def["parameters"],
            },
        }
        if tool_def.get("strict"):
            schema["function"]["strict"] = True
        result.append(schema)
    return result


def call_azure_openai(messages: list, system_prompt: str) -> dict:
    """Call Azure OpenAI API with messages and tools."""
    global token_usage

    if not AZURE_ENDPOINT or not AZURE_API_KEY:
        raise ValueError(
            "Missing Azure OpenAI configuration.\n"
            "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables."
        )

    url = f"{AZURE_ENDPOINT.rstrip('/')}/openai/deployments/{AZURE_DEPLOYMENT}/chat/completions?api-version={AZURE_API_VERSION}"
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    payload = {
        "messages": full_messages,
        "tools": make_openai_tools_schema(),
        "tool_choice": "auto",
        "max_tokens": 8192,
        "temperature": 0.7,
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": AZURE_API_KEY,
        },
        method="POST",
    )

    ssl_context = ssl.create_default_context()

    # Retry logic with exponential backoff
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = urllib.request.urlopen(request, context=ssl_context, timeout=120)
            data = json.loads(response.read().decode("utf-8"))

            # Track token usage
            if "usage" in data:
                usage = data["usage"]
                token_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                token_usage["completion_tokens"] += usage.get("completion_tokens", 0)
                token_usage["total_tokens"] += usage.get("total_tokens", 0)

            return data
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            if e.code == 429 and attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 1)
                if RICH_AVAILABLE:
                    console.print(f"[yellow]Rate limited. Waiting {wait_time}s...[/yellow]")
                time.sleep(wait_time)
                continue
            raise Exception(f"API error {e.code}: {error_body}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def print_rich(content: str, style: str = ""):
    """Print with Rich if available, otherwise plain."""
    if RICH_AVAILABLE:
        console.print(content, style=style)
    else:
        print(content)


def print_tool_call(name: str, args: dict):
    """Display a tool call with Rich formatting."""
    arg_preview = ""
    if args:
        first_key = list(args.keys())[0]
        first_val = str(args[first_key])[:50]
        if len(str(args[first_key])) > 50:
            first_val += "..."
        arg_preview = f"{first_key}={first_val}"

    if RICH_AVAILABLE:
        console.print(f"  [green]●[/green] [bold]{name}[/bold]([dim]{arg_preview}[/dim])")
    else:
        print(f"  ● {name}({arg_preview})")


def print_tool_result(result: str):
    """Display tool result with Rich formatting."""
    lines = result.split("\n")
    preview = lines[0][:70]
    if len(lines[0]) > 70:
        preview += "..."
    if len(lines) > 1:
        preview += f" (+{len(lines) - 1} lines)"

    if RICH_AVAILABLE:
        console.print(f"    [dim]└ {preview}[/dim]")
    else:
        print(f"    └ {preview}")


def print_assistant_message(content: str):
    """Display assistant message with Rich markdown rendering."""
    if RICH_AVAILABLE:
        console.print()
        console.print(Panel(Markdown(content), border_style="cyan", padding=(0, 1)))
    else:
        print(f"\n{content}")


def show_help():
    """Display available commands."""
    if RICH_AVAILABLE:
        table = Table(title="Commands", show_header=True, header_style="bold")
        table.add_column("Command", style="cyan")
        table.add_column("Description")
        table.add_row("/c", "Clear conversation history")
        table.add_row("/tokens", "Show token usage statistics")
        table.add_row("/help", "Show this help message")
        table.add_row("/q, exit", "Quit the assistant")
        table.add_row("Ctrl+C", "Interrupt current operation")
        console.print(table)
    else:
        print("Commands: /c (clear), /tokens (usage), /help, /q or exit (quit)")


def show_tokens():
    """Display token usage statistics."""
    if RICH_AVAILABLE:
        table = Table(title="Token Usage", show_header=True)
        table.add_column("Type", style="cyan")
        table.add_column("Count", justify="right")
        table.add_row("Prompt", f"{token_usage['prompt_tokens']:,}")
        table.add_row("Completion", f"{token_usage['completion_tokens']:,}")
        table.add_row("Total", f"{token_usage['total_tokens']:,}")
        console.print(table)
    else:
        print(f"Tokens - Prompt: {token_usage['prompt_tokens']}, Completion: {token_usage['completion_tokens']}, Total: {token_usage['total_tokens']}")


def show_banner():
    """Display startup banner."""
    if RICH_AVAILABLE:
        console.print()
        console.print(Panel(
            f"[bold cyan]azure_nanocode[/bold cyan]\n"
            f"[dim]Azure OpenAI • {AZURE_DEPLOYMENT}[/dim]\n"
            f"[dim]Working directory: {os.getcwd()}[/dim]",
            subtitle="[dim]/help for commands[/dim]",
            border_style="blue"
        ))
        console.print()
    else:
        print(f"\nazure_nanocode | Azure OpenAI - {AZURE_DEPLOYMENT}")
        print(f"Working directory: {os.getcwd()}")
        print("Commands: /help\n")


# System prompt based on best practices from ghuntley.com/agent and research
SYSTEM_PROMPT_TEMPLATE = """You are an expert coding assistant with access to file system tools.

Current working directory: {cwd}
Operating system: {os_type}

## Your Approach
1. **Plan first**: Before making changes, understand the codebase structure and the user's goal
2. **Read before edit**: ALWAYS read a file before modifying it to see exact content
3. **Minimal changes**: Make focused, surgical edits - don't refactor unrelated code
4. **Verify results**: After making changes, verify they work (run tests, check syntax)
5. **Learn from errors**: If something fails, analyze the error and adjust your approach

## Tool Usage Guidelines
- Use `ls` and `glob` to explore project structure
- Use `grep` to find specific code patterns, function definitions, usages
- Use `read` to view file contents before any edit
- Use `edit` for surgical changes to existing files (requires exact string match)
- Use `write` only for new files or complete rewrites
- Use `bash` for running tests, git operations, builds, and system commands

## Important Rules
- Check if directories exist before creating files in them
- Preserve existing code style and patterns
- Don't add unnecessary comments or documentation
- Keep explanations concise and actionable"""


def main():
    """Main interactive loop."""
    show_banner()

    messages = []
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        cwd=os.getcwd(),
        os_type="Windows" if os.name == "nt" else "Unix/Linux/macOS"
    )

    iteration_count = 0

    while True:
        try:
            # Get user input
            if RICH_AVAILABLE:
                console.print(Rule(style="dim"))
                user_input = Prompt.ask("[bold blue]>[/bold blue]").strip()
            else:
                print("-" * 60)
                user_input = input("> ").strip()

            if not user_input:
                continue

            # Handle commands
            cmd = user_input.lower()
            if cmd in ("/q", "exit", "quit"):
                print_rich("[green]Goodbye![/green]" if RICH_AVAILABLE else "Goodbye!")
                break
            if cmd == "/c":
                messages = []
                iteration_count = 0
                print_rich("[green]Conversation history cleared.[/green]" if RICH_AVAILABLE else "Conversation history cleared.")
                continue
            if cmd == "/tokens":
                show_tokens()
                continue
            if cmd == "/help":
                show_help()
                continue

            # Add user message
            messages.append({"role": "user", "content": user_input})

            # Agentic loop
            loop_iteration = 0
            max_iterations = 25  # Safety limit

            while loop_iteration < max_iterations:
                loop_iteration += 1
                iteration_count += 1

                # Show spinner while waiting for API
                if RICH_AVAILABLE:
                    with Status("[cyan]Thinking...[/cyan]", spinner="dots"):
                        response = call_azure_openai(messages, system_prompt)
                else:
                    print("Thinking...")
                    response = call_azure_openai(messages, system_prompt)

                if "error" in response:
                    print_rich(f"[red]API Error: {response['error']}[/red]" if RICH_AVAILABLE else f"API Error: {response['error']}")
                    break

                choices = response.get("choices", [])
                if not choices:
                    print_rich("[red]No response from model[/red]" if RICH_AVAILABLE else "No response from model")
                    break

                message = choices[0].get("message", {})
                content = message.get("content")
                tool_calls = message.get("tool_calls", [])
                finish_reason = choices[0].get("finish_reason")

                # Print text response
                if content:
                    print_assistant_message(content)

                # Add assistant message to history
                messages.append(message)

                # Process tool calls
                if tool_calls:
                    completed_tool_ids = set()
                    interrupted = False
                    try:
                        for tool_call in tool_calls:
                            tool_id = tool_call["id"]
                            function = tool_call["function"]
                            tool_name = function["name"]

                            try:
                                tool_args = json.loads(function["arguments"])
                            except json.JSONDecodeError:
                                tool_args = {}

                            print_tool_call(tool_name, tool_args)
                            result = run_tool(tool_name, tool_args)
                            print_tool_result(result)

                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_id,
                                "content": result,
                            })
                            completed_tool_ids.add(tool_id)
                    except KeyboardInterrupt:
                        interrupted = True
                        # Ensure tool call/message history remains consistent:
                        # exactly one tool result message per tool_call_id.
                        for tool_call in tool_calls:
                            tool_id = tool_call["id"]
                            if tool_id in completed_tool_ids:
                                continue
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_id,
                                "content": "error: interrupted",
                            })

                    if interrupted:
                        print_rich(
                            "\n[yellow]Interrupted during tool execution - you can type your next message or /q to quit[/yellow]"
                            if RICH_AVAILABLE
                            else "\nInterrupted during tool execution"
                        )
                        break

                # Check if done
                if not tool_calls or finish_reason == "stop":
                    break

            if loop_iteration >= max_iterations:
                print_rich("[yellow]Reached maximum iterations. Use /c to clear and start fresh.[/yellow]" if RICH_AVAILABLE else "Reached maximum iterations.")

            if RICH_AVAILABLE:
                console.print()

        except KeyboardInterrupt:
            print_rich("\n[yellow]Interrupted - type your next message or /q to quit[/yellow]" if RICH_AVAILABLE else "\nInterrupted")
            continue
        except EOFError:
            print_rich("\n[green]Goodbye![/green]" if RICH_AVAILABLE else "\nGoodbye!")
            break
        except Exception as err:
            if RICH_AVAILABLE:
                console.print_exception()
            else:
                print(f"Error: {err}")
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()
