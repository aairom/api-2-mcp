"""
App 4 - Mock AI Agent
Connects to the MCP Server (App 3) and simulates an AI agent that:
1. Discovers available tools from the MCP server
2. Accepts natural language queries
3. Determines which MCP tools to call
4. Executes tool calls and shows reasoning chain
5. Returns final answers

Uses Ollama (locally installed) for LLM inference.
Falls back to a rule-based mock agent if Ollama is unavailable.

Runs on port 8004.
"""
import os
import json
import re
import uuid
import asyncio
import httpx
from datetime import datetime
from typing import Optional, Any
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("AGENT_HOST", "0.0.0.0")
PORT = int(os.getenv("AGENT_PORT", "8004"))
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8003")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

app = FastAPI(title="Mock AI Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ─── Session Store ────────────────────────────────────────────────────────────

sessions: dict[str, list[dict]] = {}
mcp_tools_cache: list[dict] = []
active_websockets: list[WebSocket] = []

# ─── MCP Client (HTTP) ────────────────────────────────────────────────────────

# SSE session state for MCP
_mcp_session_id: str | None = None
_mcp_post_url: str | None = None

async def _ensure_mcp_session() -> tuple[str, str]:
    """Establish an SSE session with the MCP server if not already done."""
    global _mcp_session_id, _mcp_post_url
    if _mcp_session_id:
        return _mcp_session_id, _mcp_post_url

    # Open SSE stream to get session info
    async with httpx.AsyncClient(timeout=10.0) as client:
        async with client.stream("GET", f"{MCP_SERVER_URL}/mcp/sse") as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    data = line[5:].strip()
                    # The first message from SSEServerTransport contains the post URL
                    if "/mcp/messages" in data:
                        _mcp_post_url = f"{MCP_SERVER_URL}{data.split(MCP_SERVER_URL)[-1]}" if MCP_SERVER_URL in data else data
                        # Extract sessionId
                        if "sessionId=" in _mcp_post_url:
                            _mcp_session_id = _mcp_post_url.split("sessionId=")[-1].split("&")[0]
                        break
    return _mcp_session_id, _mcp_post_url


async def mcp_send(method: str, params: dict = None) -> dict:
    """Send a JSON-RPC request to the MCP server via the status API or direct HTTP."""
    # Use the status endpoint for tool discovery (faster, no protocol overhead)
    if method == "tools/list":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{MCP_SERVER_URL}/status")
                if resp.status_code == 200:
                    data = resp.json()
                    tools = []
                    for t in data.get("tools", []):
                        tools.append({
                            "name": t["name"] if isinstance(t, dict) else t,
                            "description": t.get("description", "") if isinstance(t, dict) else "",
                        })
                    return {"result": {"tools": tools}}
        except Exception:
            pass
        return {"result": {"tools": []}}

    # For tool calls: use SSE transport with POST
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
    }
    if params:
        payload["params"] = params

    # Try SSE POST approach
    try:
        session_id, post_url = await _ensure_mcp_session()
        if session_id and post_url:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(post_url, json=payload)
                if resp.status_code == 200:
                    return resp.json()
    except Exception:
        pass

    # Fallback: try streamable HTTP with initialization
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Initialize session
            init_payload = {"jsonrpc": "2.0", "id": "init", "method": "initialize",
                           "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                     "clientInfo": {"name": "mock-agent", "version": "1.0"}}}
            init_resp = await client.post(
                f"{MCP_SERVER_URL}/mcp", json=init_payload,
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
            )
            session_hdr = init_resp.headers.get("mcp-session-id")
            headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
            if session_hdr:
                headers["mcp-session-id"] = session_hdr
            # Send initialized notification
            notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            await client.post(f"{MCP_SERVER_URL}/mcp", json=notif, headers=headers)
            # Send actual request
            resp = await client.post(f"{MCP_SERVER_URL}/mcp", json=payload, headers=headers)
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "")
                if "event-stream" in ct:
                    for line in resp.text.split("\n"):
                        if line.startswith("data:"):
                            d = line[5:].strip()
                            if d and d != "[DONE]":
                                return json.loads(d)
                else:
                    return resp.json()
    except Exception as e:
        pass

    return {"error": "MCP request failed"}


async def discover_mcp_tools() -> list[dict]:
    """Fetch the list of available tools from the MCP server."""
    global mcp_tools_cache
    try:
        result = await mcp_send("tools/list")
        if "result" in result and "tools" in result["result"]:
            mcp_tools_cache = result["result"]["tools"]
            return mcp_tools_cache
    except Exception as e:
        pass
    # Fallback: fetch from status endpoint
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{MCP_SERVER_URL}/status")
            if resp.status_code == 200:
                data = resp.json()
                mcp_tools_cache = data.get("tools", [])
                return mcp_tools_cache
    except Exception:
        pass
    return mcp_tools_cache


async def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Call a specific MCP tool via the direct REST endpoint on App 3."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{MCP_SERVER_URL}/tools/call",
                json={"name": tool_name, "arguments": arguments},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return data.get("result", "No result")
                else:
                    return f"Tool error: {data.get('error', 'Unknown error')}"
            else:
                # Fallback to MCP protocol
                result = await mcp_send("tools/call", {"name": tool_name, "arguments": arguments})
                if "result" in result:
                    content = result["result"].get("content", [])
                    texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                    return "\n".join(texts)
    except Exception as e:
        return f"Error calling tool: {str(e)}"
    return "No result"

# ─── Ollama LLM ───────────────────────────────────────────────────────────────

async def check_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def ollama_generate(prompt: str, system: str = None) -> str:
    """Call Ollama for text generation."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 512},
    }
    if system:
        payload["system"] = system

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json()["response"]

# ─── ReAct Agent Logic ────────────────────────────────────────────────────────

TOOLS_SCHEMA_TEXT = """Available MCP Tools:
1. list_books(genre?, available?, search?) - List all books with optional filters
2. get_book(book_id) - Get details of a specific book by ID
3. create_book(title, author, genre, year, available, description?) - Add a new book
4. update_book(book_id, title?, author?, genre?, year?, available?) - Update a book
5. delete_book(book_id) - Delete a book from the library
6. borrow_book(book_id) - Mark a book as borrowed (unavailable)
7. return_book(book_id) - Mark a book as returned (available)
8. list_genres() - Get all available genres
"""

REACT_SYSTEM_PROMPT = """You are a library assistant AI agent that uses tools to help users.
You follow the ReAct pattern: Thought → Action → Observation → Thought → ... → Final Answer.

When you need to take action, output EXACTLY in this format:
Thought: <your reasoning>
Action: <tool_name>
Action Input: <JSON object with parameters>

When you have the final answer:
Thought: <your final reasoning>
Final Answer: <your response to the user>

Rules:
- Only use the tools listed. 
- Action Input must be valid JSON.
- If a tool fails, try an alternative approach.
- Always provide a Final Answer at the end.
- Keep responses concise and helpful.
""" + TOOLS_SCHEMA_TEXT


def parse_react_step(text: str) -> dict:
    """Parse a ReAct step from LLM output."""
    thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|Final Answer:|$)", text, re.DOTALL | re.IGNORECASE)
    action_match = re.search(r"Action:\s*(\w+)", text, re.IGNORECASE)
    input_match = re.search(r"Action Input:\s*(\{.+?\})", text, re.DOTALL | re.IGNORECASE)
    final_match = re.search(r"Final Answer:\s*(.+)", text, re.DOTALL | re.IGNORECASE)

    result = {}
    if thought_match:
        result["thought"] = thought_match.group(1).strip()
    if final_match:
        result["type"] = "final"
        result["answer"] = final_match.group(1).strip()
    elif action_match:
        result["type"] = "action"
        result["tool"] = action_match.group(1).strip()
        if input_match:
            try:
                result["args"] = json.loads(input_match.group(1))
            except Exception:
                result["args"] = {}
        else:
            result["args"] = {}
    return result


# ─── Rule-Based Mock Agent (fallback when Ollama unavailable) ──────────────────

def mock_agent_decide(query: str, tools: list[dict], history: list[dict]) -> list[dict]:
    """Simple rule-based agent that decides tool calls based on keywords."""
    q = query.lower()
    steps = []

    if any(w in q for w in ["list", "show", "all books", "available", "find", "search"]):
        args = {}
        genre_match = re.search(r"(fantasy|sci.fi|science fiction|non.fiction|technology|dystopian|fiction)", q, re.I)
        if genre_match:
            args["genre"] = genre_match.group(1).title()
        if "available" in q and "borrow" not in q:
            args["available"] = True
        if "borrowed" in q:
            args["available"] = False
        search_match = re.search(r"(?:about|by|titled?|search for)\s+['\"]?([a-z\s]+)['\"]?", q, re.I)
        if search_match and not genre_match:
            args["search"] = search_match.group(1).strip()
        steps.append({"thought": f"I need to list books from the library. {'Filtering by: ' + str(args) if args else 'No filters needed.'}", "tool": "list_books", "args": args})

    elif any(w in q for w in ["genre", "genres", "types", "categories"]):
        steps.append({"thought": "The user wants to know available genres.", "tool": "list_genres", "args": {}})

    elif re.search(r"add|create|new book", q, re.I):
        title_m = re.search(r"['\"]([^'\"]+)['\"]", q)
        title = title_m.group(1) if title_m else "New Book"
        author_m = re.search(r"by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", query)
        author = author_m.group(1) if author_m else "Unknown Author"
        steps.append({"thought": f"I need to create a new book titled '{title}'.", "tool": "create_book", "args": {"title": title, "author": author, "genre": "Fiction", "year": 2024, "available": True}})

    elif any(w in q for w in ["borrow", "check out"]):
        id_m = re.search(r"[a-f0-9]{8}-[a-f0-9-]{27}", q)
        if id_m:
            steps.append({"thought": f"I need to borrow book with ID {id_m.group(0)}.", "tool": "borrow_book", "args": {"book_id": id_m.group(0)}})
        else:
            steps.append({"thought": "I need to list books first to find the one to borrow.", "tool": "list_books", "args": {}})

    elif any(w in q for w in ["return", "give back"]):
        id_m = re.search(r"[a-f0-9]{8}-[a-f0-9-]{27}", q)
        if id_m:
            steps.append({"thought": f"I need to return book with ID {id_m.group(0)}.", "tool": "return_book", "args": {"book_id": id_m.group(0)}})
        else:
            steps.append({"thought": "I need to list borrowed books first.", "tool": "list_books", "args": {"available": False}})

    elif any(w in q for w in ["delete", "remove"]):
        id_m = re.search(r"[a-f0-9]{8}-[a-f0-9-]{27}", q)
        if id_m:
            steps.append({"thought": f"I need to delete book {id_m.group(0)}.", "tool": "delete_book", "args": {"book_id": id_m.group(0)}})
        else:
            steps.append({"thought": "I need to list books first to find the one to delete.", "tool": "list_books", "args": {}})

    elif "hello" in q or "help" in q or "what can you" in q:
        steps.append({"thought": "The user wants to know what I can do.", "tool": "list_genres", "args": {}})

    else:
        steps.append({"thought": "I'll search the library for relevant books.", "tool": "list_books", "args": {"search": query[:30]}})

    return steps


async def run_agent(query: str, session_id: str, ws: WebSocket, use_ollama: bool) -> None:
    """Run the agent loop and stream steps to the WebSocket."""

    async def send_step(step_type: str, data: dict):
        await ws.send_json({"type": step_type, "data": data, "timestamp": datetime.now().isoformat()})

    await send_step("thinking", {"message": "🔍 Discovering available MCP tools..."})

    tools = await discover_mcp_tools()
    await send_step("tools_discovered", {
        "tools": [t["name"] if isinstance(t, dict) else t for t in tools],
        "count": len(tools),
        "mcp_url": MCP_SERVER_URL,
    })

    history = sessions.get(session_id, [])
    history.append({"role": "user", "content": query})

    max_steps = 4
    step_count = 0

    if use_ollama:
        # ReAct loop with Ollama
        conversation = []
        for msg in history[-6:]:  # Last 3 turns
            conversation.append(f"{msg['role'].capitalize()}: {msg['content']}")
        prompt = "\n".join(conversation) + f"\n\nHuman: {query}\nAssistant:"

        for _ in range(max_steps):
            step_count += 1
            await send_step("thinking", {"message": f"🤔 Step {step_count}: Reasoning with {OLLAMA_MODEL}..."})

            try:
                llm_out = await ollama_generate(
                    prompt=f"User query: {query}\n\nPrevious steps:\n{prompt}\n\nWhat should I do?",
                    system=REACT_SYSTEM_PROMPT
                )
                parsed = parse_react_step(llm_out)

                if "thought" in parsed:
                    await send_step("thought", {"content": parsed["thought"]})

                if parsed.get("type") == "final":
                    await send_step("final_answer", {"content": parsed["answer"]})
                    history.append({"role": "assistant", "content": parsed["answer"]})
                    break

                elif parsed.get("type") == "action":
                    tool_name = parsed["tool"]
                    args = parsed.get("args", {})

                    await send_step("tool_call", {
                        "tool": tool_name,
                        "args": args,
                        "mcp_url": f"{MCP_SERVER_URL}/mcp",
                    })

                    result = await call_mcp_tool(tool_name, args)
                    await send_step("tool_result", {"tool": tool_name, "result": result})

                    prompt += f"\nThought: {parsed.get('thought','')}\nAction: {tool_name}\nAction Input: {json.dumps(args)}\nObservation: {result}\n"
                else:
                    # Fallback
                    await send_step("final_answer", {"content": llm_out.strip()})
                    history.append({"role": "assistant", "content": llm_out.strip()})
                    break
            except Exception as e:
                await send_step("error", {"message": f"LLM error: {str(e)}"})
                break

    else:
        # Rule-based mock agent
        await send_step("thinking", {"message": "🤖 Using rule-based mock agent (Ollama not available)..."})
        steps = mock_agent_decide(query, tools, history)

        all_results = []
        for step in steps:
            await send_step("thought", {"content": step["thought"]})
            await asyncio.sleep(0.3)

            await send_step("tool_call", {
                "tool": step["tool"],
                "args": step["args"],
                "mcp_url": f"{MCP_SERVER_URL}/mcp",
            })

            result = await call_mcp_tool(step["tool"], step["args"])
            await send_step("tool_result", {"tool": step["tool"], "result": result})
            all_results.append(result)
            await asyncio.sleep(0.2)

        # Generate final answer
        combined = "\n\n".join(all_results)
        q_lower = query.lower()
        if "list" in q_lower or "show" in q_lower or "find" in q_lower or "search" in q_lower:
            final = f"Here are the results from the library:\n\n{combined}"
        elif "create" in q_lower or "add" in q_lower:
            final = f"I've added the book to the library:\n\n{combined}"
        elif "genre" in q_lower:
            final = f"Available genres in the library:\n\n{combined}"
        elif "borrow" in q_lower:
            final = f"Book borrowing result:\n\n{combined}"
        elif "return" in q_lower:
            final = f"Book return result:\n\n{combined}"
        else:
            final = combined

        await asyncio.sleep(0.3)
        await send_step("final_answer", {"content": final})
        history.append({"role": "assistant", "content": final})

    sessions[session_id] = history[-20:]  # Keep last 20 messages
    await send_step("done", {"session_id": session_id})

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/config")
async def config():
    ollama_ok = await check_ollama()
    tools = await discover_mcp_tools()
    return {
        "mcp_server_url": MCP_SERVER_URL,
        "ollama_url": OLLAMA_BASE_URL,
        "ollama_model": OLLAMA_MODEL,
        "ollama_available": ollama_ok,
        "mcp_tools_count": len(tools),
        "mcp_tools": [t["name"] if isinstance(t, dict) else t for t in tools],
    }

@app.post("/discover-tools")
async def discover_tools():
    tools = await discover_mcp_tools()
    return {"tools": tools, "count": len(tools)}

@app.websocket("/ws/agent/{session_id}")
async def agent_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        # Send initial config
        ollama_ok = await check_ollama()
        tools = await discover_mcp_tools()
        await websocket.send_json({
            "type": "connected",
            "data": {
                "session_id": session_id,
                "ollama_available": ollama_ok,
                "ollama_model": OLLAMA_MODEL,
                "mcp_server_url": MCP_SERVER_URL,
                "tools_count": len(tools),
                "tools": [t["name"] if isinstance(t, dict) else t for t in tools],
            }
        })

        while True:
            data = await websocket.receive_json()
            if data.get("type") == "query":
                query = data.get("query", "")
                use_ollama = data.get("use_ollama", True) and ollama_ok
                if query.strip():
                    try:
                        await run_agent(query, session_id, websocket, use_ollama)
                    except Exception as e:
                        await websocket.send_json({"type": "error", "data": {"message": str(e)}})
            elif data.get("type") == "clear":
                sessions.pop(session_id, None)
                await websocket.send_json({"type": "cleared"})

    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
