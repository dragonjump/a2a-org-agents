#!/usr/bin/env bash
set -euo pipefail 

python3 -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
export ORG1_URL=${ORG1_URL:-http://127.0.0.1:8101}
export ORG2_URL=${ORG2_URL:-http://127.0.0.1:8102}
exec uvicorn app.main:app --host 127.0.0.1 --port 8001

