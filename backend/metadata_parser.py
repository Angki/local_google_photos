# ==============================================================================
# File: backend/metadata_parser.py
# Description: Resolves and parses Google Takeout companion JSON metadata files
#              with fallback to EXIF and filesystem stats.
#
# CHANGELOG:
# 2026-09-05 - Initial creation: Built multi-tier resolution chain for Takeout JSONs
#              including supplemental-metadata, parentheses numbering quirks,
#              truncation handling, and rich field extraction (timestamp, geo, origin).
# ==============================================================================

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image, ExifTags

# Regex to detect duplicate numbering like "IMG_001(1).jpg" -> base "IMG_001", num "1", ext ".jpg"
NUMBERED_FILE_REGEX = re.compile(r"^(.*?)\((\d+)\)(\.[^.]+)$")


def find_metadata_json(media_path: Path) -> Optional[Path]:
    """
    Locates the companion Google Takeout JSON file for a given media file
    using a multi-tier resolution chain.
    """
    directory = media_path.parent
    filename = media_path.name
    stem = media_path.stem
    suffix = media_path.suffix

    candidates: List[Path] = [
        # 1. Direct supplemental-metadata (Standard modern Google Takeout)
        directory / f"{filename}.supplemental-metadata.json",
        # 2. Direct .json extension (Classic Google Takeout)
        directory / f"{filename}.json",
        # 3. Stem .json
        directory / f"{stem}.json",
        # 4. Stem .supplemental-metadata.json
        directory / f"{stem}.supplemental-metadata.json",
    ]

    # 5. Handle numbered duplicate quirk:
    # E.g. "IMG_123(1).jpg" -> Google names JSON "IMG_123.jpg.supplemental-metadata(1).json"
    match = NUMBERED_FILE_REGEX.match(filename)
    if match:
        base_name, num, ext = match.group(1), match.group(2), match.group(3)
        candidates.extend([
            directory / f"{base_name}{ext}.supplemental-metadata({num}).json",
            directory / f"{base_name}{ext}({num}).json",
            directory / f"{base_name}({num}){ext}.supplemental-metadata.json",
            directory / f"{base_name}({num}).json",
            directory / f"{base_name}.supplemental-metadata({num}).json",
        ])

    # 6. Check candidates
    for cand in candidates:
        if cand.is_file():
            return cand

    # 7. Truncated filename heuristic:
    # Google Takeout truncates filenames longer than ~46-51 chars before appending .json
    if len(stem) > 40:
        short_stem = stem[:46]
        for f in directory.glob(f"{short_stem}*.json"):
            return f

    return None


def extract_exif_datetime(image_path: Path) -> Optional[int]:
    """Extracts capture timestamp directly from image EXIF if available."""
    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
            if not exif:
                return None
            for tag_id, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                if tag_name in ("DateTimeOriginal", "DateTime"):
                    # Format: "YYYY:MM:DD HH:MM:SS"
                    dt = datetime.strptime(str(value).strip(), "%Y:%m:%d %H:%M:%S")
                    return int(dt.timestamp())
    except Exception:
        pass
    return None


def parse_photo_metadata(media_path: Path) -> Dict[str, Any]:
    """
    Parses Google Takeout JSON companion file or falls back to EXIF / file stats.
    Returns a normalized dictionary of metadata.
    """
    json_path = find_metadata_json(media_path)
    data: Dict[str, Any] = {}

    if json_path:
        try:
            with open(json_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except Exception:
            data = {}

    # 1. Determine Taken Timestamp
    taken_timestamp: Optional[int] = None
    taken_formatted: str = ""

    # Check photoTakenTime.timestamp (Google Photos original shot time)
    photo_taken_time = data.get("photoTakenTime", {})
    if isinstance(photo_taken_time, dict):
        raw_ts = photo_taken_time.get("timestamp")
        if raw_ts:
            try:
                taken_timestamp = int(raw_ts)
                taken_formatted = photo_taken_time.get("formatted", "")
            except (ValueError, TypeError):
                pass

    # Fallback to creationTime (Google Photos upload time)
    if not taken_timestamp:
        creation_time = data.get("creationTime", {})
        if isinstance(creation_time, dict):
            raw_ts = creation_time.get("timestamp")
            if raw_ts:
                try:
                    taken_timestamp = int(raw_ts)
                    taken_formatted = creation_time.get("formatted", "")
                except (ValueError, TypeError):
                    pass

    # Fallback to EXIF if image
    if not taken_timestamp and media_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
        taken_timestamp = extract_exif_datetime(media_path)

    # Final Fallback to OS file modification time
    if not taken_timestamp or taken_timestamp <= 0:
        try:
            taken_timestamp = int(media_path.stat().st_mtime)
        except Exception:
            taken_timestamp = int(datetime.now().timestamp())

    # Derive year, month, day
    dt = datetime.fromtimestamp(taken_timestamp)
    year = dt.year
    month = dt.month
    day = dt.day
    if not taken_formatted:
        taken_formatted = dt.strftime("%b %d, %Y, %I:%M:%S %p")
    else:
        # Google Takeout uses narrow no-break space (\u202f) before AM/PM; normalize to standard space
        taken_formatted = taken_formatted.replace("\u202f", " ").replace("\u00a0", " ")

    # 2. Geolocation extraction
    geo = data.get("geoData", {})
    latitude = float(geo.get("latitude", 0.0) or 0.0)
    longitude = float(geo.get("longitude", 0.0) or 0.0)
    altitude = float(geo.get("altitude", 0.0) or 0.0)
    has_geo = not (abs(latitude) < 0.0001 and abs(longitude) < 0.0001)

    # 3. People tagged
    people_list = []
    raw_people = data.get("people", [])
    if isinstance(raw_people, list):
        for p in raw_people:
            if isinstance(p, dict) and "name" in p:
                people_list.append(p["name"])

    # 4. Origin and App Source
    device_folder = ""
    origin = data.get("googlePhotosOrigin", {})
    if isinstance(origin, dict):
        mobile_upload = origin.get("mobileUpload", {})
        if isinstance(mobile_upload, dict):
            device_folder = mobile_upload.get("deviceFolder", {}).get("localFolderName", "")
        elif "webUpload" in origin:
            device_folder = "Web Upload"

    app_source = ""
    app_source_data = data.get("appSource", {})
    if isinstance(app_source_data, dict):
        app_source = app_source_data.get("androidPackageName", "")

    description = str(data.get("description", "") or "").strip()
    google_url = str(data.get("url", "") or "")

    return {
        "json_found": json_path is not None,
        "json_path": str(json_path) if json_path else None,
        "taken_at": taken_timestamp,
        "taken_year": year,
        "taken_month": month,
        "taken_day": day,
        "taken_formatted": taken_formatted,
        "latitude": latitude if has_geo else None,
        "longitude": longitude if has_geo else None,
        "altitude": altitude if has_geo else None,
        "has_geo": has_geo,
        "description": description,
        "people": people_list,
        "device_folder": device_folder,
        "app_source": app_source,
        "google_url": google_url,
    }
