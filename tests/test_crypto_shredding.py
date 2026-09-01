"""
Rigorous Unit Tests for AES-256-GCM Encryption and GDPR Article 17 Cryptographic Shredding.
"""

import pytest
from src.core.security import (
    KeyVaultManager,
    CryptoService,
    KeyRevokedError,
    DecryptionError,
)


def test_key_generation_and_metadata(fresh_key_vault: KeyVaultManager):
    """Verifies generation of 256-bit keys with tenant metadata."""
    key_id = fresh_key_vault.generate_key(tenant_id="tenant_eu_101", subject_id="user_88")
    assert key_id.startswith("key_tenant_eu_101_")

    meta = fresh_key_vault.get_metadata(key_id)
    assert meta is not None
    assert meta.tenant_id == "tenant_eu_101"
    assert meta.subject_id == "user_88"
    assert meta.is_revoked is False

    # Key bytes can be retrieved when active
    key_bytes = fresh_key_vault.get_key(key_id)
    assert len(key_bytes) == 32  # 256 bits


def test_encryption_and_decryption_flow(crypto_service: CryptoService, fresh_key_vault: KeyVaultManager):
    """Verifies AES-256-GCM authenticated encryption round-trip."""
    key_id = fresh_key_vault.generate_key(tenant_id="tenant_de_01")
    plaintext = "Confidential GDPR-protected employee record for audit."

    ciphertext = crypto_service.encrypt(plaintext, key_id=key_id, associated_data="metadata_aad")
    assert ciphertext != plaintext
    assert isinstance(ciphertext, str)

    decrypted = crypto_service.decrypt(ciphertext, key_id=key_id, associated_data="metadata_aad")
    assert decrypted == plaintext


def test_crypto_shredding_renders_data_undecryptable(crypto_service: CryptoService, fresh_key_vault: KeyVaultManager):
    """
    CRITICAL GDPR ART. 17 TEST:
    Verifies that revoking (shredding) a key permanently prevents decryption
    of pre-existing ciphertexts.
    """
    key_id = fresh_key_vault.generate_key(tenant_id="tenant_fr_02", subject_id="doc_sensitive_999")
    plaintext = "Patient medical history and private diagnosis notes."

    ciphertext = crypto_service.encrypt(plaintext, key_id=key_id)

    # 1. Decrypt succeeds while key is active
    assert crypto_service.decrypt(ciphertext, key_id=key_id) == plaintext

    # 2. Execute Cryptographic Shredding
    revoked_meta = fresh_key_vault.revoke_key(key_id, reason="User requested erasure under GDPR Art. 17")
    assert revoked_meta.is_revoked is True
    assert revoked_meta.revoked_at is not None

    # 3. Subsequent attempts to retrieve key or decrypt ciphertext MUST fail with KeyRevokedError
    with pytest.raises(KeyRevokedError) as exc_info:
        fresh_key_vault.get_key(key_id)
    assert "shredded" in str(exc_info.value)

    with pytest.raises(KeyRevokedError):
        crypto_service.decrypt(ciphertext, key_id=key_id)


def test_tampered_ciphertext_detection(crypto_service: CryptoService, fresh_key_vault: KeyVaultManager):
    """Verifies that modified ciphertexts fail authentication and trigger DecryptionError."""
    key_id = fresh_key_vault.generate_key(tenant_id="tenant_nl_03")
    ciphertext = crypto_service.encrypt("Secret corporate transaction", key_id=key_id)

    # Corrupt the ciphertext
    import base64
    raw = bytearray(base64.b64decode(ciphertext))
    raw[-1] ^= 0xFF  # Flip bits in the auth tag
    corrupted_b64 = base64.b64encode(raw).decode("ascii")

    with pytest.raises(DecryptionError):
        crypto_service.decrypt(corrupted_b64, key_id=key_id)
