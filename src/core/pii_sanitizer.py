"""
Microsoft Presidio-Powered PII Detection, Redaction, and Reversible Pseudonymization Engine.
Ensures GDPR Article 25 (Data Protection by Design) compliance by preventing raw PII
from entering vector databases or LLM prompts.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Try importing Microsoft Presidio
try:
    from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern, RecognizerRegistry, RecognizerResult
    from presidio_anonymizer import AnonymizerEngine
    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False
    logger.warning("Microsoft Presidio not found. Initializing built-in regex analyzer.")


@dataclass
class PIIEntity:
    """Represents a detected PII entity within text."""
    entity_type: str
    text: str
    start: int
    end: int
    confidence: float
    pseudonym: Optional[str] = None


class SanitizedResult(BaseModel):
    """Result of PII sanitization containing cleaned text and mappings."""
    sanitized_text: str
    entities_detected: List[Dict[str, str]]
    pseudonym_map: Dict[str, str] = Field(
        default_factory=dict,
        description="Map from pseudonym back to original value (encrypted at rest)"
    )
    has_pii: bool = False
    engine: str = "microsoft_presidio"


class PIISanitizer:
    """
    Microsoft Presidio-backed PII Sanitizer with custom EU Recognizers
    (IBAN, EU Tax ID, German phone formats, honorifics, etc.)
    and deterministic reversible pseudonymization.
    """

    # EU-specific high-confidence patterns
    FALLBACK_PATTERNS = {
        "EMAIL_ADDRESS": (
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", re.IGNORECASE),
            0.95
        ),
        "IBAN_CODE": (
            re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{12,30}\b"),
            0.98
        ),
        "PHONE_NUMBER": (
            re.compile(r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b"),
            0.85
        ),
        "IP_ADDRESS": (
            re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
            0.90
        ),
        "PASSPORT_NUMBER": (
            re.compile(r"\b[A-Z]{1,2}[0-9]{7,8}\b"),
            0.80
        ),
        "CREDIT_CARD": (
            re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
            0.95
        ),
        "EU_TAX_ID": (
            re.compile(r"\b(?:DE|FR|IT|ES|NL|BE|AT|PL|SE|DK|FI|IE)\d{8,12}\b"),
            0.92
        ),
        "PERSON": (
            # Recognizes common salutations and titles + 2-3 capitalized words
            re.compile(r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Herr|Frau|Monsieur|M\.|Mme)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b"),
            0.88
        ),
    }

    def __init__(self, confidence_threshold: float = 0.60):
        self.confidence_threshold = confidence_threshold
        self.presidio_analyzer: Optional[Any] = None
        self.presidio_anonymizer: Optional[Any] = None
        self.engine_name = "built_in_regex"

        if PRESIDIO_AVAILABLE:
            try:
                self._init_presidio()
            except Exception as e:
                logger.warning(f"Failed to initialize Presidio NLP engine: {e}. Using pattern recognizer mode.")

    def _init_presidio(self):
        """Initializes Presidio AnalyzerEngine with custom EU recognizers."""
        registry = RecognizerRegistry()
        registry.load_predefined_recognizers()

        # 1. Custom IBAN Recognizer for EU SEPA
        iban_pattern = Pattern(
            name="eu_iban_pattern",
            regex=r"\b[A-Z]{2}\d{2}[A-Z0-9]{12,30}\b",
            score=0.98
        )
        iban_recognizer = PatternRecognizer(
            supported_entity="IBAN_CODE",
            patterns=[iban_pattern],
            context=["iban", "bank", "account", "transfer", "sepa", "debit", "konto"]
        )
        registry.add_recognizer(iban_recognizer)

        # 2. Custom EU Tax ID Recognizer
        tax_pattern = Pattern(
            name="eu_tax_id_pattern",
            regex=r"\b(?:DE|FR|IT|ES|NL|BE|AT|PL|SE|DK|FI|IE)\d{8,12}\b",
            score=0.92
        )
        tax_recognizer = PatternRecognizer(
            supported_entity="EU_TAX_ID",
            patterns=[tax_pattern],
            context=["tax", "vat", "ust-idnr", "steuernummer", "steuer", "id"]
        )
        registry.add_recognizer(tax_recognizer)

        # 3. Custom Person Honorifics Recognizer
        person_pattern = Pattern(
            name="honorific_person_pattern",
            regex=r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Herr|Frau|Monsieur|M\.|Mme)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b",
            score=0.88
        )
        person_recognizer = PatternRecognizer(
            supported_entity="PERSON",
            patterns=[person_pattern],
            context=["contact", "officer", "manager", "representative", "author", "dpo"]
        )
        registry.add_recognizer(person_recognizer)

        # 4. Custom EU Phone Recognizer
        phone_pattern = Pattern(
            name="eu_phone_pattern",
            regex=r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b",
            score=0.85
        )
        phone_recognizer = PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            patterns=[phone_pattern],
            context=["phone", "tel", "mobile", "contact", "telefon", "anruf"]
        )
        registry.add_recognizer(phone_recognizer)

        self.presidio_analyzer = AnalyzerEngine(registry=registry)
        self.presidio_anonymizer = AnonymizerEngine()
        self.engine_name = "microsoft_presidio"

    def detect_entities(self, text: str) -> List[PIIEntity]:
        """Detects PII entities using Presidio Analyzer if available, with regex fallback."""
        if self.presidio_analyzer is not None:
            try:
                results: List[RecognizerResult] = self.presidio_analyzer.analyze(
                    text=text,
                    language="en",
                    score_threshold=self.confidence_threshold
                )
                entities: List[PIIEntity] = []
                for r in results:
                    matched_text = text[r.start:r.end]
                    # Filter out short digit sequences mistakenly caught as phone
                    if r.entity_type == "PHONE_NUMBER" and len(re.sub(r"\D", "", matched_text)) < 7:
                        continue
                    entities.append(
                        PIIEntity(
                            entity_type=r.entity_type,
                            text=matched_text,
                            start=r.start,
                            end=r.end,
                            confidence=round(r.score, 3)
                        )
                    )

                # Sort by start index ascending
                entities.sort(key=lambda e: (e.start, -(e.end - e.start)))
                # Resolve overlapping spans
                filtered_entities: List[PIIEntity] = []
                last_end = -1
                for e in entities:
                    if e.start >= last_end:
                        filtered_entities.append(e)
                        last_end = e.end
                return filtered_entities
            except Exception as e:
                logger.warning(f"Presidio analyze error: {e}. Falling back to regex.")

        # Fallback to high-precision regex engine
        entities: List[PIIEntity] = []
        for entity_type, (pattern, confidence) in self.FALLBACK_PATTERNS.items():
            if confidence < self.confidence_threshold:
                continue

            for match in pattern.finditer(text):
                start, end = match.start(), match.end()
                matched_text = match.group(0)

                if entity_type == "PHONE_NUMBER" and len(re.sub(r"\D", "", matched_text)) < 7:
                    continue

                entities.append(
                    PIIEntity(
                        entity_type=entity_type,
                        text=matched_text,
                        start=start,
                        end=end,
                        confidence=confidence
                    )
                )

        entities.sort(key=lambda e: (e.start, -(e.end - e.start)))
        filtered_entities: List[PIIEntity] = []
        last_end = -1
        for e in entities:
            if e.start >= last_end:
                filtered_entities.append(e)
                last_end = e.end

        return filtered_entities

    def sanitize(
        self,
        text: str,
        strategy: str = "pseudonymize",
        tenant_salt: str = "default_salt"
    ) -> SanitizedResult:
        """
        Sanitizes text by replacing detected PII with pseudonyms, redaction tags, or synthetic masks.
        Returns the sanitized text along with the bidirectional pseudonym mapping.
        """
        entities = self.detect_entities(text)
        if not entities:
            return SanitizedResult(
                sanitized_text=text,
                entities_detected=[],
                pseudonym_map={},
                has_pii=False,
                engine=self.engine_name
            )

        type_counters: Dict[str, int] = {}
        pseudonym_map: Dict[str, str] = {}
        entity_summary: List[Dict[str, str]] = []

        # Build replacement strings
        for ent in entities:
            if ent.text in pseudonym_map.values():
                # Reuse existing pseudonym for identical token in document
                for p, val in pseudonym_map.items():
                    if val == ent.text:
                        ent.pseudonym = p
                        break
            else:
                type_counters[ent.entity_type] = type_counters.get(ent.entity_type, 0) + 1
                index = type_counters[ent.entity_type]

                if strategy == "pseudonymize":
                    # Generate deterministic pseudonym token
                    ent.pseudonym = f"<{ent.entity_type}_{index:02d}>"
                elif strategy == "redact":
                    ent.pseudonym = f"[REDACTED_{ent.entity_type}]"
                else:
                    ent.pseudonym = "***"

                pseudonym_map[ent.pseudonym] = ent.text

            entity_summary.append({
                "type": ent.entity_type,
                "pseudonym": ent.pseudonym,
                "confidence": str(ent.confidence)
            })

        # Apply substitutions from right to left to preserve offsets
        sanitized_chars = list(text)
        for ent in sorted(entities, key=lambda e: e.start, reverse=True):
            sanitized_chars[ent.start:ent.end] = list(ent.pseudonym)

        sanitized_text = "".join(sanitized_chars)

        return SanitizedResult(
            sanitized_text=sanitized_text,
            entities_detected=entity_summary,
            pseudonym_map=pseudonym_map,
            has_pii=True,
            engine=self.engine_name
        )

    def rehydrate(self, text: str, pseudonym_map: Dict[str, str]) -> str:
        """
        Restores original PII into sanitized text using the authorized pseudonym map.
        Only executed for authorized user roles during final response synthesis.
        """
        rehydrated = text
        for pseudonym, original in pseudonym_map.items():
            rehydrated = rehydrated.replace(pseudonym, original)
        return rehydrated


# Singleton sanitizer instance
global_pii_sanitizer = PIISanitizer()
