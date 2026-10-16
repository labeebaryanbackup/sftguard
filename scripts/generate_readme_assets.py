"""Render README evidence graphics from the sealed confirmatory artifact.

Run without arguments to update the SVG, or use ``--check`` in CI to fail
when the checked-in image no longer matches the checked-in evidence.
"""

# SVG elements remain one-per-line so generated diffs stay readable.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "v0.1.0-confirmatory.json"
OUTPUT = ROOT / "docs" / "assets" / "sftguard-confirmatory-evidence.svg"


def _load_evidence() -> dict[str, Any]:
    data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    if data.get("schema_version") != "sftguard.confirmatory-fault-matrix.v1":
        raise ValueError("unsupported confirmatory evidence schema")

    summary = data.get("summary")
    faults = data.get("per_fault")
    cases = data.get("cases")
    gates = data.get("gates")
    seed_range = data.get("protocol", {}).get("seed_range")
    if not isinstance(summary, dict) or not isinstance(faults, list):
        raise ValueError("confirmatory evidence is missing its summary or fault rows")
    if (
        not faults
        or not isinstance(cases, list)
        or not isinstance(gates, dict)
        or not isinstance(seed_range, dict)
    ):
        raise ValueError("confirmatory evidence is missing graphable protocol data")

    for fault in faults:
        if not isinstance(fault, dict):
            raise ValueError("invalid per-fault row")
        total = fault.get("case_count")
        detected = fault.get("detected_count")
        if not isinstance(total, int) or not isinstance(detected, int):
            raise ValueError("fault counts must be integers")
        if total <= 0 or detected < 0 or detected > total:
            raise ValueError("fault counts are outside their valid range")
    return data


def _svg(data: dict[str, Any]) -> str:
    summary = data["summary"]
    faults = data["per_fault"]
    cases = data["cases"]
    gates = data["gates"]
    seeds = data["protocol"]["seed_range"]
    seed_values = list(range(int(seeds["first"]), int(seeds["last"]) + 1))
    if len(seed_values) != int(seeds["count"]):
        raise ValueError("frozen seed count does not match its endpoints")

    fault_outcomes: dict[tuple[str, int], bool] = {}
    clean_outcomes: dict[int, bool] = {}
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("seed"), int):
            raise ValueError("invalid confirmatory case row")
        if case.get("kind") == "fault":
            key = (str(case.get("fault_id")), int(case["seed"]))
            if key in fault_outcomes:
                raise ValueError(f"duplicate confirmatory fault case: {key}")
            fault_outcomes[key] = case.get("primary_expectation_met") is True
        elif case.get("kind") == "clean_control":
            seed = int(case["seed"])
            if seed in clean_outcomes:
                raise ValueError(f"duplicate clean control for seed {seed}")
            clean_outcomes[seed] = bool(case.get("observed_signal_ids"))
        else:
            raise ValueError("unknown confirmatory case kind")

    detected_total = sum(row["detected_count"] for row in faults)
    fault_total = sum(row["case_count"] for row in faults)
    passed_gates = sum(value is True for value in gates.values())
    clean_total = int(summary["clean_control_count"])
    clean_false_positives = int(summary["clean_false_positive_count"])

    width = 1200
    height = 720
    row_start = 318
    row_step = 34
    dot_start = 415
    dot_span = 665

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">SFTGuard preregistered confirmatory fault matrix</title>',
        (
            '<desc id="desc">A matrix of nine synthetic fault classes across '
            f"{escape(str(seeds['count']))} frozen seeds. {detected_total} of "
            f"{fault_total} injected faults were detected, with "
            f"{clean_false_positives} false positives across {clean_total} clean controls.</desc>"
        ),
        '<rect width="1200" height="720" rx="30" fill="#f4f1e8"/>',
        '<path d="M0 0H1200V13H0Z" fill="#1d3b36"/>',
        '<g font-family="Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif">',
        '<text x="58" y="68" fill="#1d3b36" font-size="16" font-weight="700" letter-spacing="2.4">SFTGUARD / FROZEN EVIDENCE</text>',
        '<text x="58" y="125" fill="#172723" font-size="43" font-weight="750">The release gate was exercised, not assumed.</text>',
        (
            f'<text x="58" y="160" fill="#5b6863" font-size="18">Synthetic fault templates × seeds '
            f"{escape(str(seeds['first']))}–{escape(str(seeds['last']))}; "
            "every dot below is one preregistered injected case.</text>"
        ),
        '<rect x="58" y="194" width="330" height="82" rx="14" fill="#ffffff" stroke="#d7d4c9"/>',
        f'<text x="82" y="232" fill="#1d3b36" font-size="28" font-weight="760">{detected_total}/{fault_total}</text>',
        '<text x="82" y="257" fill="#65716c" font-size="15">required signals detected</text>',
        '<rect x="408" y="194" width="330" height="82" rx="14" fill="#ffffff" stroke="#d7d4c9"/>',
        f'<text x="432" y="232" fill="#1d3b36" font-size="28" font-weight="760">{clean_false_positives}/{clean_total}</text>',
        '<text x="432" y="257" fill="#65716c" font-size="15">clean-control false positives</text>',
        '<rect x="758" y="194" width="384" height="82" rx="14" fill="#1d3b36"/>',
        f'<text x="782" y="232" fill="#d8f3e7" font-size="28" font-weight="760">{passed_gates}/{len(gates)}</text>',
        '<text x="782" y="257" fill="#b8d1c8" font-size="15">frozen carry-forward gates passed</text>',
        '<text x="58" y="299" fill="#6a746f" font-size="12" font-weight="700" letter-spacing="1.4">FAULT CLASS</text>',
        (
            f'<text x="747" y="299" fill="#6a746f" font-size="12" font-weight="700" '
            f'text-anchor="middle" letter-spacing="1.2">{escape(str(seeds["count"]))} '
            f"FROZEN SEEDS ({escape(str(seeds['first']))}–{escape(str(seeds['last']))})</text>"
        ),
        '<text x="1142" y="299" fill="#6a746f" font-size="12" font-weight="700" text-anchor="end" letter-spacing="1.2">DETECTED</text>',
    ]

    severity_colours = {
        "critical": "#b7473f",
        "error": "#bd7623",
        "warning": "#8a6b2f",
    }
    for index, row in enumerate(faults):
        y = row_start + index * row_step
        total = int(row["case_count"])
        outcomes = [fault_outcomes.get((str(row["fault_id"]), seed)) for seed in seed_values]
        if any(outcome is None for outcome in outcomes) or len(outcomes) != total:
            raise ValueError(f"fault case rows do not match {row['fault_id']}")
        detected = sum(outcome is True for outcome in outcomes)
        if detected != int(row["detected_count"]):
            raise ValueError(f"per-fault summary does not match {row['fault_id']} cases")
        severity = str(row.get("severity", "unknown"))
        colour = severity_colours.get(severity, "#66736e")
        label = escape(str(row["fault_id"]))
        lines.extend(
            [
                f'<circle cx="66" cy="{y - 5}" r="5" fill="{colour}"/>',
                f'<text x="82" y="{y}" fill="#263732" font-size="14" font-weight="620">{label}</text>',
            ]
        )
        if total == 1:
            positions = [dot_start]
        else:
            positions = [dot_start + i * dot_span / (total - 1) for i in range(total)]
        for position, outcome in zip(positions, outcomes, strict=True):
            fill = "#2c8b70" if outcome else "#d9d8d0"
            lines.append(f'<circle cx="{position:.1f}" cy="{y - 5}" r="5.2" fill="{fill}"/>')
        lines.append(
            f'<text x="1142" y="{y}" fill="#1d3b36" font-size="14" font-weight="720" text-anchor="end">{detected}/{total}</text>'
        )

    clean_y = row_start + len(faults) * row_step + 12
    lines.extend(
        [
            f'<line x1="58" y1="{clean_y - 25}" x2="1142" y2="{clean_y - 25}" stroke="#d7d4c9"/>',
            f'<circle cx="66" cy="{clean_y - 5}" r="5" fill="#2c8b70"/>',
            f'<text x="82" y="{clean_y}" fill="#263732" font-size="14" font-weight="620">clean controls</text>',
        ]
    )
    if clean_total == 1:
        clean_positions = [dot_start]
    else:
        clean_positions = [dot_start + i * dot_span / (clean_total - 1) for i in range(clean_total)]
    if set(clean_outcomes) != set(seed_values):
        raise ValueError("clean-control rows do not match the frozen seed range")
    if sum(clean_outcomes.values()) != clean_false_positives:
        raise ValueError("clean-control summary does not match its case rows")
    for position, seed in zip(clean_positions, seed_values, strict=True):
        if clean_outcomes[seed]:
            lines.append(f'<circle cx="{position:.1f}" cy="{clean_y - 5}" r="5.2" fill="#b7473f"/>')
        else:
            lines.append(
                f'<circle cx="{position:.1f}" cy="{clean_y - 5}" r="5.2" fill="#f4f1e8" stroke="#2c8b70" stroke-width="1.8"/>'
            )
    lines.extend(
        [
            f'<text x="1142" y="{clean_y}" fill="#1d3b36" font-size="14" font-weight="720" text-anchor="end">{clean_false_positives}/{clean_total} FP</text>',
            '<text x="58" y="663" fill="#65716c" font-size="12" font-weight="700" letter-spacing="1.1">PROTOCOL SEVERITY</text>',
            '<circle cx="219" cy="659" r="4.8" fill="#b7473f"/>',
            '<text x="231" y="663" fill="#65716c" font-size="12">critical</text>',
            '<circle cx="295" cy="659" r="4.8" fill="#bd7623"/>',
            '<text x="307" y="663" fill="#65716c" font-size="12">error</text>',
            '<circle cx="356" cy="659" r="4.8" fill="#8a6b2f"/>',
            '<text x="368" y="663" fill="#65716c" font-size="12">warning</text>',
            '<text x="58" y="696" fill="#65716c" font-size="13">Internal detector regression • deterministic synthetic templates • not an external fine-tuning benchmark or safety certification</text>',
            "</g>",
            "</svg>",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_svg(content: str) -> None:
    try:
        ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError(f"generated invalid SVG: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the checked-in SVG differs from the evidence-derived output",
    )
    args = parser.parse_args()

    content = _svg(_load_evidence())
    _validate_svg(content)
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
            print(f"stale: {OUTPUT.relative_to(ROOT)}", file=sys.stderr)
            return 1
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "capture_readme_dashboard.py"), "--check"],
            cwd=ROOT,
            check=True,
        )
        print("SFTGuard README evidence asset is current and valid XML.")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    print(f"wrote {OUTPUT.relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
