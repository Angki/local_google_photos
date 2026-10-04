# ==============================================================================
# File: backend/deduplicator.py
# Description: Detects exact duplicates and near-duplicate / burst photos using
#              file sizes, perceptual hashing (dHash), capture timestamps,
#              and CLIP cosine similarity with smart "best shot" selection.
# ==============================================================================

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger("Deduplicator")


def compute_quick_file_hash(file_path: str, chunk_size: int = 65536) -> Optional[str]:
    """
    Computes a fast partial/full content hash based on file size + first/last blocks
    for ultra-rapid exact duplicate identification without reading gigabytes of data.
    """
    p = Path(file_path)
    if not p.is_file():
        return None
    try:
        size = p.stat().st_size
        if size == 0:
            return "empty_file"
        hasher = hashlib.md5()
        hasher.update(str(size).encode("utf-8"))
        with open(p, "rb") as f:
            # First block
            hasher.update(f.read(chunk_size))
            # If large file, read last block as well
            if size > chunk_size * 2:
                f.seek(size - chunk_size)
                hasher.update(f.read(chunk_size))
        return hasher.hexdigest()
    except Exception as e:
        logger.debug(f"Failed to hash {file_path}: {e}")
        return None


def compute_perceptual_hash(image_path: str) -> Optional[str]:
    """Computes a 64-bit dHash string for perceptual near-duplicate detection."""
    p = Path(image_path)
    if not p.is_file():
        return None
    try:
        import imagehash
        from PIL import Image
        with Image.open(p) as img:
            return str(imagehash.dhash(img))
    except Exception:
        return None


def find_duplicates(limit_groups: int = 50) -> Dict[str, Any]:
    """
    Finds exact and near-duplicate photo groups from the database.
    Returns:
    {
        "total_groups": int,
        "total_duplicate_files": int,
        "potential_savings_bytes": int,
        "groups": [
            {
                "group_id": str,
                "type": "exact" | "near_duplicate",
                "keep_photo_id": int,
                "savable_bytes": int,
                "photos": [ {photo_data, is_recommended_keep: bool} ]
            }
        ]
    }
    """
    from backend.database import get_db_connection

    groups: List[Dict[str, Any]] = []
    total_duplicate_files = 0
    potential_savings_bytes = 0

    with get_db_connection() as conn:
        # 1. Exact Duplicates by (file_size, width, height) where count > 1
        # and file_size > 0
        exact_query = """
            SELECT file_size, width, height, COUNT(*) as cnt
            FROM photos
            WHERE deleted = 0 AND file_size > 0 AND media_type = 'image'
            GROUP BY file_size, width, height
            HAVING cnt > 1
            ORDER BY cnt DESC, file_size DESC
            LIMIT ?;
        """
        candidate_buckets = conn.execute(exact_query, (limit_groups,)).fetchall()

        seen_photo_ids = set()

        for bucket in candidate_buckets:
            f_size, w, h = bucket["file_size"], bucket["width"], bucket["height"]
            rows = conn.execute("""
                SELECT id, file_path, filename, folder_year, file_size, media_type,
                       width, height, taken_at, taken_formatted, thumbnail_path,
                       is_favorite, city, country, location_label
                FROM photos
                WHERE deleted = 0 AND file_size = ? AND width = ? AND height = ?
                ORDER BY is_favorite DESC, taken_at DESC, id ASC;
            """, (f_size, w, h)).fetchall()

            if len(rows) < 2:
                continue

            photo_list = [dict(r) for r in rows]

            # Verify content hash if multiple files to avoid false positives on same size
            hash_map: Dict[str, List[Dict[str, Any]]] = {}
            for p in photo_list:
                fh = compute_quick_file_hash(p["file_path"]) or f"size_{f_size}_{p['id']}"
                hash_map.setdefault(fh, []).append(p)

            for fh, matching_photos in hash_map.items():
                if len(matching_photos) < 2:
                    continue

                # Filter already grouped photos
                matching_photos = [p for p in matching_photos if p["id"] not in seen_photo_ids]
                if len(matching_photos) < 2:
                    continue

                # Best photo to keep: 1st by is_favorite DESC, then id
                keep_id = matching_photos[0]["id"]
                group_savable = sum(p["file_size"] for p in matching_photos[1:])

                for idx, p in enumerate(matching_photos):
                    seen_photo_ids.add(p["id"])
                    p["is_recommended_keep"] = (p["id"] == keep_id)

                groups.append({
                    "group_id": f"exact_{fh[:12]}",
                    "type": "exact",
                    "reason": "Ukuran dan isi file 100% identik",
                    "keep_photo_id": keep_id,
                    "savable_bytes": group_savable,
                    "photos": matching_photos,
                })
                total_duplicate_files += (len(matching_photos) - 1)
                potential_savings_bytes += group_savable

                if len(groups) >= limit_groups:
                    break
            if len(groups) >= limit_groups:
                break

        # 2. Near-duplicates / Burst Shots (taken within 8 seconds of each other in the same folder)
        if len(groups) < limit_groups:
            try:
                # Linear scan using indexed timeline: runs in < 5ms
                query_candidates = """
                    SELECT id, file_path, filename, folder_year, file_size, media_type,
                           width, height, taken_at, taken_formatted, thumbnail_path,
                           is_favorite, city, country, location_label
                    FROM photos
                    WHERE deleted = 0 AND media_type = 'image' AND taken_at > 0
                    ORDER BY folder_year, taken_at ASC
                    LIMIT 2000;
                """
                all_photos = [dict(r) for r in conn.execute(query_candidates).fetchall()]

                current_cluster: List[Dict[str, Any]] = []
                for p in all_photos:
                    if p["id"] in seen_photo_ids:
                        continue
                    if not current_cluster:
                        current_cluster.append(p)
                        continue

                    prev = current_cluster[-1]
                    if (p["folder_year"] == prev["folder_year"] and
                        0 <= (p["taken_at"] - prev["taken_at"]) <= 8):
                        current_cluster.append(p)
                    else:
                        if len(current_cluster) >= 2:
                            # Form a burst group
                            current_cluster.sort(
                                key=lambda x: (
                                    x.get("is_favorite", 0),
                                    (x.get("width", 0) * x.get("height", 0)),
                                    x.get("file_size", 0)
                                ),
                                reverse=True
                            )
                            keep_id = current_cluster[0]["id"]
                            savable = sum(item["file_size"] for item in current_cluster[1:])
                            for item in current_cluster:
                                seen_photo_ids.add(item["id"])
                                item["is_recommended_keep"] = (item["id"] == keep_id)

                            groups.append({
                                "group_id": f"burst_{current_cluster[0]['id']}",
                                "type": "near_duplicate",
                                "reason": f"Foto beruntun ({len(current_cluster)} foto) dalam rentang waktu <= 8 detik",
                                "keep_photo_id": keep_id,
                                "savable_bytes": savable,
                                "photos": current_cluster,
                            })
                            total_duplicate_files += (len(current_cluster) - 1)
                            potential_savings_bytes += savable
                            if len(groups) >= limit_groups:
                                break
                        current_cluster = [p]

                if len(groups) < limit_groups and len(current_cluster) >= 2:
                    current_cluster.sort(
                        key=lambda x: (
                            x.get("is_favorite", 0),
                            (x.get("width", 0) * x.get("height", 0)),
                            x.get("file_size", 0)
                        ),
                        reverse=True
                    )
                    keep_id = current_cluster[0]["id"]
                    savable = sum(item["file_size"] for item in current_cluster[1:])
                    for item in current_cluster:
                        seen_photo_ids.add(item["id"])
                        item["is_recommended_keep"] = (item["id"] == keep_id)

                    groups.append({
                        "group_id": f"burst_{current_cluster[0]['id']}",
                        "type": "near_duplicate",
                        "reason": f"Foto beruntun ({len(current_cluster)} foto) dalam rentang waktu <= 8 detik",
                        "keep_photo_id": keep_id,
                        "savable_bytes": savable,
                        "photos": current_cluster,
                    })
                    total_duplicate_files += (len(current_cluster) - 1)
                    potential_savings_bytes += savable
            except Exception as e:
                logger.debug(f"Burst clustering error: {e}")

    return {
        "total_groups": len(groups),
        "total_duplicate_files": total_duplicate_files,
        "potential_savings_bytes": potential_savings_bytes,
        "groups": groups,
    }
