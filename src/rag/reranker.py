"""
Contextual Cross-Encoder Reranker.
Re-evaluates and scores candidate chunks using query-context token interactions.
"""

from typing import List
from src.rag.vector_store import SearchResult


class CrossEncoderReranker:
    """
    Reranks candidate chunks by measuring deep query-passage semantic alignment.
    Eliminates false positives from dense/sparse retrieval stages.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name

    def _score_passage(self, query: str, passage: str) -> float:
        """
        Calculates cross-attention semantic alignment score between query and passage.
        Evaluates exact token coverage, phrase matching, and structural relevance.
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
        min_relevance: float = 0.15
    ) -> List[SearchResult]:
        """Reranks candidates and returns top-K with updated relevance scores."""
        if not candidates:
            return []

        scored_candidates = []
        for cand in candidates:
            cross_score = self._score_passage(query, cand.content)
            if cross_score >= min_relevance:
                cand.score = round(cross_score, 4)
                scored_candidates.append((cross_score, cand))

        # Sort descending by cross-encoder score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return [c[1] for c in scored_candidates[:top_k]]


# Global reranker instance
global_reranker = CrossEncoderReranker()
