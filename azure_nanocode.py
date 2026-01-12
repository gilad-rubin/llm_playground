#!/usr/bin/env python3
"""azure_nanocode - minimal agentic coding assistant for Azure OpenAI (GPT 5.2)

A single-file agentic coding assistant that enables end-to-end coding workflows
using Azure OpenAI's GPT 5.2 model with function calling.

Usage:
    export AZURE_OPENAI_API_KEY="your-key"
    export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
    export AZURE_OPENAI_DEPLOYMENT="gpt-52"  # your deployment name
    python azure_nanocode.py

Commands:
    /c  - Clear conversation history
    /q  - Quit (or type 'exit')
"""

import glob as globlib
import json
import os
import re
import subprocess
import urllib.request
import ssl

# Azure OpenAI Configuration
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-52")
AZURE_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")

# ANSI colors for terminal output
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = "\033[34m", "\033[36m", "\033[32m", "\033[33m", "\033[31m"


# --- Tool implementations ---


def read(args: dict) -> str:
    """Read file contents with line numbers."""
    path = args["path"]
    if not os.path.isfile(path):
        return f"error: '{path}' is not a file or does not exist"
    lines = open(path).readlines()
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


def write(args: dict) -> str:
    """Write content to a file."""
    path = args["path"]
    content = args["content"]
    # Create parent directories if they don't exist
    parent_dir = os.path.dirname(path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return "ok"


def edit(args: dict) -> str:
    """Replace old string with new string in file."""
    path = args["path"]
    if not os.path.isfile(path):
        return f"error: '{path}' does not exist"
    text = open(path).read()
    old, new = args["old"], args["new"]
    if old not in text:
        return "error: old_string not found in file"
    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique (use all=true to replace all)"
    replacement = text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
    with open(path, "w") as f:
        f.write(replacement)
    return "ok"


def glob(args: dict) -> str:
    """Find files matching a glob pattern, sorted by modification time."""
    base_path = args.get("path", ".")
    pattern = (base_path + "/" + args["pattern"]).replace("//", "/")
    files = globlib.glob(pattern, recursive=True)
    files = sorted(
        files,
        key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
        reverse=True,
    )
    return "\n".join(files[:100]) or "no files found"


def grep(args: dict) -> str:
    """Search files for a regex pattern."""
    try:
        pattern = re.compile(args["pattern"])
    except re.error as e:
        return f"error: invalid regex pattern - {e}"
    base_path = args.get("path", ".")
    hits = []
    for filepath in globlib.glob(base_path + "/**", recursive=True):
        if not os.path.isfile(filepath):
            continue
        try:
            for line_num, line in enumerate(open(filepath, errors="ignore"), 1):
                if pattern.search(line):
                    hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
                    if len(hits) >= 50:
                        break
        except Exception:
            pass
        if len(hits) >= 50:
            break
    return "\n".join(hits) or "no matches found"


def bash(args: dict) -> str:
    """Execute a shell command."""
    cmd = args["command"]
    timeout = args.get("timeout", 60)
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        output = (result.stdout + result.stderr).strip()
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return f"error: command timed out after {timeout}s"
    except Exception as e:
        return f"error: {e}"


def ls(args: dict) -> str:
    """List directory contents."""
    path = args.get("path", ".")
    if not os.path.isdir(path):
        return f"error: '{path}' is not a directory"
    try:
        entries = os.listdir(path)
        result = []
        for entry in sorted(entries):
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                result.append(f"{entry}/")
            else:
                size = os.path.getsize(full_path)
                result.append(f"{entry} ({size} bytes)")
        return "\n".join(result) or "(empty directory)"
    except Exception as e:
        return f"error: {e}"


# --- Tool definitions for OpenAI function calling ---

TOOLS = {
    "read": {
        "description": "Read a file's contents with line numbers. Use this to view source code or text files.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read"},
                "offset": {"type": "integer", "description": "Starting line number (0-indexed, default: 0)"},
                "limit": {"type": "integer", "description": "Maximum number of lines to read (default: all)"},
            },
            "required": ["path"],
        },
        "fn": read,
    },
    "write": {
        "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["path", "content"],
        },
        "fn": write,
    },
    "edit": {
        "description": "Replace a specific string in a file. The old string must be unique unless all=true.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to edit"},
                "old": {"type": "string", "description": "The exact string to find and replace"},
                "new": {"type": "string", "description": "The string to replace it with"},
                "all": {"type": "boolean", "description": "If true, replace all occurrences (default: false)"},
            },
            "required": ["path", "old", "new"],
        },
        "fn": edit,
    },
    "glob": {
        "description": "Find files matching a glob pattern (e.g., '**/*.py'). Results sorted by modification time.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern to match (e.g., '**/*.py', 'src/*.js')"},
                "path": {"type": "string", "description": "Base directory to search from (default: current dir)"},
            },
            "required": ["pattern"],
        },
        "fn": glob,
    },
    "grep": {
        "description": "Search files for lines matching a regex pattern. Returns matching lines with file paths.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "description": "Base directory to search from (default: current dir)"},
            },
            "required": ["pattern"],
        },
        "fn": grep,
    },
    "bash": {
        "description": "Execute a shell command. Use for running scripts, git commands, tests, builds, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default: 60)"},
            },
            "required": ["command"],
        },
        "fn": bash,
    },
    "ls": {
        "description": "List contents of a directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list (default: current dir)"},
            },
            "required": [],
        },
        "fn": ls,
    },
}


def run_tool(name: str, args: dict) -> str:
    """Execute a tool by name with given arguments."""
    if name not in TOOLS:
        return f"error: unknown tool '{name}'"
    try:
        return TOOLS[name]["fn"](args)
    except Exception as err:
        return f"error: {err}"


def make_openai_tools_schema() -> list:
    """Generate OpenAI function calling schema from tool definitions."""
    result = []
    for name, tool_def in TOOLS.items():
        result.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool_def["description"],
                "parameters": tool_def["parameters"],
            },
        })
    return result


def call_azure_openai(messages: list, system_prompt: str) -> dict:
    """Call Azure OpenAI API with messages and tools."""
    if not AZURE_ENDPOINT or not AZURE_API_KEY:
        raise ValueError(
            "Missing Azure OpenAI configuration. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables."
        )

    # Construct the API URL
    url = f"{AZURE_ENDPOINT.rstrip('/')}/openai/deployments/{AZURE_DEPLOYMENT}/chat/completions?api-version={AZURE_API_VERSION}"

    # Build the request payload
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    payload = {
        "messages": full_messages,
        "tools": make_openai_tools_schema(),
        "tool_choice": "auto",
        "max_tokens": 8192,
        "temperature": 0.7,
    }

    # Make the API request
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": AZURE_API_KEY,
        },
        method="POST",
    )

    # Handle SSL
    ssl_context = ssl.create_default_context()

    try:
        response = urllib.request.urlopen(request, context=ssl_context, timeout=120)
        return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise Exception(f"API error {e.code}: {error_body}")


def separator() -> str:
    """Generate a visual separator line."""
    try:
        width = min(os.get_terminal_size().columns, 80)
    except OSError:
        width = 80
    return f"{DIM}{'─' * width}{RESET}"


def render_markdown(text: str) -> str:
    """Basic markdown rendering for terminal output."""
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)
    # Code blocks - highlight them
    text = re.sub(r"`([^`]+)`", f"{CYAN}\\1{RESET}", text)
    return text


def truncate(text: str, max_len: int = 60) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def main():
    """Main interactive loop."""
    print(f"\n{BOLD}azure_nanocode{RESET} | {DIM}Azure OpenAI - {AZURE_DEPLOYMENT}{RESET}")
    print(f"{DIM}Working directory: {os.getcwd()}{RESET}")
    print(f"{DIM}Commands: /c (clear history), /q or exit (quit){RESET}\n")

    messages = []
    system_prompt = f"""You are an expert coding assistant with access to file system tools.
You help users write, edit, debug, and understand code.

Current working directory: {os.getcwd()}

Guidelines:
- Use tools to explore and modify the codebase
- Read files before making edits to understand context
- Make minimal, focused changes
- Explain your actions concisely
- Use bash for running tests, git operations, and other commands
- When creating files, ensure parent directories exist"""

    while True:
        try:
            print(separator())
            user_input = input(f"{BOLD}{BLUE}>{RESET} ").strip()
            print(separator())

            if not user_input:
                continue

            if user_input.lower() in ("/q", "exit", "quit"):
                print(f"{GREEN}Goodbye!{RESET}")
                break

            if user_input == "/c":
                messages = []
                print(f"{GREEN}Conversation history cleared.{RESET}")
                continue

            # Add user message
            messages.append({"role": "user", "content": user_input})

            # Agentic loop: keep calling API until no more tool calls
            while True:
                response = call_azure_openai(messages, system_prompt)

                if "error" in response:
                    print(f"{RED}API Error: {response['error']}{RESET}")
                    break

                choices = response.get("choices", [])
                if not choices:
                    print(f"{RED}No response from model{RESET}")
                    break

                message = choices[0].get("message", {})
                content = message.get("content")
                tool_calls = message.get("tool_calls", [])
                finish_reason = choices[0].get("finish_reason")

                # Print text response if any
                if content:
                    print(f"\n{CYAN}●{RESET} {render_markdown(content)}")

                # Add assistant message to history
                messages.append(message)

                # Process tool calls
                if tool_calls:
                    for tool_call in tool_calls:
                        tool_id = tool_call["id"]
                        function = tool_call["function"]
                        tool_name = function["name"]

                        try:
                            tool_args = json.loads(function["arguments"])
                        except json.JSONDecodeError:
                            tool_args = {}

                        # Display tool call
                        arg_preview = ""
                        if tool_args:
                            first_arg = list(tool_args.values())[0]
                            arg_preview = truncate(str(first_arg), 50)

                        print(f"\n{GREEN}● {tool_name}{RESET}({DIM}{arg_preview}{RESET})")

                        # Execute tool
                        result = run_tool(tool_name, tool_args)

                        # Display result preview
                        result_lines = result.split("\n")
                        preview = truncate(result_lines[0], 60)
                        if len(result_lines) > 1:
                            preview += f" ... +{len(result_lines) - 1} lines"

                        print(f"  {DIM}└ {preview}{RESET}")

                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": result,
                        })

                # Check if we should continue the loop
                if not tool_calls or finish_reason == "stop":
                    break

            print()

        except KeyboardInterrupt:
            print(f"\n{YELLOW}Interrupted{RESET}")
            continue
        except EOFError:
            print(f"\n{GREEN}Goodbye!{RESET}")
            break
        except Exception as err:
            print(f"{RED}Error: {err}{RESET}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
