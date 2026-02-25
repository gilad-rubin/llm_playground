#!/usr/bin/env bash
# =============================================================================
# review-pr.sh — Trigger multi-model code review on a PR
# =============================================================================
# Usage:
#   ./review-pr.sh <pr-number> [reviewers...]
#
# Examples:
#   ./review-pr.sh 42                          # all available reviewers
#   ./review-pr.sh 42 claude codex             # specific reviewers
#
# Reviewers:
#   claude  - Claude Code review (cautious, thorough)
#   codex   - Codex review (edge cases, logic errors)
#   gemini  - Gemini Code Assist (auto-installed GitHub App)
#
# Note: Gemini Code Assist reviews are automatic if the GitHub App is
# installed. This script handles Claude and Codex manual reviews.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAWDBOT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$CLAWDBOT_DIR/logs"

PR_NUMBER="${1:?Usage: review-pr.sh <pr-number> [reviewers...]}"
shift
REVIEWERS=("${@:-claude codex}")

if [ ${#REVIEWERS[@]} -eq 0 ]; then
  REVIEWERS=("claude" "codex")
fi

mkdir -p "$LOG_DIR"

log() {
  echo "[$(date '+%H:%M:%S')] $*"
}

# -- Preflight --
if ! command -v gh >/dev/null 2>&1; then
  echo "Error: gh CLI is required. Install: https://cli.github.com/"
  exit 1
fi

# Verify PR exists
PR_INFO=$(gh pr view "$PR_NUMBER" --json title,headRefName,state,files 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "Error: PR #$PR_NUMBER not found."
  exit 1
fi

PR_TITLE=$(echo "$PR_INFO" | jq -r '.title')
PR_BRANCH=$(echo "$PR_INFO" | jq -r '.headRefName')
PR_STATE=$(echo "$PR_INFO" | jq -r '.state')

log "=== Code Review: PR #$PR_NUMBER ==="
log "Title:  $PR_TITLE"
log "Branch: $PR_BRANCH"
log "State:  $PR_STATE"
log "Reviewers: ${REVIEWERS[*]}"
log ""

# Get the diff
DIFF=$(gh pr diff "$PR_NUMBER" 2>/dev/null)
DIFF_LINES=$(echo "$DIFF" | wc -l)
log "Diff: $DIFF_LINES lines"

# Truncate large diffs
MAX_DIFF_LINES=500
if [ "$DIFF_LINES" -gt "$MAX_DIFF_LINES" ]; then
  DIFF=$(echo "$DIFF" | head -n "$MAX_DIFF_LINES")
  DIFF="${DIFF}\n\n... (diff truncated at $MAX_DIFF_LINES lines, full diff has $DIFF_LINES lines)"
  log "Warning: Diff truncated to $MAX_DIFF_LINES lines"
fi

# -- Review prompt template --
REVIEW_PROMPT="You are a senior code reviewer. Review this pull request thoroughly.

PR #$PR_NUMBER: $PR_TITLE
Branch: $PR_BRANCH

## Review Checklist
- [ ] Correctness: Logic errors, edge cases, race conditions
- [ ] Security: Injection, XSS, CSRF, insecure data handling
- [ ] Performance: Bottlenecks, memory leaks, N+1 queries
- [ ] Maintainability: Readability, naming, modularity
- [ ] Tests: Are changes adequately tested?

## Diff
\`\`\`diff
$DIFF
\`\`\`

## Instructions
1. Identify any critical issues (bugs, security, data loss)
2. Identify important improvements (performance, maintainability)
3. Note minor suggestions (style, naming)
4. Rate overall: APPROVE, REQUEST_CHANGES, or COMMENT
5. Be specific — reference file names and line numbers

Format your review as a GitHub PR comment with sections for each category."

# -- Run reviews --
for REVIEWER in "${REVIEWERS[@]}"; do
  log "Starting review by: $REVIEWER"
  REVIEW_LOG="$LOG_DIR/review-pr${PR_NUMBER}-${REVIEWER}.log"

  case "$REVIEWER" in
    claude)
      if command -v claude >/dev/null 2>&1; then
        REVIEW_OUTPUT=$(claude --dangerously-skip-permissions -p "$REVIEW_PROMPT" 2>"$REVIEW_LOG")
        if [ -n "$REVIEW_OUTPUT" ]; then
          # Post as PR comment
          gh pr comment "$PR_NUMBER" --body "## Claude Code Review

$REVIEW_OUTPUT

---
*Automated review by Claude Code*" 2>/dev/null
          log "Claude review posted to PR #$PR_NUMBER"
        else
          log "Warning: Claude review returned empty output"
        fi
      else
        log "Skipping Claude review: claude CLI not installed"
      fi
      ;;

    codex)
      if command -v codex >/dev/null 2>&1; then
        REVIEW_OUTPUT=$(codex exec "$REVIEW_PROMPT" 2>"$REVIEW_LOG")
        if [ -n "$REVIEW_OUTPUT" ]; then
          gh pr comment "$PR_NUMBER" --body "## Codex Review

$REVIEW_OUTPUT

---
*Automated review by Codex*" 2>/dev/null
          log "Codex review posted to PR #$PR_NUMBER"
        else
          log "Warning: Codex review returned empty output"
        fi
      else
        log "Skipping Codex review: codex CLI not installed"
      fi
      ;;

    gemini)
      log "Gemini Code Assist reviews are automatic via the GitHub App."
      log "Trigger manually with: comment '/gemini review' on the PR."
      if command -v gh >/dev/null 2>&1; then
        gh pr comment "$PR_NUMBER" --body "/gemini review" 2>/dev/null
        log "Triggered Gemini review via PR comment."
      fi
      ;;

    *)
      log "Unknown reviewer: $REVIEWER (skipping)"
      ;;
  esac
done

log ""
log "=== Reviews Complete ==="
log "View: gh pr view $PR_NUMBER --comments"
