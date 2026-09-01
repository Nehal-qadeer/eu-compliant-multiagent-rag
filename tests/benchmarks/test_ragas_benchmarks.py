"""
Automated RAGAS / DeepEval Benchmark Test Suite.
Validates Faithfulness, Answer Relevance, Context Precision, and Context Recall
across an enterprise compliance test corpus.
"""

import pytest
from src.eval.ragas_evaluator import RagasEvaluator
from src.agents.supervisor import MultiAgentSupervisor
from src.rag.vector_store import SovereignVectorStore
from src.rag.chunking import ContextualChunker, IngestionDocument
from src.core.security import KeyVaultManager
from src.rag.hybrid_search import HybridSearchEngine
from src.agents.retrieval_agent import RetrievalAgent


BENCHMARK_DATASET = [
    {
        "query": "What is the mandatory timeline to notify authorities after a data breach?",
        "ground_truth": "Under GDPR Article 33, personal data breaches must be reported to the supervisory authority within 72 hours of becoming aware.",
        "expected_section": "Breach Notification"
    },
    {
        "query": "How are biometric identification systems classified under the EU AI Act?",
        "ground_truth": "Biometric identification systems are categorized as High-Risk AI under Article 6 of the EU AI Act.",
        "expected_section": "High-Risk AI"
    },
    {
        "query": "What cryptographic method is used for Right to be Forgotten data erasure?",
        "ground_truth": "Cryptographic shredding revokes the AES-256 key, rendering all indexed document vectors and cached ciphertexts permanently unrecoverable.",
        "expected_section": "Cryptographic Shredding"
    }
]


@pytest.fixture
def benchmark_rag_environment(fresh_key_vault: KeyVaultManager):
    """Sets up a populated knowledge base for RAGAS evaluation."""
    store = SovereignVectorStore(key_vault=fresh_key_vault)
    chunker = ContextualChunker()

    doc_content = """# Breach Notification
Under GDPR Article 33, personal data breaches must be reported to the supervisory authority within 72 hours of becoming aware.
Failure to notify may result in severe administrative fines under GDPR enforcement frameworks.

# High-Risk AI
Biometric identification systems are categorized as High-Risk AI under Article 6 of the EU AI Act.
Providers must maintain detailed risk management logs and continuous post-market monitoring.

# Cryptographic Shredding
Cryptographic shredding revokes the AES-256 key, rendering all indexed document vectors and cached ciphertexts permanently unrecoverable.
This provides instant Article 17 erasure compliance without re-indexing vector stores."""

    doc = IngestionDocument(
        tenant_id="tenant_benchmark_eu",
        title="EU Regulatory Handbook",
        content=doc_content
    )
    key_id = fresh_key_vault.generate_key(tenant_id="tenant_benchmark_eu", subject_id=doc.doc_id)
    chunks = chunker.chunk_document(doc)
    store.index_chunks(tenant_id="tenant_benchmark_eu", chunks=chunks, key_id=key_id)

    hybrid = HybridSearchEngine(vector_store=store)
    retriever = RetrievalAgent(hybrid_engine=hybrid)
    supervisor = MultiAgentSupervisor(retrieval_agent=retriever)

    return supervisor, store


@pytest.mark.asyncio
async def test_ragas_metrics_across_benchmark_corpus(benchmark_rag_environment):
    """
    Executes full multi-agent RAG on the benchmark dataset and asserts
    that Faithfulness, Answer Relevance, Context Precision, and Context Recall all pass.
    """
    supervisor, store = benchmark_rag_environment
    evaluator = RagasEvaluator(
        faithfulness_threshold=0.80,
        relevance_threshold=0.70,
        precision_threshold=0.60,
        recall_threshold=0.70
    )

    reports = []

    for item in BENCHMARK_DATASET:
        rag_result = await supervisor.run_pipeline(
            tenant_id="tenant_benchmark_eu",
            user_query=item["query"]
        )

        assert rag_result.status == "SUCCESS"
        contexts = [
            store._namespaces["tenant_benchmark_eu"][c.chunk_id].content
            for c in rag_result.citations
            if c.chunk_id in store._namespaces.get("tenant_benchmark_eu", {})
        ]

        report = evaluator.evaluate_triad(
            query=item["query"],
            answer=rag_result.answer,
            contexts=contexts,
            ground_truth=item["ground_truth"]
        )

        reports.append(report)

        # Assert individual metrics
        assert report.faithfulness.passed, f"Faithfulness failed for query: {item['query']} ({report.faithfulness.score})"
        assert report.answer_relevance.passed, f"Relevance failed for query: {item['query']} ({report.answer_relevance.score})"
        assert report.overall_quality_score >= 0.70, f"Overall quality score ({report.overall_quality_score}) below threshold."

    # Mean overall score across dataset
    avg_score = sum(r.overall_quality_score for r in reports) / len(reports)
    assert avg_score >= 0.75, f"Average RAGAS quality score ({avg_score:.3f}) must exceed 0.75"
