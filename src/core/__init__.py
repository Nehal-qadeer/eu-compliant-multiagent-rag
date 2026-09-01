"""
Core Security, Privacy, and Compliance Module.
"""

from src.core.security import (
    KeyVaultManager,
    CryptoService,
    KeyMetadata,
    KeyRevokedError,
    DecryptionError,
    global_key_vault,
)
from src.core.audit_logger import (
    AuditLogger,
    AuditEvent,
    global_audit_logger,
)
from src.core.pii_sanitizer import (
    PIISanitizer,
    PIIEntity,
    SanitizedResult,
    global_pii_sanitizer,
)

__all__ = [
    "KeyVaultManager",
    "CryptoService",
    "KeyMetadata",
    "KeyRevokedError",
    "DecryptionError",
    "global_key_vault",
    "AuditLogger",
    "AuditEvent",
    "global_audit_logger",
    "PIISanitizer",
    "PIIEntity",
    "SanitizedResult",
    "global_pii_sanitizer",
]
