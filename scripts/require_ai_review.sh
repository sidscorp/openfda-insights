#!/usr/bin/env bash
# Commit-msg hook: require Reviewed-by header for AI agent approval
# Usage: require_ai_review.sh <commit-msg-file>

# Path to commit message file
MSG_FILE="$1"

if ! grep -qE '^Reviewed-by: ' "$MSG_FILE"; then
  echo "error: Missing 'Reviewed-by: <agent>' header."
  echo "Please obtain AI agent approval and add a 'Reviewed-by: <agent>' line to your commit message."
  exit 1
fi
exit 0