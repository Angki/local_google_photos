# ==============================================================================
# File: backend/watcher.py
# Description: Real-time Hot Folder Watcher using watchdog.
#              Automatically monitors the Google Photos library directory for
#              newly transferred or dropped photos/videos, ingests them into the
#              database, creates WebP thumbnails, and broadcasts live updates.
# ==============================================================================

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Set
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
from watchdog.observers import Observer

from backend.config import ALL_MEDIA_EXTENSIONS, SOURCE_DATA_DIR
from backend.database import get_db_connection
from backend.scanner import index_single_media_file

logger = logging.getLogger("FolderWatcher")


class MediaWatcherHandler(FileSystemEventHandler):
    def __init__(self, on_new_media_callback: Optional[Callable[[int, Path], None]] = None):
        super().__init__()
        self.on_new_media_callback = on_new_media_callback
        self._recently_processed: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _should_process(self, path_str: str) -> bool:
        path = Path(path_str)
        if path.name.startswith(".") or path.suffix.lower() not in ALL_MEDIA_EXTENSIONS:
            return False

        now = time.time()
        with self._lock:
            # Clean up old entries older than 30s
            self._recently_processed = {
                k: v for k, v in self._recently_processed.items() if now - v < 30.0
            }
            last_time = self._recently_processed.get(path_str, 0.0)
            if now - last_time < 3.0:
                return False  # Debounce events within 3s
            self._recently_processed[path_str] = now
            return True

    def on_created(self, event):
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            self._handle_media_change(Path(event.src_path))

    def on_modified(self, event):
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            self._handle_media_change(Path(event.src_path))

    def _handle_media_change(self, file_path: Path):
        # Allow brief time for file copy to finish writing
        time.sleep(0.5)
        try:
            if not file_path.is_file() or file_path.stat().st_size == 0:
                return

            resolved_path_str = str(file_path.resolve())
            with get_db_connection() as conn:
                existing = conn.execute(
                    "SELECT id FROM photos WHERE file_path = ?", (resolved_path_str,)
                ).fetchone()

            is_truly_new = existing is None
            photo_id = index_single_media_file(file_path)
            if photo_id and is_truly_new:
                logger.info(f"Auto-indexed new photo (ID: {photo_id}): {file_path.name}")
                if self.on_new_media_callback:
                    self.on_new_media_callback(photo_id, file_path)
        except Exception as e:
            logger.warning(f"Error handling watched file {file_path}: {e}")


class HotFolderWatcher:
    def __init__(self, watch_dir: Path = SOURCE_DATA_DIR, on_new_media: Optional[Callable[[int, Path], None]] = None):
        self.watch_dir = watch_dir
        self.on_new_media = on_new_media
        self.observer: Optional[Observer] = None
        self._is_running = False

    def start(self):
        if self._is_running:
            return

        if not self.watch_dir.is_dir():
            logger.warning(f"HotFolderWatcher: directory does not exist: {self.watch_dir}")
            return

        try:
            handler = MediaWatcherHandler(on_new_media_callback=self.on_new_media)
            self.observer = Observer()
            self.observer.schedule(handler, str(self.watch_dir), recursive=True)
            self.observer.daemon = True
            self.observer.start()
            self._is_running = True
            logger.info(f"HotFolderWatcher successfully started on '{self.watch_dir}'")
        except Exception as e:
            logger.error(f"Failed to start HotFolderWatcher: {e}")

    def stop(self):
        if not self._is_running or not self.observer:
            return

        try:
            self.observer.stop()
            self.observer.join(timeout=2.0)
            self._is_running = False
            logger.info("HotFolderWatcher stopped.")
        except Exception as e:
            logger.debug(f"Error stopping HotFolderWatcher: {e}")


# Singleton instance
folder_watcher = HotFolderWatcher()
