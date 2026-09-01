"""
Retrieval Agent.
Coordinates hybrid multi-stage retrieval, sub-query aggregation, deduplication, and cross-encoder reranking.
"""

from typing import List, Dict, Optional
from src.agents.query_planner import QueryPlan
from src.rag.vector_store import SearchResult
from src.rag.hybrid_search import HybridSearchEngine, global_hybrid_search
from src.rag.reranker import CrossEncoderReranker, global_reranker


class RetrievalAgent:
    """
    Executes hybrid dense/sparse retrieval across tenant-isolated namespaces
    and invokes cross-encoder reranking.
    """

    def __init__(
        self,
        hybrid_engine: Optional[HybridSearchEngine] = None,
        reranker: Optional[CrossEncoderReranker] = None
    ):
        self.hybrid_engine = hybrid_engine or global_hybrid_search
        self.reranker = reranker or global_reranker

    def execute_retrieval(
        self,
        tenant_id: str,
        plan: QueryPlan,
        top_k: int = 4
    ) -> List[SearchResult]:
        """
        Executes hybrid search across all planned subqueries, aggregates results,
        and applies cross-encoder reranking against the original query.
        """
        candidates_map: Dict[str, SearchResult] = {}

        # 1. Execute Hybrid Search for each subquery
        for sq in plan.subqueries:
            sub_results = self.hybrid_engine.search_hybrid(
                tenant_id=tenant_id,
                query=sq.query_text,
                top_k=top_k * 2
            )
            for res in sub_results:
                if res.chunk_id not in candidates_map or res.score > candidates_map[res.chunk_id].score:
                    candidates_map[res.chunk_id] = res

        aggregated_candidates = list(candidates_map.values())
        if not aggregated_candidates:
            return []

        # 2. Cross-Encoder Rerank against full original query
        reranked_results = self.reranker.rerank(
            query=plan.original_query,
            candidates=aggregated_candidates,
            top_k=top_k
        )

        return reranked_results


# Global retrieval agent instance
global_retrieval_agent = RetrievalAgent()
