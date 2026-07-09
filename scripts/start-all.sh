#!/usr/bin/env bash
# ============================================================
# Start All Applications
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         API-2-MCP — Starting All Apps        ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# Create logs directory
mkdir -p "$ROOT_DIR/logs"

# Load .env if present
if [ -f "$ROOT_DIR/.env" ]; then
  set -a; source "$ROOT_DIR/.env"; set +a
fi

# ─── App 1: API Server ──────────────────────────────────────
echo -e "${BLUE}▶ Starting App 1 — Library API Server (port 8001)…${NC}"
cd "$ROOT_DIR/app1-api-server"
if [ ! -d "venv" ]; then
  python3 -m venv venv
  ./venv/bin/pip install -q -r requirements.txt
fi
nohup ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8001 \
  > "$ROOT_DIR/logs/app1.log" 2>&1 &
echo $! > "$ROOT_DIR/logs/app1.pid"
echo -e "  ${GREEN}✓ App 1 PID: $(cat "$ROOT_DIR/logs/app1.pid")${NC}"

# ─── App 2: API Client ──────────────────────────────────────
echo -e "${BLUE}▶ Starting App 2 — API Client (port 8002)…${NC}"
cd "$ROOT_DIR/app2-api-client"
if [ ! -d "venv" ]; then
  python3 -m venv venv
  ./venv/bin/pip install -q -r requirements.txt
fi
nohup ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8002 \
  > "$ROOT_DIR/logs/app2.log" 2>&1 &
echo $! > "$ROOT_DIR/logs/app2.pid"
echo -e "  ${GREEN}✓ App 2 PID: $(cat "$ROOT_DIR/logs/app2.pid")${NC}"

# ─── App 3: MCP Server ──────────────────────────────────────
echo -e "${BLUE}▶ Starting App 3 — MCP Server (port 8003)…${NC}"
cd "$ROOT_DIR/app3-mcp-server"
if [ ! -d "node_modules" ]; then
  npm install --silent
fi
if [ ! -d "build" ]; then
  npm run build --silent
fi
nohup node build/index.js \
  > "$ROOT_DIR/logs/app3.log" 2>&1 &
echo $! > "$ROOT_DIR/logs/app3.pid"
echo -e "  ${GREEN}✓ App 3 PID: $(cat "$ROOT_DIR/logs/app3.pid")${NC}"

# ─── App 4: Mock Agent ──────────────────────────────────────
echo -e "${BLUE}▶ Starting App 4 — Mock Agent (port 8004)…${NC}"
cd "$ROOT_DIR/app4-mock-agent"
if [ ! -d "venv" ]; then
  python3 -m venv venv
  ./venv/bin/pip install -q -r requirements.txt
fi
nohup ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8004 \
  > "$ROOT_DIR/logs/app4.log" 2>&1 &
echo $! > "$ROOT_DIR/logs/app4.pid"
echo -e "  ${GREEN}✓ App 4 PID: $(cat "$ROOT_DIR/logs/app4.pid")${NC}"

# Wait for services to start
echo ""
echo -e "${YELLOW}⏳ Waiting for services to start…${NC}"
sleep 4

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              Applications Ready              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}📚 App 1 — Library API Server${NC}"
echo -e "     URL: ${BLUE}http://localhost:8001${NC}"
echo -e "     Swagger: ${BLUE}http://localhost:8001/docs${NC}"
echo ""
echo -e "  ${GREEN}🔗 App 2 — API Client Dashboard${NC}"
echo -e "     URL: ${BLUE}http://localhost:8002${NC}"
echo ""
echo -e "  ${GREEN}⚙️  App 3 — MCP Server Dashboard${NC}"
echo -e "     URL: ${BLUE}http://localhost:8003${NC}"
echo -e "     MCP SSE: ${BLUE}http://localhost:8003/mcp/sse${NC}"
echo ""
echo -e "  ${GREEN}🤖 App 4 — Mock AI Agent${NC}"
echo -e "     URL: ${BLUE}http://localhost:8004${NC}"
echo ""
echo -e "Logs: ${YELLOW}$ROOT_DIR/logs/${NC}"
echo -e "To stop: ${YELLOW}./scripts/stop-all.sh${NC}"
