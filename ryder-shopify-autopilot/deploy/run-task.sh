#!/usr/bin/env bash
# Run one Ryder pipeline task headless with Claude Code.
# Usage: run-task.sh drafter|autopilot|index-watch
# Called by cron (see crontab.txt). Never prints credentials.
set -euo pipefail

TASK="${1:?usage: run-task.sh drafter|autopilot|index-watch}"
ROOT="${RYDER_ROOT:-$HOME/CodingStudio}"
DEPLOY="$ROOT/ryder-shopify-autopilot/deploy"
PROMPT_FILE="$DEPLOY/prompts/$TASK.md"
LOG_DIR="$HOME/ryder-logs"
STAMP="$(date +%Y-%m-%d_%H%M)"
SCRATCH="$HOME/ryder-scratch/$TASK-$STAMP"
LOG="$LOG_DIR/$TASK-$STAMP.log"

[ -f "$PROMPT_FILE" ] || { echo "no prompt for task '$TASK'" >&2; exit 64; }
mkdir -p "$LOG_DIR" "$SCRATCH"

# Claude auth (CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY), PATH for node.
# shellcheck disable=SC1091
[ -f "$HOME/.ryder-claude.env" ] && set -a && . "$HOME/.ryder-claude.env" && set +a
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# One pipeline task at a time: a drafter run still going when the publisher
# fires makes the publisher wait (up to 50 min) instead of racing it.
exec 9>"$HOME/.ryder-pipeline.lock"
if ! flock -w 3000 9; then
  echo "$(date '+%Y-%m-%dT%H:%M:%S%z') $TASK skipped: previous task still holds the lock" >>"$LOG_DIR/skipped.log"
  exit 75
fi

# Pick up workflow changes pushed to GitHub. Local drafts are untracked and
# unaffected; a failed pull keeps the current checkout.
git -C "$ROOT" pull --ff-only --quiet || echo "git pull failed; running current checkout" >>"$LOG"

PROMPT="Scratch directory for this run (use it wherever the instructions say <scratch> or session scratchpad): $SCRATCH
This run is on the Ryder cloud server, started by cron at $(date '+%Y-%m-%d %H:%M %Z'). No human is watching.

$(sed "s#{{ROOT}}#$ROOT#g" "$PROMPT_FILE")"

cd "$ROOT"
{
  echo "=== $TASK start $(date '+%Y-%m-%dT%H:%M:%S%z')"
  rc=0
  claude -p "$PROMPT" \
    --permission-mode acceptEdits \
    --allowedTools "Bash Read Write Edit Glob Grep WebSearch WebFetch Skill" \
    --output-format text || rc=$?
  echo "=== $TASK end $(date '+%Y-%m-%dT%H:%M:%S%z') exit $rc"
} >>"$LOG" 2>&1

# Keep 30 days of logs and scratch.
find "$LOG_DIR" -name '*.log' -mtime +30 -delete 2>/dev/null || true
find "$HOME/ryder-scratch" -mindepth 1 -maxdepth 1 -mtime +30 -exec rm -rf {} + 2>/dev/null || true
