# Enterprise EU Sovereign Multi-Agent RAG Platform

[![GDPR Privacy-by-Design](https://img.shields.io/badge/GDPR-Technical%20Measures%20by%20Design-blue.svg)](#)
[![EU AI Act Transparency](https://img.shields.io/badge/EU%20AI%20Act-Art.%2050%20Transparency%20Compliant-green.svg)](#)
[![Multi-Agent Architecture](https://img.shields.io/badge/Architecture-Autonomous%20Multi--Agent-orange.svg)](#)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](#)

A privacy-first, enterprise-grade Retrieval-Augmented Generation (RAG) platform powered by a coordinated 4-agent team. Built to implement **Technical and Organizational Measures (TOMs)** under the **European General Data Protection Regulation (GDPR Articles 17, 25, 32)** and transparency & record-keeping scaffolding under the **EU Artificial Intelligence Act (Articles 12, 13, 14, 15, 50)**.

---

## 🏛️ Autonomous 4-Agent Pipeline

```
User Query ➔ [PII Sanitizer (Presidio)]
                     │
                     ▼
          [1. Query Planner Agent] ➔ Sub-query decomposition & Intent routing
                     │
                     ▼
          [2. Retrieval Agent]    ➔ Hybrid Search (Dense Vectors + BM25) + Cross-Encoder Rerank
                     │
                     ▼
          [3. Verifier Pre-Gate]  ➔ Context sufficiency threshold check (rejects out-of-scope)
                     │
                     ▼
          [4. Synthesizer Agent]  ➔ Sovereign LLM generation with bracketed [Doc: Sec] citations
                     │
                     ▼
          [3. Verifier Post-Gate] ➔ Natural Language Inference (NLI) claim entailment check
                     │
                     ▼
          [Audit Ledger Logger]   ➔ SHA-256 hash-chained immutable regulatory log
```

---

## 🔬 Architecture & Implementation Transparency

To ensure complete clarity during technical reviews and security audits, the underlying implementation mechanics are structured across production neural models, cryptographic primitives, and deterministic fallbacks:

| Layer / Component | Primary Engine | Model / Standard | Offline / Fallback Mode |
| :--- | :--- | :--- | :--- |
| **PII Anonymization** | Microsoft Presidio Engine | Custom EU SEPA Recognizer + spaCy NER | Deterministic regex token recognizers |
| **Dense Vector Embeddings** | SentenceTransformers | `all-MiniLM-L6-v2` / `BAAI/bge-m3` (384-dim) | Normalized n-gram frequency hash vectors |
| **Sparse Keyword Search** | BM25 Lexical Engine | Okapi BM25 (`rank-bm25`) | Term frequency matching |
| **Passage Reranking** | Transformer Cross-Encoder | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Linguistic cross-token density scoring |
| **Hallucination Verification** | Natural Language Inference | `cross-encoder/nli-deberta-v3-small` | Token grounding & phrase overlap analysis |
| **Answer Synthesis** | Sovereign LLM / Transformers | Ollama / vLLM (`Mistral-7B-Instruct`) | Query-focused grounded extractor & citation builder |
| **Data At Rest Security** | AES-256-GCM Encryption | Cryptography primitives (NIST SP 800-38D) | In-memory / encrypted key vault |
| **Right to Erasure** | Cryptographic Key Revocation | GDPR Art. 17 Instant Crypto-Shredding | Mathematical tombstoning (zero re-indexing required) |
| **Audit Logging** | Tamper-Evident Ledger | SHA-256 Merkle hash chain | Append-only local structured JSONL |
| **Access Control** | RBAC Middleware | API Key & Bearer Token (`admin`, `dpo`, `employee`) | Role-gated FastAPI dependencies |

---

## ⚖️ Legal & Regulatory Standing in the European Union

### 1. General Data Protection Regulation (GDPR)
> [!NOTE]
> Software alone cannot be certified "GDPR-compliant" in a vacuum — organizational compliance requires operational Data Protection Impact Assessments (DPIA), Article 30 Records of Processing Activities (RoPA), and valid Data Processing Agreements (DPA).

This platform provides the foundational **Technical and Organizational Measures (TOMs) by Design**:
- **Article 25 (Data Protection by Design & Default)**: Automated Microsoft Presidio PII pseudonymization strips personal data (emails, German/EU phone numbers, IBANs, tax identifiers) *before* vector indexing or prompt ingestion.
- **Article 17 (Right to Erasure / "Right to be Forgotten")**: Implements **Cryptographic Shredding**. Every ingested document is encrypted with a dedicated AES-256 key. Revoking the key from the vault renders stored vectors and records mathematically unrecoverable without needing to re-index the entire vector database.
- **Article 32 (Security of Processing)**: Authenticated AES-256-GCM encryption with SHA-256 hash validation and Role-Based Access Control.

### 2. EU Artificial Intelligence Act (Regulation 2024/1689)
- **Classification**: Internal enterprise knowledge retrieval is categorized as **Minimal / Low Risk (General Purpose AI)** under the EU AI Act.
- **Article 50 Transparency**: Every synthesized response includes explicit machine-generated disclosures and grounded citation mappings `[Document: Section]`.
- **Article 12 Record-Keeping**: Cryptographically hashed audit ledger tracks all queries, subquery plans, retrieved chunk IDs, faithfulness scores, and model versions.
- **Article 15 Accuracy & Robustness**: Automated pre-generation context gates reject queries with insufficient relevance, preventing forced model hallucinations.

---

## 🚀 Quick Start

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/Nehal-qadeer/enterprise-eu-compliant-rag.git
cd enterprise-eu-compliant-rag

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 2. Run Interactive Live Demo
```bash
python scripts/live_demo.py
```

### 3. Run Test Suite
```bash
pytest tests/ -v
```

### 4. Start FastAPI Server
```bash
uvicorn src.api.main:app --reload --port 8000
# Access Swagger UI at http://localhost:8000/docs
```

---

## 📚 Technical Documentation
- [System Specification](docs/system_specification.md)
- [Use Case Diagram & Actor Matrix](docs/use_case_diagram.md)
- [End-to-End Data Flow Architecture](docs/data_flow_chart.md)
- [Regulatory Compliance & TOMs Matrix](docs/compliance_matrix.md)
- [Layman's Architecture Guide](docs/comprehensive_layman_guide.md)

