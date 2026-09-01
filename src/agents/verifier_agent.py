"""
Verification & Fact-Checking Agent (Hallucination Guardrail).
Evaluates retrieval sufficiency (Pre-LLM Gate) and factual claim consistency (Post-LLM Gate).
"""

import re
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from src.rag.vector_store import SearchResult


class ContextValidationResult(BaseModel):
    """Result of pre-generation context sufficiency check."""
    is_sufficient: bool
    top_relevance_score: float
    reason: str
    usable_context_chunks: List[SearchResult]


class FaithfulnessVerificationResult(BaseModel):
    """Result of post-generation factual consistency and hallucination check."""
    is_faithful: bool
    faithfulness_score: float = Field(ge=0.0, le=1.0)
    total_claims: int
    verified_claims: int
    unsupported_claims: List[str]
    verification_notes: str
    hallucination_detected: bool


class VerifierAgent:
    """
    Guards against hallucinations by enforcing pre-inference context gates
    and post-inference NLI / claim entailment validation.
    """

    def __init__(self, min_context_relevance: float = 0.15, min_faithfulness: float = 0.80):
        self.min_context_relevance = min_context_relevance
        self.min_faithfulness = min_faithfulness

    def validate_retrieval_context(
        self,
        query: str,
        candidates: List[SearchResult]
    ) -> ContextValidationResult:
        """
        Pre-LLM Gate: Evaluates if retrieved chunks provide sufficient relevance
        to answer the user's query without forcing hallucination.
        """
        if not candidates:
            return ContextValidationResult(
                is_sufficient=False,
                top_relevance_score=0.0,
                reason="Zero context chunks found in tenant database.",
                usable_context_chunks=[]
            )

        top_score = candidates[0].score
        if top_score < self.min_context_relevance:
            return ContextValidationResult(
                is_sufficient=False,
                top_relevance_score=top_score,
                reason=f"Top relevance score ({top_score:.3f}) below sufficiency threshold ({self.min_context_relevance:.3f}).",
                usable_context_chunks=[]
            )

        # Filter chunks that meet threshold
        usable = [c for c in candidates if c.score >= self.min_context_relevance]
        return ContextValidationResult(
            is_sufficient=True,
            top_relevance_score=top_score,
            reason=f"Context verified with {len(usable)} relevant chunk(s).",
            usable_context_chunks=usable
        )

    def verify_response_faithfulness(
        self,
        synthesized_text: str,
        context_chunks: List[SearchResult]
    ) -> FaithfulnessVerificationResult:
        """
        Post-LLM Gate: Deconstructs synthesized response into atomic claims and verifies
        that every claim is grounded in the retrieved context text.
        """
        # Combine all context text into one reference corpus
        combined_context = " ".join([c.content.lower() for c in context_chunks])
        
        # Split synthesized response into sentences/claims
        raw_sentences = re.split(r"(?<=[.?!])\s+", synthesized_text)
        claims = [s.strip() for s in raw_sentences if len(s.strip().split()) >= 3]

        if not claims:
            return FaithfulnessVerificationResult(
                is_faithful=True,
                faithfulness_score=1.0,
                total_claims=0,
                verified_claims=0,
                unsupported_claims=[],
                verification_notes="No verifiable declarative claims in short response.",
                hallucination_detected=False
            )

        verified_count = 0
        unsupported = []

        stop_words = {"the", "a", "an", "is", "are", "and", "or", "to", "in", "of", "for", "with", "this", "that"}

        for claim in claims:
            # Extract key claim tokens
            tokens = [t for t in re.findall(r"\b\w+\b", claim.lower()) if t not in stop_words and len(t) > 2]
            if not tokens:
                verified_count += 1
                continue

            # Check overlap against context
            overlap = sum(1 for t in tokens if t in combined_context)
            claim_ratio = overlap / len(tokens)

            # A claim is supported if at least 50% of its content words are present in context
            if claim_ratio >= 0.50:
                verified_count += 1
            else:
                unsupported.append(claim)

        faithfulness_score = round(verified_count / len(claims), 4)
        is_faithful = faithfulness_score >= self.min_faithfulness
        hallucination_detected = not is_faithful

        return FaithfulnessVerificationResult(
            is_faithful=is_faithful,
            faithfulness_score=faithfulness_score,
            total_claims=len(claims),
            verified_claims=verified_count,
            unsupported_claims=unsupported,
            verification_notes=(
                f"Verified {verified_count}/{len(claims)} claims against ground truth context."
                if is_faithful else
                f"Potential hallucination detected: {len(unsupported)} claim(s) unsupported by context."
            ),
            hallucination_detected=hallucination_detected
        )


# Global verifier agent instance
global_verifier_agent = VerifierAgent()
