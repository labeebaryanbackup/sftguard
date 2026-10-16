# SFTGuard v0.1 fault-injection protocol

Status: frozen before confirmatory seeds are generated or inspected.

## Purpose

The benchmark tests whether SFTGuard detects a bounded list of deterministic
pipeline faults while leaving clean controls unflagged. It tests this repository,
not the general quality of supervised fine-tuning.

## Frozen matrix

Confirmatory seeds are integers `4100` through `4129`. Each seed produces one
clean training/evaluation pair and one independently injected case for each
fault below:

| Fault ID | Injected condition | Required signal | Severity |
| --- | --- | --- | --- |
| `schema.invalid_role` | A message role is outside the allowed role set | `invalid_role` | error |
| `schema.role_order` | Assistant content appears without a preceding user turn | `role_order` | error |
| `template.missing_eos` | The rendered assistant turn lacks the configured EOS token | `missing_eos` | error |
| `mask.prompt_supervised` | At least one system or user token is marked for loss | `prompt_token_supervised` | critical |
| `truncation.answer_removed` | Truncation removes every supervised assistant token | `assistant_fully_truncated` | critical |
| `data.exact_duplicate` | A complete training record is duplicated | `exact_duplicate` | warning |
| `data.prompt_conflict` | The same prompt maps to different assistant answers | `prompt_conflict` | error |
| `data.train_eval_leakage` | A prompt occurs in both train and evaluation splits | `train_eval_leakage` | critical |
| `privacy.secret_pattern` | A synthetic credential-shaped string occurs in a record | `secret_pattern` | critical |

Each case has exactly one primary injected fault. Incidental secondary signals
are permitted but must be recorded. Clean controls contain no injected fault.

Development seeds `0` through `9` may be used before the confirmatory run.
Confirmatory data or aggregate results must not be used to change detection
rules or thresholds.

## Frozen gates

The v0.1 result carries forward only if all gates pass:

1. Recall is `100%` for every critical fault class.
2. Macro recall across all nine primary fault classes is at least `90%`.
3. The clean-control false-positive rate is no greater than `10%`.
4. Every result records its expected and observed primary signal.
5. A fresh process reproduces the canonical result payload byte-for-byte.
6. Reports contain no raw prompt, response, or injected synthetic secret.

No post-result threshold tuning is allowed on seeds `4100` through `4129`.
If a gate fails, the evidence remains checked in with `carryForward: false`.

## Determinism and provenance

The result records:

- protocol and implementation Git commits;
- Python version and SFTGuard version;
- exact seed range and fault list;
- configuration and per-case hashes;
- raw artifact SHA-256 and canonical payload SHA-256;
- aggregate counts and per-case status without dataset contents.

Bootstrap intervals, when reported, use seed-cluster resampling with
`10,000` draws and PRNG seed `2339`.

## Claim boundary

A passing result supports only this statement:

> SFTGuard detected the preregistered synthetic fault matrix with the reported
> false-positive rate and reproduced its content-addressed evidence.

It does not show that SFTGuard catches unknown faults, evaluates model quality,
prevents every privacy leak, or makes fine-tuning safe.
