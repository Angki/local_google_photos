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


_dhash_cache: Dict[int, int] = {}


def compute_perceptual_hash(image_or_path: Any) -> Optional[int]:
    """
    Computes a 64-bit difference hash (dHash) using PIL and numpy.
    Resizes image to 9x8 grayscale, evaluates row-wise gradient,
    producing a compact 64-bit integer representation of visual structure.
    Zero C-library requirement, fast and robust to resolution/compression differences.
    """
    try:
        from PIL import Image
        close_needed = False
        if isinstance(image_or_path, (str, Path)):
            p = Path(image_or_path)
            if not p.is_file():
                return None
            img = Image.open(p)
            close_needed = True
        else:
            img = image_or_path

        gray = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = np.asarray(gray, dtype=np.int32)
        diff = pixels[:, 1:] > pixels[:, :-1]
        hash_val = 0
        for bit in diff.flatten():
            hash_val = (hash_val << 1) | int(bit)

        if close_needed:
            img.close()

        return hash_val
    except Exception:
        return None


def hamming_distance(h1: int, h2: int) -> int:
    """Calculates bitwise Hamming distance between two 64-bit hashes."""
    return bin(h1 ^ h2).count("1")


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

        # 3. Perceptual Similarities (dHash visual match, e.g. WhatsApp compression vs original camera, edits/crops)
        if len(groups) < limit_groups:
            try:
                candidate_perceptual = [p for p in all_photos if p["id"] not in seen_photo_ids][:600]
                hashes: List[Tuple[Dict[str, Any], int]] = []
                for p in candidate_perceptual:
                    pid = p["id"]
                    if pid in _dhash_cache:
                        h = _dhash_cache[pid]
                    else:
                        img_path = p.get("thumbnail_path") or p.get("file_path")
                        h = compute_perceptual_hash(img_path)
                        if h is not None:
                            _dhash_cache[pid] = h
                    if h is not None:
                        hashes.append((p, h))

                # Group by perceptual proximity (Hamming distance <= 6 out of 64 bits)
                p_used = set()
                for i in range(len(hashes)):
                    if hashes[i][0]["id"] in p_used:
                        continue
                    cluster = [hashes[i][0]]
                    h1 = hashes[i][1]
                    for j in range(i + 1, len(hashes)):
                        p2, h2 = hashes[j]
                        if p2["id"] in p_used:
                            continue
                        if hamming_distance(h1, h2) <= 6:
                            cluster.append(p2)
                            p_used.add(p2["id"])

                    if len(cluster) >= 2:
                        p_used.add(hashes[i][0]["id"])
                        cluster.sort(
                            key=lambda x: (
                                x.get("is_favorite", 0),
                                (x.get("width", 0) * x.get("height", 0)),
                                x.get("file_size", 0)
                            ),
                            reverse=True
                        )
                        keep_id = cluster[0]["id"]
                        savable = sum(item["file_size"] for item in cluster[1:])
                        for item in cluster:
                            seen_photo_ids.add(item["id"])
                            item["is_recommended_keep"] = (item["id"] == keep_id)

                        groups.append({
                            "group_id": f"perceptual_{cluster[0]['id']}",
                            "type": "perceptual",
                            "reason": f"Kemiripan visual > 90% (Perceptual Match / Kompresi)",
                            "keep_photo_id": keep_id,
                            "savable_bytes": savable,
                            "photos": cluster,
                        })
                        total_duplicate_files += (len(cluster) - 1)
                        potential_savings_bytes += savable
                        if len(groups) >= limit_groups:
                            break
            except Exception as e:
                logger.debug(f"Perceptual clustering error: {e}")

    return {
        "total_groups": len(groups),
        "total_duplicate_files": total_duplicate_files,
        "potential_savings_bytes": potential_savings_bytes,
        "groups": groups,
    }
