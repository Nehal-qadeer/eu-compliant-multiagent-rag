"""
Rigorous QA Tests for Hybrid Search (Dense Vectors + BM25 Sparse) and Cross-Encoder Reranking.
"""

import pytest
from src.rag.chunking import ContextualChunker, IngestionDocument
from src.rag.vector_store import SovereignVectorStore
from src.rag.hybrid_search import HybridSearchEngine
from src.rag.reranker import CrossEncoderReranker
from src.core.security import KeyVaultManager


@pytest.fixture
def populated_vector_store(fresh_key_vault: KeyVaultManager, contextual_chunker: ContextualChunker):
    """Provides a vector store populated with sample compliance documents."""
    store = SovereignVectorStore(key_vault=fresh_key_vault)

    doc_content = """# Data Protection Standard
All customer records must be pseudonymized before transmission.
Article 17 requests must be processed within 30 calendar days.

# Incident Response Procedure
In the event of a personal data breach, notify the supervisory authority within 72 hours.
All breach containment records are maintained in the secure audit ledger."""

    doc = IngestionDocument(
        tenant_id="tenant_qa_eu",
        title="EU Compliance Standard",
        content=doc_content
    )
    key_id = fresh_key_vault.generate_key(tenant_id="tenant_qa_eu", subject_id=doc.doc_id)
    chunks = contextual_chunker.chunk_document(doc, sanitize_pii=True)
    store.index_chunks(tenant_id="tenant_qa_eu", chunks=chunks, key_id=key_id)

    return store, key_id


def test_dense_similarity_search(populated_vector_store):
    """Verifies dense semantic vector similarity retrieval."""
    store, _ = populated_vector_store
    results = store.search_dense(tenant_id="tenant_qa_eu", query="data breach notification 72 hours", top_k=2)

    assert len(results) > 0
    assert "Incident Response" in results[0].section_title
    assert results[0].score > 0.0


def test_hybrid_rrf_combines_dense_and_sparse(populated_vector_store):
    """Verifies that Hybrid Search merges Dense and BM25 Sparse ranks using RRF."""
    store, _ = populated_vector_store
    hybrid = HybridSearchEngine(vector_store=store)

    results = hybrid.search_hybrid(
        tenant_id="tenant_qa_eu",
        query="Article 17 right to erasure 30 days",
        top_k=2
    )

    assert len(results) > 0
    assert results[0].retrieval_method == "hybrid_rrf"
    assert "Data Protection" in results[0].section_title


def test_cross_encoder_reranking_accuracy(populated_vector_store):
    """Verifies that the Cross-Encoder reorders candidates to prioritize highest relevance."""
    store, _ = populated_vector_store
    hybrid = HybridSearchEngine(vector_store=store)
    reranker = CrossEncoderReranker()

    candidates = hybrid.search_hybrid(tenant_id="tenant_qa_eu", query="personal data breach supervisory authority", top_k=4)
    reranked = reranker.rerank(query="personal data breach supervisory authority", candidates=candidates, top_k=2)

    assert len(reranked) > 0
    assert "Incident Response" in reranked[0].section_title
    assert reranked[0].score > 0.20
