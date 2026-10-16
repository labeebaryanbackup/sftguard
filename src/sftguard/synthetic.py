"""Deterministic synthetic fault generation with phase-separated seeds."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Any

from .artifacts import canonical_json_bytes, sha256_bytes

DEVELOPMENT_SEEDS = tuple(range(10))
CONFIRMATORY_SEEDS = tuple(range(4100, 4130))


@dataclass(frozen=True)
class FaultSpec:
    fault_id: str
    expected_signal: str
    severity: str


FAULT_SPECS = (
    FaultSpec("schema.invalid_role", "invalid_role", "error"),
    FaultSpec("schema.role_order", "role_order", "error"),
    FaultSpec("template.missing_eos", "missing_eos", "error"),
    FaultSpec("mask.prompt_supervised", "prompt_token_supervised", "critical"),
    FaultSpec("truncation.answer_removed", "assistant_fully_truncated", "critical"),
    FaultSpec("data.exact_duplicate", "exact_duplicate", "warning"),
    FaultSpec("data.prompt_conflict", "prompt_conflict", "error"),
    FaultSpec("data.train_eval_leakage", "train_eval_leakage", "critical"),
    FaultSpec("privacy.secret_pattern", "secret_pattern", "critical"),
)


@dataclass(frozen=True)
class SyntheticCase:
    seed: int
    fault: FaultSpec | None
    train: tuple[tuple[int, dict[str, Any]], ...]
    evaluation: tuple[tuple[int, dict[str, Any]], ...]
    case_sha256: str
    private_markers: tuple[str, ...]


def _marker(seed: int, split: str, index: int) -> str:
    hexadecimal = hashlib.sha256(f"sftguard:{seed}:{split}:{index}".encode()).hexdigest()[:16]
    return hexadecimal.translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))


def _record(marker: str, answer: str, offset: int) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": "Return the requested class label."},
            {"role": "user", "content": f"Classify marker_{marker}."},
            {"role": "assistant", "content": answer},
        ],
        "_sftguard": {
            "token_ids": [10 + offset, 20 + offset, 30 + offset, 2],
            "token_roles": ["system", "user", "assistant", "assistant"],
            "loss_mask": [False, False, True, True],
            "eos_token_id": 2,
            "original_assistant_tokens": 2,
            "truncated": False,
        },
    }


def _clean(seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    train_markers = [_marker(seed, "train", index) for index in range(3)]
    evaluation_markers = [_marker(seed, "evaluation", index) for index in range(2)]
    train = [
        _record(marker, "class_a" if index % 2 == 0 else "class_b", index)
        for index, marker in enumerate(train_markers)
    ]
    evaluation = [
        _record(marker, "class_b" if index % 2 == 0 else "class_a", index + 10)
        for index, marker in enumerate(evaluation_markers)
    ]
    return train, evaluation, train_markers + evaluation_markers


def _generate_case(seed: int, fault_id: str | None = None) -> SyntheticCase:
    spec = next((item for item in FAULT_SPECS if item.fault_id == fault_id), None)
    if fault_id is not None and spec is None:
        raise ValueError("unknown synthetic fault identifier")

    train, evaluation, markers = _clean(seed)
    private_markers = list(markers)
    if spec is not None:
        if spec.fault_id == "schema.invalid_role":
            train[0]["messages"][1]["role"] = "invalid_development_role"
        elif spec.fault_id == "schema.role_order":
            train[0]["messages"].insert(0, {"role": "assistant", "content": "class_a"})
        elif spec.fault_id == "template.missing_eos":
            train[0]["_sftguard"]["token_ids"][-1] = 99
        elif spec.fault_id == "mask.prompt_supervised":
            train[0]["_sftguard"]["loss_mask"][1] = True
        elif spec.fault_id == "truncation.answer_removed":
            train[0]["_sftguard"] = {
                "token_ids": [10, 20],
                "token_roles": ["system", "user"],
                "loss_mask": [False, False],
                "eos_token_id": 2,
                "original_assistant_tokens": 2,
                "truncated": True,
            }
        elif spec.fault_id == "data.exact_duplicate":
            train.append(copy.deepcopy(train[0]))
        elif spec.fault_id == "data.prompt_conflict":
            conflicting = copy.deepcopy(train[0])
            conflicting["messages"][-1]["content"] = "class_conflict"
            train.append(conflicting)
        elif spec.fault_id == "data.train_eval_leakage":
            evaluation.append(copy.deepcopy(train[0]))
        elif spec.fault_id == "privacy.secret_pattern":
            secret = f"sk-test-{hashlib.sha256(f'secret:{seed}'.encode()).hexdigest()[:20]}"
            train[0]["messages"][1]["content"] += f" Credential {secret}."
            private_markers.append(secret)

    numbered_train = tuple((index + 1, record) for index, record in enumerate(train))
    numbered_evaluation = tuple((index + 1, record) for index, record in enumerate(evaluation))
    case_hash = sha256_bytes(
        canonical_json_bytes(
            {
                "seed": seed,
                "fault_id": fault_id,
                "train": train,
                "evaluation": evaluation,
            }
        )
    )
    return SyntheticCase(
        seed=seed,
        fault=spec,
        train=numbered_train,
        evaluation=numbered_evaluation,
        case_sha256=case_hash,
        private_markers=tuple(private_markers),
    )


def generate_case(seed: int, fault_id: str | None = None) -> SyntheticCase:
    """Generate one development case without exposing confirmatory seeds."""

    if seed not in DEVELOPMENT_SEEDS:
        raise ValueError("synthetic generation is restricted to development seeds 0 through 9")
    return _generate_case(seed, fault_id)


def generate_confirmatory_case(seed: int, fault_id: str | None = None) -> SyntheticCase:
    """Generate a preregistered confirmatory case for the evidence runner only."""

    if seed not in CONFIRMATORY_SEEDS:
        raise ValueError("seed is outside the frozen confirmatory range")
    return _generate_case(seed, fault_id)
