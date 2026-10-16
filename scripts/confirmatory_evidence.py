"""Generate once or independently verify the frozen SFTGuard v0.1 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

PROTOCOL_COMMIT = "d4c74cefca6729124142635dc8893b5e3ddec2d3"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT = Path("evidence/v0.1.0-confirmatory.json")
DEFAULT_MANIFEST = Path("evidence/v0.1.0-confirmatory.manifest.json")
MAX_EVIDENCE_BYTES = 16 * 1024 * 1024


class EvidenceError(RuntimeError):
    """Raised when an evidence safety or verification condition fails."""


def _git(*arguments: str, cwd: Path = REPOSITORY_ROOT) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise EvidenceError(detail)
    return completed.stdout.strip()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _seal(payload: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(payload)
    sealed["integrity"] = {
        "algorithm": "sha256",
        "canonical_payload_sha256": _sha256(_canonical_json_bytes(sealed)),
    }
    return sealed


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _verify_integrity(value: dict[str, Any]) -> bool:
    integrity = value.get("integrity")
    if not isinstance(integrity, dict):
        return False
    expected = integrity.get("canonical_payload_sha256")
    payload = dict(value)
    payload.pop("integrity", None)
    return isinstance(expected, str) and expected == _sha256(_canonical_json_bytes(payload))


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError("JSON object contains a duplicate key")
        result[key] = value
    return result


def _parse_object(raw: bytes, label: str) -> dict[str, Any]:
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise EvidenceError(f"{label} exceeds the evidence byte limit")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} must contain a JSON object")
    return value


def _worker_bytes(source_root: Path, implementation_commit: str) -> bytes:
    environment = os.environ.copy()
    existing_path = environment.get("PYTHONPATH")
    source_path = str(source_root / "src")
    environment["PYTHONPATH"] = (
        source_path if not existing_path else os.pathsep.join((source_path, existing_path))
    )
    environment["PYTHONHASHSEED"] = "0"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "sftguard.confirmatory",
            "--protocol-commit",
            PROTOCOL_COMMIT,
            "--implementation-commit",
            implementation_commit,
        ],
        cwd=source_root,
        env=environment,
        check=False,
        capture_output=True,
    )
    if completed.returncode not in {0, 1}:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise EvidenceError(detail or "confirmatory worker failed")
    artifact = _parse_object(completed.stdout, "worker output")
    if not _verify_integrity(artifact):
        raise EvidenceError("worker produced an invalid artifact integrity hash")
    return completed.stdout


def _resolve_output(path: Path) -> Path:
    resolved = (REPOSITORY_ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        resolved.relative_to(REPOSITORY_ROOT)
    except ValueError as exc:
        raise EvidenceError("evidence outputs must remain inside the repository") from exc
    return resolved


def _write_exclusive(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise EvidenceError(f"refusing to overwrite existing evidence: {path}") from exc


def generate(artifact_path: Path, manifest_path: Path) -> None:
    artifact = _resolve_output(artifact_path)
    manifest = _resolve_output(manifest_path)
    if artifact.exists() or manifest.exists():
        raise EvidenceError("refusing to overwrite an existing evidence bundle")
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise EvidenceError("generation requires a completely clean Git worktree")

    implementation_commit = _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", PROTOCOL_COMMIT, implementation_commit)
    remote_branches = _git("branch", "-r", "--contains", implementation_commit)
    if not any(line.strip().startswith("origin/") for line in remote_branches.splitlines()):
        raise EvidenceError("implementation commit must be pushed to origin before generation")

    first = _worker_bytes(REPOSITORY_ROOT, implementation_commit)
    second = _worker_bytes(REPOSITORY_ROOT, implementation_commit)
    if first != second:
        raise EvidenceError("fresh worker processes did not reproduce byte-identical evidence")

    evidence = _parse_object(first, "confirmatory artifact")
    manifest_value = _seal(
        {
            "schema_version": "sftguard.confirmatory-manifest.v1",
            "artifact_file_sha256": _sha256(first),
            "artifact_integrity_sha256": evidence["integrity"]["canonical_payload_sha256"],
            "artifact_path": artifact.relative_to(REPOSITORY_ROOT).as_posix(),
            "implementation_git_commit": implementation_commit,
            "protocol_git_commit": PROTOCOL_COMMIT,
        }
    )
    _write_exclusive(artifact, first)
    try:
        _write_exclusive(manifest, _pretty_json_bytes(manifest_value))
    except BaseException:
        artifact.unlink(missing_ok=True)
        raise
    print(f"wrote {artifact.relative_to(REPOSITORY_ROOT)}")
    print(f"artifact sha256: {_sha256(first)}")
    print(f"carry forward: {str(evidence.get('carry_forward')).lower()}")


def _verify_bundle(artifact_path: Path, manifest_path: Path) -> tuple[bytes, dict[str, Any]]:
    artifact = _resolve_output(artifact_path)
    manifest = _resolve_output(manifest_path)
    try:
        if artifact.stat().st_size > MAX_EVIDENCE_BYTES:
            raise EvidenceError("artifact exceeds the evidence byte limit")
        if manifest.stat().st_size > MAX_EVIDENCE_BYTES:
            raise EvidenceError("manifest exceeds the evidence byte limit")
        artifact_raw = artifact.read_bytes()
        manifest_raw = manifest.read_bytes()
    except OSError as exc:
        raise EvidenceError("evidence bundle cannot be read") from exc
    artifact_value = _parse_object(artifact_raw, "artifact")
    manifest_value = _parse_object(manifest_raw, "manifest")
    if not _verify_integrity(artifact_value) or not _verify_integrity(manifest_value):
        raise EvidenceError("artifact or manifest integrity verification failed")
    if manifest_value.get("artifact_file_sha256") != _sha256(artifact_raw):
        raise EvidenceError("raw artifact SHA-256 does not match the manifest")
    if (
        manifest_value.get("artifact_integrity_sha256")
        != artifact_value["integrity"]["canonical_payload_sha256"]
    ):
        raise EvidenceError("canonical artifact SHA-256 does not match the manifest")
    if manifest_value.get("protocol_git_commit") != PROTOCOL_COMMIT:
        raise EvidenceError("manifest protocol commit does not match the frozen runner")
    if manifest_value.get("artifact_path") != artifact.relative_to(REPOSITORY_ROOT).as_posix():
        raise EvidenceError("manifest artifact path does not match the selected artifact")
    if artifact_value.get("schema_version") != "sftguard.confirmatory-fault-matrix.v1":
        raise EvidenceError("artifact schema version is not the frozen v0.1 schema")
    provenance = artifact_value.get("provenance")
    if not isinstance(provenance, dict):
        raise EvidenceError("artifact provenance is missing")
    if provenance.get("protocol_git_commit") != PROTOCOL_COMMIT:
        raise EvidenceError("artifact protocol commit does not match the frozen runner")
    implementation_commit = provenance.get("implementation_git_commit")
    if (
        not isinstance(implementation_commit, str)
        or len(implementation_commit) != 40
        or any(character not in "0123456789abcdef" for character in implementation_commit)
    ):
        raise EvidenceError("artifact implementation commit is invalid")
    if implementation_commit != manifest_value.get("implementation_git_commit"):
        raise EvidenceError("implementation commit differs between artifact and manifest")
    return artifact_raw, manifest_value


def verify(artifact_path: Path, manifest_path: Path, *, replay: bool) -> None:
    artifact_raw, manifest = _verify_bundle(artifact_path, manifest_path)
    implementation_commit = manifest["implementation_git_commit"]
    if replay:
        _git("cat-file", "-e", f"{implementation_commit}^{{commit}}")
        with tempfile.TemporaryDirectory(prefix="sftguard-evidence-") as temporary:
            worktree = Path(temporary) / "source"
            _git("worktree", "add", "--detach", str(worktree), implementation_commit)
            try:
                replayed = _worker_bytes(worktree, implementation_commit)
            finally:
                _git("worktree", "remove", "--force", str(worktree))
        if replayed != artifact_raw:
            raise EvidenceError("exact implementation replay did not match checked-in evidence")
    print("evidence integrity verified")
    if replay:
        print("exact implementation replay matched")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate_command = commands.add_parser("generate")
    verify_command = commands.add_parser("verify")
    for command in (generate_command, verify_command):
        command.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
        command.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    verify_command.add_argument(
        "--integrity-only",
        action="store_true",
        help="verify hashes without recreating the implementation worktree",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "generate":
            generate(args.artifact, args.manifest)
        else:
            verify(args.artifact, args.manifest, replay=not args.integrity_only)
    except EvidenceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
