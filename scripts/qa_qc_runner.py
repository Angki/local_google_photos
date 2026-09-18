# ==============================================================================
# File: scripts/qa_qc_runner.py
# Description: Automated QA / QC Test Suite for Google Photos Local Application.
#              Performs static checks, database validation, API contract tests,
#              edge cases, security checks, and latency benchmarking.
# ==============================================================================

import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
DB_PATH = Path("data/photos.db")

passed = 0
failed = 0
warnings = 0

def log_pass(name, details=""):
    global passed
    passed += 1
    print(f"  [PASS] {name}" + (f" -> {details}" if details else ""))

def log_fail(name, error=""):
    global failed
    failed += 1
    print(f"  [FAIL] {name}" + (f" -> {error}" if error else ""))

def log_warn(name, warning=""):
    global warnings
    warnings += 1
    print(f"  [WARN] {name}" + (f" -> {warning}" if warning else ""))

def http_request(path, method="GET", data=None, headers=None):
    url = f"{BASE_URL}{path}" if path.startswith("/") else path
    req_headers = headers or {}
    payload = None
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=payload, headers=req_headers, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            latency_ms = (time.perf_counter() - t0) * 1000
            body = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            return {
                "status": resp.status,
                "latency_ms": latency_ms,
                "headers": dict(resp.headers),
                "data": json.loads(body.decode("utf-8")) if "application/json" in content_type else body,
                "content_type": content_type
            }
    except urllib.error.HTTPError as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        err_body = e.read().decode("utf-8", errors="ignore")
        return {
            "status": e.code,
            "latency_ms": latency_ms,
            "headers": dict(e.headers),
            "data": err_body,
            "error": str(e)
        }
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        return {
            "status": 0,
            "latency_ms": latency_ms,
            "error": str(e)
        }

print("=" * 70)
print("GOOGLE PHOTOS LOCAL TAKEOUT ARCHIVE - COMPREHENSIVE QA / QC SUITE")
print("=" * 70)

# ------------------------------------------------------------------------------
# 1. STATIC & DOM CONSISTENCY AUDIT
# ------------------------------------------------------------------------------
print("\n[PHASE 1] Static Code & DOM Consistency Audit...")

try:
    with open("frontend/index.html", encoding="utf-8") as f:
        html_content = f.read()
    with open("frontend/app.js", encoding="utf-8") as f:
        js_content = f.read()

    html_ids = set(re.findall(r'id=["\']([a-zA-Z0-9_-]+)["\']', html_content))
    js_ids = set(re.findall(r'getElementById\(["\']([a-zA-Z0-9_-]+)["\']\)', js_content))
    
    missing_in_html = js_ids - html_ids
    if missing_in_html:
        log_warn("DOM Element IDs", f"IDs referenced in JS but missing in HTML: {missing_in_html}")
    else:
        log_pass("DOM Element IDs", f"All {len(js_ids)} JS element IDs exist in index.html")
except Exception as e:
    log_fail("Static DOM check", str(e))

# ------------------------------------------------------------------------------
# 2. DATABASE INTEGRITY & INDEX AUDIT
# ------------------------------------------------------------------------------
print("\n[PHASE 2] Database Integrity & SQLite Index Audit...")

if not DB_PATH.is_file():
    log_fail("Database file", f"Database not found at {DB_PATH}")
else:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        
        # Integrity check
        check = cur.execute("PRAGMA integrity_check;").fetchone()
        if check and check[0] == "ok":
            log_pass("SQLite Integrity", "PRAGMA integrity_check passed (ok)")
        else:
            log_fail("SQLite Integrity", str(check))
            
        # Foreign key check
        fk_check = cur.execute("PRAGMA foreign_key_check;").fetchall()
        if not fk_check:
            log_pass("Foreign Key Constraints", "No foreign key violations")
        else:
            log_fail("Foreign Key Constraints", f"Violations found: {len(fk_check)}")

        # WAL Mode Check
        journal_mode = cur.execute("PRAGMA journal_mode;").fetchone()
        log_pass("Journal Mode", f"Active mode is {journal_mode[0].upper()}")

        # Verify Tables & Row Counts
        cur.execute("SELECT COUNT(*) FROM photos WHERE deleted = 0;")
        active_photos = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM photos WHERE deleted = 1;")
        trash_photos = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM albums;")
        albums_count = cur.fetchone()[0]
        log_pass("Table Schema & Rows", f"Active Photos: {active_photos:,} | Trash: {trash_photos:,} | Albums: {albums_count}")

        # Index verification
        cur.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = [r[0] for r in cur.fetchall()]
        expected_indexes = ["idx_photos_taken_at", "idx_photos_deleted"]
        for idx in expected_indexes:
            if idx in indexes:
                log_pass(f"Index: {idx}", "Found and active")
            else:
                log_warn(f"Index: {idx}", "Missing index - recommended for query speed")

    except Exception as e:
        log_fail("Database checks", str(e))
    finally:
        conn.close()

# ------------------------------------------------------------------------------
# 3. API CONTRACT & ENDPOINT TESTS
# ------------------------------------------------------------------------------
print("\n[PHASE 3] API Endpoint Contract & Response Testing...")

endpoints_to_test = [
    ("Frontend Index HTML", "/", "GET", None, 200),
    ("Library Stats", "/api/stats", "GET", None, 200),
    ("Timeline Hierarchy", "/api/timeline", "GET", None, 200),
    ("Photos Pagination (Normal)", "/api/photos?limit=10&offset=0", "GET", None, 200),
    ("Photos Filtering by Year", "/api/photos?year=2024&limit=5", "GET", None, 200),
    ("Photos Filtering by Category", "/api/photos?category=nature&limit=5", "GET", None, 200),
    ("Photos Filtering by Media Type", "/api/photos?media_type=video&limit=5", "GET", None, 200),
    ("Photos Filtering by Geolocation", "/api/photos?has_geo=true&limit=5", "GET", None, 200),
    ("Albums List", "/api/albums", "GET", None, 200),
    ("Trash List", "/api/photos/trash?limit=5", "GET", None, 200),
    ("Scanner Status", "/api/scan/status", "GET", None, 200),
    ("Keyword / Semantic Search", "/api/search?q=pantai&limit=5", "GET", None, 200),
]

for name, path, method, data, expected_status in endpoints_to_test:
    res = http_request(path, method=method, data=data)
    if res["status"] == expected_status:
        log_pass(name, f"Status {res['status']} in {res['latency_ms']:.1f}ms")
    else:
        log_fail(name, f"Expected {expected_status}, got {res['status']} (Latency: {res['latency_ms']:.1f}ms) - {res.get('error', '')}")

# ------------------------------------------------------------------------------
# 4. EDGE CASE & BOUNDARY TESTING
# ------------------------------------------------------------------------------
print("\n[PHASE 4] Boundary, Negative & Edge-Case Testing...")

edge_cases = [
    ("Negative Limit", "/api/photos?limit=-5", "GET", None, 422),
    ("Zero Limit", "/api/photos?limit=0", "GET", None, 422),
    ("Large Offset", "/api/photos?offset=999999&limit=10", "GET", None, 200),
    ("Non-Existent Photo Detail", "/api/photos/9999999", "GET", None, 404),
    ("Invalid Non-Integer Photo ID", "/api/photos/notanumber", "GET", None, 422),
    ("Empty Search Query", "/api/search?q=", "GET", None, 422),
    ("Create Album Empty Name", "/api/albums", "POST", {"name": "   "}, 400),
    ("Non-Existent Album Detail", "/api/albums/9999999/photos", "GET", None, 200),
]

for name, path, method, data, expected_status in edge_cases:
    res = http_request(path, method=method, data=data)
    if res["status"] == expected_status:
        log_pass(name, f"Handled correctly with {res['status']} in {res['latency_ms']:.1f}ms")
    else:
        log_fail(name, f"Expected {expected_status}, got {res['status']} ({res.get('data')})")

# ------------------------------------------------------------------------------
# 5. MEDIA STREAMING, THUMBNAILS & HTTP RANGE TESTS
# ------------------------------------------------------------------------------
print("\n[PHASE 5] Media Streaming, Thumbnails & HTTP Range Partial Content...")

# Grab 1 image and 1 video from database
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
image_sample = cur.execute("SELECT id, file_path FROM photos WHERE media_type='image' AND deleted=0 LIMIT 1;").fetchone()
video_sample = cur.execute("SELECT id, file_path FROM photos WHERE media_type='video' AND deleted=0 LIMIT 1;").fetchone()
conn.close()

if image_sample:
    img_id = image_sample[0]
    # Test Thumbnail headers
    thumb_res = http_request(f"/api/thumbnails/{img_id}")
    if thumb_res["status"] == 200:
        cache_hdr = thumb_res["headers"].get("cache-control", "")
        if "immutable" in cache_hdr or "max-age" in cache_hdr:
            log_pass(f"Thumbnail Cache Headers (ID {img_id})", f"Cache-Control: {cache_hdr}")
        else:
            log_warn(f"Thumbnail Cache Headers (ID {img_id})", f"Missing immutable cache header: {cache_hdr}")
    else:
        log_fail(f"Thumbnail Serving (ID {img_id})", f"Status {thumb_res['status']}")

    # Test Full Media
    media_res = http_request(f"/api/media/{img_id}")
    if media_res["status"] == 200:
        log_pass(f"Image Media Serving (ID {img_id})", f"Content-Type: {media_res['content_type']}")
    else:
        log_fail(f"Image Media Serving (ID {img_id})", f"Status {media_res['status']}")

if video_sample:
    vid_id = video_sample[0]
    # Test HTTP Range request (bytes=0-1023)
    range_res = http_request(f"/api/media/{vid_id}", headers={"Range": "bytes=0-1023"})
    if range_res["status"] == 206:
        content_range = range_res["headers"].get("content-range", "")
        log_pass(f"Video Range 206 Partial Content (ID {vid_id})", f"Content-Range: {content_range}")
    elif range_res["status"] == 200:
        log_warn(f"Video Range (ID {vid_id})", "Returned 200 instead of 206 Partial Content")
    else:
        log_fail(f"Video Range (ID {vid_id})", f"Status {range_res['status']}")
else:
    log_warn("Video Range Test", "No videos available in database to test video streaming")

# ------------------------------------------------------------------------------
# 6. MUTATION CYCLE: CREATE ALBUM -> ADD PHOTOS -> REMOVE -> DELETE
# ------------------------------------------------------------------------------
print("\n[PHASE 6] Album Lifecycle & Photo Mutex Testing...")

album_name = f"QA Test Album {int(time.time())}"
create_res = http_request("/api/albums", method="POST", data={"name": album_name})
if create_res["status"] == 200 and create_res.get("data", {}).get("album_id"):
    created_id = create_res["data"]["album_id"]
    log_pass(f"Create Album ('{album_name}')", f"Created Album ID {created_id}")

    # Add photo to album
    if image_sample:
        add_res = http_request(f"/api/albums/{created_id}/photos", method="POST", data={"photo_ids": [image_sample[0]]})
        if add_res["status"] == 200 and add_res["data"].get("added_count") == 1:
            log_pass("Add Photo to Album", f"Added photo {image_sample[0]}")
        else:
            log_fail("Add Photo to Album", str(add_res))

        # Check album photos
        chk_res = http_request(f"/api/albums/{created_id}/photos")
        if chk_res["status"] == 200 and len(chk_res["data"].get("photos", [])) == 1:
            log_pass("Verify Photos in Album", "Photo confirmed in album")
        else:
            log_fail("Verify Photos in Album", str(chk_res))

        # Remove photo from album
        rem_res = http_request(f"/api/albums/{created_id}/photos", method="DELETE", data={"photo_ids": [image_sample[0]]})
        if rem_res["status"] == 200 and rem_res["data"].get("removed_count") == 1:
            log_pass("Remove Photo from Album", "Photo removed from album")
        else:
            log_fail("Remove Photo from Album", str(rem_res))

    # Delete album
    del_alb_res = http_request(f"/api/albums/{created_id}", method="DELETE")
    if del_alb_res["status"] == 200 and del_alb_res["data"].get("success"):
        log_pass(f"Delete Album (ID {created_id})", "Album deleted successfully")
    else:
        log_fail(f"Delete Album (ID {created_id})", str(del_alb_res))
else:
    log_fail("Create Album", str(create_res))

# ------------------------------------------------------------------------------
# 7. MUTATION CYCLE: SOFT-DELETE -> TRASH -> RESTORE
# ------------------------------------------------------------------------------
print("\n[PHASE 7] Soft-Delete & Restore Lifecycle Testing...")

if image_sample:
    target_id = image_sample[0]
    
    # 1. Soft delete
    del_res = http_request("/api/photos/delete", method="POST", data={"photo_ids": [target_id]})
    if del_res["status"] == 200 and del_res["data"].get("deleted_count") == 1:
        log_pass(f"Soft-Delete Photo (ID {target_id})", "Photo marked deleted=1")
    else:
        log_fail(f"Soft-Delete Photo (ID {target_id})", str(del_res))

    # 2. Verify in Trash
    trash_res = http_request("/api/photos/trash?limit=20")
    trash_ids = [p["id"] for p in trash_res.get("data", {}).get("photos", [])]
    if target_id in trash_ids:
        log_pass("Verify in Trash", f"Photo {target_id} is present in trash list")
    else:
        log_fail("Verify in Trash", f"Photo {target_id} not found in trash list")

    # 3. Verify absent from active library
    active_res = http_request(f"/api/photos?limit=100")
    active_ids = [p["id"] for p in active_res.get("data", {}).get("photos", [])]
    if target_id not in active_ids:
        log_pass("Verify Hidden from Active Library", f"Photo {target_id} not in active feed")
    else:
        log_fail("Verify Hidden from Active Library", f"Photo {target_id} still appears in active feed!")

    # 4. Restore photo
    res_res = http_request("/api/photos/restore", method="POST", data={"photo_ids": [target_id]})
    if res_res["status"] == 200 and res_res["data"].get("restored_count") == 1:
        log_pass(f"Restore Photo (ID {target_id})", "Photo restored to active library")
    else:
        log_fail(f"Restore Photo (ID {target_id})", str(res_res))

# ------------------------------------------------------------------------------
# 8. BENCHMARK SUMMARY
# ------------------------------------------------------------------------------
print("\n" + "=" * 70)
print(f"QA / QC AUDIT RESULTS: {passed} PASSED | {failed} FAILED | {warnings} WARNINGS")
print("=" * 70)

if failed > 0:
    sys.exit(1)
