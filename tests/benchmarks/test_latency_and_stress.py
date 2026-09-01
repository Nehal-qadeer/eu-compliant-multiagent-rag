"""
Latency Profiling and Concurrency Stress Benchmark Suite.
Validates sub-second throughput and p95 latency guarantees under concurrent query loads.
"""

import time
import asyncio
import pytest
from src.agents.supervisor import MultiAgentSupervisor
from src.rag.vector_store import SovereignVectorStore
from src.rag.chunking import ContextualChunker, IngestionDocument
from src.core.security import KeyVaultManager
from src.rag.hybrid_search import HybridSearchEngine
from src.agents.retrieval_agent import RetrievalAgent


@pytest.fixture
def stress_environment(fresh_key_vault: KeyVaultManager):
    """Sets up a populated knowledge base for stress testing."""
    store = SovereignVectorStore(key_vault=fresh_key_vault)
    chunker = ContextualChunker()

    doc = IngestionDocument(
        tenant_id="tenant_stress_eu",
        title="Corporate Compliance Manual",
        content="""# Privacy Operations
Data controllers must maintain records of processing activities under Article 30.
Regular vulnerability scans and cryptographic reviews must be performed monthly.

# Whistleblower Protections
Confidential reporting channels must be provided under EU Directive 2019/1937."""
    )
    key_id = fresh_key_vault.generate_key(tenant_id="tenant_stress_eu", subject_id=doc.doc_id)
    chunks = chunker.chunk_document(doc)
    store.index_chunks(tenant_id="tenant_stress_eu", chunks=chunks, key_id=key_id)

    hybrid = HybridSearchEngine(vector_store=store)
    retriever = RetrievalAgent(hybrid_engine=hybrid)
    supervisor = MultiAgentSupervisor(retrieval_agent=retriever)
    return supervisor


@pytest.mark.asyncio
async def test_concurrent_query_latency_and_throughput(stress_environment):
    """
    Executes 10 concurrent multi-agent RAG queries, measures latencies,
    and validates p50 and p95 latency thresholds.
    """
    supervisor = stress_environment
    queries = [
        "What records must data controllers maintain under Article 30?",
        "What are the whistleblower protection rules under EU Directive?",
        "What is the frequency of vulnerability scans?",
        "What records must data controllers maintain under Article 30?",
        "What are the whistleblower protection rules under EU Directive?",
        "What is the frequency of vulnerability scans?",
        "What records must data controllers maintain under Article 30?",
        "What are the whistleblower protection rules under EU Directive?",
        "What is the frequency of vulnerability scans?",
        "What records must data controllers maintain under Article 30?",
    ]

    async def timed_query(q: str):
        start = time.perf_counter()
        res = await supervisor.run_pipeline(
            tenant_id="tenant_stress_eu",
            user_query=q
        )
        elapsed = time.perf_counter() - start
        return res, elapsed

    # Run all queries concurrently
    tasks = [timed_query(q) for q in queries]
    results_and_times = await asyncio.gather(*tasks)

    latencies = [t for _, t in results_and_times]
    statuses = [r.status for r, _ in results_and_times]

    assert all(s == "SUCCESS" for s in statuses)

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    avg_latency = sum(latencies) / len(latencies)

    print(f"\n[Stress Benchmark Results] Queries: {len(queries)} | Avg: {avg_latency*1000:.1f}ms | p50: {p50*1000:.1f}ms | p95: {p95*1000:.1f}ms")

    # Assert sub-second throughput and latency guarantees
    assert p50 < 0.50, f"p50 latency ({p50:.3f}s) exceeded 500ms target"
    assert p95 < 1.00, f"p95 latency ({p95:.3f}s) exceeded 1000ms target"
