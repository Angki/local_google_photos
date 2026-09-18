# ==============================================================================
# File: backend/thumbnail_manager.py
# Description: Generates, caches, and serves high-performance WebP thumbnails
#              for rapid gallery scrolling and minimal memory footprint.
#
# CHANGELOG:
# 2026-09-05 - Initial creation: Added EXIF auto-rotation, WebP compression,
#              hash-based thumbnail caching, and video thumbnail handling.
# 2026-09-05 - v2: Added magic-byte content sniffing for mislabeled Google
#              Takeout files (HEIC→.jpg, WEBP→.jpg, etc), pillow-heif HEIC
#              decoder integration, and broken-file placeholder generation
#              so every photo gets SOME thumbnail and the gallery never has gaps.
# ==============================================================================

import hashlib
import io
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageOps

from backend.config import THUMBNAIL_QUALITY, THUMBNAIL_SIZE, THUMBNAILS_DIR

logger = logging.getLogger("ThumbnailManager")

# --------------------------------------------------------------------------
# Locate FFmpeg for video frame extraction
# --------------------------------------------------------------------------
_env_ffmpeg = os.environ.get("FFMPEG_PATH")
_ffmpeg_path: Optional[str] = shutil.which("ffmpeg")
if _env_ffmpeg and Path(_env_ffmpeg).is_file():
    _ffmpeg_path = _env_ffmpeg
elif not _ffmpeg_path and Path(r"C:\ffmpeg\bin\ffmpeg.exe").is_file():
    _ffmpeg_path = r"C:\ffmpeg\bin\ffmpeg.exe"

if _ffmpeg_path:
    logger.info(f"FFmpeg located at: {_ffmpeg_path} (Video thumbnails enabled)")
else:
    logger.warning("FFmpeg not found. Video files will use fallback placeholder thumbnails.")

# --------------------------------------------------------------------------
# Register pillow-heif for HEIC/HEIF support if available
# --------------------------------------------------------------------------
_heif_available = False
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    _heif_available = True
    logger.info("pillow-heif registered: HEIC/HEIF thumbnails enabled.")
except ImportError:
    logger.warning("pillow-heif not installed. HEIC files will get placeholder thumbnails.")


def get_thumbnail_filename(file_path: str, photo_id: int) -> str:
    """Generates a stable deterministic thumbnail filename."""
    path_hash = hashlib.md5(file_path.encode("utf-8")).hexdigest()[:12]
    return f"thumb_{photo_id}_{path_hash}.webp"


def _extract_video_thumbnail(video_path: Path, thumb_path: Path) -> Tuple[bool, int, int]:
    """
    Extracts a frame snapshot from a video using ffmpeg at 1.0s (or 0.0s fallback)
    and saves it directly as a high-performance WebP thumbnail.
    Uses -hwaccel auto for GPU-accelerated frame decoding.
    Returns: (success, width, height)
    """
    if not _ffmpeg_path:
        return False, 0, 0

    seek_times = ["00:00:01.000", "00:00:00.000"]
    scale_filter = f"scale={THUMBNAIL_SIZE[0]}:{THUMBNAIL_SIZE[1]}:force_original_aspect_ratio=decrease"

    for seek in seek_times:
        try:
            cmd = [
                _ffmpeg_path,
                "-y",
                "-hwaccel", "auto",
                "-ss", seek,
                "-i", str(video_path),
                "-vframes", "1",
                "-vf", scale_filter,
                "-q:v", str(THUMBNAIL_QUALITY),
                str(thumb_path),
            ]
            res = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            if res.returncode == 0 and thumb_path.is_file() and thumb_path.stat().st_size > 0:
                with Image.open(thumb_path) as im:
                    w, h = im.size
                return True, w, h
        except Exception as e:
            logger.debug(f"ffmpeg extraction failed at {seek} for {video_path.name}: {e}")

    return False, 0, 0


def _detect_real_format(file_path: Path) -> str:
    """
    Sniffs magic bytes to detect actual image format, ignoring the file extension.
    Google Takeout frequently mislabels HEIC as .jpg and WEBP as .jpg/.png.
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(32)
    except Exception:
        return "UNKNOWN"

    # JPEG: FF D8 FF
    if header[:3] == b'\xff\xd8\xff':
        return "JPEG"
    # PNG: 89 50 4E 47
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return "PNG"
    # WEBP: RIFF....WEBP
    if header[:4] == b'RIFF' and b'WEBP' in header[:16]:
        return "WEBP"
    # GIF: GIF87a or GIF89a
    if header[:4] == b'GIF8':
        return "GIF"
    # HEIC/HEIF/AVIF: ftyp box
    if b'ftyp' in header[:16]:
        ftyp_data = header[:32].lower()
        if b'heic' in ftyp_data or b'heif' in ftyp_data or b'mif1' in ftyp_data:
            return "HEIC"
        if b'avif' in ftyp_data:
            return "AVIF"
        # Could be video (mp4/mov) mislabeled
        return "MP4_FTYP"
    # BMP: BM
    if header[:2] == b'BM':
        return "BMP"
    # TIFF: II or MM
    if header[:2] in (b'II', b'MM'):
        return "TIFF"
    return "UNKNOWN"


def _open_image_with_sniffing(file_path: Path) -> Image.Image:
    """
    Opens an image file, using content sniffing to handle mislabeled extensions.
    Falls back through multiple strategies to maximize compatibility.
    """
    # Strategy 1: Try Pillow directly (works for correctly-labeled files)
    try:
        img = Image.open(file_path)
        img.load()  # Force decode to catch lazy-load errors
        return img
    except Exception:
        pass

    # Strategy 2: Detect real format and try format-specific opening
    real_format = _detect_real_format(file_path)

    if real_format == "WEBP":
        # Re-open with explicit format hint by reading bytes
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            img = Image.open(io.BytesIO(data))
            img.load()
            return img
        except Exception:
            pass

    if real_format == "HEIC":
        if _heif_available:
            try:
                # pillow-heif registered opener should handle BytesIO
                with open(file_path, "rb") as f:
                    data = f.read()
                img = Image.open(io.BytesIO(data))
                img.load()
                return img
            except Exception as e:
                logger.debug(f"HEIC decode failed for {file_path.name}: {e}")
        else:
            raise ValueError(f"HEIC file but pillow-heif not available: {file_path.name}")

    if real_format in ("JPEG", "PNG", "GIF", "BMP", "TIFF"):
        # Try reading bytes and opening without file extension influence
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            img = Image.open(io.BytesIO(data))
            img.load()
            return img
        except Exception:
            pass

    raise ValueError(f"Cannot decode image: {file_path.name} (detected format: {real_format})")


def create_video_placeholder(thumb_path: Path, filename: str) -> None:
    """Generates an aesthetic modern placeholder for video files."""
    img = Image.new("RGB", THUMBNAIL_SIZE, color=(24, 28, 36))
    draw = ImageDraw.Draw(img)

    cx, cy = THUMBNAIL_SIZE[0] // 2, THUMBNAIL_SIZE[1] // 2
    # Draw play circle
    r = 48
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(45, 52, 68), outline=(90, 105, 135), width=2)

    # Draw play triangle
    poly = [(cx - 14, cy - 22), (cx - 14, cy + 22), (cx + 26, cy)]
    draw.polygon(poly, fill=(255, 255, 255))

    img.save(thumb_path, "WEBP", quality=85)


def _create_broken_placeholder(thumb_path: Path, filename: str) -> None:
    """
    Creates a styled placeholder for images that truly cannot be decoded.
    This ensures the gallery grid has no gaps — every photo gets a thumbnail.
    """
    img = Image.new("RGB", THUMBNAIL_SIZE, color=(32, 30, 38))
    draw = ImageDraw.Draw(img)

    cx, cy = THUMBNAIL_SIZE[0] // 2, THUMBNAIL_SIZE[1] // 2

    # Draw broken image icon (cracked rectangle)
    r = 40
    draw.rectangle([cx - r, cy - r, cx + r, cy + r], outline=(80, 70, 90), width=2)
    # Diagonal crack
    draw.line([(cx - r, cy - r), (cx, cy)], fill=(120, 100, 130), width=2)
    draw.line([(cx, cy), (cx + r, cy + r)], fill=(120, 100, 130), width=2)

    # Small text: filename truncated
    label = filename[:20] + "…" if len(filename) > 20 else filename
    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, cy + r + 8), label, fill=(100, 90, 110), font=font)

    img.save(thumb_path, "WEBP", quality=75)


def generate_thumbnail(
    photo_id: int,
    file_path: str,
    media_type: str = "image",
    force: bool = False,
) -> Tuple[Optional[str], int, int]:
    """
    Generates a high-quality WebP thumbnail for a media file.
    Uses content-sniffing for photos and ffmpeg frame extraction for videos.
    Always returns a valid thumbnail (placeholder for truly broken files).
    Returns: (thumbnail_relative_path, original_width, original_height)
    """
    source_path = Path(file_path)
    if not source_path.is_file():
        return None, 0, 0

    thumb_name = get_thumbnail_filename(file_path, photo_id)
    thumb_path = THUMBNAILS_DIR / thumb_name
    rel_path = f"data/thumbnails/{thumb_name}"

    # If thumbnail already exists on disk and force is False, return it
    if not force and thumb_path.is_file():
        try:
            with Image.open(thumb_path) as im:
                return rel_path, im.width, im.height
        except Exception:
            # Corrupted thumbnail — regenerate
            thumb_path.unlink(missing_ok=True)

    # ----- Video thumbnails (extract real frame via FFmpeg) -----
    if media_type == "video":
        success, vw, vh = _extract_video_thumbnail(source_path, thumb_path)
        if success:
            return rel_path, vw, vh

        # Fallback to placeholder if extraction fails or video file corrupted
        try:
            create_video_placeholder(thumb_path, source_path.name)
            return rel_path, THUMBNAIL_SIZE[0], THUMBNAIL_SIZE[1]
        except Exception as e:
            logger.error(f"Video placeholder fallback failed for {source_path.name}: {e}")
            return None, 0, 0

    # ----- Image thumbnailing with content-sniffing -----
    try:
        img = _open_image_with_sniffing(source_path)

        # Auto-rotate according to EXIF
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass  # Some formats don't have EXIF

        orig_width, orig_height = img.width, img.height

        # Convert mode if necessary (e.g. RGBA/CMYK/P to RGB for WebP)
        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGBA", img.size, (25, 27, 31, 255))
            background.paste(img, mask=img.split()[-1])
            img = background.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Thumbnail preserving aspect ratio
        img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        img.save(thumb_path, "WEBP", quality=THUMBNAIL_QUALITY, method=4)

        return rel_path, orig_width, orig_height

    except Exception as e:
        # Truly unreadable — generate a styled broken-file placeholder
        logger.warning(f"Image unreadable, creating placeholder: {source_path.name} ({e})")
        try:
            _create_broken_placeholder(thumb_path, source_path.name)
            return rel_path, THUMBNAIL_SIZE[0], THUMBNAIL_SIZE[1]
        except Exception as e2:
            logger.error(f"Placeholder creation also failed: {e2}")
            return None, 0, 0
