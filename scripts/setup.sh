#!/usr/bin/env bash
# ============================================================
# Setup: Install all dependencies
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       API-2-MCP — Installing Dependencies    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"

# Create logs directory
mkdir -p "$ROOT_DIR/logs"

# Copy .env if not present
if [ ! -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo -e "${BLUE}  ✓ Created .env from .env.example${NC}"
fi

# App 1
echo -e "\n${BLUE}▶ Setting up App 1 (Library API Server)…${NC}"
cd "$ROOT_DIR/app1-api-server"
python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt
echo -e "${GREEN}  ✓ App 1 dependencies installed${NC}"

# App 2
echo -e "\n${BLUE}▶ Setting up App 2 (API Client)…${NC}"
cd "$ROOT_DIR/app2-api-client"
python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt
echo -e "${GREEN}  ✓ App 2 dependencies installed${NC}"

# App 3
echo -e "\n${BLUE}▶ Setting up App 3 (MCP Server)…${NC}"
cd "$ROOT_DIR/app3-mcp-server"
npm install
npm run build
echo -e "${GREEN}  ✓ App 3 dependencies installed and compiled${NC}"

# App 4
echo -e "\n${BLUE}▶ Setting up App 4 (Mock Agent)…${NC}"
cd "$ROOT_DIR/app4-mock-agent"
python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt
echo -e "${GREEN}  ✓ App 4 dependencies installed${NC}"

echo -e "\n${CYAN}✅ All dependencies installed!${NC}"
echo -e "Run: ${BLUE}./scripts/start-all.sh${NC} to start all applications"
