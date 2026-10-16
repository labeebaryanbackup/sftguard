from __future__ import annotations

import json

import pytest

from sftguard.artifacts import (
    canonical_json_bytes,
    seal_artifact,
    verify_artifact,
    write_artifact,
)
from sftguard.io import InputError, read_json_bounded, read_jsonl_bounded


def test_canonical_json_is_sorted_compact_and_utf8() -> None:
    assert canonical_json_bytes({"z": 1, "a": "Sarawak"}) == b'{"a":"Sarawak","z":1}'


def test_sealed_artifact_verifies_and_tampering_fails() -> None:
    artifact = seal_artifact({"status": "PASS", "count": 2})
    assert verify_artifact(artifact)
    artifact["count"] = 3
    assert not verify_artifact(artifact)


def test_write_artifact_round_trips(tmp_path) -> None:
    artifact = seal_artifact({"status": "PASS"})
    destination = tmp_path / "nested" / "report.json"
    write_artifact(destination, artifact)
    assert json.loads(destination.read_text(encoding="utf-8")) == artifact


def test_jsonl_reader_streams_objects_and_hashes_bytes(tmp_path) -> None:
    source = tmp_path / "records.jsonl"
    source.write_bytes(b'{"a":1}\n\n{"b":2}\n')
    parsed = read_jsonl_bounded(source)
    assert parsed.records == ((1, {"a": 1}), (3, {"b": 2}))
    assert parsed.summary.byte_count == source.stat().st_size
    assert parsed.summary.record_count == 2
    assert len(parsed.summary.sha256) == 64


@pytest.mark.parametrize(
    ("contents", "kwargs"),
    [
        (b'{"a":1}\n', {"max_file_bytes": 2}),
        (b'{"long":"value"}\n', {"max_line_bytes": 4}),
        (b'{"a":1}\n{"b":2}\n', {"max_records": 1}),
        (b'{"a":1,"a":2}\n', {}),
        (b"[1,2,3]\n", {}),
        (b'{"score":NaN}\n', {}),
        (b"\xff\xfe\n", {}),
    ],
)
def test_jsonl_reader_rejects_malformed_or_bounded_input(tmp_path, contents, kwargs) -> None:
    source = tmp_path / "bad.jsonl"
    source.write_bytes(contents)
    with pytest.raises(InputError):
        read_jsonl_bounded(source, **kwargs)


def test_bounded_json_rejects_duplicate_keys_and_large_file(tmp_path) -> None:
    source = tmp_path / "contract.json"
    source.write_text('{"x":1,"x":2}', encoding="utf-8")
    with pytest.raises(InputError):
        read_json_bounded(source)
    source.write_text('{"x":1}', encoding="utf-8")
    with pytest.raises(InputError):
        read_json_bounded(source, max_file_bytes=2)
