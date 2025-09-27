### Stage 2: A2A Mode Plan (org0 broker + org1/org2 servers)

### Goals
- Transition to A2A protocol interaction with org0 as broker, org1/org2 as remote A2A servers.
- Use formal A2A concepts: A2A client/server, Agent card, Task, Message, Artifact, Part.
- Expose agents: MayLim (org1) and Kumar (org2) as HTTP servers; org0 orchestrates.

### References
- a2a-python SDK: [github.com/a2aproject/a2a-python](https://github.com/a2aproject/a2a-python)
- Google ADK A2A intro: [google.github.io/adk-docs/a2a/intro](https://google.github.io/adk-docs/a2a/intro/)
- IBM overview (Agent2Agent protocol): [ibm.com/think/topics/agent2agent-protocol](https://www.ibm.com/think/topics/agent2agent-protocol)

### Target folder structure
```
a2a-simple/
  org0-broker/
    app/                       # A2A client; negotiation orchestrator (FastAPI)
    cards/                     # Broker client agent card(s)
    schemas/                   # Task, Message, Artifact, Part (shared types)
    data/                      # Optional copies for simulation/testing
    requirements.txt
  org1-companyA-maylim/
    app/                       # A2A server for MayLim
    cards/                     # MayLim agent card
    data/companyA_inventory.csv
    requirements.txt
  org2-companyB-kumar/
    app/                       # A2A server for Kumar
    cards/                     # Kumar agent card
    data/companyB_pricing.csv
    requirements.txt
  frontend/                    # Reuse; points to org0 broker API
  README.md
```

### A2A concept mapping
- A2A client (client agent): org0 broker that initiates tasks and relays messages.
- A2A server (remote agent): org1 MayLim, org2 Kumar; each exposes A2A endpoints.
- Agent card: identity, endpoint, capabilities, auth for each agent; stored in `cards/`.
- Task: structured negotiation intent (sku, quantity, targets, constraints) created by org0.
- Message: turn-by-turn offers/counteroffers and decisions exchanged between parties.
- Artifact: outputs such as agreed price/quantity, quote details, CSV delta, summary.
- Part: structured subcomponents in Task/Message (e.g., sku spec, price term, quantity).

### Implementation outline
- org1/org2 servers
  - Install `a2a-sdk[http-server]` (per a2a-python) and FastAPI integration.
  - Define agent cards (id, org, endpoint, capabilities).
  - Implement handlers to accept Task ➜ emit Message stream ➜ produce Artifact on completion.
  - MayLim: read `companyA_inventory.csv`, compute reorder, aim for lower unit price.
  - Kumar: read `companyB_pricing.csv`, enforce `stock` and `max_discount_pct`, aim for higher price.

- org0 broker client
  - Install `a2a-sdk` client and FastAPI for orchestration API.
  - Load org1/org2 agent cards; create Task with Parts (sku, qty, price targets/limits).
  - Orchestrate negotiation loop: send Message to one side, forward counter to other, enforce floors/ceilings, turn limit, and acceptance criteria; persist transcript and final Artifact.
  - Expose `/api/start`, `/api/transcript`, `/api/reset` (frontend continues to talk to org0 only).

- Data & persistence
  - Keep CSV state local to each org server; broker receives only what is shared via Messages/Artifacts.
  - Persist transcript and artifacts in org0 as JSON for the frontend.

### Run plan (ports and env)
- org1 MayLim server: http://127.0.0.1:8101
- org2 Kumar server: http://127.0.0.1:8102
- org0 broker API: http://127.0.0.1:8001
- Env (org0): `ORG1_URL`, `ORG2_URL` pointing to org1/org2; optional `A2A_API_KEY_*` if auth used.

### Next steps
1) Scaffold `org0-broker`, `org1-companyA-maylim`, `org2-companyB-kumar` with minimal a2a-sdk server/client.
2) Write agent cards for MayLim and Kumar.
3) Define shared schemas (Task, Message, Artifact, Part) for local type safety.
4) Implement negotiation loop in org0 and minimal strategies in org1/org2.
5) Wire frontend to org0 transcript.
6) End-to-end run scripts and smoke tests.


