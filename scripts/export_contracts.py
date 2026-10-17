from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from app.contracts.models import DomainEvent, StoredEvent  # noqa: E402
from app.main import create_app  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def export_python_contracts(output_root: Path) -> None:
    generated = output_root / "contracts" / "generated"
    with tempfile.TemporaryDirectory(prefix="aeroguard-openapi-") as directory:
        app = create_app(Path(directory) / "schema.db")
        try:
            write_json(generated / "openapi.json", app.openapi())
        finally:
            app.state.orchestrator.close()
    write_json(generated / "events" / "domain_event.schema.json", DomainEvent.model_json_schema())
    write_json(generated / "events" / "stored_event.schema.json", StoredEvent.model_json_schema())
    for event_type, payload_type in sorted(DomainEvent._payload_types.items(), key=lambda item: item[0].value):
        write_json(
            generated / "events" / f"{event_type.value.lower()}.payload.schema.json",
            payload_type.model_json_schema(),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Export deterministic AeroGuard Python contracts")
    parser.add_argument("--output-root", type=Path, default=REPOSITORY_ROOT)
    arguments = parser.parse_args()
    export_python_contracts(arguments.output_root.resolve())


if __name__ == "__main__":
    main()
