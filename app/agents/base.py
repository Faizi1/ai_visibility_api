"""
Base agent — shared Anthropic client setup and JSON-safe response parsing.
All three agents inherit from this to keep LLM wiring in one place.
"""
from __future__ import annotations

import json
import os
import re
import structlog

log = structlog.get_logger()

# ── Lazy client singleton ────────────────────────────────────────────
_client = None


def get_client():
    """Return (and cache) the Anthropic client."""
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


class BaseAgent:
    """
    Shared base for all three agents.

    Subclasses implement:
        _system_prompt  → str property
        run(**kwargs)   → dict
    """

    MODEL = "claude-opus-4-5"       # powerful enough for structured JSON
    MAX_TOKENS = 4096

    # ── LLM call ────────────────────────────────────────────────────
    def _call_llm(self, user_prompt: str, max_tokens: int | None = None) -> tuple[str, int]:
        """
        Send a prompt to Claude and return (raw_text, tokens_used).
        Raises on network errors; malformed JSON is handled by callers.
        """
        client = get_client()
        response = client.messages.create(
            model=self.MODEL,
            max_tokens=max_tokens or self.MAX_TOKENS,
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens
        log.debug("llm_response", agent=self.__class__.__name__, tokens=tokens, chars=len(text))
        return text, tokens

    # ── JSON extraction ──────────────────────────────────────────────
    @staticmethod
    def _extract_json(raw: str) -> dict | list:
        """
        Robustly extract JSON from an LLM response.
        Handles:
          - bare JSON
          - ```json ... ``` fenced blocks
          - JSON embedded in prose
        Raises ValueError if no valid JSON found.
        """
        # 1. Try direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 2. Try stripping markdown fences
        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", raw)
        if fenced:
            try:
                return json.loads(fenced.group(1))
            except json.JSONDecodeError:
                pass

        # 3. Try finding largest JSON object in text
        for match in re.finditer(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw):
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue

        raise ValueError(f"No valid JSON found in LLM output. Raw (first 300 chars): {raw[:300]}")
