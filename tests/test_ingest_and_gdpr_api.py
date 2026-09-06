"""
Integration and End-to-End API Tests for Ingestion, PII Sanitization, RBAC Auth, and GDPR Erasure.
"""

import pytest
from httpx import AsyncClient
from src.config import settings


@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: AsyncClient):
    """Verifies that the API health endpoint reports calibrated compliance posture."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["gdpr_compliance"] == "ACTIVE"
    assert "MINIMAL_LOW_RISK" in data["eu_ai_act_classification"]
    assert "Presidio" in data["pii_engine"]


@pytest.mark.asyncio
async def test_rbac_unauthenticated_requests_rejected(async_client: AsyncClient):
    """Verifies that operational API routes reject unauthenticated requests with HTTP 401."""
    # 1. Ingestion without key
    ingest_resp = await async_client.post("/api/v1/ingest", json={"tenant_id": "t1", "title": "Doc", "content": "Text"})
    assert ingest_resp.status_code == 401
    assert "Missing 'X-API-Key'" in ingest_resp.json()["detail"]

    # 2. Erasure without key
    erasure_resp = await async_client.post("/api/v1/gdpr/erasure", json={"tenant_id": "t1", "doc_id": "doc1"})
    assert erasure_resp.status_code == 401

    # 3. Query without key
    query_resp = await async_client.post("/api/v1/query", json={"tenant_id": "t1", "query": "What is the policy?"})
    assert query_resp.status_code == 401


@pytest.mark.asyncio
async def test_rbac_invalid_key_rejected(async_client: AsyncClient):
    """Verifies that requests with invalid API keys are rejected with HTTP 401."""
    headers = {"X-API-Key": "invalid-hacker-key-999"}
    resp = await async_client.post("/api/v1/ingest", json={"tenant_id": "t1", "title": "Doc", "content": "Text"}, headers=headers)
    assert resp.status_code == 401
    assert "Invalid API Key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_rbac_role_permissions_and_forbidden_actions(async_client: AsyncClient):
    """Verifies that Employee role is forbidden (403) from executing GDPR Erasure, while DPO succeeds."""
    employee_headers = {"X-API-Key": settings.API_KEY_EMPLOYEE}
    dpo_headers = {"X-API-Key": settings.API_KEY_DPO}

    # 1. Employee tries to call GDPR Erasure -> 403 Forbidden
    erasure_payload = {"tenant_id": "tenant_test", "key_id": "fake_key_123", "reason": "Test"}
    emp_erasure_resp = await async_client.post("/api/v1/gdpr/erasure", json=erasure_payload, headers=employee_headers)
    assert emp_erasure_resp.status_code == 403
    assert "Access forbidden" in emp_erasure_resp.json()["detail"]

    # 2. DPO calling keys list -> 200 OK
    keys_resp = await async_client.get("/api/v1/gdpr/keys/tenant_test", headers=dpo_headers)
    assert keys_resp.status_code == 200


@pytest.mark.asyncio
async def test_ingest_document_with_pii_sanitization(async_client: AsyncClient):
    """Verifies document ingestion, automatic PII masking, chunk generation, and key assignment."""
    headers = {"X-API-Key": settings.API_KEY_EMPLOYEE}
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

    response = await async_client.post("/api/v1/ingest", json=payload, headers=headers)
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
    1. Ingest document with employee role
    2. Execute crypto-shredding with DPO role
    3. Verify document key is revoked and audit ledger records cryptographic deletion receipt
    """
    emp_headers = {"X-API-Key": settings.API_KEY_EMPLOYEE}
    dpo_headers = {"X-API-Key": settings.API_KEY_DPO}

    # 1. Ingest
    ingest_payload = {
        "tenant_id": "tenant_privacy_fr",
        "title": "Customer Data Export",
        "content": "Customer Dr. Jean Dupont with email jean.dupont@paris.fr.",
        "actor_id": "crm_sync"
    }
    ingest_resp = await async_client.post("/api/v1/ingest", json=ingest_payload, headers=emp_headers)
    assert ingest_resp.status_code == 201
    doc_id = ingest_resp.json()["doc_id"]
    key_id = ingest_resp.json()["key_id"]

    # 2. Execute Right to Erasure as DPO
    erasure_payload = {
        "tenant_id": "tenant_privacy_fr",
        "doc_id": doc_id,
        "actor_id": "dpo_officer_01",
        "reason": "Customer withdrawn consent under GDPR Article 17"
    }
    erasure_resp = await async_client.post("/api/v1/gdpr/erasure", json=erasure_payload, headers=dpo_headers)
    assert erasure_resp.status_code == 200
    erasure_data = erasure_resp.json()
    assert erasure_data["status"] == "ERASED_CRYPTOGRAPHICALLY"
    assert erasure_data["shredded_key_id"] == key_id
    assert "audit_event_id" in erasure_data

    # 3. Verify key is marked revoked
    status_resp = await async_client.get(f"/api/v1/ingest/{doc_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["is_key_revoked"] is True

    # 4. Check audit log for deletion record as DPO
    audit_resp = await async_client.get("/api/v1/gdpr/audit-log?event_type=CRYPTO_SHRED_RIGHT_TO_ERASURE", headers=dpo_headers)
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 1
    assert logs[-1]["details"]["shredded_key_id"] == key_id

