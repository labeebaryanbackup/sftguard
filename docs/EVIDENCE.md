# Reproducing the v0.1 evidence

The confirmatory bundle is generated once from the frozen implementation and
then retained whether its gates pass or fail. The runner does not overwrite an
existing result.

## Phase separation

1. Commit and publish the [fault protocol](FAULT_INJECTION_PROTOCOL.md).
2. Implement and test only with development seeds `0–9`.
3. Commit and push the complete detector, runner, tests, and frozen thresholds.
4. From that clean pushed commit, execute the confirmatory seeds `4100–4129`.
5. Commit the resulting artifact and manifest without changing a detector or
   threshold in response to the result.

The runner enforces steps 3 and 4 by refusing a dirty tree, an implementation
commit not represented by a local `origin/*` ref, or existing evidence paths.

## Generate the bundle once

```bash
python scripts/confirmatory_evidence.py generate
```

Two fresh Python processes independently produce the complete JSON bytes. The
runner writes files only if those bytes match and both artifacts pass their
canonical integrity check.

The bundle contains:

- `evidence/v0.1.0-confirmatory.json` — aggregate gates, per-fault recall,
  per-case identifiers/statuses, provenance, and no synthetic record text;
- `evidence/v0.1.0-confirmatory.manifest.json` — raw file SHA-256, canonical
  payload SHA-256, protocol commit, and implementation commit.

The raw file digest lives in the manifest because a file cannot contain its own
SHA-256 without changing that digest.

## Verify integrity

This check needs only the two evidence files:

```bash
python scripts/confirmatory_evidence.py verify --integrity-only
```

## Replay the exact implementation

With full Git history available, this creates a temporary detached worktree at
the recorded implementation commit and regenerates the bytes:

```bash
python scripts/confirmatory_evidence.py verify
```

Replay requires the same Python major/minor version recorded by the artifact.
CI performs the exact replay on Python 3.11 and integrity checks across the
supported matrix.

## Interpretation

A passing artifact supports only the claim frozen in the protocol. The nine
injections are structural templates repeated across deterministic synthetic
markers. The result is internal detector regression evidence, not an external
dataset benchmark or a claim about unknown fine-tuning failures.
