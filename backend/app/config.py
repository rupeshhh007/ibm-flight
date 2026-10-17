from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    database_path: str = "aeroguard.db"

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(database_path=getenv("AEROGUARD_DATABASE_PATH", "aeroguard.db"))
