# ==============================================================================
# File: backend/routes.py
# Description: FastAPI REST API routes and WebSocket handlers for timeline,
#              photo streaming, HTTP Range video playback, semantic search,
#              and background worker management with strict Pydantic models.
# ==============================================================================

import asyncio
import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse

from backend.ai_engine import ai_engine
from backend.config import THUMBNAILS_DIR
from backend.database import (
    get_db_connection,
    get_all_embeddings,
    get_category_counts,
    get_library_stats,
    get_photo_by_id,
    get_photos,
    get_geo_points,
    get_timeline_hierarchy,
    update_thumbnail_path,
    get_albums,
    create_album,
    add_photos_to_album,
    delete_photos,
    remove_photos_from_album,
    delete_album,
    restore_photos,
    get_deleted_photos,
    get_trash_count,
    permanent_delete_photos,
    delete_photos_from_disk_and_db,
)
from backend.scanner import LibraryScanner
from backend.thumbnail_manager import generate_thumbnail

api_router = APIRouter()


# ==============================================================================
# Pydantic Request & Response Schemas (Enterprise OpenAPI Contracts)
# ==============================================================================

class DeletePhotosRequest(BaseModel):
    photo_ids: List[int] = Field(..., description="List of photo IDs to delete")
    delete_from_disk: bool = Field(False, description="If true, permanently wipes file from disk")


class RestorePhotosRequest(BaseModel):
    photo_ids: List[int] = Field(..., description="List of photo IDs to restore")


class CreateAlbumRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="Album name")


class AddPhotosToAlbumRequest(BaseModel):
    photo_ids: List[int] = Field(..., description="List of photo IDs to add to the album")


class TimelineMonthItem(BaseModel):
    month: int
    name: str
    count: int


class TimelineYearItem(BaseModel):
    year: int
    total: int
    months: List[TimelineMonthItem]


class TimelineResponse(BaseModel):
    timeline: List[TimelineYearItem]


class PhotoListResponse(BaseModel):
    photos: List[Dict[str, Any]]
    count: int
    offset: int
    limit: int


class TrashListResponse(BaseModel):
    photos: List[Dict[str, Any]]
    count: int
    total: int
    limit: int
    offset: int


class TrashCountResponse(BaseModel):
    total: int


class DeleteActionResponse(BaseModel):
    success: bool
    deleted_count: int
    photo_ids: Optional[List[int]] = None
    delete_from_disk: Optional[bool] = False
    media_files_deleted: Optional[int] = None
    json_files_deleted: Optional[int] = None
    thumbnails_deleted: Optional[int] = None
    message: Optional[str] = None


class RestoreActionResponse(BaseModel):
    success: bool
    restored_count: int
    photo_ids: List[int]


class GeoPointsResponse(BaseModel):
    count: int
    points: List[Dict[str, Any]]


class AlbumCreateResponse(BaseModel):
    success: bool
    album_id: int


class AlbumMutationResponse(BaseModel):
    success: bool
    added_count: Optional[int] = None
    removed_count: Optional[int] = None


class AlbumPhotosResponse(BaseModel):
    album_id: int
    photos: List[Dict[str, Any]]


class SimpleSuccessResponse(BaseModel):
    success: bool
    message: Optional[str] = None


class SearchResponse(BaseModel):
    mode: str
    query: str
    count: int
    photos: List[Dict[str, Any]]


class StatsResponse(BaseModel):
    stats: Dict[str, Any]


class CategoriesResponse(BaseModel):
    categories: Dict[str, int]


class ScanControlResponse(BaseModel):
    success: bool
    status: Dict[str, Any]


# ==============================================================================
# Global WebSocket Connection Manager
# ==============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        text = json.dumps(message)
        dead_conns = []
        for connection in self.active_connections:
            try:
                await connection.send_text(text)
            except Exception:
                dead_conns.append(connection)
        for dead in dead_conns:
            self.disconnect(dead)


ws_manager = ConnectionManager()
_loop = None


def broadcast_progress(status_data: dict):
    """Bridge for background scanner thread to broadcast to async WebSocket clients."""
    global _loop
    if _loop and not _loop.is_closed():
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(status_data), _loop)


# Scanner singleton
scanner = LibraryScanner(broadcast_callback=broadcast_progress)


# ==============================================================================
# WebSocket & Scanner Status Endpoints
# ==============================================================================

@api_router.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    await ws_manager.connect(websocket)
    # Send current state immediately on connect
    await websocket.send_text(json.dumps(scanner.get_status()))
    try:
        while True:
            # Keep connection open and handle client ping/pong
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@api_router.get("/ws/status", tags=["Scanner"], summary="Scanner Status (HTTP Fallback)")
def get_ws_status_http() -> Dict[str, Any]:
    """Fallback HTTP endpoint for scanner status if WebSocket is unavailable or queried via HTTP."""
    return scanner.get_status()


# ==============================================================================
# Timeline & Photos Endpoints
# ==============================================================================

@api_router.get("/api/timeline", response_model=TimelineResponse, tags=["Timeline"], summary="Timeline Hierarchy")
def get_timeline():
    """Returns Year -> Month timeline tree with photo counts."""
    return {"timeline": get_timeline_hierarchy()}


@api_router.get("/api/photos", response_model=PhotoListResponse, tags=["Photos"], summary="List Photos")
def list_photos(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    media_type: Optional[str] = Query(None),
    has_geo: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(80, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Returns paginated photos with optional timeline and category filters."""
    photos = get_photos(
        year=year,
        month=month,
        category=category,
        media_type=media_type,
        has_geo=has_geo,
        search_text=search,
        limit=limit,
        offset=offset,
    )
    return {"photos": photos, "count": len(photos), "offset": offset, "limit": limit}


@api_router.get("/api/photos/trash", response_model=TrashListResponse, tags=["Trash"], summary="List Trash Photos")
def api_get_trash(limit: int = Query(120, ge=1, le=500), offset: int = Query(0, ge=0)):
    """Fetches photos in the Trash along with total trash count."""
    photos = get_deleted_photos(limit=limit, offset=offset)
    total = get_trash_count()
    return {"photos": photos, "count": len(photos), "total": total, "limit": limit, "offset": offset}


@api_router.get("/api/photos/trash/count", response_model=TrashCountResponse, tags=["Trash"], summary="Trash Total Count")
def api_get_trash_count():
    """Returns the total number of items currently in the Trash."""
    return {"total": get_trash_count()}


@api_router.post("/api/photos/delete", response_model=DeleteActionResponse, tags=["Trash"], summary="Delete Photos")
def api_delete_photos(req: DeletePhotosRequest):
    """Moves photos to Trash (soft delete) or deletes from disk if requested."""
    if req.delete_from_disk:
        return delete_photos_from_disk_and_db(req.photo_ids)
    count = delete_photos(req.photo_ids)
    return {"success": True, "deleted_count": count, "photo_ids": req.photo_ids, "delete_from_disk": False}


@api_router.post("/api/photos/restore", response_model=RestoreActionResponse, tags=["Trash"], summary="Restore Photos")
def api_restore_photos(req: RestorePhotosRequest):
    """Restores soft-deleted photos back to the active library."""
    count = restore_photos(req.photo_ids)
    return {"success": True, "restored_count": count, "photo_ids": req.photo_ids}


@api_router.post("/api/photos/delete-permanent", response_model=DeleteActionResponse, tags=["Trash"], summary="Permanently Purge Photos")
def api_permanent_delete_photos(req: DeletePhotosRequest):
    """Permanently deletes photos from disk (media file, companion JSON, thumbnail) and database."""
    return delete_photos_from_disk_and_db(req.photo_ids)


@api_router.post("/api/photos/trash/empty", response_model=DeleteActionResponse, tags=["Trash"], summary="Empty Entire Trash")
def api_empty_trash():
    """Permanently deletes all items currently in Trash from disk and database."""
    with get_db_connection() as conn:
        rows = conn.execute("SELECT id FROM photos WHERE deleted = 1").fetchall()
        photo_ids = [r["id"] for r in rows]

    if not photo_ids:
        return {"success": True, "deleted_count": 0, "message": "Trash is already empty"}

    return delete_photos_from_disk_and_db(photo_ids)


@api_router.get("/api/photos/{photo_id}", tags=["Photos"], summary="Get Photo Detail")
def get_photo_detail(photo_id: int):
    """Returns single photo with full metadata."""
    photo = get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return photo


# ==============================================================================
# Thumbnail & Media Streaming (with HTTP Range for smooth video seeking)
# ==============================================================================
_video_batch_running = False

@api_router.get("/api/thumbnails/{photo_id}", tags=["Media"], summary="Get WebP Thumbnail")
def get_thumbnail(photo_id: int, force: bool = Query(False)):
    """Serves high-performance cached WebP thumbnail."""
    photo = get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    thumb_path = photo.get("thumbnail_path")
    if not force and thumb_path and Path(thumb_path).is_file():
        return FileResponse(
            thumb_path,
            media_type="image/webp",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    # On-demand generation fallback
    file_path = photo["file_path"]
    media_type = photo.get("media_type", "image")
    thumb_rel, w, h = generate_thumbnail(photo_id, file_path, media_type, force=force)
    if thumb_rel and Path(thumb_rel).is_file():
        update_thumbnail_path(photo_id, thumb_rel, width=w, height=h)
        return FileResponse(
            thumb_rel,
            media_type="image/webp",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    # Fallback to serving original image directly if thumbnail generation failed
    if Path(file_path).is_file() and media_type == "image":
        mime = photo.get("mime_type") or "image/jpeg"
        return FileResponse(file_path, media_type=mime)

    raise HTTPException(status_code=404, detail="Thumbnail not available")


@api_router.post("/api/videos/generate-thumbnails", tags=["Media"], summary="Batch Video Thumbnails")
def api_generate_video_thumbnails():
    """Triggers background extraction of real video frame thumbnails for all videos."""
    global _video_batch_running
    if _video_batch_running:
        return {"status": "already_running", "message": "Video thumbnail extraction is already in progress"}

    def _worker():
        global _video_batch_running
        _video_batch_running = True
        try:
            from scripts.generate_video_thumbnails import run_batch
            run_batch(max_workers=4)
        finally:
            _video_batch_running = False

    import threading
    threading.Thread(target=_worker, daemon=True).start()
    return {"status": "started", "message": "Video thumbnail extraction started in background"}


@api_router.get("/api/videos/generate-thumbnails/status", tags=["Media"], summary="Video Batch Status")
def api_get_video_thumbnails_status():
    global _video_batch_running
    return {"running": _video_batch_running}


@api_router.get("/api/media/{photo_id}", tags=["Media"], summary="Stream Media File")
async def get_media(photo_id: int, request: Request):
    """
    Streams original image or video file.
    Supports HTTP Range requests (206 Partial Content) for fluid video playback.
    """
    photo = get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Media not found")

    file_path = Path(photo["file_path"])
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Original media file not found on disk")

    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        mime_type = "video/mp4" if photo.get("media_type") == "video" else "image/jpeg"

    # Handle HTTP Range requests for video seeking
    range_header = request.headers.get("Range")
    file_size = file_path.stat().st_size

    if range_header and photo.get("media_type") == "video":
        byte1, byte2 = 0, None
        match = range_header.replace("bytes=", "").split("-")
        if match[0]:
            byte1 = int(match[0])
        if len(match) > 1 and match[1]:
            byte2 = int(match[1])

        chunk_size = 1024 * 1024 * 2  # 2MB chunks
        length = file_size - byte1
        if byte2 is not None:
            length = byte2 - byte1 + 1
        elif length > chunk_size:
            length = chunk_size
        end = byte1 + length - 1

        def iterfile():
            with open(file_path, "rb") as f:
                f.seek(byte1)
                yield f.read(length)

        headers = {
            "Content-Range": f"bytes {byte1}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": mime_type,
        }
        return StreamingResponse(iterfile(), status_code=206, headers=headers)

    return FileResponse(
        file_path,
        media_type=mime_type,
        headers={"Accept-Ranges": "bytes"},
    )


# ==============================================================================
# AI Semantic Search & Categories
# ==============================================================================

@api_router.get("/api/search", response_model=SearchResponse, tags=["Search & AI"], summary="Semantic Search")
def search_photos(
    q: str = Query(..., min_length=1),
    limit: int = Query(80, ge=1, le=200),
):
    """
    Performs AI-powered semantic vector search using CLIP embeddings
    combined with database text and category matching.
    """
    query_text = q.strip()
    # 1. First attempt CLIP semantic vector search
    query_vec = ai_engine.encode_text_query(query_text)
    if query_vec is not None:
        photo_ids, matrix = get_all_embeddings()
        if len(photo_ids) > 0 and matrix.shape[0] > 0:
            # Cosine similarity (both vectors are L2-normalized)
            scores = np.dot(matrix, query_vec)
            ranked_indices = np.argsort(scores)[::-1]
            matched_ids = [
                photo_ids[i] for i in ranked_indices[:limit] if scores[i] > 0.18
            ]
            if matched_ids:
                results = get_photos(photo_ids=matched_ids, limit=limit)
                id_to_photo = {p["id"]: p for p in results}
                ordered_results = [id_to_photo[pid] for pid in matched_ids if pid in id_to_photo]
                return {
                    "mode": "semantic",
                    "query": query_text,
                    "count": len(ordered_results),
                    "photos": ordered_results,
                }

    # 2. Fallback to keyword search across tags, description, filename, category
    keyword_results = get_photos(search_text=query_text, limit=limit)
    return {
        "mode": "keyword",
        "query": query_text,
        "count": len(keyword_results),
        "photos": keyword_results,
    }


@api_router.get("/api/categories", response_model=CategoriesResponse, tags=["Search & AI"], summary="AI Categories")
def get_categories():
    """Returns detected AI categories and photo counts."""
    counts = get_category_counts()
    return {"categories": counts}


@api_router.get("/api/stats", response_model=StatsResponse, tags=["System"], summary="Library Stats")
def get_stats():
    """Returns general library statistics."""
    stats = get_library_stats()
    return {"stats": stats}


# ==============================================================================
# Scanner Control Endpoints
# ==============================================================================

@api_router.post("/api/scan/start", response_model=ScanControlResponse, tags=["Scanner"], summary="Start Scanner")
def start_scan():
    """Triggers background library scan."""
    started = scanner.start()
    return {"success": started, "status": scanner.get_status()}


@api_router.post("/api/scan/pause", response_model=ScanControlResponse, tags=["Scanner"], summary="Pause Scanner")
def pause_scan():
    """Pauses background scanner."""
    scanner.pause()
    return {"success": True, "status": scanner.get_status()}


@api_router.post("/api/scan/resume", response_model=ScanControlResponse, tags=["Scanner"], summary="Resume Scanner")
def resume_scan():
    """Resumes paused background scanner."""
    scanner.resume()
    return {"success": True, "status": scanner.get_status()}


@api_router.get("/api/scan/status", tags=["Scanner"], summary="Scan Status")
def scan_status() -> Dict[str, Any]:
    """Returns current scanner status."""
    return scanner.get_status()


# ==============================================================================
# Geolocation Points Route
# ==============================================================================

@api_router.get("/api/geo/points", response_model=GeoPointsResponse, tags=["Geolocation"], summary="Photo Map Points")
def api_get_geo_points():
    """Returns list of lightweight coordinates and metadata for all active geotagged photos."""
    points = get_geo_points()
    return {"count": len(points), "points": points}


# ==============================================================================
# Albums Routes
# ==============================================================================

@api_router.get("/api/albums", response_model=List[Dict[str, Any]], tags=["Albums"], summary="List Albums")
def api_get_albums():
    """Fetches all albums."""
    return get_albums()


@api_router.post("/api/albums", response_model=AlbumCreateResponse, tags=["Albums"], summary="Create Album")
def api_create_album(req: CreateAlbumRequest):
    """Creates a new album or returns existing album ID."""
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Album name required")
    album_id = create_album(req.name.strip())
    if not album_id:
        raise HTTPException(status_code=400, detail="Unable to create album")
    return {"success": True, "album_id": album_id}


@api_router.post("/api/albums/{album_id}/photos", response_model=AlbumMutationResponse, tags=["Albums"], summary="Add Photos to Album")
def api_add_photos_to_album(album_id: int, req: AddPhotosToAlbumRequest):
    """Adds selected photos to an album."""
    count = add_photos_to_album(album_id, req.photo_ids)
    return {"success": True, "added_count": count}


@api_router.get("/api/albums/{album_id}/photos", response_model=AlbumPhotosResponse, tags=["Albums"], summary="Get Album Photos")
def api_get_album_photos(
    album_id: int,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0)
):
    """Fetches paginated photos for a specific album."""
    photos = get_photos(album_id=album_id, limit=limit, offset=offset)
    return {"album_id": album_id, "photos": photos}


@api_router.delete("/api/albums/{album_id}/photos", response_model=AlbumMutationResponse, tags=["Albums"], summary="Remove Photos from Album")
def api_remove_photos_from_album(album_id: int, req: DeletePhotosRequest):
    """Removes selected photos from an album."""
    count = remove_photos_from_album(album_id, req.photo_ids)
    return {"success": True, "removed_count": count}


@api_router.delete("/api/albums/{album_id}", response_model=SimpleSuccessResponse, tags=["Albums"], summary="Delete Album")
def api_delete_album(album_id: int):
    """Deletes an entire album (does not delete the original photos)."""
    success = delete_album(album_id)
    if not success:
        raise HTTPException(status_code=404, detail="Album not found")
    return {"success": True}
