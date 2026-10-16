# SFTGuard v0.1 product specification

Status: frozen before confirmatory implementation evidence.

## Question

Can a local, fail-closed harness catch common supervised fine-tuning pipeline
faults and block adapter releases that exceed explicit regression budgets?

## User workflow

1. Audit local JSONL training and evaluation files.
2. Inspect exact rendered token roles and the supervised-token mask when a
   compatible tokenizer is available.
3. Run a tiny overfit smoke test outside the core package if desired.
4. Supply paired base and adapter evaluation records.
5. Generate a machine-readable Regression Card and a static browser report.
6. Use the CLI exit code in continuous integration.

## v0.1 components

- A dependency-light Python library and `sftguard` CLI.
- Deterministic dataset audits with bounded input sizes.
- A tokenizer integration that abstains when the chat template cannot expose a
  trustworthy assistant-token mask.
- Paired target/retention regression gates with deterministic bootstrap
  intervals.
- Content-addressed JSON artifacts that contain hashes and aggregates, not raw
  prompts or responses.
- A static React report viewer. Imported reports remain in the browser.
- A synthetic fault-injection benchmark and checked-in evidence artifact.
- GitHub Actions checks for Python, web, dependency, and artifact validation.

## Status semantics

- `PASS`: every required check ran and every frozen gate passed.
- `FAIL`: at least one required check ran and violated its gate.
- `ABSTAIN`: the harness lacks the evidence required to make a pass/fail
  decision. Abstention must never be silently converted to a pass.

## Privacy and security

- Dataset analysis is local by default.
- Reports must not contain raw dataset text, secrets, or model weights.
- Secret and PII-like detectors report only location and category.
- Input files are size-limited and parsed line by line.
- No shell commands are constructed from dataset values.
- The public dashboard has no analytics, external fonts, or upload endpoint.

## Evidence boundary

The built-in fault matrix is deterministic synthetic validation of SFTGuard's
own checks. It is not an external benchmark, a safety certification, or proof
that the tool catches every real fine-tuning failure. Base-versus-adapter
Regression Cards measure only the supplied evaluation contract.
