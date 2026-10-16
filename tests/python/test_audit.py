from __future__ import annotations

import copy
import json

import pytest

from sftguard.audit import audit_files, audit_records
from sftguard.models import Status
from sftguard.synthetic import FAULT_SPECS, generate_case
from sftguard.tokenizer import FixtureMaskInspector


def test_clean_control_passes_without_findings() -> None:
    case = generate_case(0)
    report = audit_records(case.train, case.evaluation)
    assert report["status"] == Status.PASS
    assert report["findings"] == []
    assert report["summary"]["signal_counts"] == {}


@pytest.mark.parametrize("fault", FAULT_SPECS, ids=lambda fault: fault.fault_id)
def test_each_registered_fault_emits_its_primary_signal(fault) -> None:
    case = generate_case(1, fault.fault_id)
    report = audit_records(case.train, case.evaluation)
    assert fault.expected_signal in report["summary"]["signal_counts"]


def test_warning_duplicate_is_detected_without_forcing_failure() -> None:
    case = generate_case(2, "data.exact_duplicate")
    report = audit_records(case.train, case.evaluation)
    assert report["status"] == Status.PASS
    assert report["summary"]["signal_counts"] == {"exact_duplicate": 1}


def test_missing_mask_abstains_and_is_not_silently_passed() -> None:
    case = generate_case(2)
    train = copy.deepcopy(case.train)
    train[0][1].pop("_sftguard")
    report = audit_records(train, case.evaluation)
    assert report["status"] == Status.ABSTAIN
    assert report["checks"]["assistant_mask"]["status"] == Status.ABSTAIN
    assert report["summary"]["signal_counts"]["assistant_mask_unavailable"] == 1


def test_known_failure_dominates_mask_abstention() -> None:
    case = generate_case(3, "schema.invalid_role")
    train = copy.deepcopy(case.train)
    train[0][1].pop("_sftguard")
    report = audit_records(train, case.evaluation)
    assert report["status"] == Status.FAIL


def test_invalid_mask_fixture_abstains() -> None:
    case = generate_case(4)
    train = copy.deepcopy(case.train)
    train[0][1]["_sftguard"]["loss_mask"] = [True]
    report = audit_records(train, case.evaluation)
    assert report["status"] == Status.ABSTAIN
    assert "mask_fixture_invalid" in report["summary"]["signal_counts"]


def test_direct_nonfinite_record_fails_closed() -> None:
    case = generate_case(4)
    train = copy.deepcopy(case.train)
    train[0][1]["score"] = float("nan")
    report = audit_records(train, case.evaluation)
    assert report["status"] == Status.FAIL
    assert report["summary"]["signal_counts"]["invalid_record"] == 1


def test_secret_and_pii_findings_are_redacted_and_values_absent() -> None:
    case = generate_case(5)
    secret = "sk-test-abcdefghijklmnopqrst"
    email = "person@example.invalid"
    train = copy.deepcopy(case.train)
    train[0][1]["messages"][1]["content"] += f" {secret} {email}"
    report = audit_records(train, case.evaluation)
    rendered = json.dumps(report, sort_keys=True)
    assert secret not in rendered
    assert email not in rendered
    findings = [
        finding
        for finding in report["findings"]
        if finding["signal"] in {"secret_pattern", "pii_like"}
    ]
    assert {finding["signal"] for finding in findings} == {"secret_pattern", "pii_like"}
    assert all(finding["redacted"] is True for finding in findings)
    assert all("category" in finding and "location" in finding for finding in findings)


def test_artifact_never_contains_prompt_or_response_text() -> None:
    case = generate_case(6)
    report = audit_records(case.train, case.evaluation)
    rendered = json.dumps(report, sort_keys=True)
    for _, record in (*case.train, *case.evaluation):
        for message in record["messages"]:
            assert message["content"] not in rendered


def test_mask_inspector_flags_each_semantic_fault() -> None:
    inspector = FixtureMaskInspector()
    for fault_id, signal in (
        ("template.missing_eos", "missing_eos"),
        ("mask.prompt_supervised", "prompt_token_supervised"),
        ("truncation.answer_removed", "assistant_fully_truncated"),
    ):
        case = generate_case(7, fault_id)
        inspection = inspector.inspect(case.train[0][1])
        assert inspection.available
        assert signal in {item.signal for item in inspection.signals}


def test_audit_files_returns_abstention_for_bad_input(tmp_path) -> None:
    train = tmp_path / "train.jsonl"
    evaluation = tmp_path / "eval.jsonl"
    train.write_text("not-json\n", encoding="utf-8")
    evaluation.write_text("{}\n", encoding="utf-8")
    report = audit_files(str(train), str(evaluation))
    assert report["status"] == Status.ABSTAIN
    assert report["inputs"] == []
