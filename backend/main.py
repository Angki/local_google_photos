# ==============================================================================
# File: backend/main.py
# Description: Main entry point for the FastAPI application. Serves the Google
#              Photos clone web UI, handles WebSocket lifecycle, lifespan hooks,
#              health probes, and initializes database migrations.
# ==============================================================================

import asyncio
from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.config import APP_ROOT, SOURCE_DATA_DIR
from backend.database import get_db_connection, get_library_stats, init_db
from backend.routes import api_router, scanner
import backend.routes as routes_module

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("GooglePhotosApp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan context manager replacing deprecated startup/shutdown events."""
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

    yield
    logger.info("Shutting down Google Photos Local application...")


# Create FastAPI instance
app = FastAPI(
    title="Google Photos Local Takeout Archive",
    description="Enterprise-grade local photo management system indexing Google Takeout archives",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security and cache-control middleware
@app.middleware("http")
async def add_security_and_cache_headers(request, call_next):
    response = await call_next(request)
    # Enterprise security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Dynamic cache control for frontend development assets
    path = request.url.path
    if path.endswith(".css") or path.endswith(".js") or path == "/" or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Register Health Probes
@app.get("/healthz", tags=["System"], summary="Liveness Probe")
def liveness_check():
    """Liveness probe indicating whether the server process is alive and responsive."""
    return {"status": "healthy", "service": "google-photos-local", "version": "1.1.0"}


@app.get("/readyz", tags=["System"], summary="Readiness Probe")
def readiness_check():
    """Readiness probe verifying database connectivity and storage directory status."""
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1;").fetchone()
        return {
            "status": "ready",
            "database": "connected",
            "source_dir_exists": SOURCE_DATA_DIR.is_dir(),
        }
    except Exception as e:
        return Response(
            content=json.dumps({"status": "unavailable", "error": str(e)}),
            status_code=503,
            media_type="application/json",
        )


# Register API & WebSocket routes
app.include_router(api_router)

# Mount frontend static directory
FRONTEND_DIR = APP_ROOT / "frontend"

# Favicon handling to prevent 404
@app.get("/favicon.ico", include_in_schema=False)
def get_favicon():
    favicon_file = FRONTEND_DIR / "favicon.svg"
    if favicon_file.is_file():
        return FileResponse(str(favicon_file), media_type="image/svg+xml")
    return Response(status_code=204)


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
