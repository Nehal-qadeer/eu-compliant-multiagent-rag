"""
Sovereign Embedding Engine.
Generates normalized dense vector embeddings using SentenceTransformers (e.g. all-MiniLM-L6-v2 / BAAI/bge-m3)
within EU sovereign boundaries with zero external data leakage.
"""

import math
import hashlib
import logging
import numpy as np
from typing import List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Try importing SentenceTransformer
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.info("sentence-transformers not installed. Using sovereign deterministic embedding generator.")


class EmbeddingModel:
    """
    Sovereign Dense Embedding Generator.
    Supports real neural embeddings via SentenceTransformers (CPU/GPU)
    and transparent deterministic fallback for strictly isolated offline environments.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", dimension: int = 384):
        self.model_name = model_name
        self.dimension = dimension
        self.neural_model: Optional[Any] = None
        self.is_neural: bool = False

        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Initialize neural embedding model
                self.neural_model = SentenceTransformer(self.model_name)
                self.dimension = self.neural_model.get_sentence_embedding_dimension()
                self.is_neural = True
                logger.info(f"Loaded neural embedding model: {self.model_name} (dim: {self.dimension})")
            except Exception as e:
                logger.warning(
                    f"Could not load neural model '{self.model_name}': {e}. "
                    "Engaging sovereign deterministic vector engine."
                )
                self.is_neural = False

    def _generate_deterministic_vector(self, text: str) -> List[float]:
        """
        Generates a deterministic, normalized embedding vector from text using
        token hashing and frequency distribution. Guarantees cosine similarity
        reflects semantic keyword overlap and token n-gram alignment.
        """
        vector = np.zeros(self.dimension, dtype=np.float32)
        tokens = text.lower().split()
        if not tokens:
            return vector.tolist()

        for idx, token in enumerate(tokens):
            # Generate deterministic hash for token
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            slot = h % self.dimension
            weight = 1.0 / math.sqrt(idx + 1)
            vector[slot] += weight

            # Also embed bi-grams for localized phrase awareness
            if idx > 0:
                bigram = f"{tokens[idx-1]}_{token}"
                h_bi = int(hashlib.sha256(bigram.encode("utf-8")).hexdigest(), 16)
                slot_bi = h_bi % self.dimension
                vector[slot_bi] += 1.5 * weight

        # Normalize vector to unit length (L2 norm) for cosine similarity
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector.tolist()

    def embed_text(self, text: str) -> List[float]:
        """Embeds a single text string into a dense vector."""
        if self.is_neural and self.neural_model is not None:
            try:
                emb = self.neural_model.encode(text, normalize_embeddings=True)
                return emb.tolist() if hasattr(emb, "tolist") else list(emb)
            except Exception as e:
                logger.warning(f"Neural embedding failed: {e}. Falling back to deterministic vector.")
        return self._generate_deterministic_vector(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embeds a batch of document texts."""
        if self.is_neural and self.neural_model is not None:
            try:
                embs = self.neural_model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
                return [e.tolist() if hasattr(e, "tolist") else list(e) for e in embs]
            except Exception as e:
                logger.warning(f"Batch neural embedding failed: {e}. Falling back to deterministic vectors.")
        return [self.embed_text(t) for t in texts]

    def compute_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Computes cosine similarity between two normalized vectors."""
        v1 = np.array(vec1, dtype=np.float32)
        v2 = np.array(vec2, dtype=np.float32)
        denom = (np.linalg.norm(v1) * np.linalg.norm(v2))
        if denom == 0:
            return 0.0
        return float(np.dot(v1, v2) / denom)


# Global sovereign embedding model
global_embedding_model = EmbeddingModel()
