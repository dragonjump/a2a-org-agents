from __future__ import annotations

from typing import Any, Dict

import httpx
from app.schemas import Message, Task


class RemoteA2aAgent:
    """Lightweight wrapper simulating ADK RemoteA2aAgent semantics over HTTP.

    Provides create_task and message send operations compatible with our servers.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def create_task(self, client: httpx.AsyncClient, task: Task) -> str:
        res = await client.post(f"{self.base_url}/a2a/task", json=task.model_dump(exclude_none=True))
        res.raise_for_status()
        payload = res.json()
        return payload["task_id"]

    async def send_message(self, client: httpx.AsyncClient, task_id: str, message: Message) -> Dict[str, Any]:
        res = await client.post(
            f"{self.base_url}/a2a/message",
            json={"task_id": task_id, "message": message.model_dump()},
        )
        res.raise_for_status()
        return res.json()


