# Contributing to SFTGuard

SFTGuard welcomes small, reviewable contributions that preserve its
fail-closed and local-first boundaries. Before beginning a large change, open a
feature request describing the intended evidence and failure behavior.

## Privacy first

Use synthetic fixtures in issues, pull requests, tests, and screenshots. Never
submit private training data, prompts, responses, access tokens, model weights,
or reports containing them. Redact local usernames and absolute paths. Security
and privacy vulnerabilities belong in a private report under
[SECURITY.md](SECURITY.md), not a public issue.

SFTGuard does not automatically publish reports or post results to external
services. Contributions must not introduce telemetry, remote report processing,
or automatic uploads without an explicit design review and an opt-in boundary.

## Development setup

Python 3.11 or 3.12 and Node.js 22 are supported for development.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
```

Build and test the static viewer separately:

```bash
cd web
npm ci
npm run check
```

The repository CI is the authority for the complete supported-platform matrix.
If a command changes, update the workflow and this file in the same pull
request.

## Change requirements

- Keep input parsing bounded and avoid reading entire untrusted files when a
  streaming implementation is possible.
- Never construct shell commands from dataset values.
- Preserve `PASS`, `FAIL`, and `ABSTAIN` as distinct outcomes. Missing evidence
  must not become a pass.
- Keep public artifacts free of raw prompt, response, and injected-secret text.
- Add deterministic tests for every detector, gate, parser, and schema change.
- Document new report fields and state whether they are safe to share.
- Do not describe synthetic validation as a real-world safety guarantee.

The confirmatory seed range in
[docs/FAULT_INJECTION_PROTOCOL.md](docs/FAULT_INJECTION_PROTOCOL.md) is frozen.
Do not tune rules or thresholds after inspecting confirmatory results. A failed
gate should remain visible with `carryForward: false`.

## Pull requests

Create a focused branch, run the relevant Python and web checks, and complete
the pull-request checklist. Explain the user-visible behavior, evidence, and
privacy impact. Generated build directories, local artifacts, datasets, and
model files must remain untracked.

By participating, you agree to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
