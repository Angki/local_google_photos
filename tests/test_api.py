import unittest
from backend.config import is_target_folder
from backend.database import (
    add_photos_to_album,
    create_album,
    delete_photos,
    get_albums,
    get_deleted_photos,
    get_library_stats,
    get_photo_by_id,
    get_photos,
    get_timeline_hierarchy,
    init_db,
    restore_photos,
)


class TestGooglePhotosTakeout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

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

        album_name = "Test Unit Album"
        album_id = create_album(album_name)
        if album_id is None:
            # Already exists from previous run, find it
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

    def test_routes_api(self):
        """Tests REST API handler functions directly."""
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


if __name__ == "__main__":
    unittest.main()
