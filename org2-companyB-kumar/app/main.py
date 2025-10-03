from __future__ import annotations

import csv
from pathlib import Path
import json
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import logging
from .groq_decider import decide_with_groq
import json


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "companyB_pricing.csv"


class Part(BaseModel):
    type: str
    # data: Dict[str, Any] | str 
    data: Union[Dict[str, Any], str]

class Message(BaseModel):
    role: str
    content: str
    rationale: str = ""
    transcript_response: str = ""
    parts: List[Part] = []


class Task(BaseModel):
    task_id: Optional[str] = None
    subject: str
    sku: str
    quantity: int
    target_price: Optional[float] = None
    constraints: Dict[str, Any] = {}
    context: Dict[str, Any] = {}


class MessageRequest(BaseModel):
    task_id: str
    message: Message


app = FastAPI(title="A2A Server - Kumar (org2)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


STATE: Dict[str, Any] = {"tasks": {}}
load_dotenv()
logger = logging.getLogger("org2-kumar")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [org2] %(message)s")


def read_pricing() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"sku": "MACBOOK-PRO-14", "stock": 100, "unit_price": 1999.0, "max_discount_pct": 0.10}
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            return {
                "sku": row["sku"],
                "stock": int(row["stock"]),
                "unit_price": float(row["unit_price"]),
                "max_discount_pct": float(row["max_discount_pct"]),
            }
    return {"sku": "MACBOOK-PRO-14", "stock": 100, "unit_price": 1999.0, "max_discount_pct": 0.10}


@app.get("/")
def root():
    return {"ok": True, "service": "org2-kumar"}


@app.post("/a2a/task")
def create_task(task: Task):
    local_id = f"t-{len(STATE['tasks'])+1}"
    STATE["tasks"][local_id] = {"task": task, "messages": []}
    return {"task_id": local_id}


@app.post("/a2a/message")
def handle_message(req: MessageRequest):
    price = read_pricing()
    STATE["tasks"].setdefault(req.task_id, {"task": None, "messages": []})
    STATE["tasks"][req.task_id]["messages"].append(req.message.model_dump())

    import re
    content = req.message.content.lower()
    # Opening quote path
    if "request quote" in content or "quote" in content:
        buyer_price = None
    else:
        m = re.search(r"(\$|usd\s*)?(\d{3,5})(?:\.(\d{2}))?", content)
        buyer_price = float(m.group(2) + (f".{m.group(3)}" if m.group(3) else "")) if m else None

    try:
        decision = decide_with_groq(
            sku=price["sku"],
            quantity=STATE["tasks"][req.task_id]["task"].quantity if STATE["tasks"][req.task_id]["task"] else 0,
            buyer_price=buyer_price,
            unit_price=price["unit_price"],
            max_discount_pct=price["max_discount_pct"],
            constraints=STATE["tasks"][req.task_id]["task"].constraints if STATE["tasks"][req.task_id]["task"] else {},
            partner_message=req.message.content,
            history_text=json.dumps(STATE["tasks"][req.task_id]["messages"][-4:]) if STATE["tasks"][req.task_id]["messages"] else "[]",
        )
        action = (decision.get("action") or "").lower()
        offer_price = decision.get("price")
        rationale = str(decision.get("rationale") or "")
        speak = str(decision.get("transcript_response") or "")

        if action == "accept" and isinstance(buyer_price, (int, float)):
            reply = Message(role="Kumar", content=f"Accepted at ${buyer_price:.2f}", rationale=rationale, transcript_response=speak)
            logger.info("reply_out status=accepted content=%s rationale=%s speak=%s", reply.content, reply.rationale, reply.transcript_response)
            return {"reply": reply.model_dump(), "status": "accepted"}

        if action == "counter" and isinstance(offer_price, (int, float)):
            reply = Message(role="Kumar", content=f"Offer: ${float(offer_price):.2f}", rationale=rationale, transcript_response=speak)
            logger.info("reply_out status=offer content=%s rationale=%s speak=%s", reply.content, reply.rationale, reply.transcript_response)
            return {"reply": reply.model_dump(), "status": "offer"}

        reply = Message(role="Kumar", content="Rejecting: cannot meet requested price.", rationale=rationale, transcript_response=speak)
        logger.info("reply_out status=reject content=%s rationale=%s speak=%s", reply.content, reply.rationale, reply.transcript_response)
        return {"reply": reply.model_dump(), "status": "reject"}

    except Exception:
        logger.exception("decision_error org2")
        reply = Message(role="Kumar", content="Rejecting due to decision error.", rationale="System got issue la.", transcript_response="Paiseh, system problem a bit.")
        return {"reply": reply.model_dump(), "status": "reject"}


