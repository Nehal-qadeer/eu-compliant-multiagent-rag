"""
Rigorous QA Tests for Multi-Agent Personas and Supervisor Orchestration Pipeline.
"""

import pytest
from src.agents.query_planner import QueryPlannerAgent
from src.agents.verifier_agent import VerifierAgent
from src.agents.synthesizer_agent import ResponseSynthesizerAgent
from src.agents.supervisor import MultiAgentSupervisor
from src.rag.vector_store import SovereignVectorStore, SearchResult
from src.rag.hybrid_search import HybridSearchEngine
from src.rag.reranker import CrossEncoderReranker
from src.core.security import KeyVaultManager
from src.core.pii_sanitizer import PIISanitizer
from src.core.audit_logger import AuditLogger


def test_query_planner_decomposition():
    """Verifies that QueryPlanner decomposes multi-faceted questions into atomic subqueries."""
    planner = QueryPlannerAgent()

    # Simple query
    plan_simple = planner.plan_query("What is the data retention period under GDPR?")
    assert plan_simple.is_complex is False
    assert len(plan_simple.subqueries) == 1

    # Complex comparative query
    plan_complex = planner.plan_query("Compare GDPR Article 17 erasure timeline versus data breach notification rules?")
    assert plan_complex.is_complex is True
    assert len(plan_complex.subqueries) >= 2


def test_verifier_agent_pre_and_post_gates():
    """Verifies pre-LLM context validation and post-LLM hallucination checking."""
    verifier = VerifierAgent(min_context_relevance=0.15, min_faithfulness=0.80)

    # 1. Pre-LLM Gate (Insufficient Context)
    insufficient_res = verifier.validate_retrieval_context("quantum physics teleportation", candidates=[])
    assert insufficient_res.is_sufficient is False

    # 2. Pre-LLM Gate (Sufficient Context)
    sample_candidate = SearchResult(
        chunk_id="c1",
        doc_id="d1",
        tenant_id="t1",
        content="Under Article 17, personal data must be erased without undue delay.",
        score=0.85,
        section_title="Erasure Policy",
        metadata={"title": "GDPR Standard"}
    )
    sufficient_res = verifier.validate_retrieval_context("erasure policy", candidates=[sample_candidate])
    assert sufficient_res.is_sufficient is True

    # 3. Post-LLM Gate (Faithful Response)
    faithful_resp = verifier.verify_response_faithfulness(
        synthesized_text="Under Article 17, personal data must be erased without undue delay.",
        context_chunks=[sample_candidate]
    )
    assert faithful_resp.is_faithful is True
    assert faithful_resp.faithfulness_score >= 0.80
    assert faithful_resp.hallucination_detected is False

    # 4. Post-LLM Gate (Hallucinated Unsupported Response)
    hallucinated_resp = verifier.verify_response_faithfulness(
        synthesized_text="The company guarantees 100% cloud revenue growth by deploying satellite constellations.",
        context_chunks=[sample_candidate]
    )
    assert hallucinated_resp.is_faithful is False
    assert hallucinated_resp.hallucination_detected is True


@pytest.mark.asyncio
async def test_supervisor_end_to_end_pipeline(fresh_key_vault: KeyVaultManager, tmp_path):
    """Verifies end-to-end multi-agent pipeline orchestration with audit logging."""
    store = SovereignVectorStore(key_vault=fresh_key_vault)
    audit = AuditLogger(log_file_path=str(tmp_path / "supervisor_audit.jsonl"))

    # Ingest document
    from src.rag.chunking import ContextualChunker, IngestionDocument
    chunker = ContextualChunker()
    doc = IngestionDocument(
        tenant_id="tenant_audit_de",
        title="Security Guidelines",
        content="# Access Control\nAll API endpoints require Bearer Token authorization with TLS 1.3 encryption."
    )
    key_id = fresh_key_vault.generate_key(tenant_id="tenant_audit_de", subject_id=doc.doc_id)
    chunks = chunker.chunk_document(doc)
    store.index_chunks(tenant_id="tenant_audit_de", chunks=chunks, key_id=key_id)

    from src.rag.hybrid_search import HybridSearchEngine
    from src.agents.retrieval_agent import RetrievalAgent

    hybrid_engine = HybridSearchEngine(vector_store=store)
    retrieval_agent = RetrievalAgent(hybrid_engine=hybrid_engine)

    supervisor = MultiAgentSupervisor(
        retrieval_agent=retrieval_agent,
        audit_logger=audit
    )

    # Execute Query
    result = await supervisor.run_pipeline(
        tenant_id="tenant_audit_de",
        user_query="What are the security requirements for API endpoints?",
        actor_id="auditor_01"
    )

    assert result.status == "SUCCESS"
    assert result.is_faithful is True
    assert len(result.citations) >= 1
    assert "Bearer Token" in result.answer or "TLS 1.3" in result.answer
    assert "EU AI Act Transparency Notice" in result.eu_transparency_disclaimer
