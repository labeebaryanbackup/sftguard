from __future__ import annotations

import json
from pathlib import Path

import pytest

from sftguard.cli import build_parser, main

REPOSITORY = Path(__file__).resolve().parents[2]


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_audit_cli_pass_exit_and_artifact(tmp_path) -> None:
    output = tmp_path / "audit.json"
    code = main(
        [
            "audit",
            "--train",
            str(REPOSITORY / "examples" / "clean-train.jsonl"),
            "--eval",
            str(REPOSITORY / "examples" / "clean-eval.jsonl"),
            "--output",
            str(output),
        ]
    )
    assert code == 0
    assert _read(output)["status"] == "PASS"


def test_gate_cli_pass_exit_and_artifact(tmp_path) -> None:
    output = tmp_path / "card.json"
    code = main(
        [
            "gate",
            "--base",
            str(REPOSITORY / "examples" / "base-eval.jsonl"),
            "--adapter",
            str(REPOSITORY / "examples" / "adapter-eval.jsonl"),
            "--contract",
            str(REPOSITORY / "examples" / "regression-contract.json"),
            "--output",
            str(output),
        ]
    )
    assert code == 0
    assert _read(output)["status"] == "PASS"


def test_demo_and_benchmark_cli_pass(tmp_path) -> None:
    demo = tmp_path / "demo.json"
    benchmark = tmp_path / "benchmark.json"
    assert main(["demo", "--output", str(demo)]) == 0
    assert main(["benchmark", "--seeds", "0-2", "--output", str(benchmark)]) == 0
    assert _read(demo)["status"] == "PASS"
    assert _read(benchmark)["development_only"] is True


def test_audit_cli_abstains_on_unreadable_input(tmp_path) -> None:
    output = tmp_path / "audit.json"
    code = main(
        [
            "audit",
            "--train",
            str(tmp_path / "missing.jsonl"),
            "--eval",
            str(tmp_path / "also-missing.jsonl"),
            "--output",
            str(output),
        ]
    )
    assert code == 2
    assert _read(output)["status"] == "ABSTAIN"


def test_gate_cli_fail_exit(tmp_path) -> None:
    base = REPOSITORY / "examples" / "base-eval.jsonl"
    adapter = tmp_path / "adapter.jsonl"
    rows = [json.loads(line) for line in base.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        if row["group"] == "target":
            row["value"] -= 0.1
    adapter.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    output = tmp_path / "card.json"
    code = main(
        [
            "gate",
            "--base",
            str(base),
            "--adapter",
            str(adapter),
            "--contract",
            str(REPOSITORY / "examples" / "regression-contract.json"),
            "--output",
            str(output),
        ]
    )
    assert code == 1
    assert _read(output)["status"] == "FAIL"


def test_cli_rejects_out_of_scope_benchmark_seed() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["benchmark", "--seeds", "10"])
    assert exc.value.code == 2


def test_cli_rejects_huge_benchmark_range_without_expanding_it() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["benchmark", "--seeds", "0-1000000000"])
    assert exc.value.code == 2
