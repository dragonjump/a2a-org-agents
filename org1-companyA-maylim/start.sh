#!/usr/bin/env bash
set -euo pipefail 
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
exec uvicorn app.main:app --host 127.0.0.1 --port 8101

