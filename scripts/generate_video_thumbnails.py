# ==============================================================================
# File: scripts/generate_video_thumbnails.py
# Description: Multi-threaded batch processor that extracts real video frame
#              thumbnails using FFmpeg with GPU DXVA2 hardware acceleration.
# ==============================================================================

from __future__ import annotations
import concurrent.futures
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import get_db_connection, update_thumbnail_path
from backend.thumbnail_manager import generate_thumbnail

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("VideoThumbnailBatch")


def process_single_video(video_record: dict) -> tuple[int, bool, str]:
    """Processes a single video record, extracting a frame thumbnail."""
    photo_id = video_record["id"]
    file_path = video_record["file_path"]
    filename = video_record["filename"]

    try:
        rel_path, w, h = generate_thumbnail(photo_id, file_path, media_type="video", force=True)
        if rel_path:
            update_thumbnail_path(photo_id, rel_path, width=w, height=h)
            return photo_id, True, filename
        return photo_id, False, f"{filename} (No thumbnail path returned)"
    except Exception as e:
        return photo_id, False, f"{filename} ({e})"


def run_batch(max_workers: int = 4):
    """Fetches all videos and processes them concurrently."""
    logger.info("=" * 65)
    logger.info("  STARTING VIDEO THUMBNAIL EXTRACTION BATCH")
    logger.info("=" * 65)

    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT id, file_path, filename
            FROM photos
            WHERE media_type = 'video' AND deleted = 0
            ORDER BY taken_at DESC;
        """).fetchall()
        videos = [dict(r) for r in rows]

    total = len(videos)
    logger.info(f"Found {total} videos to process with {max_workers} worker threads.")

    if total == 0:
        logger.info("No videos found in library.")
        return

    start_time = time.time()
    completed = 0
    successes = 0
    failures = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_video = {
            executor.submit(process_single_video, vid): vid
            for vid in videos
        }

        for future in concurrent.futures.as_completed(future_to_video):
            photo_id, ok, info = future.result()
            completed += 1
            if ok:
                successes += 1
            else:
                failures += 1

            if completed % 25 == 0 or completed == total:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                remaining = (total - completed) / rate if rate > 0 else 0
                pct = (completed / total) * 100
                logger.info(
                    f"[{completed}/{total}] ({pct:.1f}%) | "
                    f"Success: {successes} | Fail: {failures} | "
                    f"Speed: {rate:.1f} vid/s | ETA: {int(remaining)}s"
                )

    total_time = time.time() - start_time
    logger.info("=" * 65)
    logger.info(f"COMPLETED in {total_time:.1f}s ({total_time/60:.1f} min)")
    logger.info(f"Total: {total} | Success: {successes} | Failures: {failures}")
    logger.info("=" * 65)


if __name__ == "__main__":
    workers = 4
    if len(sys.argv) > 1:
        try:
            workers = int(sys.argv[1])
        except ValueError:
            pass
    run_batch(max_workers=workers)
