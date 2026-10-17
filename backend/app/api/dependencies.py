from fastapi import Request

from app.core.orchestrator import Orchestrator


def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator
