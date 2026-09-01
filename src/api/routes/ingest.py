"""
Document Ingestion & PII Redaction API Route.
Handles multi-format document ingestion, automated PII sanitization, and cryptographic key assignment.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.rag.chunking import IngestionDocument, global_chunker, DocumentChunk
from src.rag.vector_store import global_vector_store
from src.core.security import global_key_vault
from src.core.audit_logger import global_audit_logger

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion & Privacy"])


class IngestRequest(BaseModel):
    """Payload for submitting a document for ingestion."""
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document text or markdown content")
    source_type: str = Field(default="markdown", description="Document type: markdown, text, pdf")
    actor_id: str = Field(default="system_admin", description="ID of user or service ingesting document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional custom metadata")


class IngestResponse(BaseModel):
    """Response returned upon successful document ingestion and chunking."""
    doc_id: str
    tenant_id: str
    title: str
    key_id: str
    total_chunks: int
    has_pii: bool
    total_pii_entities: int
    chunks_preview: List[Dict[str, Any]]
    compliance_proof: Dict[str, str]


# In-memory document index store for tracking ingested document state
ingested_documents_store: Dict[str, Dict[str, Any]] = {}


@router.post("", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_document(payload: IngestRequest):
    """
    Ingests an enterprise document, generates a dedicated cryptographic key for GDPR compliance,
    sanitizes PII via Presidio/NER, produces context-aware chunks, and records an immutable audit log.
    """
    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="Document content cannot be empty.")

    # 1. Create Ingestion Document object
    doc = IngestionDocument(
        tenant_id=payload.tenant_id,
        title=payload.title,
        content=payload.content,
        source_type=payload.source_type,
        metadata=payload.metadata
    )

    # 2. Generate a dedicated AES-256 Key for this document in the Key Vault (GDPR Art. 17 Ready)
    key_id = global_key_vault.generate_key(
        tenant_id=payload.tenant_id,
        subject_id=doc.doc_id
    )

    # 3. Contextual Chunking + PII Sanitization
    chunks: List[DocumentChunk] = global_chunker.chunk_document(doc, sanitize_pii=True)

    has_pii = any(c.has_pii for c in chunks)
    total_pii_entities = sum(len(c.pseudonym_map) for c in chunks)

    # 4. Index Chunks in Tenant-Isolated Vector Store
    global_vector_store.index_chunks(
        tenant_id=payload.tenant_id,
        chunks=chunks,
        key_id=key_id
    )

    # 5. Record Immutable Audit Event (GDPR Art. 25 & EU AI Act Art. 12)
    audit_evt = global_audit_logger.log_event(
        event_type="INGESTION_AND_PII_REDACTION",
        tenant_id=payload.tenant_id,
        actor_id=payload.actor_id,
        raw_content_to_hash=payload.content,
        details={
            "doc_id": doc.doc_id,
            "title": payload.title,
            "key_id": key_id,
            "total_chunks": len(chunks),
            "has_pii": has_pii,
            "total_pii_detected": total_pii_entities
        },
        compliance_tags=["GDPR_ART_25_PRIVACY_BY_DESIGN", "EU_AI_ACT_ART_12_RECORD_KEEPING"]
    )

    # 5. Persist document metadata in registry
    ingested_documents_store[doc.doc_id] = {
        "doc_id": doc.doc_id,
        "tenant_id": doc.tenant_id,
        "title": doc.title,
        "key_id": key_id,
        "chunks": chunks,
        "total_chunks": len(chunks),
        "audit_event_id": audit_evt.event_id,
        "record_hash": audit_evt.record_hash
    }

    chunks_preview = [
        {
            "chunk_id": c.chunk_id,
            "section": c.section_title,
            "token_count": c.token_count,
            "has_pii": c.has_pii,
            "preview": c.content[:160] + "..." if len(c.content) > 160 else c.content
        }
        for c in chunks[:5]  # Preview top 5 chunks
    ]

    return IngestResponse(
        doc_id=doc.doc_id,
        tenant_id=doc.tenant_id,
        title=doc.title,
        key_id=key_id,
        total_chunks=len(chunks),
        has_pii=has_pii,
        total_pii_entities=total_pii_entities,
        chunks_preview=chunks_preview,
        compliance_proof={
            "audit_event_id": audit_evt.event_id,
            "record_hash": audit_evt.record_hash or "",
            "gdpr_status": "PII_Pseudonymized_At_Rest",
            "crypto_key_id": key_id
        }
    )


@router.get("/{doc_id}")
async def get_document_status(doc_id: str):
    """Retrieves metadata and chunk status for an ingested document."""
    if doc_id not in ingested_documents_store:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")
    
    doc_info = ingested_documents_store[doc_id]
    key_meta = global_key_vault.get_metadata(doc_info["key_id"])

    return {
        "doc_id": doc_info["doc_id"],
        "tenant_id": doc_info["tenant_id"],
        "title": doc_info["title"],
        "total_chunks": doc_info["total_chunks"],
        "key_id": doc_info["key_id"],
        "is_key_revoked": key_meta.is_revoked if key_meta else False,
        "audit_event_id": doc_info["audit_event_id"],
        "record_hash": doc_info["record_hash"]
    }
