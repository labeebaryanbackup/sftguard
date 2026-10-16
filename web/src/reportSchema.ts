/**
 * SFTGuard browser render model and artifact adapters.
 *
 * The parser is deliberately allow-list based: it copies only documented
 * aggregate fields into the render model. Unknown fields are ignored and are
 * never rendered. Core artifact adapters intentionally discard record-level
 * locations, hashes, details, and synthetic cases before React sees them.
 */
export const REPORT_SCHEMA_VERSION = "sftguard.report.v1" as const;
export const AUDIT_SCHEMA_VERSION = "sftguard.audit.v1" as const;
export const REGRESSION_SCHEMA_VERSION =
  "sftguard.regression-card.v1" as const;
export const DEVELOPMENT_BENCHMARK_SCHEMA_VERSION =
  "sftguard.development-benchmark.v1" as const;
export const CONFIRMATORY_FAULT_MATRIX_SCHEMA_VERSION =
  "sftguard.confirmatory-fault-matrix.v1" as const;
export const MAX_REPORT_BYTES = 2 * 1024 * 1024;

export type ReportStatus = "PASS" | "FAIL" | "ABSTAIN";
export type ReportType = "audit" | "regression" | "fault-matrix";
export type IssueSeverity = "critical" | "error" | "warning" | "info";

export interface ReportIssue {
  id: string;
  category: string;
  severity: IssueSeverity;
  outcome: ReportStatus;
  count: number;
  title: string;
  detail: string;
}

export interface AuditSummary {
  recordsScanned: number;
  checksPassed: number;
  checksTotal: number;
  supervisedTokens: number | null;
}

export interface ScoreContract {
  label: string;
  status: "PASS" | "FAIL";
  baseScore: number | null;
  adapterScore: number | null;
  delta: number;
  unit: "percentage-points" | "normalized-delta";
  pairCount?: number;
  confidenceInterval?: { low: number; high: number };
}

export interface TargetScoreContract extends ScoreContract {
  minimumGain: number;
}

export interface RetentionScoreContract extends ScoreContract {
  maximumRegression: number;
}

export interface RegressionSummary {
  target: TargetScoreContract;
  retention: RetentionScoreContract;
}

export interface FaultCoverage {
  expectedFaultClasses: number;
  detectedFaultClasses: number;
  criticalRecallPercent: number;
  macroRecallPercent: number;
  cleanFalsePositiveRatePercent: number;
  carryForward: boolean;
}

export interface ReportProvenance {
  toolVersion: string;
  protocolCommit: string | null;
  implementationCommit: string | null;
  inputSha256: string | null;
  artifactSha256: string;
  integrityStatus: "verified" | "mismatch" | "unverified";
  runtime: string | null;
  deterministicReplay: boolean | null;
}

export interface ReportBoundaries {
  claim: string[];
  privacy: string[];
}

export interface SftGuardReport {
  schemaVersion: typeof REPORT_SCHEMA_VERSION;
  reportType: ReportType;
  reportId: string;
  title: string;
  generatedAt: string | null;
  status: ReportStatus;
  summary: string;
  audit?: AuditSummary;
  regression?: RegressionSummary;
  faultCoverage?: FaultCoverage;
  issues: ReportIssue[];
  provenance: ReportProvenance;
  boundaries: ReportBoundaries;
}

function asRecord(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError(`${label} must be an object.`);
  }
  return value as Record<string, unknown>;
}

function asString(
  value: unknown,
  label: string,
  maximumLength = 500,
): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new TypeError(`${label} must be a non-empty string.`);
  }
  if (value.length > maximumLength) {
    throw new RangeError(`${label} is longer than ${maximumLength} characters.`);
  }
  return value;
}

function asFiniteNumber(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`${label} must be a finite number.`);
  }
  return value;
}

function asNonNegativeInteger(value: unknown, label: string): number {
  const number = asFiniteNumber(value, label);
  if (!Number.isSafeInteger(number) || number < 0) {
    throw new RangeError(`${label} must be a non-negative safe integer.`);
  }
  return number;
}

function asBoolean(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") {
    throw new TypeError(`${label} must be true or false.`);
  }
  return value;
}

function asEnum<T extends string>(
  value: unknown,
  label: string,
  choices: readonly T[],
): T {
  if (typeof value !== "string" || !choices.includes(value as T)) {
    throw new RangeError(`${label} must be one of ${choices.join(", ")}.`);
  }
  return value as T;
}

function asSha256(value: unknown, label: string): string {
  const hash = asString(value, label, 64);
  if (!/^[0-9a-f]{64}$/.test(hash)) {
    throw new RangeError(`${label} must be a lowercase SHA-256 digest.`);
  }
  return hash;
}

function asCommit(value: unknown, label: string): string {
  const commit = asString(value, label, 40);
  if (!/^[0-9a-f]{40}$/.test(commit)) {
    throw new RangeError(`${label} must be a full lowercase Git commit.`);
  }
  return commit;
}

function asStringArray(value: unknown, label: string): string[] {
  if (!Array.isArray(value) || value.length === 0 || value.length > 20) {
    throw new RangeError(`${label} must contain between 1 and 20 entries.`);
  }
  return value.map((entry, index) =>
    asString(entry, `${label}[${index}]`, 300),
  );
}

function parseIssue(value: unknown, index: number): ReportIssue {
  const issue = asRecord(value, `issues[${index}]`);
  return {
    id: asString(issue.id, `issues[${index}].id`, 120),
    category: asString(issue.category, `issues[${index}].category`, 80),
    severity: asEnum(issue.severity, `issues[${index}].severity`, [
      "critical",
      "error",
      "warning",
      "info",
    ] as const),
    outcome: asEnum(issue.outcome, `issues[${index}].outcome`, [
      "PASS",
      "FAIL",
      "ABSTAIN",
    ] as const),
    count: asNonNegativeInteger(issue.count, `issues[${index}].count`),
    title: asString(issue.title, `issues[${index}].title`, 140),
    detail: asString(issue.detail, `issues[${index}].detail`, 500),
  };
}

function parseAudit(value: unknown): AuditSummary {
  const audit = asRecord(value, "audit");
  const supervisedTokens =
    audit.supervisedTokens === null
      ? null
      : asNonNegativeInteger(audit.supervisedTokens, "audit.supervisedTokens");
  const parsed = {
    recordsScanned: asNonNegativeInteger(
      audit.recordsScanned,
      "audit.recordsScanned",
    ),
    checksPassed: asNonNegativeInteger(
      audit.checksPassed,
      "audit.checksPassed",
    ),
    checksTotal: asNonNegativeInteger(audit.checksTotal, "audit.checksTotal"),
    supervisedTokens,
  };
  if (parsed.checksPassed > parsed.checksTotal) {
    throw new RangeError("audit.checksPassed cannot exceed checksTotal.");
  }
  return parsed;
}

function parseScore(
  value: unknown,
  label: string,
): Omit<ScoreContract, "status"> {
  const score = asRecord(value, label);
  const parsed = {
    label: asString(score.label, `${label}.label`, 100),
    baseScore: asFiniteNumber(score.baseScore, `${label}.baseScore`),
    adapterScore: asFiniteNumber(score.adapterScore, `${label}.adapterScore`),
    delta: asFiniteNumber(
      score.deltaPercentagePoints,
      `${label}.deltaPercentagePoints`,
    ),
    unit: "percentage-points" as const,
  };
  const calculatedDelta = parsed.adapterScore - parsed.baseScore;
  if (Math.abs(calculatedDelta - parsed.delta) > 1e-9) {
    throw new RangeError(
      `${label}.deltaPercentagePoints must equal adapterScore minus baseScore.`,
    );
  }
  return parsed;
}

function parseRegression(value: unknown): RegressionSummary {
  const regression = asRecord(value, "regression");
  const target = asRecord(regression.target, "regression.target");
  const retention = asRecord(regression.retention, "regression.retention");
  const targetScore = parseScore(target, "regression.target");
  const retentionScore = parseScore(retention, "regression.retention");
  const minimumGain = asFiniteNumber(
    target.minimumGainPercentagePoints,
    "regression.target.minimumGainPercentagePoints",
  );
  const maximumRegression = asFiniteNumber(
    retention.maximumRegressionPercentagePoints,
    "regression.retention.maximumRegressionPercentagePoints",
  );
  return {
    target: {
      ...targetScore,
      status: targetScore.delta >= minimumGain ? "PASS" : "FAIL",
      minimumGain,
    },
    retention: {
      ...retentionScore,
      status:
        retentionScore.delta >= -maximumRegression ? "PASS" : "FAIL",
      maximumRegression,
    },
  };
}

function asPercent(value: unknown, label: string): number {
  const percent = asFiniteNumber(value, label);
  if (percent < 0 || percent > 100) {
    throw new RangeError(`${label} must be between 0 and 100.`);
  }
  return percent;
}

function parseFaultCoverage(value: unknown): FaultCoverage {
  const coverage = asRecord(value, "faultCoverage");
  const expected = asNonNegativeInteger(
    coverage.expectedFaultClasses,
    "faultCoverage.expectedFaultClasses",
  );
  const detected = asNonNegativeInteger(
    coverage.detectedFaultClasses,
    "faultCoverage.detectedFaultClasses",
  );
  if (detected > expected) {
    throw new RangeError(
      "faultCoverage.detectedFaultClasses cannot exceed expectedFaultClasses.",
    );
  }
  return {
    expectedFaultClasses: expected,
    detectedFaultClasses: detected,
    criticalRecallPercent: asPercent(
      coverage.criticalRecallPercent,
      "faultCoverage.criticalRecallPercent",
    ),
    macroRecallPercent: asPercent(
      coverage.macroRecallPercent,
      "faultCoverage.macroRecallPercent",
    ),
    cleanFalsePositiveRatePercent: asPercent(
      coverage.cleanFalsePositiveRatePercent,
      "faultCoverage.cleanFalsePositiveRatePercent",
    ),
    carryForward: asBoolean(
      coverage.carryForward,
      "faultCoverage.carryForward",
    ),
  };
}

function parseProvenance(value: unknown): ReportProvenance {
  const provenance = asRecord(value, "provenance");
  return {
    toolVersion: asString(provenance.toolVersion, "provenance.toolVersion", 80),
    protocolCommit: asCommit(
      provenance.protocolCommit,
      "provenance.protocolCommit",
    ),
    implementationCommit: asCommit(
      provenance.implementationCommit,
      "provenance.implementationCommit",
    ),
    inputSha256: asSha256(provenance.inputSha256, "provenance.inputSha256"),
    artifactSha256: asSha256(
      provenance.artifactSha256,
      "provenance.artifactSha256",
    ),
    integrityStatus: "unverified",
    runtime: asString(provenance.runtime, "provenance.runtime", 160),
    deterministicReplay: asBoolean(
      provenance.deterministicReplay,
      "provenance.deterministicReplay",
    ),
  };
}

function parseEnvelopeReport(value: unknown): SftGuardReport {
  const report = asRecord(value, "report");
  const schemaVersion = asEnum(report.schemaVersion, "schemaVersion", [
    REPORT_SCHEMA_VERSION,
  ] as const);
  const reportType = asEnum(report.reportType, "reportType", [
    "audit",
    "regression",
    "fault-matrix",
  ] as const);
  const generatedAt = asString(report.generatedAt, "generatedAt", 80);
  if (!Number.isFinite(Date.parse(generatedAt))) {
    throw new RangeError("generatedAt must be an ISO-compatible date string.");
  }
  if (!Array.isArray(report.issues) || report.issues.length > 100) {
    throw new RangeError("issues must be an array with at most 100 entries.");
  }
  const boundaries = asRecord(report.boundaries, "boundaries");

  const parsed: SftGuardReport = {
    schemaVersion,
    reportType,
    reportId: asString(report.reportId, "reportId", 120),
    title: asString(report.title, "title", 160),
    generatedAt,
    status: asEnum(report.status, "status", [
      "PASS",
      "FAIL",
      "ABSTAIN",
    ] as const),
    summary: asString(report.summary, "summary", 800),
    issues: report.issues.map(parseIssue),
    provenance: parseProvenance(report.provenance),
    boundaries: {
      claim: asStringArray(boundaries.claim, "boundaries.claim"),
      privacy: asStringArray(boundaries.privacy, "boundaries.privacy"),
    },
  };

  if (reportType === "audit") parsed.audit = parseAudit(report.audit);
  if (reportType === "regression") {
    parsed.regression = parseRegression(report.regression);
  }
  if (reportType === "fault-matrix") {
    parsed.faultCoverage = parseFaultCoverage(report.faultCoverage);
  }
  return parsed;
}

const REPORT_STATUSES = ["PASS", "FAIL", "ABSTAIN"] as const;
const ISSUE_SEVERITIES = ["critical", "error", "warning", "info"] as const;

function asBoundedArray(
  value: unknown,
  label: string,
  maximumLength: number,
): unknown[] {
  if (!Array.isArray(value) || value.length > maximumLength) {
    throw new RangeError(
      `${label} must be an array with at most ${maximumLength} entries.`,
    );
  }
  return value;
}

function asFraction(value: unknown, label: string): number {
  const fraction = asFiniteNumber(value, label);
  if (fraction < 0 || fraction > 1) {
    throw new RangeError(`${label} must be between 0 and 1.`);
  }
  return fraction;
}

function asNonNegativeNumber(value: unknown, label: string): number {
  const number = asFiniteNumber(value, label);
  if (number < 0) {
    throw new RangeError(`${label} must be non-negative.`);
  }
  return number;
}

function humanizeIdentifier(value: string): string {
  const words = value.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  return `${words.slice(0, 1).toUpperCase()}${words.slice(1)}`;
}

function formatDecimal(value: number): string {
  const normalized = Object.is(value, -0) ? 0 : value;
  return normalized.toFixed(4).replace(/\.0+$|(?<=\.[0-9]*?)0+$/g, "");
}

function parseCoreMetadata(
  report: Record<string, unknown>,
  label: string,
  deterministicReplay: boolean | null = null,
): ReportProvenance {
  const tool = asRecord(report.tool, `${label}.tool`);
  if (asString(tool.name, `${label}.tool.name`, 80) !== "sftguard") {
    throw new RangeError(`${label}.tool.name must be sftguard.`);
  }
  const integrity = asRecord(report.integrity, `${label}.integrity`);
  if (
    asString(integrity.algorithm, `${label}.integrity.algorithm`, 20) !==
    "sha256"
  ) {
    throw new RangeError(`${label}.integrity.algorithm must be sha256.`);
  }
  return {
    toolVersion: asString(tool.version, `${label}.tool.version`, 80),
    protocolCommit: null,
    implementationCommit: null,
    inputSha256: null,
    artifactSha256: asSha256(
      integrity.canonical_payload_sha256,
      `${label}.integrity.canonical_payload_sha256`,
    ),
    integrityStatus: "unverified",
    runtime: null,
    deterministicReplay,
  };
}

function validateCoreInputs(
  value: unknown,
  label: string,
  requireRecordCount = false,
): number {
  const inputs = asBoundedArray(value, label, 100);
  let records = 0;
  inputs.forEach((entry, index) => {
    const input = asRecord(entry, `${label}[${index}]`);
    asString(input.split, `${label}[${index}].split`, 80);
    asSha256(input.sha256, `${label}[${index}].sha256`);
    if (input.byte_count !== undefined) {
      asNonNegativeInteger(input.byte_count, `${label}[${index}].byte_count`);
    }
    if (input.record_count === undefined) {
      if (requireRecordCount) {
        throw new TypeError(`${label}[${index}].record_count is required.`);
      }
    } else {
      records += asNonNegativeInteger(
        input.record_count,
        `${label}[${index}].record_count`,
      );
    }
  });
  return records;
}

function parseAuditArtifact(report: Record<string, unknown>): SftGuardReport {
  const label = "audit artifact";
  const status = asEnum(report.status, `${label}.status`, REPORT_STATUSES);
  const provenance = parseCoreMetadata(report, label);
  const recordsScanned = validateCoreInputs(report.inputs, `${label}.inputs`, true);

  const checks = asRecord(report.checks, `${label}.checks`);
  const checkEntries = Object.entries(checks);
  if (checkEntries.length === 0 || checkEntries.length > 100) {
    throw new RangeError(`${label}.checks must contain between 1 and 100 entries.`);
  }
  const parsedChecks = checkEntries.map(([name, value]) => {
    asString(name, `${label}.checks key`, 100);
    const check = asRecord(value, `${label}.checks.${name}`);
    return {
      name,
      status: asEnum(
        check.status,
        `${label}.checks.${name}.status`,
        REPORT_STATUSES,
      ),
    };
  });

  const findings = asBoundedArray(report.findings, `${label}.findings`, 100_000);
  type AuditAggregate = {
    signal: string;
    category: string;
    severity: IssueSeverity;
    count: number;
  };
  const aggregates = new Map<string, AuditAggregate>();
  const derivedSignalCounts = new Map<string, number>();
  findings.forEach((entry, index) => {
    const finding = asRecord(entry, `${label}.findings[${index}]`);
    const signal = asString(
      finding.signal,
      `${label}.findings[${index}].signal`,
      120,
    );
    const severity = asEnum(
      finding.severity,
      `${label}.findings[${index}].severity`,
      ISSUE_SEVERITIES,
    );
    const location = asRecord(
      finding.location,
      `${label}.findings[${index}].location`,
    );
    asEnum(
      location.split,
      `${label}.findings[${index}].location.split`,
      ["train", "evaluation"] as const,
    );
    const line = asNonNegativeInteger(
      location.line,
      `${label}.findings[${index}].location.line`,
    );
    if (line < 1) {
      throw new RangeError(
        `${label}.findings[${index}].location.line must be at least 1.`,
      );
    }
    if (location.field !== undefined) {
      asString(
        location.field,
        `${label}.findings[${index}].location.field`,
        160,
      );
    }
    const category =
      finding.category === undefined
        ? "Audit finding"
        : asString(
            finding.category,
            `${label}.findings[${index}].category`,
            80,
          );
    const key = `${category}\u0000${signal}\u0000${severity}`;
    const aggregate = aggregates.get(key);
    if (aggregate) {
      aggregate.count += 1;
    } else {
      if (aggregates.size >= 100) {
        throw new RangeError(
          `${label}.findings contain more than 100 aggregate categories.`,
        );
      }
      aggregates.set(key, { signal, category, severity, count: 1 });
    }
    derivedSignalCounts.set(
      signal,
      (derivedSignalCounts.get(signal) ?? 0) + 1,
    );
  });

  const summary = asRecord(report.summary, `${label}.summary`);
  const findingCount = asNonNegativeInteger(
    summary.finding_count,
    `${label}.summary.finding_count`,
  );
  if (findingCount !== findings.length) {
    throw new RangeError(
      `${label}.summary.finding_count must match findings length.`,
    );
  }
  const signalCounts = asRecord(
    summary.signal_counts,
    `${label}.summary.signal_counts`,
  );
  if (Object.keys(signalCounts).length > 100) {
    throw new RangeError(`${label}.summary.signal_counts has too many entries.`);
  }
  for (const [signal, count] of Object.entries(signalCounts)) {
    const parsedCount = asNonNegativeInteger(
      count,
      `${label}.summary.signal_counts.${signal}`,
    );
    if (derivedSignalCounts.get(signal) !== parsedCount) {
      throw new RangeError(
        `${label}.summary.signal_counts must match aggregate findings.`,
      );
    }
  }
  if (Object.keys(signalCounts).length !== derivedSignalCounts.size) {
    throw new RangeError(
      `${label}.summary.signal_counts must cover every finding signal.`,
    );
  }

  const issues: ReportIssue[] = [...aggregates.values()].map(
    (aggregate, index) => ({
      id: `audit-signal-${index + 1}`,
      category: aggregate.category,
      severity: aggregate.severity,
      outcome:
        status === "ABSTAIN"
          ? "ABSTAIN"
          : aggregate.severity === "critical" || aggregate.severity === "error"
            ? "FAIL"
            : "PASS",
      count: aggregate.count,
      title: humanizeIdentifier(aggregate.signal),
      detail: `${aggregate.count} aggregate finding${aggregate.count === 1 ? "" : "s"} reported. Record locations and record-level details are not copied into this viewer.`,
    }),
  );
  for (const check of parsedChecks.filter((entry) => entry.status === "ABSTAIN")) {
    issues.push({
      id: `audit-check-${check.name}`,
      category: "Audit check",
      severity: "warning",
      outcome: "ABSTAIN",
      count: 1,
      title: humanizeIdentifier(check.name),
      detail:
        "This check abstained. Its raw reason and record context remain outside the aggregate render model.",
    });
  }

  return {
    schemaVersion: REPORT_SCHEMA_VERSION,
    reportType: "audit",
    reportId: `core-audit-${provenance.artifactSha256.slice(0, 12)}`,
    title: "Dataset and mask audit",
    generatedAt: null,
    status,
    summary: `The audit declared ${status} across ${recordsScanned} record${recordsScanned === 1 ? "" : "s"}, ${findingCount} finding${findingCount === 1 ? "" : "s"}, and ${parsedChecks.length} check${parsedChecks.length === 1 ? "" : "s"}.`,
    audit: {
      recordsScanned,
      checksPassed: parsedChecks.filter((entry) => entry.status === "PASS").length,
      checksTotal: parsedChecks.length,
      supervisedTokens: null,
    },
    issues,
    provenance,
    boundaries: {
      claim: [
        "The decision reflects the supplied local audit artifact only.",
        "A passing audit does not prove dataset quality, model quality, or model safety.",
      ],
      privacy: [
        "Only aggregate signals, severities, and counts are rendered.",
        "Record locations, record hashes, finding details, and source records are discarded by the adapter.",
      ],
    },
  };
}

interface ParsedCoreMetric {
  group: "target" | "retention";
  metric: string;
  status: "PASS" | "FAIL";
  pairCount: number;
  mean: number;
  interval: { low: number; high: number };
  threshold: number;
}

function parseCoreMetric(value: unknown, index: number): ParsedCoreMetric {
  const label = `regression artifact.metrics[${index}]`;
  const metric = asRecord(value, label);
  const group = asEnum(metric.group, `${label}.group`, [
    "target",
    "retention",
  ] as const);
  if (metric.higher_is_better !== undefined) {
    asBoolean(metric.higher_is_better, `${label}.higher_is_better`);
  }
  if (metric.seed_cluster_count !== undefined) {
    asNonNegativeInteger(
      metric.seed_cluster_count,
      `${label}.seed_cluster_count`,
    );
  }
  const interval = asRecord(
    metric.confidence_interval,
    `${label}.confidence_interval`,
  );
  const low = asFiniteNumber(interval.low, `${label}.confidence_interval.low`);
  const high = asFiniteNumber(
    interval.high,
    `${label}.confidence_interval.high`,
  );
  if (low > high) {
    throw new RangeError(`${label}.confidence_interval.low cannot exceed high.`);
  }
  const threshold = asRecord(metric.threshold, `${label}.threshold`);
  const thresholdKey =
    group === "target" ? "min_improvement" : "max_regression";
  asString(metric.decision_rule, `${label}.decision_rule`, 300);
  return {
    group,
    metric: asString(metric.metric, `${label}.metric`, 120),
    status: asEnum(metric.status, `${label}.status`, ["PASS", "FAIL"] as const),
    pairCount: asNonNegativeInteger(metric.pair_count, `${label}.pair_count`),
    mean: asFiniteNumber(
      metric.mean_normalized_improvement,
      `${label}.mean_normalized_improvement`,
    ),
    interval: { low, high },
    threshold: asNonNegativeNumber(
      threshold[thresholdKey],
      `${label}.threshold.${thresholdKey}`,
    ),
  };
}

function parseRegressionArtifact(
  report: Record<string, unknown>,
): SftGuardReport {
  const label = "regression artifact";
  const status = asEnum(report.status, `${label}.status`, REPORT_STATUSES);
  const provenance = parseCoreMetadata(report, label);
  validateCoreInputs(report.inputs, `${label}.inputs`);
  const rawMetrics = asBoundedArray(report.metrics, `${label}.metrics`, 100);
  const metrics = rawMetrics
    .map(parseCoreMetric)
    .sort((left, right) =>
      `${left.group}:${left.metric}`.localeCompare(`${right.group}:${right.metric}`),
    );
  const summary = asRecord(report.summary, `${label}.summary`);
  const metricCount = asNonNegativeInteger(
    summary.metric_count,
    `${label}.summary.metric_count`,
  );
  if (metricCount !== metrics.length) {
    throw new RangeError(`${label}.summary.metric_count must match metrics length.`);
  }
  asNonNegativeInteger(summary.pair_count, `${label}.summary.pair_count`);
  asNonNegativeInteger(
    summary.seed_cluster_count,
    `${label}.summary.seed_cluster_count`,
  );

  const reasonCodes =
    report.reason_codes === undefined
      ? []
      : asBoundedArray(report.reason_codes, `${label}.reason_codes`, 100).map(
          (reason, index) =>
            asString(reason, `${label}.reason_codes[${index}]`, 160),
        );
  const issues: ReportIssue[] = metrics.map((metric, index) => ({
    id: `regression-metric-${index + 1}`,
    category:
      metric.group === "target" ? "Target behavior" : "Retention behavior",
    severity: metric.status === "FAIL" ? "error" : "info",
    outcome: metric.status,
    count: 1,
    title: metric.metric,
    detail: `Mean normalized improvement ${formatDecimal(metric.mean)} with reported interval [${formatDecimal(metric.interval.low)}, ${formatDecimal(metric.interval.high)}] across ${metric.pairCount} pairs; ${metric.group === "target" ? "minimum improvement" : "maximum regression"} ${formatDecimal(metric.threshold)}.`,
  }));
  reasonCodes.forEach((reason, index) => {
    issues.push({
      id: `regression-reason-${index + 1}`,
      category: "Decision evidence",
      severity: "warning",
      outcome: "ABSTAIN",
      count: 1,
      title: humanizeIdentifier(reason),
      detail:
        "The regression card reported this aggregate reason code without exposing evaluation examples.",
    });
  });
  if (status === "ABSTAIN" && reasonCodes.length === 0) {
    issues.push({
      id: "regression-reason-unavailable",
      category: "Decision evidence",
      severity: "warning",
      outcome: "ABSTAIN",
      count: 1,
      title: "Reason unavailable",
      detail: "The artifact abstained without a reason code in its aggregate fields.",
    });
  }

  const target = metrics.find((metric) => metric.group === "target");
  const retention = metrics.find((metric) => metric.group === "retention");
  const adapted: SftGuardReport = {
    schemaVersion: REPORT_SCHEMA_VERSION,
    reportType: "regression",
    reportId: `core-regression-${provenance.artifactSha256.slice(0, 12)}`,
    title: "Target and retention regression card",
    generatedAt: null,
    status,
    summary: `The regression card declared ${status} across ${metricCount} aggregate metric${metricCount === 1 ? "" : "s"}. Estimates are normalized paired improvements, not raw percentage-point scores.`,
    issues,
    provenance,
    boundaries: {
      claim: [
        "The decision applies only to the supplied metric contract and paired evaluation artifact.",
        "Passing declared gates does not establish broad model quality or safety.",
      ],
      privacy: [
        "Only aggregate estimates, intervals, thresholds, pair counts, and reason codes are rendered.",
        "Evaluation rows, prompts, responses, and per-example results are not copied into the viewer.",
      ],
    },
  };
  if (target && retention) {
    adapted.regression = {
      target: {
        label: target.metric,
        status: target.status,
        baseScore: null,
        adapterScore: null,
        delta: target.mean,
        unit: "normalized-delta",
        pairCount: target.pairCount,
        confidenceInterval: target.interval,
        minimumGain: target.threshold,
      },
      retention: {
        label: retention.metric,
        status: retention.status,
        baseScore: null,
        adapterScore: null,
        delta: retention.mean,
        unit: "normalized-delta",
        pairCount: retention.pairCount,
        confidenceInterval: retention.interval,
        maximumRegression: retention.threshold,
      },
    };
  }
  return adapted;
}

interface ParsedFaultClass {
  faultId: string;
  expectedSignal: string;
  severity: IssueSeverity;
  caseCount: number;
  detectedCount: number;
  recall: number;
}

function parseFaultClasses(value: unknown, label: string): ParsedFaultClass[] {
  return asBoundedArray(value, label, 90).map((entry, index) => {
    const faultLabel = `${label}[${index}]`;
    const fault = asRecord(entry, faultLabel);
    const caseCount = asNonNegativeInteger(
      fault.case_count,
      `${faultLabel}.case_count`,
    );
    if (caseCount < 1) {
      throw new RangeError(`${faultLabel}.case_count must be at least 1.`);
    }
    const detectedCount = asNonNegativeInteger(
      fault.detected_count,
      `${faultLabel}.detected_count`,
    );
    if (detectedCount > caseCount) {
      throw new RangeError(
        `${faultLabel}.detected_count cannot exceed case_count.`,
      );
    }
    const recall = asFraction(fault.recall, `${faultLabel}.recall`);
    if (Math.abs(recall - detectedCount / caseCount) > 1e-9) {
      throw new RangeError(`${faultLabel}.recall must match aggregate counts.`);
    }
    return {
      faultId: asString(fault.fault_id, `${faultLabel}.fault_id`, 120),
      expectedSignal: asString(
        fault.expected_signal,
        `${faultLabel}.expected_signal`,
        120,
      ),
      severity: asEnum(
        fault.severity,
        `${faultLabel}.severity`,
        ISSUE_SEVERITIES,
      ),
      caseCount,
      detectedCount,
      recall,
    };
  });
}

function parseDevelopmentBenchmarkArtifact(
  report: Record<string, unknown>,
): SftGuardReport {
  const label = "development benchmark artifact";
  if (asBoolean(report.development_only, `${label}.development_only`) !== true) {
    throw new RangeError(`${label}.development_only must be true.`);
  }
  const status = asEnum(report.status, `${label}.status`, ["PASS", "FAIL"] as const);
  const gates = asRecord(report.gates, `${label}.gates`);
  const gateKeys = [
    "critical_fault_recall_100_percent",
    "macro_recall_at_least_90_percent",
    "clean_false_positive_rate_at_most_10_percent",
    "expected_and_observed_primary_recorded",
    "in_process_byte_reproducible",
    "raw_synthetic_text_absent",
  ] as const;
  const parsedGates = new Map(
    gateKeys.map((key) => [
      key,
      asBoolean(gates[key], `${label}.gates.${key}`),
    ]),
  );
  const allGatesPassed = asBoolean(
    report.all_development_gates_passed,
    `${label}.all_development_gates_passed`,
  );
  if (allGatesPassed !== [...parsedGates.values()].every(Boolean)) {
    throw new RangeError(
      `${label}.all_development_gates_passed must match the declared gates.`,
    );
  }
  if ((status === "PASS") !== allGatesPassed) {
    throw new RangeError(`${label}.status must match the development gates.`);
  }
  const provenance = parseCoreMetadata(
    report,
    label,
    parsedGates.get("in_process_byte_reproducible") ?? null,
  );

  const seedRange = asRecord(report.seed_range, `${label}.seed_range`);
  asNonNegativeInteger(seedRange.first, `${label}.seed_range.first`);
  asNonNegativeInteger(seedRange.last, `${label}.seed_range.last`);
  const seedCount = asNonNegativeInteger(
    seedRange.count,
    `${label}.seed_range.count`,
  );
  if (seedCount < 1) {
    throw new RangeError(`${label}.seed_range.count must be at least 1.`);
  }

  const faults = parseFaultClasses(report.per_fault, `${label}.per_fault`);
  const faultCount = asNonNegativeInteger(
    report.fault_count,
    `${label}.fault_count`,
  );
  if (faultCount !== faults.length) {
    throw new RangeError(`${label}.fault_count must match per_fault length.`);
  }

  const summary = asRecord(report.summary, `${label}.summary`);
  const caseCount = asNonNegativeInteger(
    summary.case_count,
    `${label}.summary.case_count`,
  );
  const cleanControlCount = asNonNegativeInteger(
    summary.clean_control_count,
    `${label}.summary.clean_control_count`,
  );
  const cleanFalsePositiveCount = asNonNegativeInteger(
    summary.clean_false_positive_count,
    `${label}.summary.clean_false_positive_count`,
  );
  if (cleanFalsePositiveCount > cleanControlCount) {
    throw new RangeError(
      `${label}.summary.clean_false_positive_count cannot exceed clean_control_count.`,
    );
  }
  if (
    caseCount !==
    cleanControlCount + faults.reduce((total, fault) => total + fault.caseCount, 0)
  ) {
    throw new RangeError(
      `${label}.summary.case_count must match clean and injected aggregate counts.`,
    );
  }
  const cleanFalsePositiveRate = asFraction(
    summary.clean_false_positive_rate,
    `${label}.summary.clean_false_positive_rate`,
  );
  if (
    cleanControlCount > 0 &&
    Math.abs(cleanFalsePositiveRate - cleanFalsePositiveCount / cleanControlCount) >
      1e-9
  ) {
    throw new RangeError(
      `${label}.summary.clean_false_positive_rate must match aggregate counts.`,
    );
  }
  const macroRecall = asFraction(
    summary.macro_recall,
    `${label}.summary.macro_recall`,
  );
  const calculatedMacro =
    faults.length === 0
      ? 0
      : faults.reduce((total, fault) => total + fault.recall, 0) / faults.length;
  if (Math.abs(macroRecall - calculatedMacro) > 1e-9) {
    throw new RangeError(`${label}.summary.macro_recall must match per_fault recall.`);
  }

  const criticalFaults = faults.filter((fault) => fault.severity === "critical");
  const criticalRecall =
    criticalFaults.length === 0
      ? 0
      : Math.min(...criticalFaults.map((fault) => fault.recall));
  const issues: ReportIssue[] = faults.map((fault, index) => ({
    id: `fault-class-${index + 1}`,
    category: "Fault detection",
    severity: fault.severity,
    outcome: fault.detectedCount === fault.caseCount ? "PASS" : "FAIL",
    count: fault.caseCount,
    title: humanizeIdentifier(fault.faultId),
    detail: `Expected signal ${fault.expectedSignal}; detected ${fault.detectedCount} of ${fault.caseCount} aggregate synthetic cases (${(fault.recall * 100).toFixed(1)}% recall).`,
  }));
  for (const [key, passed] of parsedGates) {
    if (!passed) {
      issues.push({
        id: `development-gate-${key}`,
        category: "Development gate",
        severity: key === "critical_fault_recall_100_percent" ? "critical" : "error",
        outcome: "FAIL",
        count: 1,
        title: humanizeIdentifier(key),
        detail: "This aggregate development-only gate was reported as false.",
      });
    }
  }

  return {
    schemaVersion: REPORT_SCHEMA_VERSION,
    reportType: "fault-matrix",
    reportId: `core-benchmark-${provenance.artifactSha256.slice(0, 12)}`,
    title: "Development fault-injection matrix",
    generatedAt: null,
    status,
    summary: `The development-only benchmark declared ${status} across ${caseCount} synthetic cases and ${faultCount} known fault classes.`,
    faultCoverage: {
      expectedFaultClasses: faultCount,
      detectedFaultClasses: faults.filter(
        (fault) => fault.detectedCount === fault.caseCount,
      ).length,
      criticalRecallPercent: criticalRecall * 100,
      macroRecallPercent: macroRecall * 100,
      cleanFalsePositiveRatePercent: cleanFalsePositiveRate * 100,
      carryForward: allGatesPassed,
    },
    issues,
    provenance,
    boundaries: {
      claim: [
        "This is a development-only synthetic benchmark of known SFTGuard checks.",
        "It is not a confirmatory benchmark and does not demonstrate coverage of unknown real-world faults.",
      ],
      privacy: [
        "Only per-fault aggregate counts, recall, and gate results are rendered.",
        "The cases array and any raw synthetic case content are discarded by the adapter.",
      ],
    },
  };
}

function parseConfirmatoryFaultMatrixArtifact(
  report: Record<string, unknown>,
): SftGuardReport {
  const label = "confirmatory fault-matrix artifact";
  const status = asEnum(report.status, `${label}.status`, ["PASS", "FAIL"] as const);
  asRecord(report.protocol, `${label}.protocol`);
  asBoundedArray(report.cases, `${label}.cases`, 100_000);

  const gates = asRecord(report.gates, `${label}.gates`);
  const gateKeys = [
    "clean_false_positive_rate_at_most_10_percent",
    "critical_fault_recall_100_percent",
    "expected_and_observed_primary_recorded",
    "fresh_process_byte_reproducible",
    "macro_recall_at_least_90_percent",
    "raw_synthetic_text_absent",
  ] as const;
  const parsedGates = new Map(
    gateKeys.map((key) => [
      key,
      asBoolean(gates[key], `${label}.gates.${key}`),
    ]),
  );
  const carryForward = asBoolean(
    report.carry_forward,
    `${label}.carry_forward`,
  );
  if (carryForward !== [...parsedGates.values()].every(Boolean)) {
    throw new RangeError(`${label}.carry_forward must match the declared gates.`);
  }
  if ((status === "PASS") !== carryForward) {
    throw new RangeError(`${label}.status must match carry_forward.`);
  }

  const artifactProvenance = asRecord(
    report.provenance,
    `${label}.provenance`,
  );
  const pythonImplementation = asString(
    artifactProvenance.python_implementation,
    `${label}.provenance.python_implementation`,
    80,
  );
  const pythonVersion = asString(
    artifactProvenance.python_version,
    `${label}.provenance.python_version`,
    40,
  );
  const baseProvenance = parseCoreMetadata(
    report,
    label,
    parsedGates.get("fresh_process_byte_reproducible") ?? null,
  );
  const provenance: ReportProvenance = {
    ...baseProvenance,
    protocolCommit: asCommit(
      artifactProvenance.protocol_git_commit,
      `${label}.provenance.protocol_git_commit`,
    ),
    implementationCommit: asCommit(
      artifactProvenance.implementation_git_commit,
      `${label}.provenance.implementation_git_commit`,
    ),
    runtime: `${pythonImplementation} ${pythonVersion}`,
  };

  const faults = parseFaultClasses(report.per_fault, `${label}.per_fault`);
  if (faults.length === 0) {
    throw new RangeError(`${label}.per_fault must contain at least one entry.`);
  }
  const summary = asRecord(report.summary, `${label}.summary`);
  const caseCount = asNonNegativeInteger(
    summary.case_count,
    `${label}.summary.case_count`,
  );
  const cleanControlCount = asNonNegativeInteger(
    summary.clean_control_count,
    `${label}.summary.clean_control_count`,
  );
  const faultCaseCount = asNonNegativeInteger(
    summary.fault_case_count,
    `${label}.summary.fault_case_count`,
  );
  const cleanFalsePositiveCount = asNonNegativeInteger(
    summary.clean_false_positive_count,
    `${label}.summary.clean_false_positive_count`,
  );
  if (cleanFalsePositiveCount > cleanControlCount) {
    throw new RangeError(
      `${label}.summary.clean_false_positive_count cannot exceed clean_control_count.`,
    );
  }
  if (caseCount !== cleanControlCount + faultCaseCount) {
    throw new RangeError(
      `${label}.summary.case_count must equal clean and fault case counts.`,
    );
  }
  if (
    faultCaseCount !==
    faults.reduce((total, fault) => total + fault.caseCount, 0)
  ) {
    throw new RangeError(
      `${label}.summary.fault_case_count must match per_fault aggregate counts.`,
    );
  }
  const cleanFalsePositiveRate = asFraction(
    summary.clean_false_positive_rate,
    `${label}.summary.clean_false_positive_rate`,
  );
  if (
    cleanControlCount > 0 &&
    Math.abs(cleanFalsePositiveRate - cleanFalsePositiveCount / cleanControlCount) >
      1e-9
  ) {
    throw new RangeError(
      `${label}.summary.clean_false_positive_rate must match aggregate counts.`,
    );
  }
  const macroRecall = asFraction(
    summary.macro_recall,
    `${label}.summary.macro_recall`,
  );
  const calculatedMacro =
    faults.reduce((total, fault) => total + fault.recall, 0) / faults.length;
  if (Math.abs(macroRecall - calculatedMacro) > 1e-9) {
    throw new RangeError(`${label}.summary.macro_recall must match per_fault recall.`);
  }

  const criticalFaults = faults.filter((fault) => fault.severity === "critical");
  const criticalRecall =
    criticalFaults.length === 0
      ? 0
      : Math.min(...criticalFaults.map((fault) => fault.recall));
  const issues: ReportIssue[] = faults.map((fault, index) => ({
    id: `confirmatory-fault-class-${index + 1}`,
    category: "Confirmatory fault detection",
    severity: fault.severity,
    outcome: fault.detectedCount === fault.caseCount ? "PASS" : "FAIL",
    count: fault.caseCount,
    title: humanizeIdentifier(fault.faultId),
    detail: `Expected signal ${fault.expectedSignal}; detected ${fault.detectedCount} of ${fault.caseCount} aggregate confirmatory cases (${(fault.recall * 100).toFixed(1)}% recall).`,
  }));
  for (const [key, passed] of parsedGates) {
    if (!passed) {
      issues.push({
        id: `confirmatory-gate-${key}`,
        category: "Confirmatory gate",
        severity: key === "critical_fault_recall_100_percent" ? "critical" : "error",
        outcome: "FAIL",
        count: 1,
        title: humanizeIdentifier(key),
        detail: "This aggregate confirmatory gate was reported as false.",
      });
    }
  }

  return {
    schemaVersion: REPORT_SCHEMA_VERSION,
    reportType: "fault-matrix",
    reportId: `confirmatory-matrix-${provenance.artifactSha256.slice(0, 12)}`,
    title: "Confirmatory fault-injection matrix",
    generatedAt: null,
    status,
    summary: `The confirmatory matrix declared ${status} across ${caseCount} synthetic cases and ${faults.length} known fault classes.`,
    faultCoverage: {
      expectedFaultClasses: faults.length,
      detectedFaultClasses: faults.filter(
        (fault) => fault.detectedCount === fault.caseCount,
      ).length,
      criticalRecallPercent: criticalRecall * 100,
      macroRecallPercent: macroRecall * 100,
      cleanFalsePositiveRatePercent: cleanFalsePositiveRate * 100,
      carryForward,
    },
    issues,
    provenance,
    boundaries: {
      claim: [
        "The result is scoped to the declared frozen protocol, provenance, and known fault matrix.",
        "It does not establish coverage of unknown faults, model quality, or model safety.",
      ],
      privacy: [
        "Only summary, per-fault aggregates, gates, and declared provenance are rendered.",
        "All per-case fields and any private synthetic content are discarded by the adapter.",
      ],
    },
  };
}

export function parseReport(value: unknown): SftGuardReport {
  const report = asRecord(value, "report");
  if ("schemaVersion" in report) {
    return parseEnvelopeReport(value);
  }
  const schemaVersion = asString(report.schema_version, "schema_version", 100);
  if (schemaVersion === AUDIT_SCHEMA_VERSION) {
    return parseAuditArtifact(report);
  }
  if (schemaVersion === REGRESSION_SCHEMA_VERSION) {
    return parseRegressionArtifact(report);
  }
  if (schemaVersion === DEVELOPMENT_BENCHMARK_SCHEMA_VERSION) {
    return parseDevelopmentBenchmarkArtifact(report);
  }
  if (schemaVersion === CONFIRMATORY_FAULT_MATRIX_SCHEMA_VERSION) {
    return parseConfirmatoryFaultMatrixArtifact(report);
  }
  throw new RangeError(
    `Unsupported SFTGuard report schema: ${schemaVersion}.`,
  );
}

export function parseReportText(text: string): SftGuardReport {
  if (new TextEncoder().encode(text).byteLength > MAX_REPORT_BYTES) {
    throw new RangeError("Report exceeds the 2 MB local import limit.");
  }
  let value: unknown;
  try {
    value = JSON.parse(text) as unknown;
  } catch {
    throw new SyntaxError("The selected file is not valid JSON.");
  }
  return parseReport(value);
}

export function reportTypeLabel(reportType: ReportType): string {
  if (reportType === "fault-matrix") return "Fault matrix";
  if (reportType === "regression") return "Regression card";
  return "Dataset audit";
}
