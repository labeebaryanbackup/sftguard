"""Paired target/retention Regression Cards with deterministic bootstrap CIs."""

from __future__ import annotations

import math
import re
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from . import __version__
from .artifacts import canonical_json_bytes, seal_artifact, sha256_bytes
from .io import InputSummary, summarize_records
from .models import Status

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
MAX_BOOTSTRAP_WORK = 10_000_000


@dataclass(frozen=True)
class BootstrapConfig:
    draws: int = 10_000
    confidence: float = 0.95
    seed: int = 2339


class _XorShift32:
    def __init__(self, seed: int):
        self.state = seed & 0xFFFFFFFF or 0x6D2B79F5

    def next_u32(self) -> int:
        value = self.state
        value ^= (value << 13) & 0xFFFFFFFF
        value ^= value >> 17
        value ^= (value << 5) & 0xFFFFFFFF
        self.state = value & 0xFFFFFFFF
        return self.state

    def randbelow(self, stop: int) -> int:
        if stop <= 0:
            raise ValueError("stop must be positive")
        return self.next_u32() % stop


def _round(value: float) -> float:
    return round(value, 12)


def _percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("cannot calculate a percentile of no values")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def seed_cluster_bootstrap(
    values_by_seed: Mapping[int, tuple[float, ...]], config: BootstrapConfig
) -> tuple[float, float]:
    """Cluster-resample seeds, retaining all pairs inside each selected seed."""

    seeds = sorted(values_by_seed)
    if not seeds:
        raise ValueError("at least one seed cluster is required")
    if config.draws <= 0 or config.draws > 100_000:
        raise ValueError("bootstrap draws must be between 1 and 100000")
    if not 0.0 < config.confidence < 1.0:
        raise ValueError("bootstrap confidence must be between 0 and 1")

    generator = _XorShift32(config.seed)
    estimates: list[float] = []
    for _ in range(config.draws):
        sampled_values: list[float] = []
        for _ in seeds:
            selected_seed = seeds[generator.randbelow(len(seeds))]
            sampled_values.extend(values_by_seed[selected_seed])
        estimates.append(statistics.fmean(sampled_values))
    estimates.sort()
    tail = (1.0 - config.confidence) / 2.0
    return _round(_percentile(estimates, tail)), _round(_percentile(estimates, 1.0 - tail))


@dataclass(frozen=True)
class _Evaluation:
    seed: int
    sample_id: str
    group: str
    metric: str
    value: float

    @property
    def key(self) -> tuple[int, str, str, str]:
        return self.seed, self.sample_id, self.group, self.metric


def _parse_evaluations(
    records: Iterable[tuple[int, dict[str, Any]]],
) -> tuple[dict[tuple[int, str, str, str], _Evaluation], set[str]]:
    parsed: dict[tuple[int, str, str, str], _Evaluation] = {}
    errors: set[str] = set()
    for _, record in records:
        seed = record.get("seed")
        sample_id = record.get("sample_id")
        group = record.get("group")
        metric = record.get("metric")
        value = record.get("value")
        valid = (
            isinstance(seed, int)
            and not isinstance(seed, bool)
            and isinstance(sample_id, str)
            and 0 < len(sample_id) <= 512
            and isinstance(group, str)
            and _IDENTIFIER.fullmatch(group) is not None
            and isinstance(metric, str)
            and _IDENTIFIER.fullmatch(metric) is not None
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )
        if not valid:
            errors.add("invalid_evaluation_record")
            continue
        evaluation = _Evaluation(seed, sample_id, group, metric, float(value))
        if evaluation.key in parsed:
            errors.add("duplicate_pair_key")
        else:
            parsed[evaluation.key] = evaluation
    return parsed, errors


def _parse_contract(contract: Any) -> tuple[list[dict[str, Any]], BootstrapConfig, set[str]]:
    errors: set[str] = set()
    if not isinstance(contract, dict):
        return [], BootstrapConfig(), {"invalid_contract"}
    raw_metrics = contract.get("metrics")
    raw_bootstrap = contract.get("bootstrap", {})
    if not isinstance(raw_metrics, list) or not raw_metrics:
        errors.add("invalid_contract_metrics")
        raw_metrics = []
    if not isinstance(raw_bootstrap, dict):
        errors.add("invalid_bootstrap_config")
        raw_bootstrap = {}

    draws = raw_bootstrap.get("draws", 10_000)
    confidence = raw_bootstrap.get("confidence", 0.95)
    seed = raw_bootstrap.get("seed", 2339)
    if (
        not isinstance(draws, int)
        or isinstance(draws, bool)
        or not 1 <= draws <= 100_000
        or not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0.0 < float(confidence) < 1.0
        or not isinstance(seed, int)
        or isinstance(seed, bool)
    ):
        errors.add("invalid_bootstrap_config")
        bootstrap = BootstrapConfig()
    else:
        bootstrap = BootstrapConfig(draws, float(confidence), seed)

    parsed: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    groups: set[str] = set()
    for raw in raw_metrics:
        if not isinstance(raw, dict):
            errors.add("invalid_metric_contract")
            continue
        group = raw.get("group")
        metric = raw.get("metric")
        higher = raw.get("higher_is_better")
        if (
            group not in {"target", "retention"}
            or not isinstance(metric, str)
            or _IDENTIFIER.fullmatch(metric) is None
            or not isinstance(higher, bool)
        ):
            errors.add("invalid_metric_contract")
            continue
        key = (group, metric)
        if key in seen:
            errors.add("duplicate_metric_contract")
            continue
        seen.add(key)
        groups.add(group)

        if group == "target":
            threshold = raw.get("min_improvement", 0.0)
            threshold_name = "min_improvement"
            if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
                errors.add("invalid_metric_threshold")
                continue
        else:
            threshold = raw.get("max_regression")
            threshold_name = "max_regression"
            if (
                not isinstance(threshold, (int, float))
                or isinstance(threshold, bool)
                or float(threshold) < 0.0
            ):
                errors.add("invalid_metric_threshold")
                continue
        if not math.isfinite(float(threshold)):
            errors.add("invalid_metric_threshold")
            continue
        parsed.append(
            {
                "group": group,
                "metric": metric,
                "higher_is_better": higher,
                threshold_name: float(threshold),
            }
        )

    if groups != {"target", "retention"}:
        errors.add("target_and_retention_contracts_required")
    return parsed, bootstrap, errors


def _abstain_card(
    reasons: set[str],
    *,
    base_summary: InputSummary,
    adapter_summary: InputSummary,
    contract_hash: str,
) -> dict[str, Any]:
    return seal_artifact(
        {
            "schema_version": "sftguard.regression-card.v1",
            "tool": {"name": "sftguard", "version": __version__},
            "status": Status.ABSTAIN,
            "inputs": [
                base_summary.as_dict("base"),
                adapter_summary.as_dict("adapter"),
                {"split": "contract", "sha256": contract_hash},
            ],
            "reason_codes": sorted(reasons),
            "metrics": [],
            "summary": {"metric_count": 0, "pair_count": 0, "seed_cluster_count": 0},
        }
    )


def _safe_summary(records: tuple[tuple[int, dict[str, Any]], ...]) -> InputSummary:
    try:
        return summarize_records(records)
    except (TypeError, ValueError, RecursionError):
        marker = canonical_json_bytes({"invalid_input": True, "record_count": len(records)})
        return InputSummary(
            sha256=sha256_bytes(marker),
            byte_count=len(marker),
            record_count=len(records),
        )


def _safe_contract_hash(contract: Any) -> str:
    try:
        material = canonical_json_bytes(contract)
    except (TypeError, ValueError, RecursionError):
        material = canonical_json_bytes({"invalid_contract": True})
    return sha256_bytes(material)


def build_regression_card(
    base_records: Iterable[tuple[int, dict[str, Any]]],
    adapter_records: Iterable[tuple[int, dict[str, Any]]],
    contract: Any,
    *,
    base_summary: InputSummary | None = None,
    adapter_summary: InputSummary | None = None,
) -> dict[str, Any]:
    base_materialized = tuple(base_records)
    adapter_materialized = tuple(adapter_records)
    base_summary = base_summary or _safe_summary(base_materialized)
    adapter_summary = adapter_summary or _safe_summary(adapter_materialized)
    contract_hash = _safe_contract_hash(contract)

    base, base_errors = _parse_evaluations(base_materialized)
    adapter, adapter_errors = _parse_evaluations(adapter_materialized)
    metric_contracts, bootstrap, contract_errors = _parse_contract(contract)
    errors = base_errors | adapter_errors | contract_errors
    if set(base) != set(adapter):
        errors.add("unpaired_evaluation_records")
    if not base:
        errors.add("paired_evaluation_records_required")

    declared = {(item["group"], item["metric"]) for item in metric_contracts}
    observed = {(item.group, item.metric) for item in base.values()}
    if observed - declared:
        errors.add("undeclared_metric_records")
    if declared - observed:
        errors.add("contract_metric_without_pairs")
    if bootstrap.draws * len(base) > MAX_BOOTSTRAP_WORK:
        errors.add("bootstrap_work_limit_exceeded")
    if errors:
        return _abstain_card(
            errors,
            base_summary=base_summary,
            adapter_summary=adapter_summary,
            contract_hash=contract_hash,
        )

    metric_results: list[dict[str, Any]] = []
    all_seeds: set[int] = set()
    for metric_contract in sorted(
        metric_contracts, key=lambda item: (item["group"], item["metric"])
    ):
        group = metric_contract["group"]
        metric = metric_contract["metric"]
        sign = 1.0 if metric_contract["higher_is_better"] else -1.0
        values_by_seed: dict[int, list[float]] = {}
        for key, base_value in base.items():
            if base_value.group != group or base_value.metric != metric:
                continue
            delta = sign * (adapter[key].value - base_value.value)
            values_by_seed.setdefault(base_value.seed, []).append(delta)
            all_seeds.add(base_value.seed)
        frozen_clusters = {seed: tuple(values) for seed, values in sorted(values_by_seed.items())}
        all_values = [value for values in frozen_clusters.values() for value in values]
        estimate = _round(statistics.fmean(all_values))
        ci_low, ci_high = seed_cluster_bootstrap(frozen_clusters, bootstrap)

        if group == "target":
            threshold_name = "min_improvement"
            threshold = metric_contract[threshold_name]
            passed = ci_low >= threshold
            decision = "lower_confidence_bound_at_or_above_minimum"
        else:
            threshold_name = "max_regression"
            threshold = metric_contract[threshold_name]
            passed = ci_low >= -threshold
            decision = "lower_confidence_bound_within_regression_budget"
        metric_results.append(
            {
                "group": group,
                "metric": metric,
                "higher_is_better": metric_contract["higher_is_better"],
                "status": Status.PASS if passed else Status.FAIL,
                "pair_count": len(all_values),
                "seed_cluster_count": len(frozen_clusters),
                "mean_normalized_improvement": estimate,
                "confidence_interval": {"low": ci_low, "high": ci_high},
                "threshold": {threshold_name: _round(threshold)},
                "decision_rule": decision,
            }
        )

    overall = (
        Status.PASS
        if all(result["status"] == Status.PASS for result in metric_results)
        else Status.FAIL
    )
    return seal_artifact(
        {
            "schema_version": "sftguard.regression-card.v1",
            "tool": {"name": "sftguard", "version": __version__},
            "status": overall,
            "inputs": [
                base_summary.as_dict("base"),
                adapter_summary.as_dict("adapter"),
                {"split": "contract", "sha256": contract_hash},
            ],
            "bootstrap": {
                "method": "paired_seed_cluster_xorshift32",
                "draws": bootstrap.draws,
                "confidence": bootstrap.confidence,
                "seed": bootstrap.seed,
            },
            "metrics": metric_results,
            "summary": {
                "metric_count": len(metric_results),
                "pair_count": len(base),
                "seed_cluster_count": len(all_seeds),
                "passed_metric_count": sum(
                    result["status"] == Status.PASS for result in metric_results
                ),
                "failed_metric_count": sum(
                    result["status"] == Status.FAIL for result in metric_results
                ),
            },
        }
    )
