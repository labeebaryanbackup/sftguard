## Change

Describe the user-visible behavior and why it belongs inside SFTGuard's bounded
correctness or regression contract.

## Evidence

List the deterministic tests, synthetic fixtures, commands, and observed
results. Do not attach private datasets or an unsanitized report.

## Privacy and security

Describe new inputs, outputs, paths, dependencies, or network behavior. State
whether any artifact schema or safe-sharing guidance changed.

## Checklist

- [ ] Python tests pass on the supported versions, when applicable.
- [ ] The Node 22 viewer checks and production build pass, when applicable.
- [ ] New behavior has a deterministic synthetic test and negative control.
- [ ] `PASS`, `FAIL`, and `ABSTAIN` remain distinct and fail closed.
- [ ] Artifacts and fixtures contain no raw private records, credentials, or model weights.
- [ ] No telemetry, automatic upload, or automatic posting was introduced.
- [ ] Documentation and the frozen evidence boundary remain accurate.
