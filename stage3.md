### Stage 3: Integrate A2A SDK, Agent Cards, and Orchestration

### Objectives
- Replace HTTP shims with real A2A SDK client/server.
- Author formal agent cards for MayLim (org1) and Kumar (org2).
- Define shared schemas (Task, Message, Artifact, Part) for local typing; map to A2A messages.
- Plug org0 broker into A2A message flow; persist transcripts and artifacts.

### References
- a2a-python SDK: https://github.com/a2aproject/a2a-python
- Google ADK A2A intro: https://google.github.io/adk-docs/a2a/intro/
- IBM A2A overview: https://www.ibm.com/think/topics/agent2agent-protocol

### Deliverables
- org1/org2: A2A servers (`a2a-sdk[http-server]`) with handlers:
  - `POST /a2a/task` create task
  - `POST /a2a/message` streaming or step replies
  - Produce final Artifact on acceptance
- org0: A2A client orchestration:
  - Load agent cards, create Task, manage turn-based negotiation, store transcript and Artifact
  - Expose `/api/start`, `/api/transcript`, `/api/reset`
- Agent cards:
  - Identity, endpoint, capabilities, auth; stored under `cards/`
- Shared schemas:
  - Python `pydantic` models for Task, Message, Artifact, Part

### Tasks
1) Define shared schemas under `org0-broker/schemas` and vendor as needed to org1/org2.
2) Implement agent cards: `org1-companyA-maylim/cards/agent.json`, `org2-companyB-kumar/cards/agent.json`.
3) Install SDKs: `pip install "a2a-sdk[http-server]"` for servers; `pip install a2a-sdk` for broker client.
4) Implement org1/org2 server handlers backed by SDK constructs (tasks, messages, artifacts).
5) Implement org0 broker orchestration using SDK client to call remote agents.
6) Persist transcript/artifacts as JSON in `org0-broker/app/state/`.
7) Frontend: point to org0 and render transcript/artifacts.
8) E2E run scripts and smoke tests.

### Run plan
- Ports: org1 8101, org2 8102, org0 8001
- Env (org0): `ORG1_URL`, `ORG2_URL`; add auth if required later


