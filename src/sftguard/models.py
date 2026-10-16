"""Shared status and finding types."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ABSTAIN = "ABSTAIN"


SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2, "critical": 3}


@dataclass(frozen=True)
class Finding:
    signal: str
    severity: str
    split: str
    line: int
    field: str | None = None
    category: str | None = None
    related_line: int | None = None
    record_sha256: str | None = None
    redacted: bool = False
    details: dict[str, Any] = dataclass_field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "signal": self.signal,
            "severity": self.severity,
            "location": {"split": self.split, "line": self.line},
        }
        if self.field is not None:
            result["location"]["field"] = self.field
        if self.category is not None:
            result["category"] = self.category
        if self.related_line is not None:
            result["related_line"] = self.related_line
        if self.record_sha256 is not None:
            result["record_sha256"] = self.record_sha256
        if self.redacted:
            result["redacted"] = True
        if self.details:
            result["details"] = dict(sorted(self.details.items()))
        return result


def combine_status(*statuses: Status) -> Status:
    if Status.FAIL in statuses:
        return Status.FAIL
    if Status.ABSTAIN in statuses:
        return Status.ABSTAIN
    return Status.PASS
