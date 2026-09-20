# ==============================================================================
# File: backend/scanner.py
# Description: Two-stage background worker for Google Takeout archive indexing,
#              fast JSON metadata ingestion, asynchronous thumbnail generation,
#              and CLIP AI tagging with real-time WebSocket progress broadcasts.
#
# CHANGELOG:
# 2026-09-05 - Initial creation: Added two-stage non-blocking architecture,
#              strict folder filter (2013-2026), live WebSocket progress emitter,
#              and pause/resume controls to keep the UI silky smooth.
# ==============================================================================

import asyncio
import logging
import mimetypes
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.ai_engine import ai_engine
from backend.config import (
    ALL_MEDIA_EXTENSIONS,
    IMAGE_EXTENSIONS,
    SOURCE_DATA_DIR,
    VIDEO_EXTENSIONS,
    YEAR_FOLDER_PATTERN,
    is_target_folder,
)
from backend.database import (
    add_photos_to_album,
    deduplicate_library,
    find_canonical_photo,
    get_db_connection,
    get_library_stats,
    get_or_create_album,
    get_unprocessed_photos_for_ai,
    get_unprocessed_photos_for_thumbnails,
    save_ai_results,
    update_thumbnail_path,
    upsert_photo,
)
from backend.metadata_parser import parse_photo_metadata
from backend.thumbnail_manager import generate_thumbnail

logger = logging.getLogger("LibraryScanner")


class ScannerState:
    IDLE = "idle"
    SCANNING_METADATA = "scanning_metadata"
    PROCESSING_MEDIA = "processing_media"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class LibraryScanner:
    def __init__(self, broadcast_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.broadcast_callback = broadcast_callback
        self.state = ScannerState.IDLE
        self._thread: Optional[threading.Thread] = None
        self._pause_event = threading.Event()
        self._stop_event = threading.Event()
        self._pause_event.set()  # Not paused initially

        # Progress metrics
        self.current_folder: str = ""
        self.current_file: str = ""
        self.total_discovered: int = 0
        self.metadata_indexed: int = 0
        self.thumbnails_done: int = 0
        self.ai_processed: int = 0
        self.start_time: float = 0.0
        self.last_broadcast_time: float = 0.0
        self.error_message: Optional[str] = None

    def get_status(self) -> Dict[str, Any]:
        """Returns the current state and progress metrics."""
        elapsed = time.time() - self.start_time if self.start_time > 0 else 0.0
        total_target = max(self.total_discovered, 1)

        # Overall progress weight: 20% metadata scan, 40% thumbnails, 40% AI
        meta_ratio = min(self.metadata_indexed / total_target, 1.0)
        thumb_ratio = min(self.thumbnails_done / total_target, 1.0)
        ai_ratio = min(self.ai_processed / total_target, 1.0)
        overall_pct = round((meta_ratio * 20.0) + (thumb_ratio * 40.0) + (ai_ratio * 40.0), 1)

        speed_fps = round(self.metadata_indexed / elapsed, 1) if elapsed > 1.0 else 0.0

        return {
            "status": self.state,
            "current_folder": self.current_folder,
            "current_file": self.current_file,
            "total_discovered": self.total_discovered,
            "metadata_indexed": self.metadata_indexed,
            "thumbnails_done": self.thumbnails_done,
            "ai_processed": self.ai_processed,
            "percent": overall_pct,
            "speed_fps": speed_fps,
            "elapsed_seconds": int(elapsed),
            "error_message": self.error_message,
        }

    def notify_progress(self, force: bool = False) -> None:
        """Sends live status update to WebSocket clients."""
        now = time.time()
        if force or (now - self.last_broadcast_time > 0.4):
            self.last_broadcast_time = now
            status_data = self.get_status()
            if self.broadcast_callback:
                self.broadcast_callback(status_data)

    def start(self) -> bool:
        """Starts scanning in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.info("Scanner thread is already active.")
            return False

        self._stop_event.clear()
        self._pause_event.set()
        self.state = ScannerState.SCANNING_METADATA
        self.start_time = time.time()
        self.error_message = None

        self._thread = threading.Thread(target=self._run_pipeline, daemon=True, name="ScannerThread")
        self._thread.start()
        logger.info("Background scanner thread launched.")
        return True

    def pause(self) -> None:
        """Pauses the scanner."""
        if self.state in (ScannerState.SCANNING_METADATA, ScannerState.PROCESSING_MEDIA):
            self.state = ScannerState.PAUSED
            self._pause_event.clear()
            self.notify_progress(force=True)

    def resume(self) -> None:
        """Resumes the scanner."""
        if self.state == ScannerState.PAUSED:
            self.state = ScannerState.PROCESSING_MEDIA
            self._pause_event.set()
            self.notify_progress(force=True)

    def stop(self) -> None:
        """Stops the scanner cleanly."""
        self._stop_event.set()
        self._pause_event.set()  # Unblock if paused
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self.state = ScannerState.IDLE
        self.notify_progress(force=True)

    def _run_pipeline(self) -> None:
        """Orchestrates Stage 1 (Fast Metadata Scan) and Stage 2 (Thumbnails & AI)."""
        try:
            # -------------------------------------------------------------
            # Stage 1: Discover Folders & Fast Parse Companion JSON Metadata
            # -------------------------------------------------------------
            self.state = ScannerState.SCANNING_METADATA
            self.notify_progress(force=True)

            if not SOURCE_DATA_DIR.is_dir():
                raise FileNotFoundError(f"Source directory not found: {SOURCE_DATA_DIR}")

            target_dirs = [
                d for d in SOURCE_DATA_DIR.iterdir()
                if d.is_dir() and is_target_folder(d.name)
            ]
            # Prioritize 'Photos from <Year>' folders first so canonical photos are indexed first
            target_dirs.sort(
                key=lambda d: (0 if YEAR_FOLDER_PATTERN.match(d.name) else 1, d.name),
                reverse=False
            )

            # Discover media files
            all_media_files: List[Path] = []
            for folder in target_dirs:
                if self._stop_event.is_set():
                    break
                self.current_folder = folder.name
                try:
                    for entry in folder.iterdir():
                        if entry.is_file() and entry.suffix.lower() in ALL_MEDIA_EXTENSIONS:
                            all_media_files.append(entry)
                except Exception as e:
                    logger.error(f"Error scanning folder {folder.name}: {e}")

            self.total_discovered = len(all_media_files)
            logger.info(f"Discovered {self.total_discovered} media items across {len(target_dirs)} target folders.")
            self.notify_progress(force=True)

            # Ingest metadata into SQLite in fast batches
            for idx, media_path in enumerate(all_media_files):
                if self._stop_event.is_set():
                    return
                self._pause_event.wait()

                self.current_file = media_path.name
                self.current_folder = media_path.parent.name
                ext = media_path.suffix.lower()
                media_type = "video" if ext in VIDEO_EXTENSIONS else "image"
                mime_type = mimetypes.guess_type(str(media_path))[0]

                folder_name = media_path.parent.name
                folder_year_match = YEAR_FOLDER_PATTERN.match(folder_name)
                folder_year_val = int(folder_year_match.group(1)) if folder_year_match else None

                try:
                    meta = parse_photo_metadata(media_path, fallback_year=folder_year_val)
                    stat = media_path.stat()
                    file_size = stat.st_size
                except Exception:
                    file_size = 0
                    meta = {
                        "taken_at": int(time.time()),
                        "taken_year": folder_year_val or 2026,
                        "taken_month": 1,
                        "taken_day": 1,
                        "taken_formatted": "",
                        "latitude": None,
                        "longitude": None,
                        "altitude": None,
                        "has_geo": False,
                        "description": "",
                        "people": [],
                        "device_folder": "",
                        "app_source": "",
                        "google_url": "",
                    }

                is_album = not folder_year_match

                # If this photo is in an album folder and already exists in the library, link to album without duplicating
                if is_album and file_size > 0:
                    canonical_id = find_canonical_photo(media_path.name, file_size)
                    if canonical_id:
                        try:
                            album_id = get_or_create_album(folder_name)
                            if album_id:
                                add_photos_to_album(album_id, [canonical_id])
                        except Exception as e:
                            logger.debug(f"Album auto-mapping failed for {folder_name}: {e}")
                        self.metadata_indexed = idx + 1
                        self.notify_progress()
                        continue

                record = {
                    "file_path": str(media_path.resolve()),
                    "filename": media_path.name,
                    "folder_year": media_path.parent.name,
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
                }

                p_id = upsert_photo(record)

                # If this photo belongs to a custom Takeout album folder, automatically associate it with that album
                if is_album:
                    try:
                        album_id = get_or_create_album(folder_name)
                        if album_id and p_id:
                            add_photos_to_album(album_id, [p_id])
                    except Exception as e:
                        logger.debug(f"Album auto-mapping failed for {folder_name}: {e}")

                self.metadata_indexed = idx + 1
                self.notify_progress()

            logger.info(f"Stage 1 completed: {self.metadata_indexed} photos indexed in database.")
            self.notify_progress(force=True)

            # -------------------------------------------------------------
            # Stage 2: Background Thumbnail Generation & AI Vision Analysis
            # -------------------------------------------------------------
            self.state = ScannerState.PROCESSING_MEDIA
            self.notify_progress(force=True)

            # Update initial counts from DB
            stats = get_library_stats()
            self.thumbnails_done = stats.get("total_thumbnails", 0) or 0
            self.ai_processed = stats.get("total_ai_processed", 0) or 0

            # Batch process loop
            batch_size = 50
            while not self._stop_event.is_set():
                self._pause_event.wait()

                # 1. Fetch chunk needing thumbnails
                unprocessed_thumbs = get_unprocessed_photos_for_thumbnails(limit=batch_size)
                # 2. Fetch chunk needing AI tagging
                unprocessed_ai = get_unprocessed_photos_for_ai(limit=batch_size)

                if not unprocessed_thumbs and not unprocessed_ai:
                    logger.info("All media processed! Scan pipeline complete.")
                    break

                # Process thumbnails
                for item in unprocessed_thumbs:
                    if self._stop_event.is_set():
                        return
                    self._pause_event.wait()

                    p_id = item["id"]
                    f_path = item["file_path"]
                    m_type = item["media_type"]
                    self.current_file = Path(f_path).name

                    thumb_rel, w, h = generate_thumbnail(p_id, f_path, m_type)
                    if thumb_rel:
                        update_thumbnail_path(p_id, thumb_rel, width=w, height=h)
                    else:
                        # Mark as failed so we don't retry infinitely
                        update_thumbnail_path(p_id, "FAILED", width=0, height=0)
                    self.thumbnails_done += 1
                    self.notify_progress()

                # Process AI tags
                for item in unprocessed_ai:
                    if self._stop_event.is_set():
                        return
                    self._pause_event.wait()

                    p_id = item["id"]
                    f_path = Path(item["file_path"])
                    self.current_file = f_path.name

                    cat, conf, tags, emb_bytes = ai_engine.analyze_image(f_path)
                    save_ai_results(p_id, cat, conf, tags, emb_bytes)
                    self.ai_processed += 1
                    self.notify_progress()

            self.state = ScannerState.COMPLETED
            self.notify_progress(force=True)
            logger.info("LibraryScanner finished successfully.")

        except Exception as e:
            logger.exception(f"Error in scanner pipeline: {e}")
            self.state = ScannerState.ERROR
            self.error_message = str(e)
            self.notify_progress(force=True)
