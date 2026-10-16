import auditJson from "./data/sample-audit.json";
import faultJson from "./data/sample-fault.json";
import regressionJson from "./data/sample-regression.json";
import confirmatoryJson from "../../evidence/v0.1.0-confirmatory.json";
import { parseReport, type SftGuardReport } from "./reportSchema";

export interface ReportSource {
  report: SftGuardReport;
  origin: "checked-in evidence" | "checked-in sample" | "local import";
  sourceLabel: string;
}

export const SAMPLE_REPORTS: ReportSource[] = [
  {
    report: parseReport(confirmatoryJson),
    origin: "checked-in evidence",
    sourceLabel: "v0.1 confirmatory evidence",
  },
  {
    report: parseReport(regressionJson),
    origin: "checked-in sample",
    sourceLabel: "Regression sample",
  },
  {
    report: parseReport(faultJson),
    origin: "checked-in sample",
    sourceLabel: "Fault-matrix sample",
  },
  {
    report: parseReport(auditJson),
    origin: "checked-in sample",
    sourceLabel: "Audit sample",
  },
];
