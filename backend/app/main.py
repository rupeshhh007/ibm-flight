from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import Settings
from app.contracts.models import CommonApiError
from app.core.clock import VirtualClock
from app.core.event_bus import InMemoryEventPublisher
from app.core.event_store import SQLiteEventStore
from app.core.orchestrator import DomainError, Orchestrator
from app.modules.guardian import MockGuardianAgent
from app.modules.sentinel import MockSentinelAgent
from app.modules.simulator import MockAircraftSimulator
from app.modules.vision import MockVisionAdapter


def create_app(
    database_path: str | Path | None = None,
    *,
    agent_mode: Literal["mock", "deterministic"] | None = None,
) -> FastAPI:
    """Create one simulation API with explicit, opt-in deterministic agents.

    Defaults to the frozen v1 mock demo. In deterministic mode, the real
    Guardian and Sentinel are both injected through their public Protocols.
    All orchestration and simulator authorization remain in the same root.
    """
    settings = Settings.from_environment()
    mode = settings.agent_mode if agent_mode is None else agent_mode
    if mode not in ("mock", "deterministic"):
        raise ValueError("agent_mode must be 'mock' or 'deterministic'")
    if mode == "deterministic":
        # Lazy imports avoid eagerly initializing optional modules in mock mode.
        # These are the owned public exports, not feature-private internals.
        from app.modules.guardian import DeterministicGuardianAgent
        from app.modules.sentinel import DeterministicSentinelAgent

        guardian = DeterministicGuardianAgent()
        sentinel = DeterministicSentinelAgent()
    else:
        guardian = MockGuardianAgent()
        sentinel = MockSentinelAgent()

    store = SQLiteEventStore(database_path or settings.database_path)
    orchestrator = Orchestrator(
        store=store,
        publisher=InMemoryEventPublisher(),
        clock=VirtualClock(),
        vision=MockVisionAdapter(),
        simulator=MockAircraftSimulator(),
        guardian=guardian,
        sentinel=sentinel,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.orchestrator.close()

    app = FastAPI(
        title="AeroGuard Simulation API",
        version="1.0.0",
        description="SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE",
        lifespan=lifespan,
    )
    app.state.orchestrator = orchestrator
    app.state.agent_mode = mode

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        error = CommonApiError(code=exc.code, message=exc.message)
        return JSONResponse(status_code=exc.status_code, content=error.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in exc.errors()]
        error = CommonApiError(code="VALIDATION_ERROR", message="Request validation failed", details=details)
        return JSONResponse(status_code=422, content=error.model_dump(mode="json"))

    app.include_router(router)
    return app


app = create_app()
