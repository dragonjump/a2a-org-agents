from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from groq import Groq


def conclude_with_groq(transcript: List[Dict[str, Any]], artifact: Dict[str, Any] | None) -> Dict[str, str]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        # Fallback conclusion
        return {
            "content": "Broker conclusion: agreement reached, proceed with paperwork.",
            "rationale": "Default fallback since no GROQ_API_KEY set.",
            "transcript_response": "Okay team, we proceed with PO and invoice, can?",
        }

    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    temperature = float(os.getenv("GROQ_TEMPERATURE", "0.3"))
    max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "512"))

    client = Groq(api_key=api_key)

    sys = (
        "You are the broker. Summarize if the negotiation concluded with a valid agreement (price & quantity present). "
        "If agreed, say to proceed with paperwork; else advise retry or abort. Write a short   rationale and a polite transcript_response. "
        "Respond ONLY JSON: {\"content\": string, \"rationale\": string, \"transcript_response\": string}."
    )

    usr = json.dumps({"transcript": transcript, "artifact": artifact}, ensure_ascii=False)

    res = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": usr},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = res.choices[0].message.content or "{}"
    try:
        obj = json.loads(content)
        if not isinstance(obj, dict):
            raise ValueError("bad json")
        return {
            "content": str(obj.get("content") or "Broker conclusion."),
            "rationale": str(obj.get("rationale") or ""),
            "transcript_response": str(obj.get("transcript_response") or ""),
        }
    except Exception:
        return {
            "content": "Broker conclusion: proceed with paperwork if artifact is present, else retry.",
            "rationale": "Fallback parse.",
            "transcript_response": "Okay la, we move forward if all set.",
        }


