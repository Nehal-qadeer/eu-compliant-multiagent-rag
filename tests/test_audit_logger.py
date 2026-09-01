"""
Rigorous Tests for Tamper-Evident Immutable Audit Logger (EU AI Act Art. 12 & GDPR).
"""

import pytest
from src.core.audit_logger import AuditLogger


def test_audit_event_hash_chaining(temp_audit_logger: AuditLogger):
    """Verifies that audit events are securely hashed and chained sequentially."""
    evt1 = temp_audit_logger.log_event(
        event_type="INGESTION",
        tenant_id="tenant_de",
        actor_id="admin_01",
        raw_content_to_hash="document_payload_one",
        details={"doc_id": "doc_1"}
    )
    assert evt1.prev_record_hash is None
    assert evt1.record_hash is not None

    evt2 = temp_audit_logger.log_event(
        event_type="PII_REDACTION",
        tenant_id="tenant_de",
        actor_id="admin_01",
        raw_content_to_hash="document_payload_two",
        details={"doc_id": "doc_2"}
    )
    assert evt2.prev_record_hash == evt1.record_hash
    assert evt2.record_hash is not None
    assert evt2.record_hash != evt1.record_hash


def test_audit_log_querying_and_filtering(temp_audit_logger: AuditLogger):
    """Verifies log retrieval filtered by tenant or event type."""
    temp_audit_logger.log_event("INGESTION", "tenant_a", "actor_1", "content_a")
    temp_audit_logger.log_event("CRYPTO_SHRED", "tenant_a", "dpo_1", "content_shred")
    temp_audit_logger.log_event("INGESTION", "tenant_b", "actor_2", "content_b")

    # Filter by tenant
    tenant_a_logs = temp_audit_logger.query_logs(tenant_id="tenant_a")
    assert len(tenant_a_logs) == 2

    # Filter by event type
    shred_logs = temp_audit_logger.query_logs(event_type="CRYPTO_SHRED")
    assert len(shred_logs) == 1
    assert shred_logs[0].tenant_id == "tenant_a"
