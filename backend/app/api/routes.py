from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_orchestrator
from app.contracts.models import (
    ATCDecision,
    CommandResponse,
    CommunicationLinkRequest,
    EventHistoryResponse,
    HealthResponse,
    IncidentListResponse,
    PilotAcknowledgement,
    ScenarioAdvanceRequest,
    ScenarioListResponse,
    ScenarioResetRequest,
    ScenarioStartRequest,
    SystemSnapshot,
)
from app.core.orchestrator import Orchestrator


router = APIRouter()
OrchestratorDependency = Annotated[Orchestrator, Depends(get_orchestrator)]


@router.get("/healthz", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=HealthResponse)
def ready(orchestrator: OrchestratorDependency) -> HealthResponse:
    orchestrator.store.latest_seq()
    return HealthResponse(status="ready")


@router.get("/api/v1/state", response_model=SystemSnapshot)
def state(orchestrator: OrchestratorDependency) -> SystemSnapshot:
    return orchestrator.snapshot


@router.get("/api/v1/scenarios", response_model=ScenarioListResponse)
def scenarios(orchestrator: OrchestratorDependency) -> ScenarioListResponse:
    return orchestrator.scenarios()


@router.post("/api/v1/scenarios/start", response_model=CommandResponse)
def start(request: ScenarioStartRequest, orchestrator: OrchestratorDependency) -> CommandResponse:
    return orchestrator.start(request)


@router.post("/api/v1/scenarios/advance", response_model=CommandResponse)
def advance(request: ScenarioAdvanceRequest, orchestrator: OrchestratorDependency) -> CommandResponse:
    return orchestrator.advance(request)


@router.post("/api/v1/scenarios/reset", response_model=CommandResponse)
def reset(request: ScenarioResetRequest, orchestrator: OrchestratorDependency) -> CommandResponse:
    return orchestrator.reset(request)


@router.post("/api/v1/pilots/acknowledge", response_model=CommandResponse)
def acknowledge(request: PilotAcknowledgement, orchestrator: OrchestratorDependency) -> CommandResponse:
    return orchestrator.acknowledge(request)


@router.post("/api/v1/atc/decision", response_model=CommandResponse)
def atc_decision(request: ATCDecision, orchestrator: OrchestratorDependency) -> CommandResponse:
    return orchestrator.atc_decision(request)


@router.post("/api/v1/communications/link", response_model=CommandResponse)
def communications_link(request: CommunicationLinkRequest, orchestrator: OrchestratorDependency) -> CommandResponse:
    return orchestrator.set_link(request)


@router.get("/api/v1/incidents", response_model=IncidentListResponse)
def incidents(orchestrator: OrchestratorDependency) -> IncidentListResponse:
    return orchestrator.incidents()


@router.get("/api/v1/events", response_model=EventHistoryResponse)
def events(
    orchestrator: OrchestratorDependency,
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> EventHistoryResponse:
    return orchestrator.history(after_seq, limit)
