# ==============================================================================
# File: backend/ai_engine.py
# Description: Local AI Vision Engine utilizing OpenAI CLIP for zero-shot photo
#              categorization and natural language semantic image search.
#
# CHANGELOG:
# 2026-09-05 - Initial creation: Added lazy model loader, GPU/CPU auto-detection,
#              zero-shot classification across 12 categories, vector embedding
#              generation, and fast cosine similarity search.
# ==============================================================================

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

from backend.config import CLIP_MODEL_NAME, DEFAULT_CATEGORIES, EMBEDDING_DIM

logger = logging.getLogger("AIEngine")


class AIEngine:
    def __init__(self, model_name: str = CLIP_MODEL_NAME):
        self.model_name = model_name
        self.model = None
        self.processor = None
        self.device = "cpu"
        self._is_loaded = False
        self._load_failed = False  # Prevent repeated load attempts after failure
        self._warned = False  # Suppress duplicate log warnings
        self._category_embeddings = None
        self._categories = list(DEFAULT_CATEGORIES)

    def is_available(self) -> bool:
        """Returns True if dependencies for AI are importable."""
        try:
            import torch
            import transformers
            return True
        except ImportError:
            return False

    def load_model(self) -> bool:
        """Loads CLIP model and precomputes text embeddings for default categories."""
        if self._is_loaded:
            return True
        if self._load_failed:
            return False  # Don't retry after a confirmed failure

        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading CLIP model '{self.model_name}' on device: {self.device}...")

            self.processor = CLIPProcessor.from_pretrained(self.model_name)
            self.model = CLIPModel.from_pretrained(self.model_name).to(self.device)
            self.model.eval()

            # Precompute text embeddings for all default categories
            self._precompute_category_embeddings()

            self._is_loaded = True
            logger.info("CLIP model loaded successfully.")
            return True
        except Exception as e:
            if not self._warned:
                logger.warning(f"Unable to load local CLIP model ({e}). AI features will use rule-based fallback.")
                self._warned = True
            self._is_loaded = False
            self._load_failed = True
            return False

    def _precompute_category_embeddings(self) -> None:
        """Precomputes normalized text embeddings for standard categories."""
        import torch

        # Prompts designed for zero-shot photo classification
        prompts = [f"a photo of {cat}" for cat in self._categories]
        inputs = self.processor(text=prompts, return_tensors="pt", padding=True).to(self.device)

        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
            # Normalize vectors
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            self._category_embeddings = text_features.cpu().numpy()

    def analyze_image(self, image_path: Path) -> Tuple[str, float, List[str], Optional[bytes]]:
        """
        Analyzes a single image:
        Returns: (primary_category, confidence_score, list_of_top_tags, embedding_bytes)
        """
        if not self._is_loaded:
            if not self.load_model():
                # Fallback rule-based tagging if AI model isn't available
                return self._fallback_analyze(image_path)

        import torch

        try:
            with Image.open(image_path) as raw_img:
                if raw_img.mode != "RGB":
                    raw_img = raw_img.convert("RGB")

                inputs = self.processor(images=raw_img, return_tensors="pt").to(self.device)

                with torch.no_grad():
                    # 1. Image feature embedding
                    image_features = self.model.get_image_features(**inputs)
                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)

                    # Store embedding as 512-dim float32 binary
                    img_vec = image_features.cpu().numpy()[0].astype(np.float32)
                    embedding_bytes = img_vec.tobytes()

                    # 2. Zero-shot classification against precomputed category embeddings
                    similarities = np.dot(self._category_embeddings, img_vec)
                    # Softmax to get relative probabilities
                    exp_sims = np.exp(similarities * 100.0)  # Temperature scaling
                    probs = exp_sims / np.sum(exp_sims)

                    top_indices = np.argsort(probs)[::-1]
                    top_cat = self._categories[top_indices[0]]
                    top_conf = float(probs[top_indices[0]])

                    # Select tags that have meaningful confidence (> 0.08)
                    top_tags = [
                        self._categories[i]
                        for i in top_indices[:3]
                        if probs[i] > 0.08 or i == top_indices[0]
                    ]

                    return top_cat, round(top_conf, 3), top_tags, embedding_bytes
        except Exception as e:
            logger.error(f"Error analyzing image {image_path.name}: {e}")
            return self._fallback_analyze(image_path)

    def encode_text_query(self, query: str) -> Optional[np.ndarray]:
        """Encodes user search query into normalized 512-dim embedding."""
        if not self._is_loaded:
            if not self.load_model():
                return None

        import torch

        try:
            inputs = self.processor(text=[query], return_tensors="pt", padding=True).to(self.device)
            with torch.no_grad():
                text_features = self.model.get_text_features(**inputs)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                return text_features.cpu().numpy()[0].astype(np.float32)
        except Exception as e:
            logger.error(f"Error encoding query '{query}': {e}")
            return None

    def _fallback_analyze(self, image_path: Path) -> Tuple[str, float, List[str], Optional[bytes]]:
        """Heuristic fallback categorization based on filename and directory cues."""
        name_lower = image_path.name.lower()
        parent_lower = image_path.parent.name.lower()

        if any(x in name_lower for x in ["screenshot", "screen_shot", "capture"]):
            return "screenshots", 0.90, ["screenshots", "documents"], None
        if any(x in name_lower for x in ["receipt", "bill", "invoice", "struk", "nota"]):
            return "receipts", 0.85, ["receipts", "documents"], None
        if any(x in name_lower for x in ["doc", "surat", "arsip", "berkas", "scan"]):
            return "documents", 0.80, ["documents"], None
        if any(x in name_lower for x in ["art", "design", "sticker", "stiker", "poster"]):
            return "artwork", 0.75, ["artwork"], None

        # Generic default
        return "nature", 0.30, ["nature"], None


# Singleton instance
ai_engine = AIEngine()
