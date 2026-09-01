"""
PyTest Fixtures and Configuration for EU-Compliant RAG Testing.
"""

import os
import pytest
from httpx import AsyncClient, ASGITransport

from src.core.security import KeyVaultManager, CryptoService
from src.core.audit_logger import AuditLogger
from src.core.pii_sanitizer import PIISanitizer
from src.rag.chunking import ContextualChunker
from src.api.main import app


@pytest.fixture
def fresh_key_vault():
    """Provides an isolated KeyVault instance."""
    return KeyVaultManager()


@pytest.fixture
def crypto_service(fresh_key_vault):
    """Provides a CryptoService instance with isolated key vault."""
    return CryptoService(key_vault=fresh_key_vault)


@pytest.fixture
def temp_audit_logger(tmp_path):
    """Provides an isolated AuditLogger pointing to a temporary file."""
    log_file = tmp_path / "test_audit.jsonl"
    return AuditLogger(log_file_path=str(log_file))


@pytest.fixture
def pii_sanitizer():
    """Provides a fresh PIISanitizer instance."""
    return PIISanitizer(confidence_threshold=0.60)


@pytest.fixture
def contextual_chunker(pii_sanitizer):
    """Provides a ContextualChunker instance."""
    return ContextualChunker(chunk_size=200, chunk_overlap=30, pii_sanitizer=pii_sanitizer)


@pytest.fixture
async def async_client():
    """Provides an async HTTP client for testing FastAPI routes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
