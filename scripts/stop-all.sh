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

for i in 1 2 3 4; do
  PID_FILE="$ROOT_DIR/logs/app${i}.pid"
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      kill "$PID"
      echo -e "  ${GREEN}✓ App ${i} stopped (PID $PID)${NC}"
    else
      echo -e "  ${YELLOW}~ App ${i} was not running${NC}"
    fi
    rm -f "$PID_FILE"
  else
    echo -e "  ${YELLOW}~ App ${i} — no PID file found${NC}"
  fi
done

echo ""
echo -e "${GREEN}All applications stopped.${NC}"
