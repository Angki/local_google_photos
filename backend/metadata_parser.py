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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image, ExifTags

# Regex to detect duplicate numbering like "IMG_001(1).jpg" -> base "IMG_001", num "1", ext ".jpg"
NUMBERED_FILE_REGEX = re.compile(r"^(.*?)\((\d+)\)(\.[^.]+)$")
YEAR_FOLDER_REGEX = re.compile(r"^Photos from (\d{4})$", re.IGNORECASE)


def extract_date_from_filename(filename: str, fallback_year: Optional[int] = None) -> Optional[datetime]:
    """
    Extracts capture datetime from filename using regex patterns for camera standard,
    WhatsApp, 1998CAM, epoch timestamps, and screenshots.
    If fallback_year is provided, ensures the year aligns with the folder year.
    If no date pattern matches and fallback_year is provided, returns Jan 1 of that year.
    """
    stem = Path(filename).stem

    def make_dt(y: int, mo: int, d: int, h: int = 12, mi: int = 0, s: int = 0) -> Optional[datetime]:
        target_year = fallback_year if fallback_year is not None else y
        # Clamp day to valid range for month
        if mo in (4, 6, 9, 11):
            d = min(d, 30)
        elif mo == 2:
            is_leap = (target_year % 4 == 0 and (target_year % 100 != 0 or target_year % 400 == 0))
            d = min(d, 29 if is_leap else 28)
        else:
            d = min(d, 31)
        try:
            return datetime(target_year, mo, max(1, d), min(23, max(0, h)), min(59, max(0, mi)), min(59, max(0, s)))
        except ValueError:
            return None

    # 1. Full camera/screenshot format: YYYYMMDD_HHMMSS (e.g. 20210715_170109, IMG_20211025_212930_508, IMG20210312231839, Screenshot_20211029-163538)
    m = re.search(r"(?:^|[^\d])(20\d\d)[_-]?([01]\d)[_-]?([0-3]\d)[_-]?([0-2]\d)([0-5]\d)([0-5]\d)", stem)
    if m:
        y, mo, d, h, mi, s = map(int, m.groups())
        if 1 <= mo <= 12 and 1 <= d <= 31:
            res = make_dt(y, mo, d, h, mi, s)
            if res:
                return res

    # 2. 1998CAM app format: 1998CAM_2021_01_04_14_32_47_FN
    m = re.search(r"1998CAM_(20\d\d)_([01]\d)_([0-3]\d)_([0-2]\d)_([0-5]\d)_([0-5]\d)", stem, re.I)
    if m:
        y, mo, d, h, mi, s = map(int, m.groups())
        if 1 <= mo <= 12 and 1 <= d <= 31:
            res = make_dt(y, mo, d, h, mi, s)
            if res:
                return res

    # 3. WhatsApp format: VID-20211017-WA0081, IMG-20210223-WA0031
    m = re.search(r"(?:IMG|VID)[_-](20\d\d)([01]\d)([0-3]\d)[_-]WA\d+", stem, re.I)
    if m:
        y, mo, d = map(int, m.groups())
        if 1 <= mo <= 12 and 1 <= d <= 31:
            res = make_dt(y, mo, d)
            if res:
                return res

    # 4. Video camera prefix with MM and DD: VID_\d{4}(MM)(DD)_(HH)(MM)(SS) (e.g. VID_23471011_115355_190)
    m = re.search(r"VID_\d{4}([01]\d)([0-3]\d)[_-]([0-2]\d)([0-5]\d)([0-5]\d)", stem, re.I)
    if m:
        mo, d, h, mi, s = map(int, m.groups())
        if 1 <= mo <= 12 and 1 <= d <= 31 and fallback_year is not None:
            res = make_dt(fallback_year, mo, d, h, mi, s)
            if res:
                return res

    # 5. Standard compact date: YYYYMMDD
    m = re.search(r"(?:^|[^\d])(20\d\d)([01]\d)([0-3]\d)(?:[^\d]|$)", stem)
    if m:
        y, mo, d = map(int, m.groups())
        if 1 <= mo <= 12 and 1 <= d <= 31:
            res = make_dt(y, mo, d)
            if res:
                return res

    # 6. Delimited date: YYYY-MM-DD or YYYY_MM_DD
    m = re.search(r"(?:^|[^\d])(20\d\d)[-_]([01]\d)[-_]([0-3]\d)(?:[^\d]|$)", stem)
    if m:
        y, mo, d = map(int, m.groups())
        if 1 <= mo <= 12 and 1 <= d <= 31:
            res = make_dt(y, mo, d)
            if res:
                return res

    # 7. Unix Epoch millisecond (13 digits: FB_IMG_1611317343217, 1615579230801)
    m = re.search(r"(?:^|[^\d])(1[3-7]\d{11})(?:[^\d]|$)", stem)
    if m:
        try:
            ts = int(m.group(1)) / 1000.0
            dt = datetime.fromtimestamp(ts)
            res = make_dt(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
            if res:
                return res
        except (ValueError, OSError):
            pass

    # 8. Unix Epoch second (10 digits: 1611317343)
    m = re.search(r"(?:^|[^\d])(1[3-7]\d{8})(?:[^\d]|$)", stem)
    if m:
        try:
            ts = int(m.group(1))
            dt = datetime.fromtimestamp(ts)
            res = make_dt(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
            if res:
                return res
        except (ValueError, OSError):
            pass

    # 9. Fallback when no date pattern matched:
    # If in a year folder, default to January 1st of that year as requested
    if fallback_year is not None:
        return datetime(fallback_year, 1, 1, 12, 0, 0)

    return None


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


def parse_photo_metadata(media_path: Path, fallback_year: Optional[int] = None) -> Dict[str, Any]:
    """
    Parses Google Takeout JSON companion file or falls back to EXIF,
    filename date parsing, or parent directory year fallback.
    Returns a normalized dictionary of metadata.
    """
    json_path = find_metadata_json(media_path)
    data: Dict[str, Any] = {}

    parent_name = media_path.parent.name
    year_match = YEAR_FOLDER_REGEX.match(parent_name)
    if year_match:
        parent_folder_year: Optional[int] = int(year_match.group(1))
    elif fallback_year is not None:
        parent_folder_year = fallback_year
    else:
        # Check if parent folder name contains a 4-digit year like "LaLaLa Fest 2025" or "RIC 2022"
        year_search = re.search(r"\b(20\d\d)\b", parent_name)
        parent_folder_year = int(year_search.group(1)) if year_search else None

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

    # Fallback to filename date parsing (especially for folders with no JSON like 2021, 2020)
    if not taken_timestamp or taken_timestamp <= 0:
        parsed_dt = extract_date_from_filename(media_path.name, fallback_year=parent_folder_year)
        if parsed_dt:
            taken_timestamp = int(parsed_dt.timestamp())
            taken_formatted = parsed_dt.strftime("%b %d, %Y, %I:%M:%S %p")

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

    # If inside a year archive (Photos from YYYY), ensure year alignment
    if parent_folder_year is not None and year != parent_folder_year:
        # Check if UTC time resolves the boundary (e.g. Dec 31 UTC vs Jan 1 local)
        try:
            dt_utc = datetime.fromtimestamp(taken_timestamp, timezone.utc)
            if dt_utc.year == parent_folder_year:
                year = dt_utc.year
                month = dt_utc.month
                day = dt_utc.day
            else:
                year = parent_folder_year
        except Exception:
            year = parent_folder_year

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
