from __future__ import annotations

import json

import pytest

from sftguard.artifacts import canonical_json_bytes, verify_artifact
from sftguard.benchmark import run_development_benchmark, validate_development_seeds
from sftguard.models import Status
from sftguard.synthetic import DEVELOPMENT_SEEDS, FAULT_SPECS, generate_case


def test_generator_accepts_every_development_seed() -> None:
    for seed in DEVELOPMENT_SEEDS:
        assert generate_case(seed).seed == seed


@pytest.mark.parametrize("seed", [-1, 10, 99])
def test_generator_rejects_non_development_seeds(seed) -> None:
    with pytest.raises(ValueError, match="development seeds"):
        generate_case(seed)


def test_seed_validator_deduplicates_and_sorts() -> None:
    assert validate_development_seeds([3, 1, 3, 2]) == (1, 2, 3)


def test_benchmark_passes_all_registered_faults_on_development_matrix() -> None:
    result = run_development_benchmark()
    assert result["status"] == Status.PASS
    assert result["development_only"] is True
    assert result["summary"]["case_count"] == len(DEVELOPMENT_SEEDS) * (len(FAULT_SPECS) + 1)
    assert result["summary"]["macro_recall"] == 1.0
    assert result["summary"]["clean_false_positive_rate"] == 0.0
    assert all(result["gates"].values())
    assert verify_artifact(result)


def test_benchmark_is_byte_deterministic() -> None:
    first = run_development_benchmark([0, 1, 2])
    second = run_development_benchmark([0, 1, 2])
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_benchmark_artifact_excludes_synthetic_record_text_and_secret() -> None:
    case = generate_case(0, "privacy.secret_pattern")
    result = run_development_benchmark([0])
    rendered = json.dumps(result, sort_keys=True)
    for marker in case.private_markers:
        assert marker not in rendered
    for _, record in (*case.train, *case.evaluation):
        for message in record["messages"]:
            assert message["content"] not in rendered
