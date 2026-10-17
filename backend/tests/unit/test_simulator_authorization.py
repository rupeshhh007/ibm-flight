from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

import pytest

from app.contracts.enums import SimulatorActionType
from app.contracts.models import SentinelDecision
from app.modules.simulator import MockAircraftSimulator


def test_simulator_rejects_noncanonical_action_even_from_buggy_producer() -> None:
    simulator = MockAircraftSimulator()
    run_id = uuid4()
    now = datetime.now(timezone.utc)
    simulator.start(run_id, "normal_flight", now)
    with pytest.raises(ValueError, match="canonical SimulatorActionType"):
        simulator.apply_action(run_id, cast(SimulatorActionType, "LAND_REAL_AIRCRAFT"), cast(SentinelDecision, None), now)
