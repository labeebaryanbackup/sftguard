"""Frozen v0.1 confirmatory fault-matrix evidence construction.

The public orchestration script invokes this module only from a clean, pushed
implementation commit. Keeping construction separate from orchestration makes
the payload testable on development seeds without touching the confirmatory
range before the implementation is frozen.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from . import __version__
from .artifacts import canonical_json_bytes, seal_artifact
from .audit import AuditConfig, audit_records
from .models import Status
from .synthetic import (
    CONFIRMATORY_SEEDS,
    FAULT_SPECS,
    SyntheticCase,
    generate_confirmatory_case,
)

_FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def pretty_json_bytes(value: Any) -> bytes:
    """Render stable human-readable JSON for the checked-in evidence file."""

    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _validate_commit(value: str, label: str) -> None:
    if _FULL_COMMIT.fullmatch(value) is None:
        raise ValueError(f"{label} must be a full lowercase Git commit")


def _build_artifact(
    seeds: Iterable[int],
    case_factory: Callable[[int, str | None], SyntheticCase],
    *,
    protocol_commit: str,
    implementation_commit: str,
    fresh_process_byte_reproducible: bool,
) -> dict[str, Any]:
    """Build a sealed matrix; tests exercise this with development seeds."""

    _validate_commit(protocol_commit, "protocol_commit")
    _validate_commit(implementation_commit, "implementation_commit")
    selected = tuple(seeds)
    if not selected or tuple(sorted(set(selected))) != selected:
        raise ValueError("seeds must be a non-empty sorted unique sequence")

    cases: list[dict[str, Any]] = []
    recall_by_fault: dict[str, list[bool]] = defaultdict(list)
    private_text: set[str] = set()
    clean_false_positives = 0

    for seed in selected:
        for fault_id in (None, *(spec.fault_id for spec in FAULT_SPECS)):
            case = case_factory(seed, fault_id)
            private_text.update(case.private_markers)
            for _, record in (*case.train, *case.evaluation):
                messages = record.get("messages")
                if isinstance(messages, list):
                    private_text.update(
                        message["content"]
                        for message in messages
                        if isinstance(message, dict) and isinstance(message.get("content"), str)
                    )

            report = audit_records(case.train, case.evaluation)
            observed_signals = tuple(sorted(report["summary"]["signal_counts"]))
            expected = case.fault.expected_signal if case.fault else None
            expectation_met = expected in observed_signals if expected else not observed_signals
            observed_primary = expected if expected in observed_signals else None

            if case.fault is None:
                if observed_signals:
                    clean_false_positives += 1
            else:
                recall_by_fault[case.fault.fault_id].append(expectation_met)

            cases.append(
                {
                    "audit_status": report["status"],
                    "case_sha256": case.case_sha256,
                    "expected_primary_signal": expected,
                    "fault_id": case.fault.fault_id if case.fault else None,
                    "kind": "fault" if case.fault else "clean_control",
                    "observed_primary_signal": observed_primary,
                    "observed_signal_ids": list(observed_signals),
                    "primary_expectation_met": expectation_met,
                    "seed": seed,
                }
            )

    per_fault: list[dict[str, Any]] = []
    recalls: list[float] = []
    for spec in FAULT_SPECS:
        observations = recall_by_fault[spec.fault_id]
        detected_count = sum(observations)
        recall = detected_count / len(observations)
        recalls.append(recall)
        per_fault.append(
            {
                "case_count": len(observations),
                "detected_count": detected_count,
                "expected_signal": spec.expected_signal,
                "fault_id": spec.fault_id,
                "recall": round(recall, 12),
                "severity": spec.severity,
            }
        )

    clean_count = len(selected)
    clean_false_positive_rate = clean_false_positives / clean_count
    macro_recall = statistics.fmean(recalls)
    critical_faults = [item for item in per_fault if item["severity"] == "critical"]
    expected_observed_recorded = all(
        "expected_primary_signal" in case and "observed_primary_signal" in case for case in cases
    )

    payload_without_redaction_gate: dict[str, Any] = {
        "schema_version": "sftguard.confirmatory-fault-matrix.v1",
        "tool": {"name": "sftguard", "version": __version__},
        "provenance": {
            "implementation_git_commit": implementation_commit,
            "protocol_git_commit": protocol_commit,
            "python_implementation": platform.python_implementation(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
        "protocol": {
            "audit_config": AuditConfig().as_dict(),
            "faults": [
                {
                    "expected_signal": spec.expected_signal,
                    "fault_id": spec.fault_id,
                    "severity": spec.severity,
                }
                for spec in FAULT_SPECS
            ],
            "seed_range": {
                "count": len(selected),
                "first": selected[0],
                "last": selected[-1],
            },
        },
        "summary": {
            "case_count": len(cases),
            "clean_control_count": clean_count,
            "clean_false_positive_count": clean_false_positives,
            "clean_false_positive_rate": round(clean_false_positive_rate, 12),
            "fault_case_count": len(cases) - clean_count,
            "macro_recall": round(macro_recall, 12),
        },
        "per_fault": per_fault,
        "cases": cases,
        "gates": {
            "clean_false_positive_rate_at_most_10_percent": (clean_false_positive_rate <= 0.10),
            "critical_fault_recall_100_percent": all(
                item["recall"] == 1.0 for item in critical_faults
            ),
            "expected_and_observed_primary_recorded": expected_observed_recorded,
            "fresh_process_byte_reproducible": fresh_process_byte_reproducible,
            "macro_recall_at_least_90_percent": macro_recall >= 0.90,
        },
    }
    rendered = canonical_json_bytes(payload_without_redaction_gate).decode("utf-8")
    payload_without_redaction_gate["gates"]["raw_synthetic_text_absent"] = all(
        value not in rendered for value in private_text
    )
    carry_forward = all(payload_without_redaction_gate["gates"].values())
    payload_without_redaction_gate["carry_forward"] = carry_forward
    payload_without_redaction_gate["status"] = Status.PASS if carry_forward else Status.FAIL
    return seal_artifact(payload_without_redaction_gate)


def build_confirmatory_artifact(
    *,
    protocol_commit: str,
    implementation_commit: str,
    fresh_process_byte_reproducible: bool = True,
) -> dict[str, Any]:
    """Execute the exact preregistered seed range and fault matrix."""

    return _build_artifact(
        CONFIRMATORY_SEEDS,
        generate_confirmatory_case,
        protocol_commit=protocol_commit,
        implementation_commit=implementation_commit,
        fresh_process_byte_reproducible=fresh_process_byte_reproducible,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build frozen SFTGuard evidence bytes.")
    parser.add_argument("--protocol-commit", required=True)
    parser.add_argument("--implementation-commit", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    artifact = build_confirmatory_artifact(
        protocol_commit=args.protocol_commit,
        implementation_commit=args.implementation_commit,
    )
    sys.stdout.buffer.write(pretty_json_bytes(artifact))
    return 0 if artifact["status"] == Status.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
