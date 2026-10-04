# Google Photos Local Takeout Gallery 📸

[![CI Test & Quality Suite](https://github.com/Angki/local_google_photos/actions/workflows/ci.yml/badge.svg)](https://github.com/Angki/local_google_photos/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.103+-009688.svg)](https://fastapi.tiangolo.com)
[![PyTorch CLIP](https://img.shields.io/badge/AI-OpenAI%20CLIP%20ViT--B%2F32-EE4C2C.svg)](https://github.com/openai/CLIP)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Privacy First](https://img.shields.io/badge/Data-100%25%20Local%20%26%20Private-success.svg)](#)

A high-performance, private, 100% local photo and video gallery application designed specifically for **Google Takeout** exports. 

It recreates the authentic Google Photos experience directly from your hard drive: an interactive chronological timeline, expandable year/month scrubber, natural-language semantic AI search (powered by local OpenAI CLIP), an interactive Photo Map with GPS clustering, virtual albums, and a safe two-tier trash system.

---

## 💡 The Problem with Google Takeout

When exporting your photo library from Google Photos via Google Takeout:
1. **Scrambled Timestamps**: File modification dates are reset to the day you downloaded the archive, ruining chronological order.
2. **Disconnected Metadata**: Capture dates, GPS locations, descriptions, and people tags are separated into companion `.json` / `.supplemental-metadata.json` files.
3. **No Native Viewer**: Google provides raw folders without any user-friendly interface to browse, search, or navigate your memories.

**Google Photos Local Takeout Gallery** solves this by scanning your Takeout archive, parsing all companion JSON metadata, caching fast WebP thumbnails, generating local AI vector embeddings, and serving a fluid web application—all without uploading a single byte to the cloud.

---

## ✨ Features

### 📅 1. Chronological Timeline & Hierarchical Scrubber
- Accurately resolves original capture timestamps (`photoTakenTime`) from Google Takeout JSON files.
- Automatically groups photos into Year and Month sections.
- Fast, smooth infinite scroll rendered via dynamic Intersection Observers (batches of 60 items).
- Right-rail navigation scrubber with collapsible year groups and direct month jumps (`Jan`–`Dec`) with live scroll-spy tracking.

### 🗺️ 2. Interactive Photo Map & Geolocation
- **Timeline GPS Badges (📍)**: Identifies all geotagged photos at a glance.
- **Dedicated Fullscreen Map (`🗺️ Photo Map`)**: Plots all geotagged coordinates using Leaflet.js with smooth marker clustering.
- **Theme-Aware Map Tiles**: Automatically matches Dark Mode (CartoDB Dark Matter) and Light Mode (CartoDB Voyager/Positron).
- **Synchronized Viewport Tray**: Bottom drawer dynamically filters and displays thumbnails located inside the currently visible map boundary.
- **Lightbox Mini-Map**: Inspect any photo to view its coordinates, open an interactive mini-map with a direct "Fly to on Map" button, or open in Google Maps.

### 🧠 3. Local AI Vision & Natural Language Semantic Search
- **OpenAI CLIP Model (`clip-vit-base-patch32`)**: Runs completely offline using PyTorch (CUDA GPU accelerated or CPU).
- **Natural Language Search**: Query concepts like *"sunset at the beach"*, *"dog playing in grass"*, or *"makan bersama"* to match 512-dimensional vector similarities.
- **Zero-Shot Categorization**: Automatically classifies media into categories like *Artwork, Documents, Nature, Receipts, People, Food, Screenshots, Pets & Animals, Architecture, Vehicles, Videos*.

### ⭐ 4. Favorites & Starred Collection
- **1-Click Favoriting**: Star photos and videos directly from the Lightbox viewer or via multi-select batch action.
- **Dedicated Favorites Filter**: Instant `⭐ Favorites` filter chip in the navigation bar to isolate your best memories.
- **Visual Star Badges**: Displays golden badges on favorited items throughout the timeline and album views.

### ⚡ 5. Keyboard Navigation & Slideshow Mode
- **Full Keyboard Control**: Fast browsing with `←` / `→` (prev/next), `F` (toggle favorite), `D` (download original), `Space` (slideshow toggle), `I` (info inspector), and `Del` / `Backspace` (trash).
- **Interactive Shortcuts Guide (`⌨️` / `?`)**: Built-in modal dialog detailing all shortcut keys.
- **Auto-Play Slideshow**: Smooth auto-advancing slideshow (3.5s interval) to sit back and enjoy your photo archive.
- **Direct Media Download**: Easily download original full-resolution files directly from the browser.

### 📂 6. Multi-Select & Custom Virtual Albums
- Hover checkmarks and **Shift+Click** range selection optimized for hundreds of items without browser lag.
- Floating selection action bar: **Add to Album**, **Favorit**, **Delete Selected**, and **Select All Visible**.
- Virtual albums organize photos without duplicating or moving physical files on disk.

### 🗑️ 7. Safe Two-Tier Trash System
- **Soft Delete by Default**: Deleted photos are hidden from timeline and moved to `🗑️ Trash` with a live count badge.
- **Batch & Single Restore**: Instantly restore deleted photos back to their timeline position and albums.
- **Permanent Purge**: Hard delete physically wipes media files, companion JSON files, and thumbnails from disk with safety confirmation.
- **Empty Trash**: One-click "Kosongkan Sampah" button to clean up all deleted items.

### 🎞️ 8. "On This Day" Throwbacks & Memories Carousel
- Automatically scans your archive for historical moments taken on the current calendar day (e.g. *1 year ago*, *3 years ago*, *5 years ago*).
- Displays an interactive top carousel with gradient backdrops and count pills.
- Clicking any memory tile launches the Lightbox at that historical memory.

### 🧹 9. Smart Duplicate Detector & Safe Storage Cleanup
- **Exact & Near-Duplicate Detection**: Combines fast chunked sha256 hashing and fuzzy timestamp clustering.
- **Dedicated View (`👯 Duplicates`)**: Categorizes duplicates into groups, highlighting size savings.
- **1-Click Smart Auto-Select**: Automatically selects duplicates while preserving the oldest or highest-resolution primary copy.
- **Safe Soft-Delete**: Moves redundant copies to the safe Trash system without risk of data loss.

### 🎬 10. Apple & Samsung Live Photo / Motion Photo Playback
- **Embedded Motion Extraction**: Automatically parses JPEG micro-video payloads (XMP `GCamera:MicroVideoOffset` and Apple paired `.mov` files).
- **Interactive Playback**: Toggle the `LIVE` button in Lightbox or press `L` to watch the 3-second live moment before returning to high-res still.

### 📱 11. Progressive Web App (PWA) Offline-Ready & App Install
- Full `manifest.webmanifest` and Service Worker (`sw.js`).
- Installable directly to Windows Desktop, macOS Dock, or Android/iOS homescreen.
- Caches UI assets and icons for immediate launch.

### 🎨 12. In-Browser Photo Editing Suite (Studio)
- **Tune & Adjustments**: Real-time 60fps sliders for Brightness, Contrast, Saturation, and Color Warmth.
- **✨ Auto-Enhance**: 1-click automatic contrast and color tone optimization.
- **Transform**: 90° rotation and horizontal flip.
- **Non-Destructive Saving**: Save as a new copy (`filename_edited_timestamp.jpg`) or safely overwrite with atomic backup.

### 👁️ 13. Real-Time Hot Folder Watcher
- Monitored continuously via Python `watchdog` on `SOURCE_DATA_DIR`.
- Instantly ingests new photos or videos dropped into the folder without needing manual re-indexing.
- Automatically generates WebP thumbnails and broadcasts real-time WebSocket toast notifications.

### 🎥 14. Cinematic Story Mode & Ken Burns Slideshow
- Smooth slow pan/zoom animation on photo transitions (`ken-burns` keyframe animation).
- Toggle auto-play with `Space` or top bar button.

### ⚡ 15. High-Speed Media Processing & Enterprise Observability
- **Compressed WebP Thumbnails**: On-demand and batch background generation for instant loading.
- **Video Playback with Seeking**: Custom HTTP Range streaming handler supporting `.mp4`, `.mov`, `.m4v`, `.webm`, `.mkv`, and `.3gp`.
- **FFmpeg Frame Thumbnails**: Automatically extracts representative video frames for video previews.
- **Reverse Geocoding**: Automatically turns raw GPS coordinates into human-readable city, state, and country names.
- **Observability**: Structured request latency logs with correlation IDs (`X-Request-ID`) and process times (`X-Process-Time`).

### 🔍 16. Live Text & OCR Search (Google Lens Style)
- **100% Offline Optical Character Recognition**: Powered by local Tesseract OCR engine without external cloud APIs.
- **Full-Text Search Indexing**: Extracts text from receipts, documents, screenshots, signs, and labels directly into SQLite full-text and semantic queries (`ocr_text LIKE ?`).
- **Interactive Lightbox Scanner**: Click the OCR button (`🔍`) in the Lightbox toolbar to extract text on-the-fly and copy it with 1-click in the result modal.

### 📱 17. Home Wi-Fi LAN Mode & Mobile Quick-Access QR Code
- **Automatic Local IP Detection**: Detects your computer's local Wi-Fi IPv4 address (e.g. `http://192.168.18.27:8000`).
- **Zero-Dependency SVG QR Code**: Generates crisp, scalable vector QR codes on-the-fly without third-party web services.
- **Instant Cross-Device Browsing**: Scan with any iPhone, iPad, Android phone, or tablet on the same Wi-Fi network to browse your archive or install as a PWA app.

### 🔒 18. Locked Folder with 4-Digit PIN (Private Vault)
- **Zero-Leakage Privacy**: Photos marked as locked (`is_locked = 1`) are completely hidden from the main timeline, "On This Day" memories, search suggestions, and the Photo Map.
- **Interactive Numeric Keypad**: Beautiful 4-digit PIN setup and authentication modal with visual dot feedback.
- **Time-Limited Session Token**: Issues a cryptographic 15-minute access token for private viewing.
- **Seamless Management**: 1-click locking from multi-select toolbar or Lightbox, and instant unlocking back to the public gallery.

### 📤 19. Direct Mobile & Web Wi-Fi Uploader
- **Instant Cross-Device Upload**: Upload photos and videos directly from mobile phones over Wi-Fi LAN or desktop browsers without cloud intermediaries.
- **Full-Window Drag-and-Drop**: Drop files anywhere onto the gallery interface to trigger upload progress dialog.
- **Intelligent Organization**: Saves media automatically into `Photos from {year}` based on parsed EXIF timestamps, creates WebP thumbnails, and broadcasts live WebSocket events to all active devices.

### 📦 20. 1-Click Batch ZIP Archive Downloader
- **Bulk Media Export**: Pack selected photos or entire albums into an uncompressed/compressed ZIP archive on the fly.
- **Zero-Disk Overhead**: Streams the archive directly into the browser using chunked streaming responses, preserving original file resolutions and names.
- **Album & Selection Integration**: Accessible directly from the floating multi-selection toolbar and the album header.

### ✏️ 21. Manual Metadata & Location Editor
- **Capture Date & Time Correction**: Adjust incorrect or missing timestamps via datetime picker, updating timeline hierarchy and chronological sorting.
- **Interactive Leaflet Map Pin Picker**: Click or drag a pin anywhere on the world map to set or modify GPS coordinates.
- **Automated Reverse Geocoding**: Automatically enriches modified coordinates with city, state, country, and location labels.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Browser UI                            │
│   (Timeline, Infinite Scroll, Leaflet Map, Albums, Trash)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / WebSocket
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Backend Server                   │
│   (REST Endpoints, Streaming Media, Range Video Handler)     │
└───────────────┬──────────────────────────────┬──────────────┘
                │                              │
┌───────────────▼──────────────┐┌──────────────▼──────────────┐
│  Background Library Scanner  ││     AI Vision Engine        │
│  - Stage 1: Fast JSON Read   ││  - PyTorch + CLIP ViT-B/32  │
│  - Stage 2: WebP Thumbnails  ││  - 512-dim Cosine Sim       │
└───────────────┬──────────────┘└──────────────┬──────────────┘
                │                              │
┌───────────────▼──────────────────────────────▼──────────────┐
│                  SQLite Database (photos.db)                │
│    Photos, Metadata, Geo Index, Vectors, Virtual Albums     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python**: 3.10, 3.11, or 3.12
- **FFmpeg** *(Optional, recommended)*: For video thumbnail frame extraction. Ensure `ffmpeg` is available on your system `PATH`.
- **CUDA** *(Optional)*: If you have an NVIDIA GPU, PyTorch with CUDA enables lightning-fast AI indexing and semantic search.

### 2. Clone the Repository
```bash
git clone https://github.com/Angki/local_google_photos.git
cd local_google_photos
```

### 3. Create a Virtual Environment & Install Dependencies
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> **Tip for GPU Acceleration**: To enable NVIDIA CUDA for CLIP, install the CUDA-enabled PyTorch build from [pytorch.org](https://pytorch.org/get-started/locally/):
> ```bash
> pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
> ```

> **Tip for Apple HEIC / HEIF Images**:
> ```bash
> pip install pillow-heif
> ```

### 4. Configure Your Google Takeout Path

Create a `.env` file from the example template:
```bash
# Windows (cmd)
copy .env.example .env

# Windows (PowerShell) / Linux / macOS
cp .env.example .env
```

Open `.env` and set `TAKEOUT_DIR` to the folder containing your exported Google Photos:
```ini
TAKEOUT_DIR=D:\Takeout\Google Photos
```
*(Your Takeout directory should contain folders like `Photos from 2024`, `Photos from 2023`, etc., or your album folders).*

Alternatively, you can skip `.env` and pass the path directly via CLI:
```bash
python run.py --source "D:\Takeout\Google Photos"
```

### 5. Launch the Application

**Windows:**
Double-click `start.bat` or run:
```cmd
start.bat
```

**Linux / macOS:**
```bash
chmod +x start.sh
./start.sh
```

**Manual Python Execution:**
```bash
python run.py
```

The application will start and automatically open your default browser at:
👉 **http://127.0.0.1:8000**

---

## ⚙️ Configuration & CLI Options

### Environment Variables (`.env`)

| Variable | Description | Default |
|---|---|---|
| `TAKEOUT_DIR` | Path to extracted Google Photos Takeout folder | `E:\Takeout\Google Photos` (or `./takeout`) |
| `HOST` | Server bind address | `127.0.0.1` |
| `PORT` | Server HTTP port | `8000` |
| `DATA_DIR` | Runtime directory for SQLite database and thumbnails | `./data` |
| `FFMPEG_PATH` | Explicit path to `ffmpeg.exe` binary | Searches system `PATH` |

### CLI Options (`python run.py --help`)

```
usage: run.py [-h] [--source SOURCE] [--host HOST] [--port PORT] [--no-browser]

options:
  -h, --help            Show this help message and exit
  --source, -s SOURCE   Path to extracted Google Photos Takeout directory (overrides .env)
  --host HOST           Host address to bind server (default: 127.0.0.1)
  --port, -p PORT       Port number to bind server (default: 8000)
  --no-browser          Disable automatic browser opening on launch
```

---

## 📡 REST API & WebSocket Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/healthz` | Liveness probe indicating server health |
| `GET` | `/readyz` | Readiness probe checking database connectivity and storage status |
| `GET` | `/api/photos` | Paginated timeline photos (`limit`, `offset`, `category`, `year`, `month`) |
| `GET` | `/api/photos/hierarchy` | Year and month distribution for the timeline scrubber |
| `GET` | `/api/photos/{photo_id}` | Detailed metadata, tags, GPS coordinates, and companion info |
| `POST`| `/api/photos/{photo_id}/favorite` | Toggle favorite (star) status for a single photo |
| `POST`| `/api/photos/favorite` | Batch update favorite status for multiple photos |
| `GET` | `/api/photos/favorites/count` | Total count of favorited photos |
| `GET` | `/api/photos/trash` | List of soft-deleted items currently in Trash |
| `GET` | `/api/photos/trash/count` | Total count of soft-deleted items in Trash |
| `POST`| `/api/photos/delete` | Soft delete or hard delete photos (`hard_delete: bool`) |
| `POST`| `/api/photos/restore` | Restore soft-deleted photos back to timeline and albums |
| `POST`| `/api/photos/delete-permanent` | Permanently remove selected photos and JSON metadata from disk |
| `POST`| `/api/photos/trash/empty` | Empty the entire trash and wipe physical media from disk |
| `GET` | `/api/geo/points` | Fast retrieval of all geotagged photos for Photo Map |
| `GET` | `/api/albums` | List all virtual albums with photo counts |
| `POST`| `/api/albums` | Create a new custom album |
| `GET` | `/api/albums/{id}/photos` | Fetch photos belonging to an album |
| `POST`| `/api/albums/{id}/photos` | Add photos to an existing album |
| `DELETE`| `/api/albums/{id}` | Delete an album (does not delete original photos) |
| `GET` | `/api/search` | Natural language semantic vector search using CLIP |
| `GET` | `/api/thumbnails/{photo_id}` | High-speed WebP thumbnail image |
| `GET` | `/api/media/{photo_id}` | Full-resolution original photo or streamed video with HTTP Range seeking |
| `GET` | `/api/stats` | Overall library statistics (total media, indexed, thumbnails, AI processed) |
| `POST`| `/api/scan/start` | Trigger background indexing scan |
| `POST`| `/api/scan/pause` | Pause background indexing worker |
| `POST`| `/api/scan/resume` | Resume background indexing worker |
| `WS`  | `/ws/status` | Real-time WebSocket connection for background scanner progress |

---

## 🧪 Testing

Run the automated test suite using Python's built-in `unittest`:

```bash
python -m unittest discover -s tests
```

---

## 📁 Repository Structure

```
local_google_photos/
├── backend/
│   ├── __init__.py
│   ├── config.py              # Environment configuration & path resolution
│   ├── database.py            # SQLite schemas, vector storage, and operations
│   ├── metadata_parser.py     # Google Takeout companion JSON resolution
│   ├── ai_engine.py           # PyTorch CLIP model loader & cosine similarity
│   ├── thumbnail_manager.py   # WebP thumbnail cache & FFmpeg frame extraction
│   ├── scanner.py             # Two-stage non-blocking background indexer
│   ├── routes.py              # REST API & WebSocket handlers
│   └── main.py                # FastAPI lifecycle & static mount
├── frontend/
│   ├── index.html             # Google Photos UI structure (Timeline, Map, Albums, Trash)
│   ├── styles.css             # Material Design 3 theme (Light / Dark mode)
│   ├── app.js                 # UI interactions, virtual scrolling & Leaflet map
│   └── favicon.svg            # Custom application icon
├── scripts/
│   ├── generate_video_thumbnails.py # Multi-threaded video frame extractor
│   ├── qa_qc_runner.py        # Automated QA/QC verification suite
│   └── debug_audit.py         # Diagnostic tool for database audits
├── tests/
│   └── test_api.py            # Unit test suite
├── .env.example               # Configuration template
├── .gitattributes             # Line ending normalization
├── .gitignore                 # Strict rules to prevent database/thumbnail leakage
├── LICENSE                    # MIT License
├── README.md                  # Project documentation
├── requirements.txt           # Python dependencies
├── run.py                     # Python launcher with CLI argument support
├── start.bat                  # Windows one-click launcher
└── start.sh                   # Linux/macOS launcher
```

---

## 🛡️ Privacy & Security
 
- **Zero Cloud Leakage**: This tool never uploads your photos, thumbnails, metadata, or AI embeddings to any external server.
- **Local AI Execution**: OpenAI CLIP runs locally on your own hardware via PyTorch.
- **Strict Git Rules**: The repository's `.gitignore` guarantees that your SQLite database (`photos.db`), thumbnails (`data/thumbnails/`), and personal files will never be tracked or pushed to Git.
- See our [Security Policy](SECURITY.md) for vulnerability disclosure details.

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) before submitting Pull Requests.

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.
