from dataclasses import dataclass
from os import getenv
from typing import Literal


@dataclass(frozen=True)
class Settings:
    database_path: str = "aeroguard.db"
    agent_mode: Literal["mock", "deterministic"] = "mock"

    @classmethod
    def from_environment(cls) -> "Settings":
        # Opt-in real-agent simulation; the safe, dependency-free mock remains
        # the default for the classroom demo and standard smoke tests.
        mode = getenv("AEROGUARD_AGENT_MODE", "mock")
        if mode not in ("mock", "deterministic"):
            raise ValueError("AEROGUARD_AGENT_MODE must be 'mock' or 'deterministic'")
        return cls(database_path=getenv("AEROGUARD_DATABASE_PATH", "aeroguard.db"), agent_mode=mode)
