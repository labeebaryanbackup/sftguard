# v0.1 confirmatory result

Status: `PASS`

Carry forward: `true`

The result was generated after the protocol and implementation were committed
and pushed. No detector or threshold was changed after confirmatory execution.
Post-result changes are limited to checked-in evidence, documentation,
packaging metadata, Pages routing, and rendering that evidence in the static
viewer; the recorded implementation remains the replay authority.

## Frozen gates

| Gate | Result |
| --- | ---: |
| 100% recall for every critical fault class | pass — 30/30 for each class |
| Macro recall across all nine fault classes ≥ 90% | pass — 100% |
| Clean-control false-positive rate ≤ 10% | pass — 0/30 (0%) |
| Expected and observed primary signal recorded | pass |
| Fresh process reproduces result bytes | pass |
| Raw prompts, responses, and injected secrets absent | pass |

Across 30 seeds, all 270 injected cases emitted their required primary signal.
All 30 clean controls emitted no signal. The exact implementation replay
matched the checked-in artifact byte-for-byte.

## Provenance

| Item | Value |
| --- | --- |
| Protocol commit | `d4c74cefca6729124142635dc8893b5e3ddec2d3` |
| Implementation commit | `b0f168ab4d6a959d4e28611e345a250c14ca2ea9` |
| Python | CPython 3.11 |
| Raw artifact SHA-256 | `961b2842d7791f6f3af7bec5bce6105e433b68d41bf6f7b82a9f3a98e1f695ab` |
| Canonical payload SHA-256 | `eb55eaa16a492881ff1bcec8812b2ef37bb2ed6055b6b90a1da408386f632e3a` |

See the [artifact](../evidence/v0.1.0-confirmatory.json),
[manifest](../evidence/v0.1.0-confirmatory.manifest.json), and
[reproduction guide](EVIDENCE.md).

## Allowed claim

> SFTGuard detected the preregistered synthetic fault matrix with the reported
> false-positive rate and reproduced its content-addressed evidence.

This is internal detector regression evidence. Each class uses one structural
fault template across deterministic marker variations. The result does not show
coverage of unknown faults, model quality, or safety, and it is not an external
fine-tuning benchmark.
