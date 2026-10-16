# SFTGuard report viewer

Static, local-first browser UI for SFTGuard aggregate report artifacts.

```bash
npm ci
npm run dev
```

`npm run check` performs the TypeScript, unit-test, and production-build checks.

## Supported artifacts

The viewer validates and adapts these checked-in core artifact formats:

- `sftguard.audit.v1`;
- `sftguard.regression-card.v1`;
- `sftguard.development-benchmark.v1`; and
- `sftguard.confirmatory-fault-matrix.v1`.

The illustrative UI fixtures use the additional `sftguard.report.v1` render
envelope documented in `src/reportSchema.ts`. The allow-listed render model
contains:

- a `PASS`, `FAIL`, or `ABSTAIN` decision;
- one audit, regression, or fault-matrix summary;
- aggregate issue categories and counts;
- content-addressed provenance; and
- claim and privacy boundaries.

Unknown fields are not copied into the render model. Audit record locations,
record hashes and details, evaluation rows, benchmark `cases`, and confirmatory
protocol internals are intentionally discarded by the adapters. Missing
timestamps, commits, runtime details, or replay evidence are shown as
unavailable rather than inferred. Artifact digests are displayed as declared
and explicitly marked unverified because this static viewer does not reproduce
the Python canonical-JSON hash calculation.

Imports are read into the current browser tab only and are neither uploaded nor
stored. The default entry is adapted from the checked-in v0.1 confirmatory
artifact; the regression, failing fault-matrix, and abstaining audit entries are
clearly labelled illustrative UI fixtures.
