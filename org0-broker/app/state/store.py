from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas import Artifact, Message, Transcript


DATA_DIR = Path(__file__).resolve().parents[1] / "state" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_transcript(session_id: str, messages: List[Message]) -> Path:
    path = DATA_DIR / f"{session_id}-transcript.json"
    payload = [m.model_dump() for m in messages]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def save_artifact(session_id: str, artifact: Optional[Artifact]) -> Optional[Path]:
    if artifact is None:
        return None
    path = DATA_DIR / f"{session_id}-artifact.json"
    path.write_text(json.dumps(artifact.model_dump(), indent=2), encoding="utf-8")
    return path


