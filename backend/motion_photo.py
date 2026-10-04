# ==============================================================================
# File: backend/motion_photo.py
# Description: Detects and streams iPhone Live Photos (companion MOV/MP4)
#              and Android Motion Photos (embedded MP4 micro-video in JPEG/HEIC).
# ==============================================================================

import io
import logging
import os
import re
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("MotionPhoto")

# Common companion video extensions for iPhone Live Photos
LIVE_VIDEO_EXTS = [".mov", ".MOV", ".mp4", ".MP4"]


def find_companion_live_video(image_path: Path) -> Optional[Path]:
    """
    Checks if an image (e.g. IMG_1234.HEIC or IMG_1234.JPG) has a companion
    Live Photo video file (IMG_1234.MOV) in the same folder.
    """
    folder = image_path.parent
    stem = image_path.stem

    # 1. Exact stem match: IMG_1234.HEIC -> IMG_1234.MOV
    for ext in LIVE_VIDEO_EXTS:
        candidate = folder / f"{stem}{ext}"
        if candidate.is_file():
            return candidate

    # 2. Numbered companion: IMG_1234(1).MOV or IMG_1234_HEVC.MOV
    for ext in LIVE_VIDEO_EXTS:
        candidate_num = folder / f"{stem}(1){ext}"
        if candidate_num.is_file():
            return candidate_num
        candidate_hevc = folder / f"{stem}_HEVC{ext}"
        if candidate_hevc.is_file():
            return candidate_hevc

    return None


def find_embedded_motion_offset(image_path: Path) -> Optional[int]:
    """
    Detects embedded micro-video offset in Android Motion Photos (Pixel / Samsung).
    Returns the byte offset where the embedded MP4 begins, or None.
    """
    p = Path(image_path)
    if not p.is_file() or p.suffix.lower() not in [".jpg", ".jpeg"]:
        return None

    try:
        file_size = p.stat().st_size
        if file_size < 1024 * 50:  # Need at least 50KB
            return None

        # Read the file to locate the embedded MP4 signature
        # 1. Check for XMP MicroVideoOffset in the first 64KB
        with open(p, "rb") as f:
            header = f.read(65536)
            m = re.search(rb'MicroVideoOffset="(\d+)"', header)
            if not m:
                m = re.search(rb'MicroVideoOffset>(\d+)<', header)
            if m:
                offset_from_end = int(m.group(1).decode("ascii"))
                if 0 < offset_from_end < file_size:
                    return file_size - offset_from_end

            # 2. Fallback: Search backwards in chunks for 'ftyp' MP4 box header
            # Scan last 20MB of file (most motion videos are 1-15MB)
            scan_size = min(file_size, 20 * 1024 * 1024)
            f.seek(file_size - scan_size)
            chunk = f.read(scan_size)

            # Search for 'ftypmp42' or 'ftypisom' or 'ftypqt  '
            ftyp_pos = chunk.find(b"ftyp")
            if ftyp_pos >= 4:
                # The 4 bytes before 'ftyp' are the box size
                mp4_start = (file_size - scan_size) + (ftyp_pos - 4)
                return mp4_start
    except Exception as e:
        logger.debug(f"Error checking embedded motion video for {image_path}: {e}")

    return None


def detect_motion_photo(image_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Detects if an image is an iPhone Live Photo or Android Motion Photo.
    Returns: (is_live_photo: bool, motion_video_source: Optional[str])
    If companion file: returns absolute path to .MOV
    If embedded: returns "embedded:<offset>"
    """
    companion = find_companion_live_video(image_path)
    if companion:
        return True, str(companion)

    offset = find_embedded_motion_offset(image_path)
    if offset:
        return True, f"embedded:{offset}"

    return False, None
