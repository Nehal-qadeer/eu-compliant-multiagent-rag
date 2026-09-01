"""
GDPR Compliance & Right to Erasure (Article 17) API Routes.
Provides cryptographic shredding operations and audit trail verification endpoints.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.core.security import global_key_vault, KeyMetadata, KeyRevokedError
from src.core.audit_logger import global_audit_logger, AuditEvent
from src.api.routes.ingest import ingested_documents_store

router = APIRouter(prefix="/api/v1/gdpr", tags=["GDPR & AI Act Compliance"])


class ErasureRequest(BaseModel):
    """Payload for GDPR Article 17 Right to Erasure request."""
    tenant_id: str = Field(..., description="Tenant identifier")
    actor_id: str = Field(default="dpo_officer", description="Identity of requester / DPO")
    key_id: Optional[str] = Field(default=None, description="Specific cryptographic key to shred")
    doc_id: Optional[str] = Field(default=None, description="Document ID whose key should be shredded")
    reason: str = Field(default="GDPR Article 17 Right to Erasure", description="Legal basis or reason for erasure")


class ErasureResponse(BaseModel):
    """Cryptographic proof of deletion."""
    status: str
    tenant_id: str
    shredded_key_id: str
    revoked_at: str
    reason: str
    audit_event_id: str
    record_hash: str
    message: str


@router.post("/erasure", response_model=ErasureResponse, status_code=status.HTTP_200_OK)
async def execute_right_to_erasure(payload: ErasureRequest):
    """
    Executes GDPR Article 17 Cryptographic Shredding.
    Permanently destroys the AES-256 encryption key associated with the subject/document,
    rendering any stored or cached embeddings and ciphertexts mathematically unrecoverable.
    """
    target_key_id = payload.key_id

    # If doc_id was provided instead of key_id, resolve it
    if not target_key_id and payload.doc_id:
        if payload.doc_id in ingested_documents_store:
            target_key_id = ingested_documents_store[payload.doc_id]["key_id"]
        else:
            raise HTTPException(status_code=404, detail=f"Document '{payload.doc_id}' not found.")

    if not target_key_id:
        raise HTTPException(status_code=400, detail="Must provide either 'key_id' or 'doc_id' for erasure.")

    try:
        # Revoke & shred the cryptographic key material
        revoked_meta = global_key_vault.revoke_key(key_id=target_key_id, reason=payload.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Key '{target_key_id}' does not exist.")

    # Record immutable audit proof of cryptographic deletion (GDPR Art. 17 & EU AI Act Art. 12)
    audit_evt = global_audit_logger.log_event(
        event_type="CRYPTO_SHRED_RIGHT_TO_ERASURE",
        tenant_id=payload.tenant_id,
        actor_id=payload.actor_id,
        raw_content_to_hash=f"SHRED:{target_key_id}:{revoked_meta.revoked_at}",
        details={
            "shredded_key_id": target_key_id,
            "doc_id": payload.doc_id,
            "revocation_reason": payload.reason,
            "revoked_at": revoked_meta.revoked_at
        },
        compliance_tags=["GDPR_ART_17_RIGHT_TO_ERASURE", "CRYPTOGRAPHIC_SHREDDING"]
    )

    return ErasureResponse(
        status="ERASED_CRYPTOGRAPHICALLY",
        tenant_id=payload.tenant_id,
        shredded_key_id=target_key_id,
        revoked_at=revoked_meta.revoked_at or "",
        reason=payload.reason,
        audit_event_id=audit_evt.event_id,
        record_hash=audit_evt.record_hash or "",
        message="Cryptographic key destroyed. All associated document vectors and stored representations are permanently unrecoverable."
    )


@router.get("/keys/{tenant_id}", response_model=List[Dict[str, Any]])
async def list_tenant_keys(tenant_id: str):
    """Lists all cryptographic keys for a given tenant and their active/shredded status."""
    keys = global_key_vault.list_keys_for_tenant(tenant_id)
    return [
        {
            "key_id": meta.key_id,
            "subject_id": meta.subject_id,
            "created_at": meta.created_at,
            "is_revoked": meta.is_revoked,
            "revoked_at": meta.revoked_at,
            "revocation_reason": meta.revocation_reason
        }
        for meta in keys.values()
    ]


@router.get("/audit-log", response_model=List[AuditEvent])
async def get_audit_trail(
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, le=200, description="Max number of records")
):
    """Queries the immutable tamper-evident audit ledger for regulatory inspection."""
    return global_audit_logger.query_logs(tenant_id=tenant_id, event_type=event_type, limit=limit)
