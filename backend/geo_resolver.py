# ==============================================================================
# File: backend/geo_resolver.py
# Description: 100% offline reverse geocoder for resolving photo coordinates into
#              city, state, country, and readable location labels using KD-Tree.
# ==============================================================================

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("GeoResolver")

# ISO 3166-1 alpha-2 country code to English country name mapping for common countries
COUNTRY_NAMES = {
    "ID": "Indonesia",
    "MY": "Malaysia",
    "SG": "Singapore",
    "TH": "Thailand",
    "VN": "Vietnam",
    "PH": "Philippines",
    "JP": "Japan",
    "KR": "South Korea",
    "CN": "China",
    "HK": "Hong Kong",
    "TW": "Taiwan",
    "AU": "Australia",
    "NZ": "New Zealand",
    "US": "United States",
    "CA": "Canada",
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
    "CH": "Switzerland",
    "AE": "United Arab Emirates",
    "SA": "Saudi Arabia",
    "TR": "Turkey",
    "IN": "India",
}

# In-memory spatial cache rounded to ~1.1km (2 decimal places)
_GEO_CACHE: Dict[Tuple[float, float], Dict[str, str]] = {}
_RG_AVAILABLE: Optional[bool] = None


def is_geo_available() -> bool:
    """Checks if reverse-geocoder is importable and ready."""
    global _RG_AVAILABLE
    if _RG_AVAILABLE is None:
        try:
            import reverse_geocoder
            _RG_AVAILABLE = True
        except ImportError:
            _RG_AVAILABLE = False
            logger.warning("reverse-geocoder library not available. Location labels will be disabled.")
    return _RG_AVAILABLE


def resolve_location(lat: Optional[float], lon: Optional[float]) -> Dict[str, str]:
    """
    Resolves (lat, lon) coordinates into human-readable city, state, country.
    Returns dictionary with keys: 'city', 'state', 'country', 'country_code', 'location_label'.
    """
    empty_result = {
        "city": "",
        "state": "",
        "country": "",
        "country_code": "",
        "location_label": "",
    }
    if lat is None or lon is None:
        return empty_result
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        if lat_f == 0.0 and lon_f == 0.0:
            return empty_result
        if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
            return empty_result
    except (ValueError, TypeError):
        return empty_result

    # Check cache (round to 2 decimal places ~ 1.1 km)
    cache_key = (round(lat_f, 2), round(lon_f, 2))
    if cache_key in _GEO_CACHE:
        return _GEO_CACHE[cache_key]

    if not is_geo_available():
        return empty_result

    try:
        import reverse_geocoder as rg
        results = rg.search((lat_f, lon_f), mode=1)
        if not results:
            return empty_result

        match = results[0]
        city = (match.get("name") or "").strip()
        state = (match.get("admin1") or "").strip()
        cc = (match.get("cc") or "").strip().upper()
        country = COUNTRY_NAMES.get(cc, cc)

        # Build clean label: "Bandung, West Java (ID)" or "Tokyo, Japan"
        parts = []
        if city:
            parts.append(city)
        if state and state.lower() != city.lower():
            parts.append(state)
        if cc:
            parts.append(f"({cc})" if parts else country)

        location_label = ", ".join(parts) if parts else ""

        res = {
            "city": city,
            "state": state,
            "country": country,
            "country_code": cc,
            "location_label": location_label,
        }
        _GEO_CACHE[cache_key] = res
        return res
    except Exception as e:
        logger.debug(f"Reverse geocode lookup error for ({lat}, {lon}): {e}")
        return empty_result


def backfill_missing_locations(batch_size: int = 1000) -> int:
    """
    Scans database for geotagged photos missing city/state/country and fills them.
    Returns count of updated photos.
    """
    from backend.database import get_db_connection

    if not is_geo_available():
        return 0

    updated_count = 0
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT id, latitude, longitude
            FROM photos
            WHERE has_geo = 1 
              AND latitude IS NOT NULL 
              AND longitude IS NOT NULL
              AND (city IS NULL OR city = '')
            LIMIT ?;
        """, (batch_size,)).fetchall()

        if not rows:
            return 0

        updates = []
        for r in rows:
            info = resolve_location(r["latitude"], r["longitude"])
            if info["city"] or info["country"]:
                updates.append((
                    info["city"],
                    info["state"],
                    info["country"],
                    info["country_code"],
                    info["location_label"],
                    r["id"]
                ))

        if updates:
            conn.executemany("""
                UPDATE photos
                SET city = ?, state = ?, country = ?, country_code = ?, location_label = ?
                WHERE id = ?;
            """, updates)
            conn.commit()
            updated_count = len(updates)
            logger.info(f"Backfilled location data for {updated_count} photos.")

    return updated_count
