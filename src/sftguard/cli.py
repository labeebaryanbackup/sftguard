"""Command-line interface for audit, gate, benchmark, and demo workflows."""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import Any

from . import __version__
from .artifacts import seal_artifact, write_artifact
from .audit import AuditConfig, audit_files
from .benchmark import run_development_benchmark, validate_development_seeds
from .demo import run_demo
from .io import InputError, read_json_bounded, read_jsonl_bounded
from .models import Status
from .regression import build_regression_card

EXIT_CODES = {Status.PASS: 0, Status.FAIL: 1, Status.ABSTAIN: 2}


def _bounded_positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _parse_seeds(value: str) -> tuple[int, ...]:
    try:
        selected: list[int] = []
        for part in value.split(","):
            part = part.strip()
            range_match = re.fullmatch(r"([0-9])-([0-9])", part)
            if range_match:
                start, end = (int(component) for component in range_match.groups())
                if end < start:
                    raise ValueError
                selected.extend(range(start, end + 1))
            elif re.fullmatch(r"[0-9]", part):
                selected.append(int(part))
            else:
                raise ValueError
        return validate_development_seeds(selected)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "seeds must be a subset of development seeds 0 through 9"
        ) from exc


def _input_abstention(schema_version: str) -> dict[str, Any]:
    return seal_artifact(
        {
            "schema_version": schema_version,
            "tool": {"name": "sftguard", "version": __version__},
            "status": Status.ABSTAIN,
            "reason_codes": ["invalid_unreadable_or_oversized_input"],
        }
    )


def _emit(artifact: dict[str, Any], output: str | None) -> int:
    write_artifact(output, artifact)
    status = Status(artifact["status"])
    return EXIT_CODES[status]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sftguard",
        description="Local-first correctness and regression gates for SFT pipelines.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    audit = commands.add_parser("audit", help="audit training and evaluation JSONL files")
    audit.add_argument("--train", required=True)
    audit.add_argument("--eval", required=True, dest="evaluation")
    audit.add_argument("--output")
    audit.add_argument("--max-file-bytes", type=_bounded_positive_int, default=16 * 1024 * 1024)
    audit.add_argument("--max-line-bytes", type=_bounded_positive_int, default=1024 * 1024)
    audit.add_argument("--max-records", type=_bounded_positive_int, default=100_000)

    gate = commands.add_parser("gate", help="build a paired target/retention Regression Card")
    gate.add_argument("--base", required=True)
    gate.add_argument("--adapter", required=True)
    gate.add_argument("--contract", required=True)
    gate.add_argument("--output")
    gate.add_argument("--max-file-bytes", type=_bounded_positive_int, default=16 * 1024 * 1024)
    gate.add_argument("--max-line-bytes", type=_bounded_positive_int, default=1024 * 1024)
    gate.add_argument("--max-records", type=_bounded_positive_int, default=100_000)

    benchmark = commands.add_parser(
        "benchmark", help="run the deterministic development-only synthetic matrix"
    )
    benchmark.add_argument("--seeds", type=_parse_seeds, default=tuple(range(10)))
    benchmark.add_argument("--output")

    demo = commands.add_parser("demo", help="run a redacted deterministic end-to-end demo")
    demo.add_argument("--output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "audit":
        config = AuditConfig(
            max_file_bytes=args.max_file_bytes,
            max_line_bytes=args.max_line_bytes,
            max_records=args.max_records,
        )
        return _emit(audit_files(args.train, args.evaluation, config=config), args.output)

    if args.command == "gate":
        try:
            base = read_jsonl_bounded(
                args.base,
                max_file_bytes=args.max_file_bytes,
                max_line_bytes=args.max_line_bytes,
                max_records=args.max_records,
            )
            adapter = read_jsonl_bounded(
                args.adapter,
                max_file_bytes=args.max_file_bytes,
                max_line_bytes=args.max_line_bytes,
                max_records=args.max_records,
            )
            contract, _, _ = read_json_bounded(args.contract, max_file_bytes=args.max_file_bytes)
            artifact = build_regression_card(
                base.records,
                adapter.records,
                contract,
                base_summary=base.summary,
                adapter_summary=adapter.summary,
            )
        except InputError:
            artifact = _input_abstention("sftguard.regression-card.v1")
        return _emit(artifact, args.output)

    if args.command == "benchmark":
        return _emit(run_development_benchmark(args.seeds), args.output)

    if args.command == "demo":
        return _emit(run_demo(), args.output)

    raise AssertionError("argparse accepted an unknown command")
