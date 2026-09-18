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

### 📂 4. Multi-Select & Custom Virtual Albums
- Hover checkmarks and **Shift+Click** range selection optimized for hundreds of items without browser lag.
- Floating selection action bar: **Add to Album**, **Delete Selected**, and **Select All Visible**.
- Virtual albums organize photos without duplicating or moving physical files on disk.

### 🗑️ 5. Safe Two-Tier Trash System
- **Soft Delete by Default**: Deleted photos are hidden from timeline and moved to `🗑️ Trash` with a live count badge.
- **Batch & Single Restore**: Instantly restore deleted photos back to their timeline position and albums.
- **Permanent Purge**: Hard delete physically wipes media files, companion JSON files, and thumbnails from disk with safety confirmation.
- **Empty Trash**: One-click "Kosongkan Sampah" button to clean up all deleted items.

### ⚡ 6. High-Speed Media Processing
- **Compressed WebP Thumbnails**: On-demand and batch background generation for instant loading.
- **Video Playback with Seeking**: Custom HTTP Range streaming handler supporting `.mp4`, `.mov`, `.m4v`, `.webm`, `.mkv`, and `.3gp`.
- **FFmpeg Frame Thumbnails**: Automatically extracts representative video frames for video previews.
- **Non-Blocking Background Worker**: Live indexing progress displayed via real-time WebSocket with automatic HTTP polling fallback.

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
