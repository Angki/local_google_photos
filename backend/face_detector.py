# ==============================================================================
# File: backend/face_detector.py
# Description: On-Device Lightweight Face Detection Engine using UltraFace ONNX
#              (320x240 RFB) with NMS and offline skin-tone heuristic fallback.
#              Automatically detects faces on untagged photos and mobile uploads.
# ==============================================================================

import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image

logger = logging.getLogger("FaceDetector")

MODEL_PATH = Path(__file__).parent / "models" / "version-RFB-320.onnx"
FACES_DIR = Path(__file__).parent.parent / "thumbnails" / "faces"

_onnx_session = None
_cached_priors = None


def _get_onnx_session():
    """Lazily initializes the ONNX runtime inference session."""
    global _onnx_session
    if _onnx_session is None and MODEL_PATH.exists():
        try:
            import onnxruntime as ort
            # Suppress verbose ONNX logging
            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            _onnx_session = ort.InferenceSession(str(MODEL_PATH), sess_options=opts, providers=["CPUExecutionProvider"])
            logger.info("UltraFace ONNX session loaded successfully.")
        except Exception as e:
            logger.warning(f"Failed to load UltraFace ONNX session: {e}")
            _onnx_session = None
    return _onnx_session


def _generate_priors(width: int = 320, height: int = 240) -> np.ndarray:
    """Generates the 4420 anchor prior boxes for UltraFace 320x240."""
    global _cached_priors
    if _cached_priors is not None:
        return _cached_priors

    strides = [8, 16, 32, 64]
    min_boxes = [[10, 16, 24], [32, 48], [64, 96], [128, 256, 512]]
    priors = []

    for i, s in enumerate(strides):
        fm_h = math.ceil(height / s)
        fm_w = math.ceil(width / s)
        for y in range(fm_h):
            for x in range(fm_w):
                cx = (x + 0.5) * s / width
                cy = (y + 0.5) * s / height
                for min_box in min_boxes[i]:
                    bw = min_box / width
                    bh = min_box / height
                    priors.append([cx, cy, bw, bh])

    _cached_priors = np.array(priors, dtype=np.float32)
    return _cached_priors


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float = 0.3) -> List[int]:
    """Fast Non-Maximum Suppression (NMS) in pure NumPy."""
    if len(boxes) == 0:
        return []

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)

    order = scores.argsort()[::-1]
    keep = []

    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h

        ovr = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        inds = np.where(ovr <= iou_threshold)[0]
        order = order[inds + 1]

    return keep


def detect_faces_image(
    image: Union[str, Path, Image.Image],
    conf_threshold: float = 0.65,
    iou_threshold: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Detects faces in an image using UltraFace ONNX (or heuristic fallback).
    Returns a list of dicts with normalized coordinates:
    [{"box": [x1, y1, x2, y2], "confidence": float}, ...]
    where x1, y1, x2, y2 are in range [0.0, 1.0].
    """
    if isinstance(image, (str, Path)):
        try:
            pil_img = Image.open(str(image)).convert("RGB")
        except Exception as e:
            logger.warning(f"Could not open image for face detection {image}: {e}")
            return []
    else:
        pil_img = image.convert("RGB")

    orig_w, orig_h = pil_img.size
    if orig_w == 0 or orig_h == 0:
        return []

    session = _get_onnx_session()
    if session is not None:
        try:
            # 1. Resize to model input 320x240
            resized = pil_img.resize((320, 240), Image.BILINEAR)
            img_np = np.array(resized, dtype=np.float32)
            # Normalize with mean=127, std=128
            img_np = (img_np - 127.0) / 128.0
            img_np = np.transpose(img_np, (2, 0, 1))
            img_np = np.expand_dims(img_np, axis=0)

            # 2. Run inference
            scores_out, boxes_out = session.run(None, {"input": img_np})
            scores = scores_out[0]  # (4420, 2)
            boxes = boxes_out[0]    # (4420, 4)

            # 3. Decode prior boxes
            priors = _generate_priors(320, 240)
            cx = boxes[:, 0] * 0.1 * priors[:, 2] + priors[:, 0]
            cy = boxes[:, 1] * 0.1 * priors[:, 3] + priors[:, 1]
            bw = np.exp(boxes[:, 2] * 0.2) * priors[:, 2]
            bh = np.exp(boxes[:, 3] * 0.2) * priors[:, 3]

            x1 = np.clip(cx - bw / 2.0, 0.0, 1.0)
            y1 = np.clip(cy - bh / 2.0, 0.0, 1.0)
            x2 = np.clip(cx + bw / 2.0, 0.0, 1.0)
            y2 = np.clip(cy + bh / 2.0, 0.0, 1.0)

            face_probs = scores[:, 1]
            valid_mask = (face_probs >= conf_threshold) & (x2 > x1 + 0.02) & (y2 > y1 + 0.02)

            if not np.any(valid_mask):
                return []

            cand_boxes = np.stack([x1[valid_mask], y1[valid_mask], x2[valid_mask], y2[valid_mask]], axis=-1)
            cand_scores = face_probs[valid_mask]

            keep_indices = _nms(cand_boxes, cand_scores, iou_threshold=iou_threshold)
            results = []
            for idx in keep_indices:
                b = cand_boxes[idx].tolist()
                results.append({
                    "box": [round(coord, 4) for coord in b],
                    "confidence": round(float(cand_scores[idx]), 4),
                })
            return results
        except Exception as e:
            logger.warning(f"UltraFace ONNX execution failed: {e}")

    # Fallback heuristic: skin-tone chrominance clustering
    return _heuristic_face_detect(pil_img)


def _heuristic_face_detect(img: Image.Image) -> List[Dict[str, Any]]:
    """Simple offline skin-tone heuristic fallback if ONNX is unavailable."""
    try:
        w, h = img.size
        # Resize small for fast chrominance estimation
        small = img.resize((160, 120), Image.BILINEAR)
        ycbcr = small.convert("YCbCr")
        arr = np.array(ycbcr)
        cb = arr[:, :, 1]
        cr = arr[:, :, 2]

        # Standard human skin chrominance range in YCbCr: 77 <= Cb <= 127 and 133 <= Cr <= 173
        skin = (cb >= 77) & (cb <= 127) & (cr >= 133) & (cr <= 173)
        skin_ratio = np.sum(skin) / skin.size

        # If significant skin cluster in upper half, hypothesize central face
        if 0.05 <= skin_ratio <= 0.60:
            y_indices, x_indices = np.where(skin)
            if len(y_indices) > 50:
                y1 = float(np.percentile(y_indices, 15)) / 120.0
                y2 = float(np.percentile(y_indices, 85)) / 120.0
                x1 = float(np.percentile(x_indices, 15)) / 160.0
                x2 = float(np.percentile(x_indices, 85)) / 160.0
                return [{
                    "box": [round(max(0.0, x1), 4), round(max(0.0, y1), 4), round(min(1.0, x2), 4), round(min(1.0, y2), 4)],
                    "confidence": 0.55,
                }]
    except Exception as e:
        logger.debug(f"Heuristic face detect failed: {e}")
    return []


def detect_and_save_faces_for_photo(
    photo_id: int,
    file_path: Union[str, Path],
    save_crops: bool = True,
) -> List[Dict[str, Any]]:
    """
    Detects faces for a photo, saves square avatar crops to thumbnails/faces/,
    and returns detected face details.
    """
    p = Path(file_path)
    if not p.exists():
        return []

    try:
        pil_img = Image.open(str(p)).convert("RGB")
    except Exception as e:
        logger.warning(f"Failed to open image for face detection {file_path}: {e}")
        return []

    w, h = pil_img.size
    detected = detect_faces_image(pil_img)
    if not detected:
        return []

    FACES_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for idx, face in enumerate(detected):
        box = face["box"]
        x1_norm, y1_norm, x2_norm, y2_norm = box
        # Add 15% margin around face
        fw = x2_norm - x1_norm
        fh = y2_norm - y1_norm
        mx = fw * 0.15
        my = fh * 0.15

        x1_px = int(max(0, (x1_norm - mx) * w))
        y1_px = int(max(0, (y1_norm - my) * h))
        x2_px = int(min(w, (x2_norm + mx) * w))
        y2_px = int(min(h, (y2_norm + my) * h))

        crop_rel_path = None
        if save_crops and (x2_px > x1_px + 10) and (y2_px > y1_px + 10):
            try:
                face_crop = pil_img.crop((x1_px, y1_px, x2_px, y2_px))
                face_crop.thumbnail((160, 160), Image.LANCZOS)
                crop_filename = f"face_{photo_id}_{idx + 1}.jpg"
                crop_dest = FACES_DIR / crop_filename
                face_crop.save(str(crop_dest), "JPEG", quality=85)
                crop_rel_path = f"faces/{crop_filename}"
            except Exception as e:
                logger.debug(f"Failed to save face crop for photo {photo_id}: {e}")

        results.append({
            "index": idx + 1,
            "box": box,
            "confidence": face["confidence"],
            "crop_path": crop_rel_path,
            "label": f"Person {idx + 1}" if len(detected) > 1 else "Person",
        })

    return results
