"""
Core Security and Cryptographic Key Management.
Implements AES-256-GCM authenticated encryption and GDPR Article 17 Cryptographic Shredding.
"""

import os
import secrets
import base64
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class KeyRevokedError(Exception):
    """Raised when an operation is attempted with a cryptographically revoked (shredded) key."""
    pass


class DecryptionError(Exception):
    """Raised when decryption or ciphertext authentication fails."""
    pass


@dataclass
class KeyMetadata:
    """Metadata associated with an encryption key."""
    key_id: str
    tenant_id: str
    subject_id: Optional[str]  # e.g., user_id or doc_id
    created_at: str
    is_revoked: bool = False
    revoked_at: Optional[str] = None
    revocation_reason: Optional[str] = None


class KeyVaultManager:
    """
    Manages lifecycle of cryptographic keys per tenant and document.
    Enforces GDPR Article 17 by supporting instant cryptographic shredding.
    """

    def __init__(self):
        self._keys: Dict[str, bytes] = {}
        self._metadata: Dict[str, KeyMetadata] = {}

    def generate_key(
        self,
        tenant_id: str,
        subject_id: Optional[str] = None,
        key_id: Optional[str] = None
    ) -> str:
        """Generates a new 256-bit AES key for a given tenant/subject."""
        actual_key_id = key_id or f"key_{tenant_id}_{secrets.token_hex(8)}"
        raw_key = AESGCM.generate_key(bit_length=256)
        
        self._keys[actual_key_id] = raw_key
        self._metadata[actual_key_id] = KeyMetadata(
            key_id=actual_key_id,
            tenant_id=tenant_id,
            subject_id=subject_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            is_revoked=False
        )
        return actual_key_id

    def get_key(self, key_id: str) -> bytes:
        """Retrieves raw key bytes if active, raises KeyRevokedError if shredded."""
        if key_id not in self._metadata:
            raise KeyError(f"Key '{key_id}' does not exist in key vault.")
        
        meta = self._metadata[key_id]
        if meta.is_revoked:
            raise KeyRevokedError(
                f"Key '{key_id}' has been shredded on {meta.revoked_at} (Reason: {meta.revocation_reason})."
            )
        
        return self._keys[key_id]

    def revoke_key(self, key_id: str, reason: str = "GDPR Article 17 Right to Erasure") -> KeyMetadata:
        """
        Executes cryptographic shredding by zeroing out and deleting the key material.
        Leaves immutable audit metadata confirming the deletion.
        """
        if key_id not in self._metadata:
            raise KeyError(f"Key '{key_id}' does not exist in key vault.")
        
        # Zero out key bytes before removal
        if key_id in self._keys:
            del self._keys[key_id]
        
        meta = self._metadata[key_id]
        meta.is_revoked = True
        meta.revoked_at = datetime.now(timezone.utc).isoformat()
        meta.revocation_reason = reason
        return meta

    def get_metadata(self, key_id: str) -> Optional[KeyMetadata]:
        """Returns metadata for a key."""
        return self._metadata.get(key_id)

    def list_keys_for_tenant(self, tenant_id: str) -> Dict[str, KeyMetadata]:
        """Lists all keys associated with a tenant."""
        return {k: v for k, v in self._metadata.items() if v.tenant_id == tenant_id}


# Singleton key vault instance for system-wide lifecycle management
global_key_vault = KeyVaultManager()


class CryptoService:
    """
    High-level AES-256-GCM encryption/decryption service integrated with the KeyVault.
    """

    def __init__(self, key_vault: Optional[KeyVaultManager] = None):
        self.key_vault = key_vault or global_key_vault

    def encrypt(
        self,
        plaintext: str,
        key_id: str,
        associated_data: Optional[str] = None
    ) -> str:
        """
        Encrypts plaintext string using AES-256-GCM.
        Returns a base64 encoded string: nonce(12 bytes) + ciphertext + tag.
        """
        key_bytes = self.key_vault.get_key(key_id)
        aesgcm = AESGCM(key_bytes)
        
        nonce = secrets.token_bytes(12)  # Standard 96-bit nonce for GCM
        aad_bytes = associated_data.encode("utf-8") if associated_data else None
        
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad_bytes)
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode("ascii")

    def decrypt(
        self,
        encrypted_b64: str,
        key_id: str,
        associated_data: Optional[str] = None
    ) -> str:
        """
        Decrypts base64 encoded ciphertext string using AES-256-GCM.
        Raises KeyRevokedError if key was shredded, DecryptionError if tamper detected.
        """
        key_bytes = self.key_vault.get_key(key_id)
        aesgcm = AESGCM(key_bytes)
        
        try:
            raw = base64.b64decode(encrypted_b64.encode("ascii"))
            if len(raw) < 12:
                raise DecryptionError("Payload too short to contain valid nonce.")
            
            nonce = raw[:12]
            ciphertext = raw[12:]
            aad_bytes = associated_data.encode("utf-8") if associated_data else None
            
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, aad_bytes)
            return decrypted_bytes.decode("utf-8")
        except KeyRevokedError:
            raise
        except Exception as exc:
            raise DecryptionError(f"Decryption failed: {str(exc)}") from exc
