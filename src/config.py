"""
Enterprise EU-Compliant RAG Configuration Module.
Provides validated environment settings with strict defaults for GDPR and EU AI Act compliance.
"""

from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """System configuration parameters."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # General
    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Application log level")

    # Security & Encryption
    MASTER_KEY: str = Field(
        default="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        description="Master key hex string used for key vault root operations"
    )
    VAULT_BACKEND: Literal["in_memory", "file", "azure_key_vault"] = Field(
        default="in_memory",
        description="Backend storage for cryptographic tenant keys"
    )
    AUDIT_LOG_FILE: str = Field(
        default="./logs/audit_ledger.jsonl",
        description="Path for immutable EU AI Act Art. 12 audit ledger"
    )

    # Sovereign Inference
    SOVEREIGN_LLM_PROVIDER: Literal["local_vllm", "ollama", "mistral_eu", "azure_eu", "mock"] = Field(
        default="local_vllm",
        description="EU Sovereign LLM provider"
    )
    SOVEREIGN_LLM_BASE_URL: str = Field(
        default="http://localhost:8000/v1",
        description="Base URL for sovereign LLM endpoint"
    )
    SOVEREIGN_LLM_MODEL: str = Field(
        default="mistralai/Mistral-7B-Instruct-v0.3",
        description="Model identifier"
    )
    SOVEREIGN_EMBEDDING_MODEL: str = Field(
        default="BAAI/bge-m3",
        description="Embedding model identifier"
    )

    # Vector Storage
    VECTOR_DB_TYPE: Literal["in_memory", "qdrant", "pgvector"] = Field(
        default="in_memory",
        description="Vector database backend"
    )
    VECTOR_DB_HOST: str = Field(default="localhost")
    VECTOR_DB_PORT: int = Field(default=6333)
    VECTOR_DB_COLLECTION: str = Field(default="enterprise_knowledge_base")

    # PII & Privacy Guardrails
    PII_DETECTION_CONFIDENCE: float = Field(
        default=0.60,
        description="Minimum confidence score for PII entity recognition"
    )
    PII_MASKING_STRATEGY: Literal["pseudonymize", "redact", "mask"] = Field(
        default="pseudonymize",
        description="Default strategy for sanitizing detected PII entities"
    )

    # RAG Chunking Parameters
    DEFAULT_CHUNK_SIZE: int = Field(default=512, description="Target chunk size in tokens")
    DEFAULT_CHUNK_OVERLAP: int = Field(default=64, description="Chunk overlap in tokens")


settings = Settings()
