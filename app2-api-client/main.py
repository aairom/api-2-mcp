"""
App 2 - API Client Application
Consumes the Library API Server (App 1) and provides a rich dashboard GUI.
Runs on port 8002.
"""
import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("API_CLIENT_HOST", "0.0.0.0")
PORT = int(os.getenv("API_CLIENT_PORT", "8002"))
API_SERVER_URL = os.getenv("API_SERVER_URL", "http://localhost:8001")

app = FastAPI(
    title="Library API Client",
    description="Client application that consumes the Library API Server",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class BookCreate(BaseModel):
    title: str
    author: str
    genre: str
    year: int
    available: bool = True
    description: Optional[str] = None

class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    available: Optional[bool] = None
    description: Optional[str] = None

# ─── Helper ───────────────────────────────────────────────────────────────────

async def api_request(method: str, path: str, **kwargs):
    """Proxy request to the upstream API server."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"{API_SERVER_URL}{path}"
        response = await client.request(method, url, **kwargs)
        return response

# ─── Dashboard Route ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "api_server_url": API_SERVER_URL
    })

@app.get("/config")
async def get_config():
    return {
        "api_server_url": API_SERVER_URL,
        "client_port": PORT,
    }

# ─── Proxy Routes ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    try:
        r = await api_request("GET", "/health")
        api_data = r.json() if r.status_code == 200 else {"status": "error"}
        return {"client_status": "ok", "api_server": api_data, "api_server_url": API_SERVER_URL}
    except Exception as e:
        return {"client_status": "ok", "api_server": {"status": "unreachable", "error": str(e)}, "api_server_url": API_SERVER_URL}

@app.get("/api/books")
async def list_books(genre: Optional[str] = None, available: Optional[bool] = None, search: Optional[str] = None):
    params = {}
    if genre: params["genre"] = genre
    if available is not None: params["available"] = str(available).lower()
    if search: params["search"] = search
    r = await api_request("GET", "/books", params=params)
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()

@app.post("/api/books", status_code=201)
async def create_book(book: BookCreate):
    r = await api_request("POST", "/books", json=book.model_dump())
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.json().get("detail", r.text))
    return r.json()

@app.get("/api/books/{book_id}")
async def get_book(book_id: str):
    r = await api_request("GET", f"/books/{book_id}")
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.json().get("detail", r.text))
    return r.json()

@app.put("/api/books/{book_id}")
async def update_book(book_id: str, updates: BookUpdate):
    r = await api_request("PUT", f"/books/{book_id}", json=updates.model_dump(exclude_none=True))
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.json().get("detail", r.text))
    return r.json()

@app.delete("/api/books/{book_id}")
async def delete_book(book_id: str):
    r = await api_request("DELETE", f"/books/{book_id}")
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.json().get("detail", r.text))
    return r.json()

@app.post("/api/books/{book_id}/borrow")
async def borrow_book(book_id: str):
    r = await api_request("POST", f"/books/{book_id}/borrow")
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.json().get("detail", r.text))
    return r.json()

@app.post("/api/books/{book_id}/return")
async def return_book(book_id: str):
    r = await api_request("POST", f"/books/{book_id}/return")
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.json().get("detail", r.text))
    return r.json()

@app.get("/api/genres")
async def list_genres():
    r = await api_request("GET", "/genres")
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
