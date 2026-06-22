"""Client LLM unifié — abstraction Mistral.

Deux backends possibles, choisis via LLM_BACKEND :
  - mistral_api : API La Plateforme (hébergée en France). Clé requise.
  - local       : serveur local (vLLM/Ollama) compatible OpenAI. 100% on-prem.

Pour le reste du code, on parle toujours de `llm.chat(...)` / `llm.embed(...)`,
peu importe le backend. C'est important pour que l'on puisse basculer une
installation client de l'API cloud vers du full-local sans toucher au code.
"""
from __future__ import annotations

import json
import re
from typing import Any, Literal, TypedDict

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

Role = Literal["system", "user", "assistant"]


class ChatMessage(TypedDict):
    role: Role
    content: str


class LLMResponse(TypedDict):
    content: str
    model: str
    usage: dict[str, int]


class LLMClient:
    """Abstraction unique sur le LLM (Mistral cloud ou local)."""

    def __init__(self) -> None:
        self.backend: str = settings.llm_backend
        self._mistral: Any = None
        self._openai_compat: OpenAI | None = None
        self._setup()

    def _setup(self) -> None:
        if self.backend == "mistral_api":
            # On privilégie le SDK officiel Mistral quand la clé est présente.
            if not settings.mistral_api_key:
                raise RuntimeError(
                    "LLM_BACKEND=mistral_api mais MISTRAL_API_KEY est vide. "
                    "Renseignez-le dans .env (ou passez LLM_BACKEND=local)."
                )
            try:
                from mistralai import Mistral
                self._mistral = Mistral(api_key=settings.mistral_api_key)
            except ImportError as e:
                raise RuntimeError("Paquet 'mistralai' manquant.") from e
        elif self.backend == "local":
            # vLLM/Ollama exposent une API compatible OpenAI.
            self._openai_compat = OpenAI(
                base_url=settings.local_llm_base_url,
                api_key="not-needed",
            )
        else:
            raise ValueError(f"LLM_BACKEND inconnu : {self.backend}")

    # ---------- Chat ----------
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: dict | None = None,  # {"type": "json_object"}
    ) -> LLMResponse:
        model = model or settings.mistral_model_large
        if self.backend == "mistral_api":
            return self._chat_mistral(
                messages, model, temperature, max_tokens, response_format
            )
        return self._chat_local(messages, model, temperature, max_tokens, response_format)

    def _chat_mistral(self, messages, model, temperature, max_tokens, response_format) -> LLMResponse:
        resp = self._mistral.chat.complete(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        usage = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
            "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
        }
        return LLMResponse(content=resp.choices[0].message.content or "", model=model, usage=usage)

    def _chat_local(self, messages, model, temperature, max_tokens, response_format) -> LLMResponse:
        kwargs: dict[str, Any] = dict(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if response_format:
            kwargs["response_format"] = response_format
        resp = self._openai_compat.chat.completions.create(**kwargs)
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
        }
        return LLMResponse(content=resp.choices[0].message.content or "", model=model, usage=usage)

    # ---------- Embeddings ----------
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.backend == "mistral_api":
            resp = self._mistral.embeddings.create(
                model=settings.mistral_embed_model,
                inputs=texts,
            )
            return [list(map(float, d.embedding)) for d in resp.data]
        # Local (vLLM/Ollama avec modèle d'embedding)
        resp = self._openai_compat.embeddings.create(
            model=settings.mistral_embed_model,
            input=texts,
        )
        return [list(map(float, d.embedding)) for d in resp.data]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]

    # ---------- Helpers ----------
    @staticmethod
    def extract_json(content: str) -> Any:
        """Récupère proprement un JSON noyé dans du texte markdown."""
        # Bloc ```json ... ```
        m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", content, re.DOTALL)
        raw = m.group(1) if m else content
        # Sinon, premier objet/tableau brut
        if not m:
            m = re.search(r"(\{.*\}|\[.*\])", content, re.DOTALL)
            raw = m.group(1) if m else content
        return json.loads(raw)


# ---------- Singleton paresseux ----------
# On ne crée le client qu'au premier appel : permet de lancer l'app même
# sans clé API (les routes non-IA restent utilisables, utile pour les tests).
_llm_instance: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMClient()
    return _llm_instance
