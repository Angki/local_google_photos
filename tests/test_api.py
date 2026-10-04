# ==============================================================================
# File: tests/test_api.py
# Description: Enterprise-grade automated test suite for Google Photos Local App.
#              Tests API contracts, OpenAPI schema, health probes, migrations,
#              lifecycle endpoints, and AI search with isolated mocking.
# ==============================================================================

import asyncio
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
import httpx
import numpy as np

from backend.config import is_target_folder
from backend.database import (
    add_photos_to_album,
    create_album,
    delete_photos,
    delete_photos_from_disk_and_db,
    get_albums,
    get_db_connection,
    get_deleted_photos,
    get_library_stats,
    get_photo_by_id,
    get_photos,
    get_timeline_hierarchy,
    init_db,
    restore_photos,
)
from backend.main import app


class TestGooglePhotosTakeout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initializes database and verifies schema migrations."""
        init_db()

    def test_database_schema_migrations(self):
        """Verifies that schema_migrations table tracks versions properly."""
        with get_db_connection() as conn:
            rows = conn.execute("SELECT version, description FROM schema_migrations ORDER BY version ASC;").fetchall()
            versions = [r["version"] for r in rows]
            self.assertIn(1, versions)
            self.assertIn(2, versions)
            self.assertIn(3, versions)
            self.assertIn(4, versions)
            self.assertIn(5, versions)

    def test_target_folder_filtering(self):
        """Tests that years 2013-2026 and Takeout albums are accepted, and system folders are rejected."""
        # Supported year folders
        self.assertTrue(is_target_folder("Photos from 2013"))
        self.assertTrue(is_target_folder("Photos from 2015"))
        self.assertTrue(is_target_folder("Photos from 2020"))
        self.assertTrue(is_target_folder("Photos from 2024"))
        self.assertTrue(is_target_folder("Photos from 2026"))

        # Supported album folders
        self.assertTrue(is_target_folder("ART"))
        self.assertTrue(is_target_folder("RIC 2022"))
        self.assertTrue(is_target_folder("Flyer"))
        self.assertTrue(is_target_folder("Bahan Stiker"))

        # Excluded system folders
        self.assertFalse(is_target_folder(".local-photo-manager"))
        self.assertFalse(is_target_folder("local-google-photos"))
        self.assertFalse(is_target_folder(".venv"))
        self.assertFalse(is_target_folder(".git"))
        self.assertFalse(is_target_folder("thumbnails"))

    def test_openapi_schema_generation(self):
        """Verifies that the OpenAPI/Swagger documentation schema compiles cleanly."""
        schema = app.openapi()
        self.assertIsInstance(schema, dict)
        self.assertEqual(schema["info"]["title"], "Google Photos Local Takeout Archive")
        self.assertIn("/healthz", schema["paths"])
        self.assertIn("/readyz", schema["paths"])
        self.assertIn("/api/photos", schema["paths"])
        self.assertIn("/api/search", schema["paths"])

    def test_healthz_liveness_probe(self):
        """Tests the /healthz liveness endpoint via ASGI client."""
        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/healthz")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertEqual(data["status"], "healthy")
                self.assertEqual(data["service"], "google-photos-local")
        asyncio.run(_run())

    def test_readyz_readiness_probe(self):
        """Tests the /readyz readiness endpoint via ASGI client."""
        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/readyz")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertEqual(data["status"], "ready")
                self.assertEqual(data["database"], "connected")
        asyncio.run(_run())

    def test_security_headers_middleware(self):
        """Verifies enterprise security headers on responses."""
        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/healthz")
                self.assertEqual(resp.headers.get("x-content-type-options"), "nosniff")
                self.assertEqual(resp.headers.get("x-frame-options"), "SAMEORIGIN")
                self.assertEqual(resp.headers.get("referrer-policy"), "strict-origin-when-cross-origin")
        asyncio.run(_run())

    def test_timeline_hierarchy(self):
        """Verifies timeline hierarchy returns structured year and month counts."""
        timeline = get_timeline_hierarchy()
        self.assertIsInstance(timeline, list)
        if timeline:
            first_year = timeline[0]
            self.assertIn("year", first_year)
            self.assertIn("total", first_year)
            self.assertIn("months", first_year)
            self.assertGreater(first_year["total"], 0)

    def test_api_timeline_endpoint(self):
        """Tests the /api/timeline endpoint via ASGI client to ensure Pydantic response validation passes."""
        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/timeline")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertIn("timeline", data)
                self.assertIsInstance(data["timeline"], list)
                if data["timeline"]:
                    first_item = data["timeline"][0]
                    self.assertIn("year", first_item)
                    self.assertIn("total", first_item)
                    self.assertIn("months", first_item)
                    if first_item["months"]:
                        m = first_item["months"][0]
                        self.assertIn("month", m)
                        self.assertIn("month_name", m)
                        self.assertIn("count", m)
        asyncio.run(_run())

    def test_photos_pagination(self):
        """Verifies photo pagination works and returns dictionaries."""
        photos = get_photos(limit=5, offset=0)
        self.assertIsInstance(photos, list)
        if photos:
            p = photos[0]
            self.assertIn("id", p)
            self.assertIn("file_path", p)
            self.assertIn("taken_year", p)
            self.assertIn("taken_month", p)

    def test_soft_delete_and_restore(self):
        """Verifies that delete_photos hides photos, appears in trash, and restore_photos restores them."""
        photos = get_photos(limit=2, offset=0)
        if not photos:
            self.skipTest("No photos in database to test delete/restore.")

        test_id = photos[0]["id"]

        # Delete photo
        deleted_count = delete_photos([test_id])
        self.assertEqual(deleted_count, 1)

        # Should not appear in active get_photos
        active_ids = [p["id"] for p in get_photos(photo_ids=[test_id])]
        self.assertEqual(active_ids, [])

        # Should appear in Trash
        trash = get_deleted_photos(limit=20)
        trash_ids = [p["id"] for p in trash]
        self.assertIn(test_id, trash_ids)

        # Restore photo
        restored_count = restore_photos([test_id])
        self.assertEqual(restored_count, 1)

        # Should appear back in active get_photos
        restored_active = [p["id"] for p in get_photos(photo_ids=[test_id])]
        self.assertEqual(restored_active, [test_id])

    def test_album_creation_and_stats(self):
        """Verifies album creation, linking photos, and stats."""
        photos = get_photos(limit=3, offset=0)
        if not photos:
            self.skipTest("No photos in database.")

        album_name = "Enterprise Test Album"
        album_id = create_album(album_name)
        if album_id is None:
            all_albums = get_albums()
            for a in all_albums:
                if a["name"] == album_name:
                    album_id = a["id"]
                    break

        self.assertIsNotNone(album_id)
        p_ids = [p["id"] for p in photos]
        add_photos_to_album(album_id, p_ids)

        albums = get_albums()
        matching = [a for a in albums if a["id"] == album_id]
        self.assertTrue(len(matching) > 0)
        self.assertGreaterEqual(matching[0]["photo_count"], len(p_ids))

    def test_ai_semantic_search_mocked(self):
        """Tests semantic search ranking with mocked CLIP model without downloading weights."""
        from backend.routes import search_photos

        # Create mock 512-dim normalized query vector
        dummy_query_vec = np.ones(512, dtype=np.float32)
        dummy_query_vec /= np.linalg.norm(dummy_query_vec)

        # Create mock embeddings matrix for 2 photos
        dummy_matrix = np.vstack([dummy_query_vec, -dummy_query_vec])
        photo_ids = [101, 102]

        with patch("backend.routes.ai_engine.encode_text_query", return_value=dummy_query_vec), \
             patch("backend.routes.get_all_embeddings", return_value=(photo_ids, dummy_matrix)), \
             patch("backend.routes.get_photos", return_value=[{"id": 101, "filename": "beach.jpg"}]):
            res = search_photos(q="beach sunset", limit=10)
            self.assertEqual(res["mode"], "semantic")
            self.assertEqual(res["count"], 1)
            self.assertEqual(res["photos"][0]["id"], 101)

    def test_routes_api(self):
        """Tests REST API handler functions directly with Pydantic schemas."""
        from backend.routes import (
            DeletePhotosRequest,
            RestorePhotosRequest,
            api_delete_photos,
            api_get_trash,
            api_restore_photos,
        )

        photos = get_photos(limit=1, offset=0)
        if not photos:
            self.skipTest("No photos in database.")

        test_id = photos[0]["id"]

        # Delete via API route
        del_resp = api_delete_photos(DeletePhotosRequest(photo_ids=[test_id]))
        self.assertTrue(del_resp["success"])
        self.assertEqual(del_resp["deleted_count"], 1)
        self.assertIn(test_id, del_resp["photo_ids"])

        # Check Trash via API route
        trash_resp = api_get_trash(limit=10)
        trash_ids = [p["id"] for p in trash_resp["photos"]]
        self.assertIn(test_id, trash_ids)

        # Restore via API route
        res_resp = api_restore_photos(RestorePhotosRequest(photo_ids=[test_id]))
        self.assertTrue(res_resp["success"])
        self.assertEqual(res_resp["restored_count"], 1)

    def test_scanner_status_endpoint(self):
        """Verifies scanner status and HTTP fallback endpoint."""
        from backend.routes import get_ws_status_http, scan_status
        status = get_ws_status_http()
        self.assertIsInstance(status, dict)
        self.assertIn("status", status)
        self.assertIn("percent", status)
        self.assertEqual(status, scan_status())

    def test_deduplicate_library_execution(self):
        """Verifies deduplicate_library executes cleanly without variable reference errors."""
        from backend.database import deduplicate_library
        res = deduplicate_library()
        self.assertIsInstance(res, dict)
        self.assertIn("cleaned_duplicates", res)
        self.assertIn("mapped_albums", res)

    def test_favorites_system_and_routes(self):
        """Verifies favorite toggling, batch favoriting, count, and filtering."""
        from backend.database import (
            toggle_photo_favorite,
            set_photos_favorite,
            get_favorites_count,
        )
        from backend.routes import (
            BatchFavoriteRequest,
            api_toggle_favorite,
            api_batch_favorite,
            api_get_favorites_count,
        )

        photos = get_photos(limit=2, offset=0)
        if not photos:
            self.skipTest("No photos in database.")

        test_id = photos[0]["id"]

        # Ensure known starting state (unfavorited)
        set_photos_favorite([test_id], is_favorite=False)
        self.assertFalse(get_photo_by_id(test_id)["is_favorite"])

        # Toggle to favorite
        new_status = toggle_photo_favorite(test_id)
        self.assertTrue(new_status)
        self.assertTrue(get_photo_by_id(test_id)["is_favorite"])

        # Count should be at least 1
        self.assertGreaterEqual(get_favorites_count(), 1)

        # Filter should include this photo
        fav_photos = get_photos(is_favorite=True, limit=50)
        fav_ids = [p["id"] for p in fav_photos]
        self.assertIn(test_id, fav_ids)

        # Test API endpoints
        # Toggle back via route
        toggle_res = api_toggle_favorite(test_id)
        self.assertTrue(toggle_res["success"])
        self.assertFalse(toggle_res["is_favorite"])

        # Batch set via route
        batch_res = api_batch_favorite(BatchFavoriteRequest(photo_ids=[test_id], is_favorite=True))
        self.assertTrue(batch_res["success"])
        self.assertEqual(batch_res["updated_count"], 1)
        self.assertTrue(get_photo_by_id(test_id)["is_favorite"])

        # API count check
        count_res = api_get_favorites_count()
        self.assertGreaterEqual(count_res["total"], 1)

        # Clean up
        set_photos_favorite([test_id], is_favorite=False)

    def test_media_streaming_and_ranges(self):
        """Verifies full media streaming and RFC-compliant HTTP 206 Range requests."""
        photos = get_photos(limit=5, offset=0)
        videos = [p for p in photos if p["media_type"] == "video"]
        if not videos:
            self.skipTest("No video available for streaming test.")
        vid = videos[0]

        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                # 1. Full content request
                resp1 = await client.get(f"/api/media/{vid['id']}")
                self.assertEqual(resp1.status_code, 200)
                self.assertEqual(resp1.headers.get("accept-ranges"), "bytes")
                self.assertIn("video/", resp1.headers.get("content-type", ""))

                # 2. Sub-range request (bytes=0-1023)
                resp2 = await client.get(f"/api/media/{vid['id']}", headers={"Range": "bytes=0-1023"})
                self.assertEqual(resp2.status_code, 206)
                self.assertIn("bytes 0-1023/", resp2.headers.get("content-range", ""))
                self.assertEqual(resp2.headers.get("content-length"), "1024")
                self.assertEqual(len(resp2.content), 1024)

                # 3. Open-ended range request (bytes=100-)
                resp3 = await client.get(f"/api/media/{vid['id']}", headers={"Range": "bytes=100-"})
                self.assertEqual(resp3.status_code, 206)
                self.assertIn("bytes 100-", resp3.headers.get("content-range", ""))

                # 4. Out-of-bounds range request
                resp4 = await client.get(f"/api/media/{vid['id']}", headers={"Range": "bytes=9999999999-99999999999"})
                self.assertEqual(resp4.status_code, 416)
        asyncio.run(_run())

    def test_media_open_local(self):
        """Verifies the open-local endpoint triggers desktop system launcher."""
        photos = get_photos(limit=1, offset=0)
        if not photos:
            self.skipTest("No photo found.")
        pid = photos[0]["id"]

        with patch.object(Path, "is_file", return_value=True), patch("os.startfile", return_value=None) as mock_start:
            async def _run():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post(f"/api/media/{pid}/open-local")
                    self.assertEqual(resp.status_code, 200)
                    self.assertTrue(resp.json().get("success"))
                    mock_start.assert_called_once()
            asyncio.run(_run())

    def test_media_download_content_disposition(self):
        """Verifies ?download=1 query parameter adds Content-Disposition: attachment header."""
        import tempfile
        from PIL import Image
        from backend.scanner import index_single_media_file

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "test_download_photo.jpg"
            img = Image.new("RGB", (100, 100), color=(120, 180, 240))
            img.save(tmp_path, "JPEG")

            photo_id = index_single_media_file(tmp_path)
            self.assertIsNotNone(photo_id)

            async def _run():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    # 1. With download=1
                    resp_dl = await client.get(f"/api/media/{photo_id}?download=1")
                    self.assertEqual(resp_dl.status_code, 200)
                    cd = resp_dl.headers.get("content-disposition", "")
                    self.assertIn("attachment", cd)
                    self.assertIn("test_download_photo.jpg", cd)

                    # 2. Normal viewing without download parameter
                    resp_view = await client.get(f"/api/media/{photo_id}")
                    self.assertEqual(resp_view.status_code, 200)
                    cd_view = resp_view.headers.get("content-disposition", "")
                    self.assertNotIn("attachment", cd_view)

            asyncio.run(_run())

    def test_memories_endpoint(self):
        """Verifies the /api/memories endpoint returns structured On This Day groups."""
        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/memories?month=1&day=1&year=2026")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertIn("target_date", data)
                self.assertIn("groups", data)
                self.assertIsInstance(data["groups"], list)
        asyncio.run(_run())

    def test_geo_backfill_endpoint(self):
        """Verifies the /api/geo/backfill endpoint responds cleanly."""
        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/geo/backfill?batch_size=10")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertTrue(data.get("success"))
                self.assertIn("updated_count", data)
        asyncio.run(_run())

    def test_duplicates_endpoint(self):
        """Verifies the /api/duplicates endpoint returns duplicate groups and savable metrics."""
        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/duplicates?limit_groups=10")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertIn("total_groups", data)
                self.assertIn("potential_savings_bytes", data)
                self.assertIn("groups", data)
        asyncio.run(_run())

    def test_motion_photo_endpoint_not_found(self):
        """Verifies that non-motion photos return 404 on /api/media/{id}/motion."""
        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/media/99999999/motion")
                self.assertEqual(resp.status_code, 404)
        asyncio.run(_run())

    def test_pwa_static_assets(self):
        """Verifies that manifest.webmanifest and sw.js are served correctly."""
        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                manifest_resp = await client.get("/manifest.webmanifest")
                self.assertEqual(manifest_resp.status_code, 200)
                self.assertIn("Google Photos", manifest_resp.text)

                sw_resp = await client.get("/sw.js")
                self.assertEqual(sw_resp.status_code, 200)
                self.assertIn("self.addEventListener", sw_resp.text)
        asyncio.run(_run())

    def test_duplicates_cleanup_endpoint(self):
        """Verifies duplicate cleanup endpoint rejects empty or processes soft-deletes."""
        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/duplicates/cleanup", json={"photo_ids": []})
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.json().get("success"))
        asyncio.run(_run())

    def test_photo_editor_api(self):
        """Verifies photo editing pipeline: adjustments, rotation, flip, and non-destructive saving."""
        import tempfile
        from pathlib import Path
        from PIL import Image
        from backend.scanner import index_single_media_file

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "test_photo_edit.jpg"
            img = Image.new("RGB", (200, 200), color=(100, 150, 200))
            img.save(tmp_path, "JPEG")

            photo_id = index_single_media_file(tmp_path)
            self.assertIsNotNone(photo_id)

            async def _run():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    # Test save as copy
                    payload = {
                        "rotate": 90,
                        "flip_h": True,
                        "brightness": 20,
                        "contrast": 10,
                        "saturation": 15,
                        "warmth": 25,
                        "auto_enhance": True,
                        "save_as_copy": True,
                    }
                    resp = await client.post(f"/api/photos/{photo_id}/edit", json=payload)
                    self.assertEqual(resp.status_code, 200)
                    data = resp.json()
                    self.assertEqual(data.get("status"), "success")
                    self.assertTrue(data.get("is_copy"))
                    new_id = data.get("photo_id")
                    self.assertNotEqual(new_id, photo_id)

                    # Test overwrite edit
                    overwrite_payload = {
                        "rotate": 0,
                        "flip_h": False,
                        "brightness": -10,
                        "contrast": 5,
                        "save_as_copy": False,
                    }
                    resp_ow = await client.post(f"/api/photos/{photo_id}/edit", json=overwrite_payload)
                    self.assertEqual(resp_ow.status_code, 200)
                    self.assertEqual(resp_ow.json().get("photo_id"), photo_id)

            asyncio.run(_run())

    def test_hot_folder_watcher(self):
        """Verifies HotFolderWatcher startup, filtering logic, and clean shutdown."""
        import tempfile
        from pathlib import Path
        from backend.watcher import HotFolderWatcher, MediaWatcherHandler

        handler = MediaWatcherHandler()
        # Test hidden file rejection
        self.assertFalse(handler._should_process(".hidden_photo.jpg"))
        # Test non-media extension rejection
        self.assertFalse(handler._should_process("document.pdf"))
        # Test valid media extension acceptance
        self.assertTrue(handler._should_process("holiday.jpg"))
        # Test debounce logic within 3s
        self.assertFalse(handler._should_process("holiday.jpg"))

        with tempfile.TemporaryDirectory() as tmp_dir:
            watcher = HotFolderWatcher(watch_dir=Path(tmp_dir))
            watcher.start()
            self.assertTrue(watcher._is_running)
            watcher.stop()
            self.assertFalse(watcher._is_running)

    def test_network_info_and_qr_code(self):
        """Verifies LAN IP detection and standalone SVG QR code generation."""
        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/system/network")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertIn("local_ip", data)
                self.assertIn("port", data)
                self.assertIn("lan_url", data)
                self.assertIn("qr_code_svg", data)
                self.assertTrue(data["qr_code_svg"].startswith("<svg") or "<svg" in data["qr_code_svg"])
                self.assertIn(str(data["port"]), data["lan_url"])
        asyncio.run(_run())

    def test_locked_folder_lifecycle(self):
        """Tests PIN setup, verification, locking/unlocking photos, and token authorization."""
        # Reset PIN state for clean test isolation
        with get_db_connection() as conn:
            conn.execute("DELETE FROM security_settings WHERE key = 'locked_folder_pin';")
            conn.commit()

        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                # 1. Status check
                resp = await client.get("/api/locked/status")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertFalse(data.get("has_pin"))
                self.assertIn("locked_count", data)

                # 2. Setup PIN (Reject invalid PINs)
                resp_bad = await client.post("/api/locked/setup-pin", json={"pin": "123"})
                self.assertIn(resp_bad.status_code, [400, 422])
                resp_letters = await client.post("/api/locked/setup-pin", json={"pin": "abcd"})
                self.assertIn(resp_letters.status_code, [400, 422])

                # Setup valid 4-digit PIN
                resp_ok = await client.post("/api/locked/setup-pin", json={"pin": "7890"})
                self.assertEqual(resp_ok.status_code, 200)
                self.assertTrue(resp_ok.json().get("success"))

                # 3. Verify PIN
                resp_wrong = await client.post("/api/locked/verify-pin", json={"pin": "0000"})
                self.assertEqual(resp_wrong.status_code, 401)

                resp_verify = await client.post("/api/locked/verify-pin", json={"pin": "7890"})
                self.assertEqual(resp_verify.status_code, 200)
                token = resp_verify.json().get("token")
                self.assertIsNotNone(token)
                self.assertTrue(len(token) > 10)

                # 4. Lock a photo if one exists
                photos = get_photos(limit=1, is_locked=False)
                if photos:
                    p_id = photos[0]["id"]
                    lock_resp = await client.post("/api/photos/lock", json={"photo_ids": [p_id]})
                    self.assertEqual(lock_resp.status_code, 200)
                    self.assertTrue(lock_resp.json().get("success"))

                    # Access locked photos without token -> 401
                    resp_no_token = await client.get("/api/locked/photos")
                    self.assertEqual(resp_no_token.status_code, 401)

                    # Access locked photos with valid token -> 200
                    resp_locked = await client.get(f"/api/locked/photos?token={token}")
                    self.assertEqual(resp_locked.status_code, 200)
                    locked_ids = [p["id"] for p in resp_locked.json().get("photos", [])]
                    self.assertIn(p_id, locked_ids)

                    # Verify photo is excluded from regular get_photos
                    regular_photos = get_photos(limit=50, is_locked=False)
                    self.assertNotIn(p_id, [p["id"] for p in regular_photos])

                    # Unlock photo (requires token)
                    unlock_resp = await client.post("/api/photos/unlock", json={"photo_ids": [p_id], "token": token})
                    self.assertEqual(unlock_resp.status_code, 200)
                    self.assertTrue(unlock_resp.json().get("success"))

                    # Verify photo returns to regular photos
                    restored_photos = get_photos(limit=50, is_locked=False)
                    self.assertIn(p_id, [p["id"] for p in restored_photos])

        asyncio.run(_run())

    def test_ocr_engine_and_endpoint(self):
        """Tests OCR text extraction engine and HTTP endpoints."""
        import tempfile
        from PIL import Image, ImageDraw
        from backend.ocr_engine import extract_ocr_text

        # Create temporary synthetic test image with clean text
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            img = Image.new("RGB", (400, 100), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((20, 35), "GOOGLE PHOTOS LOCAL OCR", fill=(0, 0, 0))
            img.save(tmp_path)

            text = extract_ocr_text(tmp_path)
            self.assertIn("PHOTOS", text.upper())
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        # Test endpoint with existing photo
        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                photos = get_photos(limit=1, media_type="image")
                if photos:
                    p_id = photos[0]["id"]
                    resp = await client.get(f"/api/photos/{p_id}/ocr")
                    self.assertEqual(resp.status_code, 200)
                    self.assertIn("ocr_text", resp.json())
        asyncio.run(_run())

    def test_direct_upload_and_zip_and_metadata(self):
        """Tests file upload via /api/upload, ZIP packaging via /api/photos/download-zip, and metadata editing."""
        import io
        import zipfile
        from PIL import Image

        # 1. Create a tiny test image in memory
        img_byte_arr = io.BytesIO()
        test_img = Image.new("RGB", (64, 64), color=(73, 109, 137))
        test_img.save(img_byte_arr, format="PNG")
        raw_bytes = img_byte_arr.getvalue()

        async def _run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                # Test direct upload
                files = [
                    ("files", ("antigravity_test_upload.png", raw_bytes, "image/png"))
                ]
                upload_resp = await client.post("/api/upload", files=files)
                self.assertEqual(upload_resp.status_code, 200)
                upload_data = upload_resp.json()
                self.assertTrue(upload_data.get("success"))
                self.assertGreaterEqual(upload_data.get("count"), 1)
                uploaded_photo = upload_data["uploaded"][0]
                p_id = uploaded_photo["id"]

                try:
                    # Test manual metadata editing
                    meta_payload = {
                        "taken_at": "2023-08-17 09:30:00",
                        "latitude": -6.2088,
                        "longitude": 106.8456,
                        "description": "Test Merdeka Landmark",
                    }
                    meta_resp = await client.post(f"/api/photos/{p_id}/metadata", json=meta_payload)
                    self.assertEqual(meta_resp.status_code, 200)
                    meta_data = meta_resp.json()
                    self.assertTrue(meta_data.get("success"))
                    self.assertEqual(meta_data["photo"]["taken_year"], 2023)
                    self.assertEqual(meta_data["photo"]["taken_month"], 8)
                    self.assertEqual(meta_data["photo"]["description"], "Test Merdeka Landmark")
                    self.assertEqual(meta_data["photo"]["has_geo"], 1)

                    # Test ZIP download
                    zip_req = {
                        "photo_ids": [p_id],
                        "archive_name": "test_bundle.zip"
                    }
                    zip_resp = await client.post("/api/photos/download-zip", json=zip_req)
                    self.assertEqual(zip_resp.status_code, 200)
                    self.assertEqual(zip_resp.headers.get("content-type"), "application/zip")
                    self.assertIn("test_bundle.zip", zip_resp.headers.get("content-disposition", ""))

                    # Verify zip content structure
                    zip_in_mem = io.BytesIO(zip_resp.content)
                    with zipfile.ZipFile(zip_in_mem, "r") as zf:
                        namelist = zf.namelist()
                        self.assertEqual(len(namelist), 1)

                finally:
                    # Clean up database and file
                    delete_photos_from_disk_and_db([p_id])

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()

