## A2A Simple - Org0 Broker with Org1/Org2 Agents

This repo runs three services for a simple Agent2Agent-style negotiation:
- `org1-companyA-maylim` (buyer) 
- `org2-companyB-kumar` (seller)
- `org0-broker` (broker/orchestrator)

You are in org0.
Optionally, a Vite React frontend visualizes the transcript from `org0-broker`.

### Prerequisites
- Windows PowerShell
- Python 3.10+ installed on PATH (python)
- Node.js 18+ (for the frontend)

### Quick Start (recommended)
Open four PowerShell windows and run the following from the repo root:
```
 


kill -9 $(  lsof -t -i:8102)
netstat -ano | findstr :8102
taskkill /PID <PID> /F


```
Then open the UI: http://localhost:5173

Press Start to initiate a negotiation; the broker will orchestrate messages between Org1 and Org2 and produce a final artifact (quote) when agreed.

### Manual Start (alternative)

Start Org1 (MayLim):
```
cd org1-companyA-maylim
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8101

cd org1-companyA-maylim
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8101



```

Start Org2 (Kumar):
```
cd org2-companyB-kumar
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8102

cd org2-companyB-kumar
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt 
uvicorn app.main:app --host 127.0.0.1 --port 8102

```

Start Org0 (Broker):
```
cd org0-broker
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:ORG1_URL='http://127.0.0.1:8101'
$env:ORG2_URL='http://127.0.0.1:8102'
uvicorn app.main:app --host 127.0.0.1 --port 8001


cd org0-broker
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Start Frontend:
```
cd frontend
npm install
npm run dev
```

### Verify
- Org1 health: http://127.0.0.1:8101/
- Org2 health: http://127.0.0.1:8102/
- Broker health: http://127.0.0.1:8001/
- Transcript API: http://127.0.0.1:8001/api/transcript
- UI: http://localhost:5173

### How it works (brief)
- `org0-broker` exposes `/api/start`, `/api/transcript`, `/api/reset`.
- When started, broker calls Org2 for an offer, forwards to Org1 for counter/accept, and loops until agreement or turn limit.
- Final artifact (quote) is persisted under `org0-broker/app/state/data/`.

### Ports
- Org1 (MayLim): 8101
- Org2 (Kumar): 8102
- Org0 (Broker): 8001
- Frontend: 5173

### Troubleshooting
- If ports are in use, stop existing processes and restart scripts.
- Ensure your PowerShell policy permits running scripts (use a new terminal with "Run as administrator" if needed):
```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
- If Node is outdated, upgrade to Node 18+.


