from pathlib import Path

from scripts.verify_contracts import collect_drift


def test_drift_comparison_detects_stale_artifact(tmp_path: Path) -> None:
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()
    (expected / "schema.json").write_text("current\n", encoding="utf-8")
    (actual / "schema.json").write_text("stale\n", encoding="utf-8")
    assert collect_drift(expected, actual) == ["stale generated file: schema.json"]
