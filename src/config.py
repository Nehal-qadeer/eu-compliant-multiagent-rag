"""
Enterprise EU-Compliant RAG Configuration Module.
Provides validated environment settings with strict defaults for GDPR and EU AI Act compliance.
"""

from typing import Literal, List, Optional
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

    # Security, CORS & Access Control
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
            "https://nehal-portfolio-one.vercel.app"
        ],
        description="Allowed CORS origin domains"
    )
    REQUIRE_AUTH: bool = Field(
        default=True,
        description="Enforce strict API Key authentication across all /api/v1/* routes"
    )
    API_KEY_ADMIN: str = Field(default="admin-root-key-1122", description="Admin role API key")
    API_KEY_DPO: str = Field(default="dpo-secure-key-9988", description="DPO / Compliance officer API key")
    API_KEY_EMPLOYEE: str = Field(default="employee-user-key-3344", description="Employee user API key")
    API_KEY_AUDITOR: str = Field(default="auditor-inspect-key-5566", description="Auditor role API key")

    # Encryption & Key Vault
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

    # Inference Providers & Sovereignty
    SOVEREIGN_LLM_PROVIDER: Literal["local_vllm", "ollama", "mistral_eu", "azure_eu", "anthropic_claude", "mock"] = Field(
        default="local_vllm",
        description="EU Sovereign or configured LLM provider"
    )
    SOVEREIGN_LLM_BASE_URL: str = Field(
        default="http://localhost:8000/v1",
        description="Base URL for sovereign OpenAI-compatible endpoint"
    )
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Base URL for local Ollama instance"
    )
    SOVEREIGN_LLM_MODEL: str = Field(
        default="mistralai/Mistral-7B-Instruct-v0.3",
        description="Model identifier"
    )
    ANTHROPIC_API_KEY: Optional[str] = Field(
        default=None,
        description="Optional Anthropic API Key (Note: Cloud API, sets is_sovereign=False)"
    )
    ANTHROPIC_MODEL: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Anthropic Claude model identifier"
    )
    SOVEREIGN_EMBEDDING_MODEL: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Dense embedding model identifier"
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

