# Quickstart Guide

## Prerequisites

- **Python 3.11+** installed
- **Node.js 20+** and npm installed
- **Ollama** installed locally (optional, for LLM-powered agent)

---

## 1. Clone / Enter the Project

```bash
cd API-2-MCP
```

## 2. One-Step Setup

Run the setup script to install all dependencies for all four applications:

```bash
./scripts/setup.sh
```

This will:
- Create Python virtual environments for Apps 1, 2, and 4
- Install Python dependencies
- Run `npm install` and compile TypeScript for App 3

## 3. Configure Environment

The setup script copies `.env.example` to `.env` automatically.
You can edit `.env` to change ports or Ollama model:

```env
# Default values — change only if you have port conflicts
API_SERVER_PORT=8001
API_CLIENT_PORT=8002
MCP_SERVER_PORT=8003
AGENT_PORT=8004

OLLAMA_MODEL=llama3.2   # Change to any installed Ollama model
```

## 4. (Optional) Pull Ollama Model

For the AI-powered agent mode in App 4:

```bash
ollama pull llama3.2
```

If Ollama or the model is unavailable, App 4 automatically falls back to a rule-based mock agent.

## 5. Start All Applications

```bash
./scripts/start-all.sh
```

## 6. Open the GUIs

| Application | URL | Description |
|-------------|-----|-------------|
| App 1 — Library API Server | http://localhost:8001 | Book catalogue CRUD dashboard |
| App 1 — Swagger UI | http://localhost:8001/docs | Interactive API documentation |
| App 2 — API Client | http://localhost:8002 | Client dashboard proxying to App 1 |
| App 3 — MCP Server | http://localhost:8003 | MCP tools registry and call log |
| App 4 — Mock Agent | http://localhost:8004 | AI agent chat interface |

## 7. Try the Demo Flow

1. **Start with App 1** — Browse the pre-loaded books, add/edit/delete via the dashboard
2. **Open App 2** — See the same books via the API client proxy; switch between table and card views
3. **Open App 3** — See the 8 MCP tools derived from App 1's API; watch tool calls arrive in real-time
4. **Open App 4** — Type a query like *"Show all Fantasy books"* and watch the agent:
   - Discover tools from the MCP server
   - Reason about which tool to call (Ollama LLM or rule-based fallback)
   - Execute the MCP call and stream each step back in real time
   - If the LLM output cannot be parsed as a valid ReAct action, App 4 automatically falls back to the rule-based mock agent and still returns a meaningful result

> **Tool Call Log (right panel)** — The panel on the right of App 4's chat interface records every MCP tool call made during the session. It is intentionally preserved when you clear the chat, so you always retain a full history of tool executions.

## 8. Stop All Applications

```bash
./scripts/stop-all.sh
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port already in use | Edit `.env` to change port numbers |
| App 3 build fails | Ensure Node.js 20+: `node --version` |
| MCP tools not found in App 4 | Make sure App 3 is running; click **↻ Refresh** in App 4 |
| Ollama not available | App 4 falls back to mock agent automatically |
| App 2 shows API offline | Make sure App 1 is running on port 8001 |

---

## Architecture Overview

```
App 4 (Agent GUI) → [MCP Protocol] → App 3 (MCP Server) → [HTTP REST] → App 1 (API Server)
App 2 (Client GUI) → [HTTP Proxy] → App 1 (API Server)
```

See [Architecture.md](./Architecture.md) for full diagrams.
