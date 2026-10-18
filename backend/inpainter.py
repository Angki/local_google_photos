# ==============================================================================
# File: backend/inpainter.py
# Description: Magic Eraser / Object Removal Inpainting Engine.
#              Fast Harmonic Boundary Diffusion & Poisson Smoothing via SciPy & NumPy,
#              with automatic graceful fallback to OpenCV inpaint if present.
# ==============================================================================

import io
import logging
from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image
import scipy.ndimage as ndi

logger = logging.getLogger("Inpainter")


def inpaint_photo(
    image: Union[str, Path, Image.Image],
    mask: Union[str, Path, Image.Image, np.ndarray, bytes],
    iterations: int = 15,
) -> Image.Image:
    """
    Erases unwanted objects indicated by the mask from the photo.
    
    Args:
        image: Path to photo or PIL Image.
        mask: Mask image where white/non-zero pixels mark the object to remove.
        iterations: Number of harmonic diffusion smoothing steps.
        
    Returns:
        Clean PIL Image with object removed and texture synthesized.
    """
    # 1. Load source image as RGB PIL
    if isinstance(image, (str, Path)):
        pil_img = Image.open(str(image)).convert("RGB")
    else:
        pil_img = image.convert("RGB")

    w, h = pil_img.size

    # 2. Load mask and ensure binary uint8 array matching image size
    if isinstance(mask, (str, Path)):
        mask_pil = Image.open(str(mask)).convert("L")
    elif isinstance(mask, bytes):
        mask_pil = Image.open(io.BytesIO(mask)).convert("L")
    elif isinstance(mask, np.ndarray):
        mask_pil = Image.fromarray(mask).convert("L")
    else:
        mask_pil = mask.convert("L")

    # Resize mask to match image exactly if needed
    if mask_pil.size != (w, h):
        mask_pil = mask_pil.resize((w, h), Image.NEAREST)

    img_rgb = np.array(pil_img, dtype=np.uint8)
    mask_np = np.array(mask_pil, dtype=np.uint8)

    # Threshold mask: pixels > 30 are considered marked for inpainting
    mask_bool = mask_np > 30

    if not np.any(mask_bool):
        # Empty mask, nothing to erase
        return pil_img

    # 3. Try OpenCV if available
    try:
        import cv2
        mask_cv = (mask_bool * 255).astype(np.uint8)
        # Dilate mask slightly in cv2
        kernel_cv = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask_cv = cv2.dilate(mask_cv, kernel_cv)
        # Convert RGB to BGR for OpenCV
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        result_bgr = cv2.inpaint(img_bgr, mask_cv, inpaintRadius=5, flags=cv2.INPAINT_TELEA)
        result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(result_rgb)
    except (ImportError, Exception) as cv_err:
        logger.debug(f"OpenCV inpainting skipped or unavailable ({cv_err}), running Fast Harmonic Diffusion.")

    # 4. Fast Harmonic Diffusion via SciPy & NumPy
    # Dilate mask to encompass object edges and antialiasing halos
    mask_dilated = ndi.binary_dilation(mask_bool, iterations=3)

    # Distance transform nearest neighbor boundary propagation
    _, (nearest_y, nearest_x) = ndi.distance_transform_edt(mask_dilated, return_indices=True)

    out = img_rgb.copy().astype(np.float32)
    # Seed masked pixels from closest boundary background pixels
    out[mask_dilated] = img_rgb[nearest_y[mask_dilated], nearest_x[mask_dilated]]

    # Normalized 3x3 Laplace/Poisson smoothing kernel
    kernel = np.array([
        [0.05, 0.20, 0.05],
        [0.20, 0.00, 0.20],
        [0.05, 0.20, 0.05]
    ], dtype=np.float32)

    # Iterative diffusion to blend boundaries seamlessly
    for _ in range(iterations):
        for c in range(3):
            smoothed = ndi.convolve(out[:, :, c], kernel, mode="nearest")
            out[mask_dilated, c] = 0.75 * smoothed[mask_dilated] + 0.25 * out[mask_dilated, c]

    # Texture/film grain synthesis: calculate noise std from the surrounding boundary ring
    boundary_ring = ndi.binary_dilation(mask_dilated, iterations=6) ^ mask_dilated
    if np.any(boundary_ring):
        std_per_channel = np.std(img_rgb[boundary_ring], axis=0)
        # Generate subtle gaussian noise
        noise = np.random.normal(0, std_per_channel * 0.35, (h, w, 3))
        out[mask_dilated] += noise[mask_dilated]

    out_uint8 = np.clip(out, 0, 255).astype(np.uint8)
    return Image.fromarray(out_uint8)
