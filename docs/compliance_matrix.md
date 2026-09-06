# Regulatory Compliance & Technical Measures Matrix (GDPR & EU AI Act)

> **Important Legal Context**: Under European data protection law, software provides **Technical and Organizational Measures (TOMs)** by design. Full organizational compliance additionally requires institutional measures (DPIA, Article 30 Records of Processing, Access Policies, and Data Processing Agreements).

---

## 🛡️ General Data Protection Regulation (GDPR)

| Article | Principle / Requirement | Technical Implementation in System | Verification & Enforcement |
| :--- | :--- | :--- | :--- |
| **Article 25** | **Data Protection by Design & by Default** | Pre-ingestion automated PII extraction and deterministic pseudonymization via Microsoft Presidio with EU SEPA IBAN & Tax ID recognizers. Raw personal data is never vectorized or submitted to LLMs. | `tests/test_pii_sanitizer.py` |
| **Article 17** | **Right to Erasure ("Right to be Forgotten")** | Dedicated AES-256-GCM cryptographic key per document/subject in KeyVault. Shredding the key permanently invalidates stored vectors and text without database re-indexing. | `tests/test_crypto_shredding.py` |
| **Article 32** | **Security of Processing** | AES-256-GCM authenticated encryption at rest, SHA-256 record hashing, and Role-Based Access Control (RBAC) separating `dpo`, `admin`, and `employee` operations. | `tests/test_ingest_and_gdpr_api.py` |
| **Article 33/34** | **Breach Notification & Audit Trail** | Tamper-evident SHA-256 Merkle-linked audit ledger recording all key revocations, ingestion events, and query operations. | `tests/test_audit_logger.py` |

---

## 🇪🇺 EU Artificial Intelligence Act (Regulation 2024/1689)

| Article | Risk Tier / Requirement | Technical Implementation in System | Verification & Enforcement |
| :--- | :--- | :--- | :--- |
| **Article 50** | **General Purpose AI Transparency (Mandatory)** | Mandatory machine-generated transparency notices appended to every response, with explicit source document attribution `[Doc Title: Section]`. | `src/agents/synthesizer_agent.py` |
| **Article 12** | **Technical Record-Keeping (High-Risk Scaffolding)** | Immutable logging of user queries, subquery plans, retrieved chunk IDs, similarity scores, and model metadata. | `src/core/audit_logger.py` |
| **Article 14** | **Human Oversight (High-Risk Scaffolding)** | Pre-generation and post-generation verification gates; rejection circuits for out-of-scope queries preventing forced hallucination. | `src/agents/verifier_agent.py` |
| **Article 15** | **Accuracy, Robustness & Cybersecurity** | Automated NLI verification (DeBERTa cross-encoder) and RAGAS automated benchmark evaluation (Faithfulness > 0.90, Context Precision). | `src/eval/ragas_evaluator.py` |

