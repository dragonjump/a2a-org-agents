from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Tuple


def _read_card(path: Path) -> Optional[dict]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def resolve_org_urls() -> Tuple[str, str]:
    org1_env = os.getenv("ORG1_URL")
    org2_env = os.getenv("ORG2_URL")
    if org1_env and org2_env:
        return org1_env, org2_env

    # Try resolve from agent cards within monorepo
    root = Path(__file__).resolve().parents[2]
    org1_card = _read_card(root / "org1-companyA-maylim" / "cards" / "agent.json")
    org2_card = _read_card(root / "org2-companyB-kumar" / "cards" / "agent.json")

    org1_url = org1_env or (org1_card.get("endpoint") if org1_card else None) or "http://127.0.0.1:8101"
    org2_url = org2_env or (org2_card.get("endpoint") if org2_card else None) or "http://127.0.0.1:8102"
    return org1_url, org2_url


