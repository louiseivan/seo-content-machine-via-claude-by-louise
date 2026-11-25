#!/usr/bin/env bash
# Run on Louise's Mac to copy what git does not carry to the server:
# credentials (shopify.env, GSC key), the full drafts archive (needed for
# dedup and numbering), manifests/index-watch state, and the writing skill.
# Usage: push-from-mac.sh ryder@SERVER_IP
set -euo pipefail
DEST="${1:?usage: push-from-mac.sh ryder@SERVER_IP}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RO="$ROOT/CLAUDE OUTPUTS/Ryder One"

ssh "$DEST" 'mkdir -p "$HOME/CodingStudio/CLAUDE OUTPUTS/Ryder One" "$HOME/.claude/skills"'
rsync -az \
  "$RO/shopify.env" "$RO/gsc-service-account.json" \
  "$RO/RYDER_CONTENT_SYSTEM_PROMPT.md" "$RO/CONTENT-MACHINE-SETUP.md" \
  "$DEST:CodingStudio/CLAUDE\ OUTPUTS/Ryder\ One/"
rsync -az "$RO/rewrites" "$RO/outputs" \
  "$DEST:CodingStudio/CLAUDE\ OUTPUTS/Ryder\ One/"
[ -d "$HOME/.claude/skills/humanize-writing" ] && \
  rsync -az "$HOME/.claude/skills/humanize-writing" "$DEST:.claude/skills/"
ssh "$DEST" 'chmod 600 "$HOME/CodingStudio/CLAUDE OUTPUTS/Ryder One/shopify.env" "$HOME/CodingStudio/CLAUDE OUTPUTS/Ryder One/gsc-service-account.json"'
echo "copied. Secrets are chmod 600 on the server."
