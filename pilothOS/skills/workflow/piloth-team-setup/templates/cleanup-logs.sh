#!/usr/bin/env bash
# Delete execution logs for a completed task
TASK_ID="$1"
[ -z "$TASK_ID" ] && { echo "Usage: $0 <task-id>"; exit 1; }
rm -rf "plans/execution-logs/$TASK_ID"
echo "Cleaned execution logs for $TASK_ID"
