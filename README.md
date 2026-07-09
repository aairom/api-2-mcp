# API-2-MCP

> A four-application demo showcasing the journey from REST API → API Client → MCP Server → AI Agent

## Overview

This project demonstrates how traditional REST APIs can be transformed into MCP (Model Context Protocol) tools, enabling AI agents to interact with real data sources through a standardized protocol.

### The Four Applications

| # | App | Port | Description |
|---|-----|------|-------------|
| 1 | **Library API Server** | 8001 | FastAPI REST server with 10 endpoints for library book management (CRUD, borrow/return) |
| 2 | **API Client** | 8002 | Python client app that consumes App 1 via HTTP proxy, with a rich dashboard GUI |
| 3 | **MCP Server** | 8003 | Node.js server that transforms App 1's REST endpoints into 8 MCP tools |
| 4 | **Mock AI Agent** | 8004 | Python agent with a chat GUI that discovers and calls MCP tools using Ollama LLM |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Browsers                            │
└─────┬──────────────┬──────────────┬──────────────┬─────────────┘
      │              │              │              │
  :8001          :8002          :8003          :8004
  App 1          App 2          App 3          App 4
  API Server     Client         MCP Server     Agent GUI
  (FastAPI)      (FastAPI)      (Node.js)      (FastAPI+WS)
      ▲              │              │              │
      │         HTTP Proxy          │         WebSocket
      │              ▼              │              │
      └──────────────┘         MCP Protocol       │
      ▲                             │              │
      └─────────────────────────────┘              │
           HTTP REST API calls               Ollama LLM
           (list_books, get_book, etc)    (llama3.2 local)
```

---

## Quick Start

```bash
# 1. Install all dependencies
./scripts/setup.sh

# 2. (Optional) Pull Ollama model for AI-powered agent
ollama pull llama3.2

# 3. Start all applications
./scripts/start-all.sh

# 4. Open the GUIs
open http://localhost:8001   # Library API Server + Swagger
open http://localhost:8002   # API Client Dashboard
open http://localhost:8003   # MCP Server Dashboard
open http://localhost:8004   # Mock AI Agent Chat
```

See [Docs/Quickstart.md](Docs/Quickstart.md) for detailed setup instructions.

---

## MCP Tools Exposed (App 3)

The MCP Server transforms 10 REST endpoints into 8 AI-callable tools:

| MCP Tool | REST Mapping | Description |
|----------|-------------|-------------|
| `list_books` | `GET /books` | List books with genre/available/search filters |
| `get_book` | `GET /books/{id}` | Get a specific book by ID |
| `create_book` | `POST /books` | Add a new book to the library |
| `update_book` | `PUT /books/{id}` | Update book details |
| `delete_book` | `DELETE /books/{id}` | Remove a book |
| `borrow_book` | `POST /books/{id}/borrow` | Mark a book as borrowed |
| `return_book` | `POST /books/{id}/return` | Mark a book as returned |
| `list_genres` | `GET /genres` | Get all available genres |

---

## Agent Example Queries

When using App 4, try these natural language queries:

- *"Show all Fantasy books"*
- *"What books are currently available?"*
- *"Find books about space or science fiction"*
- *"What genres are in the library?"*
- *"Add a new book: AI Revolution by Sam Altman, genre Technology, year 2024"*
- *"Show me borrowed books"*

---

## Project Structure

```
API-2-MCP/
├── app1-api-server/        # FastAPI Library REST API
│   ├── main.py
│   ├── requirements.txt
│   └── templates/index.html
├── app2-api-client/        # FastAPI API Client with Dashboard
│   ├── main.py
│   ├── requirements.txt
│   └── templates/index.html
├── app3-mcp-server/        # Node.js MCP Server
│   ├── src/index.ts
│   ├── package.json
│   └── tsconfig.json
├── app4-mock-agent/        # FastAPI AI Agent with Chat GUI
│   ├── main.py
│   ├── requirements.txt
│   └── templates/index.html
├── scripts/
│   ├── setup.sh            # Install all dependencies
│   ├── start-all.sh        # Launch all apps in background
│   └── stop-all.sh         # Gracefully stop all apps
├── Docs/
│   ├── Architecture.md     # Mermaid architecture diagrams
│   └── Quickstart.md       # Detailed setup guide
├── .env.example            # Environment variable template
└── README.md
```

---

## Tech Stack

- **App 1 & 2 & 4**: Python 3.11+, FastAPI, Uvicorn, httpx
- **App 3**: Node.js 20+, TypeScript, Express, @modelcontextprotocol/sdk
- **LLM**: Ollama (local) with llama3.2 (fallback: rule-based mock agent)
- **Frontend**: Vanilla HTML5, Bootstrap 5, WebSocket API
- **MCP Transport**: JSON-RPC over HTTP + SSE

---

## License

MIT License — See [LICENSE](LICENSE) for details.

Copyright © 2025 — API-2-MCP Project
