# Regulatory Compliance Matrix: GDPR & EU AI Act

| Regulation | Article / Clause | Requirement Summary | Technical Implementation in System | Verifying Agent |
|---|---|---|---|---|
| **GDPR** | **Article 25** | Data Protection by Design and by Default | Pre-ingestion automated PII extraction and pseudonymization using Presidio. Raw PII is never vectorized or fed to embedding models. | Dev Agent / QA Agent |
| **GDPR** | **Article 17** | Right to Erasure ("Right to be Forgotten") | Cryptographic shredding architecture. Tenant/document key destruction invalidates embeddings without rebuilding indexes. | Dev Agent / QA Agent |
| **GDPR** | **Article 22** | Automated Decision-Making & Human-in-the-loop | Responses exceeding critical sensitivity or failing verification scores require human sign-off; users are informed of AI generation. | PM Agent / Dev Agent |
| **GDPR** | **Article 32** | Security of Processing | AES-256 encryption at rest, TLS 1.3 in transit, strict RBAC, and zero persistent external data logging. | Dev Agent / GitOps Agent |
| **EU AI Act** | **Article 10** | Data & Data Governance | Rigorous curation, toxicity filtering, and validation of retrieval corpus. | QA Agent / PM Agent |
| **EU AI Act** | **Article 12** | Technical Record-Keeping & Logging | Immutable logging of user queries, retrieved chunk IDs, similarity scores, reranker metrics, and model outputs. | Dev Agent / GitOps Agent |
| **EU AI Act** | **Article 13** | Transparency & Provision of Information | Explicit citation footers, source document links, confidence metrics, and synthetic content watermarking. | Dev Agent |
| **EU AI Act** | **Article 14** | Human Oversight | Admin override capabilities, hallucination rejection circuits, and fallback degradation policies. | Dev Agent / QA Agent |
| **EU AI Act** | **Article 15** | Accuracy, Robustness & Cybersecurity | RAGAS evaluation thresholds (Faithfulness > 0.90), prompt-injection fuzzer testing, resilient fallback behavior. | QA Agent |
| **EU AI Act** | **Article 50** | GPAI Transparency & Copyright Compliance | Compliance with open-weight sovereign model licenses and copyright-safe document ingestion practices. | PM Agent |
