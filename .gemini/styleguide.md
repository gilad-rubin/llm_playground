# Code Review Style Guide

## Python
- Follow PEP 8 conventions
- Use type hints for function signatures
- Prefer f-strings over .format() or % formatting
- Use pathlib.Path over os.path when possible
- Keep functions focused and under 50 lines
- Use docstrings for public functions

## General
- No hardcoded secrets or API keys
- Prefer explicit over implicit
- Error messages should be actionable
- Tests should cover edge cases, not just happy paths
- Log files should never contain sensitive data
