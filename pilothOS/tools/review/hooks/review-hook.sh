#!/bin/sh
# Piloth Review bridge hook. Forwards a Claude Code hook event to the local
# review server so the browser can mirror activity, show status, and (optionally)
# gate tool permissions. Faithful to annotron's hook bridge design.
#
# Usage (from hooks.json):
#   review-hook.sh gate  /hook/pretool     # PreToolUse — may return a decision
#   review-hook.sh fire  /hook/posttool    # PostToolUse — fire-and-forget
#   review-hook.sh fire  /hook/notify      # Notification
#   review-hook.sh fire  /hook/stop        # Stop
#
# Design goals: zero cost when the server isn't running (curl fails fast -> allow),
# never blocks the review CLI itself, no hard dependency on jq (server parses JSON).

# Off-switch: set PILOTH_REVIEW=off (e.g. in .claude/settings.json env) to make
# this hook a complete no-op — gate returns empty (Claude's default flow) and fire
# does nothing. Default is on.
[ "${PILOTH_REVIEW:-on}" = "off" ] && exit 0

mode="$1"
endpoint="$2"
input=$(cat)

host="${REVIEW_HOST:-127.0.0.1}"
port="${REVIEW_PORT:-7321}"
url="http://$host:$port$endpoint"

if [ "$mode" = "gate" ]; then
  resp=$(printf '%s' "$input" | curl -s --max-time 185 \
    -H 'Content-Type: application/json' --data-binary @- "$url" 2>/dev/null) || exit 0
  [ -z "$resp" ] && exit 0
  printf '%s' "$resp"
  exit 0
fi

printf '%s' "$input" | curl -s --max-time 3 \
  -H 'Content-Type: application/json' --data-binary @- "$url" >/dev/null 2>&1 || true
exit 0
