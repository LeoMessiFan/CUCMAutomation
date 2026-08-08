"""
core/ai_diagnosis.py
────────────────────
Plain-English diagnosis for failed CUCM provisioning jobs.
"""

import json
import re
from typing import Any, Dict, Optional

from core.ai_client import call_ai


SYSTEM_PROMPT = (
    "You are a Cisco CUCM expert. Analyze AXL provisioning errors and explain "
    "them in plain English for IT administrators. Always return only valid JSON "
    "with this exact shape: {\"cause\": string, \"suggestion\": string, "
    "\"severity\": \"info\" | \"warning\" | \"error\" | \"critical\"}."
)

VALID_SEVERITIES = {"info", "warning", "error", "critical"}


def diagnose_error(step: str, error_msg: str, params: Dict[str, Any]) -> Dict[str, str]:
    """
    Return a normalized diagnosis dict for a failed provisioning step.

    If the model returns non-JSON text, keep the raw text so the UI can still
    display the supplemental diagnosis instead of discarding it.
    """
    prompt = json.dumps(
        {
            "step": step,
            "error": error_msg,
            "inputs": _safe_params(params),
        },
        ensure_ascii=True,
        indent=2,
    )

    raw = call_ai(prompt=prompt, system=SYSTEM_PROMPT)
    data = _parse_json_object(raw)
    if data is None:
        return {
            "cause": "AI returned an unstructured diagnosis.",
            "suggestion": raw[:1200] if raw else "No AI diagnosis text was returned.",
            "severity": "warning",
            "raw": raw[:1200],
        }

    severity = str(data.get("severity", "error")).lower().strip()
    if severity not in VALID_SEVERITIES:
        severity = "error"

    return {
        "cause": str(data.get("cause") or "No cause provided.").strip(),
        "suggestion": str(data.get("suggestion") or "No suggestion provided.").strip(),
        "severity": severity,
    }


def _safe_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Keep useful provisioning context while avoiding secret/config values."""
    allowed = {
        "mirror_dn",
        "new_dn",
        "user_id",
        "full_name",
        "vm_enable",
        "phone_mac",
        "phone_model",
        "jabber_model",
    }
    return {key: params.get(key, "") for key in allowed}


def _parse_json_object(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None

    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    return parsed if isinstance(parsed, dict) else None
