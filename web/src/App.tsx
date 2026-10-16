import {
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type CSSProperties,
  type ReactNode,
} from "react";
import {
  MAX_REPORT_BYTES,
  parseReportText,
  reportTypeLabel,
  type ReportIssue,
  type ReportStatus,
  type ScoreContract,
  type SftGuardReport,
} from "./reportSchema";
import { SAMPLE_REPORTS, type ReportSource } from "./sampleReports";

const STATUS_COPY: Record<
  ReportStatus,
  { eyebrow: string; action: string; explanation: string }
> = {
  PASS: {
    eyebrow: "Release gate cleared",
    action: "Proceed within this evidence contract",
    explanation: "Every required check represented by this report passed.",
  },
  FAIL: {
    eyebrow: "Release gate blocked",
    action: "Resolve failures before release",
    explanation: "At least one required check violated its declared gate.",
  },
  ABSTAIN: {
    eyebrow: "Decision withheld",
    action: "Supply the missing evidence",
    explanation: "The harness could not make a trustworthy pass/fail decision.",
  },
};

function reportSourceKey(source: ReportSource): string {
  return `${source.origin}:${source.report.reportId}`;
}

function signedPoints(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "\u2212" : "";
  return `${sign}${Math.abs(value).toFixed(1)} pp`;
}

function signedMetric(
  value: number,
  unit: ScoreContract["unit"],
): string {
  if (unit === "percentage-points") return signedPoints(value);
  const sign = value > 0 ? "+" : value < 0 ? "\u2212" : "";
  return `${sign}${Math.abs(value).toFixed(3)} normalized`;
}

function compactNumber(value: number | null): string {
  if (value === null) return "Not verified";
  return new Intl.NumberFormat("en", { notation: "compact" }).format(value);
}

function displayDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(new Date(value));
}

function shortHash(hash: string): string {
  return `${hash.slice(0, 10)}\u2026${hash.slice(-8)}`;
}

function StatusBadge({ status, compact = false }: { status: ReportStatus; compact?: boolean }) {
  return (
    <span className={`status-badge status-${status.toLowerCase()} ${compact ? "is-compact" : ""}`}>
      <span className="status-dot" aria-hidden="true" />
      {status}
    </span>
  );
}

function SectionHeading({
  number,
  title,
  detail,
}: {
  number: string;
  title: string;
  detail: string;
}) {
  return (
    <div className="section-heading">
      <span className="section-number" aria-hidden="true">
        {number}
      </span>
      <div>
        <h2>{title}</h2>
        <p>{detail}</p>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  context,
  tone = "neutral",
  children,
}: {
  label: string;
  value: string;
  context: string;
  tone?: "positive" | "negative" | "caution" | "neutral";
  children?: ReactNode;
}) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
      <p className="metric-context">{context}</p>
      {children}
    </article>
  );
}

function ScoreEvidence({ score, label }: { score: ScoreContract; label: string }) {
  if (score.baseScore !== null && score.adapterScore !== null) {
    return (
      <div className="score-pair" aria-label={`${label} base and adapter scores`}>
        <span>Base {score.baseScore.toFixed(1)}</span>
        <span className="score-line" aria-hidden="true" />
        <span>Adapter {score.adapterScore.toFixed(1)}</span>
      </div>
    );
  }
  if (score.confidenceInterval) {
    return (
      <div className="score-pair" aria-label={`${label} aggregate evidence`}>
        <span>Pairs {score.pairCount ?? "unavailable"}</span>
        <span className="score-line" aria-hidden="true" />
        <span>
          Interval {score.confidenceInterval.low.toFixed(3)} to{" "}
          {score.confidenceInterval.high.toFixed(3)}
        </span>
      </div>
    );
  }
  return null;
}

function RegressionContract({ report }: { report: SftGuardReport }) {
  const regression = report.regression;
  if (!regression) {
    return (
      <div className="metric-grid two-up">
        <MetricCard
          label="Target gain"
          value="—"
          context={`Not measured by this ${reportTypeLabel(report.reportType).toLowerCase()}.`}
        />
        <MetricCard
          label="Retention regression"
          value="—"
          context="No base-versus-adapter retention contract is present."
        />
      </div>
    );
  }

  const targetPassed = regression.target.status === "PASS";
  const retentionPassed = regression.retention.status === "PASS";

  return (
    <div className="metric-grid two-up">
      <MetricCard
        label="Target gain"
        value={signedMetric(regression.target.delta, regression.target.unit)}
        context={`${regression.target.label} · minimum ${signedMetric(regression.target.minimumGain, regression.target.unit)}`}
        tone={targetPassed ? "positive" : "negative"}
      >
        <ScoreEvidence score={regression.target} label="Target" />
      </MetricCard>
      <MetricCard
        label="Retention regression"
        value={signedMetric(regression.retention.delta, regression.retention.unit)}
        context={`${regression.retention.label} · floor ${signedMetric(-regression.retention.maximumRegression, regression.retention.unit)}`}
        tone={retentionPassed ? "positive" : "negative"}
      >
        <ScoreEvidence score={regression.retention} label="Retention" />
      </MetricCard>
    </div>
  );
}

function AuditContract({ report }: { report: SftGuardReport }) {
  if (!report.audit) return null;
  const audit = report.audit;
  return (
    <div className="metric-grid three-up supplemental-metrics">
      <MetricCard
        label="Records scanned"
        value={compactNumber(audit.recordsScanned)}
        context="Bounded local JSONL scan"
      />
      <MetricCard
        label="Required checks"
        value={`${audit.checksPassed} / ${audit.checksTotal}`}
        context="Completed without converting abstention"
        tone={audit.checksPassed === audit.checksTotal ? "positive" : "caution"}
      />
      <MetricCard
        label="Supervised tokens"
        value={compactNumber(audit.supervisedTokens)}
        context={audit.supervisedTokens === null ? "Aggregate not present in artifact" : "Aggregate count only"}
        tone={audit.supervisedTokens === null ? "caution" : "neutral"}
      />
    </div>
  );
}

function FaultCoveragePanel({ report }: { report: SftGuardReport }) {
  const coverage = report.faultCoverage;
  if (!coverage) {
    return (
      <div className="empty-panel">
        <p className="empty-kicker">Not part of this artifact</p>
        <h3>No fault matrix attached</h3>
        <p>
          Open the checked-in fault-matrix sample or import a compatible report
          to inspect detection coverage and clean-control behavior.
        </p>
      </div>
    );
  }

  const coveragePercent =
    coverage.expectedFaultClasses === 0
      ? 0
      : (coverage.detectedFaultClasses / coverage.expectedFaultClasses) * 100;
  return (
    <div className="coverage-layout">
      <div className="coverage-ring" style={{ "--coverage": `${coveragePercent}%` } as CSSProperties}>
        <div>
          <strong>{coverage.detectedFaultClasses}</strong>
          <span>of {coverage.expectedFaultClasses}</span>
        </div>
      </div>
      <div className="coverage-copy">
        <p className="coverage-result">
          {coverage.carryForward ? "Carry-forward allowed" : "Carry-forward blocked"}
        </p>
        <p>
          This reports deterministic synthetic coverage of SFTGuard’s own
          checks—not coverage of unknown real-world faults.
        </p>
        <div className="coverage-bars">
          <CoverageBar label="Critical recall" value={coverage.criticalRecallPercent} target="100% required" />
          <CoverageBar label="Macro recall" value={coverage.macroRecallPercent} target="90% minimum" />
          <CoverageBar
            label="Clean false positives"
            value={coverage.cleanFalsePositiveRatePercent}
            target="10% maximum"
            inverse
          />
        </div>
      </div>
    </div>
  );
}

function CoverageBar({
  label,
  value,
  target,
  inverse = false,
}: {
  label: string;
  value: number;
  target: string;
  inverse?: boolean;
}) {
  return (
    <div className="coverage-row">
      <div>
        <span>{label}</span>
        <span className="coverage-target">{target}</span>
      </div>
      <div className="coverage-value">{value.toFixed(1)}%</div>
      <div
        className={`bar-track ${inverse ? "is-inverse" : ""}`}
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
      >
        <span style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
      </div>
    </div>
  );
}

function IssueSummary({ issues }: { issues: ReportIssue[] }) {
  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const issue of issues) {
      counts.set(issue.category, (counts.get(issue.category) ?? 0) + issue.count);
    }
    return [...counts.entries()].sort((left, right) => right[1] - left[1]);
  }, [issues]);

  if (issues.length === 0) {
    return (
      <div className="empty-panel compact-empty">
        <h3>No reported issues</h3>
        <p>The artifact contains no issue records.</p>
      </div>
    );
  }

  return (
    <>
      <div className="category-strip" aria-label="Issue categories">
        {categoryCounts.map(([category, count]) => (
          <span key={category}>
            {category} <strong>{count}</strong>
          </span>
        ))}
      </div>
      <div className="table-shell">
        <table>
          <caption className="sr-only">Reported SFTGuard issues</caption>
          <thead>
            <tr>
              <th scope="col">Signal</th>
              <th scope="col">Severity</th>
              <th scope="col">Outcome</th>
              <th scope="col" className="number-cell">Count</th>
            </tr>
          </thead>
          <tbody>
            {issues.map((issue) => (
              <tr key={issue.id}>
                <td>
                  <div className="issue-title">{issue.title}</div>
                  <code>{issue.id}</code>
                  <p>{issue.detail}</p>
                </td>
                <td>
                  <span className={`severity severity-${issue.severity}`}>
                    {issue.severity}
                  </span>
                </td>
                <td>
                  <StatusBadge status={issue.outcome} compact />
                </td>
                <td className="number-cell">{issue.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function ProvenancePanel({ report }: { report: SftGuardReport }) {
  const provenance = report.provenance;
  const values: Array<{
    label: string;
    value: string | null;
    isHash?: boolean;
  }> = [
    { label: "Tool version", value: provenance.toolVersion },
    { label: "Protocol commit", value: provenance.protocolCommit, isHash: true },
    {
      label: "Implementation",
      value: provenance.implementationCommit,
      isHash: true,
    },
    { label: "Input SHA-256", value: provenance.inputSha256, isHash: true },
    {
      label: "Declared artifact SHA-256",
      value: provenance.artifactSha256,
      isHash: true,
    },
    {
      label: "Digest verification",
      value:
        provenance.integrityStatus === "verified"
          ? "Verified"
          : provenance.integrityStatus === "mismatch"
            ? "Mismatch"
            : "Unverified — digest not recomputed",
    },
    { label: "Runtime", value: provenance.runtime },
  ];
  const replayTone =
    provenance.deterministicReplay === null
      ? "replay-unknown"
      : provenance.deterministicReplay
        ? "replay-pass"
        : "replay-fail";
  const replayTitle =
    provenance.deterministicReplay === null
      ? "Unavailable"
      : provenance.deterministicReplay
        ? "Matched"
        : "Not matched";
  const replayDetail =
    provenance.deterministicReplay === null
      ? "The artifact does not declare a replay result"
      : provenance.deterministicReplay
        ? "Canonical payload reproduced"
        : "Reproduction claim is blocked";
  return (
    <div className="provenance-grid">
      <div className={`replay-card ${replayTone}`}>
        <p>Deterministic replay</p>
        <strong>{replayTitle}</strong>
        <span>{replayDetail}</span>
      </div>
      <dl className="provenance-list">
        {values.map(({ label, value, isHash = false }) => {
          return (
            <div key={label}>
              <dt>{label}</dt>
              <dd
                title={isHash && value !== null ? value : undefined}
                className={isHash && value !== null ? "hash-value" : undefined}
              >
                {value === null
                  ? "Unavailable in artifact"
                  : isHash
                    ? shortHash(value)
                    : value}
              </dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

function BoundaryPanel({ report }: { report: SftGuardReport }) {
  return (
    <div className="boundary-grid">
      <article className="boundary-card claim-boundary">
        <p className="boundary-label">Claim boundary</p>
        <h3>Evidence, not certification</h3>
        <ul>
          {report.boundaries.claim.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </article>
      <article className="boundary-card privacy-boundary">
        <p className="boundary-label">Privacy boundary</p>
        <h3>Local viewing, narrow display</h3>
        <ul>
          {report.boundaries.privacy.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </article>
    </div>
  );
}

export default function App() {
  const [selectedKey, setSelectedKey] = useState(
    reportSourceKey(SAMPLE_REPORTS[0]),
  );
  const [importedReport, setImportedReport] = useState<ReportSource | null>(null);
  const [importMessage, setImportMessage] = useState<string>(
    "Choose a compatible JSON report. The file never leaves this browser tab.",
  );
  const [importError, setImportError] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reports = importedReport
    ? [importedReport, ...SAMPLE_REPORTS]
    : SAMPLE_REPORTS;
  const activeSource =
    reports.find((source) => reportSourceKey(source) === selectedKey) ?? reports[0];
  const report = activeSource.report;
  const statusCopy = STATUS_COPY[report.status];

  async function handleImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      if (file.size > MAX_REPORT_BYTES) {
        throw new RangeError("Report exceeds the 2 MB local import limit.");
      }
      const parsed = parseReportText(await file.text());
      const source: ReportSource = {
        report: parsed,
        origin: "local import",
        sourceLabel: file.name,
      };
      setImportedReport(source);
      setSelectedKey(reportSourceKey(source));
      setImportError(false);
      setImportMessage(`${file.name} loaded locally. Nothing was uploaded or stored.`);
    } catch (error) {
      setImportError(true);
      setImportMessage(
        error instanceof Error ? error.message : "The report could not be read.",
      );
    } finally {
      event.target.value = "";
    }
  }

  function removeImportedReport() {
    setImportedReport(null);
    setSelectedKey(reportSourceKey(SAMPLE_REPORTS[0]));
    setImportError(false);
    setImportMessage("Local import cleared from memory. Checked-in samples remain available.");
    fileInputRef.current?.focus();
  }

  return (
    <>
      <a className="skip-link" href="#report-main">
        Skip to report
      </a>
      <div className="app-shell">
        <header className="topbar">
          <a className="brand" href="#top" aria-label="SFTGuard report viewer home">
            <span className="brand-mark" aria-hidden="true">SG</span>
            <span>
              <strong>SFTGuard</strong>
              <small>Local report viewer</small>
            </span>
          </a>
          <div className="local-indicator">
            <span aria-hidden="true" />
            Browser-local · no network path
          </div>
        </header>

        <div className="workspace" id="top">
          <aside className="report-rail" aria-label="Available reports">
            <div className="rail-heading">
              <p>Evidence library</p>
              <span>{reports.length.toString().padStart(2, "0")}</span>
            </div>
            <nav className="report-list">
              {reports.map((source) => (
                <button
                  type="button"
                  key={`${source.origin}-${source.report.reportId}`}
                  className={reportSourceKey(source) === selectedKey ? "is-active" : undefined}
                  aria-current={reportSourceKey(source) === selectedKey ? "page" : undefined}
                  onClick={() => setSelectedKey(reportSourceKey(source))}
                >
                  <span className="report-list-topline">
                    <span>{reportTypeLabel(source.report.reportType)}</span>
                    <StatusBadge status={source.report.status} compact />
                  </span>
                  <strong>{source.report.title}</strong>
                  <small>
                    {source.origin === "local import"
                      ? "Local import"
                      : source.origin === "checked-in evidence"
                        ? "Confirmatory evidence"
                        : "Illustrative sample"}
                  </small>
                </button>
              ))}
            </nav>

            <div className="import-card">
              <p className="import-eyebrow">Inspect your artifact</p>
              <h2>Open report JSON</h2>
              <p>
                Nothing is uploaded. Reports are parsed in memory with no
                analytics, storage, or external request.
              </p>
              <button
                type="button"
                className="import-button"
                onClick={() => fileInputRef.current?.click()}
              >
                Choose local file
              </button>
              <input
                ref={fileInputRef}
                className="visually-hidden-input"
                id="report-file"
                type="file"
                tabIndex={-1}
                aria-label="Choose SFTGuard report JSON"
                accept=".json,application/json"
                onChange={handleImport}
              />
              <p
                className={`import-message ${importError ? "is-error" : ""}`}
                role={importError ? "alert" : "status"}
                aria-live="polite"
              >
                {importMessage}
              </p>
              {importedReport ? (
                <button type="button" className="clear-import" onClick={removeImportedReport}>
                  Clear local import
                </button>
              ) : null}
            </div>
          </aside>

          <main id="report-main" className="report-main" tabIndex={-1}>
            <section className={`decision-hero hero-${report.status.toLowerCase()}`} aria-labelledby="report-title">
              <div className="decision-copy">
                <div className="hero-meta">
                  <StatusBadge status={report.status} />
                  <span>{reportTypeLabel(report.reportType)}</span>
                  <span>{activeSource.origin}</span>
                  <span>report-declared decision</span>
                </div>
                <p className="hero-eyebrow">{statusCopy.eyebrow}</p>
                <h1 id="report-title">{report.title}</h1>
                <p className="hero-summary">{report.summary}</p>
                <p className="hero-action">{statusCopy.action}</p>
              </div>
              <div className="decision-seal" aria-label={`Decision ${report.status}`}>
                <span>{report.status.slice(0, 1)}</span>
                <div>
                  <strong>{report.status}</strong>
                  <small>{statusCopy.explanation}</small>
                </div>
              </div>
              <div className="hero-footer">
                <span>Report <code>{report.reportId}</code></span>
                <span>
                  {report.generatedAt
                    ? `Generated ${displayDate(report.generatedAt)}`
                    : "Generated time unavailable in artifact"}
                </span>
              </div>
            </section>

            <section className="report-section" aria-labelledby="contract-heading">
              <SectionHeading
                number="01"
                title="Evaluation contract"
                detail="Target improvement and retained capability are separate gates."
              />
              <div id="contract-heading" className="sr-only">Evaluation contract results</div>
              <RegressionContract report={report} />
              <AuditContract report={report} />
            </section>

            <section className="report-section" aria-labelledby="issues-heading">
              <SectionHeading
                number="02"
                title="Signals and issue categories"
                detail="Only aggregate categories, counts, and bounded explanations are rendered."
              />
              <div id="issues-heading" className="sr-only">Signals and issue categories</div>
              <IssueSummary issues={report.issues} />
            </section>

            <section className="report-section" aria-labelledby="coverage-heading">
              <SectionHeading
                number="03"
                title="Fault coverage"
                detail="Synthetic validation of known checks, kept separate from adapter quality."
              />
              <div id="coverage-heading" className="sr-only">Fault coverage results</div>
              <FaultCoveragePanel report={report} />
            </section>

            <section className="report-section" aria-labelledby="provenance-heading">
              <SectionHeading
                number="04"
                title="Provenance"
                detail="Declared content addresses and available metadata are shown without implying independent attestation."
              />
              <div id="provenance-heading" className="sr-only">Artifact provenance</div>
              <ProvenancePanel report={report} />
            </section>

            <section className="report-section boundaries-section" aria-labelledby="boundaries-heading">
              <SectionHeading
                number="05"
                title="Boundaries"
                detail="What this report can support—and what stays outside its evidence."
              />
              <div id="boundaries-heading" className="sr-only">Claim and privacy boundaries</div>
              <BoundaryPanel report={report} />
            </section>

            <footer className="report-footer">
              <span>SFTGuard v0.1 viewer</span>
              <p>
                This viewer displays supplied evidence. It does not train a
                model, certify safety, prove dataset quality, or detect unknown
                failures. It validates the display schema but does not
                recompute or independently attest declared hashes. Imported JSON remains in
                this tab and is discarded on refresh.
              </p>
            </footer>
          </main>
        </div>
      </div>
    </>
  );
}
