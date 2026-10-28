#!/usr/bin/env bash
# Remove complete message blocks containing the Telegram join-by-link action.
set -euo pipefail

file=${1:-input/dz-semanticheskoe-prostranstvo/messages.md}
[[ -f "$file" ]] || { printf 'File not found: %s\n' "$file" >&2; exit 1; }
tmp=$(mktemp "${file}.tmp.XXXXXX")
trap 'rm -f "$tmp"' EXIT

awk '
  function flush() {
    if (index(block, "MessageActionChatJoinedByLink") == 0)
      printf "%s", block
    block = ""
  }
  /^## [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T/ { flush() }
  { block = block $0 "\n" }
  END { flush() }
' "$file" > "$tmp"

# Keep the original file permissions.
cat "$tmp" > "$file"
