"""
Hybrid Search Engine combining Dense Semantic Vectors and Sparse BM25.
Implements Reciprocal Rank Fusion (RRF) for balanced enterprise context retrieval.
"""

from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi

from src.rag.vector_store import SovereignVectorStore, SearchResult, global_vector_store


class HybridSearchEngine:
    """
    Combines dense semantic vector retrieval with sparse BM25 lexical search.
    Merges multi-source candidate lists using Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, vector_store: Optional[SovereignVectorStore] = None, rrf_k: int = 60):
        self.vector_store = vector_store or global_vector_store
        self.rrf_k = rrf_k

    def _tokenize(self, text: str) -> List[str]:
        """Simple alphanumeric tokenizer for BM25."""
        import re
        return re.findall(r"\b\w+\b", text.lower())

    def search_sparse_bm25(
        self,
        tenant_id: str,
        query: str,
        top_k: int = 5
    ) -> List[SearchResult]:
        """Executes BM25 keyword matching over active tenant chunks."""
        active_records = self.vector_store.get_all_active_chunks_for_tenant(tenant_id)
        if not active_records:
            return []

        corpus = [self._tokenize(r.content) for r in active_records]
        bm25 = BM25Okapi(corpus)

        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            return []

        doc_scores = bm25.get_scores(tokenized_query)
        scored_pairs = list(zip(doc_scores, active_records))
        scored_pairs.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, rec in scored_pairs[:top_k]:
            if score <= 0:
                continue
            results.append(
                SearchResult(
                    chunk_id=rec.chunk_id,
                    doc_id=rec.doc_id,
                    tenant_id=rec.tenant_id,
                    content=rec.content,
                    score=float(score),
                    section_title=rec.metadata.get("section_title", "Unknown Section"),
                    metadata=rec.metadata,
                    retrieval_method="sparse_bm25"
                )
            )
        return results

    def search_hybrid(
        self,
        tenant_id: str,
        query: str,
        top_k: int = 5,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5
    ) -> List[SearchResult]:
        """
        Executes parallel Dense and BM25 Sparse searches, then fuses results
        using Reciprocal Rank Fusion (RRF).
        """
        candidate_pool = top_k * 3
        dense_results = self.vector_store.search_dense(tenant_id, query, top_k=candidate_pool)
        sparse_results = self.search_sparse_bm25(tenant_id, query, top_k=candidate_pool)

        if not dense_results and not sparse_results:
            return []

        # RRF Scoring Map: chunk_id -> {score, result_obj}
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, SearchResult] = {}

        # 1. Process Dense Ranks
        for rank, res in enumerate(dense_results):
            rrf_score = dense_weight * (1.0 / (self.rrf_k + rank + 1))
            rrf_scores[res.chunk_id] = rrf_scores.get(res.chunk_id, 0.0) + rrf_score
            chunk_map[res.chunk_id] = res

        # 2. Process Sparse Ranks
        for rank, res in enumerate(sparse_results):
            rrf_score = sparse_weight * (1.0 / (self.rrf_k + rank + 1))
            rrf_scores[res.chunk_id] = rrf_scores.get(res.chunk_id, 0.0) + rrf_score
            if res.chunk_id not in chunk_map:
                chunk_map[res.chunk_id] = res

        # 3. Sort by fused RRF score
        sorted_chunks = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)

        final_results = []
        for chunk_id, fused_score in sorted_chunks[:top_k]:
            base_res = chunk_map[chunk_id]
            final_results.append(
                SearchResult(
                    chunk_id=base_res.chunk_id,
                    doc_id=base_res.doc_id,
                    tenant_id=base_res.tenant_id,
                    content=base_res.content,
                    score=round(fused_score * 100, 4),  # Scale for clarity
                    section_title=base_res.section_title,
                    metadata=base_res.metadata,
                    retrieval_method="hybrid_rrf"
                )
            )

        return final_results


# Global hybrid search engine instance
global_hybrid_search = HybridSearchEngine()
