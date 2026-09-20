# ==============================================================================
# File: scripts/fix_dates_by_filename.py
# Description: Batch updates photo dates in photos.db by parsing filenames for
#              media missing companion JSON metadata, categorizing them into
#              their correct months and defaulting to January 1st for files without dates.
# ==============================================================================

import os
import sys
import sqlite3
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import DATABASE_PATH, YEAR_FOLDER_PATTERN
from backend.metadata_parser import parse_photo_metadata


def fix_dates():
    db_path = DATABASE_PATH
    if not db_path.exists():
        print(f"[!] Database not found at: {db_path}")
        return

    print("=" * 72)
    print("   UPDATING DATES FROM FILENAMES & MONTHLY CATEGORIZATION")
    print("=" * 72)
    print(f"[+] Database: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query all photos in year folders
    cursor.execute("""
        SELECT id, file_path, filename, folder_year, taken_at, taken_year, taken_month, taken_day
        FROM photos
        WHERE folder_year LIKE 'Photos from%'
    """)
    rows = cursor.fetchall()
    print(f"[+] Found {len(rows)} photos in year folders.")

    updated_count = 0
    updates = []

    for r in rows:
        p_id = r["id"]
        file_path_str = r["file_path"]
        media_path = Path(file_path_str)
        folder_match = YEAR_FOLDER_PATTERN.match(r["folder_year"])
        fallback_year = int(folder_match.group(1)) if folder_match else None

        try:
            meta = parse_photo_metadata(media_path, fallback_year=fallback_year)
        except Exception as e:
            continue

        new_year = meta["taken_year"]
        new_month = meta["taken_month"]
        new_day = meta["taken_day"]
        new_at = meta["taken_at"]
        new_formatted = meta["taken_formatted"]

        old_year = r["taken_year"]
        old_month = r["taken_month"]
        old_day = r["taken_day"]
        old_at = r["taken_at"]

        if (new_year != old_year) or (new_month != old_month) or (new_day != old_day) or (abs(new_at - old_at) > 3600):
            updates.append((new_at, new_year, new_month, new_day, new_formatted, p_id))
            updated_count += 1

    print(f"[+] Preparing to update {updated_count} photos...")

    if updates:
        cursor.executemany("""
            UPDATE photos
            SET taken_at = ?,
                taken_year = ?,
                taken_month = ?,
                taken_day = ?,
                taken_formatted = ?
            WHERE id = ?
        """, updates)
        conn.commit()
        print(f"[OK] Successfully updated {updated_count} photos in database.")
    else:
        print("[+] All photos are already up to date.")

    # Show new distribution for targeted years: 2013, 2015, 2020, 2021
    print("\n" + "=" * 72)
    print("   CURRENT MONTHLY DISTRIBUTION (2013, 2015, 2020, 2021)")
    print("=" * 72)
    cursor.execute("""
        SELECT folder_year, taken_year, taken_month, COUNT(*) as count
        FROM photos
        WHERE folder_year IN ('Photos from 2013', 'Photos from 2015', 'Photos from 2020', 'Photos from 2021')
        GROUP BY folder_year, taken_year, taken_month
        ORDER BY folder_year, taken_year, taken_month
    """)
    for row in cursor.fetchall():
        print(f"  {row['folder_year']:18s} | Year: {row['taken_year']} | Month: {row['taken_month']:02d} | Count: {row['count']}")

    # Check if any photos in Photos from 2021 still have taken_year = 2026
    cursor.execute("""
        SELECT COUNT(*) FROM photos
        WHERE folder_year = 'Photos from 2021' AND taken_year = 2026
    """)
    remaining_2026 = cursor.fetchone()[0]
    print(f"\n[+] Remaining 2021 photos in 2026: {remaining_2026} (Target: 0)")
    print("=" * 72)

    conn.close()


if __name__ == "__main__":
    fix_dates()
