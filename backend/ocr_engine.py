# ==============================================================================
# File: backend/ocr_engine.py
# Description: Optical Character Recognition (OCR) Engine using local Tesseract.
#              Extracts printed and handwritten text from images (receipts,
#              documents, whiteboards, screenshots, and signs) completely offline.
# ==============================================================================

import logging
from pathlib import Path
from typing import Optional
from PIL import Image

logger = logging.getLogger("OCREngine")

_ocr_available: Optional[bool] = None


def is_ocr_available() -> bool:
    """Checks whether pytesseract and Tesseract OCR engine are installed and operational."""
    global _ocr_available
    if _ocr_available is not None:
        return _ocr_available

    try:
        import pytesseract
        # Quick probe with a tiny 1x1 image
        img = Image.new("RGB", (30, 30), color="white")
        pytesseract.image_to_string(img, timeout=3)
        _ocr_available = True
    except Exception as e:
        logger.warning(f"Tesseract OCR engine is not available: {e}")
        _ocr_available = False

    return _ocr_available


def extract_ocr_text(file_path: Path) -> str:
    """
    Extracts text from image file using local Tesseract OCR engine.
    Optimized with bilinear downsampling for large images to execute under 1 second.
    Returns cleaned string or empty string.
    """
    if not is_ocr_available():
        return ""

    try:
        import pytesseract

        if not file_path.is_file():
            return ""

        with Image.open(file_path) as img:
            # Convert palette/RGBA to RGB
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Optimization: Downscale if image dimensions exceed 2200px
            max_dim = 2200
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / float(max(w, h))
                new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
                img = img.resize(new_size, Image.Resampling.BILINEAR)

            # Extract text
            raw_text = pytesseract.image_to_string(img, timeout=12)
            cleaned = " ".join(raw_text.split())
            return cleaned

    except Exception as e:
        logger.warning(f"OCR extraction failed for {file_path.name}: {e}")
        return ""
