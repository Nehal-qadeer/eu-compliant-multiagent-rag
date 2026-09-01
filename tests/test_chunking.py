"""
Rigorous Tests for Contextual & Hierarchical Document Chunking with PII Sanitization.
"""

import pytest
from src.rag.chunking import ContextualChunker, IngestionDocument


def test_chunking_with_markdown_sections(contextual_chunker: ContextualChunker):
    """Verifies that markdown headings are extracted and enriched into chunk metadata."""
    content = """# Corporate Privacy Policy

This policy governs the handling of all enterprise data.

## Section 1: Data Retention
Data shall be retained for 3 years unless an Article 17 erasure request is received.

## Section 2: Contact Information
For privacy inquiries, contact Dr. Jane Doe at dpo@enterprise.eu."""

    doc = IngestionDocument(
        tenant_id="tenant_001",
        title="Privacy Guidelines 2026",
        content=content,
        source_type="markdown",
        metadata={"department": "Compliance"}
    )

    chunks = contextual_chunker.chunk_document(doc, sanitize_pii=True)

    assert len(chunks) >= 2
    assert all(c.tenant_id == "tenant_001" for c in chunks)
    assert all(c.doc_id == doc.doc_id for c in chunks)

    # Check section title preservation
    section_titles = [c.section_title for c in chunks]
    assert any("Section 1: Data Retention" in s for s in section_titles)
    assert any("Section 2: Contact Information" in s for s in section_titles)

    # Verify PII was sanitized inside chunks
    contact_chunk = next(c for c in chunks if "Section 2" in c.section_title)
    assert "dpo@enterprise.eu" not in contact_chunk.content
    assert "<EMAIL_ADDRESS_01>" in contact_chunk.content
    assert contact_chunk.has_pii is True
