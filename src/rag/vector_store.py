"""
Tenant-Isolated Vector Store with Cryptographic Shredding Support.
Maintains dense vector indexes partitioned by tenant, enforcing GDPR key-revocation checks.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from src.rag.chunking import DocumentChunk
from src.rag.embeddings import EmbeddingModel, global_embedding_model
from src.core.security import KeyVaultManager, global_key_vault, KeyRevokedError


@dataclass
class VectorRecord:
    """Indexed vector representation of a DocumentChunk."""
    chunk_id: str
    doc_id: str
    tenant_id: str
    key_id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any]
    is_tombstoned: bool = False


@dataclass
class SearchResult:
    """Result of vector or hybrid retrieval."""
    chunk_id: str
    doc_id: str
    tenant_id: str
    content: str
    score: float
    section_title: str
    metadata: Dict[str, Any]
    retrieval_method: str = "dense_vector"


class SovereignVectorStore:
    """
    In-memory / persistent sovereign vector database with tenant namespace partitioning.
    Integrates with KeyVault to guarantee that shredded keys cannot return search results.
    """

    def __init__(
        self,
        embedding_model: Optional[EmbeddingModel] = None,
        key_vault: Optional[KeyVaultManager] = None
    ):
        self.embedding_model = embedding_model or global_embedding_model
        self.key_vault = key_vault or global_key_vault
        # Namespace: tenant_id -> Dict[chunk_id, VectorRecord]
        self._namespaces: Dict[str, Dict[str, VectorRecord]] = {}

    def index_chunks(
        self,
        tenant_id: str,
        chunks: List[DocumentChunk],
        key_id: str
    ) -> int:
        """
        Embeds and indexes document chunks into the tenant's isolated namespace.
        """
        if tenant_id not in self._namespaces:
            self._namespaces[tenant_id] = {}

        texts = [c.content for c in chunks]
        embeddings = self.embedding_model.embed_documents(texts)

        for chunk, emb in zip(chunks, embeddings):
            record = VectorRecord(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                tenant_id=tenant_id,
                key_id=key_id,
                content=chunk.content,
                embedding=emb,
                metadata={
                    **chunk.metadata,
                    "section_title": chunk.section_title,
                    "token_count": chunk.token_count,
                    "has_pii": chunk.has_pii
                }
            )
            self._namespaces[tenant_id][chunk.chunk_id] = record

        return len(chunks)

    def search_dense(
        self,
        tenant_id: str,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0
    ) -> List[SearchResult]:
        """
        Executes dense vector similarity search within a tenant's isolated namespace.
        Automatically filters out chunks whose cryptographic keys have been shredded.
        """
        if tenant_id not in self._namespaces:
            return []

        query_emb = self.embedding_model.embed_text(query)
        candidates: List[Tuple[float, VectorRecord]] = []

        for record in self._namespaces[tenant_id].values():
            if record.is_tombstoned:
                continue

            # GDPR Article 17 Key Revocation Check
            key_meta = self.key_vault.get_metadata(record.key_id)
            if key_meta and key_meta.is_revoked:
                record.is_tombstoned = True
                continue

            similarity = self.embedding_model.compute_similarity(query_emb, record.embedding)
            if similarity >= min_score:
                candidates.append((similarity, record))

        # Sort descending by cosine similarity score
        candidates.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, rec in candidates[:top_k]:
            results.append(
                SearchResult(
                    chunk_id=rec.chunk_id,
                    doc_id=rec.doc_id,
                    tenant_id=rec.tenant_id,
                    content=rec.content,
                    score=float(score),
                    section_title=rec.metadata.get("section_title", "Unknown Section"),
                    metadata=rec.metadata,
                    retrieval_method="dense_vector"
                )
            )

        return results

    def get_all_active_chunks_for_tenant(self, tenant_id: str) -> List[VectorRecord]:
        """Returns all non-revoked chunk records for BM25 sparse indexing."""
        if tenant_id not in self._namespaces:
            return []
        
        active_records = []
        for record in self._namespaces[tenant_id].values():
            if record.is_tombstoned:
                continue
            key_meta = self.key_vault.get_metadata(record.key_id)
            if key_meta and key_meta.is_revoked:
                record.is_tombstoned = True
                continue
            active_records.append(record)

        return active_records

    def count_chunks(self, tenant_id: str) -> int:
        """Returns the number of active chunks in a tenant's namespace."""
        return len(self.get_all_active_chunks_for_tenant(tenant_id))


# Global vector store instance
global_vector_store = SovereignVectorStore()
