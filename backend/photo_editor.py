# ==============================================================================
# File: backend/photo_editor.py
# Description: High-fidelity image manipulation engine for the in-browser
#              Google Photos Editor Suite. Supports auto-enhancement,
#              adjustments (brightness, contrast, saturation, warmth),
#              rotation, flipping, and aspect ratio cropping using Pillow.
# ==============================================================================

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from PIL import Image, ImageEnhance, ImageOps

logger = logging.getLogger("PhotoEditor")


def apply_warmth(img: Image.Image, warmth: float) -> Image.Image:
    """
    Shifts color balance along the temperature spectrum (warm amber vs cool blue).
    warmth range: -1.0 (cool blue) to +1.0 (warm golden).
    """
    if abs(warmth) < 0.01:
        return img

    if img.mode != "RGB":
        img = img.convert("RGB")

    r, g, b = img.split()

    if warmth > 0:
        # Increase red, slightly reduce blue
        r_factor = 1.0 + (warmth * 0.18)
        b_factor = 1.0 - (warmth * 0.14)
    else:
        # Increase blue, slightly reduce red
        cool = abs(warmth)
        r_factor = 1.0 - (cool * 0.14)
        b_factor = 1.0 + (cool * 0.18)

    r = r.point(lambda i: min(255, max(0, int(i * r_factor))))
    b = b.point(lambda i: min(255, max(0, int(i * b_factor))))

    return Image.merge("RGB", (r, g, b))


def process_image_edits(
    source_path: Path,
    target_path: Path,
    edits: Dict[str, Any]
) -> Tuple[int, int, int]:
    """
    Applies a chain of edits to source image and saves to target_path.
    Returns: (width, height, file_size) of the resulting image.
    """
    with Image.open(source_path) as orig_img:
        # Normalize EXIF orientation first
        img = ImageOps.exif_transpose(orig_img) or orig_img
        img = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img

        # 1. Rotation (90, 180, 270 degrees)
        rotate_deg = int(edits.get("rotate", 0)) % 360
        if rotate_deg != 0:
            # Pillow rotates counter-clockwise for positive degrees, so invert for clockwise
            img = img.rotate(-rotate_deg, expand=True, resample=Image.Resampling.BICUBIC)

        # 2. Horizontal Flip
        if edits.get("flip_h", False):
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

        # 3. Cropping (relative coordinates: 0.0 to 1.0 or absolute pixels)
        crop_rect = edits.get("crop")
        if crop_rect and isinstance(crop_rect, dict):
            orig_w, orig_h = img.size
            # Support normalized coordinates (0.0 - 1.0)
            if crop_rect.get("normalized", False) or (crop_rect.get("w", 1) <= 1.0 and crop_rect.get("h", 1) <= 1.0):
                left = int(crop_rect.get("x", 0) * orig_w)
                top = int(crop_rect.get("y", 0) * orig_h)
                right = int((crop_rect.get("x", 0) + crop_rect.get("w", 1.0)) * orig_w)
                bottom = int((crop_rect.get("y", 0) + crop_rect.get("h", 1.0)) * orig_h)
            else:
                left = int(crop_rect.get("x", 0))
                top = int(crop_rect.get("y", 0))
                right = left + int(crop_rect.get("w", orig_w))
                bottom = top + int(crop_rect.get("h", orig_h))

            # Clamp boundaries
            left = max(0, min(orig_w - 1, left))
            top = max(0, min(orig_h - 1, top))
            right = max(left + 1, min(orig_w, right))
            bottom = max(top + 1, min(orig_h, bottom))

            if right > left and bottom > top:
                img = img.crop((left, top, right, bottom))

        # 4. Auto Enhance ("I'm Feeling Lucky")
        if edits.get("auto_enhance", False):
            if img.mode == "RGBA":
                rgb_img = img.convert("RGB")
                rgb_img = ImageOps.autocontrast(rgb_img, cutoff=0.5)
                img = rgb_img.convert("RGBA")
            else:
                img = ImageOps.autocontrast(img, cutoff=0.5)
            # Slight saturation & contrast boost for punchy Google Photos look
            img = ImageEnhance.Color(img).enhance(1.12)
            img = ImageEnhance.Contrast(img).enhance(1.08)

        # 5. Brightness Adjustment (slider -100 to +100 -> multiplier 0.4 to 1.6)
        brightness_val = float(edits.get("brightness", 0))
        if abs(brightness_val) > 0.5:
            # Map -100..100 to 0.4..1.6
            factor = 1.0 + (brightness_val / 100.0) * 0.6
            factor = max(0.2, min(2.0, factor))
            img = ImageEnhance.Brightness(img).enhance(factor)

        # 6. Contrast Adjustment (slider -100 to +100 -> multiplier 0.4 to 1.6)
        contrast_val = float(edits.get("contrast", 0))
        if abs(contrast_val) > 0.5:
            factor = 1.0 + (contrast_val / 100.0) * 0.6
            factor = max(0.2, min(2.0, factor))
            img = ImageEnhance.Contrast(img).enhance(factor)

        # 7. Saturation Adjustment (slider -100 to +100 -> multiplier 0.0 to 2.0)
        saturation_val = float(edits.get("saturation", 0))
        if abs(saturation_val) > 0.5:
            if saturation_val < 0:
                # -100 brings saturation to 0 (monochrome / B&W)
                factor = 1.0 + (saturation_val / 100.0)
            else:
                factor = 1.0 + (saturation_val / 100.0) * 1.0
            factor = max(0.0, min(2.5, factor))
            img = ImageEnhance.Color(img).enhance(factor)

        # 8. Warmth / Color Temperature (-100 to +100)
        warmth_val = float(edits.get("warmth", 0)) / 100.0
        if abs(warmth_val) > 0.01:
            img = apply_warmth(img, warmth_val)

        # 9. Format & Save
        target_path.parent.mkdir(parents=True, exist_ok=True)
        is_jpeg = target_path.suffix.lower() in (".jpg", ".jpeg")

        save_kwargs = {}
        if is_jpeg:
            save_kwargs["quality"] = 92
            save_kwargs["optimize"] = True
            if img.mode == "RGBA":
                img = img.convert("RGB")
        elif target_path.suffix.lower() == ".png":
            save_kwargs["optimize"] = True

        img.save(str(target_path), **save_kwargs)

        width, height = img.size
        file_size = target_path.stat().st_size
        return width, height, file_size
