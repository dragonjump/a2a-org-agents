from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from groq import Groq


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "companyA_inventory.csv"


def get_inventory_for_sku(sku: str) -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"sku": sku, "stock": 5, "reorder_threshold": 10, "reorder_amount": 20}
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("sku") == sku:
                return {
                    "sku": row["sku"],
                    "stock": int(row["stock"]),
                    "reorder_threshold": int(row["reorder_threshold"]),
                    "reorder_amount": int(row["reorder_amount"]),
                }
    # default if not found
    return {"sku": sku, "stock": 0, "reorder_threshold": 0, "reorder_amount": 0}


def _build_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_inventory_for_sku",
                "description": "Read local inventory data for a given SKU",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sku": {
                            "type": "string",
                            "description": "SKU to lookup, e.g. MACBOOK-PRO-14",
                        }
                    },
                    "required": ["sku"],
                },
            },
        }
    ]


def _call_tool(tool_name: str, arguments_json: str) -> str:
    # Parse tool arguments safely
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        args = {}

    if tool_name == "get_inventory_for_sku":
        sku = str(args.get("sku") or "")
        return json.dumps(get_inventory_for_sku(sku))

    return json.dumps({"error": f"unknown tool {tool_name}"})


def decide_with_groq(
    sku: str,
    quantity: int,
    offered_price: Optional[float],
    target_price: Optional[float],
    constraints: Dict[str, Any],
    partner_message: str = "",
    history_text: str = "[]",
) -> Dict[str, Any]:
    """Return a dict: { action: 'accept'|'counter'|'reject', price: float|None, rationale: str }"""

    api_key = os.getenv("GROQ_API_KEY2")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")

    # model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    temperature = float(os.getenv("GROQ_TEMPERATURE", "0.2"))
    max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "512"))

    client = Groq(api_key=api_key)

    system_prompt = (
        "You are MayLim, procurement for Company A. Your goals: minimize unit price while ensuring "
        "the requested quantity can be fulfilled. You must obey constraints (turn limits, price floors/ceilings).\n"
        "You can call tools to read local inventory for the SKU.\n"
        "Write the rationale in Manglish (friendly, <= 2 sentences). Also produce a one-line transcript_response (Manglish, polite).\n"
        "Do not repeat the exact same counter more than once; if the partner repeats the same price, either accept per rules or adjust slightly.\n"
        "Acceptance rule: If seller price within +$40 or within +2.5% of target_price, you MAY accept.\n"
        "Respond ONLY strict JSON: {\"action\": \"accept|counter|reject\", \"price\": number|null, \"rationale\": string, \"transcript_response\": string}."
    )

    user_prompt = (
        f"SKU: {sku}\n"
        f"Quantity: {quantity}\n"
        f"Seller offered price: {offered_price if offered_price is not None else 'unknown'}\n"
        f"Target price (if any): {target_price if target_price is not None else 'none'}\n"
        f"Constraints: {json.dumps(constraints)}\n\n"
        f"Partner message: {partner_message}\n"
        f"History JSON (recent turns): {history_text}\n\n"
        "Decide to accept or counter. If countering, propose a single numeric unit price."
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # First call (may request a tool)
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
        # Handle the first tool call only (sufficient for this scenario)
        tc = tool_calls[0]
        tool_name = tc.function.name
        tool_args = tc.function.arguments or "{}"
        tool_output = _call_tool(tool_name, tool_args)

        # Explicitly append an assistant message with tool_calls per API contract
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": tool_args,
                        },
                    }
                ],
            }
        )
        # Then append the tool response message
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_output})

        # Second call to get final JSON decision
        second = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = second.choices[0].message.content or "{}"
    else:
        content = choice.message.content or "{}"

    # Parse decision JSON
    try:
        decision = json.loads(content)
    except json.JSONDecodeError:
        decision = {"action": "counter", "price": offered_price or 1900.0, "rationale": "fallback", "transcript_response": "Can give better price ah?"}

    # Coerce fields
    action = str(decision.get("action") or "counter").lower()
    price_val = decision.get("price")
    try:
        price = float(price_val) if price_val is not None else None
    except Exception:
        price = None
    rationale = str(decision.get("rationale") or "")
    transcript_response = str(decision.get("transcript_response") or "")

    return {"action": action, "price": price, "rationale": rationale, "transcript_response": transcript_response}


