#!/usr/bin/env node
/**
 * App 3 - MCP Server
 * Transforms the Library API Server (App 1) into an MCP server.
 * Exposes Book CRUD operations as MCP tools.
 * Also serves a status dashboard on HTTP.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import express, { Request, Response } from "express";
import cors from "cors";
import { z } from "zod";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import * as dotenv from "dotenv";

dotenv.config({ path: join(dirname(fileURLToPath(import.meta.url)), "../../.env") });

const API_SERVER_URL = process.env.MCP_API_SERVER_URL || "http://localhost:8001";
const MCP_PORT = parseInt(process.env.MCP_SERVER_PORT || "8003");
const MCP_HOST = process.env.MCP_SERVER_HOST || "0.0.0.0";

// ─── Tool Registry (for dashboard) ─────────────────────────────────────────────

interface ToolCall {
  id: string;
  tool: string;
  input: Record<string, unknown>;
  result: unknown;
  error?: string;
  timestamp: string;
  durationMs: number;
}

const toolCallLog: ToolCall[] = [];

function logToolCall(call: Omit<ToolCall, "id">) {
  toolCallLog.unshift({
    id: Math.random().toString(36).slice(2, 10),
    ...call,
  });
  if (toolCallLog.length > 100) toolCallLog.pop();
}

// ─── API Helper ────────────────────────────────────────────────────────────────

async function apiCall(
  method: string,
  path: string,
  body?: Record<string, unknown>,
  params?: Record<string, string>
): Promise<unknown> {
  const url = new URL(`${API_SERVER_URL}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") url.searchParams.set(k, v);
    });
  }
  const init: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) init.body = JSON.stringify(body);
  const res = await fetch(url.toString(), init);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as { detail?: string }).detail || `API error ${res.status}`);
  }
  return res.json();
}

// ─── MCP Server Setup ──────────────────────────────────────────────────────────

const server = new McpServer({
  name: "library-mcp-server",
  version: "1.0.0",
});

// Tool: list_books
server.registerTool(
  "list_books",
  {
    description: "List all books in the library with optional filters",
    inputSchema: z.object({
      genre: z.string().optional().describe("Filter by genre (e.g. Fantasy, Science Fiction)"),
      available: z.boolean().optional().describe("Filter by availability (true = available, false = borrowed)"),
      search: z.string().optional().describe("Search by title, author, or description"),
    }),
  },
  async ({ genre, available, search }) => {
    const start = Date.now();
    try {
      const params: Record<string, string> = {};
      if (genre) params.genre = genre;
      if (available !== undefined) params.available = String(available);
      if (search) params.search = search;
      const result = await apiCall("GET", "/books", undefined, params);
      const ms = Date.now() - start;
      logToolCall({ tool: "list_books", input: { genre, available, search }, result, timestamp: new Date().toISOString(), durationMs: ms });
      const books = result as Array<Record<string, unknown>>;
      return {
        content: [{
          type: "text" as const,
          text: `Found ${books.length} book(s):\n\n${books.map(b =>
            `• **${b.title}** by ${b.author} (${b.genre}, ${b.year}) — ${b.available ? "✓ Available" : "✗ Borrowed"}\n  ID: ${b.id}\n  ${b.description || ""}`
          ).join("\n\n")}`,
        }],
      };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      logToolCall({ tool: "list_books", input: { genre, available, search }, result: null, error: msg, timestamp: new Date().toISOString(), durationMs: Date.now() - start });
      return { content: [{ type: "text" as const, text: `Error listing books: ${msg}` }], isError: true };
    }
  }
);

// Tool: get_book
server.registerTool(
  "get_book",
  {
    description: "Get details of a specific book by its ID",
    inputSchema: z.object({
      book_id: z.string().describe("The unique ID of the book"),
    }),
  },
  async ({ book_id }) => {
    const start = Date.now();
    try {
      const result = await apiCall("GET", `/books/${book_id}`);
      const ms = Date.now() - start;
      logToolCall({ tool: "get_book", input: { book_id }, result, timestamp: new Date().toISOString(), durationMs: ms });
      const b = result as Record<string, unknown>;
      return {
        content: [{
          type: "text" as const,
          text: `**${b.title}** by ${b.author}\n- Genre: ${b.genre}\n- Year: ${b.year}\n- Status: ${b.available ? "✓ Available" : "✗ Borrowed"}\n- Description: ${b.description || "N/A"}\n- ID: ${b.id}\n- Updated: ${b.updated_at}`,
        }],
      };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      logToolCall({ tool: "get_book", input: { book_id }, result: null, error: msg, timestamp: new Date().toISOString(), durationMs: Date.now() - start });
      return { content: [{ type: "text" as const, text: `Error getting book: ${msg}` }], isError: true };
    }
  }
);

// Tool: create_book
server.registerTool(
  "create_book",
  {
    description: "Add a new book to the library",
    inputSchema: z.object({
      title: z.string().min(1).describe("Book title"),
      author: z.string().min(1).describe("Author name"),
      genre: z.string().min(1).describe("Book genre"),
      year: z.number().int().min(1000).max(2100).describe("Publication year"),
      available: z.boolean().default(true).describe("Whether the book is available"),
      description: z.string().optional().describe("Brief description of the book"),
    }),
  },
  async ({ title, author, genre, year, available, description }) => {
    const start = Date.now();
    try {
      const body: Record<string, unknown> = { title, author, genre, year, available };
      if (description) body.description = description;
      const result = await apiCall("POST", "/books", body);
      const ms = Date.now() - start;
      logToolCall({ tool: "create_book", input: { title, author, genre, year }, result, timestamp: new Date().toISOString(), durationMs: ms });
      const b = result as Record<string, unknown>;
      return { content: [{ type: "text" as const, text: `✓ Book created successfully!\n- ID: ${b.id}\n- Title: ${b.title}\n- Author: ${b.author}\n- Genre: ${b.genre}` }] };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      logToolCall({ tool: "create_book", input: { title, author, genre }, result: null, error: msg, timestamp: new Date().toISOString(), durationMs: Date.now() - start });
      return { content: [{ type: "text" as const, text: `Error creating book: ${msg}` }], isError: true };
    }
  }
);

// Tool: update_book
server.registerTool(
  "update_book",
  {
    description: "Update an existing book's details",
    inputSchema: z.object({
      book_id: z.string().describe("The ID of the book to update"),
      title: z.string().optional().describe("New title"),
      author: z.string().optional().describe("New author"),
      genre: z.string().optional().describe("New genre"),
      year: z.number().int().optional().describe("New publication year"),
      available: z.boolean().optional().describe("New availability status"),
      description: z.string().optional().describe("New description"),
    }),
  },
  async ({ book_id, title, author, genre, year, available, description }) => {
    const start = Date.now();
    try {
      const body: Record<string, unknown> = {};
      if (title !== undefined) body.title = title;
      if (author !== undefined) body.author = author;
      if (genre !== undefined) body.genre = genre;
      if (year !== undefined) body.year = year;
      if (available !== undefined) body.available = available;
      if (description !== undefined) body.description = description;
      const result = await apiCall("PUT", `/books/${book_id}`, body);
      const ms = Date.now() - start;
      logToolCall({ tool: "update_book", input: { book_id, ...body }, result, timestamp: new Date().toISOString(), durationMs: ms });
      const b = result as Record<string, unknown>;
      return { content: [{ type: "text" as const, text: `✓ Book updated: "${b.title}" (ID: ${b.id})` }] };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      logToolCall({ tool: "update_book", input: { book_id }, result: null, error: msg, timestamp: new Date().toISOString(), durationMs: Date.now() - start });
      return { content: [{ type: "text" as const, text: `Error updating book: ${msg}` }], isError: true };
    }
  }
);

// Tool: delete_book
server.registerTool(
  "delete_book",
  {
    description: "Delete a book from the library",
    inputSchema: z.object({
      book_id: z.string().describe("The ID of the book to delete"),
    }),
  },
  async ({ book_id }) => {
    const start = Date.now();
    try {
      const result = await apiCall("DELETE", `/books/${book_id}`);
      const ms = Date.now() - start;
      logToolCall({ tool: "delete_book", input: { book_id }, result, timestamp: new Date().toISOString(), durationMs: ms });
      return { content: [{ type: "text" as const, text: `✓ Book deleted successfully (ID: ${book_id})` }] };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      logToolCall({ tool: "delete_book", input: { book_id }, result: null, error: msg, timestamp: new Date().toISOString(), durationMs: Date.now() - start });
      return { content: [{ type: "text" as const, text: `Error deleting book: ${msg}` }], isError: true };
    }
  }
);

// Tool: borrow_book
server.registerTool(
  "borrow_book",
  {
    description: "Mark a book as borrowed (make it unavailable)",
    inputSchema: z.object({
      book_id: z.string().describe("The ID of the book to borrow"),
    }),
  },
  async ({ book_id }) => {
    const start = Date.now();
    try {
      const result = await apiCall("POST", `/books/${book_id}/borrow`);
      const ms = Date.now() - start;
      logToolCall({ tool: "borrow_book", input: { book_id }, result, timestamp: new Date().toISOString(), durationMs: ms });
      const b = result as Record<string, unknown>;
      return { content: [{ type: "text" as const, text: `✓ Book "${b.title}" is now borrowed (unavailable)` }] };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      logToolCall({ tool: "borrow_book", input: { book_id }, result: null, error: msg, timestamp: new Date().toISOString(), durationMs: Date.now() - start });
      return { content: [{ type: "text" as const, text: `Error borrowing book: ${msg}` }], isError: true };
    }
  }
);

// Tool: return_book
server.registerTool(
  "return_book",
  {
    description: "Mark a borrowed book as returned (make it available again)",
    inputSchema: z.object({
      book_id: z.string().describe("The ID of the book to return"),
    }),
  },
  async ({ book_id }) => {
    const start = Date.now();
    try {
      const result = await apiCall("POST", `/books/${book_id}/return`);
      const ms = Date.now() - start;
      logToolCall({ tool: "return_book", input: { book_id }, result, timestamp: new Date().toISOString(), durationMs: ms });
      const b = result as Record<string, unknown>;
      return { content: [{ type: "text" as const, text: `✓ Book "${b.title}" has been returned (now available)` }] };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      logToolCall({ tool: "return_book", input: { book_id }, result: null, error: msg, timestamp: new Date().toISOString(), durationMs: Date.now() - start });
      return { content: [{ type: "text" as const, text: `Error returning book: ${msg}` }], isError: true };
    }
  }
);

// Tool: list_genres
server.registerTool(
  "list_genres",
  {
    description: "Get all available genres in the library",
    inputSchema: z.object({}),
  },
  async () => {
    const start = Date.now();
    try {
      const result = await apiCall("GET", "/genres");
      const ms = Date.now() - start;
      logToolCall({ tool: "list_genres", input: {}, result, timestamp: new Date().toISOString(), durationMs: ms });
      const data = result as { genres: string[] };
      return { content: [{ type: "text" as const, text: `Available genres (${data.genres.length}):\n${data.genres.map(g => `• ${g}`).join("\n")}` }] };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      logToolCall({ tool: "list_genres", input: {}, result: null, error: msg, timestamp: new Date().toISOString(), durationMs: Date.now() - start });
      return { content: [{ type: "text" as const, text: `Error listing genres: ${msg}` }], isError: true };
    }
  }
);

// ─── Express HTTP Server ───────────────────────────────────────────────────────

const expressApp = express();
expressApp.use(cors());
expressApp.use(express.json());

// SSE sessions map
const sseSessions = new Map<string, SSEServerTransport>();

// MCP SSE endpoint (legacy transport for broad compatibility)
expressApp.get("/mcp/sse", async (req: Request, res: Response) => {
  console.error(`[MCP] New SSE connection from ${req.ip}`);
  const transport = new SSEServerTransport("/mcp/messages", res);
  const sessionId = transport.sessionId;
  sseSessions.set(sessionId, transport);
  res.on("close", () => {
    sseSessions.delete(sessionId);
    console.error(`[MCP] SSE session ${sessionId} closed`);
  });
  await server.connect(transport);
});

expressApp.post("/mcp/messages", async (req: Request, res: Response) => {
  const sessionId = req.query.sessionId as string;
  const transport = sseSessions.get(sessionId);
  if (!transport) {
    res.status(404).json({ error: "Session not found" });
    return;
  }
  await transport.handlePostMessage(req, res, req.body);
});

// Streamable HTTP (modern MCP transport)
expressApp.all("/mcp", async (req: Request, res: Response) => {
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: () => Math.random().toString(36).slice(2),
    enableJsonResponse: true,
  });
  res.on("close", () => transport.close());
  await server.connect(transport);
  await transport.handleRequest(req, res, req.body);
});

// ─── Status Dashboard API ──────────────────────────────────────────────────────

expressApp.get("/status", async (req: Request, res: Response) => {
  // Test upstream API
  let apiStatus = "unknown";
  let apiBookCount = 0;
  try {
    const health = await apiCall("GET", "/health") as { status: string; book_count: number };
    apiStatus = health.status;
    apiBookCount = health.book_count;
  } catch { apiStatus = "unreachable"; }

  res.json({
    mcp_server: "online",
    version: "1.0.0",
    api_server_url: API_SERVER_URL,
    api_server_status: apiStatus,
    api_book_count: apiBookCount,
    active_sse_sessions: sseSessions.size,
    tool_calls_total: toolCallLog.length,
    tools: [
      { name: "list_books", description: "List all books with optional filters" },
      { name: "get_book", description: "Get a specific book by ID" },
      { name: "create_book", description: "Add a new book to the library" },
      { name: "update_book", description: "Update an existing book" },
      { name: "delete_book", description: "Delete a book from the library" },
      { name: "borrow_book", description: "Mark a book as borrowed" },
      { name: "return_book", description: "Mark a book as returned" },
      { name: "list_genres", description: "Get all available genres" },
    ],
    recent_calls: toolCallLog.slice(0, 20),
  });
});

expressApp.get("/tool-log", (req: Request, res: Response) => {
  res.json({ calls: toolCallLog.slice(0, 50) });
});

// Direct tool call endpoint (simplified REST, no MCP protocol overhead needed)
expressApp.post("/tools/call", async (req: Request, res: Response) => {
  const { name, arguments: args = {} } = req.body;
  if (!name) { res.status(400).json({ error: "Missing tool name" }); return; }
  const start = Date.now();
  try {
    const text = await callToolDirect(name, args as Record<string, unknown>);
    const ms = Date.now() - start;
    logToolCall({ tool: name, input: args as Record<string, unknown>, result: text, timestamp: new Date().toISOString(), durationMs: ms });
    res.json({ success: true, tool: name, result: text, durationMs: ms });
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    res.status(500).json({ success: false, tool: name, error: msg });
  }
});

async function callToolDirect(name: string, args: Record<string, unknown>): Promise<string> {
  switch (name) {
    case "list_books": {
      const params: Record<string, string> = {};
      if (args.genre) params.genre = String(args.genre);
      if (args.available !== undefined) params.available = String(args.available);
      if (args.search) params.search = String(args.search);
      const result = await apiCall("GET", "/books", undefined, params) as Array<Record<string, unknown>>;
      return `Found ${result.length} book(s):\n\n${result.map(b =>
        `• **${b.title}** by ${b.author} (${b.genre}, ${b.year}) — ${b.available ? "✓ Available" : "✗ Borrowed"}\n  ID: ${b.id}\n  ${b.description || ""}`
      ).join("\n\n")}`;
    }
    case "get_book": {
      const b = await apiCall("GET", `/books/${args.book_id}`) as Record<string, unknown>;
      return `**${b.title}** by ${b.author}\n- Genre: ${b.genre}\n- Year: ${b.year}\n- Status: ${b.available ? "✓ Available" : "✗ Borrowed"}\n- Description: ${b.description || "N/A"}\n- ID: ${b.id}`;
    }
    case "create_book": {
      const b = await apiCall("POST", "/books", args) as Record<string, unknown>;
      return `✓ Book created: "${b.title}" by ${b.author} (ID: ${b.id})`;
    }
    case "update_book": {
      const { book_id, ...rest } = args as { book_id: string; [key: string]: unknown };
      const b = await apiCall("PUT", `/books/${book_id}`, rest) as Record<string, unknown>;
      return `✓ Book updated: "${b.title}" (ID: ${b.id})`;
    }
    case "delete_book": {
      await apiCall("DELETE", `/books/${String(args.book_id)}`);
      return `✓ Book deleted (ID: ${args.book_id})`;
    }
    case "borrow_book": {
      const b = await apiCall("POST", `/books/${String(args.book_id)}/borrow`) as Record<string, unknown>;
      return `✓ Book "${b.title}" is now borrowed`;
    }
    case "return_book": {
      const b = await apiCall("POST", `/books/${String(args.book_id)}/return`) as Record<string, unknown>;
      return `✓ Book "${b.title}" has been returned`;
    }
    case "list_genres": {
      const data = await apiCall("GET", "/genres") as { genres: string[] };
      return `Genres (${data.genres.length}):\n${data.genres.map(g => `• ${g}`).join("\n")}`;
    }
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

// Dashboard HTML
expressApp.get("/", (req: Request, res: Response) => {
  res.send(getDashboardHTML());
});

function getDashboardHTML(): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MCP Server Dashboard</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: system-ui, sans-serif; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; }
    .card-header { background: #1e293b; border-bottom: 1px solid #334155; }
    .stat-value { font-size: 2.2rem; font-weight: 700; }
    .tool-card { background: #0f172a; border: 1px solid #1e3a5f; border-radius: 8px; padding: .75rem 1rem; margin-bottom: .5rem; }
    .tool-name { font-family: monospace; font-size: .85rem; color: #38bdf8; }
    .tool-desc { font-size: .78rem; color: #94a3b8; }
    .badge-tool { background: #1e3a5f; color: #38bdf8; font-size: .7rem; font-family: monospace; padding: .25em .6em; border-radius: 4px; }
    .log-row { border-bottom: 1px solid #1e293b; padding: .5rem 0; font-size: .78rem; }
    .log-row:last-child { border-bottom: none; }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .dot-green { background: #22c55e; box-shadow: 0 0 6px #22c55e; }
    .dot-red { background: #ef4444; }
    .dot-yellow { background: #f59e0b; }
    pre.code { background: #0f172a; color: #7dd3fc; border: 1px solid #1e3a5f; border-radius: 6px; padding: .5rem .75rem; font-size: .78rem; }
    .endpoint-badge { background: #0f172a; border: 1px solid #334155; padding: .3rem .75rem; border-radius: 6px; font-family: monospace; font-size: .82rem; color: #a5f3fc; }
  </style>
</head>
<body>
<nav class="navbar" style="background:#1e293b;border-bottom:1px solid #334155;padding:.75rem 1.5rem">
  <span class="navbar-brand text-white fw-bold">⚙️ MCP Server <small class="text-secondary fw-normal fs-6">— App 3</small></span>
  <div class="d-flex gap-2 align-items-center">
    <span class="status-dot dot-green" id="status-dot"></span>
    <span id="status-text" class="text-secondary small">Online</span>
    <span class="ms-3 text-secondary small">Port <strong class="text-white">${MCP_PORT}</strong></span>
  </div>
</nav>

<div class="container-fluid p-4">
  <div class="row g-3 mb-4">
    <div class="col-6 col-md-3"><div class="card"><div class="card-body text-center py-3"><div class="stat-value text-info" id="st-tools">8</div><div class="text-secondary small">MCP Tools</div></div></div></div>
    <div class="col-6 col-md-3"><div class="card"><div class="card-body text-center py-3"><div class="stat-value text-success" id="st-calls">0</div><div class="text-secondary small">Tool Calls</div></div></div></div>
    <div class="col-6 col-md-3"><div class="card"><div class="card-body text-center py-3"><div class="stat-value text-warning" id="st-sessions">0</div><div class="text-secondary small">SSE Sessions</div></div></div></div>
    <div class="col-6 col-md-3"><div class="card"><div class="card-body text-center py-3"><div class="stat-value text-primary" id="st-books">—</div><div class="text-secondary small">Books in API</div></div></div></div>
  </div>

  <div class="row g-4">
    <div class="col-lg-5">
      <div class="card mb-4">
        <div class="card-header py-3 d-flex justify-content-between align-items-center">
          <span class="fw-semibold">🛠️ Registered MCP Tools</span>
          <span class="badge bg-info text-dark">8 tools</span>
        </div>
        <div class="card-body">
          <div id="tools-list"></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header py-3"><span class="fw-semibold">🔗 MCP Endpoints</span></div>
        <div class="card-body">
          <div class="mb-2"><div class="text-secondary small mb-1">SSE Transport (legacy)</div>
            <div class="endpoint-badge">GET /mcp/sse</div><br>
            <div class="endpoint-badge mt-1">POST /mcp/messages?sessionId=…</div>
          </div>
          <div class="mt-3"><div class="text-secondary small mb-1">Streamable HTTP (modern)</div>
            <div class="endpoint-badge">POST /mcp</div>
          </div>
          <div class="mt-3"><div class="text-secondary small mb-1">Status API</div>
            <div class="endpoint-badge">GET /status</div>
          </div>
          <div class="mt-3">
            <div class="text-secondary small mb-1">Connect from agents:</div>
            <pre class="code">http://localhost:${MCP_PORT}/mcp/sse</pre>
          </div>
        </div>
      </div>
    </div>
    <div class="col-lg-7">
      <div class="card mb-4">
        <div class="card-header py-3 d-flex justify-content-between">
          <span class="fw-semibold">📋 Tool Call Log</span>
          <button class="btn btn-sm btn-outline-secondary" onclick="loadStatus()">↻ Refresh</button>
        </div>
        <div class="card-body p-0" style="max-height:360px;overflow-y:auto">
          <div id="call-log" class="px-3"></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header py-3"><span class="fw-semibold">🗺️ Architecture Flow</span></div>
        <div class="card-body">
          <div style="text-align:center;font-family:monospace;font-size:.82rem;line-height:2">
            <div style="background:#1e3a5f;padding:.4rem 1rem;border-radius:8px;display:inline-block;color:#7dd3fc">🤖 AI Agent / App 4<br><small style="color:#64748b">:8004</small></div>
            <div style="color:#475569">⬇ MCP Protocol (SSE / HTTP)</div>
            <div style="background:#172554;padding:.4rem 1rem;border-radius:8px;display:inline-block;color:#93c5fd">⚙️ App 3: MCP Server<br><small style="color:#64748b">:${MCP_PORT}</small></div>
            <div style="color:#475569">⬇ HTTP REST Calls</div>
            <div style="background:#14532d;padding:.4rem 1rem;border-radius:8px;display:inline-block;color:#86efac">📚 App 1: API Server<br><small style="color:#64748b">:8001</small></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
const TOOLS = [
  { name: 'list_books', desc: 'List all books with optional genre/availability/search filters', params: ['genre?','available?','search?'] },
  { name: 'get_book', desc: 'Get details of a specific book by ID', params: ['book_id'] },
  { name: 'create_book', desc: 'Add a new book to the library', params: ['title','author','genre','year','available','description?'] },
  { name: 'update_book', desc: 'Update an existing book's details', params: ['book_id','title?','author?','genre?','year?','available?'] },
  { name: 'delete_book', desc: 'Remove a book from the library', params: ['book_id'] },
  { name: 'borrow_book', desc: 'Mark a book as borrowed (unavailable)', params: ['book_id'] },
  { name: 'return_book', desc: 'Mark a borrowed book as returned (available)', params: ['book_id'] },
  { name: 'list_genres', desc: 'Get all unique genres available in the library', params: [] },
];

function renderTools() {
  const el = document.getElementById('tools-list');
  el.innerHTML = TOOLS.map(t => \`
    <div class="tool-card">
      <div class="d-flex justify-content-between align-items-start">
        <div class="tool-name">\${t.name}</div>
        <div class="d-flex gap-1 flex-wrap justify-content-end">
          \${t.params.map(p => \`<span class="badge-tool">\${p}</span>\`).join('')}
        </div>
      </div>
      <div class="tool-desc mt-1">\${t.desc}</div>
    </div>\`).join('');
}

async function loadStatus() {
  try {
    const d = await fetch('/status').then(r => r.json());
    document.getElementById('st-calls').textContent = d.tool_calls_total;
    document.getElementById('st-sessions').textContent = d.active_sse_sessions;
    document.getElementById('st-books').textContent = d.api_book_count;
    const apiOk = d.api_server_status === 'ok';
    document.getElementById('status-dot').className = 'status-dot ' + (apiOk ? 'dot-green' : 'dot-yellow');

    const log = document.getElementById('call-log');
    if (d.recent_calls && d.recent_calls.length > 0) {
      log.innerHTML = d.recent_calls.map(c => \`
        <div class="log-row">
          <div class="d-flex align-items-center gap-2">
            <code style="color:#38bdf8;font-size:.78rem">\${c.tool}</code>
            <span class="badge \${c.error ? 'bg-danger' : 'bg-success'} ms-auto">\${c.error ? 'Error' : 'OK'}</span>
            <span class="text-secondary" style="font-size:.72rem">\${c.durationMs}ms</span>
          </div>
          <div style="font-size:.72rem;color:#64748b">
            Input: \${JSON.stringify(c.input).slice(0,80)}
            · \${new Date(c.timestamp).toLocaleTimeString()}
          </div>
        </div>\`).join('');
    } else {
      log.innerHTML = '<div class="text-secondary p-3 small">No tool calls yet. Send queries from the Mock Agent (App 4).</div>';
    }
  } catch(e) {
    document.getElementById('status-dot').className = 'status-dot dot-red';
  }
}

renderTools();
loadStatus();
setInterval(loadStatus, 3000);
</script>
</body>
</html>`;
}

// ─── Start Server ──────────────────────────────────────────────────────────────

expressApp.listen(MCP_PORT, MCP_HOST, () => {
  console.error(`[MCP Server] Running on http://${MCP_HOST}:${MCP_PORT}`);
  console.error(`[MCP Server] Dashboard: http://localhost:${MCP_PORT}`);
  console.error(`[MCP Server] SSE endpoint: http://localhost:${MCP_PORT}/mcp/sse`);
  console.error(`[MCP Server] HTTP endpoint: http://localhost:${MCP_PORT}/mcp`);
  console.error(`[MCP Server] Status: http://localhost:${MCP_PORT}/status`);
  console.error(`[MCP Server] API Server URL: ${API_SERVER_URL}`);
});
