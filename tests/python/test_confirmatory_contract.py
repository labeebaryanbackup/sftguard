from __future__ import annotations

import json

import pytest

from sftguard.artifacts import verify_artifact
from sftguard.confirmatory import _build_artifact, pretty_json_bytes
from sftguard.synthetic import (
    CONFIRMATORY_SEEDS,
    FAULT_SPECS,
    generate_case,
    generate_confirmatory_case,
)

FAKE_COMMIT = "a" * 40


def test_frozen_confirmatory_range_is_exact_without_generating_it() -> None:
    assert CONFIRMATORY_SEEDS == tuple(range(4100, 4130))
    assert len(CONFIRMATORY_SEEDS) == 30


def test_phase_separation_rejects_the_other_phase_before_generation() -> None:
    with pytest.raises(ValueError, match="development seeds"):
        generate_case(CONFIRMATORY_SEEDS[0])
    with pytest.raises(ValueError, match="confirmatory range"):
        generate_confirmatory_case(0)


def test_confirmatory_payload_logic_is_covered_only_with_development_seed() -> None:
    artifact = _build_artifact(
        (0,),
        generate_case,
        protocol_commit=FAKE_COMMIT,
        implementation_commit=FAKE_COMMIT,
        fresh_process_byte_reproducible=True,
    )
    assert artifact["status"] == "PASS"
    assert artifact["carry_forward"] is True
    assert artifact["summary"]["case_count"] == len(FAULT_SPECS) + 1
    assert artifact["gates"]["raw_synthetic_text_absent"] is True
    assert all(artifact["gates"].values())
    assert verify_artifact(artifact)
    assert json.loads(pretty_json_bytes(artifact)) == artifact


@pytest.mark.parametrize("commit", ["short", "G" * 40, "a" * 39])
def test_evidence_payload_rejects_noncanonical_commits(commit: str) -> None:
    with pytest.raises(ValueError, match="full lowercase Git commit"):
        _build_artifact(
            (0,),
            generate_case,
            protocol_commit=commit,
            implementation_commit=FAKE_COMMIT,
            fresh_process_byte_reproducible=True,
        )
