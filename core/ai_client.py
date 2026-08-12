"""
core/ai_client.py
─────────────────
AI client wrapper that supports two backends:
  1. Ollama (local) — used when OPENAI_API_KEY is not set (default for internal deployment)
  2. OpenAI API     — used when OPENAI_API_KEY is present in .env

Ollama endpoint: http://127.0.0.1:11434 (local, no internet required)
"""

import json
import requests
from config import Config


def call_ai(prompt: str, system: str = "") -> str:
    """
    Send a prompt to the configured AI backend and return the response text.

    Args:
        prompt: The user prompt / question
        system: Optional system role instruction

    Returns:
        AI response as a string
    """
    if Config.OPENAI_API_KEY:
        return _call_openai(prompt, system)
    else:
        return _call_ollama(prompt, system)


def _call_openai(prompt: str, system: str) -> str:
    """Call OpenAI API (requires OPENAI_API_KEY and internet access)."""
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=Config.OPENAI_API_KEY,
            timeout=Config.OPENAI_TIMEOUT,
        )
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        raise RuntimeError(f"OpenAI request failed: {e}")


def _call_ollama(prompt: str, system: str) -> str:
    """Call local Ollama instance (no internet required)."""
    try:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        response = requests.post(
            f"{Config.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": Config.OLLAMA_MODEL,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 512,
                }
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()

    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot connect to Ollama. Make sure 'ollama serve' is running.")
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama request timed out.")
    except Exception as e:
        raise RuntimeError(f"Ollama request failed: {e}")
