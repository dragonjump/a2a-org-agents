from __future__ import annotations

import csv
import os
from pathlib import Path
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from .groq_decider import decide_with_groq


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "companyA_inventory.csv"


class Part(BaseModel):
    type: str
    data: Dict[str, Any] | str


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


app = FastAPI(title="A2A Server - MayLim (org1)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


STATE: Dict[str, Any] = {"tasks": {}}

# Load .env if present for GROQ_*
load_dotenv()

# Logger
logger = logging.getLogger("org1-maylim")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [org1] %(message)s")


def read_inventory() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"sku": "MACBOOK-PRO-14", "stock": 5, "reorder_threshold": 10, "reorder_amount": 20}
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            return {
                "sku": row["sku"],
                "stock": int(row["stock"]),
                "reorder_threshold": int(row["reorder_threshold"]),
                "reorder_amount": int(row["reorder_amount"]),
            }
    return {"sku": "MACBOOK-PRO-14", "stock": 5, "reorder_threshold": 10, "reorder_amount": 20}


@app.get("/")
def root():
    return {"ok": True, "service": "org1-maylim"}


@app.post("/a2a/task")
def create_task(task: Task):
    # Assign a local task id
    local_id = f"t-{len(STATE['tasks'])+1}"
    STATE["tasks"][local_id] = {"task": task, "messages": []}
    return {"task_id": local_id}


@app.post("/a2a/message")
def handle_message(req: MessageRequest):
    inv = read_inventory()
    STATE["tasks"].setdefault(req.task_id, {"task": None, "messages": []})
    STATE["tasks"][req.task_id]["messages"].append(req.message.model_dump())

    # Groq-backed decision with fallback
    content = req.message.content.lower()
    offered_price: Optional[float] = None
    import re

    m = re.search(r"(\$|usd\s*)?(\d{3,5})(?:\.(\d{2}))?", content)
    if m:
        offered_price = float(m.group(2) + (f".{m.group(3)}" if m.group(3) else ""))

    target = STATE["tasks"][req.task_id]["task"].target_price if STATE["tasks"][req.task_id]["task"] else None

    logger.info(
        "msg_in task=%s sku=%s qty=%s offered_price=%s target=%s content=%s",
        req.task_id,
        inv.get("sku"),
        inv.get("reorder_amount"),
        offered_price,
        target,
        req.message.content,
    )

    try:
        decision = decide_with_groq(
            sku=inv["sku"],
            quantity=inv["reorder_amount"],
            offered_price=offered_price,
            target_price=target,
            constraints=STATE["tasks"][req.task_id]["task"].constraints if STATE["tasks"][req.task_id]["task"] else {},
            partner_message=req.message.content,
            history_text=json.dumps(STATE["tasks"][req.task_id]["messages"][-4:]) if STATE["tasks"][req.task_id]["messages"] else "[]",
        )
        action = (decision.get("action") or "").lower()
        price = decision.get("price")
        logger.info("llm_decision task=%s action=%s price=%s", req.task_id, action, price)

        if action == "accept":
            price_to_use: Optional[float] = None
            if isinstance(price, (int, float)):
                price_to_use = float(price)
            elif offered_price is not None:
                price_to_use = float(offered_price)

            rationale = str(decision.get("rationale") or "")
            speak = str(decision.get("transcript_response") or "")
            if price_to_use is not None:
                reply_text = f"Accepted at ${price_to_use:.2f} for {inv['reorder_amount']} units."
            else:
                reply_text = "Accepted the offer."
            reply = Message(role="MayLim", content=reply_text, rationale=rationale, transcript_response=speak)
            logger.info(
                "reply_out task=%s status=accepted content=%s rationale=%s speak=%s",
                req.task_id,
                reply.content,
                reply.rationale,
                reply.transcript_response,
            )
            return {"reply": reply.model_dump(), "status": "accepted"}

        if action == "counter" and isinstance(price, (int, float)):
            rationale = str(decision.get("rationale") or "")
            speak = str(decision.get("transcript_response") or "")
            reply = Message(role="MayLim", content=f"Counter: ${float(price):.2f}", rationale=rationale, transcript_response=speak)
            logger.info(
                "reply_out task=%s status=counter content=%s rationale=%s speak=%s",
                req.task_id,
                reply.content,
                reply.rationale,
                reply.transcript_response,
            )
            return {"reply": reply.model_dump(), "status": "counter"}

        # If LLM could not produce a usable decision/price, reject without hardcoded pricing
        rationale = str(decision.get("rationale") or "")
        speak = str(decision.get("transcript_response") or "")
        reply = Message(
            role="MayLim",
            content="Rejecting offer: insufficient data to decide.",
            rationale=rationale,
            transcript_response=speak,
        )
        logger.info("decision_reject task=%s reason=insufficient_data", req.task_id)
        logger.info(
            "reply_out task=%s status=reject content=%s rationale=%s speak=%s",
            req.task_id,
            reply.content,
            reply.rationale,
            reply.transcript_response,
        )
        return {"reply": reply.model_dump(), "status": "reject"}

    except Exception:
        # On error, avoid hardcoded price; signal rejection so the broker can proceed
        logger.exception("decision_error task=%s", req.task_id)
        reply = Message(
            role="MayLim",
            content="Rejecting offer due to decision error.",
            rationale="Aiyo, got problem calling LLM just now, later try again la.",
            transcript_response="Sorry ah boss, system hiccup a bit. Can wait a while?",
        )
        logger.info(
            "reply_out task=%s status=reject content=%s rationale=%s speak=%s",
            req.task_id,
            reply.content,
            reply.rationale,
            reply.transcript_response,
        )
        return {"reply": reply.model_dump(), "status": "reject"}


