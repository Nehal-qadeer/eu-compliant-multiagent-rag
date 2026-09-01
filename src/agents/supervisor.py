"""
Supervisor Orchestrator Agent.
Central state-machine orchestrating the entire multi-agent query, retrieval, verification, and audit pipeline.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from src.core.pii_sanitizer import PIISanitizer, global_pii_sanitizer
from src.core.audit_logger import AuditLogger, global_audit_logger
from src.agents.query_planner import QueryPlannerAgent, QueryPlan, global_query_planner
from src.agents.retrieval_agent import RetrievalAgent, global_retrieval_agent
from src.agents.verifier_agent import (
    VerifierAgent,
    ContextValidationResult,
    FaithfulnessVerificationResult,
    global_verifier_agent
)
from src.agents.synthesizer_agent import (
    ResponseSynthesizerAgent,
    SynthesizedOutput,
    Citation,
    global_synthesizer_agent
)


class MultiAgentRAGResult(BaseModel):
    """Final unified result of the multi-agent RAG workflow."""
    status: str  # 'SUCCESS', 'INSUFFICIENT_CONTEXT', 'HALLUCINATION_BLOCKED'
    query: str
    sanitized_query: str
    answer: str
    citations: List[Citation]
    faithfulness_score: float
    is_faithful: bool
    query_plan: QueryPlan
    model_name: str
    tokens_used: int
    audit_event_id: str
    record_hash: str
    eu_transparency_disclaimer: str


class MultiAgentSupervisor:
    """
    Supervisor Agent coordinating QueryPlanner, RetrievalAgent, VerifierAgent,
    ResponseSynthesizer, and AuditLogger.
    """

    def __init__(
        self,
        query_planner: Optional[QueryPlannerAgent] = None,
        retrieval_agent: Optional[RetrievalAgent] = None,
        verifier_agent: Optional[VerifierAgent] = None,
        synthesizer_agent: Optional[ResponseSynthesizerAgent] = None,
        pii_sanitizer: Optional[PIISanitizer] = None,
        audit_logger: Optional[AuditLogger] = None
    ):
        self.planner = query_planner or global_query_planner
        self.retriever = retrieval_agent or global_retrieval_agent
        self.verifier = verifier_agent or global_verifier_agent
        self.synthesizer = synthesizer_agent or global_synthesizer_agent
        self.sanitizer = pii_sanitizer or global_pii_sanitizer
        self.audit_logger = audit_logger or global_audit_logger

    async def run_pipeline(
        self,
        tenant_id: str,
        user_query: str,
        actor_id: str = "enterprise_user",
        top_k: int = 4
    ) -> MultiAgentRAGResult:
        """Executes the full end-to-end multi-agent RAG pipeline."""
        # 1. Ingress Query Sanitization (GDPR Art. 25)
        sanitized_req = self.sanitizer.sanitize(user_query, strategy="pseudonymize")
        clean_query = sanitized_req.sanitized_text

        # 2. Query Decomposition & Planning (Query Planner Agent)
        plan: QueryPlan = self.planner.plan_query(clean_query)

        # 3. Hybrid Dense + Sparse Retrieval & Cross-Encoder Rerank (Retrieval Agent)
        candidate_chunks = self.retriever.execute_retrieval(
            tenant_id=tenant_id,
            plan=plan,
            top_k=top_k
        )

        # 4. Pre-LLM Context Validation Gate (Verifier Agent)
        context_val: ContextValidationResult = self.verifier.validate_retrieval_context(
            query=clean_query,
            candidates=candidate_chunks
        )

        if not context_val.is_sufficient:
            # Safe Fallback: Prevent forced LLM hallucination
            fallback_answer = (
                "Insufficient context in verified enterprise documents to answer this query truthfully. "
                "No matching policies or records meet the required confidence threshold."
            )
            audit_evt = self.audit_logger.log_event(
                event_type="QUERY_FALLBACK_INSUFFICIENT_CONTEXT",
                tenant_id=tenant_id,
                actor_id=actor_id,
                raw_content_to_hash=user_query,
                details={"reason": context_val.reason, "query": clean_query},
                compliance_tags=["EU_AI_ACT_ART_14_HUMAN_OVERSIGHT", "EU_AI_ACT_ART_15_ROBUSTNESS"]
            )
            return MultiAgentRAGResult(
                status="INSUFFICIENT_CONTEXT",
                query=user_query,
                sanitized_query=clean_query,
                answer=fallback_answer,
                citations=[],
                faithfulness_score=1.0,
                is_faithful=True,
                query_plan=plan,
                model_name="safe-fallback-circuit",
                tokens_used=0,
                audit_event_id=audit_evt.event_id,
                record_hash=audit_evt.record_hash or "",
                eu_transparency_disclaimer=self.synthesizer.EU_AI_ACT_DISCLAIMER
            )

        # 5. Grounded Sovereign Synthesis (Response Synthesizer Agent)
        synth_output: SynthesizedOutput = await self.synthesizer.synthesize(
            query=clean_query,
            context_chunks=context_val.usable_context_chunks
        )

        # 6. Post-LLM Factual Groundedness Verification (Verifier Agent)
        faith_val: FaithfulnessVerificationResult = self.verifier.verify_response_faithfulness(
            synthesized_text=synth_output.answer,
            context_chunks=context_val.usable_context_chunks
        )

        status_code = "SUCCESS" if faith_val.is_faithful else "HALLUCINATION_BLOCKED"
        final_answer = synth_output.answer

        if not faith_val.is_faithful:
            final_answer = (
                f"⚠️ [Verification Warning: Potential Hallucination Blocked]\n"
                f"The generated answer could not be fully verified against context.\n"
                f"Ground Truth Extract: {synth_output.answer}"
            )

        # 7. Record Immutable Audit Ledger Entry (EU AI Act Art. 12 & GDPR)
        audit_evt = self.audit_logger.log_event(
            event_type="MULTI_AGENT_QUERY_EXECUTION",
            tenant_id=tenant_id,
            actor_id=actor_id,
            raw_content_to_hash=f"{user_query}:{final_answer}",
            details={
                "subqueries": [sq.query_text for sq in plan.subqueries],
                "retrieved_chunk_ids": [c.chunk_id for c in synth_output.citations],
                "faithfulness_score": faith_val.faithfulness_score,
                "is_faithful": faith_val.is_faithful,
                "model": synth_output.model_name,
                "tokens_used": synth_output.tokens_used
            },
            compliance_tags=[
                "EU_AI_ACT_ART_12_RECORD_KEEPING",
                "EU_AI_ACT_ART_13_TRANSPARENCY",
                "GDPR_ART_25_PRIVACY_BY_DESIGN"
            ]
        )

        return MultiAgentRAGResult(
            status=status_code,
            query=user_query,
            sanitized_query=clean_query,
            answer=final_answer,
            citations=synth_output.citations,
            faithfulness_score=faith_val.faithfulness_score,
            is_faithful=faith_val.is_faithful,
            query_plan=plan,
            model_name=synth_output.model_name,
            tokens_used=synth_output.tokens_used,
            audit_event_id=audit_evt.event_id,
            record_hash=audit_evt.record_hash or "",
            eu_transparency_disclaimer=synth_output.eu_transparency_disclaimer
        )


# Global supervisor instance
global_multiagent_supervisor = MultiAgentSupervisor()
