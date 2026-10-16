"""Deterministic SFT dataset and rendered-mask audits."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from . import __version__
from .artifacts import canonical_json_bytes, seal_artifact, sha256_bytes
from .io import (
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_LINE_BYTES,
    DEFAULT_MAX_RECORDS,
    InputError,
    InputSummary,
    read_jsonl_bounded,
    summarize_records,
)
from .models import SEVERITY_ORDER, Finding, Status, combine_status
from .privacy import scan_record
from .tokenizer import FixtureMaskInspector, MaskInspector

ALLOWED_MESSAGE_ROLES = {"system", "user", "assistant", "tool"}


@dataclass(frozen=True)
class AuditConfig:
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_line_bytes: int = DEFAULT_MAX_LINE_BYTES
    max_records: int = DEFAULT_MAX_RECORDS
    require_assistant_mask: bool = True
    scan_privacy: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_file_bytes": self.max_file_bytes,
            "max_line_bytes": self.max_line_bytes,
            "max_records": self.max_records,
            "require_assistant_mask": self.require_assistant_mask,
            "scan_privacy": self.scan_privacy,
        }


@dataclass(frozen=True)
class _RecordIdentity:
    split: str
    line: int
    record_sha256: str
    prompt_sha256: str | None
    answer_sha256: str | None


def _record_hash(record: dict[str, Any], *, split: str, line: int) -> tuple[str, bool]:
    try:
        return sha256_bytes(canonical_json_bytes(record)), True
    except (TypeError, ValueError, RecursionError):
        marker = canonical_json_bytes({"invalid_record": True, "split": split, "line": line})
        return sha256_bytes(marker), False


def _message_identity(
    record: dict[str, Any],
    *,
    split: str,
    line: int,
    record_sha256: str,
) -> tuple[str | None, str | None, list[Finding]]:
    findings: list[Finding] = []
    messages = record.get("messages")
    if not isinstance(messages, list) or not messages:
        findings.append(
            Finding("invalid_messages", "error", split, line, record_sha256=record_sha256)
        )
        return None, None, findings

    valid_messages: list[dict[str, str]] = []
    awaiting_assistant = False
    for message in messages:
        if not isinstance(message, dict):
            findings.append(
                Finding("invalid_messages", "error", split, line, record_sha256=record_sha256)
            )
            continue
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or role not in ALLOWED_MESSAGE_ROLES:
            findings.append(
                Finding(
                    "invalid_role",
                    "error",
                    split,
                    line,
                    field="role",
                    record_sha256=record_sha256,
                )
            )
            continue
        if not isinstance(content, str):
            findings.append(
                Finding(
                    "invalid_messages",
                    "error",
                    split,
                    line,
                    field="content",
                    record_sha256=record_sha256,
                )
            )
            continue
        valid_messages.append({"role": role, "content": content})
        if role == "user":
            awaiting_assistant = True
        elif role == "assistant":
            if not awaiting_assistant:
                findings.append(
                    Finding("role_order", "error", split, line, record_sha256=record_sha256)
                )
            awaiting_assistant = False

    if len(valid_messages) != len(messages):
        return None, None, findings

    assistant_indexes = [
        index for index, message in enumerate(valid_messages) if message["role"] == "assistant"
    ]
    if not assistant_indexes:
        findings.append(
            Finding("missing_assistant", "error", split, line, record_sha256=record_sha256)
        )
        return None, None, findings
    final_index = assistant_indexes[-1]
    prompt = valid_messages[:final_index]
    answer = valid_messages[final_index]["content"]
    prompt_hash = sha256_bytes(canonical_json_bytes(prompt))
    answer_hash = sha256_bytes(canonical_json_bytes(answer))
    return prompt_hash, answer_hash, findings


def _check_status(findings: Iterable[Finding], signals: set[str]) -> Status:
    relevant = [finding for finding in findings if finding.signal in signals]
    if any(SEVERITY_ORDER[finding.severity] >= SEVERITY_ORDER["error"] for finding in relevant):
        return Status.FAIL
    return Status.PASS


def _abstain_report(config: AuditConfig, reason: str) -> dict[str, Any]:
    return seal_artifact(
        {
            "schema_version": "sftguard.audit.v1",
            "tool": {"name": "sftguard", "version": __version__},
            "status": Status.ABSTAIN,
            "config": config.as_dict(),
            "inputs": [],
            "checks": {"input": {"status": Status.ABSTAIN, "reason": reason}},
            "summary": {"finding_count": 0, "signal_counts": {}},
            "findings": [],
        }
    )


def audit_files(
    train_path: str,
    evaluation_path: str,
    *,
    config: AuditConfig | None = None,
    mask_inspector: MaskInspector | None = None,
) -> dict[str, Any]:
    selected = config or AuditConfig()
    try:
        train = read_jsonl_bounded(
            train_path,
            max_file_bytes=selected.max_file_bytes,
            max_line_bytes=selected.max_line_bytes,
            max_records=selected.max_records,
        )
        evaluation = read_jsonl_bounded(
            evaluation_path,
            max_file_bytes=selected.max_file_bytes,
            max_line_bytes=selected.max_line_bytes,
            max_records=selected.max_records,
        )
    except InputError:
        return _abstain_report(selected, "invalid_unreadable_or_oversized_input")
    return audit_records(
        train.records,
        evaluation.records,
        train_summary=train.summary,
        evaluation_summary=evaluation.summary,
        config=selected,
        mask_inspector=mask_inspector,
    )


def audit_records(
    train_records: Iterable[tuple[int, dict[str, Any]]],
    evaluation_records: Iterable[tuple[int, dict[str, Any]]],
    *,
    train_summary: InputSummary | None = None,
    evaluation_summary: InputSummary | None = None,
    config: AuditConfig | None = None,
    mask_inspector: MaskInspector | None = None,
) -> dict[str, Any]:
    selected = config or AuditConfig()
    inspector = mask_inspector or FixtureMaskInspector()
    train = tuple(train_records)
    evaluation = tuple(evaluation_records)
    train_summary = train_summary or summarize_records(train)
    evaluation_summary = evaluation_summary or summarize_records(evaluation)

    if not train or not evaluation:
        return _abstain_report(selected, "train_and_evaluation_records_required")

    findings: list[Finding] = []
    identities: list[_RecordIdentity] = []
    mask_abstentions = 0
    seen_records: dict[tuple[str, str], int] = {}

    for split, records in (("train", train), ("evaluation", evaluation)):
        for line, record in records:
            record_sha, record_serializable = _record_hash(record, split=split, line=line)
            if not record_serializable:
                findings.append(
                    Finding(
                        "invalid_record",
                        "error",
                        split,
                        line,
                        record_sha256=record_sha,
                    )
                )
            prompt_sha, answer_sha, schema_findings = _message_identity(
                record,
                split=split,
                line=line,
                record_sha256=record_sha,
            )
            findings.extend(schema_findings)
            identities.append(_RecordIdentity(split, line, record_sha, prompt_sha, answer_sha))

            duplicate_key = (split, record_sha)
            if duplicate_key in seen_records:
                findings.append(
                    Finding(
                        "exact_duplicate",
                        "warning",
                        split,
                        line,
                        related_line=seen_records[duplicate_key],
                        record_sha256=record_sha,
                    )
                )
            else:
                seen_records[duplicate_key] = line

            if selected.scan_privacy:
                for signal, category, field in scan_record(record):
                    findings.append(
                        Finding(
                            signal,
                            "critical" if signal == "secret_pattern" else "warning",
                            split,
                            line,
                            field=field,
                            category=category,
                            record_sha256=record_sha,
                            redacted=True,
                        )
                    )

            inspection = inspector.inspect(record)
            if not inspection.available:
                if selected.require_assistant_mask:
                    mask_abstentions += 1
                    findings.append(
                        Finding(
                            inspection.reason or "assistant_mask_unavailable",
                            "info",
                            split,
                            line,
                            record_sha256=record_sha,
                            redacted=True,
                        )
                    )
            else:
                for signal in inspection.signals:
                    findings.append(
                        Finding(
                            signal.signal,
                            signal.severity,
                            split,
                            line,
                            record_sha256=record_sha,
                        )
                    )

    prompt_answers: dict[str, dict[str, int]] = {}
    for identity in identities:
        if (
            identity.split != "train"
            or identity.prompt_sha256 is None
            or identity.answer_sha256 is None
        ):
            continue
        prior = prompt_answers.setdefault(identity.prompt_sha256, {})
        if prior and identity.answer_sha256 not in prior:
            findings.append(
                Finding(
                    "prompt_conflict",
                    "error",
                    identity.split,
                    identity.line,
                    related_line=min(prior.values()),
                    record_sha256=identity.record_sha256,
                )
            )
        prior.setdefault(identity.answer_sha256, identity.line)

    prompts_by_split: dict[str, dict[str, int]] = {"train": {}, "evaluation": {}}
    for identity in identities:
        if identity.prompt_sha256 is not None:
            prompts_by_split[identity.split].setdefault(identity.prompt_sha256, identity.line)
    for prompt_sha in sorted(set(prompts_by_split["train"]) & set(prompts_by_split["evaluation"])):
        findings.append(
            Finding(
                "train_eval_leakage",
                "critical",
                "train",
                prompts_by_split["train"][prompt_sha],
                related_line=prompts_by_split["evaluation"][prompt_sha],
                record_sha256=prompt_sha,
            )
        )

    findings.sort(
        key=lambda finding: (
            finding.split,
            finding.line,
            finding.signal,
            finding.related_line or 0,
            finding.category or "",
        )
    )
    signal_counts = Counter(finding.signal for finding in findings)

    schema_signals = {
        "invalid_record",
        "invalid_messages",
        "invalid_role",
        "role_order",
        "missing_assistant",
    }
    exact_signals = {"exact_duplicate", "prompt_conflict", "train_eval_leakage"}
    privacy_signals = {"secret_pattern", "pii_like"}
    mask_signals = {
        "prompt_token_supervised",
        "assistant_fully_truncated",
        "missing_eos",
    }
    checks = {
        "schema": {"status": _check_status(findings, schema_signals)},
        "duplicates_conflicts_and_leakage": {"status": _check_status(findings, exact_signals)},
        "privacy_patterns": {"status": _check_status(findings, privacy_signals)},
        "assistant_mask": {
            "status": (
                Status.ABSTAIN if mask_abstentions else _check_status(findings, mask_signals)
            ),
            "abstained_record_count": mask_abstentions,
        },
    }
    overall = combine_status(*(entry["status"] for entry in checks.values()))

    return seal_artifact(
        {
            "schema_version": "sftguard.audit.v1",
            "tool": {"name": "sftguard", "version": __version__},
            "status": overall,
            "config": selected.as_dict(),
            "inputs": [
                train_summary.as_dict("train"),
                evaluation_summary.as_dict("evaluation"),
            ],
            "checks": checks,
            "summary": {
                "finding_count": len(findings),
                "signal_counts": dict(sorted(signal_counts.items())),
                "error_or_critical_count": sum(
                    SEVERITY_ORDER[finding.severity] >= SEVERITY_ORDER["error"]
                    for finding in findings
                ),
                "redacted_finding_count": sum(finding.redacted for finding in findings),
            },
            "findings": [finding.as_dict() for finding in findings],
        }
    )
