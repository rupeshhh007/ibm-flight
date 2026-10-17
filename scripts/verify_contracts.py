from __future__ import annotations

import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from export_contracts import export_python_contracts  # noqa: E402


def collect_drift(expected: Path, actual: Path) -> list[str]:
    expected_files = {path.relative_to(expected) for path in expected.rglob("*") if path.is_file()}
    actual_files = {path.relative_to(actual) for path in actual.rglob("*") if path.is_file()}
    messages = [f"missing generated file: {path}" for path in sorted(expected_files - actual_files)]
    messages += [f"unexpected generated file: {path}" for path in sorted(actual_files - expected_files)]
    for relative in sorted(expected_files & actual_files):
        if not filecmp.cmp(expected / relative, actual / relative, shallow=False):
            messages.append(f"stale generated file: {relative}")
    return messages


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aeroguard-contract-check-") as directory:
        temporary_root = Path(directory)
        export_python_contracts(temporary_root)
        ts_output = temporary_root / "frontend" / "src" / "api" / "generated" / "schema.d.ts"
        ts_output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "npm.cmd" if os.name == "nt" else "npm",
                "--prefix",
                str(REPOSITORY_ROOT / "frontend"),
                "exec",
                "--",
                "openapi-typescript",
                str(temporary_root / "contracts" / "generated" / "openapi.json"),
                "-o",
                str(ts_output),
            ],
            check=True,
        )
        drift = collect_drift(
            REPOSITORY_ROOT / "contracts" / "generated",
            temporary_root / "contracts" / "generated",
        )
        drift += collect_drift(
            REPOSITORY_ROOT / "frontend" / "src" / "api" / "generated",
            temporary_root / "frontend" / "src" / "api" / "generated",
        )
    if drift:
        print("Contract drift detected:")
        for message in drift:
            print(f"- {message}")
        return 1
    print("Contract artifacts are current and deterministic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
