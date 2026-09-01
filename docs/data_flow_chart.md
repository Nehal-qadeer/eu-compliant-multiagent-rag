# End-to-End Data Flow Architecture

## 1. Sequence & Data Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as Enterprise User
    participant Gateway as API Gateway (FastAPI)
    participant PII as PII Engine (Presidio / NER)
    participant KeyStore as Key Vault (Crypto-Shredding)
    participant Orchestrator as Supervisor Orchestrator
    participant Retriever as Hybrid Retriever (Vector + BM25)
    participant VectorDB as Vector DB (Qdrant / pgvector)
    participant Reranker as Cross-Encoder Reranker
    participant Verifier as Fact-Check & Guardrail Agent
    participant SovereignLLM as EU Sovereign LLM (vLLM / Mistral)
    participant AuditLog as Audit Ledger (EU AI Act Log)

    %% Flow A: Ingestion Flow (Background)
    note over User, VectorDB: Phase A: Secure Ingestion Flow (Data Ingestion Pipeline)
    User->>Gateway: Upload Enterprise Document (PDF/Doc)
    Gateway->>PII: Extract Text & Scan for PII (GDPR Art. 25)
    PII->>KeyStore: Generate/Assign Document Encryption Key
    PII->>PII: Pseudonymize PII Entities (Tokens -> Pseudonyms)
    PII->>VectorDB: Index Contextual Chunks + Encrypted Tenant Metadata
    Gateway-->>User: Ingestion Complete (Document ID, Cryptographic Index Ref)

    %% Flow B: Query & Retrieval Flow
    note over User, AuditLog: Phase B: Multi-Agent Query & Sovereign Synthesis Flow
    User->>Gateway: Submit Query ("Summarize Q3 Compliance Audits")
    Gateway->>PII: Sanitize Query (Strip prompt injection & PII)
    PII->>Orchestrator: Cleaned Query Request
    
    Orchestrator->>Orchestrator: Query Planner: Decompose into Sub-Queries
    
    par Parallel Retrieval
        Orchestrator->>Retriever: Dense Vector Search (Cosine Sim)
        Retriever->>VectorDB: Query Vector DB (Tenant Namespace)
        VectorDB-->>Retriever: Top-K Vector Chunks
    and
        Orchestrator->>Retriever: Sparse Keyword Search (BM25)
        Retriever->>VectorDB: Query Sparse Index
        VectorDB-->>Retriever: Top-K Lexical Chunks
    end

    Retriever->>Reranker: Reciprocal Rank Fusion & Cross-Encoder Rerank
    Reranker-->>Orchestrator: Top Ranked Chunks with Relevance Scores

    Orchestrator->>Verifier: Validate Context Sufficiency
    alt Context Insufficient or Irrelevant
        Verifier-->>Orchestrator: Flag Retrieval Gap
        Orchestrator->>User: Safe Fallback: "Insufficient context in compliance documents."
    else Context Verified
        Verifier-->>Orchestrator: Context Approved
        Orchestrator->>SovereignLLM: Prompt with Grounded Context (Strict Citations)
        SovereignLLM-->>Orchestrator: Raw Synthesized Response
        
        Orchestrator->>Verifier: Hallucination & NLI Verification Check (RAGAS Groundedness)
        Verifier-->>Orchestrator: Verification Passed (Faithfulness Score > 0.92)
        
        Orchestrator->>AuditLog: Log Query Metadata, Chunk Citations & Explainability Data (EU AI Act Art. 12)
        Orchestrator->>PII: Re-hydrate Pseudonyms (if authorized for user role)
        PII->>Gateway: Final Verified Response + Citation Map
        Gateway-->>User: Verified Response with Attributions & AI Transparency Disclaimer
    end

    %% Flow C: Right to Erasure Flow
    note over User, VectorDB: Phase C: GDPR Article 17 Right to Erasure Flow
    User->>Gateway: Request Erasure for Document / User Data
    Gateway->>KeyStore: Revoke / Destroy Encryption Key (Crypto-Shredding)
    KeyStore-->>VectorDB: Mark Chunks Tombstoned
    Gateway->>AuditLog: Record Cryptographic Erasure Proof
    Gateway-->>User: Deletion Acknowledged & Cryptographically Verified
```

---

## 2. In-Depth Subsystem Data Transformations

### 2.1 Ingestion & Privacy Transformation Pipeline
```
[Raw Document: PDF/DOCX]
        │
        ▼ (Text Extraction & Structural Parsing)
[Structured Markdown / Section AST]
        │
        ▼ (Presidio / Local NER Analyzer)
[Identified PII Spans: {type: 'PERSON', text: 'Dr. Jane Smith', start: 42, end: 56}]
        │
        ▼ (Pseudonym Token Generator + Key Vault)
[Pseudonymized Text: "...authorized by <PERSON_a8f9> on 2026-04-12..."]
        │
        ▼ (Contextual Hierarchical Chunker - 512 tokens with 64 overlap)
[Context-Enriched Chunks: {chunk_id, doc_id, section, text_pseudonymized}]
        │
        ▼ (EU-Hosted Sovereign Embedding Model: e.g., BAAI/bge-m3 or local Ollama)
[Dense Vector (1024-dim)] + [Sparse Lexical Tokens (BM25)]
        │
        ▼ (Encrypted Indexing with Tenant AES-256 Key)
[Qdrant / pgvector Vector Store with Tenant Namespace]
```

### 2.2 Inference & Multi-Agent Verification Pipeline
```
[User Query] 
        │
        ▼ (Query Ingress Sanitizer)
[Clean Query] ──▶ [Supervisor Agent] ──▶ [Query Planner]
                                              │ (Sub-query Generation)
                                              ▼
                                 [Hybrid Retriever: Vector + BM25]
                                              │ (Candidate Chunks)
                                              ▼
                                 [Cross-Encoder Reranker]
                                              │ (Top-5 Reranked Chunks)
                                              ▼
                                 [Fact Verifier (Pre-LLM Gate)]
                                              │ (Approved Context)
                                              ▼
                                 [Sovereign EU LLM Inference]
                                              │ (Draft Synthesized Response)
                                              ▼
                                 [NLI Factual Consistency Guardrail]
                                  ├─ Pass (Score ≥ 0.90) ──▶ [Audit Log + Watermark] ──▶ [User]
                                  └─ Fail (Hallucination) ──▶ [Correction Loop / Safe Fallback]
```
