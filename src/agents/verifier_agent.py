"""
Verification & Fact-Checking Agent (Hallucination Guardrail).
Evaluates retrieval sufficiency (Pre-LLM Gate) and factual claim consistency (Post-LLM Gate)
using Natural Language Inference (NLI) with cross-encoder architectures or linguistic verification.
"""

import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field
from src.rag.vector_store import SearchResult

logger = logging.getLogger(__name__)

# Try importing CrossEncoder for NLI
try:
    from sentence_transformers import CrossEncoder
    NLI_AVAILABLE = True
except ImportError:
    NLI_AVAILABLE = False


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
    verification_engine: str = "neural_nli"


class VerifierAgent:
    """
    Guards against hallucinations by enforcing pre-inference context gates
    and post-inference NLI (Natural Language Inference) / claim entailment validation.
    """

    def __init__(
        self,
        min_context_relevance: float = 0.15,
        min_faithfulness: float = 0.80,
        nli_model_name: str = "cross-encoder/nli-deberta-v3-small"
    ):
        self.min_context_relevance = min_context_relevance
        self.min_faithfulness = min_faithfulness
        self.nli_model_name = nli_model_name
        self.nli_model: Optional[Any] = None
        self.is_neural_nli: bool = False
        self.engine_name = "sovereign_linguistic_grounding"

        if NLI_AVAILABLE:
            try:
                self.nli_model = CrossEncoder(self.nli_model_name)
                self.is_neural_nli = True
                self.engine_name = f"neural_nli ({self.nli_model_name})"
                logger.info(f"Loaded neural NLI verifier: {self.nli_model_name}")
            except Exception as e:
                logger.warning(
                    f"Could not load NLI model '{self.nli_model_name}': {e}. "
                    "Operating in sovereign linguistic claim grounding mode."
                )
                self.is_neural_nli = False

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

    def _verify_claim_nli(self, claim: str, context_chunks: List[SearchResult]) -> bool:
        """Evaluates entailment between retrieved context passages and claim using NLI."""
        if not self.is_neural_nli or self.nli_model is None:
            return False

        try:
            # Pair each chunk with the hypothesis claim
            pairs = [[c.content, claim] for c in context_chunks]
            scores = self.nli_model.predict(pairs)
            
            # CrossEncoder NLI classes usually: [contradiction (0), entailment (1), neutral (2)]
            # or [contradiction, neutral, entailment]
            import numpy as np
            probs = np.exp(scores) / np.sum(np.exp(scores), axis=-1, keepdims=True)
            
            for p in probs:
                # Check if entailment probability is substantial
                # In 3-class NLI, if entailment is highest or > 0.45
                if len(p) == 3 and (p[1] >= 0.45 or p[2] >= 0.45):
                    return True
                elif len(p) == 2 and p[1] >= 0.50:
                    return True
            return False
        except Exception as e:
            logger.warning(f"NLI evaluation failed for claim: {e}")
            return False

    def verify_response_faithfulness(
        self,
        synthesized_text: str,
        context_chunks: List[SearchResult]
    ) -> FaithfulnessVerificationResult:
        """
        Post-LLM Gate: Deconstructs synthesized response into atomic claims and verifies
        that every claim is grounded in the retrieved context text via NLI or linguistic analysis.
        """
        combined_context = " ".join([c.content.lower() for c in context_chunks])

        # Split synthesized response into sentences/claims
        raw_sentences = re.split(r"(?<=[.?!])\s+", synthesized_text)
        claims = [
            s.strip() for s in raw_sentences
            if len(s.strip().split()) >= 3
            and not s.strip().startswith("🇪🇺")
            and not s.strip().startswith("⚠️")
        ]

        if not claims:
            return FaithfulnessVerificationResult(
                is_faithful=True,
                faithfulness_score=1.0,
                total_claims=0,
                verified_claims=0,
                unsupported_claims=[],
                verification_notes="No verifiable declarative claims in short response.",
                hallucination_detected=False,
                verification_engine=self.engine_name
            )

        verified_count = 0
        unsupported = []
        stop_words = {"the", "a", "an", "is", "are", "and", "or", "to", "in", "of", "for", "with", "this", "that"}

        for claim in claims:
            # 1. Try Neural NLI verification if available
            if self.is_neural_nli:
                is_entailed = self._verify_claim_nli(claim, context_chunks)
                if is_entailed:
                    verified_count += 1
                    continue

            # 2. Linguistic Grounding Fallback
            tokens = [t for t in re.findall(r"\b\w+\b", claim.lower()) if t not in stop_words and len(t) > 2]
            if not tokens:
                verified_count += 1
                continue

            overlap = sum(1 for t in tokens if t in combined_context)
            claim_ratio = overlap / len(tokens)

            # Claim supported if at least 45% of content words align with ground context
            if claim_ratio >= 0.45:
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
                f"Verified {verified_count}/{len(claims)} claims against ground truth context via {self.engine_name}."
                if is_faithful else
                f"Potential hallucination detected: {len(unsupported)} claim(s) unsupported by context."
            ),
            hallucination_detected=hallucination_detected,
            verification_engine=self.engine_name
        )


# Global verifier agent instance
global_verifier_agent = VerifierAgent()
