"""
main.py
───────
FastAPI application entry point.
Run with: uvicorn main:app --reload --port 8000
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from src.config import settings
from src.faq.loader import faq_store
from src.llm.nim_client import nim_client
from src.routes.api import router as api_router
from src.connectors.webhook import router as webhook_router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG if settings.app_env == "development" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Loading FAQ data from: %s", settings.faq_file)
    faq_store.load()
    logger.info("FAQ store ready — %d entries loaded", len(faq_store.all_items()))
    logger.info("NIM model: %s  base: %s", settings.nim_model, settings.nim_base_url)
    yield
    # Shutdown
    await nim_client.aclose()
    logger.info("NIM client closed.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="NIM FAQ Assistant",
    description="AI-powered FAQ + General Assistant backed by NVIDIA NIM",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router)
app.include_router(webhook_router)

# ── Serve frontend static files (when built) ──────────────────────────────────
# TODO: For production, serve the built frontend from this path.
#       Run `npm run build` in /frontend first, then output goes to frontend/dist.
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=(settings.app_env == "development"),
    )
