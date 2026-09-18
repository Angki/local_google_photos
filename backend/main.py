# ==============================================================================
# File: backend/main.py
# Description: Main entry point for the FastAPI application. Serves the Google
#              Photos clone web UI, handles WebSocket lifecycle, and initializes
#              the database on startup.
#
# CHANGELOG:
# 2026-09-05 - Initial creation: Configured CORS, static files serving,
#              startup event hooks, and auto-indexing trigger for new databases.
# ==============================================================================

import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.config import APP_ROOT, SOURCE_DATA_DIR
from backend.database import get_library_stats, init_db
from backend.routes import api_router, scanner
import backend.routes as routes_module

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("GooglePhotosApp")

# Create FastAPI instance
app = FastAPI(
    title="Google Photos Local Takeout Archive",
    description="Local AI-powered photo management application for Google Takeout (2013-2026)",
    version="1.0.0",
)

# Enable CORS for local development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API & WebSocket routes
app.include_router(api_router)

# Prevent browser from aggressively caching HTML, CSS, and JS during local development
@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith(".css") or path.endswith(".js") or path == "/" or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.on_event("startup")
async def on_startup():
    """Application initialization on startup."""
    logger.info("Initializing Google Photos Local application...")
    init_db()

    # Capture current asyncio running loop for background thread WebSocket broadcasts
    routes_module._loop = asyncio.get_running_loop()

    # Check database status; if empty, kick off initial index scan automatically
    stats = get_library_stats()
    total_photos = stats.get("total_media", 0) if stats else 0
    if total_photos == 0:
        if SOURCE_DATA_DIR.is_dir():
            logger.info("Empty database detected. Triggering initial background scan of Google Photos...")
            scanner.start()
        else:
            logger.warning(
                f"Source directory '{SOURCE_DATA_DIR}' not found. "
                "Please configure TAKEOUT_DIR in your .env or launch using 'python run.py --source <path>'."
            )
    else:
        logger.info(f"Database ready with {total_photos} photos and videos.")


# Favicon handling to prevent 404
@app.get("/favicon.ico", include_in_schema=False)
def get_favicon():
    favicon_file = FRONTEND_DIR / "favicon.svg"
    if favicon_file.is_file():
        return FileResponse(str(favicon_file), media_type="image/svg+xml")
    return Response(status_code=204)


# Mount frontend static directory
FRONTEND_DIR = APP_ROOT / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
