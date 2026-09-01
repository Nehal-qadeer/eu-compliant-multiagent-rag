"""
Integration and End-to-End API Tests for Ingestion, PII Sanitization, and GDPR Erasure.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: AsyncClient):
    """Verifies that the API health endpoint reports GDPR and EU AI Act readiness."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["gdpr_compliance"] == "ACTIVE"
    assert data["eu_ai_act_mode"] == "HIGH_RISK_AUDIT_READY"


@pytest.mark.asyncio
async def test_ingest_document_with_pii_sanitization(async_client: AsyncClient):
    """Verifies document ingestion, automatic PII masking, chunk generation, and key assignment."""
    payload = {
        "tenant_id": "enterprise_corp_de",
        "title": "Employee Handbook 2026",
        "content": """# Chapter 1: Onboarding
Welcome new team member. Please reach out to Dr. Klaus Schmidt at klaus.schmidt@enterprise.de.
Salary accounts must be registered with IBAN: DE89370400440532013000.

# Chapter 2: IT Security
Internal server gateway is reachable at 10.0.0.1.""",
        "source_type": "markdown",
        "actor_id": "hr_lead"
    }

    response = await async_client.post("/api/v1/ingest", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["tenant_id"] == "enterprise_corp_de"
    assert data["has_pii"] is True
    assert data["total_pii_entities"] >= 2
    assert len(data["chunks_preview"]) >= 2
    assert "key_id" in data
    assert "audit_event_id" in data["compliance_proof"]

    # Retrieve document status
    doc_id = data["doc_id"]
    status_resp = await async_client.get(f"/api/v1/ingest/{doc_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["is_key_revoked"] is False


@pytest.mark.asyncio
async def test_gdpr_article_17_crypto_shredding_flow(async_client: AsyncClient):
    """
    Verifies end-to-end GDPR Right to Erasure flow:
    1. Ingest document
    2. Execute crypto-shredding
    3. Verify document key is revoked and audit ledger records cryptographic deletion receipt
    """
    # 1. Ingest
    ingest_payload = {
        "tenant_id": "tenant_privacy_fr",
        "title": "Customer Data Export",
        "content": "Customer Dr. Jean Dupont with email jean.dupont@paris.fr.",
        "actor_id": "crm_sync"
    }
    ingest_resp = await async_client.post("/api/v1/ingest", json=ingest_payload)
    assert ingest_resp.status_code == 201
    doc_id = ingest_resp.json()["doc_id"]
    key_id = ingest_resp.json()["key_id"]

    # 2. Execute Right to Erasure
    erasure_payload = {
        "tenant_id": "tenant_privacy_fr",
        "doc_id": doc_id,
        "actor_id": "dpo_officer_01",
        "reason": "Customer withdrawn consent under GDPR Article 17"
    }
    erasure_resp = await async_client.post("/api/v1/gdpr/erasure", json=erasure_payload)
    assert erasure_resp.status_code == 200
    erasure_data = erasure_resp.json()
    assert erasure_data["status"] == "ERASED_CRYPTOGRAPHICALLY"
    assert erasure_data["shredded_key_id"] == key_id
    assert "audit_event_id" in erasure_data

    # 3. Verify key is marked revoked
    status_resp = await async_client.get(f"/api/v1/ingest/{doc_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["is_key_revoked"] is True

    # 4. Check audit log for deletion record
    audit_resp = await async_client.get("/api/v1/gdpr/audit-log?event_type=CRYPTO_SHRED_RIGHT_TO_ERASURE")
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 1
    assert logs[-1]["details"]["shredded_key_id"] == key_id
