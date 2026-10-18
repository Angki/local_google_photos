# ==============================================================================
# File: backend/search_parser.py
# Description: Smart Compound NLP Query Parser for Google Photos Local.
#              Deconstructs natural search queries (e.g. "Kucing di Bandung 2024")
#              into structured filters: Entity/Subject, Location, Year, Month,
#              and Smart Category for high-precision hybrid retrieval.
# ==============================================================================

import re
import datetime
from typing import Dict, Any, Optional, List, Tuple


MONTH_MAP = {
    # Indonesian
    "januari": 1, "jan": 1,
    "februari": 2, "feb": 2,
    "maret": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "agustus": 8, "agt": 8, "agu": 8, "aug": 8, "august": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "oct": 10, "october": 10,
    "november": 11, "nov": 11,
    "desember": 12, "des": 12, "dec": 12, "december": 12,
    # English
    "january": 1, "february": 2, "march": 3,
    "june": 6, "july": 7,
}

CATEGORY_KEYWORDS = {
    "food": ["makanan", "kuliner", "food", "dish", "meal", "restoran", "sarapan", "makan", "lunch", "dinner"],
    "documents": ["dokumen", "surat", "document", "docs", "scan", "pdf", "sertifikat", "berkas"],
    "receipts": ["resi", "nota", "struk", "receipt", "invoice", "tagihan", "bukti transfer", "pembayaran"],
    "screenshots": ["screenshot", "ss", "tangkapan layar", "screen shot", "screen capture"],
    "nature": ["alam", "nature", "pemandangan", "landscape", "pantai", "beach", "gunung", "mountain", "laut", "hutan", "sunset", "sunrise"],
    "vehicles": ["mobil", "motor", "kendaraan", "car", "vehicle", "bike", "motorcycle"],
    "videos": ["video", "vidio", "rekaman", "movie", "klip"],
    "favorites": ["favorit", "favorite", "bintang", "starred"],
}


def parse_compound_query(raw_query: str) -> Dict[str, Any]:
    """
    Parses a user input string into structured components:
    - year: Optional[int] (e.g. 2024)
    - month: Optional[int] (1-12)
    - location: Optional[str] (e.g. "Bandung", "Bali")
    - category: Optional[str] (e.g. "nature", "food", "documents")
    - entity_query: str (clean remaining subject query for semantic/CLIP embedding search)
    - explanation: List[str] (human-readable filter chips to show user)
    """
    if not raw_query or not raw_query.strip():
        return {
            "year": None,
            "month": None,
            "location": None,
            "category": None,
            "entity_query": "",
            "explanation": [],
            "is_compound": False,
        }

    text = " " + raw_query.strip() + " "
    explanation = []
    detected_year = None
    detected_month = None
    detected_location = None
    detected_category = None

    # 1. Relative date keywords: "bulan lalu", "tahun lalu"
    now = datetime.datetime.now()
    if re.search(r"\b(bulan lalu|last month)\b", text, re.IGNORECASE):
        text = re.sub(r"\b(bulan lalu|last month)\b", " ", text, flags=re.IGNORECASE)
        # Previous month
        first_of_this_month = now.replace(day=1)
        last_month_date = first_of_this_month - datetime.timedelta(days=1)
        detected_year = last_month_date.year
        detected_month = last_month_date.month
        explanation.append(f"Bulan Lalu ({detected_year}-{detected_month:02d})")

    elif re.search(r"\b(tahun lalu|last year)\b", text, re.IGNORECASE):
        text = re.sub(r"\b(tahun lalu|last year)\b", " ", text, flags=re.IGNORECASE)
        detected_year = now.year - 1
        explanation.append(f"Tahun {detected_year}")

    # 2. Extract Year (2010 - 2030)
    year_match = re.search(r"\b(tahun|thn|year)?\s*(20[12][0-9])\b", text, re.IGNORECASE)
    if year_match and not detected_year:
        detected_year = int(year_match.group(2))
        text = text[:year_match.start()] + " " + text[year_match.end():]
        explanation.append(f"Tahun {detected_year}")

    # 3. Extract Month
    for name, month_num in MONTH_MAP.items():
        pattern = rf"\b(bulan|bln|month)?\s*{re.escape(name)}\b"
        if re.search(pattern, text, re.IGNORECASE):
            detected_month = month_num
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
            explanation.append(f"Bulan {name.capitalize()}")
            break

    # 4. Extract Category
    for cat_id, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            pattern = rf"\b{re.escape(kw)}\b"
            if re.search(pattern, text, re.IGNORECASE):
                detected_category = cat_id
                # Keep word in entity text if it's the only word, else remove to clean query
                break
        if detected_category:
            explanation.append(f"Kategori: {detected_category.capitalize()}")
            break

    # 5. Extract Location with "di <location>" or "in <location>"
    loc_match = re.search(r"\b(?:di|in|at|kota|pulau)\s+([A-Za-z\s]+?)(?=\s+(?:tahun|thn|pada|bulan|kategori|$))", text, re.IGNORECASE)
    if loc_match:
        cand = loc_match.group(1).strip()
        if len(cand) >= 3 and cand.lower() not in ["foto", "video", "gambar", "koleksi"]:
            detected_location = cand
            text = text[:loc_match.start()] + " " + text[loc_match.end():]
            explanation.append(f"Lokasi: {detected_location.title()}")

    # 6. Clean remaining entity query string
    # Remove filler prepositions
    text = re.sub(r"\b(foto|gambar|photo|picture|images|tentang|yang|ada|dengan|dan|dari|pada|di)\b", " ", text, flags=re.IGNORECASE)
    clean_entity = " ".join(text.split()).strip()

    has_date = bool(detected_year or detected_month)
    has_loc = bool(detected_location)
    has_cat = bool(detected_category)
    has_entity = bool(clean_entity)

    # A query is compound if it combines multiple distinct dimensions:
    # 1. Date with (Entity OR Location OR Category)
    # 2. Location with (Entity OR Category)
    # 3. Explicit date constraint alone (e.g. "2024", "bulan lalu")
    is_compound = bool(
        has_date or
        (has_loc and (has_entity or has_cat)) or
        (has_cat and has_date) or
        (has_cat and has_loc)
    )

    return {
        "year": detected_year,
        "month": detected_month,
        "location": detected_location,
        "category": detected_category,
        "entity_query": clean_entity,
        "explanation": explanation,
        "is_compound": is_compound,
    }
