# Placeholder for ADK A2AServer integration per ADK Quickstart (Exposing)
# https://google.github.io/adk-docs/a2a/quickstart-exposing/

from fastapi import FastAPI


def create_app() -> FastAPI:
    # Later: wrap MayLim logic with ADK A2AServer
    return FastAPI(title="ADK A2A - MayLim (org1) placeholder")


