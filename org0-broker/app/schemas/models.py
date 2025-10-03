from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class Part(BaseModel):
    type: str
    # data: Dict[str, Any] | str 
    data: Union[Dict[str, Any], str]


class Message(BaseModel):
    role: str
    content: str
    rationale: str = ""
    transcript_response: str = ""
    parts: List[Part] = Field(default_factory=list)


class Task(BaseModel):
    task_id: Optional[str] = None
    subject: str
    sku: str
    quantity: int
    target_price: Optional[float] = None
    constraints: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)


class Artifact(BaseModel):
    type: str
    data: Dict[str, Any]


class Transcript(BaseModel):
    session_id: Optional[str]
    status: str
    transcript: List[Message]
    artifact: Optional[Artifact] = None


