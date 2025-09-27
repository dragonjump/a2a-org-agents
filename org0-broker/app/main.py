from __future__ import annotations

import os
import logging
import re
import time
from typing import Any, Dict, List, Optional

import httpx
from app.state.store import save_artifact, save_transcript
from app.remote import RemoteA2aAgent
from app.groq_conclude import conclude_with_groq
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.schemas import Part, Message, Task, Artifact, Transcript


app = FastAPI(title="A2A Broker (org0)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


STATE: Dict[str, Any] = {
    "session_id": None,
    "status": "idle",
    "transcript": [],
    "artifact": None,
}

# Logger
logger = logging.getLogger("org0-broker")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [org0] %(message)s")


from app.config import resolve_org_urls
ORG1_URL, ORG2_URL = resolve_org_urls()


@app.get("/")
def root():
    return {"ok": True, "service": "org0-broker"}


@app.post("/api/reset")
def reset():
    STATE["session_id"] = None
    STATE["status"] = "idle"
    STATE["transcript"] = []
    STATE["artifact"] = None
    return {"ok": True}


@app.get("/api/transcript")
def get_transcript():
    return Transcript(
        session_id=STATE["session_id"],
        status=STATE["status"],
        transcript=list(STATE["transcript"]),
        artifact=STATE["artifact"],
    )


def extract_price(text: str) -> Optional[float]:
    match = re.search(r"(\$|USD\s*)?(\d{3,5})(?:\.(\d{2}))?", text)
    if not match:
        return None
    dollars = float(match.group(2))
    cents = match.group(3)
    if cents:
        return float(f"{int(dollars)}.{cents}")
    return float(dollars)


def build_history_summary(max_items: int = 4) -> str:
    try:
        import json as _json
        tail = STATE["transcript"][-max_items:]
        compact: List[Dict[str, Any]] = []
        for m in tail:
            compact.append({
                "role": getattr(m, "role", ""),
                "content": getattr(m, "content", ""),
                "rationale": getattr(m, "rationale", ""),
            })
        return _json.dumps(compact, ensure_ascii=False)
    except Exception:
        return "[]"


async def org_call_create_task(client: httpx.AsyncClient, base_url: str, task: Task) -> str:
    res = await client.post(f"{base_url}/a2a/task", json=task.model_dump(exclude_none=True))
    res.raise_for_status()
    return res.json()["task_id"]


async def org_call_message(client: httpx.AsyncClient, base_url: str, task_id: str, message: Message) -> Dict[str, Any]:
    res = await client.post(
        f"{base_url}/a2a/message",
        json={"task_id": task_id, "message": message.model_dump()},
    )
    res.raise_for_status()
    return res.json()


@app.post("/api/start")
async def start_negotiation():
    STATE["session_id"] = f"session-{int(time.time())}"
    STATE["status"] = "running"
    STATE["transcript"] = []
    STATE["artifact"] = None

    task = Task(
        subject="Bulk purchase negotiation",
        sku="MACBOOK-PRO-14",
        quantity=20,
        target_price=1789.0,
        constraints={"turn_limit": 7},
    )
    logger.info(
        "start session=%s sku=%s qty=%s target=%s constraints=%s",
        STATE["session_id"], task.sku, task.quantity, task.target_price, task.constraints,
    )

    # Seed transcript with MayLim stating purchase intent and target price
    intro_msg = Message(
        role="MayLim",
        content=(
            f"We want to buy {task.quantity} units of {task.sku}. "
            f"Our target unit price is ${task.target_price:.2f}. Can you quote your best price?"
        ),
        rationale="State requirement and target to anchor negotiation.",
        transcript_response=(
            f"Hello boss, need {task.quantity} units — can do at ${task.target_price:.2f} ah?"
        ),
    )
    STATE["transcript"].append(intro_msg)

    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
        org1 = RemoteA2aAgent(ORG1_URL)
        org2 = RemoteA2aAgent(ORG2_URL)
        org1_task_id = await org1.create_task(client, task)
        org2_task_id = await org2.create_task(client, task)

        # Ask seller (org2) for opening quote
        msg_to_org2 = Message(
            role="broker",
            content=(
                f"Request quote for {task.quantity} units of {task.sku}.\n"
                f"History:\n{build_history_summary()}"
            ),
        )
        try:
            r2 = await org2.send_message(client, org2_task_id, msg_to_org2)
            reply2 = Message(**r2["reply"])
            STATE["transcript"].append(reply2)
            logger.info(
                "recv org2 role=%s content=%s rationale=%s speak=%s",
                reply2.role, reply2.content, getattr(reply2, "rationale", ""), getattr(reply2, "transcript_response", ""),
            )
        except Exception as e:
            logger.exception("org2 initial quote failed")
            err_msg = Message(
                role="broker",
                content="Cannot proceed: seller (org2) did not respond in time.",
                rationale="Intervention: broker halted flow due to timeout.",
                transcript_response="Cannot proceed, seller agent got issue."
            )
            STATE["transcript"].append(err_msg)
            STATE["status"] = "error"
            # Persist partial transcript
            try:
                save_transcript(STATE["session_id"], STATE["transcript"])
            except Exception:
                pass
            return {"session_id": STATE["session_id"], "status": STATE["status"]}
        logger.info(
            "recv org2 role=%s content=%s rationale=%s speak=%s",
            reply2.role, reply2.content, getattr(reply2, "rationale", ""), getattr(reply2, "transcript_response", ""),
        )

        current_price = extract_price(reply2.content)
        if current_price is None:
            # Fallback
            current_price = 1900.0

        status = "in_progress"
        turn = 0
        price_agreed: Optional[float] = None

        while status == "in_progress" and turn < int(task.constraints.get("turn_limit", 7)):
            # Send seller's offer to buyer (org1)
            msg_to_org1 = Message(
                role="broker",
                content=(
                    f"Seller offer: ${current_price:.2f}\n"
                    f"History:\n{build_history_summary()}"
                ),
            )
            try:
                r1 = await org1.send_message(client, org1_task_id, msg_to_org1)
                reply1 = Message(**r1["reply"])
            except Exception:
                logger.exception("org1 counter/accept failed")
                err_msg = Message(
                    role="broker",
                    content="Cannot proceed: buyer (org1) did not respond in time.",
                    rationale="Intervention: broker halted flow due to timeout.",
                    transcript_response="Cannot proceed, buyer agent got issue."
                )
                STATE["transcript"].append(err_msg)
                STATE["status"] = "error"
                try:
                    save_transcript(STATE["session_id"], STATE["transcript"])
                except Exception:
                    pass
                return {"session_id": STATE["session_id"], "status": STATE["status"]}
            STATE["transcript"].append(reply1)
            logger.info(
                "recv org1 role=%s content=%s rationale=%s speak=%s",
                reply1.role, reply1.content, getattr(reply1, "rationale", ""), getattr(reply1, "transcript_response", ""),
            )

            if r1.get("status") == "accepted":
                price_agreed = extract_price(reply1.content) or current_price
                status = "accepted"
                # Broker speaks on acceptance
                broker_msg = Message(
                    role="broker",
                    content="Broker: buyer accepted. Proceed paperwork.",
                    rationale="Conclusion after buyer acceptance.",
                    transcript_response="Okay la, both parties agree — I’ll draft PO and invoice.",
                )
                STATE["transcript"].append(broker_msg)
                break

            if r1.get("status") == "reject":
                # Broker speaks on rejection
                broker_msg = Message(
                    role="broker",
                    content="Broker: buyer rejected. Cannot proceed.",
                    rationale="Conclusion after buyer rejection.",
                    transcript_response="Cannot proceed la, buyer cannot meet price — we pause and follow up.",
                )
                STATE["transcript"].append(broker_msg)

            # Forward buyer counter to seller
            counter_price = extract_price(reply1.content)
            if counter_price is None:
                counter_price = max(current_price - 10.0, 1500.0)

            msg_to_org2 = Message(
                role="broker",
                content=(
                    f"Buyer counter: ${counter_price:.2f}\n"
                    f"History:\n{build_history_summary()}"
                ),
            )
            try:
                r2 = await org2.send_message(client, org2_task_id, msg_to_org2)
                reply2 = Message(**r2["reply"])
            except Exception:
                logger.exception("org2 reply failed")
                err_msg = Message(
                    role="broker",
                    content="Cannot proceed: seller (org2) did not respond in time.",
                    rationale="Intervention: broker halted flow due to timeout.",
                    transcript_response="Cannot proceed, seller agent got issue."
                )
                STATE["transcript"].append(err_msg)
                STATE["status"] = "error"
                try:
                    save_transcript(STATE["session_id"], STATE["transcript"])
                except Exception:
                    pass
                return {"session_id": STATE["session_id"], "status": STATE["status"]}
            STATE["transcript"].append(reply2)
            logger.info(
                "recv org2 role=%s content=%s rationale=%s speak=%s",
                reply2.role, reply2.content, getattr(reply2, "rationale", ""), getattr(reply2, "transcript_response", ""),
            )

            if r2.get("status") == "accepted":
                price_agreed = extract_price(reply2.content) or counter_price
                status = "accepted"
                # Broker speaks on acceptance
                broker_msg = Message(
                    role="broker",
                    content="Broker: seller accepted. Proceed paperwork.",
                    rationale="Conclusion after seller acceptance.",
                    transcript_response="Okay la, both parties agree — I’ll draft PO and invoice.",
                )
                STATE["transcript"].append(broker_msg)
                break

            if r2.get("status") == "reject":
                # Broker speaks on rejection
                broker_msg = Message(
                    role="broker",
                    content="Broker: seller rejected. Cannot proceed.",
                    rationale="Conclusion after seller rejection.",
                    transcript_response="Cannot proceed la, seller cannot meet price — we pause and follow up.",
                )
                STATE["transcript"].append(broker_msg)

            next_price = extract_price(reply2.content)
            current_price = next_price if next_price is not None else current_price
            turn += 1

            # Near cutoff, broker posts notice
            turn_limit = int(task.constraints.get("turn_limit", 12))
            if turn >= turn_limit:
                cutoff_msg = Message(
                    role="broker",
                    content="Broker: turn limit reached. No agreement.",
                    rationale="No-overlap or stalled negotiation at cutoff.",
                    transcript_response="Aiyo, time up la — no agreement this round.",
                )
                STATE["transcript"].append(cutoff_msg)
                break

    final_artifact = None
    if price_agreed is not None:
        final_artifact = Artifact(
            type="quote",
            data={
                "sku": task.sku,
                "quantity": task.quantity,
                "unit_price": price_agreed,
                "total": round(price_agreed * task.quantity, 2),
                "currency": "USD",
            },
        )

    STATE["artifact"] = final_artifact
    STATE["status"] = "completed" if final_artifact else "completed"
    # persist to disk
    try:
        save_transcript(STATE["session_id"], STATE["transcript"])
        save_artifact(STATE["session_id"], STATE["artifact"])
    except Exception:
        pass
    if final_artifact:
        logger.info(
            "final artifact sku=%s qty=%s unit_price=%s total=%s",
            final_artifact.data.get("sku"),
            final_artifact.data.get("quantity"),
            final_artifact.data.get("unit_price"),
            final_artifact.data.get("total"),
        )
        # Append a broker LLM conclusion message to transcript
        concl = conclude_with_groq([
            m.model_dump() for m in STATE["transcript"]
        ], final_artifact.model_dump())
        broker_msg = Message(
            role="broker",
            content=concl.get("content", "Broker conclusion."),
            rationale=concl.get("rationale", ""),
            transcript_response=concl.get("transcript_response", ""),
        )
        STATE["transcript"].append(broker_msg)
    return {"session_id": STATE["session_id"], "status": STATE["status"]}


