import { describe, expect, it } from "vitest";
import auditJson from "./data/sample-audit.json";
import faultJson from "./data/sample-fault.json";
import regressionJson from "./data/sample-regression.json";
import {
  MAX_REPORT_BYTES,
  parseReport,
  parseReportText,
} from "./reportSchema";

const HASH_A = "a".repeat(64);
const HASH_B = "b".repeat(64);
const HASH_C = "c".repeat(64);

const coreAuditArtifact = {
  schema_version: "sftguard.audit.v1",
  tool: { name: "sftguard", version: "0.1.0" },
  status: "ABSTAIN",
  inputs: [
    {
      split: "train",
      sha256: HASH_A,
      byte_count: 120,
      record_count: 2,
    },
    {
      split: "evaluation",
      sha256: HASH_B,
      byte_count: 80,
      record_count: 1,
    },
  ],
  checks: {
    schema: { status: "PASS" },
    assistant_mask: {
      status: "ABSTAIN",
      reason: "private-record-marker",
    },
  },
  summary: {
    finding_count: 1,
    signal_counts: { pii_like: 1 },
    error_or_critical_count: 0,
    redacted_finding_count: 1,
  },
  findings: [
    {
      signal: "pii_like",
      severity: "warning",
      category: "Privacy pattern",
      location: { split: "train", line: 2, field: "messages" },
      record_sha256: HASH_C,
      details: { raw_match: "private-record-marker" },
    },
  ],
  integrity: { algorithm: "sha256", canonical_payload_sha256: HASH_C },
};

const coreRegressionArtifact = {
  schema_version: "sftguard.regression-card.v1",
  tool: { name: "sftguard", version: "0.1.0" },
  status: "FAIL",
  inputs: [
    {
      split: "base",
      sha256: HASH_A,
      byte_count: 400,
      record_count: 8,
    },
    {
      split: "adapter",
      sha256: HASH_B,
      byte_count: 400,
      record_count: 8,
    },
    { split: "contract", sha256: HASH_C },
  ],
  bootstrap: {
    method: "paired_seed_cluster_xorshift32",
    draws: 1000,
    confidence: 0.95,
    seed: 7,
  },
  metrics: [
    {
      group: "target",
      metric: "answer_accuracy",
      higher_is_better: true,
      status: "PASS",
      pair_count: 8,
      seed_cluster_count: 2,
      mean_normalized_improvement: 0.12,
      confidence_interval: { low: 0.08, high: 0.16 },
      threshold: { min_improvement: 0.05 },
      decision_rule: "lower bound meets minimum improvement",
    },
    {
      group: "retention",
      metric: "general_accuracy",
      higher_is_better: true,
      status: "FAIL",
      pair_count: 8,
      seed_cluster_count: 2,
      mean_normalized_improvement: -0.04,
      confidence_interval: { low: -0.06, high: -0.02 },
      threshold: { max_regression: 0.03 },
      decision_rule: "lower bound stays above retention floor",
    },
  ],
  summary: { metric_count: 2, pair_count: 8, seed_cluster_count: 2 },
  integrity: { algorithm: "sha256", canonical_payload_sha256: HASH_B },
};

const developmentBenchmarkArtifact = {
  schema_version: "sftguard.development-benchmark.v1",
  tool: { name: "sftguard", version: "0.1.0" },
  development_only: true,
  seed_range: { first: 1, last: 2, count: 2 },
  fault_count: 2,
  summary: {
    case_count: 6,
    clean_control_count: 2,
    clean_false_positive_count: 0,
    clean_false_positive_rate: 0,
    macro_recall: 0.75,
  },
  per_fault: [
    {
      fault_id: "train_eval_leakage",
      expected_signal: "train_eval_leakage",
      severity: "critical",
      case_count: 2,
      detected_count: 2,
      recall: 1,
    },
    {
      fault_id: "missing_eos",
      expected_signal: "missing_eos",
      severity: "error",
      case_count: 2,
      detected_count: 1,
      recall: 0.5,
    },
  ],
  cases: [{ raw_synthetic_text: "raw-case-marker" }],
  gates: {
    critical_fault_recall_100_percent: true,
    macro_recall_at_least_90_percent: false,
    clean_false_positive_rate_at_most_10_percent: true,
    expected_and_observed_primary_recorded: true,
    in_process_byte_reproducible: true,
    raw_synthetic_text_absent: true,
  },
  all_development_gates_passed: false,
  status: "FAIL",
  integrity: { algorithm: "sha256", canonical_payload_sha256: HASH_A },
};

const confirmatoryFaultMatrixArtifact = {
  schema_version: "sftguard.confirmatory-fault-matrix.v1",
  tool: { name: "sftguard", version: "0.1.0" },
  provenance: {
    implementation_git_commit: "1".repeat(40),
    protocol_git_commit: "2".repeat(40),
    python_implementation: "CPython",
    python_version: "3.13",
  },
  protocol: { private_fixture_note: "protocol-private-marker" },
  summary: {
    case_count: 6,
    clean_control_count: 2,
    clean_false_positive_count: 0,
    clean_false_positive_rate: 0,
    fault_case_count: 4,
    macro_recall: 0.75,
  },
  per_fault: [
    {
      fault_id: "train_eval_leakage",
      expected_signal: "train_eval_leakage",
      severity: "critical",
      case_count: 2,
      detected_count: 2,
      recall: 1,
    },
    {
      fault_id: "missing_eos",
      expected_signal: "missing_eos",
      severity: "error",
      case_count: 2,
      detected_count: 1,
      recall: 0.5,
    },
  ],
  cases: [{ raw_private_text: "confirmatory-case-marker" }],
  gates: {
    clean_false_positive_rate_at_most_10_percent: true,
    critical_fault_recall_100_percent: true,
    expected_and_observed_primary_recorded: true,
    fresh_process_byte_reproducible: true,
    macro_recall_at_least_90_percent: false,
    raw_synthetic_text_absent: true,
  },
  carry_forward: false,
  status: "FAIL",
  integrity: { algorithm: "sha256", canonical_payload_sha256: HASH_C },
};

describe("SFTGuard report schema", () => {
  it("loads the three checked-in status and report variants", () => {
    const audit = parseReport(auditJson);
    const regression = parseReport(regressionJson);
    const fault = parseReport(faultJson);

    expect(audit.status).toBe("ABSTAIN");
    expect(audit.audit?.supervisedTokens).toBeNull();
    expect(regression.status).toBe("PASS");
    expect(regression.regression?.target.delta).toBe(12.4);
    expect(fault.status).toBe("FAIL");
    expect(fault.faultCoverage?.detectedFaultClasses).toBe(8);
  });

  it("allow-lists aggregate fields and ignores unknown raw content", () => {
    const report = parseReport({
      ...regressionJson,
      rawPrompt: "this must never be rendered",
      messages: [{ role: "user", content: "private" }],
    });
    expect(report).not.toHaveProperty("rawPrompt");
    expect(report).not.toHaveProperty("messages");
  });

  it("adapts the core audit without retaining record-level context", () => {
    const report = parseReport(coreAuditArtifact);
    const serialized = JSON.stringify(report);

    expect(report.reportType).toBe("audit");
    expect(report.status).toBe("ABSTAIN");
    expect(report.audit?.recordsScanned).toBe(3);
    expect(report.audit?.checksPassed).toBe(1);
    expect(report.generatedAt).toBeNull();
    expect(report.provenance.protocolCommit).toBeNull();
    expect(report.provenance.integrityStatus).toBe("unverified");
    expect(serialized).not.toContain("private-record-marker");
    expect(serialized).not.toContain("record_sha256");
    expect(report.issues[0]).not.toHaveProperty("location");
  });

  it("adapts normalized regression metrics and preserves metric decisions", () => {
    const report = parseReport(coreRegressionArtifact);

    expect(report.reportType).toBe("regression");
    expect(report.status).toBe("FAIL");
    expect(report.regression?.target.unit).toBe("normalized-delta");
    expect(report.regression?.target.delta).toBe(0.12);
    expect(report.regression?.target.baseScore).toBeNull();
    expect(report.regression?.target.status).toBe("PASS");
    expect(report.regression?.retention.status).toBe("FAIL");
    expect(report.provenance.runtime).toBeNull();
  });

  it("adapts development fault aggregates and drops the raw cases array", () => {
    const report = parseReport(developmentBenchmarkArtifact);
    const serialized = JSON.stringify(report);

    expect(report.reportType).toBe("fault-matrix");
    expect(report.faultCoverage?.detectedFaultClasses).toBe(1);
    expect(report.faultCoverage?.criticalRecallPercent).toBe(100);
    expect(report.faultCoverage?.macroRecallPercent).toBe(75);
    expect(report.provenance.deterministicReplay).toBe(true);
    expect(serialized).not.toContain("raw-case-marker");
    expect(report).not.toHaveProperty("cases");
  });

  it("adapts confirmatory aggregates, commits, gates, and fresh-process replay", () => {
    const report = parseReport(confirmatoryFaultMatrixArtifact);
    const serialized = JSON.stringify(report);

    expect(report.title).toBe("Confirmatory fault-injection matrix");
    expect(report.status).toBe("FAIL");
    expect(report.faultCoverage?.carryForward).toBe(false);
    expect(report.faultCoverage?.macroRecallPercent).toBe(75);
    expect(report.provenance.protocolCommit).toBe("2".repeat(40));
    expect(report.provenance.implementationCommit).toBe("1".repeat(40));
    expect(report.provenance.runtime).toBe("CPython 3.13");
    expect(report.provenance.deterministicReplay).toBe(true);
    expect(report.provenance.integrityStatus).toBe("unverified");
    expect(serialized).not.toContain("confirmatory-case-marker");
    expect(serialized).not.toContain("protocol-private-marker");
    expect(report).not.toHaveProperty("cases");
    expect(report).not.toHaveProperty("protocol");
  });

  it("fails closed on unsupported status and malformed provenance", () => {
    expect(() =>
      parseReport({ ...regressionJson, status: "UNKNOWN" }),
    ).toThrow(/status must be one of/i);
    expect(() =>
      parseReport({
        ...regressionJson,
        provenance: { ...regressionJson.provenance, artifactSha256: "short" },
      }),
    ).toThrow(/sha-256/i);
    expect(() =>
      parseReport({
        ...regressionJson,
        regression: {
          ...regressionJson.regression,
          target: {
            ...regressionJson.regression.target,
            deltaPercentagePoints: 99,
          },
        },
      }),
    ).toThrow(/adapterScore minus baseScore/i);
  });

  it("rejects invalid JSON and files beyond the local limit", () => {
    expect(() => parseReportText("not json")).toThrow(/not valid json/i);
    expect(() => parseReportText(" ".repeat(MAX_REPORT_BYTES + 1))).toThrow(
      /2 MB/i,
    );
  });

  it("rejects unsupported artifact schemas", () => {
    expect(() =>
      parseReport({ schema_version: "sftguard.unknown.v9" }),
    ).toThrow(/unsupported sftguard report schema/i);
  });
});
