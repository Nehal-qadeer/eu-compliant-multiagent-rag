"""
Rigorous Tests for PII Detection, Redaction, and Reversible Pseudonymization.
Covers EU-specific PII formats, multi-entity text, and round-trip rehydration.
"""

import pytest
from src.core.pii_sanitizer import PIISanitizer, PIIEntity


def test_detect_eu_pii_entities(pii_sanitizer: PIISanitizer):
    """Verifies detection of multiple EU PII formats in enterprise text."""
    sample_text = (
        "Please send invoice to Dr. Klaus Weber at klaus.weber@company.de. "
        "Direct debit IBAN: DE89370400440532013000, Tax ID: DE123456789. "
        "Server accessed from IP 192.168.1.100, contact phone +49 170 1234567."
    )

    entities = pii_sanitizer.detect_entities(sample_text)
    types_found = {e.entity_type for e in entities}

    assert "EMAIL_ADDRESS" in types_found
    assert "IBAN_CODE" in types_found
    assert "EU_TAX_ID" in types_found
    assert "IP_ADDRESS" in types_found
    assert "PERSON" in types_found
    assert "PHONE_NUMBER" in types_found


def test_pseudonymization_and_rehydration_roundtrip(pii_sanitizer: PIISanitizer):
    """Verifies that PII is pseudonymized cleanly and can be rehydrated given the key map."""
    original_text = (
        "Employee Mr. John Smith with email john.smith@enterprise.eu "
        "and IBAN FR7630006000011234567890189 requested budget approval."
    )

    result = pii_sanitizer.sanitize(original_text, strategy="pseudonymize")

    assert result.has_pii is True
    assert "john.smith@enterprise.eu" not in result.sanitized_text
    assert "FR7630006000011234567890189" not in result.sanitized_text
    assert "Mr. John Smith" not in result.sanitized_text
    assert "<EMAIL_ADDRESS_01>" in result.sanitized_text
    assert "<IBAN_CODE_01>" in result.sanitized_text
    assert "<PERSON_01>" in result.sanitized_text

    # Rehydrate using the authorized pseudonym map
    rehydrated = pii_sanitizer.rehydrate(result.sanitized_text, result.pseudonym_map)
    assert rehydrated == original_text


def test_clean_text_no_pii(pii_sanitizer: PIISanitizer):
    """Verifies that generic text without PII is unaltered."""
    clean_text = "The quarterly compliance report covers general guidelines for machine learning pipelines."
    result = pii_sanitizer.sanitize(clean_text)

    assert result.has_pii is False
    assert result.sanitized_text == clean_text
    assert len(result.entities_detected) == 0
    assert len(result.pseudonym_map) == 0


def test_repeated_pii_gets_consistent_pseudonym(pii_sanitizer: PIISanitizer):
    """Verifies that the same PII occurrence in a document reuses the identical pseudonym token."""
    text = "Report authored by Dr. Klaus Weber. All inquiries should be directed back to Dr. Klaus Weber."
    result = pii_sanitizer.sanitize(text, strategy="pseudonymize")

    assert result.sanitized_text.count("<PERSON_01>") == 2
    assert "<PERSON_02>" not in result.sanitized_text
