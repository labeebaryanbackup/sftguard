"""Small deterministic, redacted end-to-end demonstration."""

from __future__ import annotations

from typing import Any

from . import __version__
from .artifacts import seal_artifact
from .audit import audit_records
from .models import Status
from .regression import build_regression_card
from .synthetic import generate_case


def _evaluation_records() -> tuple[
    tuple[tuple[int, dict[str, Any]], ...], tuple[tuple[int, dict[str, Any]], ...]
]:
    base: list[tuple[int, dict[str, Any]]] = []
    adapter: list[tuple[int, dict[str, Any]]] = []
    line = 1
    for seed in range(4):
        for group, metric, base_value, adapter_value in (
            ("target", "task_score", 0.50 + seed * 0.01, 0.65 + seed * 0.01),
            ("retention", "general_score", 0.80 - seed * 0.01, 0.795 - seed * 0.01),
        ):
            common = {
                "seed": seed,
                "sample_id": f"development-{group}-{seed}",
                "group": group,
                "metric": metric,
            }
            base.append((line, {**common, "value": base_value}))
            adapter.append((line, {**common, "value": adapter_value}))
            line += 1
    return tuple(base), tuple(adapter)


def run_demo() -> dict[str, Any]:
    case = generate_case(0)
    audit = audit_records(case.train, case.evaluation)
    base, adapter = _evaluation_records()
    card = build_regression_card(
        base,
        adapter,
        {
            "bootstrap": {"draws": 10_000, "confidence": 0.95, "seed": 2339},
            "metrics": [
                {
                    "group": "target",
                    "metric": "task_score",
                    "higher_is_better": True,
                    "min_improvement": 0.10,
                },
                {
                    "group": "retention",
                    "metric": "general_score",
                    "higher_is_better": True,
                    "max_regression": 0.02,
                },
            ],
        },
    )
    status = (
        Status.PASS
        if audit["status"] == Status.PASS and card["status"] == Status.PASS
        else Status.FAIL
    )
    return seal_artifact(
        {
            "schema_version": "sftguard.demo.v1",
            "tool": {"name": "sftguard", "version": __version__},
            "status": status,
            "note": "Deterministic synthetic development demonstration; not external evidence.",
            "audit": audit,
            "regression_card": card,
        }
    )
