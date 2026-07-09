"""
App 1 - Library API Server
A sample REST API server exposing CRUD operations for a library book management system.
Runs on port 8001.
"""
import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("API_SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("API_SERVER_PORT", "8001"))

app = FastAPI(
    title="Library API Server",
    description="A sample REST API for managing a library's book collection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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

# ─── Models ────────────────────────────────────────────────────────────────────

class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Book title")
    author: str = Field(..., min_length=1, max_length=100, description="Author name")
    genre: str = Field(..., min_length=1, max_length=50, description="Book genre")
    year: int = Field(..., ge=1000, le=2100, description="Publication year")
    available: bool = Field(True, description="Whether the book is available for borrowing")
    description: Optional[str] = Field(None, max_length=500, description="Book description")

class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    author: Optional[str] = Field(None, min_length=1, max_length=100)
    genre: Optional[str] = Field(None, min_length=1, max_length=50)
    year: Optional[int] = Field(None, ge=1000, le=2100)
    available: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=500)

class Book(BaseModel):
    id: str
    title: str
    author: str
    genre: str
    year: int
    available: bool
    description: Optional[str] = None
    created_at: str
    updated_at: str

# ─── In-Memory Data Store ──────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

BOOKS: dict[str, dict] = {}

SEED_BOOKS = [
    {"title": "The Hitchhiker's Guide to the Galaxy", "author": "Douglas Adams", "genre": "Science Fiction", "year": 1979, "available": True, "description": "A comedic science fiction series following the adventures of Arthur Dent."},
    {"title": "Dune", "author": "Frank Herbert", "genre": "Science Fiction", "year": 1965, "available": True, "description": "An epic science fiction novel set in a distant future amidst a feudal interstellar society."},
    {"title": "The Name of the Wind", "author": "Patrick Rothfuss", "genre": "Fantasy", "year": 2007, "available": False, "description": "The story of Kvothe, a legendary figure in his world, telling his life story to a chronicler."},
    {"title": "Sapiens: A Brief History of Humankind", "author": "Yuval Noah Harari", "genre": "Non-Fiction", "year": 2011, "available": True, "description": "A narrative history from the Stone Age to the twenty-first century."},
    {"title": "The Pragmatic Programmer", "author": "David Thomas & Andrew Hunt", "genre": "Technology", "year": 1999, "available": True, "description": "Classic guide for software developers covering best practices and principles."},
    {"title": "1984", "author": "George Orwell", "genre": "Dystopian Fiction", "year": 1949, "available": False, "description": "A dystopian social science fiction novel and cautionary tale about the dangers of totalitarianism."},
    {"title": "Clean Code", "author": "Robert C. Martin", "genre": "Technology", "year": 2008, "available": True, "description": "A handbook of agile software craftsmanship."},
    {"title": "The Lord of the Rings", "author": "J.R.R. Tolkien", "genre": "Fantasy", "year": 1954, "available": True, "description": "An epic high-fantasy novel set in Middle-earth."},
]

for book_data in SEED_BOOKS:
    bid = str(uuid.uuid4())
    BOOKS[bid] = {
        "id": bid,
        **book_data,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "library-api-server", "book_count": len(BOOKS)}

@app.get("/books", response_model=list[Book], tags=["Books"])
async def list_books(genre: Optional[str] = None, available: Optional[bool] = None, search: Optional[str] = None):
    """List all books with optional filtering by genre, availability, or search term."""
    books = list(BOOKS.values())
    if genre:
        books = [b for b in books if b["genre"].lower() == genre.lower()]
    if available is not None:
        books = [b for b in books if b["available"] == available]
    if search:
        q = search.lower()
        books = [b for b in books if q in b["title"].lower() or q in b["author"].lower() or q in (b.get("description") or "").lower()]
    return books

@app.post("/books", response_model=Book, status_code=201, tags=["Books"])
async def create_book(book: BookCreate):
    """Create a new book in the library."""
    bid = str(uuid.uuid4())
    new_book = {
        "id": bid,
        **book.model_dump(),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    BOOKS[bid] = new_book
    return new_book

@app.get("/books/{book_id}", response_model=Book, tags=["Books"])
async def get_book(book_id: str):
    """Get a specific book by ID."""
    if book_id not in BOOKS:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    return BOOKS[book_id]

@app.put("/books/{book_id}", response_model=Book, tags=["Books"])
async def update_book(book_id: str, updates: BookUpdate):
    """Update an existing book's details."""
    if book_id not in BOOKS:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    book = BOOKS[book_id]
    patch = updates.model_dump(exclude_none=True)
    book.update(patch)
    book["updated_at"] = now_iso()
    return book

@app.delete("/books/{book_id}", tags=["Books"])
async def delete_book(book_id: str):
    """Delete a book from the library."""
    if book_id not in BOOKS:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    del BOOKS[book_id]
    return {"message": f"Book '{book_id}' deleted successfully"}

@app.get("/genres", tags=["Books"])
async def list_genres():
    """Get all unique genres in the library."""
    genres = sorted(set(b["genre"] for b in BOOKS.values()))
    return {"genres": genres}

@app.post("/books/{book_id}/borrow", response_model=Book, tags=["Books"])
async def borrow_book(book_id: str):
    """Mark a book as borrowed (unavailable)."""
    if book_id not in BOOKS:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    if not BOOKS[book_id]["available"]:
        raise HTTPException(status_code=409, detail="Book is already borrowed")
    BOOKS[book_id]["available"] = False
    BOOKS[book_id]["updated_at"] = now_iso()
    return BOOKS[book_id]

@app.post("/books/{book_id}/return", response_model=Book, tags=["Books"])
async def return_book(book_id: str):
    """Mark a book as returned (available)."""
    if book_id not in BOOKS:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")
    if BOOKS[book_id]["available"]:
        raise HTTPException(status_code=409, detail="Book is already available")
    BOOKS[book_id]["available"] = True
    BOOKS[book_id]["updated_at"] = now_iso()
    return BOOKS[book_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
