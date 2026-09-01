"""
Contextual & Hierarchical Chunking Engine for Enterprise RAG.
Splits enterprise documents along markdown headings, paragraphs, and sentence boundaries,
attaching rich metadata and applying PII sanitization.
"""

import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from src.core.pii_sanitizer import PIISanitizer, global_pii_sanitizer


@dataclass
class DocumentChunk:
    """Represents an enriched, PII-sanitized chunk of text for vector indexing."""
    chunk_id: str
    doc_id: str
    tenant_id: str
    content: str
    raw_content_preview: str
    section_title: str
    chunk_index: int
    token_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    has_pii: bool = False
    pseudonym_map: Dict[str, str] = field(default_factory=dict)


class IngestionDocument(BaseModel):
    """Input enterprise document submitted for ingestion."""
    doc_id: str = Field(default_factory=lambda: f"doc_{uuid.uuid4().hex[:12]}")
    tenant_id: str
    title: str
    content: str
    source_type: str = "markdown"  # markdown, text, pdf, docx
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextualChunker:
    """
    Context-aware hierarchical document chunker.
    Preserves document structure (headings, bullet lists) and applies PII pseudonymization.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        pii_sanitizer: Optional[PIISanitizer] = None
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.pii_sanitizer = pii_sanitizer or global_pii_sanitizer

    def _estimate_tokens(self, text: str) -> int:
        """Heuristic estimation of tokens (approx 4 chars per token for English/EU text)."""
        words = text.split()
        return max(1, int(len(words) * 1.3))

    def _split_into_sections(self, content: str) -> List[Tuple[str, str]]:
        """Splits markdown/text into sections identified by markdown headings (#, ##, ###)."""
        lines = content.splitlines()
        sections = []
        current_title = "Introduction / Overview"
        current_lines = []

        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

        for line in lines:
            match = heading_pattern.match(line)
            if match:
                if current_lines:
                    sections.append((current_title, "\n".join(current_lines).strip()))
                    current_lines = []
                current_title = match.group(2).strip()
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_title, "\n".join(current_lines).strip()))

        return [s for s in sections if s[1]]

    def _split_into_sentences(self, text: str) -> List[str]:
        """Splits long text into sentence units preserving punctuation."""
        raw_splits = re.split(r"(?<=[.?!;])\s+|\n+", text)
        return [s.strip() for s in raw_splits if s.strip()]

    def chunk_document(
        self,
        doc: IngestionDocument,
        sanitize_pii: bool = True
    ) -> List[DocumentChunk]:
        """
        Chunks an ingestion document into structured, enriched DocumentChunk objects.
        Applies PII sanitization to all chunks prior to downstream embedding.
        """
        sections = self._split_into_sections(doc.content)
        chunks: List[DocumentChunk] = []
        chunk_index = 0

        for section_title, section_text in sections:
            paragraphs = [p.strip() for p in section_text.split("\n\n") if p.strip()]
            
            # Sub-split any paragraphs that alone exceed chunk size
            atomic_units = []
            for p in paragraphs:
                if self._estimate_tokens(p) > self.chunk_size:
                    sentences = self._split_into_sentences(p)
                    atomic_units.extend(sentences)
                else:
                    atomic_units.append(p)

            current_buffer = []
            current_tokens = 0

            for unit in atomic_units:
                unit_tokens = self._estimate_tokens(unit)
                if current_tokens + unit_tokens > self.chunk_size and current_buffer:
                    chunk_text = "\n\n".join(current_buffer)
                    chunk_obj = self._create_chunk(
                        doc=doc,
                        section_title=section_title,
                        raw_text=chunk_text,
                        chunk_index=chunk_index,
                        sanitize_pii=sanitize_pii
                    )
                    chunks.append(chunk_obj)
                    chunk_index += 1

                    current_buffer = [current_buffer[-1]] if len(current_buffer) > 1 else []
                    current_tokens = self._estimate_tokens(current_buffer[0]) if current_buffer else 0

                current_buffer.append(unit)
                current_tokens += unit_tokens

            if current_buffer:
                chunk_text = "\n\n".join(current_buffer)
                chunk_obj = self._create_chunk(
                    doc=doc,
                    section_title=section_title,
                    raw_text=chunk_text,
                    chunk_index=chunk_index,
                    sanitize_pii=sanitize_pii
                )
                chunks.append(chunk_obj)
                chunk_index += 1

        return chunks

    def _create_chunk(
        self,
        doc: IngestionDocument,
        section_title: str,
        raw_text: str,
        chunk_index: int,
        sanitize_pii: bool
    ) -> DocumentChunk:
        """Creates a DocumentChunk with metadata and optional PII pseudonymization."""
        has_pii = False
        pseudonym_map = {}
        processed_text = raw_text

        if sanitize_pii:
            sanitized = self.pii_sanitizer.sanitize(
                text=raw_text,
                strategy="pseudonymize",
                tenant_salt=doc.tenant_id
            )
            processed_text = sanitized.sanitized_text
            has_pii = sanitized.has_pii
            pseudonym_map = sanitized.pseudonym_map

        # Context header attached to chunk for improved embedding retrieval
        contextual_header = f"[Doc: {doc.title} | Section: {section_title}]\n"
        final_content = contextual_header + processed_text

        return DocumentChunk(
            chunk_id=f"{doc.doc_id}_chk_{chunk_index:04d}",
            doc_id=doc.doc_id,
            tenant_id=doc.tenant_id,
            content=final_content,
            raw_content_preview=raw_text[:120],
            section_title=section_title,
            chunk_index=chunk_index,
            token_count=self._estimate_tokens(final_content),
            metadata={
                **doc.metadata,
                "title": doc.title,
                "source_type": doc.source_type,
                "section": section_title,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            },
            has_pii=has_pii,
            pseudonym_map=pseudonym_map
        )


# Global chunker instance
global_chunker = ContextualChunker()
