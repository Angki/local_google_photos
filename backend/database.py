# ==============================================================================
# File: backend/database.py
# Description: SQLite database manager, schema definitions, indexes,
#              and vector storage for fast Google Photos queries.
#
# CHANGELOG:
# 2026-09-05 - Initial creation: Added WAL mode, high-speed timeline indexes,
#              BLOB vector embeddings, and flexible filtering helpers.
# ==============================================================================

import contextlib
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from backend.config import APP_ROOT, DATABASE_PATH

logger = logging.getLogger("Database")


@contextlib.contextmanager
def get_db_connection():
    """Context manager yielding an optimized SQLite connection with automatic close and commit."""
    conn = sqlite3.connect(str(DATABASE_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Database Schema Migrations List
MIGRATIONS = [
    (1, "Core schema: photos, photo_embeddings, albums, and album_photos", [
        """
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            folder_year TEXT NOT NULL,
            file_size INTEGER NOT NULL DEFAULT 0,
            media_type TEXT NOT NULL DEFAULT 'image',
            mime_type TEXT,
            width INTEGER DEFAULT 0,
            height INTEGER DEFAULT 0,
            taken_at INTEGER NOT NULL,
            taken_year INTEGER NOT NULL,
            taken_month INTEGER NOT NULL,
            taken_day INTEGER NOT NULL,
            taken_formatted TEXT,
            latitude REAL,
            longitude REAL,
            altitude REAL,
            has_geo BOOLEAN DEFAULT 0,
            description TEXT,
            people TEXT,
            device_folder TEXT,
            app_source TEXT,
            google_url TEXT,
            ai_category TEXT,
            ai_confidence REAL DEFAULT 0.0,
            ai_tags TEXT,
            ai_processed BOOLEAN DEFAULT 0,
            thumbnail_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted BOOLEAN DEFAULT 0
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS photo_embeddings (
            photo_id INTEGER PRIMARY KEY REFERENCES photos(id) ON DELETE CASCADE,
            embedding BLOB NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS album_photos (
            album_id INTEGER REFERENCES albums(id) ON DELETE CASCADE,
            photo_id INTEGER REFERENCES photos(id) ON DELETE CASCADE,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (album_id, photo_id)
        );
        """,
    ]),
    (2, "Performance and query optimization indexes", [
        "CREATE INDEX IF NOT EXISTS idx_photos_taken_at ON photos(taken_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_photos_timeline ON photos(taken_year DESC, taken_month DESC, taken_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_photos_category ON photos(ai_category);",
        "CREATE INDEX IF NOT EXISTS idx_photos_media_type ON photos(media_type);",
        "CREATE INDEX IF NOT EXISTS idx_photos_ai_processed ON photos(ai_processed);",
        "CREATE INDEX IF NOT EXISTS idx_photos_geo ON photos(has_geo, deleted, latitude, longitude);",
        "CREATE INDEX IF NOT EXISTS idx_photos_deleted ON photos(deleted);",
        "CREATE INDEX IF NOT EXISTS idx_photos_filename_size ON photos(filename, file_size);",
    ]),
]


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Applies pending schema migrations transactionally."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT NOT NULL
        );
    """)
    applied_versions = {
        row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }

    for version, description, statements in MIGRATIONS:
        if version not in applied_versions:
            logger.info(f"Applying migration v{version}: {description}")
            for stmt in statements:
                conn.execute(stmt)
            conn.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (?, ?);",
                (version, description),
            )
            logger.info(f"Migration v{version} applied successfully.")

    # Backward compatibility safeguard: ensure deleted column exists on legacy schemas
    try:
        conn.execute("ALTER TABLE photos ADD COLUMN deleted BOOLEAN DEFAULT 0;")
    except sqlite3.OperationalError:
        pass


def init_db() -> None:
    """Creates database tables and applies migrations if they do not exist."""
    with get_db_connection() as conn:
        apply_migrations(conn)

    # Run automatic deduplication on startup
    try:
        deduplicate_library()
    except Exception as e:
        logger.error(f"Error running initial deduplication: {e}")


def upsert_photo(item: Dict[str, Any]) -> int:
    """Inserts or updates photo record in SQLite. Returns photo ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO photos (
            file_path, filename, folder_year, file_size, media_type, mime_type,
            width, height, taken_at, taken_year, taken_month, taken_day, taken_formatted,
            latitude, longitude, altitude, has_geo, description, people,
            device_folder, app_source, google_url
        ) VALUES (
            :file_path, :filename, :folder_year, :file_size, :media_type, :mime_type,
            :width, :height, :taken_at, :taken_year, :taken_month, :taken_day, :taken_formatted,
            :latitude, :longitude, :altitude, :has_geo, :description, :people,
            :device_folder, :app_source, :google_url
        )
        ON CONFLICT(file_path) DO UPDATE SET
            filename = excluded.filename,
            folder_year = excluded.folder_year,
            file_size = excluded.file_size,
            taken_at = excluded.taken_at,
            taken_year = excluded.taken_year,
            taken_month = excluded.taken_month,
            taken_day = excluded.taken_day,
            taken_formatted = excluded.taken_formatted,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            altitude = excluded.altitude,
            has_geo = excluded.has_geo,
            description = excluded.description,
            people = excluded.people,
            device_folder = excluded.device_folder,
            app_source = excluded.app_source,
            google_url = excluded.google_url
        RETURNING id;
        """, item)
        row = cursor.fetchone()
        conn.commit()
        return row[0] if row else 0


def update_thumbnail_path(photo_id: int, thumb_path: str, width: int = 0, height: int = 0) -> None:
    """Updates thumbnail path and dimensions."""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE photos
            SET thumbnail_path = ?,
                width = CASE WHEN ? > 0 THEN ? ELSE width END,
                height = CASE WHEN ? > 0 THEN ? ELSE height END
            WHERE id = ?;
        """, (thumb_path, width, width, height, height, photo_id))
        conn.commit()


def save_ai_results(
    photo_id: int,
    category: str,
    confidence: float,
    tags: List[str],
    embedding_bytes: Optional[bytes] = None
) -> None:
    """Saves AI detected category, tags, and embedding vector."""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE photos
            SET ai_category = ?,
                ai_confidence = ?,
                ai_tags = ?,
                ai_processed = 1
            WHERE id = ?;
        """, (category, confidence, json.dumps(tags), photo_id))

        if embedding_bytes:
            conn.execute("""
                INSERT INTO photo_embeddings (photo_id, embedding)
                VALUES (?, ?)
                ON CONFLICT(photo_id) DO UPDATE SET embedding = excluded.embedding;
            """, (photo_id, embedding_bytes))
        conn.commit()


def get_timeline_hierarchy() -> List[Dict[str, Any]]:
    """
    Returns Year and Month timeline hierarchy with photo counts and latest cover photo ID.
    Example:
    [
      {
        "year": 2026,
        "total": 3800,
        "months": [
          {"month": 9, "month_name": "September", "count": 120, "cover_id": 142},
          {"month": 8, "month_name": "August", "count": 450, "cover_id": 98}
        ]
      }
    ]
    """
    import calendar
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT taken_year, taken_month, COUNT(*) as count, MAX(id) as cover_id
            FROM photos
            WHERE deleted = 0
            GROUP BY taken_year, taken_month
            ORDER BY taken_year DESC, taken_month DESC;
        """).fetchall()

    year_map: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        y, m, count, cover_id = r["taken_year"], r["taken_month"], r["count"], r["cover_id"]
        if y not in year_map:
            year_map[y] = {"year": y, "total": 0, "months": []}
        year_map[y]["total"] += count
        month_name = calendar.month_name[m] if 1 <= m <= 12 else f"Month {m}"
        year_map[y]["months"].append({
            "month": m,
            "month_name": month_name,
            "count": count,
            "cover_id": cover_id
        })

    return list(year_map.values())


def get_photos(
    year: Optional[int] = None,
    month: Optional[int] = None,
    category: Optional[str] = None,
    media_type: Optional[str] = None,
    has_geo: Optional[bool] = None,
    search_text: Optional[str] = None,
    photo_ids: Optional[List[int]] = None,
    album_id: Optional[int] = None,
    limit: int = 80,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Fetches paginated photo records based on filters."""
    conditions = ["deleted = 0"]
    params: List[Any] = []

    if album_id is not None:
        conditions.append("id IN (SELECT photo_id FROM album_photos WHERE album_id = ?)")
        params.append(album_id)


    if photo_ids is not None:
        if not photo_ids:
            return []
        placeholders = ",".join("?" for _ in photo_ids)
        conditions.append(f"id IN ({placeholders})")
        params.extend(photo_ids)

    if year is not None:
        conditions.append("taken_year = ?")
        params.append(year)

    if month is not None:
        conditions.append("taken_month = ?")
        params.append(month)

    if category and category.lower() != "all":
        conditions.append("ai_category = ?")
        params.append(category.lower())

    if media_type and media_type.lower() != "all":
        conditions.append("media_type = ?")
        params.append(media_type.lower())

    if has_geo is not None:
        conditions.append("has_geo = ?")
        params.append(1 if has_geo else 0)

    if search_text:
        term = f"%{search_text.strip()}%"
        conditions.append("(filename LIKE ? OR description LIKE ? OR people LIKE ? OR ai_tags LIKE ? OR ai_category LIKE ?)")
        params.extend([term, term, term, term, term])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_clause = "ORDER BY taken_at DESC, id DESC"

    query = f"""
        SELECT id, file_path, filename, folder_year, file_size, media_type,
               width, height, taken_at, taken_year, taken_month, taken_day,
               taken_formatted, latitude, longitude, has_geo, description,
               people, device_folder, app_source, ai_category, ai_confidence,
               ai_tags, thumbnail_path
        FROM photos
        {where_clause}
        {order_clause}
        LIMIT ? OFFSET ?;
    """
    lim = int(limit) if type(limit) in (int, str, float) else 80
    off = int(offset) if type(offset) in (int, str, float) else 0
    params.extend([lim, off])

    with get_db_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Parse JSON fields safely
            try:
                d["people"] = json.loads(d["people"]) if d.get("people") else []
            except Exception:
                d["people"] = []
            try:
                d["ai_tags"] = json.loads(d["ai_tags"]) if d.get("ai_tags") else []
            except Exception:
                d["ai_tags"] = []
            result.append(d)
        return result


def get_photo_by_id(photo_id: int, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
    """Fetches single photo record with parsed JSON people and ai_tags."""
    with get_db_connection() as conn:
        query = "SELECT * FROM photos WHERE id = ?"
        params: List[Any] = [photo_id]
        if not include_deleted:
            query += " AND deleted = 0"
        row = conn.execute(query + ";", params).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["people"] = json.loads(d["people"]) if d.get("people") else []
        except Exception:
            d["people"] = []
        try:
            d["ai_tags"] = json.loads(d["ai_tags"]) if d.get("ai_tags") else []
        except Exception:
            d["ai_tags"] = []
        return d


def get_category_counts() -> List[Dict[str, Any]]:
    """Returns counts of photos per AI category."""
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT ai_category as category, COUNT(*) as count
            FROM photos
            WHERE deleted = 0 AND ai_category IS NOT NULL AND ai_category != ''
            GROUP BY ai_category
            ORDER BY count DESC;
        """).fetchall()
        return [dict(r) for r in rows]


def get_library_stats() -> Dict[str, Any]:
    """Returns overall library statistics."""
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total_media,
                COALESCE(SUM(CASE WHEN media_type = 'image' THEN 1 ELSE 0 END), 0) as total_images,
                COALESCE(SUM(CASE WHEN media_type = 'video' THEN 1 ELSE 0 END), 0) as total_videos,
                COALESCE(SUM(CASE WHEN has_geo = 1 THEN 1 ELSE 0 END), 0) as total_geo,
                COALESCE(SUM(CASE WHEN thumbnail_path IS NOT NULL AND thumbnail_path != '' THEN 1 ELSE 0 END), 0) as total_thumbnails,
                COALESCE(SUM(CASE WHEN ai_processed = 1 THEN 1 ELSE 0 END), 0) as total_ai_processed,
                COALESCE(SUM(file_size), 0) as total_bytes
            FROM photos
            WHERE deleted = 0;
        """).fetchone()
        return dict(row) if row else {}


def get_geo_points() -> List[Dict[str, Any]]:
    """Returns essential coordinates and metadata for all active geotagged photos."""
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT id, filename, latitude, longitude, altitude, taken_formatted, taken_at, media_type
            FROM photos
            WHERE has_geo = 1 AND deleted = 0 AND latitude IS NOT NULL AND longitude IS NOT NULL
            ORDER BY taken_at DESC;
        """).fetchall()
        return [dict(r) for r in rows]


def get_all_embeddings() -> Tuple[List[int], np.ndarray]:
    """
    Loads all stored vector embeddings from SQLite into memory for fast cosine search.
    Returns: (photo_ids, np.ndarray of shape (N, 512))
    """
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT pe.photo_id, pe.embedding
            FROM photo_embeddings pe
            JOIN photos p ON pe.photo_id = p.id
            WHERE p.deleted = 0;
        """).fetchall()
        if not rows:
            return [], np.empty((0, 512), dtype=np.float32)

        photo_ids = []
        vectors = []
        for r in rows:
            p_id = r["photo_id"]
            blob = r["embedding"]
            vec = np.frombuffer(blob, dtype=np.float32)
            if vec.shape[0] == 512:
                photo_ids.append(p_id)
                vectors.append(vec)

        if not vectors:
            return [], np.empty((0, 512), dtype=np.float32)

        matrix = np.vstack(vectors)
        return photo_ids, matrix


def get_unprocessed_photos_for_thumbnails(limit: int = 200) -> List[Dict[str, Any]]:
    """Returns photos needing thumbnail generation."""
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT id, file_path, media_type
            FROM photos
            WHERE thumbnail_path IS NULL OR thumbnail_path = ''
            LIMIT ?;
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_unprocessed_photos_for_ai(limit: int = 100) -> List[Dict[str, Any]]:
    """Returns image photos needing AI classification and embedding."""
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT id, file_path, thumbnail_path
            FROM photos
            WHERE ai_processed = 0 AND media_type = 'image' AND deleted = 0
            LIMIT ?;
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_albums() -> List[Dict[str, Any]]:
    """Fetches all albums and their active photo counts."""
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT a.id, a.name, a.created_at, COUNT(p.id) as photo_count
            FROM albums a
            LEFT JOIN album_photos ap ON a.id = ap.album_id
            LEFT JOIN photos p ON ap.photo_id = p.id AND p.deleted = 0
            GROUP BY a.id
            ORDER BY a.name ASC;
        """).fetchall()
        return [dict(r) for r in rows]


def get_or_create_album(name: str) -> int:
    """Gets existing album ID or creates a new album and returns its ID."""
    clean_name = name.strip()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT id FROM albums WHERE name = ?", (clean_name,)).fetchone()
        if row:
            return row["id"]
        cursor.execute("INSERT INTO albums (name) VALUES (?)", (clean_name,))
        conn.commit()
        return cursor.lastrowid


def create_album(name: str) -> Optional[int]:
    """Creates a new album and returns its ID. If it already exists, returns the existing album's ID."""
    clean_name = name.strip()
    if not clean_name:
        return None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        existing = cursor.execute("SELECT id FROM albums WHERE name = ?", (clean_name,)).fetchone()
        if existing:
            return existing["id"]
        try:
            cursor.execute("INSERT INTO albums (name) VALUES (?)", (clean_name,))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            row = cursor.execute("SELECT id FROM albums WHERE name = ?", (clean_name,)).fetchone()
            return row["id"] if row else None


def add_photos_to_album(album_id: int, photo_ids: List[int]) -> int:
    """Adds multiple photos to an album. Returns number added."""
    if not photo_ids:
        return 0
    added = 0
    with get_db_connection() as conn:
        for pid in photo_ids:
            try:
                conn.execute(
                    "INSERT INTO album_photos (album_id, photo_id) VALUES (?, ?)",
                    (album_id, pid)
                )
                added += 1
            except sqlite3.IntegrityError:
                pass  # Already in album
        conn.commit()
    return added


def delete_photos(photo_ids: List[int]) -> int:
    """Soft deletes multiple photos."""
    if not photo_ids:
        return 0
    placeholders = ",".join("?" for _ in photo_ids)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE photos SET deleted = 1 WHERE id IN ({placeholders})", photo_ids)
        conn.commit()
        return cursor.rowcount


def remove_photos_from_album(album_id: int, photo_ids: List[int]) -> int:
    """Removes multiple photos from an album."""
    if not photo_ids:
        return 0
    placeholders = ",".join("?" for _ in photo_ids)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM album_photos WHERE album_id = ? AND photo_id IN ({placeholders})", [album_id] + photo_ids)
        conn.commit()
        return cursor.rowcount


def delete_album(album_id: int) -> bool:
    """Deletes an album and all its photo links."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM album_photos WHERE album_id = ?", (album_id,))
        cursor.execute("DELETE FROM albums WHERE id = ?", (album_id,))
        conn.commit()
        return cursor.rowcount > 0


def restore_photos(photo_ids: List[int]) -> int:
    """Restores soft-deleted photos back to the active library."""
    if not photo_ids:
        return 0
    placeholders = ",".join("?" for _ in photo_ids)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE photos SET deleted = 0 WHERE id IN ({placeholders})", photo_ids)
        conn.commit()
        return cursor.rowcount


def get_trash_count() -> int:
    """Returns the total number of photos currently in the Trash."""
    with get_db_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as count FROM photos WHERE deleted = 1;").fetchone()
        return row["count"] if row else 0


def get_deleted_photos(limit: int = 80, offset: int = 0) -> List[Dict[str, Any]]:
    """Fetches paginated photos currently in the Trash."""
    lim = int(limit) if type(limit) in (int, str, float) else 80
    off = int(offset) if type(offset) in (int, str, float) else 0
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM photos WHERE deleted = 1 ORDER BY taken_at DESC LIMIT ? OFFSET ?;",
            (lim, off)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["people"] = json.loads(d["people"]) if d.get("people") else []
            except Exception:
                d["people"] = []
            try:
                d["ai_tags"] = json.loads(d["ai_tags"]) if d.get("ai_tags") else []
            except Exception:
                d["ai_tags"] = []
            result.append(d)
        return result


def permanent_delete_photos(photo_ids: List[int]) -> int:
    """Permanently deletes photos from database (metadata, embeddings, album links)."""
    if not photo_ids:
        return 0
    placeholders = ",".join("?" for _ in photo_ids)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM album_photos WHERE photo_id IN ({placeholders})", photo_ids)
        cursor.execute(f"DELETE FROM photo_embeddings WHERE photo_id IN ({placeholders})", photo_ids)
        cursor.execute(f"DELETE FROM photos WHERE id IN ({placeholders})", photo_ids)
        conn.commit()
        return cursor.rowcount


def delete_photos_from_disk_and_db(photo_ids: List[int]) -> Dict[str, Any]:
    """
    Permanently deletes photos:
    1. Physically deletes media files from disk.
    2. Locates and deletes companion Takeout .json metadata files.
    3. Physically deletes generated WebP thumbnails from cache.
    4. Removes database rows (albums, embeddings, photos).
    """
    if not photo_ids:
        return {
            "success": True,
            "deleted_count": 0,
            "media_files_deleted": 0,
            "json_files_deleted": 0,
            "thumbnails_deleted": 0,
            "delete_from_disk": True,
        }

    from backend.metadata_parser import find_metadata_json

    placeholders = ",".join("?" for _ in photo_ids)
    items_to_delete = []

    with get_db_connection() as conn:
        rows = conn.execute(
            f"SELECT id, file_path, thumbnail_path FROM photos WHERE id IN ({placeholders})",
            photo_ids
        ).fetchall()
        for r in rows:
            items_to_delete.append({
                "id": r["id"],
                "file_path": r["file_path"],
                "thumbnail_path": r["thumbnail_path"]
            })

    media_deleted = 0
    json_deleted = 0
    thumbs_deleted = 0

    for item in items_to_delete:
        # 1. Media file & companion JSON
        if item["file_path"]:
            media_p = Path(item["file_path"])
            try:
                json_p = find_metadata_json(media_p)
                if json_p and json_p.is_file():
                    json_p.unlink(missing_ok=True)
                    json_deleted += 1
            except Exception as e:
                logger.warning(f"Error removing companion JSON for {media_p.name}: {e}")

            try:
                if media_p.is_file():
                    media_p.unlink(missing_ok=True)
                    media_deleted += 1
            except Exception as e:
                logger.warning(f"Error removing physical media {media_p.name}: {e}")

        # 2. Thumbnail
        if item["thumbnail_path"]:
            thumb_p = Path(item["thumbnail_path"])
            if not thumb_p.is_absolute():
                thumb_p = APP_ROOT / item["thumbnail_path"]
            try:
                if thumb_p.is_file():
                    thumb_p.unlink(missing_ok=True)
                    thumbs_deleted += 1
            except Exception as e:
                logger.debug(f"Error removing thumbnail {thumb_p.name}: {e}")

    # 3. Database cleanup
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM album_photos WHERE photo_id IN ({placeholders})", photo_ids)
        cursor.execute(f"DELETE FROM photo_embeddings WHERE photo_id IN ({placeholders})", photo_ids)
        cursor.execute(f"DELETE FROM photos WHERE id IN ({placeholders})", photo_ids)
        conn.commit()
        db_count = cursor.rowcount

    logger.info(
        f"Permanently deleted {db_count} database rows, "
        f"{media_deleted} media files, {json_deleted} JSON files, "
        f"{thumbs_deleted} thumbnails."
    )

    return {
        "success": True,
        "deleted_count": db_count,
        "photo_ids": photo_ids,
        "media_files_deleted": media_deleted,
        "json_files_deleted": json_deleted,
        "thumbnails_deleted": thumbs_deleted,
        "delete_from_disk": True,
    }


def find_canonical_photo(filename: str, file_size: int) -> Optional[int]:
    """Finds an existing active photo with matching filename and file size, prioritizing year timeline folders."""
    if not filename or file_size <= 0:
        return None
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT id, folder_year
            FROM photos
            WHERE filename = ? AND file_size = ? AND deleted = 0
            ORDER BY CASE WHEN folder_year LIKE 'Photos from %' THEN 0 ELSE 1 END, id ASC
            LIMIT 1;
        """, (filename, file_size)).fetchall()
        if rows:
            return rows[0]["id"]
        return None


def deduplicate_library() -> Dict[str, int]:
    """
    Identifies and resolves duplicates between Google Takeout Year timeline folders
    and custom album folders (e.g. 'Photos from 2025' vs 'Pedals - Rig').
    Links custom albums to the canonical photo and cleans up duplicate rows in photos table.
    """
    cleaned_rows = 0
    mapped_albums = 0

    with get_db_connection() as conn:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_photos_filename_size ON photos(filename, file_size);")

        cursor = conn.cursor()
        cursor.execute("""
            SELECT filename, file_size, COUNT(*) as cnt
            FROM photos
            WHERE deleted = 0 AND file_size > 0
            GROUP BY filename, file_size
            HAVING COUNT(*) > 1;
        """)
        dup_groups = cursor.fetchall()

        for g in dup_groups:
            fn = g["filename"]
            size = g["file_size"]

            items = conn.execute("""
                SELECT id, folder_year, file_path
                FROM photos
                WHERE filename = ? AND file_size = ? AND deleted = 0
                ORDER BY CASE WHEN folder_year LIKE 'Photos from %' THEN 0 ELSE 1 END, id ASC;
            """, (fn, size)).fetchall()

            if len(items) <= 1:
                continue

            # Prefer canonical item that actually exists on disk
            existing_items = [it for it in items if Path(it["file_path"]).is_file()]
            if existing_items:
                canonical_item = existing_items[0]
                duplicate_items = [it for it in items if it["id"] != canonical_item["id"]]
            else:
                canonical_item = items[0]
                duplicate_items = items[1:]

            canonical_id = canonical_item["id"]

            for dup in duplicate_items:
                dup_id = dup["id"]
                folder_year = dup["folder_year"]

                # If the duplicate is in an album folder, make sure the album links to canonical_id
                if not folder_year.startswith("Photos from "):
                    alb_row = conn.execute("SELECT id FROM albums WHERE name = ?", (folder_year,)).fetchone()
                    if alb_row:
                        alb_id = alb_row["id"]
                    else:
                        c_ins = conn.cursor()
                        c_ins.execute("INSERT INTO albums (name) VALUES (?)", (folder_year,))
                        alb_id = c_ins.lastrowid

                    if alb_id:
                        conn.execute("""
                            INSERT OR IGNORE INTO album_photos (album_id, photo_id)
                            VALUES (?, ?);
                        """, (alb_id, canonical_id))
                        mapped_albums += 1

                # Move any existing album_photos mapping from dup_id to canonical_id
                existing_albs = conn.execute("SELECT album_id FROM album_photos WHERE photo_id = ?", (dup_id,)).fetchall()
                for ea in existing_albs:
                    conn.execute("""
                        INSERT OR IGNORE INTO album_photos (album_id, photo_id)
                        VALUES (?, ?);
                    """, (ea["album_id"], canonical_id))

                # Clean up duplicate photo row
                conn.execute("DELETE FROM album_photos WHERE photo_id = ?", (dup_id,))
                conn.execute("DELETE FROM photo_embeddings WHERE photo_id = ?", (dup_id,))
                conn.execute("DELETE FROM photos WHERE id = ?", (dup_id,))
                cleaned_rows += 1

        conn.commit()

    if cleaned_rows > 0:
        logger.info(f"Deduplication complete: {cleaned_rows} duplicates cleaned, {mapped_albums} album mappings ensured.")
    return {
        "cleaned_duplicates": cleaned_rows,
        "mapped_albums": mapped_albums
    }
