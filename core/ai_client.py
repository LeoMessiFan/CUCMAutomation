"""
core/ai_client.py
─────────────────
Small OpenAI API wrapper for supplementary AI features.
"""

from openai import OpenAI
from typing import Optional

from config import Config


class AIClientError(RuntimeError):
    """Raised when the OpenAI call cannot be completed."""


def call_ai(prompt: str, system: str, model: Optional[str] = None) -> str:
    """
    Call OpenAI and return the response text.

    The SDK reads OPENAI_API_KEY from the environment by default, but we pass the
    configured value explicitly so .env loading remains centralized in config.py.
    """
    if not Config.OPENAI_API_KEY:
        raise AIClientError("OPENAI_API_KEY is not configured.")

    try:
        client = OpenAI(api_key=Config.OPENAI_API_KEY, timeout=Config.OPENAI_TIMEOUT)
        response = client.chat.completions.create(
            model=model or Config.OPENAI_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        raise AIClientError(f"OpenAI request failed: {exc}") from exc
