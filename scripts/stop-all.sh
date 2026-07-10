#!/usr/bin/env bash
# ============================================================
# Stop All Applications
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}◼ Stopping all API-2-MCP applications…${NC}"
echo ""

# Port map: app index → port
declare -A APP_PORTS=([1]=8001 [2]=8002 [3]=8003 [4]=8004)

kill_by_port() {
  local port=$1
  local pids
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill 2>/dev/null || true
    return 0
  fi
  return 1
}

for i in 1 2 3 4; do
  PORT="${APP_PORTS[$i]}"
  PID_FILE="$ROOT_DIR/logs/app${i}.pid"
  stopped=false

  # Kill by PID file first
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      kill "$PID"
      stopped=true
    fi
    rm -f "$PID_FILE"
  fi

  # Also kill anything still bound to the port (catches orphaned processes)
  if kill_by_port "$PORT"; then
    stopped=true
  fi

  if $stopped; then
    echo -e "  ${GREEN}✓ App ${i} stopped (port $PORT)${NC}"
  else
    echo -e "  ${YELLOW}~ App ${i} was not running (port $PORT)${NC}"
  fi
done

echo ""
echo -e "${GREEN}All applications stopped.${NC}"
