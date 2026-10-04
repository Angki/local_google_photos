# ==============================================================================
# File: backend/routes.py
# Description: FastAPI REST API routes and WebSocket handlers for timeline,
#              photo streaming, HTTP Range video playback, semantic search,
#              and background worker management with strict Pydantic models.
# ==============================================================================

import asyncio
import json
import logging
import mimetypes
import os
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field
from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse

logger = logging.getLogger("APIRoutes")

from backend.ai_engine import ai_engine
from backend.config import ALL_MEDIA_EXTENSIONS, PORT, SOURCE_DATA_DIR, THUMBNAILS_DIR, VIDEO_EXTENSIONS
from backend.database import (
    get_db_connection,
    get_all_embeddings,
    get_category_counts,
    get_library_stats,
    get_photo_by_id,
    get_photos,
    get_geo_points,
    get_timeline_hierarchy,
    get_memories_data,
    update_live_photo_status,
    update_photo_location,
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
    toggle_photo_favorite,
    set_photos_favorite,
    get_favorites_count,
    lock_photos,
    unlock_photos,
    get_locked_count,
    update_photo_ocr,
    update_photo_metadata,
    upsert_photo,
    has_pin_configured,
    set_pin,
    verify_pin,
)
from backend.deduplicator import compute_quick_file_hash, find_duplicates
from backend.geo_resolver import backfill_missing_locations, resolve_location
from backend.metadata_parser import parse_photo_metadata
from backend.motion_photo import detect_motion_photo
from backend.network_helper import get_network_info
from backend.ocr_engine import extract_ocr_text, is_ocr_available
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
    month_name: str
    count: int
    cover_id: Optional[int] = None
    name: Optional[str] = None


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


class FavoriteToggleResponse(BaseModel):
    success: bool
    photo_id: int
    is_favorite: bool


class BatchFavoriteRequest(BaseModel):
    photo_ids: List[int] = Field(..., description="List of photo IDs to update favorite status")
    is_favorite: bool = Field(True, description="True to mark favorite, False to unmark")


class BatchFavoriteResponse(BaseModel):
    success: bool
    updated_count: int
    is_favorite: bool


class FavoriteCountResponse(BaseModel):
    total: int


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


class DownloadZipRequest(BaseModel):
    photo_ids: List[int] = Field(..., min_length=1, description="List of photo IDs to pack into ZIP archive")
    archive_name: Optional[str] = Field("photos_export.zip", description="Filename for the downloaded ZIP")


class UpdateMetadataRequest(BaseModel):
    taken_at: Optional[str] = Field(None, description="ISO or standard timestamp (e.g. 2024-05-18 14:30:00)")
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Latitude between -90 and 90")
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Longitude between -180 and 180")
    location_label: Optional[str] = Field(None, description="Custom location text or place name")
    description: Optional[str] = Field(None, description="Caption or description of the photo")


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


@api_router.get("/api/memories", tags=["Memories"], summary="Memories On This Day")
def get_memories(
    month: Optional[int] = Query(None, ge=1, le=12),
    day: Optional[int] = Query(None, ge=1, le=31),
    year: Optional[int] = Query(None),
):
    """Returns grouped memories for 'On This Day' in past years."""
    return get_memories_data(month=month, day=day, current_year=year)


@api_router.get("/api/photos", response_model=PhotoListResponse, tags=["Photos"], summary="List Photos")
def list_photos(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    media_type: Optional[str] = Query(None),
    has_geo: Optional[bool] = Query(None),
    is_favorite: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(80, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Returns paginated photos with optional timeline, category, and favorite filters."""
    photos = get_photos(
        year=year,
        month=month,
        category=category,
        media_type=media_type,
        has_geo=has_geo,
        is_favorite=is_favorite,
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
# Favorite (Starred) Endpoints
# ==============================================================================

@api_router.post("/api/photos/{photo_id}/favorite", response_model=FavoriteToggleResponse, tags=["Favorites"], summary="Toggle Photo Favorite")
def api_toggle_favorite(photo_id: int):
    """Toggles the favorite (star) status of a single photo."""
    photo = get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    new_status = toggle_photo_favorite(photo_id)
    return {"success": True, "photo_id": photo_id, "is_favorite": new_status}


@api_router.post("/api/photos/favorite", response_model=BatchFavoriteResponse, tags=["Favorites"], summary="Batch Set Favorite")
def api_batch_favorite(req: BatchFavoriteRequest):
    """Sets favorite status for multiple photos."""
    count = set_photos_favorite(req.photo_ids, req.is_favorite)
    return {"success": True, "updated_count": count, "is_favorite": req.is_favorite}


@api_router.get("/api/photos/favorites/count", response_model=FavoriteCountResponse, tags=["Favorites"], summary="Get Favorites Count")
def api_get_favorites_count():
    """Returns total count of favorited photos."""
    return {"total": get_favorites_count()}


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
async def get_media(photo_id: int, request: Request, download: bool = False):
    """
    Streams original image or video file.
    Supports RFC-compliant HTTP Range requests (206 Partial Content) for fluid video seeking.
    """
    photo = get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Media not found")

    file_path = Path(photo["file_path"])
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Original media file not found on disk")

    # Normalize MIME types across platforms
    ext = file_path.suffix.lower()
    if ext in [".mp4", ".m4v"]:
        mime_type = "video/mp4"
    elif ext in [".mov", ".qt"]:
        mime_type = "video/quicktime"
    elif ext in [".webm"]:
        mime_type = "video/webm"
    elif ext in [".mkv"]:
        mime_type = "video/x-matroska"
    elif ext in [".avi"]:
        mime_type = "video/x-msvideo"
    elif ext in [".jpg", ".jpeg"]:
        mime_type = "image/jpeg"
    elif ext in [".png"]:
        mime_type = "image/png"
    elif ext in [".webp"]:
        mime_type = "image/webp"
    elif ext in [".gif"]:
        mime_type = "image/gif"
    else:
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "video/mp4" if photo.get("media_type") == "video" else "image/jpeg"

    file_size = file_path.stat().st_size
    range_header = request.headers.get("Range")

    # Handle HTTP Range requests for video seeking and streaming
    if range_header and photo.get("media_type") == "video":
        try:
            range_str = range_header.strip()
            if range_str.startswith("bytes="):
                range_str = range_str[6:]
            parts = range_str.split("-")
            if parts[0] and parts[1]:
                start = int(parts[0])
                end = int(parts[1])
            elif parts[0] and not parts[1]:
                start = int(parts[0])
                end = file_size - 1
            elif not parts[0] and parts[1]:
                suffix_len = int(parts[1])
                start = max(0, file_size - suffix_len)
                end = file_size - 1
            else:
                start = 0
                end = file_size - 1
        except Exception:
            start = 0
            end = file_size - 1

        if start >= file_size or end < start:
            return Response(
                status_code=416,
                headers={
                    "Content-Range": f"bytes */{file_size}",
                    "Accept-Ranges": "bytes",
                },
            )

        end = min(end, file_size - 1)
        content_length = end - start + 1

        def iterfile(offset: int, to_read: int):
            with open(file_path, "rb") as f:
                f.seek(offset)
                chunk_len = 256 * 1024  # 256KB buffer for smooth streaming
                bytes_remaining = to_read
                while bytes_remaining > 0:
                    read_len = min(bytes_remaining, chunk_len)
                    data = f.read(read_len)
                    if not data:
                        break
                    yield data
                    bytes_remaining -= len(data)

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": mime_type,
        }
        if download:
            filename_quoted = urllib.parse.quote(file_path.name)
            headers["Content-Disposition"] = f'attachment; filename="{file_path.name}"; filename*=UTF-8\'\'{filename_quoted}'

        return StreamingResponse(iterfile(start, content_length), status_code=206, headers=headers)

    headers = {"Accept-Ranges": "bytes"}
    if download:
        filename_quoted = urllib.parse.quote(file_path.name)
        headers["Content-Disposition"] = f'attachment; filename="{file_path.name}"; filename*=UTF-8\'\'{filename_quoted}'

    return FileResponse(
        file_path,
        media_type=mime_type,
        headers=headers,
    )


@api_router.post("/api/media/{photo_id}/open-local", tags=["Media"], summary="Open Media in Local App")
def open_media_in_local_app(photo_id: int):
    """
    Opens the media file in the operating system's default media player (e.g. VLC, Windows Media Player).
    """
    photo = get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Media not found")

    file_path = Path(photo["file_path"])
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Original media file not found on disk")

    try:
        import os
        os.startfile(str(file_path))
        return {"success": True, "message": f"Opened {file_path.name} in desktop player"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open in desktop player: {str(e)}")


@api_router.get("/api/media/{photo_id}/motion", tags=["Media"], summary="Stream Motion Photo Video Clip")
async def get_motion_video(photo_id: int, request: Request):
    """
    Streams the companion short video clip for iPhone Live Photos or Android Motion Photos.
    Supports HTTP Range requests (206 Partial Content).
    """
    photo = get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    file_path = Path(photo["file_path"])
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Original photo not found on disk")

    motion_path = photo.get("motion_video_path")
    is_live = bool(photo.get("is_live_photo"))

    # Auto-detect if not set yet
    if not motion_path:
        is_live, motion_path = detect_motion_photo(file_path)
        if is_live and motion_path:
            update_live_photo_status(photo_id, is_live, motion_path)

    if not is_live or not motion_path:
        raise HTTPException(status_code=404, detail="No motion photo video available for this media")

    # Case 1: Separate companion video file (iPhone Live Photo MOV/MP4)
    if not motion_path.startswith("embedded:"):
        vid_p = Path(motion_path)
        if not vid_p.is_file():
            raise HTTPException(status_code=404, detail="Companion live video file missing from disk")
        return FileResponse(vid_p, media_type="video/mp4", headers={"Accept-Ranges": "bytes"})

    # Case 2: Embedded MP4 micro-video inside JPEG/HEIC (Android Motion Photo)
    try:
        offset = int(motion_path.split(":", 1)[1])
        total_file_size = file_path.stat().st_size
        video_length = total_file_size - offset
        if video_length <= 0:
            raise HTTPException(status_code=404, detail="Invalid embedded video offset")

        # Stream embedded bytes
        def iter_embedded(seek_pos: int, bytes_to_read: int):
            with open(file_path, "rb") as f:
                f.seek(seek_pos)
                chunk_len = 256 * 1024
                remaining = bytes_to_read
                while remaining > 0:
                    read_len = min(remaining, chunk_len)
                    data = f.read(read_len)
                    if not data:
                        break
                    yield data
                    remaining -= len(data)

        range_header = request.headers.get("Range")
        if range_header:
            try:
                r_str = range_header.strip()
                if r_str.startswith("bytes="):
                    r_str = r_str[6:]
                parts = r_str.split("-")
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if parts[1] else video_length - 1
            except Exception:
                start = 0
                end = video_length - 1

            start = max(0, min(start, video_length - 1))
            end = max(start, min(end, video_length - 1))
            chunk_size = end - start + 1

            headers = {
                "Content-Range": f"bytes {start}-{end}/{video_length}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
                "Content-Type": "video/mp4",
            }
            return StreamingResponse(iter_embedded(offset + start, chunk_size), status_code=206, headers=headers)

        headers = {
            "Content-Length": str(video_length),
            "Content-Type": "video/mp4",
            "Accept-Ranges": "bytes",
        }
        return StreamingResponse(iter_embedded(offset, video_length), headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract motion video: {str(e)}")


class EditPhotoRequest(BaseModel):
    rotate: int = Field(0, description="Clockwise rotation degrees (90, 180, 270)")
    flip_h: bool = Field(False, description="Flip horizontally")
    crop: Optional[Dict[str, Any]] = Field(None, description="Crop rectangle: {x, y, w, h, normalized}")
    auto_enhance: bool = Field(False, description="Apply auto-contrast and color boost")
    brightness: float = Field(0.0, description="Brightness adjustment -100 to +100")
    contrast: float = Field(0.0, description="Contrast adjustment -100 to +100")
    saturation: float = Field(0.0, description="Saturation adjustment -100 to +100")
    warmth: float = Field(0.0, description="Warmth adjustment -100 to +100")
    save_as_copy: bool = Field(True, description="Save as new copy or overwrite original")


@api_router.post("/api/photos/{photo_id}/edit", tags=["Media"], summary="Apply Photo Edits")
def api_edit_photo(photo_id: int, req: EditPhotoRequest):
    """
    Applies image edits (crop, rotate, adjustments, auto-enhance) to a photo.
    Supports non-destructive 'save_as_copy' or atomic overwrite.
    """
    photo = get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    if photo.get("media_type") != "image":
        raise HTTPException(status_code=400, detail="Only image files can be edited")

    source_path = Path(photo["file_path"])
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail="Original photo file not found on disk")

    from backend.photo_editor import process_image_edits
    from backend.thumbnail_manager import generate_thumbnail
    from backend.database import update_thumbnail_path, upsert_photo

    edits_dict = req.model_dump()

    try:
        if req.save_as_copy:
            timestamp_suffix = int(time.time())
            new_filename = f"{source_path.stem}_edited_{timestamp_suffix}{source_path.suffix}"
            target_path = source_path.parent / new_filename

            new_w, new_h, new_size = process_image_edits(source_path, target_path, edits_dict)

            # Create copy record in DB
            new_record = dict(photo)
            new_record.pop("id", None)
            new_record["file_path"] = str(target_path.resolve())
            new_record["filename"] = new_filename
            new_record["file_size"] = new_size
            new_record["width"] = new_w
            new_record["height"] = new_h
            new_record["is_live_photo"] = 0
            new_record["motion_video_path"] = None

            new_id = upsert_photo(new_record)
            if new_id:
                thumb_res = generate_thumbnail(new_id, str(target_path), "image")
                if thumb_res:
                    t_path, tw, th = thumb_res
                    update_thumbnail_path(new_id, t_path, tw, th)
                edited_photo = get_photo_by_id(new_id)
                return {
                    "status": "success",
                    "success": True,
                    "action": "created_copy",
                    "is_copy": True,
                    "photo_id": new_id,
                    "filename": new_filename,
                    "photo": edited_photo,
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to save edited photo to database")
        else:
            # Overwrite original with safe atomic write
            temp_target = source_path.parent / f".tmp_{source_path.name}"
            new_w, new_h, new_size = process_image_edits(source_path, temp_target, edits_dict)
            temp_target.replace(source_path)

            with get_db_connection() as conn:
                conn.execute(
                    "UPDATE photos SET width = ?, height = ?, file_size = ? WHERE id = ?;",
                    (new_w, new_h, new_size, photo_id)
                )

            # Regenerate thumbnail
            thumb_res = generate_thumbnail(photo_id, str(source_path), "image")
            if thumb_res:
                t_path, tw, th = thumb_res
                update_thumbnail_path(photo_id, t_path, tw, th)

            edited_photo = get_photo_by_id(photo_id)
            return {
                "status": "success",
                "success": True,
                "action": "overwritten",
                "is_copy": False,
                "photo_id": photo_id,
                "filename": source_path.name,
                "photo": edited_photo,
            }

    except Exception as e:
        logger.exception(f"Failed to edit photo {photo_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Editing failed: {str(e)}")


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
# Geolocation Points & Backfill Route
# ==============================================================================

@api_router.get("/api/geo/points", response_model=GeoPointsResponse, tags=["Geolocation"], summary="Photo Map Points")
def api_get_geo_points():
    """Returns list of lightweight coordinates and metadata for all active geotagged photos."""
    points = get_geo_points()
    return {"count": len(points), "points": points}


@api_router.post("/api/geo/backfill", tags=["Geolocation"], summary="Backfill Location Names")
def api_backfill_geo(batch_size: int = Query(500, ge=1, le=2000)):
    """
    Triggers offline reverse geocoding to resolve city, state, and country for geotagged photos.
    """
    count = backfill_missing_locations(batch_size=batch_size)
    return {"success": True, "updated_count": count}


# ==============================================================================
# Deduplication & Cleaner Assistant Routes
# ==============================================================================

class DuplicateCleanupRequest(BaseModel):
    photo_ids: List[int] = Field(..., description="List of duplicate photo IDs to trash")
    hard_delete: bool = Field(False, description="If true, permanently delete files from disk")


@api_router.get("/api/duplicates", tags=["Deduplication"], summary="Get Duplicate Photo Groups")
def api_get_duplicates(limit_groups: int = Query(50, ge=1, le=200)):
    """
    Detects exact duplicates and burst near-duplicate photo groups for storage cleanup.
    """
    return find_duplicates(limit_groups=limit_groups)


@api_router.post("/api/duplicates/cleanup", tags=["Deduplication"], summary="Clean Up Duplicates")
def api_cleanup_duplicates(req: DuplicateCleanupRequest):
    """
    Trashes or permanently purges chosen duplicate photos.
    """
    if req.hard_delete:
        return delete_photos_from_disk_and_db(req.photo_ids)
    count = delete_photos(req.photo_ids)
    return {"success": True, "deleted_count": count, "photo_ids": req.photo_ids}


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


# ==============================================================================
# Optical Character Recognition (OCR / Live Text)
# ==============================================================================
@api_router.get("/api/photos/{photo_id}/ocr", tags=["OCR"], summary="Get Photo OCR Text")
def api_get_photo_ocr(photo_id: int):
    """Retrieves cached OCR text or extracts it on-the-fly using Tesseract."""
    photo = get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    cached_text = photo.get("ocr_text")
    if cached_text and cached_text.strip():
        return {
            "photo_id": photo_id,
            "text": cached_text,
            "ocr_text": cached_text,
            "has_text": True,
            "cached": True,
        }

    file_path = Path(photo["file_path"])
    text = extract_ocr_text(file_path)
    if text:
        update_photo_ocr(photo_id, text)

    return {
        "photo_id": photo_id,
        "text": text,
        "ocr_text": text,
        "has_text": bool(text.strip()),
        "cached": False,
    }


@api_router.post("/api/photos/{photo_id}/ocr", tags=["OCR"], summary="Extract Photo OCR Text")
def api_extract_photo_ocr(photo_id: int):
    """Force re-extracts OCR text from the photo and updates cache."""
    photo = get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    file_path = Path(photo["file_path"])
    text = extract_ocr_text(file_path)
    update_photo_ocr(photo_id, text)

    return {
        "photo_id": photo_id,
        "text": text,
        "ocr_text": text,
        "has_text": bool(text.strip()),
        "reindexed": True,
    }


# ==============================================================================
# Local Wi-Fi LAN Mode & QR Code Mobile Access
# ==============================================================================
@api_router.get("/api/system/network", tags=["System"], summary="Get LAN Network Info & QR Code")
def api_get_network_info():
    """Returns local LAN IP, network URL, and standalone SVG QR code."""
    return get_network_info(port=PORT)


# ==============================================================================
# Locked Folder (PIN-Protected Private Photos)
# ==============================================================================
_active_unlocked_tokens: Dict[str, float] = {}


def is_valid_unlocked_token(token: Optional[str]) -> bool:
    if not token or token not in _active_unlocked_tokens:
        return False
    if time.time() > _active_unlocked_tokens[token]:
        _active_unlocked_tokens.pop(token, None)
        return False
    return True


class PinSetupRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=4, pattern=r"^\d{4}$", description="4-digit numeric security PIN")


class PinVerifyRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=4, pattern=r"^\d{4}$", description="4-digit numeric security PIN")


class LockPhotosRequest(BaseModel):
    photo_ids: List[int] = Field(..., min_length=1)


class UnlockPhotosRequest(BaseModel):
    photo_ids: List[int] = Field(..., min_length=1)
    token: str = Field(...)


@api_router.get("/api/locked/status", tags=["Locked Folder"], summary="Get Locked Folder Status")
def api_get_locked_status():
    """Checks whether PIN is set and returns count of currently locked items."""
    return {
        "has_pin": has_pin_configured(),
        "locked_count": get_locked_count(),
    }


@api_router.post("/api/locked/setup-pin", tags=["Locked Folder"], summary="Setup Security PIN")
def api_setup_pin(req: PinSetupRequest):
    """Sets initial 4-digit PIN for the locked folder."""
    if has_pin_configured():
        raise HTTPException(status_code=400, detail="PIN sudah pernah dibuat.")
    set_pin(req.pin)
    return {"success": True, "message": "PIN keamanan berhasil dibuat."}


@api_router.post("/api/locked/verify-pin", tags=["Locked Folder"], summary="Verify PIN and Unlock")
def api_verify_pin(req: PinVerifyRequest):
    """Verifies security PIN and returns a temporary 15-minute access token."""
    if not verify_pin(req.pin):
        raise HTTPException(status_code=401, detail="PIN yang Anda masukkan salah.")

    import hashlib
    token = hashlib.sha256(f"{req.pin}:{time.time()}:{os.urandom(16)}".encode("utf-8")).hexdigest()[:32]
    _active_unlocked_tokens[token] = time.time() + (15 * 60)
    return {"success": True, "token": token, "expires_in": 900}


@api_router.post("/api/photos/lock", tags=["Locked Folder"], summary="Lock Photos")
def api_lock_photos(req: LockPhotosRequest):
    """Moves photos to the Locked Folder (hidden from main timeline, map, and memories)."""
    count = lock_photos(req.photo_ids)
    return {"success": True, "locked_count": count}


@api_router.post("/api/photos/unlock", tags=["Locked Folder"], summary="Unlock Photos")
def api_unlock_photos(req: UnlockPhotosRequest):
    """Restores locked photos back to the public timeline."""
    if not is_valid_unlocked_token(req.token):
        raise HTTPException(status_code=401, detail="Sesi akses terkunci kedaluwarsa. Silakan masukkan PIN ulang.")
    count = unlock_photos(req.photo_ids)
    return {"success": True, "unlocked_count": count}


@api_router.get("/api/locked/photos", tags=["Locked Folder"], summary="Get Locked Photos")
def api_get_locked_photos(
    token: Optional[str] = Query(None, description="Active unlocked session token"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Fetches photos in the Locked Folder (requires active unlocked session token)."""
    if not is_valid_unlocked_token(token):
        raise HTTPException(status_code=401, detail="Sesi akses terkunci kedaluwarsa. Silakan masukkan PIN ulang.")
    photos = get_photos(is_locked=True, limit=limit, offset=offset)
    return {"photos": photos, "count": len(photos)}


# ==============================================================================
# Direct Mobile / Web Wi-Fi Uploader
# ==============================================================================
@api_router.post("/api/upload", tags=["Media"], summary="Direct Upload Media Files")
async def api_upload_media(
    files: List[UploadFile] = File(...),
):
    """
    Directly upload photos or videos from mobile (via Wi-Fi LAN) or desktop.
    Files are saved into SOURCE_DATA_DIR / 'Photos from {year}', indexed into DB,
    thumbnails generated, and broadcasted to active WebSocket clients.
    """
    import datetime
    current_year = datetime.datetime.now().year
    uploaded = []
    errors = []

    for file in files:
        if not file.filename:
            continue
        safe_filename = Path(file.filename).name
        ext = Path(safe_filename).suffix.lower()
        if ext not in ALL_MEDIA_EXTENSIONS:
            errors.append({"filename": safe_filename, "error": f"Ekstensi {ext} tidak didukung."})
            continue

        try:
            target_dir = Path(SOURCE_DATA_DIR) / f"Photos from {current_year}"
            target_dir.mkdir(parents=True, exist_ok=True)

            # Avoid overwrite collision
            stem = Path(safe_filename).stem
            cand_path = target_dir / safe_filename
            counter = 1
            while cand_path.exists():
                cand_path = target_dir / f"{stem}_{counter}{ext}"
                counter += 1

            # Write file in chunks to disk
            with open(cand_path, "wb") as f_out:
                while chunk := await file.read(1024 * 1024):
                    f_out.write(chunk)

            file_size = cand_path.stat().st_size
            media_type = "video" if ext in VIDEO_EXTENSIONS else "image"
            mime_type, _ = mimetypes.guess_type(str(cand_path))
            if not mime_type:
                mime_type = "video/mp4" if media_type == "video" else "image/jpeg"

            # Parse metadata
            meta = parse_photo_metadata(cand_path, fallback_year=current_year)
            meta_year = meta.get("taken_year")
            if meta_year and meta_year != current_year and 2000 <= meta_year <= 2030:
                proper_dir = Path(SOURCE_DATA_DIR) / f"Photos from {meta_year}"
                proper_dir.mkdir(parents=True, exist_ok=True)
                new_stem = cand_path.stem
                new_path = proper_dir / f"{new_stem}{ext}"
                cnt = 1
                while new_path.exists():
                    new_path = proper_dir / f"{new_stem}_{cnt}{ext}"
                    cnt += 1
                cand_path.rename(new_path)
                cand_path = new_path

            # Reverse geocode if coordinates present
            geo_info = {}
            if meta.get("has_geo") and meta.get("latitude") and meta.get("longitude"):
                geo_info = resolve_location(meta["latitude"], meta["longitude"])

            # Motion photo detection
            is_live, motion_src = False, None
            if media_type == "image":
                is_live, motion_src = detect_motion_photo(cand_path)

            quick_hash = compute_quick_file_hash(str(cand_path.resolve()))

            record = {
                "file_path": str(cand_path.resolve()),
                "filename": cand_path.name,
                "folder_year": cand_path.parent.name,
                "file_size": file_size,
                "media_type": media_type,
                "mime_type": mime_type,
                "width": 0,
                "height": 0,
                "taken_at": meta["taken_at"],
                "taken_year": meta["taken_year"],
                "taken_month": meta["taken_month"],
                "taken_day": meta["taken_day"],
                "taken_formatted": meta["taken_formatted"],
                "latitude": meta["latitude"],
                "longitude": meta["longitude"],
                "altitude": meta["altitude"],
                "has_geo": meta["has_geo"],
                "description": meta["description"],
                "people": str(meta["people"]),
                "device_folder": meta["device_folder"],
                "app_source": meta["app_source"],
                "google_url": meta["google_url"],
                "city": geo_info.get("city", ""),
                "state": geo_info.get("state", ""),
                "country": geo_info.get("country", ""),
                "country_code": geo_info.get("country_code", ""),
                "location_label": geo_info.get("location_label", ""),
                "is_live_photo": 1 if is_live else 0,
                "motion_video_path": motion_src,
                "file_hash": quick_hash,
            }
            photo_id = upsert_photo(record)

            # Generate thumbnail
            thumb_rel, w, h = generate_thumbnail(photo_id, str(cand_path.resolve()), media_type=media_type)
            if thumb_rel:
                update_thumbnail_path(photo_id, thumb_rel, width=w, height=h)

            uploaded_item = {
                "id": photo_id,
                "filename": cand_path.name,
                "taken_year": meta["taken_year"],
                "media_type": media_type,
            }
            uploaded.append(uploaded_item)

            # Broadcast event to active WebSockets
            try:
                await ws_manager.broadcast({
                    "type": "photo_added",
                    "photo": uploaded_item,
                })
            except Exception as e:
                logger.debug(f"Broadcast photo_added failed: {e}")

        except Exception as e:
            logger.error(f"Error processing upload for {safe_filename}: {e}", exc_info=True)
            errors.append({"filename": safe_filename, "error": str(e)})

    return {
        "success": True,
        "count": len(uploaded),
        "uploaded": uploaded,
        "errors": errors,
    }


# ==============================================================================
# Batch ZIP Archive Downloader
# ==============================================================================
@api_router.post("/api/photos/download-zip", tags=["Media"], summary="Download Photos as ZIP Archive")
def api_download_photos_zip(req: DownloadZipRequest):
    """
    Packs selected original photos/videos into a downloadable ZIP archive on the fly.
    """
    if not req.photo_ids:
        raise HTTPException(status_code=400, detail="Tidak ada foto yang dipilih untuk diunduh.")

    photos = []
    for pid in req.photo_ids:
        p = get_photo_by_id(pid)
        if p and Path(p["file_path"]).is_file():
            photos.append(p)

    if not photos:
        raise HTTPException(status_code=404, detail="File media yang dipilih tidak ditemukan di penyimpanan.")

    import io
    import zipfile

    def zip_stream():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            added_names = set()
            for p in photos:
                fp = Path(p["file_path"])
                base_name = p.get("filename") or fp.name
                arcname = base_name
                cnt = 1
                while arcname in added_names:
                    p_stem = Path(base_name).stem
                    p_ext = Path(base_name).suffix
                    arcname = f"{p_stem}_{cnt}{p_ext}"
                    cnt += 1
                added_names.add(arcname)
                zf.write(fp, arcname=arcname)
        buf.seek(0)
        while chunk := buf.read(64 * 1024):
            yield chunk

    filename = req.archive_name if req.archive_name.endswith(".zip") else f"{req.archive_name}.zip"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return StreamingResponse(zip_stream(), media_type="application/zip", headers=headers)


@api_router.get("/api/albums/{album_id}/download-zip", tags=["Albums"], summary="Download Album as ZIP Archive")
def api_download_album_zip(album_id: int):
    """Downloads all photos in the specified album as a single ZIP archive."""
    album_photos = get_photos(album_id=album_id, limit=5000)
    if not album_photos:
        raise HTTPException(status_code=404, detail="Album kosong atau tidak ditemukan.")

    pids = [p["id"] for p in album_photos]
    albums = get_albums()
    album_title = "album"
    for alb in albums:
        if alb.get("id") == album_id:
            album_title = alb.get("name", "album")
            break
    safe_name = "".join(c for c in album_title if c.isalnum() or c in (" ", "-", "_")).strip() or "album"
    return api_download_photos_zip(DownloadZipRequest(photo_ids=pids, archive_name=f"{safe_name}.zip"))


# ==============================================================================
# Manual Metadata & Location Editor
# ==============================================================================
@api_router.post("/api/photos/{photo_id}/metadata", tags=["Media"], summary="Update Photo Metadata & Location")
def api_update_photo_metadata(photo_id: int, req: UpdateMetadataRequest):
    """
    Manually edits incorrect capture date/time, GPS coordinates, location label, or caption.
    Automatically resolves offline reverse geocoding if coordinates are provided without label.
    """
    photo = get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan.")

    location_label = req.location_label
    if (req.latitude is not None and req.longitude is not None) and not location_label:
        geo = resolve_location(req.latitude, req.longitude)
        if geo and geo.get("location_label"):
            location_label = geo["location_label"]

    success = update_photo_metadata(
        photo_id=photo_id,
        taken_at=req.taken_at,
        latitude=req.latitude,
        longitude=req.longitude,
        location_label=location_label,
        description=req.description,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Tidak ada pembaruan metadata yang valid.")

    updated_photo = get_photo_by_id(photo_id)
    return {"success": True, "photo": updated_photo}

