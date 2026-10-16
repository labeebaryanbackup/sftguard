"""Development-only execution of the preregistered synthetic fault matrix."""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from . import __version__
from .artifacts import canonical_json_bytes, seal_artifact
from .audit import audit_records
from .models import Status
from .synthetic import DEVELOPMENT_SEEDS, FAULT_SPECS, generate_case


def validate_development_seeds(seeds: Iterable[int]) -> tuple[int, ...]:
    selected = tuple(sorted(set(seeds)))
    if not selected:
        raise ValueError("at least one development seed is required")
    if any(seed not in DEVELOPMENT_SEEDS for seed in selected):
        raise ValueError("benchmark execution is restricted to development seeds 0 through 9")
    return selected


def _run_once(seeds: tuple[int, ...]) -> tuple[dict[str, Any], tuple[str, ...]]:
    cases: list[dict[str, Any]] = []
    raw_markers: list[str] = []
    recall_by_fault: dict[str, list[bool]] = defaultdict(list)
    clean_false_positives = 0
    clean_count = 0

    for seed in seeds:
        for fault_id in (None, *(spec.fault_id for spec in FAULT_SPECS)):
            case = generate_case(seed, fault_id)
            raw_markers.extend(case.private_markers)
            report = audit_records(case.train, case.evaluation)
            observed_signals = sorted(report["summary"]["signal_counts"])
            expected = case.fault.expected_signal if case.fault else None
            observed_primary = expected in observed_signals if expected else not observed_signals
            if case.fault is None:
                clean_count += 1
                if observed_signals:
                    clean_false_positives += 1
            else:
                recall_by_fault[case.fault.fault_id].append(observed_primary)
            cases.append(
                {
                    "seed": seed,
                    "kind": "fault" if case.fault else "clean_control",
                    "fault_id": case.fault.fault_id if case.fault else None,
                    "expected_primary_signal": expected,
                    "observed_primary_signal": observed_primary,
                    "observed_signals": observed_signals,
                    "audit_status": report["status"],
                    "case_sha256": case.case_sha256,
                }
            )

    per_fault: list[dict[str, Any]] = []
    fault_recalls: list[float] = []
    for spec in FAULT_SPECS:
        observations = recall_by_fault[spec.fault_id]
        detected = sum(observations)
        recall = detected / len(observations)
        fault_recalls.append(recall)
        per_fault.append(
            {
                "fault_id": spec.fault_id,
                "expected_signal": spec.expected_signal,
                "severity": spec.severity,
                "case_count": len(observations),
                "detected_count": detected,
                "recall": round(recall, 12),
            }
        )

    critical = [item for item in per_fault if item["severity"] == "critical"]
    macro_recall = statistics.fmean(fault_recalls)
    clean_false_positive_rate = clean_false_positives / clean_count
    base_gates = {
        "critical_fault_recall_100_percent": all(item["recall"] == 1.0 for item in critical),
        "macro_recall_at_least_90_percent": macro_recall >= 0.9,
        "clean_false_positive_rate_at_most_10_percent": clean_false_positive_rate <= 0.1,
        "expected_and_observed_primary_recorded": all(
            case["expected_primary_signal"] is None
            or isinstance(case["observed_primary_signal"], bool)
            for case in cases
        ),
    }
    payload = {
        "schema_version": "sftguard.development-benchmark.v1",
        "tool": {"name": "sftguard", "version": __version__},
        "development_only": True,
        "seed_range": {"first": seeds[0], "last": seeds[-1], "count": len(seeds)},
        "fault_count": len(FAULT_SPECS),
        "summary": {
            "case_count": len(cases),
            "clean_control_count": clean_count,
            "clean_false_positive_count": clean_false_positives,
            "clean_false_positive_rate": round(clean_false_positive_rate, 12),
            "macro_recall": round(macro_recall, 12),
        },
        "per_fault": per_fault,
        "cases": cases,
        "gates": base_gates,
    }
    return payload, tuple(raw_markers)


def run_development_benchmark(
    seeds: Iterable[int] = DEVELOPMENT_SEEDS,
) -> dict[str, Any]:
    selected = validate_development_seeds(seeds)
    first, markers = _run_once(selected)
    second, _ = _run_once(selected)
    reproducible = canonical_json_bytes(first) == canonical_json_bytes(second)
    rendered = canonical_json_bytes(first).decode("utf-8")
    redacted = all(marker not in rendered for marker in markers)
    first["gates"]["in_process_byte_reproducible"] = reproducible
    first["gates"]["raw_synthetic_text_absent"] = redacted
    first["all_development_gates_passed"] = all(first["gates"].values())
    first["status"] = Status.PASS if first["all_development_gates_passed"] else Status.FAIL
    return seal_artifact(first)
