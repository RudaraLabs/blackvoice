"""Free-form question answering.

Anything the rule-based router could not turn into a command lands here. Three
backends are supported and the choice lives in the config:

``ollama``     local models, nothing leaves the machine (the default)
``anthropic``  the Claude API, through the official ``anthropic`` SDK
``openai``     the OpenAI chat completions endpoint

Replies are kept short on purpose - this is a voice assistant, and nobody wants
six paragraphs read aloud.
"""

from __future__ import annotations

import logging
import os
from collections import deque
from typing import Deque, Dict, List

from ..nlu.intents import Intent
from .base import Reply, Skill, SkillContext

log = logging.getLogger(__name__)

#: how many previous turns to send along for context
HISTORY_TURNS = 6


class AISkill(Skill):
    name = "ai"

    def __init__(self, ctx: SkillContext) -> None:
        super().__init__(ctx)
        self.ai = ctx.config.ai
        self._history: Deque[Dict[str, str]] = deque(maxlen=HISTORY_TURNS * 2)
        self._client = None  # lazily built Anthropic client

    def handle(self, intent: Intent) -> Reply:
        if intent.action != "ask":
            return Reply.error("I do not know that AI command.")

        question = (intent.slots.get("question") or intent.text or "").strip()
        if not question:
            return Reply.error("I did not catch the question.")

        provider = (self.ai.provider or "none").lower()
        if provider == "none":
            return Reply.error("I did not understand that, and the AI backend is switched off.")

        try:
            answer = self._ask(provider, question)
        except Exception as exc:
            log.exception("AI backend %s failed", provider)
            return Reply.error(self._friendly_error(provider, exc))

        if not answer:
            return Reply.error("The AI backend returned an empty answer.")

        self._history.append({"role": "user", "content": question})
        self._history.append({"role": "assistant", "content": answer})
        return Reply(speech=answer, display=answer, data={"provider": provider})

    def reset(self) -> None:
        """Forget the conversation - bound to "new chat" in the tray menu."""
        self._history.clear()

    # -------------------------------------------------------------- routing
    def _ask(self, provider: str, question: str) -> str:
        if provider == "ollama":
            return self._ask_ollama(question)
        if provider == "anthropic":
            return self._ask_anthropic(question)
        if provider == "openai":
            return self._ask_openai(question)
        raise ValueError(f"unknown AI provider {provider!r}")

    def _messages(self, question: str) -> List[Dict[str, str]]:
        return list(self._history) + [{"role": "user", "content": question}]

    # --------------------------------------------------------------- ollama
    def _ask_ollama(self, question: str) -> str:
        import requests

        payload = {
            "model": self.ai.ollama_model,
            "stream": False,
            "messages": [{"role": "system", "content": self.ai.system_prompt}]
            + self._messages(question),
            "options": {"num_predict": self.ai.max_tokens},
        }
        response = requests.post(
            f"{self.ai.ollama_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=self.ai.timeout,
        )
        response.raise_for_status()
        return (response.json().get("message") or {}).get("content", "").strip()

    # ------------------------------------------------------------ anthropic
    def _anthropic_client(self):
        if self._client is not None:
            return self._client

        import anthropic

        key = self.ai.api_key or os.environ.get("ANTHROPIC_API_KEY")
        # With no explicit key the SDK still resolves ANTHROPIC_AUTH_TOKEN or an
        # `ant auth login` profile, so do not force one in.
        self._client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        return self._client

    def _ask_anthropic(self, question: str) -> str:
        client = self._anthropic_client()
        response = client.messages.create(
            model=self.ai.anthropic_model,
            max_tokens=self.ai.max_tokens,
            system=self.ai.system_prompt,
            # Spoken answers are short; low effort keeps the reply snappy.
            output_config={"effort": "low"},
            messages=self._messages(question),
        )

        if response.stop_reason == "refusal":
            return "I am not able to answer that one."

        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()

    # --------------------------------------------------------------- openai
    def _ask_openai(self, question: str) -> str:
        import requests

        key = self.ai.api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.ai.openai_model,
                "max_tokens": self.ai.max_tokens,
                "messages": [{"role": "system", "content": self.ai.system_prompt}]
                + self._messages(question),
            },
            timeout=self.ai.timeout,
        )
        response.raise_for_status()
        choices = response.json().get("choices") or []
        if not choices:
            return ""
        return (choices[0].get("message") or {}).get("content", "").strip()

    # ---------------------------------------------------------------- errors
    @staticmethod
    def _friendly_error(provider: str, exc: Exception) -> str:
        text = str(exc).lower()
        if provider == "ollama" and ("connection" in text or "refused" in text):
            return "Ollama is not running. Start it with: ollama serve"
        if "api_key" in text or "authentication" in text or "401" in text:
            return f"The {provider} API key is missing or invalid."
        if "timeout" in text or "timed out" in text:
            return "The AI backend took too long to answer."
        if "rate" in text and "limit" in text:
            return "The AI backend is rate limiting me. Try again shortly."
        return "I could not reach the AI backend."
