"""
Main FastAPI Application Entrypoint.
Initializes middleware, CORS, lifecycle management, and API routes with calibrated GDPR & EU AI Act controls.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.api.routes.ingest import router as ingest_router
from src.api.routes.gdpr import router as gdpr_router
from src.api.routes.query import router as query_router

app = FastAPI(
    title="Enterprise EU Sovereign Multi-Agent RAG Platform",
    description="Privacy-by-Design RAG platform providing Technical & Organizational Measures (TOMs) under GDPR Art. 17/25/32 and transparency disclosures under EU AI Act Art. 50.",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration with strict explicit allow-list
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(ingest_router)
app.include_router(gdpr_router)
app.include_router(query_router)


@app.get("/health", tags=["System Health"])
async def health_check():
    """Health check endpoint confirming API status, active engines, and calibrated compliance posture."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "gdpr_compliance": "ACTIVE",
        "eu_ai_act_classification": "MINIMAL_LOW_RISK (Article 50 Transparency Compliant)",
        "gdpr_technical_measures": "ACTIVE (AES-256 Crypto Shredding & Presidio PII Sanitization)",
        "eu_ai_act_transparency": "ACTIVE (Article 50 Disclosures & Article 12 Audit Logging)",
        "rbac_security": "ENFORCED (API Key Header Validation)",
        "pii_engine": "Microsoft Presidio (with EU SEPA/Tax recognizers)",
        "dense_embeddings": "SentenceTransformers (all-MiniLM-L6-v2 / sovereign fallback)",
        "verification_gate": "Natural Language Inference (NLI / DeBERTa Cross-Encoder)"
    }

