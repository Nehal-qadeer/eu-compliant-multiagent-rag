"""
EU Sovereign & Pluggable LLM Client.
Directs inference strictly to self-hosted vLLM/Ollama endpoints, optional Anthropic Claude,
or transparent query-focused grounded offline synthesis.
"""

import re
import os
import logging
import httpx
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from src.config import settings

logger = logging.getLogger(__name__)


class LLMResponse(BaseModel):
    """Structured response from LLM inference."""
    content: str
    model: str
    tokens_used: int
    finish_reason: str
    is_sovereign: bool = True
    provider: str


class SovereignLLMClient:
    """
    Sovereign LLM client supporting local vLLM, Ollama, Anthropic Claude (cloud),
    and transparent query-focused grounded synthesis.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.provider = provider or settings.SOVEREIGN_LLM_PROVIDER
        self.base_url = base_url or settings.SOVEREIGN_LLM_BASE_URL
        self.ollama_url = settings.OLLAMA_BASE_URL
        self.model_name = model_name or settings.SOVEREIGN_LLM_MODEL
        self._server_reachable: Optional[bool] = None

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1024
    ) -> LLMResponse:
        """
        Sends generation request to configured sovereign or cloud endpoint.
        Falls back transparently to offline grounded extraction if no endpoint is available.
        """
        # Tier 1: Anthropic Claude (if configured)
        if self.provider == "anthropic_claude" or (settings.ANTHROPIC_API_KEY and self.provider == "anthropic_claude"):
            try:
                timeout_cfg = httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0)
                headers = {
                    "x-api-key": settings.ANTHROPIC_API_KEY or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                payload = {
                    "model": settings.ANTHROPIC_MODEL,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
                async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                    resp = await client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        text = data["content"][0]["text"]
                        usage = data.get("usage", {}).get("output_tokens", len(text.split()))
                        logger.info(f"Generated response via Anthropic Claude ({settings.ANTHROPIC_MODEL})")
                        return LLMResponse(
                            content=text,
                            model=settings.ANTHROPIC_MODEL,
                            tokens_used=usage,
                            finish_reason="stop",
                            is_sovereign=False,  # Explicitly flagged as cloud API call
                            provider="anthropic_cloud"
                        )
            except Exception as e:
                logger.warning(f"Anthropic Claude inference failed: {e}. Falling back to sovereign offline extractor.")

        # Tier 2: Ollama Local Server
        if self.provider == "ollama" and self._server_reachable is not False:
            try:
                timeout_cfg = httpx.Timeout(connect=0.20, read=20.0, write=5.0, pool=2.0)
                payload = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False,
                    "options": {"temperature": temperature}
                }
                async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                    resp = await client.post(f"{self.ollama_url}/api/chat", json=payload)
                    if resp.status_code == 200:
                        self._server_reachable = True
                        data = resp.json()
                        content = data.get("message", {}).get("content", "")
                        logger.info(f"Generated response via local Ollama ({self.model_name})")
                        return LLMResponse(
                            content=content,
                            model=f"ollama/{self.model_name}",
                            tokens_used=len(content.split()),
                            finish_reason="stop",
                            is_sovereign=True,
                            provider="ollama_local"
                        )
            except Exception:
                self._server_reachable = False

        # Tier 3: Local Sovereign vLLM / OpenAI-Compatible Server
        if self.provider in ["local_vllm", "azure_eu", "mistral_eu"] and self._server_reachable is not False:
            try:
                timeout_cfg = httpx.Timeout(connect=0.05, read=15.0, write=5.0, pool=2.0)
                headers = {"Content-Type": "application/json"}
                api_key = os.getenv("SOVEREIGN_LLM_API_KEY", "")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                    payload = {
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers
                    )
                    if response.status_code == 200:
                        self._server_reachable = True
                        data = response.json()
                        choice = data["choices"][0]["message"]["content"]
                        usage = data.get("usage", {}).get("total_tokens", len(choice.split()))
                        logger.info(f"Generated response via sovereign endpoint ({self.model_name})")
                        return LLMResponse(
                            content=choice,
                            model=self.model_name,
                            tokens_used=usage,
                            finish_reason="stop",
                            is_sovereign=True,
                            provider=self.provider
                        )
            except Exception:
                self._server_reachable = False

        # Tier 4: Transparent Grounded Offline Synthesizer
        logger.info("No external LLM endpoint reachable. Operating in sovereign deterministic offline extraction mode.")
        return self._synthesize_grounded_answer(system_prompt, user_prompt)

    def _synthesize_grounded_answer(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """
        Grounded query-focused offline extractor.
        Accurately labeled as deterministic offline extraction with explicit source citations.
        """
        q_match = re.search(r"User Question:\s*(.+?)(?:\n\n|\nEnterprise)", user_prompt, re.DOTALL)
        query = q_match.group(1).strip() if q_match else ""
        query_words = set(re.findall(r"\b\w{3,}\b", query.lower()))

        context_matches = re.findall(
            r"\[Doc:\s*([^\]|]+)\s*\|\s*Section:\s*([^\]]+)\]\n([\s\S]*?)(?=(?:\[Doc:|$|---))",
            user_prompt
        )

        if not context_matches:
            answer = "Based on the provided enterprise documentation, no relevant contextual information was found to answer this query."
            return LLMResponse(
                content=answer,
                model="sovereign-grounded-extractor-v1 (deterministic-offline)",
                tokens_used=len(answer.split()),
                finish_reason="stop",
                is_sovereign=True,
                provider="sovereign_offline_extractor"
            )

        extracted_findings = []
        stop_words = {"what", "when", "where", "which", "how", "why", "the", "and", "for", "with", "this", "that", "about"}
        target_words = query_words - stop_words

        for doc_title, sec_title, body in context_matches:
            clean_body = body.strip()
            sentences = re.split(r"(?<=[.!?])\s+", clean_body)
            doc_label = doc_title.strip()
            sec_label = sec_title.strip()

            relevant_sentences = []
            for s in sentences:
                s_clean = s.strip()
                if not s_clean or len(s_clean.split()) < 4:
                    continue
                s_words = set(re.findall(r"\b\w{3,}\b", s_clean.lower()))
                match_count = len(target_words.intersection(s_words))
                if match_count > 0 or len(relevant_sentences) == 0:
                    relevant_sentences.append((match_count, s_clean))

            relevant_sentences.sort(key=lambda x: x[0], reverse=True)
            if relevant_sentences:
                top_facts = [s[1] for s in relevant_sentences[:2]]
                fact_text = " ".join(top_facts)
                citation = f"[{doc_label}: {sec_label}]"
                extracted_findings.append(f"• **{sec_label}**: {fact_text} (Source: {citation})")

        if extracted_findings:
            prefix = f"Regarding the inquiry on '{query}', the verified documentation states:" if query else "Based on the verified enterprise documentation:"
            answer = (
                f"{prefix}\n\n"
                + "\n\n".join(extracted_findings)
            )
        else:
            answer = "The retrieved documentation does not contain sufficient details to answer this query."

        return LLMResponse(
            content=answer,
            model="sovereign-grounded-extractor-v1 (deterministic-offline)",
            tokens_used=len(answer.split()),
            finish_reason="stop",
            is_sovereign=True,
            provider="sovereign_offline_extractor"
        )


# Global sovereign LLM client instance
global_sovereign_llm = SovereignLLMClient()

