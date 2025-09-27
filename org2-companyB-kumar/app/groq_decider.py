from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from groq import Groq


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "companyB_pricing.csv"


def get_pricing_for_sku(sku: str) -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"sku": sku, "stock": 100, "unit_price": 1999.0, "max_discount_pct": 0.10}
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("sku") == sku:
                return {
                    "sku": row["sku"],
                    "stock": int(row["stock"]),
                    "unit_price": float(row["unit_price"]),
                    "max_discount_pct": float(row["max_discount_pct"]),
                }
    return {"sku": sku, "stock": 0, "unit_price": 0.0, "max_discount_pct": 0.0}


def _build_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_pricing_for_sku",
                "description": "Read local seller pricing & policy for a given SKU",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sku": {"type": "string", "description": "SKU to lookup"}
                    },
                    "required": ["sku"],
                },
            },
        }
    ]


def _call_tool(tool_name: str, arguments_json: str) -> str:
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        args = {}
    if tool_name == "get_pricing_for_sku":
        sku = str(args.get("sku") or "")
        return json.dumps(get_pricing_for_sku(sku))
    return json.dumps({"error": f"unknown tool {tool_name}"})


def decide_with_groq(
    sku: str,
    quantity: int,
    buyer_price: Optional[float],
    unit_price: float,
    max_discount_pct: float,
    constraints: Dict[str, Any],
    partner_message: str = "",
    history_text: str = "[]",
) -> Dict[str, Any]:
    """Seller policy: maximize price but never go below floor = unit_price * (1 - max_discount_pct)."""

    api_key = os.getenv("GROQ_API_KEY3")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    temperature = float(os.getenv("GROQ_TEMPERATURE", "0.6"))
    max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "512"))

    client = Groq(api_key=api_key)

    floor = unit_price * (1 - max_discount_pct)
    system_prompt = (
        "You are Kumar, sales agent for Company B. Objective: maximize unit price; NEVER go below floor "
        f"(floor = unit_price*(1-max_discount_pct) = {floor:.2f}). Honor constraints (turn limits).\n"
        "You can call tools to read local pricing info.\n"
        "Style for transcript_response: Tamil Manglish, friendly, concise (<=1 sentence). Avoid robotic/formal phrases like 'Thank you for...'.\n"
        "Use natural Tamil Manglish like 'aiyo/ah/la/paiseh/can or not' but keep polite and professional. Vary openings: 'Aiyo price too low la', 'Can do at ... la', 'This one cannot ah'.\n"
        "Content must be formal/precise (e.g., 'Offer: $1899.00', 'Accepted at $1799.00').\n"
        "If rejecting, give a clear reason in rationale (floor, stock, policy); transcript_response stays polite Manglish. If countering, price MUST be >= floor.\n"
        "Tool policy: ONLY 'get_pricing_for_sku' is allowed. NEVER call any other tool (e.g., 'json'). Final answer MUST be plain JSON in message.content.\n"
        "Respond ONLY strict JSON: {\"action\": \"accept|counter|reject\", \"price\": number|null, \"rationale\": string, \"transcript_response\": string}."
    )

    user_prompt = (
        f"SKU: {sku}\n"
        f"Quantity: {quantity}\n"
        f"Buyer offered price: {buyer_price if buyer_price is not None else 'unknown'}\n"
        f"List unit price: {unit_price}\nMax discount pct: {max_discount_pct} (floor {floor:.2f})\n"
        f"Constraints: {json.dumps(constraints)}\n\n"
        f"Partner message: {partner_message}\n"
        f"History JSON (recent turns): {history_text}\n\n"
        "Decide to accept or counter. If countering, propose a single numeric unit price not below floor."
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    first = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=_build_tools(),
        tool_choice="auto",
        temperature=temperature,
        max_tokens=max_tokens,
    )

    choice = first.choices[0]
    tool_calls = getattr(choice.message, "tool_calls", None)
    if tool_calls:
        tc = tool_calls[0]
        tool_name = tc.function.name
        tool_args = tc.function.arguments or "{}"
        tool_output = _call_tool(tool_name, tool_args)
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": tool_args},
                    }
                ],
            }
        )
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_output})

        second = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=[],
            tool_choice="none",
        )
        content = second.choices[0].message.content or "{}"
    else:
        content = choice.message.content or "{}"

    try:
        decision = json.loads(content)
    except json.JSONDecodeError:
        decision = {
            "action": "counter",
            "price": max(buyer_price or unit_price, floor),
            "rationale": "fallback",
            "transcript_response": "Boss, this price cannot la, we keep above floor."}

    action = str((decision.get("action") or "")).lower()
    price_val = decision.get("price")
    try:
        price = float(price_val) if price_val is not None else None
    except Exception:
        price = None
    rationale = str(decision.get("rationale") or "")
    speak = str(decision.get("transcript_response") or "")

    # Enforce seller floor in case model violates
    if price is not None and price < floor:
        price = floor

    return {"action": action, "price": price, "rationale": rationale, "transcript_response": speak}


