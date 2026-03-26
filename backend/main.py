"""
TitanTool  —  FastAPI backend entry point.

Run with:
    uvicorn backend.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .database import init_db
from .routers import jobs, presets, projects, symbols

app = FastAPI(
    title="TitanTool",
    description="Electrical takeoff automation for residential floor plans",
    version="0.1.0",
)

# ── CORS (allow React dev server + production same-origin) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
app.include_router(projects.router)
app.include_router(jobs.router)
app.include_router(symbols.router)
app.include_router(presets.router)

# ── Serve uploaded files and output images ──
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
UPLOADS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

# ── Serve compiled React frontend (production) ──
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


@app.on_event("startup")
def on_startup():
    init_db()
    print("✓ TitanTool API ready")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
