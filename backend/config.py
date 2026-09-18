# ==============================================================================
# File: backend/config.py
# Description: Configuration constants, paths, and settings for Google Photos Local App
#
# CHANGELOG:
# 2026-09-05 - Initial creation: Configured source folder, target year filtering (2013-2026),
#              database paths, thumbnail cache, and AI model parameters.
# ==============================================================================

import os
import re
from pathlib import Path

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Base Paths
APP_ROOT = Path(__file__).resolve().parent.parent

# Configurable Source Data Directory:
# Priority 1: Environment variable TAKEOUT_DIR or GOOGLE_PHOTOS_TAKEOUT_DIR
# Priority 2: Existing local default 'E:\Takeout\Google Photos'
# Priority 3: Fallback 'takeout' folder within project root
_env_takeout = os.environ.get("TAKEOUT_DIR") or os.environ.get("GOOGLE_PHOTOS_TAKEOUT_DIR")
if _env_takeout:
    SOURCE_DATA_DIR = Path(_env_takeout).resolve()
elif Path(r"E:\Takeout\Google Photos").is_dir():
    SOURCE_DATA_DIR = Path(r"E:\Takeout\Google Photos")
else:
    SOURCE_DATA_DIR = (APP_ROOT / "takeout").resolve()

# Runtime Data Directories
DATA_DIR = Path(os.environ.get("DATA_DIR", APP_ROOT / "data")).resolve()
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", DATA_DIR / "photos.db")).resolve()
THUMBNAILS_DIR = Path(os.environ.get("THUMBNAILS_DIR", DATA_DIR / "thumbnails")).resolve()

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

# Target Folders Filter: Support all year archives (Photos from YYYY) and custom Takeout albums
YEAR_FOLDER_PATTERN = re.compile(r"^Photos from (\d{4})$", re.IGNORECASE)

EXCLUDED_FOLDERS = {
    ".local-photo-manager",
    "local-google-photos",
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "thumbnails",
    "indexes",
    "models",
    "tmp",
    "logs",
    "video-proxies",
}

def is_target_folder(folder_name: str) -> bool:
    """
    Returns True for any valid Google Photos Takeout media folder,
    including year archives ('Photos from YYYY') and user album folders,
    while excluding internal application and system directories.
    """
    cleaned = folder_name.strip()
    if not cleaned or cleaned.startswith("."):
        return False
    if cleaned.lower() in {f.lower() for f in EXCLUDED_FOLDERS}:
        return False
    return True

# Media File Extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp", ".gif", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv", ".3gp"}
ALL_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

# Server Configuration
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))

# Thumbnail Settings
THUMBNAIL_SIZE = (420, 420)
THUMBNAIL_QUALITY = 82

# AI Vision & CLIP Configuration
CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"
EMBEDDING_DIM = 512

# Predefined categories for zero-shot classification
DEFAULT_CATEGORIES = [
    "artwork",
    "documents",
    "nature",
    "receipts",
    "people",
    "food",
    "screenshots",
    "pets & animals",
    "architecture",
    "vehicles",
    "landscapes",
    "events"
]
