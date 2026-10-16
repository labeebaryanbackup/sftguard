"""Bounded JSON and JSONL readers used by every untrusted input path."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MAX_FILE_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_LINE_BYTES = 1024 * 1024
DEFAULT_MAX_RECORDS = 100_000


class InputError(ValueError):
    """Raised when an input cannot be safely or unambiguously parsed."""


@dataclass(frozen=True)
class InputSummary:
    sha256: str
    byte_count: int
    record_count: int

    def as_dict(self, split: str) -> dict[str, Any]:
        return {
            "split": split,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "record_count": self.record_count,
        }


@dataclass(frozen=True)
class ParsedJSONL:
    records: tuple[tuple[int, dict[str, Any]], ...]
    summary: InputSummary


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError("JSON object contains a duplicate key")
        result[key] = value
    return result


def _decode_json(raw: bytes, *, context: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"{context} is not valid UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                InputError(f"{context} contains a non-finite number")
            ),
        )
    except InputError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise InputError(f"{context} is not valid JSON") from exc


def read_jsonl_bounded(
    path: str | Path,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_line_bytes: int = DEFAULT_MAX_LINE_BYTES,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> ParsedJSONL:
    source = Path(path)
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise InputError("input file cannot be read") from exc
    if size > max_file_bytes:
        raise InputError("input file exceeds the configured byte limit")

    digest = hashlib.sha256()
    records: list[tuple[int, dict[str, Any]]] = []
    bytes_seen = 0
    try:
        with source.open("rb") as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                bytes_seen += len(raw_line)
                digest.update(raw_line)
                if bytes_seen > max_file_bytes:
                    raise InputError("input file grew beyond the configured byte limit")
                if len(raw_line) > max_line_bytes:
                    raise InputError(f"JSONL line {line_number} exceeds the byte limit")
                stripped = raw_line.strip()
                if not stripped:
                    continue
                if len(records) >= max_records:
                    raise InputError("input file exceeds the configured record limit")
                decoded = _decode_json(stripped, context=f"JSONL line {line_number}")
                if not isinstance(decoded, dict):
                    raise InputError(f"JSONL line {line_number} must be an object")
                records.append((line_number, decoded))
    except InputError:
        raise
    except OSError as exc:
        raise InputError("input file cannot be read") from exc

    return ParsedJSONL(
        records=tuple(records),
        summary=InputSummary(
            sha256=digest.hexdigest(),
            byte_count=bytes_seen,
            record_count=len(records),
        ),
    )


def read_json_bounded(
    path: str | Path, *, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
) -> tuple[Any, str, int]:
    source = Path(path)
    try:
        size = source.stat().st_size
        if size > max_file_bytes:
            raise InputError("JSON file exceeds the configured byte limit")
        raw = source.read_bytes()
    except InputError:
        raise
    except OSError as exc:
        raise InputError("JSON file cannot be read") from exc
    if len(raw) > max_file_bytes:
        raise InputError("JSON file grew beyond the configured byte limit")
    return _decode_json(raw, context="JSON file"), hashlib.sha256(raw).hexdigest(), len(raw)


def summarize_records(records: Iterable[tuple[int, dict[str, Any]]]) -> InputSummary:
    """Create a deterministic input summary for generated in-memory records."""

    from .artifacts import canonical_json_bytes

    materialized = [record for _, record in records]
    try:
        raw = canonical_json_bytes(materialized)
    except (TypeError, ValueError, RecursionError):
        raw = canonical_json_bytes({"invalid_input": True, "record_count": len(materialized)})
    return InputSummary(
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_count=len(raw),
        record_count=len(materialized),
    )
