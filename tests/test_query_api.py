"""
End-to-End API Integration Tests for Multi-Agent Query Endpoint (/api/v1/query).
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_rag_ingest_and_query_flow(async_client: AsyncClient):
    """
    End-to-End Test:
    1. Ingest compliance document via API.
    2. Query multi-agent RAG endpoint.
    3. Assert grounded answer, citations, transparency watermark, and audit trail record.
    """
    # 1. Ingest
    ingest_payload = {
        "tenant_id": "corp_berlin_01",
        "title": "AI Risk Governance Policy",
        "content": """# Chapter 1: High-Risk AI Classification
Systems performing biometric identification or employment screening are classified as High-Risk AI under EU AI Act Article 6.
Such systems must maintain comprehensive technical documentation and human oversight logs.

# Chapter 2: Transparency Obligations
All GPAI models interacting with European citizens must provide machine-readable watermarks and source disclosures.""",
        "source_type": "markdown",
        "actor_id": "compliance_lead"
    }

    ingest_res = await async_client.post("/api/v1/ingest", json=ingest_payload)
    assert ingest_res.status_code == 201

    # 2. Query
    query_payload = {
        "tenant_id": "corp_berlin_01",
        "query": "What systems are classified as High-Risk AI under the policy?",
        "actor_id": "auditor_elena"
    }

    query_res = await async_client.post("/api/v1/query", json=query_payload)
    assert query_res.status_code == 200
    data = query_res.json()

    assert data["status"] == "SUCCESS"
    assert "High-Risk AI" in data["answer"] or "biometric identification" in data["answer"]
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["doc_title"] == "AI Risk Governance Policy"
    assert data["faithfulness_score"] >= 0.70
    assert "EU AI Act Transparency Notice" in data["eu_transparency_disclaimer"]
    assert "audit_event_id" in data


@pytest.mark.asyncio
async def test_query_insufficient_context_fallback(async_client: AsyncClient):
    """Verifies that queries completely outside of indexed documents trigger safe fallback without hallucination."""
    query_payload = {
        "tenant_id": "corp_berlin_01",
        "query": "What is the secret recipe for volcanic fusion fuel?",
        "actor_id": "curious_user"
    }

    query_res = await async_client.post("/api/v1/query", json=query_payload)
    assert query_res.status_code == 200
    data = query_res.json()

    assert data["status"] == "INSUFFICIENT_CONTEXT"
    assert "Insufficient context in verified enterprise documents" in data["answer"]
    assert len(data["citations"]) == 0
