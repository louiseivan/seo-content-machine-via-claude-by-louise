#!/usr/bin/env bash
# Run on the Mac to bring server-written drafts, review notes, manifests and
# run logs back for reading. One-way server -> Mac; never deletes local files.
# Usage: pull-to-mac.sh ryder@SERVER_IP
set -euo pipefail
SRC="${1:?usage: pull-to-mac.sh ryder@SERVER_IP}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RO="$ROOT/CLAUDE OUTPUTS/Ryder One"
rsync -az "$SRC:CodingStudio/CLAUDE\ OUTPUTS/Ryder\ One/rewrites/" "$RO/rewrites/"
rsync -az "$SRC:CodingStudio/CLAUDE\ OUTPUTS/Ryder\ One/outputs/" "$RO/outputs/"
mkdir -p "$ROOT/.server-logs"
rsync -az "$SRC:ryder-logs/" "$ROOT/.server-logs/"
echo "pulled into rewrites/, outputs/ and .server-logs/"
