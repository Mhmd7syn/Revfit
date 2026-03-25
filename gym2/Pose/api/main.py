"""
main.py – FastAPI application entry point
Run with:  uvicorn main:app --reload --port 8000
"""
import os
import sys

# Ensure Pose/Code and Pose/api are on sys.path
_API_DIR = os.path.dirname(os.path.abspath(__file__))
_POSE_CODE_DIR = os.path.abspath(os.path.join(_API_DIR, '..', 'Code'))
for _p in [_API_DIR, _POSE_CODE_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from endpoints.pose import router as pose_router

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="REV FIT AI – Pose Analysis API",
    description="Upload gym exercise videos and receive pose-annotated output with form feedback.",
    version="1.0.0",
)

# ── CORS – allow Flutter (any origin) ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static outputs ─────────────────────────────────────────────────────────
_OUTPUTS_DIR = os.path.join(_API_DIR, "outputs")
os.makedirs(_OUTPUTS_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=_OUTPUTS_DIR), name="outputs")

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(pose_router)


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "REV FIT AI Pose Analysis API is running."}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
