"""
RAGAS and DeepEval Style Quantitative Evaluation Engine.
Computes Faithfulness, Answer Relevance, Context Precision, and Context Recall metrics
to quantify RAG retrieval and generation quality against EU AI Act Article 15 standards.
"""

import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class MetricScore(BaseModel):
    """Score and diagnostic details for a single RAG metric."""
    name: str
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    threshold: float
    details: Dict[str, Any] = Field(default_factory=dict)


class EvaluationReport(BaseModel):
    """Comprehensive evaluation report for a RAG query-response pair."""
    query: str
    overall_quality_score: float
    all_passed: bool
    faithfulness: MetricScore
    answer_relevance: MetricScore
    context_precision: MetricScore
    context_recall: MetricScore


class RagasEvaluator:
    """
    Evaluator implementing quantitative RAG benchmark metrics.
    """

    def __init__(
        self,
        faithfulness_threshold: float = 0.80,
        relevance_threshold: float = 0.75,
        precision_threshold: float = 0.70,
        recall_threshold: float = 0.75
    ):
        self.faithfulness_threshold = faithfulness_threshold
        self.relevance_threshold = relevance_threshold
        self.precision_threshold = precision_threshold
        self.recall_threshold = recall_threshold

    def _tokenize_clean(self, text: str) -> List[str]:
        """Extracts significant content tokens, stripping stop and functional question words."""
        stop_words = {
            "the", "a", "an", "is", "are", "and", "or", "to", "in", "of", "for", "with",
            "this", "that", "what", "how", "under", "all", "used", "method", "does", "can",
            "which", "who", "whom", "whose", "why", "when", "where", "been", "have", "has",
            "had", "will", "would", "should", "could", "be", "do", "did", "done"
        }
        tokens = re.findall(r"\b\w+\b", text.lower())
        return [t for t in tokens if t not in stop_words and len(t) > 2]

    def evaluate_faithfulness(self, answer: str, contexts: List[str]) -> MetricScore:
        """
        Measures the extent to which the generated answer is grounded in the retrieved context.
        Formula: (Number of supported claims) / (Total claims).
        """
        combined_context = " ".join([c.lower() for c in contexts])
        sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", answer) if len(s.strip().split()) >= 3]

        if not sentences:
            score = 1.0
            return MetricScore(
                name="Faithfulness",
                score=score,
                passed=score >= self.faithfulness_threshold,
                threshold=self.faithfulness_threshold,
                details={"verified_claims": 0, "total_claims": 0}
            )

        verified = 0
        for sent in sentences:
            tokens = self._tokenize_clean(sent)
            if not tokens:
                verified += 1
                continue
            overlap = sum(1 for t in tokens if t in combined_context)
            if (overlap / len(tokens)) >= 0.50:
                verified += 1

        score = round(verified / len(sentences), 4)
        return MetricScore(
            name="Faithfulness",
            score=score,
            passed=score >= self.faithfulness_threshold,
            threshold=self.faithfulness_threshold,
            details={"verified_claims": verified, "total_claims": len(sentences)}
        )

    def _match_tokens(self, tokens_a: set, tokens_b: set) -> int:
        """Matches tokens allowing for inflections, plurals, and stems (e.g. breach/breaches, notify/notification)."""
        matches = 0
        for ta in tokens_a:
            for tb in tokens_b:
                if ta == tb:
                    matches += 1
                    break
                elif len(ta) >= 4 and len(tb) >= 4 and (ta.startswith(tb[:4]) or tb.startswith(ta[:4])):
                    matches += 1
                    break
        return matches

    def evaluate_answer_relevance(self, query: str, answer: str) -> MetricScore:
        """
        Measures how directly the answer addresses the intent of the prompt.
        Formula: Keyword coverage and semantic length penalty.
        """
        q_tokens = set(self._tokenize_clean(query))
        a_tokens = set(self._tokenize_clean(answer))

        if not q_tokens:
            score = 1.0
        else:
            matched_count = self._match_tokens(q_tokens, a_tokens)
            coverage = matched_count / len(q_tokens)
            length_factor = min(1.0, len(a_tokens) / 10.0)
            score = round(min(1.0, (coverage * 0.70) + (length_factor * 0.30)), 4)

        return MetricScore(
            name="Answer Relevance",
            score=score,
            passed=score >= self.relevance_threshold,
            threshold=self.relevance_threshold,
            details={"matched_query_tokens": matched_count, "total_query_tokens": len(q_tokens)}
        )

    def evaluate_context_precision(self, query: str, contexts: List[str]) -> MetricScore:
        """
        Measures whether the highest-ranked context passages contain relevant signal for the query.
        """
        if not contexts:
            return MetricScore(
                name="Context Precision",
                score=0.0,
                passed=False,
                threshold=self.precision_threshold,
                details={"relevant_chunks": 0, "total_chunks": 0}
            )

        q_tokens = set(self._tokenize_clean(query))
        relevant_chunks = 0

        for ctx in contexts:
            c_tokens = set(self._tokenize_clean(ctx))
            if self._match_tokens(q_tokens, c_tokens) > 0:
                relevant_chunks += 1

        score = round(relevant_chunks / len(contexts), 4)
        return MetricScore(
            name="Context Precision",
            score=score,
            passed=score >= self.precision_threshold,
            threshold=self.precision_threshold,
            details={"relevant_chunks": relevant_chunks, "total_chunks": len(contexts)}
        )

    def evaluate_context_recall(self, ground_truth: str, contexts: List[str]) -> MetricScore:
        """
        Measures if the retrieved contexts successfully captured all key facts in the ground truth answer.
        """
        gt_tokens = set(self._tokenize_clean(ground_truth))
        combined_context = " ".join([c.lower() for c in contexts])

        if not gt_tokens:
            score = 1.0
        else:
            captured = sum(1 for t in gt_tokens if t in combined_context)
            score = round(captured / len(gt_tokens), 4)

        return MetricScore(
            name="Context Recall",
            score=score,
            passed=score >= self.recall_threshold,
            threshold=self.recall_threshold,
            details={"captured_ground_truth_tokens": captured, "total_gt_tokens": len(gt_tokens)}
        )

    def evaluate_triad(
        self,
        query: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None
    ) -> EvaluationReport:
        """Evaluates all RAG metrics and generates a unified report."""
        gt = ground_truth or answer
        m_faith = self.evaluate_faithfulness(answer, contexts)
        m_rel = self.evaluate_answer_relevance(query, answer)
        m_prec = self.evaluate_context_precision(query, contexts)
        m_rec = self.evaluate_context_recall(gt, contexts)

        all_passed = m_faith.passed and m_rel.passed and m_prec.passed and m_rec.passed
        overall = round(
            (m_faith.score * 0.35) + (m_rel.score * 0.25) + (m_prec.score * 0.20) + (m_rec.score * 0.20),
            4
        )

        return EvaluationReport(
            query=query,
            overall_quality_score=overall,
            all_passed=all_passed,
            faithfulness=m_faith,
            answer_relevance=m_rel,
            context_precision=m_prec,
            context_recall=m_rec
        )


# Global evaluator instance
global_ragas_evaluator = RagasEvaluator()
