"""
Contextual Cross-Encoder Reranker.
Re-evaluates and scores candidate chunks using true Transformer Cross-Encoder attention
(e.g. cross-encoder/ms-marco-MiniLM-L-6-v2) or transparent linguistic fallback.
"""

import logging
from typing import List, Optional, Any
from src.rag.vector_store import SearchResult

logger = logging.getLogger(__name__)

# Try importing CrossEncoder
try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    logger.info("sentence-transformers CrossEncoder not available. Using linguistic alignment reranker.")


class CrossEncoderReranker:
    """
    Reranks candidate chunks by measuring deep query-passage cross-attention semantic alignment.
    Eliminates false positives from dense/sparse retrieval stages.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.neural_model: Optional[Any] = None
        self.is_neural: bool = False

        if CROSS_ENCODER_AVAILABLE:
            try:
                try:
                    self.neural_model = CrossEncoder(self.model_name, local_files_only=True)
                except Exception:
                    self.neural_model = CrossEncoder(self.model_name)
                self.is_neural = True
                logger.info(f"Loaded neural cross-encoder: {self.model_name}")
            except Exception as e:
                logger.warning(
                    f"Could not load neural cross-encoder '{self.model_name}': {e}. "
                    "Engaging sovereign linguistic reranking engine."
                )
                self.is_neural = False

    def _score_passage_linguistic(self, query: str, passage: str) -> float:
        """
        Calculates cross-token linguistic alignment score between query and passage.
        Evaluates exact token coverage, phrase matching, and structural density.
        """
        q_tokens = set(query.lower().split())
        if not q_tokens:
            return 0.0

        p_lower = passage.lower()
        p_tokens = p_lower.split()
        if not p_tokens:
            return 0.0

        # Exact word match ratio
        matched_tokens = sum(1 for t in q_tokens if t in p_lower)
        coverage = matched_tokens / len(q_tokens)

        # Term frequency density
        density = sum(p_tokens.count(t) for t in q_tokens) / len(p_tokens)

        # Proximity bonus (checks if query words appear closely together)
        proximity_bonus = 0.0
        q_words = list(q_tokens)
        for i in range(len(q_words) - 1):
            if f"{q_words[i]} {q_words[i+1]}" in p_lower:
                proximity_bonus += 0.25

        score = (coverage * 0.60) + (min(1.0, density * 5.0) * 0.20) + min(0.20, proximity_bonus)
        return min(1.0, max(0.0, score))

    def rerank(
        self,
        query: str,
        candidates: List[SearchResult],
        top_k: int = 3,
        min_relevance: float = 0.01
    ) -> List[SearchResult]:
        """Reranks candidates and returns top-K with updated relevance scores."""
        if not candidates:
            return []

        # 1. Neural Cross-Encoder Prediction
        if self.is_neural and self.neural_model is not None:
            try:
                pairs = [[query, c.content] for c in candidates]
                raw_scores = self.neural_model.predict(pairs)
                
                # Sigmoid normalize if logits
                import numpy as np
                raw_arr = np.array(raw_scores, dtype=np.float32)
                scores = 1.0 / (1.0 + np.exp(-raw_arr))

                scored_candidates = []
                for cand, score in zip(candidates, scores):
                    norm_score = float(score)
                    cand.score = round(norm_score, 4)
                    cand.retrieval_method = "cross_encoder_neural"
                    scored_candidates.append((norm_score, cand))

                scored_candidates.sort(key=lambda x: x[0], reverse=True)
                valid = [c[1] for c in scored_candidates if c[0] >= min_relevance]
                return valid[:top_k] if valid else [c[1] for c in scored_candidates[:top_k]]
            except Exception as e:
                logger.warning(f"Neural cross-encoder scoring failed: {e}. Falling back to linguistic reranker.")

        # 2. Linguistic Cross-Attention Fallback
        scored_candidates = []
        for cand in candidates:
            cross_score = self._score_passage_linguistic(query, cand.content)
            cand.score = round(cross_score, 4)
            scored_candidates.append((cross_score, cand))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        valid = [c[1] for c in scored_candidates if c[0] >= min_relevance]
        return valid[:top_k] if valid else [c[1] for c in scored_candidates[:top_k]]


# Global reranker instance
global_reranker = CrossEncoderReranker()
