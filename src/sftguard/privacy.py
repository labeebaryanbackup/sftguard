"""Conservative secret and PII-like pattern location without value retention."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

_SECRET_PATTERNS = (
    ("openai_style_key", re.compile(r"\bsk-(?:test-)?[A-Za-z0-9_-]{12,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "assigned_credential",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{12,}"
        ),
    ),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}")),
)

_PII_PATTERNS = (
    (
        "email_address",
        re.compile(r"(?i)(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"),
    ),
    (
        "phone_number_like",
        re.compile(r"(?<!\d)(?:\+?\d[\d .()-]{7,}\d)(?!\d)"),
    ),
)


def _field_label(path: tuple[str | int, ...]) -> str:
    for component in reversed(path):
        if component in {"content", "arguments", "name", "role"}:
            return str(component)
    return "other"


def iter_strings(value: Any, path: tuple[str | int, ...] = ()) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield _field_label(path), value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_strings(item, path + (index,))
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from iter_strings(value[key], path + (key,))


def scan_record(value: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:
    """Return unique ``(signal, category, safe-field)`` tuples, never matches."""

    findings: set[tuple[str, str, str]] = set()
    for field, text in iter_strings(value):
        for category, pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                findings.add(("secret_pattern", category, field))
        for category, pattern in _PII_PATTERNS:
            if pattern.search(text):
                findings.add(("pii_like", category, field))
    return tuple(sorted(findings))
