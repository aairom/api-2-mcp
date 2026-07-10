# Architecture

## API-2-MCP — System Architecture

This document describes the full architecture of the four-application demo system.

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "App 1 — Library API Server :8001"
        A1[FastAPI REST Server]
        A1_DB[(In-Memory Book Store)]
        A1 <--> A1_DB
        A1_UI[Dashboard GUI + Swagger UI]
    end

    subgraph "App 2 — API Client :8002"
        A2[FastAPI HTTP Proxy]
        A2_UI[Rich Dashboard GUI]
        A2 <--> A2_UI
    end

    subgraph "App 3 — MCP Server :8003"
        A3[Node.js Express Server]
        A3_MCP[MCP Protocol Layer]
        A3_TOOLS[8 MCP Tools]
        A3_UI[Status Dashboard]
        A3 --> A3_MCP
        A3_MCP --> A3_TOOLS
        A3 --> A3_UI
    end

    subgraph "App 4 — Mock AI Agent :8004"
        A4[FastAPI + WebSocket]
        A4_AGENT[ReAct Agent Loop]
        A4_OLLAMA[Ollama LLM / Mock Engine]
        A4_UI[Chat Interface GUI]
        A4 --> A4_AGENT
        A4_AGENT <--> A4_OLLAMA
        A4 --> A4_UI
    end

    Browser1[👤 User Browser] --> A1_UI
    Browser2[👤 User Browser] --> A2_UI
    Browser3[👤 User Browser] --> A3_UI
    Browser4[👤 User Browser] --> A4_UI

    A2 -- "HTTP Proxy\nGET/POST/PUT/DELETE /books" --> A1
    A3_TOOLS -- "HTTP REST\n/books, /genres, /health" --> A1
    A4_AGENT -- "MCP Protocol\n(JSON-RPC over HTTP/SSE)" --> A3_MCP
```

---

## Data Flow: User Query → Agent → MCP → API → Response

```mermaid
sequenceDiagram
    participant U as 👤 User (App 4 UI)
    participant A as 🤖 Agent (App 4)
    participant O as 🧠 Ollama / Mock
    participant M as ⚙️ MCP Server (App 3)
    participant L as 📚 Library API (App 1)
    participant D as 🗃️ Book Store

    U->>A: "Show all Fantasy books"
    A->>O: Reason about query
    O-->>A: Thought: need list_books tool
    A->>M: POST /mcp {method: tools/call, name: list_books, args: {genre: "Fantasy"}}
    M->>L: GET /books?genre=Fantasy
    L->>D: Filter books
    D-->>L: Filtered book list
    L-->>M: JSON response
    M-->>A: MCP tool result
    A->>O: Reason about result
    O-->>A: Final Answer: "Here are the Fantasy books..."
    A-->>U: Formatted response via WebSocket
```

---

## Agent Resilience: LLM → Fallback Chain

```mermaid
flowchart TD
    Q[User Query] --> OL{Ollama\navailable?}
    OL -- Yes --> LLM[ReAct loop with Ollama LLM]
    OL -- No  --> MOCK[Rule-based Mock Agent]

    LLM --> PARSE{LLM output\nparseable as\nReAct step?}
    PARSE -- Yes → action --> TOOL[Call MCP Tool]
    PARSE -- Yes → final  --> ANS[Final Answer to User]
    PARSE -- No           --> MOCK

    MOCK --> TOOL
    TOOL --> RES[Tool Result via MCP]
    RES --> ANS
```

When Ollama is running but returns output that cannot be parsed as a valid ReAct action (Thought / Action / Final Answer), App 4 transparently falls back to the rule-based mock agent to execute the most relevant MCP tool call and still returns a meaningful answer to the user.

---

## API-to-MCP Transformation

```mermaid
graph LR
    subgraph "App 1 REST API"
        direction TB
        R1["GET /books"] 
        R2["POST /books"]
        R3["GET /books/{id}"]
        R4["PUT /books/{id}"]
        R5["DELETE /books/{id}"]
        R6["POST /books/{id}/borrow"]
        R7["POST /books/{id}/return"]
        R8["GET /genres"]
    end

    subgraph "App 3 MCP Tools"
        direction TB
        T1["list_books(genre?, available?, search?)"]
        T2["create_book(title, author, genre, year)"]
        T3["get_book(book_id)"]
        T4["update_book(book_id, ...fields)"]
        T5["delete_book(book_id)"]
        T6["borrow_book(book_id)"]
        T7["return_book(book_id)"]
        T8["list_genres()"]
    end

    R1 --> T1
    R2 --> T2
    R3 --> T3
    R4 --> T4
    R5 --> T5
    R6 --> T6
    R7 --> T7
    R8 --> T8
```

---

## MCP Protocol Flow

```mermaid
sequenceDiagram
    participant A4 as App 4 (Agent)
    participant A3 as App 3 (MCP Server)

    A4->>A3: POST /mcp {jsonrpc: "2.0", method: "tools/list"}
    A3-->>A4: {result: {tools: [list_books, get_book, ...]}}
    
    Note over A4: User asks: "Find Fantasy books"
    
    A4->>A3: POST /mcp {method: "tools/call", params: {name: "list_books", arguments: {genre: "Fantasy"}}}
    A3->>A3: HTTP GET /books?genre=Fantasy → App 1
    A3-->>A4: {result: {content: [{type: "text", text: "Found 2 books..."}]}}
```

---

## Component Summary

| App | Technology | Port | Purpose |
|-----|-----------|------|---------|
| App 1 | Python / FastAPI | 8001 | REST API server for library books (CRUD + borrow/return) |
| App 2 | Python / FastAPI | 8002 | HTTP proxy client with rich dashboard GUI |
| App 3 | Node.js / TypeScript | 8003 | MCP server exposing App 1 APIs as 8 AI tools |
| App 4 | Python / FastAPI | 8004 | Mock AI agent with ReAct loop and chat GUI |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI (Python) + Express (Node.js) |
| MCP SDK | @modelcontextprotocol/sdk v1.x |
| LLM | Ollama (llama3.2 locally) |
| Frontend | Vanilla HTML5 + Bootstrap 5 |
| Real-time | WebSocket (App 4 agent streaming) |
| Data Store | In-Memory (Python dict) |
| Process Management | Shell scripts + PID files |
