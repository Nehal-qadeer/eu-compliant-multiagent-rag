"""
Multi-Agent Query API Route.
Receives user natural language queries, coordinates multi-agent workflow, and returns verified responses.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.agents.supervisor import MultiAgentSupervisor, MultiAgentRAGResult, global_multiagent_supervisor

router = APIRouter(prefix="/api/v1/query", tags=["Multi-Agent RAG Query"])


class QueryRequest(BaseModel):
    """Payload for submitting a query to the multi-agent RAG system."""
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    query: str = Field(..., description="Natural language question or search prompt")
    actor_id: str = Field(default="enterprise_user", description="ID of querying user")
    top_k: int = Field(default=4, ge=1, le=20, description="Max number of candidate chunks to synthesize")


@router.post("", response_model=MultiAgentRAGResult, status_code=status.HTTP_200_OK)
async def query_multi_agent_rag(payload: QueryRequest):
    """
    Executes the enterprise multi-agent RAG pipeline:
    1. Query sanitization (PII & injection filtering)
    2. Query planning & decomposition
    3. Hybrid dense (vector) + sparse (BM25) retrieval
    4. Cross-encoder reranking
    5. Pre-LLM context sufficiency verification
    6. Grounded sovereign LLM synthesis
    7. Post-LLM factual consistency (hallucination) verification
    8. Immutable EU AI Act Art. 12 audit logging
    """
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    result: MultiAgentRAGResult = await global_multiagent_supervisor.run_pipeline(
        tenant_id=payload.tenant_id,
        user_query=payload.query,
        actor_id=payload.actor_id,
        top_k=payload.top_k
    )

    return result
