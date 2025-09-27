1. Initialize project structure: `backend/`, `frontend/`, `data/`. - DONE
2. Set up Python backend environment and dependencies (LangGraph, LangChain, Google A2A SDK, HTTP server, CORS). - DONE
3. Create CSV sample data: `data/companyA_inventory.csv` and `data/companyB_pricing.csv` (stock, price, max discount). - DONE
4. Implement procurement agent (MayLim): read Company A CSV, compute reorder quantity and target price, negotiate to minimize cost.
5. Implement seller agent (Kumar): read Company B CSV, enforce stock and max discount policy, negotiate to maximize price.
6. Compose agents with LangGraph: define shared state, nodes, and memory; ensure text-to-text messages are recorded.
7. Implement negotiation loop: offers/counteroffers, acceptance criteria, stalemate/turn limits, price floor/ceiling guards.
8. Expose backend endpoints: start negotiation, fetch transcript/status (polling), reset session; enable CORS. - DONE
9. Scaffold frontend with Vite + React. - DONE
10. Build UI: Start button, live transcript panel, run status/summary. - DONE
11. Wire frontend to backend: call start, poll transcript until completion, render updates. - DONE
12. Add configuration and run scripts for backend/frontend; document required environment variables.
13. Add tests: unit (agent strategies, CSV reads) and integration (happy-path negotiation).
14. Write README with setup, run, and usage instructions.
