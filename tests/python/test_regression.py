from __future__ import annotations

import json

import pytest

from sftguard.artifacts import canonical_json_bytes, verify_artifact
from sftguard.models import Status
from sftguard.regression import (
    MAX_BOOTSTRAP_WORK,
    BootstrapConfig,
    build_regression_card,
    seed_cluster_bootstrap,
)


def _records(
    target_delta: float = 0.12,
    retention_delta: float = -0.005,
    seed_count: int = 4,
):
    base = []
    adapter = []
    line = 1
    for seed in range(seed_count):
        for group, metric, baseline, delta in (
            ("target", "task_score", 0.5, target_delta),
            ("retention", "general_score", 0.8, retention_delta),
        ):
            common = {
                "seed": seed,
                "sample_id": f"private-sample-{group}-{seed}",
                "group": group,
                "metric": metric,
            }
            base.append((line, {**common, "value": baseline}))
            adapter.append((line, {**common, "value": baseline + delta}))
            line += 1
    return tuple(base), tuple(adapter)


def _contract():
    return {
        "bootstrap": {"draws": 1000, "confidence": 0.95, "seed": 2339},
        "metrics": [
            {
                "group": "target",
                "metric": "task_score",
                "higher_is_better": True,
                "min_improvement": 0.05,
            },
            {
                "group": "retention",
                "metric": "general_score",
                "higher_is_better": True,
                "max_regression": 0.02,
            },
        ],
    }


def test_regression_card_passes_target_and_retention_contract() -> None:
    base, adapter = _records()
    card = build_regression_card(base, adapter, _contract())
    assert card["status"] == Status.PASS
    assert all(metric["status"] == Status.PASS for metric in card["metrics"])
    assert card["summary"]["pair_count"] == 8
    assert verify_artifact(card)


@pytest.mark.parametrize(
    ("target_delta", "retention_delta", "failed_group"),
    [(0.01, -0.005, "target"), (0.12, -0.05, "retention")],
)
def test_regression_card_fails_violated_gate(target_delta, retention_delta, failed_group) -> None:
    base, adapter = _records(target_delta, retention_delta)
    card = build_regression_card(base, adapter, _contract())
    assert card["status"] == Status.FAIL
    assert (
        next(item for item in card["metrics"] if item["group"] == failed_group)["status"]
        == Status.FAIL
    )


def test_unpaired_records_abstain() -> None:
    base, adapter = _records()
    card = build_regression_card(base, adapter[:-1], _contract())
    assert card["status"] == Status.ABSTAIN
    assert "unpaired_evaluation_records" in card["reason_codes"]


def test_duplicate_pair_key_abstains() -> None:
    base, adapter = _records()
    card = build_regression_card((*base, base[0]), adapter, _contract())
    assert card["status"] == Status.ABSTAIN
    assert "duplicate_pair_key" in card["reason_codes"]


def test_contract_requires_both_target_and_retention() -> None:
    base, adapter = _records()
    contract = _contract()
    contract["metrics"] = contract["metrics"][:1]
    card = build_regression_card(base, adapter, contract)
    assert card["status"] == Status.ABSTAIN
    assert "target_and_retention_contracts_required" in card["reason_codes"]


def test_nonfinite_value_abstains_without_serializing_it() -> None:
    base, adapter = _records()
    broken = list(adapter)
    broken[0] = (broken[0][0], {**broken[0][1], "value": float("nan")})
    card = build_regression_card(base, broken, _contract())
    assert card["status"] == Status.ABSTAIN
    assert b"NaN" not in canonical_json_bytes(card)


def test_nonfinite_contract_abstains_without_serializing_it() -> None:
    base, adapter = _records()
    contract = _contract()
    contract["metrics"][0]["min_improvement"] = float("nan")
    card = build_regression_card(base, adapter, contract)
    assert card["status"] == Status.ABSTAIN
    assert "invalid_metric_threshold" in card["reason_codes"]
    assert b"NaN" not in canonical_json_bytes(card)


def test_seed_cluster_bootstrap_is_deterministic() -> None:
    clusters = {0: (0.1, 0.2), 1: (0.3,), 2: (0.4, 0.5)}
    config = BootstrapConfig(draws=2000, confidence=0.9, seed=2339)
    assert seed_cluster_bootstrap(clusters, config) == seed_cluster_bootstrap(clusters, config)


def test_constant_cluster_bootstrap_has_exact_interval() -> None:
    interval = seed_cluster_bootstrap(
        {0: (0.25,), 1: (0.25,), 2: (0.25,)}, BootstrapConfig(draws=100)
    )
    assert interval == (0.25, 0.25)


def test_regression_card_contains_no_sample_ids() -> None:
    base, adapter = _records()
    rendered = json.dumps(build_regression_card(base, adapter, _contract()), sort_keys=True)
    assert "private-sample" not in rendered


def test_bootstrap_joint_work_limit_abstains_before_resampling() -> None:
    base, adapter = _records(seed_count=51)
    contract = _contract()
    contract["bootstrap"]["draws"] = 100_000
    assert contract["bootstrap"]["draws"] * len(base) > MAX_BOOTSTRAP_WORK
    card = build_regression_card(base, adapter, contract)
    assert card["status"] == Status.ABSTAIN
    assert "bootstrap_work_limit_exceeded" in card["reason_codes"]
