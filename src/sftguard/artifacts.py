"""Deterministic, content-addressed JSON artifact helpers."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Return the repository's canonical UTF-8 JSON representation."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def seal_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Attach a hash of the payload excluding the integrity field itself."""

    sealed = copy.deepcopy(dict(payload))
    sealed.pop("integrity", None)
    sealed["integrity"] = {
        "algorithm": "sha256",
        "canonical_payload_sha256": sha256_bytes(canonical_json_bytes(sealed)),
    }
    return sealed


def verify_artifact(artifact: Mapping[str, Any]) -> bool:
    integrity = artifact.get("integrity")
    if not isinstance(integrity, Mapping):
        return False
    expected = integrity.get("canonical_payload_sha256")
    if not isinstance(expected, str):
        return False
    payload = copy.deepcopy(dict(artifact))
    payload.pop("integrity", None)
    return expected == sha256_bytes(canonical_json_bytes(payload))


def write_artifact(path: str | Path | None, artifact: Mapping[str, Any]) -> None:
    """Write an artifact atomically, or print it when path is ``None``."""

    rendered = (
        json.dumps(
            artifact,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if path is None:
        print(rendered, end="")
        return

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, destination)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
