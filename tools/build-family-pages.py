#!/usr/bin/env python3
"""Validate model-family manifests and generate compact public coverage pages.

The source data lives in families/*.json. Every plotted point retains an exact
measurement identity and evidence path. Repeated run medians are shown as a
range; their arithmetic mean is used only to place the SVG marker, never as a
new benchmark claim.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import sys
from itertools import product
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_seo import seo_head  # noqa: E402
CATALOG = ROOT / "families" / "catalog.json"
COVERAGE_REGISTRY = ROOT / "families" / "coverage-registry.json"
PACKAGE_CATALOG = ROOT / "packages" / "catalog.json"
GUIDE_CATALOG = ROOT / "repro" / "guide-catalog.json"
OUT_DIR = ROOT / "models"
BRIDGE = ROOT / "learn" / "assets" / "mlbottleneck-bridge.js"
SITE = "https://neural.download/"
GITHUB = "https://github.com/steveseguin/b70-optimization-lab/blob/main/"

METRICS = {
    "decode_tok_s": ("Decode", "tok/s"),
    "wall_output_tok_s": ("End-to-end output", "tok/s"),
    "aggregate_tok_s": ("Combined", "tok/s"),
    "prefill_tok_s": ("Prefill", "tok/s"),
    "ttft_ms": ("TTFT", "ms"),
    "mean_acceptance_length": ("Acceptance length", "tokens"),
    "draft_acceptance_rate": ("Draft acceptance", "ratio"),
    "effective_tokens_per_verification": ("Effective tokens / verify", "tokens"),
}
COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)"]
ALLOWED_STATES = {
    "lab-measured",
    "lab-screened",
    "community-measured",
    "estimated",
    "closed",
    "quarantined",
    "unsupported",
    "missing",
}
OBSERVED_STATES = {
    "lab-measured",
    "lab-screened",
    "community-measured",
    "quarantined",
}
CURVE_STATES = {"lab-measured", "community-measured"}
# Screened lab runs may draw curves too: they are real measurements under a
# lighter gate, and the view flag plus legend carry that caveat. Estimates and
# quarantined runs still never chart. Coverage-cell evidence requirements keep
# using CURVE_STATES: a screened cell is not obliged to carry a measurement id.
CHARTABLE_STATES = CURVE_STATES | {"lab-screened"}
MAX_COVERAGE_CONTRACT_CELLS = 50_000
CONTRACT_CELL_FIELDS = {
    "state",
    "label",
    "reason",
    "evidence_id",
    "evidence",
    "packet_id",
    "estimate_id",
    "point_x",
    "parent",
    "retry",
}
# Glyph + plain-words meaning for every coverage state. Cells show the glyph
# with the words in a tooltip (and for screen readers); the legend spells the
# words out once.
STATE_GLYPHS = {
    "lab-measured": "\u2713 measured",
    "lab-screened": "\u25c7 screened",
    "community-measured": "\u25d0 community",
    "estimated": "\u2248 estimate",
    "closed": "\u25a0 closed",
    "quarantined": "\u26a0 quarantined",
    "unsupported": "\u00d7 unsupported",
    "missing": "\u00b7 untested",
}
STATE_MEANING = {
    "lab-measured": "Measured on the lab's own machines; the number links to its proof",
    "lab-screened": "Screened: one lighter-gate lab run, not the full quality battery",
    "community-measured": "Measured by a community contributor and checked by the lab",
    "estimated": "Estimate only, no measurement behind it",
    "closed": "Closed: tried, rejected, and documented; not a blank",
    "quarantined": "Quarantined: the run did not produce usable evidence; kept for the record, do not use",
    "unsupported": "The runtime or hardware cannot run this combination",
    "missing": "Not tested yet",
}
ALLOWED_GRADES = {"A", "B", "C", "D"}
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SELECTOR_KEY_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
POINT_METRIC_PREFIX = {
    "decode_tok_s": "D",
    "wall_output_tok_s": "E2E",
    "aggregate_tok_s": "A",
    "prefill_tok_s": "P",
    "ttft_ms": "T",
    "mean_acceptance_length": "A",
    "draft_acceptance_rate": "AR",
    "effective_tokens_per_verification": "EV",
}
PUBLIC_ARTIFACT_KINDS = {
    "package",
    "repro",
    "result",
    "result-index",
    "rapid-snapshot",
    "rapid-snapshot-index",
}
REGISTRY_DISPOSITIONS = {"family", "archive", "excluded"}


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def fmt(value: float | int | None, digits: int = 2) -> str:
    if not is_finite_number(value):
        return "—"
    number = float(value)
    if abs(number) >= 1000:
        return f"{number:,.0f}"
    if number == int(number):
        return str(int(number))
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def fmt_x(value: float | int) -> str:
    number = float(value)
    if number >= 1024:
        # Binary-aligned sweep points (2K/4K/32K) use their conventional
        # token labels; measured prompt counts such as 17,274 stay decimal.
        scaled = number / (1024 if number % 1024 == 0 else 1000)
        return f"{fmt(scaled, 1)}K"
    return fmt(number, 0)


def exact_number(value: float | int) -> str:
    """Keep a finite measured number unrounded for point-level disclosure."""

    return str(value)


def compact_count(value: Any) -> str:
    if not is_finite_number(value):
        return "Pending"
    number = float(value)
    for divisor, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(number) >= divisor:
            return f"{number / divisor:.2f}".rstrip("0").rstrip(".") + suffix
    return fmt(number, 0)


def nested(item: dict[str, Any], dotted: str) -> Any:
    current: Any = item
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def is_selector_scalar(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, bool):
        return True
    return is_finite_number(value)


def is_axis_scalar(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and ":" not in value
    ) or (is_finite_number(value) and ":" not in str(value))


def is_selector_scope(value: Any) -> bool:
    return is_selector_scalar(value) or (
        isinstance(value, list)
        and bool(value)
        and all(is_selector_scalar(item) for item in value)
    )


def object_list(
    value: Any, label: str, errors: list[str]
) -> list[dict[str, Any]]:
    """Return valid object entries while recording every malformed container."""

    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    output = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] must be an object")
        else:
            output.append(item)
    return output


def safe_repo_path(value: Any) -> Path | None:
    """Resolve a repository-relative path without permitting traversal/symlink escape."""

    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return resolved


def source_label(source: Path) -> str:
    try:
        return str(source.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(source)


def json_for_html_script(value: Any) -> str:
    """Serialize JSON-LD without allowing an HTML script end-tag breakout."""

    return (
        json.dumps(value, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def point_metric_label(point: dict[str, Any]) -> str:
    return " · ".join(
        f"{POINT_METRIC_PREFIX[metric]}{fmt(point[metric])}"
        for metric in METRICS
        if is_finite_number(point.get(metric))
    )


def records(family: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for key in ("run_measurements", "series_measurements"):
        value = family.get(key)
        if isinstance(value, list):
            output.extend(item for item in value if isinstance(item, dict))
    return output


def coverage_axis(view: dict[str, Any], side: str) -> dict[str, Any]:
    """Return an additive named-axis spec, with the original MTP/TP defaults."""

    if side not in {"row", "column"}:
        raise ValueError(f"unknown coverage axis side: {side}")
    legacy_values = view.get("rows" if side == "row" else "columns")
    if not isinstance(legacy_values, list):
        legacy_values = []
    defaults = (
        {"key": "mtp", "label": "MTP", "prefix": "MTP"}
        if side == "row"
        else {"key": "tp", "label": "TP", "prefix": "TP"}
    )
    spec = dict(defaults)
    supplied = view.get(f"{side}_axis")
    if isinstance(supplied, dict):
        spec.update(supplied)
    spec["values"] = legacy_values
    return spec


def axis_value_label(axis: dict[str, Any], value: Any) -> str:
    labels = axis.get("value_labels") or {}
    explicit = labels.get(str(value))
    if explicit is not None:
        return str(explicit)
    return f'{axis.get("prefix", "")}{value}'


def record_selector_value(record: dict[str, Any], key: str) -> Any:
    if key in record:
        return record[key]
    for container_name in ("config", "identity"):
        container = record.get(container_name)
        if isinstance(container, dict) and key in container:
            return container[key]
    return None


def effective_cell_selectors(
    view: dict[str, Any],
    row: Any,
    column: Any,
    cell: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selectors = dict(view.get("fixed_selectors") or {})
    selectors[coverage_axis(view, "row")["key"]] = row
    selectors[coverage_axis(view, "column")["key"]] = column
    if isinstance(cell, dict) and isinstance(cell.get("selectors"), dict):
        selectors.update(cell["selectors"])
    return selectors


def validate_grade(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    errors = []
    if value.get("grade") not in ALLOWED_GRADES:
        errors.append(f"{label}.grade must be one of {sorted(ALLOWED_GRADES)}")
    for field in ("scope", "basis", "reviewed_at"):
        if not isinstance(value.get(field), str) or not value.get(field):
            errors.append(f"{label}.{field} is required")
    evidence = value.get("evidence")
    if (
        not isinstance(evidence, list)
        or not evidence
        or any(not isinstance(item, str) or not item for item in evidence)
    ):
        errors.append(f"{label}.evidence must be a non-empty list of strings")
    return errors


def validate_featured_metric(
    value: Any,
    label: str,
    measurements: dict[str, dict[str, Any]],
    package_backed: bool,
) -> list[str]:
    """Bind a family-only headline to one exact normalized measurement sample."""

    if value is None:
        return []
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    errors = []
    if package_backed:
        errors.append(f"{label} is only allowed on family-only research packets")
    metric = value.get("metric")
    if metric not in METRICS:
        errors.append(f"{label}.metric must be one of {sorted(METRICS)}")
    measurement_id = value.get("measurement_id")
    if not isinstance(measurement_id, str) or measurement_id not in measurements:
        errors.append(f"{label}.measurement_id must reference a known measurement")
        return errors
    measurement = measurements[measurement_id]
    if measurement.get("state") not in CHARTABLE_STATES:
        errors.append(f"{label}.measurement_id must reference measured curve evidence")
    sample_index = value.get("sample_index")
    point_x = value.get("point_x")
    if (sample_index is None) == (point_x is None):
        errors.append(f"{label} must set exactly one of sample_index or point_x")
    if sample_index is not None:
        values = (measurement.get("metrics") or {}).get(metric)
        if (
            not isinstance(sample_index, int)
            or isinstance(sample_index, bool)
            or not isinstance(values, list)
            or not 0 <= sample_index < len(values)
        ):
            errors.append(f"{label}.sample_index does not select the declared metric")
        else:
            selected_value = values[sample_index]
            if not is_finite_number(value.get("value")) or value.get("value") != selected_value:
                errors.append(
                    f"{label}.value must match {measurement_id} sample {sample_index}"
                )
    if point_x is not None:
        points = measurement.get("points") or []
        if not is_finite_number(point_x) or not any(
            point.get("x") == point_x and is_finite_number(point.get(metric))
            for point in points
            if isinstance(point, dict)
        ):
            errors.append(f"{label}.point_x does not select the declared metric")
        else:
            selected_point = next(
                point
                for point in points
                if isinstance(point, dict) and point.get("x") == point_x
            )
            if not is_finite_number(value.get("value")) or value.get("value") != selected_point[metric]:
                errors.append(
                    f"{label}.value must match {measurement_id} point {point_x}"
                )
    if metric in METRICS and value.get("unit") != METRICS[metric][1]:
        errors.append(f"{label}.unit must equal {METRICS[metric][1]}")
    for field in ("workload", "evidence"):
        if value.get(field) != measurement.get(field):
            errors.append(f"{label}.{field} must match {measurement_id}")
    return errors


def selected_metric_value(
    binding: dict[str, Any], measurement: dict[str, Any]
) -> float | None:
    """Resolve one explicit metric binding without choosing a max or average."""

    metric = binding.get("metric")
    sample_index = binding.get("sample_index")
    if isinstance(sample_index, int) and not isinstance(sample_index, bool):
        values = (measurement.get("metrics") or {}).get(metric)
        if isinstance(values, list) and 0 <= sample_index < len(values):
            value = values[sample_index]
            return float(value) if is_finite_number(value) else None
    point_x = binding.get("point_x")
    if is_finite_number(point_x):
        for point in measurement.get("points") or []:
            if (
                isinstance(point, dict)
                and point.get("x") == point_x
                and is_finite_number(point.get(metric))
            ):
                return float(point[metric])
    return None


def validate_featured_results(
    value: Any,
    label: str,
    measurements: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate presentation picks as exact pointers, never inferred highs."""

    if value is None:
        return []
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    errors: list[str] = []
    hero_count = 0
    for index, binding in enumerate(value):
        item_label = f"{label}[{index}]"
        if not isinstance(binding, dict):
            errors.append(f"{item_label} must be an object")
            continue
        role = binding.get("role")
        if role not in {"hero", "support"}:
            errors.append(f"{item_label}.role must be hero or support")
        hero_count += role == "hero"
        for field in ("label", "quality_label"):
            if not isinstance(binding.get(field), str) or not binding.get(field):
                errors.append(f"{item_label}.{field} is required")
        measurement_id = binding.get("measurement_id")
        if not isinstance(measurement_id, str) or measurement_id not in measurements:
            errors.append(f"{item_label}.measurement_id must reference a known measurement")
            continue
        measurement = measurements[measurement_id]
        if measurement.get("state") not in CHARTABLE_STATES:
            errors.append(
                f"{item_label}.measurement_id must reference measured or screened evidence"
            )
        metric = binding.get("metric")
        if metric not in METRICS:
            errors.append(f"{item_label}.metric must be one of {sorted(METRICS)}")
            continue
        sample_index = binding.get("sample_index")
        point_x = binding.get("point_x")
        if (sample_index is None) == (point_x is None):
            errors.append(
                f"{item_label} must set exactly one of sample_index or point_x"
            )
        if selected_metric_value(binding, measurement) is None:
            errors.append(f"{item_label} does not select the declared metric")
    if value and hero_count != 1:
        errors.append(f"{label} must contain exactly one hero")
    return errors


def evidence_href(path: str) -> str:
    if path.startswith(("https://", "http://")):
        return path
    return GITHUB + path


def bridge_version() -> str:
    return hashlib.sha1(BRIDGE.read_bytes()).hexdigest()[:10]


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(
            handle,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number {token}")
            ),
        )
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)}: root must be an object")
    return value


def public_evidence_inventory() -> tuple[dict[str, str], list[str]]:
    """Discover every public package, repro, result, and rapid-snapshot entry."""

    expected: dict[str, str] = {}
    errors: list[str] = []

    def add(path: Any, kind: str, label: str) -> None:
        if not isinstance(path, str) or not path:
            errors.append(f"{label}: path must be a non-empty string")
            return
        prior = expected.get(path)
        if prior is not None:
            errors.append(f"{label}: duplicate public evidence path {path} ({prior}, {kind})")
            return
        expected[path] = kind

    try:
        package_catalog = load_json(PACKAGE_CATALOG)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    else:
        for index, package in enumerate(
            object_list(package_catalog.get("packages"), "packages/catalog.json: packages", errors)
        ):
            add(package.get("manifest"), "package", f"packages/catalog.json: packages[{index}]")

    try:
        guide_catalog = load_json(GUIDE_CATALOG)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    else:
        for index, guide in enumerate(
            object_list(guide_catalog.get("guides"), "repro/guide-catalog.json: guides", errors)
        ):
            add(guide.get("guide"), "repro", f"repro/guide-catalog.json: guides[{index}]")

    results_root = ROOT / "results"
    result_index = results_root / "README.md"
    if result_index.exists():
        add("results/README.md", "result-index", "results index")
    for readme in sorted(results_root.glob("*/README.md")):
        # POSIX form on every platform: registry paths use forward slashes.
        relative = readme.relative_to(ROOT).as_posix()
        kind = (
            "rapid-snapshot-index"
            if readme.parent.name == "rapid-model-snapshots-b70"
            else "result"
        )
        add(relative, kind, "results discovery")
    rapid_root = results_root / "rapid-model-snapshots-b70"
    for readme in sorted(rapid_root.glob("*/README.md")):
        add(readme.relative_to(ROOT).as_posix(), "rapid-snapshot", "rapid snapshot discovery")
    return expected, errors


def validate_coverage_registry(
    registry: dict[str, Any], published_family_ids: set[str], expected: dict[str, str]
) -> tuple[list[str], dict[str, int]]:
    """Validate one canonical lane assignment for every public evidence artifact."""

    label = "families/coverage-registry.json"
    errors: list[str] = []
    if registry.get("format") != "neural-download-coverage-registry-v1":
        errors.append(f"{label}: unsupported format")

    planned_ids: set[str] = set()
    for index, family in enumerate(
        object_list(registry.get("planned_families"), f"{label}: planned_families", errors)
    ):
        prefix = f"{label}: planned_families[{index}]"
        family_id = family.get("id")
        if not isinstance(family_id, str) or not SLUG_RE.fullmatch(family_id):
            errors.append(f"{prefix}.id must be a lowercase hyphenated slug")
            continue
        if family_id in planned_ids or family_id in published_family_ids:
            errors.append(f"{prefix}.id duplicates a declared family: {family_id}")
        planned_ids.add(family_id)
        if not isinstance(family.get("label"), str) or not family["label"]:
            errors.append(f"{prefix}.label must be a non-empty string")

    lane_ids: set[str] = set()
    seen_artifacts: dict[str, str] = {}
    disposition_counts = {state: 0 for state in REGISTRY_DISPOSITIONS}
    lanes = object_list(registry.get("lanes"), f"{label}: lanes", errors)
    for index, lane in enumerate(lanes):
        prefix = f"{label}: lanes[{index}]"
        lane_id = lane.get("id")
        valid_lane_id = isinstance(lane_id, str) and bool(SLUG_RE.fullmatch(lane_id))
        if not valid_lane_id:
            errors.append(f"{prefix}.id must be a lowercase hyphenated slug")
            lane_label = f"lane[{index}]"
        else:
            lane_label = lane_id
            if lane_id in lane_ids:
                errors.append(f"{prefix}.id duplicates canonical lane {lane_id}")
            lane_ids.add(lane_id)

        disposition = lane.get("disposition")
        if disposition not in REGISTRY_DISPOSITIONS:
            errors.append(f"{prefix}.disposition must be one of {sorted(REGISTRY_DISPOSITIONS)}")
        else:
            disposition_counts[disposition] += 1
        family_id = lane.get("family_id")
        if disposition == "family":
            if family_id not in published_family_ids | planned_ids:
                errors.append(f"{prefix}.family_id must name a published or planned family")
        else:
            if family_id is not None:
                errors.append(f"{prefix}.family_id is only valid for family disposition")
            if not isinstance(lane.get("reason"), str) or not lane["reason"]:
                errors.append(f"{prefix}.reason is required for {disposition} disposition")

        artifacts = object_list(lane.get("artifacts"), f"{prefix}.artifacts", errors)
        if not artifacts:
            errors.append(f"{prefix}.artifacts must contain at least one public artifact")
        for artifact_index, artifact in enumerate(artifacts):
            artifact_prefix = f"{prefix}.artifacts[{artifact_index}]"
            kind = artifact.get("kind")
            path = artifact.get("path")
            if kind not in PUBLIC_ARTIFACT_KINDS:
                errors.append(f"{artifact_prefix}.kind must be a public artifact kind")
            if not isinstance(path, str) or not path:
                errors.append(f"{artifact_prefix}.path must be a non-empty string")
                continue
            source = safe_repo_path(path)
            if source is None or not source.is_file():
                errors.append(f"{artifact_prefix}.path must name an existing repository file")
            prior_lane = seen_artifacts.get(path)
            if prior_lane is not None:
                errors.append(
                    f"{artifact_prefix}.path is assigned to both {prior_lane} and {lane_label}"
                )
            else:
                seen_artifacts[path] = lane_label
            expected_kind = expected.get(path)
            if expected_kind is None:
                errors.append(f"{artifact_prefix}.path is not discovered public evidence: {path}")
            elif kind != expected_kind:
                errors.append(
                    f"{artifact_prefix}.kind must be {expected_kind} for {path}, got {kind}"
                )

    missing = sorted(set(expected) - set(seen_artifacts))
    if missing:
        errors.append(f"{label}: unmapped public evidence: " + ", ".join(missing))
    return errors, {
        "lanes": len(lane_ids),
        "artifacts": len(seen_artifacts),
        **disposition_counts,
    }


def local_evidence_paths(value: Any, key: str | None = None):
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from local_evidence_paths(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from local_evidence_paths(child, key)
    elif key in {"evidence", "manifest", "model_manifest", "record"} and isinstance(value, str):
        if not value.startswith(("https://", "http://")):
            yield value


def curve_identity(record: dict[str, Any], x_from: str) -> dict[str, Any]:
    """Identity fields that must stay fixed along one connected measured curve."""

    identity = {
        key: record.get(key)
        for key in (
            "revision",
            "variant",
            "quantization",
            "runtime",
            "runtime_family",
            "profile_id",
            "measurement_class",
            "workload",
            "model_revision",
            "artifact_id",
            "identity",
            "runtime_identity",
        )
        if key in record
    }
    config = record.get("config")
    if isinstance(config, dict):
        identity["config"] = dict(config)
    parts = x_from.split(".")
    if len(parts) == 1:
        identity.pop(parts[0], None)
    elif len(parts) == 2 and isinstance(identity.get(parts[0]), dict):
        identity[parts[0]].pop(parts[1], None)
    return identity


def expand_coverage_contract(
    contract: dict[str, Any], label: str = "coverage contract"
) -> tuple[list[dict[str, Any]], list[str]]:
    """Expand an ordered wildcard-to-exact contract into exact selector cells."""
    errors: list[str] = []
    fixed_selectors = contract.get("fixed_selectors")
    if fixed_selectors is None:
        fixed_selectors = {}
    elif not isinstance(fixed_selectors, dict) or not fixed_selectors:
        errors.append(f"{label}.fixed_selectors must be a non-empty object")
        fixed_selectors = {}
    invalid_fixed = [
        key
        for key, value in fixed_selectors.items()
        if not isinstance(key, str)
        or not SELECTOR_KEY_RE.fullmatch(key)
        or not is_selector_scalar(value)
        or value == "*"
    ]
    if invalid_fixed:
        errors.append(
            f"{label}.fixed_selectors must use selector keys and scalar values excluding '*'"
        )
    axes = contract.get("axes")
    if not isinstance(axes, list) or not axes:
        return [], [f"{label} needs a non-empty axes list"]

    axis_keys: list[str] = []
    axis_values: list[list[Any]] = []
    for index, axis in enumerate(axes):
        axis_label = f"{label} axis {index}"
        if not isinstance(axis, dict):
            errors.append(f"{axis_label} must be an object")
            continue
        key = axis.get("key")
        values = axis.get("values")
        if not isinstance(key, str) or not SELECTOR_KEY_RE.fullmatch(key):
            errors.append(f"{axis_label} needs a selector key")
            continue
        if key in axis_keys:
            errors.append(f"{label} repeats axis key {key}")
            continue
        axis_keys.append(key)
        if not isinstance(axis.get("label"), str) or not axis.get("label"):
            errors.append(f"{axis_label} needs a label")
        if (
            not isinstance(values, list)
            or not values
            or any(not is_selector_scalar(value) or value == "*" for value in values)
        ):
            errors.append(
                f"{axis_label} values must be non-empty selector scalars excluding '*'"
            )
            axis_values.append([])
            continue
        if len({json.dumps(value, sort_keys=True) for value in values}) != len(values):
            errors.append(f"{axis_label} values must be unique")
        value_labels = axis.get("value_labels")
        if value_labels is not None and (
            not isinstance(value_labels, dict)
            or set(value_labels) - {str(value) for value in values}
            or any(not isinstance(value, str) for value in value_labels.values())
        ):
            errors.append(f"{axis_label} has invalid value_labels")
        axis_values.append(values)

    if len(axis_keys) != len(axes) or any(not values for values in axis_values):
        return [], errors
    repeated_fixed = set(fixed_selectors) & set(axis_keys)
    if repeated_fixed:
        errors.append(
            f"{label}.fixed_selectors cannot repeat axis keys {sorted(repeated_fixed)}"
        )
    if invalid_fixed or repeated_fixed:
        return [], errors
    cell_count = math.prod(len(values) for values in axis_values)
    if cell_count > MAX_COVERAGE_CONTRACT_CELLS:
        errors.append(
            f"{label} expands to {cell_count} cells; maximum is {MAX_COVERAGE_CONTRACT_CELLS}"
        )
        return [], errors

    rules = contract.get("rules")
    if not isinstance(rules, list) or not rules:
        return [], errors + [f"{label} needs a non-empty ordered rules list"]
    normalized_rules: list[tuple[str, dict[str, Any], frozenset[str], dict[str, Any]]] = []
    rule_ids: set[str] = set()
    expected_match_keys = set(axis_keys)
    for index, rule in enumerate(rules):
        rule_label = f"{label} rule {index}"
        if not isinstance(rule, dict):
            errors.append(f"{rule_label} must be an object")
            continue
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not SLUG_RE.fullmatch(rule_id):
            errors.append(f"{rule_label} needs a lowercase hyphenated id")
            rule_id = f"rule-{index}"
        elif rule_id in rule_ids:
            errors.append(f"{label} repeats rule id {rule_id}")
        rule_ids.add(rule_id)
        match = rule.get("match")
        if not isinstance(match, dict) or set(match) != expected_match_keys:
            errors.append(
                f"{rule_label} match must name every axis exactly once"
            )
            continue
        match_valid = True
        for key, value in match.items():
            domain = axis_values[axis_keys.index(key)]
            if value != "*" and value not in domain:
                errors.append(
                    f"{rule_label} match {key}={value} is outside its axis"
                )
                match_valid = False
        unknown_fields = set(rule) - {"id", "match"} - CONTRACT_CELL_FIELDS
        if unknown_fields:
            errors.append(
                f"{rule_label} has unknown output fields {sorted(unknown_fields)}"
            )
        payload = {
            field: rule[field]
            for field in CONTRACT_CELL_FIELDS
            if field in rule
        }
        if "state" in payload and payload["state"] not in ALLOWED_STATES:
            errors.append(f"{rule_label}.state is not an allowed coverage state")
        for field in (
            "label",
            "reason",
            "evidence_id",
            "evidence",
            "packet_id",
            "estimate_id",
        ):
            if field in payload and (
                not isinstance(payload[field], str) or not payload[field]
            ):
                errors.append(f"{rule_label}.{field} must be a non-empty string")
        if "point_x" in payload and not is_finite_number(payload["point_x"]):
            errors.append(f"{rule_label}.point_x must be finite numeric")
        if "parent" in payload and (
            not isinstance(payload["parent"], str) or not payload["parent"]
        ):
            errors.append(f"{rule_label}.parent must be a non-empty string")
        if "retry" in payload:
            retry = payload["retry"]
            if (
                not isinstance(retry, dict)
                or not retry
                or not isinstance(retry.get("status"), str)
                or not retry.get("status")
                or any(
                    not isinstance(key, str)
                    or not SELECTOR_KEY_RE.fullmatch(key)
                    or not is_selector_scalar(value)
                    for key, value in (retry or {}).items()
                )
            ):
                errors.append(
                    f"{rule_label}.retry needs scalar metadata and a non-empty status"
                )
        if match_valid:
            normalized_rules.append(
                (
                    rule_id,
                    match,
                    frozenset(key for key, value in match.items() if value != "*"),
                    payload,
                )
            )

    cells: list[dict[str, Any]] = []
    for coordinates in product(*axis_values):
        axis_selectors = dict(zip(axis_keys, coordinates))
        selectors = {**fixed_selectors, **axis_selectors}
        matching = [
            rule
            for rule in normalized_rules
            if all(
                wanted == "*" or axis_selectors[key] == wanted
                for key, wanted in rule[1].items()
            )
        ]
        selector_text = json.dumps(selectors, sort_keys=True, separators=(",", ":"))
        if not matching:
            errors.append(f"{label} leaves cell {selector_text} uncovered")
            continue
        exact_sets = [rule[2] for rule in matching]
        if any(
            not earlier < later
            for earlier, later in zip(exact_sets, exact_sets[1:])
        ):
            errors.append(
                f"{label} has ambiguous or misordered rules for cell {selector_text}"
            )
            continue
        cell: dict[str, Any] = {"selectors": selectors}
        for _, _, _, payload in matching:
            cell.update(payload)
        cell["rule_ids"] = [rule[0] for rule in matching]
        if cell.get("state") not in ALLOWED_STATES:
            errors.append(
                f"{label} cell {selector_text} does not resolve an allowed state"
            )
        cells.append(cell)
    return cells, errors


def validate_family(family: dict[str, Any], source: Path) -> list[str]:
    label = source_label(source)
    errors: list[str] = []
    if family.get("format") != "neural-download-model-family-v1":
        errors.append(f"{label}: unsupported format")
    if "collapse_coverage_contracts" in family and not isinstance(
        family.get("collapse_coverage_contracts"), bool
    ):
        errors.append(f"{label}: collapse_coverage_contracts must be boolean")
    family_id = family.get("id")
    if not isinstance(family_id, str) or not SLUG_RE.fullmatch(family_id):
        errors.append(f"{label}: id must be a lowercase hyphenated slug")
    if not isinstance(family.get("name"), str) or not family.get("name"):
        errors.append(f"{label}: name is required")

    revisions = object_list(family.get("weight_revisions"), f"{label}: weight_revisions", errors)
    model_variants = object_list(
        family.get("model_variants"), f"{label}: model_variants", errors
    )
    packets = object_list(family.get("packets"), f"{label}: packets", errors)
    run_measurements = object_list(
        family.get("run_measurements"), f"{label}: run_measurements", errors
    )
    series_measurements = object_list(
        family.get("series_measurements"), f"{label}: series_measurements", errors
    )
    featured_results = family.get("featured_results")
    estimates = object_list(family.get("estimates"), f"{label}: estimates", errors)
    views = object_list(family.get("views"), f"{label}: views", errors)
    coverage_views = object_list(
        family.get("coverage_views"), f"{label}: coverage_views", errors
    )
    coverage_contracts = object_list(
        family.get("coverage_contracts"), f"{label}: coverage_contracts", errors
    )
    closures = object_list(
        family.get("family_closures"), f"{label}: family_closures", errors
    )

    revision_ids: set[str] = set()
    artifact_bound_revision_ids: set[str] = set()
    artifact_ids: set[str] = set()
    artifact_revision_ids: dict[str, str] = {}
    artifacts_by_id: dict[str, dict[str, Any]] = {}
    for revision in revisions:
        revision_id = revision.get("id")
        if not isinstance(revision_id, str) or not revision_id:
            errors.append(f"{label}: weight revision without id")
            continue
        if revision_id in revision_ids:
            errors.append(f"{label}: duplicate weight revision id {revision_id}")
        revision_ids.add(revision_id)
        grades = revision.get("grades")
        if grades is not None and not isinstance(grades, dict):
            errors.append(f"{label}: revision {revision_id} grades must be an object")
            grades = {}
        errors.extend(
            validate_grade(
                (grades or {}).get("capability"),
                f"{label}: revision {revision_id} capability grade",
            )
        )
        artifacts = object_list(
            revision.get("quantized_artifacts"),
            f"{label}: revision {revision_id} quantized_artifacts",
            errors,
        )
        if artifacts:
            artifact_bound_revision_ids.add(revision_id)
        for artifact in artifacts:
            artifact_id = artifact.get("id")
            if not isinstance(artifact_id, str) or not SLUG_RE.fullmatch(artifact_id):
                errors.append(
                    f"{label}: revision {revision_id} quantized artifact needs a lowercase hyphenated id"
                )
                continue
            if artifact_id in artifact_ids:
                errors.append(f"{label}: duplicate quantized artifact id {artifact_id}")
            artifact_ids.add(artifact_id)
            artifact_revision_ids[artifact_id] = revision_id
            artifacts_by_id[artifact_id] = artifact
            for field in ("label", "quantization", "repository", "evidence"):
                if not isinstance(artifact.get(field), str) or not artifact.get(field):
                    errors.append(
                        f"{label}: quantized artifact {artifact_id}.{field} is required"
                    )
            artifact_revision = artifact.get("revision")
            if artifact_revision is not None and (
                not isinstance(artifact_revision, str) or not artifact_revision
            ):
                errors.append(
                    f"{label}: quantized artifact {artifact_id}.revision must be a non-empty string"
                )
            if artifact_revision is None and (
                not isinstance(artifact.get("revision_status"), str)
                or not artifact.get("revision_status")
            ):
                errors.append(
                    f"{label}: quantized artifact {artifact_id} needs revision or explicit revision_status"
                )
            quantization_origin = artifact.get("quantization_origin")
            if quantization_origin is not None and quantization_origin not in {
                "export",
                "runtime",
            }:
                errors.append(
                    f"{label}: quantized artifact {artifact_id}.quantization_origin must be export or runtime"
                )

    declared_revision_ids = set(revision_ids)
    for variant in model_variants:
        variant_id = variant.get("id")
        if not isinstance(variant_id, str) or not variant_id:
            errors.append(f"{label}: model variant without id")
            continue
        if variant_id in declared_revision_ids:
            errors.append(f"{label}: duplicate revision/model variant id {variant_id}")
        declared_revision_ids.add(variant_id)

    all_measurements = run_measurements + series_measurements
    measurement_ids: set[str] = set()
    measurements: dict[str, dict[str, Any]] = {}
    for measurement in all_measurements:
        mid = measurement.get("id")
        if not isinstance(mid, str) or not mid:
            errors.append(f"{label}: measurement without id")
            continue
        if mid in measurement_ids:
            errors.append(f"{label}: duplicate measurement id {mid}")
        measurement_ids.add(mid)
        measurements.setdefault(mid, measurement)
        if measurement.get("state") not in OBSERVED_STATES:
            errors.append(
                f"{label}: {mid} must use an observed state, got {measurement.get('state')}"
            )
        if measurement.get("revision") not in declared_revision_ids:
            errors.append(f"{label}: {mid} references unknown revision {measurement.get('revision')}")
        artifact_id = measurement.get("artifact_id")
        if measurement.get("revision") in artifact_bound_revision_ids and (
            not isinstance(measurement.get("quantization"), str)
            or not measurement.get("quantization")
        ):
            errors.append(
                f"{label}: {mid} must name its canonical quantization for artifact-bound revision {measurement.get('revision')}"
            )
        if (
            measurement.get("revision") in artifact_bound_revision_ids
            and artifact_id is None
        ):
            errors.append(
                f"{label}: {mid} must name a quantized artifact for revision {measurement.get('revision')}"
            )
        elif artifact_id is not None:
            if not isinstance(artifact_id, str) or artifact_id not in artifacts_by_id:
                errors.append(f"{label}: {mid} references unknown quantized artifact {artifact_id}")
            else:
                if artifact_revision_ids[artifact_id] != measurement.get("revision"):
                    errors.append(
                        f"{label}: {mid} artifact {artifact_id} does not belong to revision {measurement.get('revision')}"
                    )
                artifact_quant = artifacts_by_id[artifact_id].get("quantization")
                measured_quant = measurement.get("quantization")
                if measured_quant != artifact_quant:
                    errors.append(
                        f"{label}: {mid} quantization {measured_quant} does not match artifact {artifact_id} ({artifact_quant})"
                    )
        if not isinstance(measurement.get("evidence"), str) or not measurement.get("evidence"):
            errors.append(f"{label}: {mid} lacks evidence")
        for field in ("profile_id", "measurement_class", "promotion_status", "quality_scope"):
            if field in measurement and not isinstance(measurement.get(field), str):
                errors.append(f"{label}: {mid}.{field} must be a string")

        raw_metrics = measurement.get("metrics")
        raw_points = measurement.get("points")
        metrics: dict[str, Any] = {}
        points: list[Any] = []
        if raw_metrics is not None:
            if not isinstance(raw_metrics, dict):
                errors.append(f"{label}: {mid}.metrics must be an object")
            else:
                metrics = raw_metrics
        if raw_points is not None:
            if not isinstance(raw_points, list):
                errors.append(f"{label}: {mid}.points must be a list")
            else:
                points = raw_points
        if not metrics and not points:
            errors.append(f"{label}: {mid} has no metrics or points")
        for metric, values in metrics.items():
            if metric not in METRICS:
                errors.append(f"{label}: {mid} uses unknown metric {metric}")
            if (
                not isinstance(values, list)
                or not values
                or any(not is_finite_number(value) for value in values)
            ):
                errors.append(f"{label}: {mid}.{metric} must be a non-empty finite numeric list")
        for index, point in enumerate(points):
            if not isinstance(point, dict):
                errors.append(f"{label}: {mid}.points[{index}] must be an object")
                continue
            if not is_finite_number(point.get("x")):
                errors.append(f"{label}: {mid}.points[{index}] needs finite numeric x")
            point_metrics = [metric for metric in METRICS if metric in point]
            if not point_metrics:
                errors.append(f"{label}: {mid}.points[{index}] has no recognized metric")
            for metric in point_metrics:
                if not is_finite_number(point.get(metric)):
                    errors.append(f"{label}: {mid}.points[{index}].{metric} must be finite numeric")

        annotations = measurement.get("sample_annotations")
        if annotations is None:
            annotations = []
        elif not isinstance(annotations, list):
            errors.append(f"{label}: {mid}.sample_annotations must be a list")
            annotations = []
        for index, annotation in enumerate(annotations):
            metric = annotation.get("metric") if isinstance(annotation, dict) else None
            sample_index = annotation.get("index") if isinstance(annotation, dict) else None
            if (
                metric not in metrics
                or not isinstance(sample_index, int)
                or isinstance(sample_index, bool)
            ):
                errors.append(f"{label}: {mid}.sample_annotations[{index}] has invalid metric/index")
                continue
            values = metrics.get(metric)
            if (
                not isinstance(values, list)
                or not 0 <= sample_index < len(values)
                or not isinstance(annotation.get("label"), str)
                or not annotation.get("label")
            ):
                errors.append(f"{label}: {mid}.sample_annotations[{index}] is out of range or unlabeled")
            elif "value" in annotation and annotation.get("value") != values[sample_index]:
                errors.append(
                    f"{label}: {mid}.sample_annotations[{index}].value does not match the indexed sample"
                )

    errors.extend(
        validate_featured_results(
            featured_results,
            f"{label}: featured_results",
            measurements,
        )
    )

    packet_ids: set[str] = set()
    packet_by_id: dict[str, dict[str, Any]] = {}
    for packet in packets:
        packet_id = packet.get("id")
        if not isinstance(packet_id, str) or not packet_id:
            errors.append(f"{label}: packet without id")
            continue
        if packet_id in packet_ids:
            errors.append(f"{label}: duplicate packet id {packet_id}")
        packet_ids.add(packet_id)
        packet_by_id.setdefault(packet_id, packet)
        revision = packet.get("revision")
        if not isinstance(revision, str) or revision not in declared_revision_ids:
            errors.append(f"{label}: packet {packet_id} references unknown revision {revision}")
        artifact_id = packet.get("artifact_id")
        if revision in artifact_bound_revision_ids and (
            not isinstance(packet.get("quantization"), str)
            or not packet.get("quantization")
        ):
            errors.append(
                f"{label}: packet {packet_id} must name its canonical quantization for artifact-bound revision {revision}"
            )
        if revision in artifact_bound_revision_ids and artifact_id is None:
            errors.append(
                f"{label}: packet {packet_id} must name a quantized artifact for revision {revision}"
            )
        elif artifact_id is not None:
            if not isinstance(artifact_id, str) or artifact_id not in artifacts_by_id:
                errors.append(
                    f"{label}: packet {packet_id} references unknown quantized artifact {artifact_id}"
                )
            else:
                if artifact_revision_ids[artifact_id] != revision:
                    errors.append(
                        f"{label}: packet {packet_id} artifact {artifact_id} does not belong to revision {revision}"
                    )
                artifact_quant = artifacts_by_id[artifact_id].get("quantization")
                if packet.get("quantization") != artifact_quant:
                    errors.append(
                        f"{label}: packet {packet_id} quantization does not match artifact {artifact_id}"
                    )
        grades = packet.get("grades")
        if grades is not None and not isinstance(grades, dict):
            errors.append(f"{label}: packet {packet_id} grades must be an object")
            grades = {}
        for grade_name in ("capability", "evidence"):
            errors.extend(
                validate_grade(
                    (grades or {}).get(grade_name),
                    f"{label}: packet {packet_id} {grade_name} grade",
                )
            )

        manifest = packet.get("manifest")
        manifest_path = safe_repo_path(manifest)
        package_backed = (
            isinstance(manifest, str)
            and manifest.startswith("packages/")
            and manifest.endswith("package.json")
        )
        if manifest_path is None:
            errors.append(f"{label}: packet {packet_id} manifest must stay inside the repository")
        errors.extend(
            validate_featured_metric(
                packet.get("featured_metric"),
                f"{label}: packet {packet_id} featured_metric",
                measurements,
                package_backed,
            )
        )
        if package_backed and manifest_path is not None:
            try:
                package = load_json(manifest_path)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                errors.append(str(error))
            else:
                if package.get("id") != packet_id:
                    errors.append(
                        f"{label}: packet {packet_id} does not match manifest id {package.get('id')}"
                    )

        projection = packet.get("projection")
        if projection is not None:
            projection_label = f"{label}: packet {packet_id} projection"
            if not isinstance(projection, dict):
                errors.append(f"{projection_label} must be an object")
            else:
                for field in ("model", "quant", "runtime"):
                    if not isinstance(projection.get(field), str) or not projection.get(field):
                        errors.append(f"{projection_label}.{field} is required")
                prompt = projection.get("prompt_tokens")
                output = projection.get("output_tokens")
                if (prompt is None) != (output is None):
                    errors.append(
                        f"{projection_label} must set prompt_tokens and output_tokens together"
                    )
                for field, value in (("prompt_tokens", prompt), ("output_tokens", output)):
                    if value is not None and (
                        not isinstance(value, int) or isinstance(value, bool) or value <= 0
                    ):
                        errors.append(f"{projection_label}.{field} must be a positive integer")

    primary_packet_id = family.get("primary_packet_id")
    if packets:
        if not isinstance(primary_packet_id, str) or not primary_packet_id:
            errors.append(f"{label}: families with packets need primary_packet_id")
        elif primary_packet_id not in packet_by_id:
            errors.append(
                f"{label}: primary_packet_id references missing packet {primary_packet_id}"
            )
    elif primary_packet_id is not None:
        errors.append(f"{label}: primary_packet_id is set but the family has no packets")

    estimate_ids: set[str] = set()
    estimate_by_id: dict[str, dict[str, Any]] = {}
    for estimate in estimates:
        estimate_id = estimate.get("id")
        estimate_label = f"{label}: estimate {estimate_id or '<missing>'}"
        if not isinstance(estimate_id, str) or not estimate_id:
            errors.append(f"{label}: estimate without id")
            continue
        if estimate_id in estimate_ids or estimate_id in measurement_ids:
            errors.append(f"{label}: duplicate estimate id {estimate_id}")
        estimate_ids.add(estimate_id)
        estimate_by_id.setdefault(estimate_id, estimate)
        if estimate.get("state") != "estimated":
            errors.append(f"{estimate_label} must have state estimated")
        selectors = estimate.get("selectors")
        if not isinstance(selectors, dict) or not selectors:
            errors.append(f"{estimate_label} needs non-empty selectors")
        elif any(
            not isinstance(key, str)
            or not SELECTOR_KEY_RE.fullmatch(key)
            or not is_selector_scalar(value)
            for key, value in selectors.items()
        ):
            errors.append(f"{estimate_label}.selectors must be scalar selector key/value pairs")
        if isinstance(selectors, dict):
            selector_revision = selectors.get("revision")
            selector_artifact = selectors.get("artifact_id")
            if (
                selector_revision in artifact_bound_revision_ids
                and selector_artifact is None
            ):
                errors.append(
                    f"{estimate_label} must bind quantized artifact for revision {selector_revision}"
                )
            if selector_artifact is not None:
                if (
                    not isinstance(selector_artifact, str)
                    or selector_artifact not in artifacts_by_id
                ):
                    errors.append(
                        f"{estimate_label} references unknown quantized artifact {selector_artifact}"
                    )
                else:
                    if (
                        isinstance(selector_revision, str)
                        and artifact_revision_ids[selector_artifact]
                        != selector_revision
                    ):
                        errors.append(
                            f"{estimate_label} artifact {selector_artifact} does not belong to revision {selector_revision}"
                        )
                    selector_quant = selectors.get("quantization")
                    if (
                        selector_quant is not None
                        and selector_quant
                        != artifacts_by_id[selector_artifact].get("quantization")
                    ):
                        errors.append(
                            f"{estimate_label} quantization {selector_quant} does not match artifact {selector_artifact}"
                        )
        metric = estimate.get("metric")
        if metric not in METRICS:
            errors.append(f"{estimate_label} uses unknown metric {metric}")
        elif estimate.get("unit") != METRICS[metric][1]:
            errors.append(f"{estimate_label}.unit must equal {METRICS[metric][1]}")
        value = estimate.get("value")
        interval = estimate.get("interval")
        if not is_finite_number(value):
            errors.append(f"{estimate_label}.value must be finite numeric")
        if not isinstance(interval, dict) or not all(
            is_finite_number(interval.get(bound)) for bound in ("low", "high")
        ):
            errors.append(f"{estimate_label} needs finite numeric interval.low/high")
        elif interval["low"] > interval["high"]:
            errors.append(f"{estimate_label}.interval low must not exceed high")
        elif is_finite_number(value) and not interval["low"] <= value <= interval["high"]:
            errors.append(f"{estimate_label}.value must fall within its interval")
        engine = estimate.get("engine")
        if not isinstance(engine, dict) or not all(
            isinstance(engine.get(field), str) and engine.get(field)
            for field in ("name", "version", "snapshot_sha256")
        ):
            errors.append(f"{estimate_label} needs engine name/version/snapshot_sha256")
        elif not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", engine["snapshot_sha256"]):
            errors.append(
                f"{estimate_label}.engine.snapshot_sha256 must be a lowercase SHA-256"
            )
        if not isinstance(estimate.get("generated_at"), str) or not estimate.get("generated_at"):
            errors.append(f"{estimate_label} needs generated_at")
        if safe_repo_path(estimate.get("record")) is None:
            errors.append(f"{estimate_label}.record must stay inside the repository")
        basis = estimate.get("basis_measurement_ids")
        if not isinstance(basis, list) or not basis:
            errors.append(f"{estimate_label} needs basis_measurement_ids")
        else:
            for mid in basis:
                if not isinstance(mid, str) or mid not in measurement_ids:
                    errors.append(f"{estimate_label} references missing basis {mid}")
        if estimate.get("not_for_promotion") is not True:
            errors.append(f"{estimate_label}.not_for_promotion must be true")
        if not isinstance(estimate.get("limitations"), str) or not estimate.get("limitations"):
            errors.append(f"{estimate_label} needs limitations")
        supersedes = estimate.get("supersedes")
        if supersedes and supersedes not in estimate_ids:
            errors.append(f"{estimate_label} supersedes unknown or later estimate {supersedes}")

    view_ids: set[str] = set()
    for view in views:
        view_id = view.get("id")
        if not isinstance(view_id, str) or not SLUG_RE.fullmatch(view_id):
            errors.append(f"{label}: view id must be a lowercase hyphenated slug")
            view_id = str(view_id)
        if view_id in view_ids:
            errors.append(f"{label}: duplicate view id {view_id}")
        view_ids.add(view_id)
        view_metrics = view.get("metrics")
        if not isinstance(view_metrics, list) or not view_metrics:
            errors.append(f"{label}: view {view_id} metrics must be a non-empty list")
            view_metrics = []
        for metric in view_metrics:
            if metric not in METRICS:
                errors.append(f"{label}: view {view_id} uses unknown metric {metric}")
        for field in ("missing_x", "unsupported_x"):
            values = view.get(field)
            if values is not None and (
                not isinstance(values, list)
                or any(not is_finite_number(value) for value in values)
            ):
                errors.append(f"{label}: view {view_id}.{field} must be a finite numeric list")
        view_series = object_list(view.get("series"), f"{label}: view {view_id} series", errors)
        for series in view_series:
            mids = series.get("measurement_ids")
            if not isinstance(mids, list) or not mids:
                errors.append(f"{label}: view {view_id} series needs measurement_ids")
                continue
            states = set()
            selected = []
            for mid in mids:
                if not isinstance(mid, str) or mid not in measurements:
                    errors.append(f"{label}: view {view_id} references missing {mid}")
                else:
                    selected.append(measurements[mid])
                    states.add(measurements[mid].get("state"))
            if states - CHARTABLE_STATES:
                errors.append(
                    f"{label}: view {view_id} series {series.get('label')} uses non-curve states {sorted(states - CHARTABLE_STATES)}"
                )
            if len(states) > 1:
                errors.append(
                    f"{label}: view {view_id} series {series.get('label')} mixes states {sorted(states)}"
                )
            if not view.get("discrete") and len(selected) > 1:
                x_from = series.get("x_from", "config.tp")
                if not isinstance(x_from, str) or not x_from:
                    errors.append(f"{label}: view {view_id} series x_from must be a string")
                else:
                    identities = [curve_identity(item, x_from) for item in selected]
                    if any(identity != identities[0] for identity in identities[1:]):
                        errors.append(
                            f"{label}: view {view_id} series {series.get('label')} mixes identities along a connected curve"
                        )

    initial_view_ids = family.get("initial_view_ids")
    if initial_view_ids is not None:
        if (
            not isinstance(initial_view_ids, list)
            or not initial_view_ids
            or any(not isinstance(view_id, str) for view_id in initial_view_ids)
        ):
            errors.append(f"{label}: initial_view_ids must be a non-empty string list")
        else:
            if len(set(initial_view_ids)) != len(initial_view_ids):
                errors.append(f"{label}: initial_view_ids must be unique")
            unknown_initial_views = set(initial_view_ids) - view_ids
            if unknown_initial_views:
                errors.append(
                    f"{label}: initial_view_ids reference unknown views {sorted(unknown_initial_views)}"
                )

    coverage_ids: set[str] = set()
    for coverage in coverage_views:
        coverage_id = coverage.get("id")
        if not isinstance(coverage_id, str) or not SLUG_RE.fullmatch(coverage_id):
            errors.append(f"{label}: coverage view id must be a lowercase hyphenated slug")
            coverage_id = str(coverage_id)
        if coverage_id in coverage_ids:
            errors.append(f"{label}: duplicate coverage view id {coverage_id}")
        coverage_ids.add(coverage_id)
        for side, values_key in (("row", "rows"), ("column", "columns")):
            supplied = coverage.get(f"{side}_axis")
            if supplied is not None and not isinstance(supplied, dict):
                errors.append(f"{label}: coverage {coverage_id} {side}_axis must be an object")
            if not isinstance(coverage.get(values_key), list):
                errors.append(f"{label}: coverage {coverage_id} {values_key} must be a list")
        row_axis = coverage_axis(coverage, "row")
        column_axis = coverage_axis(coverage, "column")
        axes_valid = True
        for side, axis in (("row", row_axis), ("column", column_axis)):
            values = axis["values"]
            key = axis.get("key")
            if not isinstance(key, str) or not SELECTOR_KEY_RE.fullmatch(key):
                errors.append(f"{label}: coverage {coverage_id} {side}_axis needs a selector key")
                axes_valid = False
            if not isinstance(axis.get("label"), str) or not axis.get("label"):
                errors.append(f"{label}: coverage {coverage_id} {side}_axis needs a label")
                axes_valid = False
            if "prefix" in axis and not isinstance(axis.get("prefix"), str):
                errors.append(f"{label}: coverage {coverage_id} {side}_axis prefix must be a string")
            if not values or any(not is_axis_scalar(value) for value in values):
                errors.append(
                    f"{label}: coverage {coverage_id} {side} values must be non-empty finite scalars without ':'"
                )
                axes_valid = False
            if len({str(value) for value in values}) != len(values):
                errors.append(f"{label}: coverage {coverage_id} {side} values must be unique")
                axes_valid = False
            value_labels = axis.get("value_labels")
            if value_labels is not None and (
                not isinstance(value_labels, dict)
                or set(value_labels) - {str(value) for value in values}
                or any(not isinstance(value, str) for value in value_labels.values())
            ):
                errors.append(f"{label}: coverage {coverage_id} {side}_axis has invalid value_labels")
        if row_axis.get("key") == column_axis.get("key"):
            errors.append(f"{label}: coverage {coverage_id} axes must use different keys")
            axes_valid = False
        named_axes = "row_axis" in coverage or "column_axis" in coverage
        fixed_selectors = coverage.get("fixed_selectors")
        if named_axes and (not isinstance(fixed_selectors, dict) or not fixed_selectors):
            errors.append(
                f"{label}: coverage {coverage_id} named axes need fixed_selectors (a non-empty object)"
            )
        if fixed_selectors is not None and not isinstance(fixed_selectors, dict):
            errors.append(f"{label}: coverage {coverage_id} fixed_selectors must be an object")
            fixed_selectors = {}
        if isinstance(fixed_selectors, dict):
            if row_axis.get("key") in fixed_selectors or column_axis.get("key") in fixed_selectors:
                errors.append(f"{label}: coverage {coverage_id} fixed_selectors cannot repeat an axis key")
            if any(
                not isinstance(key, str)
                or not SELECTOR_KEY_RE.fullmatch(key)
                or not is_selector_scalar(value)
                for key, value in fixed_selectors.items()
            ):
                errors.append(
                    f"{label}: coverage {coverage_id} fixed_selectors must be scalar selector key/value pairs"
                )
            selector_revision = fixed_selectors.get("revision")
            selector_artifact = fixed_selectors.get("artifact_id")
            artifact_axis = next(
                (
                    axis
                    for axis in (row_axis, column_axis)
                    if axis.get("key") == "artifact_id"
                ),
                None,
            )
            if selector_artifact is not None:
                if (
                    not isinstance(selector_artifact, str)
                    or selector_artifact not in artifacts_by_id
                ):
                    errors.append(
                        f"{label}: coverage {coverage_id} references unknown quantized artifact {selector_artifact}"
                    )
                elif (
                    isinstance(selector_revision, str)
                    and artifact_revision_ids[selector_artifact] != selector_revision
                ):
                    errors.append(
                        f"{label}: coverage {coverage_id} artifact {selector_artifact} does not belong to revision {selector_revision}"
                    )
            if artifact_axis is not None:
                for selector_artifact in artifact_axis["values"]:
                    if (
                        not isinstance(selector_artifact, str)
                        or selector_artifact not in artifacts_by_id
                    ):
                        errors.append(
                            f"{label}: coverage {coverage_id} axis references unknown quantized artifact {selector_artifact}"
                        )
                    elif (
                        isinstance(selector_revision, str)
                        and artifact_revision_ids[selector_artifact] != selector_revision
                    ):
                        errors.append(
                            f"{label}: coverage {coverage_id} artifact {selector_artifact} does not belong to revision {selector_revision}"
                        )

        expected = {
            f"{row}:{column}"
            for row in row_axis["values"]
            for column in column_axis["values"]
        } if axes_valid else set()
        cells = coverage.get("cells")
        if not isinstance(cells, dict):
            errors.append(f"{label}: coverage {coverage_id} cells must be an object")
            cells = {}
        if axes_valid and set(cells) != expected:
            errors.append(f"{label}: coverage {coverage_id} cells do not exactly match rows×columns")
        for cell_id, cell in cells.items():
            if not isinstance(cell_id, str):
                errors.append(f"{label}: coverage {coverage_id} cell keys must be strings")
                continue
            if not isinstance(cell, dict):
                errors.append(f"{label}: coverage {coverage_id} cell {cell_id} must be an object")
                continue
            cell_selectors = cell.get("selectors")
            if cell_selectors is not None and not isinstance(cell_selectors, dict):
                errors.append(
                    f"{label}: coverage {coverage_id} cell {cell_id}.selectors must be an object"
                )
                cell_selectors = {}
            if isinstance(cell_selectors, dict):
                if any(
                    not isinstance(key, str)
                    or not SELECTOR_KEY_RE.fullmatch(key)
                    or not is_selector_scalar(value)
                    for key, value in cell_selectors.items()
                ):
                    errors.append(
                        f"{label}: coverage {coverage_id} cell {cell_id}.selectors must be scalar selector key/value pairs"
                    )
                inherited_keys = set(fixed_selectors or {}) | {
                    row_axis.get("key"),
                    column_axis.get("key"),
                }
                repeated_keys = sorted(set(cell_selectors) & inherited_keys)
                if repeated_keys:
                    errors.append(
                        f"{label}: coverage {coverage_id} cell {cell_id}.selectors cannot repeat inherited keys {repeated_keys}"
                    )
            state = cell.get("state")
            if state not in ALLOWED_STATES:
                errors.append(f"{label}: coverage {coverage_id} cell {cell_id} has invalid state")
            evidence_id = cell.get("evidence_id")
            estimate_id = cell.get("estimate_id")
            packet_id = cell.get("packet_id")
            point_x = cell.get("point_x")
            observed = measurements.get(evidence_id) if isinstance(evidence_id, str) else None
            if evidence_id is not None and observed is None:
                errors.append(
                    f"{label}: coverage {coverage_id} cell {cell_id} references missing {evidence_id}"
                )
            if observed is not None and state != observed.get("state"):
                errors.append(
                    f"{label}: coverage {coverage_id} cell {cell_id} state {state} does not match {evidence_id} state {observed.get('state')}"
                )
            if packet_id is not None and packet_id not in packet_by_id:
                errors.append(
                    f"{label}: coverage {coverage_id} cell {cell_id} references missing packet {packet_id}"
                )
            if state in CURVE_STATES and observed is None:
                errors.append(
                    f"{label}: coverage {coverage_id} cell {cell_id} needs a measurement evidence_id"
                )
            if state == "estimated":
                if not isinstance(estimate_id, str) or estimate_id not in estimate_by_id:
                    errors.append(
                        f"{label}: coverage {coverage_id} cell {cell_id} needs a known estimate_id"
                    )
                if evidence_id:
                    errors.append(
                        f"{label}: coverage {coverage_id} cell {cell_id} cannot use evidence_id for an estimate"
                    )
            elif estimate_id is not None:
                errors.append(
                    f"{label}: coverage {coverage_id} cell {cell_id} uses estimate_id outside estimated state"
                )
            if state in {"lab-screened", "quarantined"} and not (
                evidence_id or cell.get("evidence") or coverage.get("evidence")
            ):
                errors.append(f"{label}: coverage {coverage_id} {state} cell {cell_id} lacks evidence")

            row_value = column_value = None
            if axes_valid and cell_id in expected:
                row_text, column_text = cell_id.split(":", 1)
                row_value = next(
                    value for value in row_axis["values"] if str(value) == row_text
                )
                column_value = next(
                    value for value in column_axis["values"] if str(value) == column_text
                )
            expected_selectors = (
                effective_cell_selectors(coverage, row_value, column_value, cell)
                if row_value is not None and column_value is not None
                else {}
            )
            selector_revision = expected_selectors.get("revision")
            selector_artifact = expected_selectors.get("artifact_id")
            if (
                selector_revision in artifact_bound_revision_ids
                and selector_artifact is None
            ):
                errors.append(
                    f"{label}: coverage {coverage_id} cell {cell_id} must bind quantized artifact for revision {selector_revision}"
                )
            if selector_artifact is not None:
                if (
                    not isinstance(selector_artifact, str)
                    or selector_artifact not in artifacts_by_id
                ):
                    errors.append(
                        f"{label}: coverage {coverage_id} cell {cell_id} references unknown quantized artifact {selector_artifact}"
                    )
                else:
                    if (
                        isinstance(selector_revision, str)
                        and artifact_revision_ids[selector_artifact]
                        != selector_revision
                    ):
                        errors.append(
                            f"{label}: coverage {coverage_id} cell {cell_id} artifact {selector_artifact} does not belong to revision {selector_revision}"
                        )
                    artifact_quant = artifacts_by_id[selector_artifact].get(
                        "quantization"
                    )
                    for quant_key in ("quantization", "variant"):
                        selector_quant = expected_selectors.get(quant_key)
                        if (
                            selector_quant is not None
                            and selector_quant != artifact_quant
                        ):
                            errors.append(
                                f"{label}: coverage {coverage_id} cell {cell_id} {quant_key}={selector_quant} does not match artifact {selector_artifact} ({artifact_quant})"
                            )
            if isinstance(packet_id, str) and packet_id in packet_by_id:
                packet = packet_by_id[packet_id]
                packet_claims = {
                    "revision": packet.get("revision"),
                    "artifact_id": packet.get("artifact_id"),
                    "variant": packet.get("quantization"),
                    "runtime": packet.get("runtime"),
                }
                for key, actual in packet_claims.items():
                    wanted = expected_selectors.get(key)
                    if wanted is not None and actual is not None and actual != wanted:
                        errors.append(
                            f"{label}: coverage {coverage_id} cell {cell_id} packet {packet_id} {key}={actual} mismatches selector {wanted}"
                        )
                wanted_tp = expected_selectors.get("tp")
                packet_cards = packet.get("cards")
                packet_topologies = packet.get("topologies")
                if wanted_tp is not None and (
                    (packet_cards is not None and packet_cards != wanted_tp)
                    or (
                        packet_cards is None
                        and isinstance(packet_topologies, list)
                        and wanted_tp not in packet_topologies
                    )
                ):
                    errors.append(
                        f"{label}: coverage {coverage_id} cell {cell_id} packet {packet_id} does not cover TP{wanted_tp}"
                    )
            if point_x is not None:
                if not is_finite_number(point_x):
                    errors.append(f"{label}: coverage {coverage_id} cell {cell_id}.point_x must be finite numeric")
                elif observed is None:
                    errors.append(f"{label}: coverage {coverage_id} cell {cell_id}.point_x needs measurement evidence")
                else:
                    point = next(
                        (
                            item
                            for item in (observed.get("points") or [])
                            if isinstance(item, dict) and item.get("x") == point_x
                        ),
                        None,
                    )
                    if point is None:
                        errors.append(
                            f"{label}: coverage {coverage_id} cell {cell_id}.point_x is absent from {evidence_id}"
                        )
                    axis_key = observed.get("axis")
                    axis_matches = [
                        wanted
                        for key, wanted in expected_selectors.items()
                        if key == axis_key and wanted == point_x
                    ]
                    if not isinstance(axis_key, str) or len(axis_matches) != 1:
                        errors.append(
                            f"{label}: coverage {coverage_id} cell {cell_id}.point_x must bind {evidence_id} measurement axis"
                        )
                    derived_label = point_metric_label(point) if point is not None else ""
                    if cell.get("label") != derived_label:
                        errors.append(
                            f"{label}: coverage {coverage_id} cell {cell_id} label must match {evidence_id} point ({derived_label})"
                        )

            selector_strict = named_axes or bool(fixed_selectors) or bool(cell_selectors)
            if observed is not None:
                for key, wanted in expected_selectors.items():
                    actual = record_selector_value(observed, key)
                    point_selector_match = (
                        point_x is not None
                        and observed.get("axis") == key
                        and point_x == wanted
                    )
                    if selector_strict and actual is None and not point_selector_match:
                        errors.append(
                            f"{label}: coverage {coverage_id} cell {cell_id} selector {key}={wanted} is absent from {evidence_id}"
                        )
                    elif actual is not None and actual != wanted:
                        errors.append(
                            f"{label}: coverage {coverage_id} cell {cell_id} selector {key}={wanted} mismatches {evidence_id} value {actual}"
                        )
            if isinstance(estimate_id, str) and estimate_id in estimate_by_id:
                estimate = estimate_by_id[estimate_id]
                for key, wanted in expected_selectors.items():
                    actual = (estimate.get("selectors") or {}).get(key)
                    if actual != wanted:
                        errors.append(
                            f"{label}: coverage {coverage_id} cell {cell_id} selector {key}={wanted} mismatches {estimate_id} value {actual}"
                        )

    contract_ids: set[str] = set()
    for contract in coverage_contracts:
        contract_id = contract.get("id")
        if not isinstance(contract_id, str) or not SLUG_RE.fullmatch(contract_id):
            errors.append(
                f"{label}: coverage contract id must be a lowercase hyphenated slug"
            )
            contract_id = str(contract_id)
        if contract_id in contract_ids or contract_id in coverage_ids:
            errors.append(f"{label}: duplicate coverage id {contract_id}")
        contract_ids.add(contract_id)
        contract_label = f"{label}: coverage contract {contract_id}"
        if not isinstance(contract.get("label"), str) or not contract.get("label"):
            errors.append(f"{contract_label} needs a label")
        if "description" in contract and not isinstance(contract.get("description"), str):
            errors.append(f"{contract_label}.description must be a string")
        contract_cells, contract_errors = expand_coverage_contract(
            contract, contract_label
        )
        errors.extend(contract_errors)
        for cell in contract_cells:
            selectors = cell["selectors"]
            selector_text = json.dumps(
                selectors, sort_keys=True, separators=(",", ":")
            )
            cell_label = f"{contract_label} cell {selector_text}"
            state = cell.get("state")
            evidence_id = cell.get("evidence_id")
            estimate_id = cell.get("estimate_id")
            packet_id = cell.get("packet_id")
            observed = (
                measurements.get(evidence_id)
                if isinstance(evidence_id, str)
                else None
            )
            if evidence_id is not None and observed is None:
                errors.append(f"{cell_label} references missing {evidence_id}")
            if observed is not None and state != observed.get("state"):
                errors.append(
                    f"{cell_label} state {state} does not match {evidence_id} state {observed.get('state')}"
                )
            if packet_id is not None and packet_id not in packet_by_id:
                errors.append(f"{cell_label} references missing packet {packet_id}")
            if isinstance(packet_id, str) and packet_id in packet_by_id:
                packet = packet_by_id[packet_id]
                packet_claims = {
                    "revision": packet.get("revision"),
                    "artifact_id": packet.get("artifact_id"),
                    "quantization": packet.get("quantization"),
                    "runtime": packet.get("runtime"),
                }
                for key, actual in packet_claims.items():
                    wanted = selectors.get(key)
                    if wanted is not None and actual is not None and actual != wanted:
                        errors.append(
                            f"{cell_label} packet {packet_id} {key}={actual} mismatches selector {wanted}"
                        )
                wanted_tp = selectors.get("tp")
                packet_cards = packet.get("cards")
                packet_topologies = packet.get("topologies")
                if wanted_tp is not None and (
                    (packet_cards is not None and packet_cards != wanted_tp)
                    or (
                        packet_cards is None
                        and isinstance(packet_topologies, list)
                        and wanted_tp not in packet_topologies
                    )
                ):
                    errors.append(
                        f"{cell_label} packet {packet_id} does not cover TP{wanted_tp}"
                    )
            if state in CURVE_STATES and observed is None:
                errors.append(f"{cell_label} needs a measurement evidence_id")
            if state == "estimated":
                if not isinstance(estimate_id, str) or estimate_id not in estimate_by_id:
                    errors.append(f"{cell_label} needs a known estimate_id")
                if evidence_id is not None:
                    errors.append(f"{cell_label} cannot use evidence_id for an estimate")
            elif estimate_id is not None:
                errors.append(f"{cell_label} uses estimate_id outside estimated state")
            if state in {"lab-screened", "quarantined"} and not (
                observed is not None or cell.get("evidence")
            ):
                errors.append(f"{cell_label} lacks evidence")

            selector_revision = selectors.get("revision")
            selector_artifact = selectors.get("artifact_id")
            if (
                selector_revision in artifact_bound_revision_ids
                and selector_artifact is None
            ):
                errors.append(
                    f"{cell_label} must bind quantized artifact for revision {selector_revision}"
                )
            if selector_artifact is not None:
                if (
                    not isinstance(selector_artifact, str)
                    or selector_artifact not in artifacts_by_id
                ):
                    errors.append(
                        f"{cell_label} references unknown quantized artifact {selector_artifact}"
                    )
                else:
                    if (
                        isinstance(selector_revision, str)
                        and artifact_revision_ids[selector_artifact]
                        != selector_revision
                    ):
                        errors.append(
                            f"{cell_label} artifact {selector_artifact} does not belong to revision {selector_revision}"
                        )
                    artifact_quant = artifacts_by_id[selector_artifact].get(
                        "quantization"
                    )
                    for quant_key in ("quantization", "variant"):
                        selector_quant = selectors.get(quant_key)
                        if selector_quant is not None and selector_quant != artifact_quant:
                            errors.append(
                                f"{cell_label} {quant_key}={selector_quant} does not match artifact {selector_artifact} ({artifact_quant})"
                            )

            selector_speculator = selectors.get("speculator_artifact_id")
            if selector_speculator is not None:
                if (
                    not isinstance(selector_speculator, str)
                    or selector_speculator not in artifacts_by_id
                ):
                    errors.append(
                        f"{cell_label} references unknown speculator artifact {selector_speculator}"
                    )
                elif (
                    isinstance(selector_revision, str)
                    and artifact_revision_ids[selector_speculator]
                    != selector_revision
                ):
                    errors.append(
                        f"{cell_label} speculator artifact {selector_speculator} does not belong to revision {selector_revision}"
                    )
                elif artifacts_by_id[selector_speculator].get("role") != "speculator":
                    errors.append(
                        f"{cell_label} speculator artifact {selector_speculator} is not declared with role=speculator"
                    )

            point_x = cell.get("point_x")
            point_axis = observed.get("axis") if observed is not None else None
            if point_x is not None:
                if not is_finite_number(point_x):
                    errors.append(f"{cell_label}.point_x must be finite numeric")
                elif observed is None:
                    errors.append(f"{cell_label}.point_x needs measurement evidence")
                elif not any(
                    isinstance(point, dict) and point.get("x") == point_x
                    for point in observed.get("points") or []
                ):
                    errors.append(
                        f"{cell_label}.point_x is absent from {evidence_id}"
                    )
                elif selectors.get(point_axis) != point_x:
                    errors.append(
                        f"{cell_label}.point_x must bind {evidence_id} measurement axis"
                    )
            if observed is not None:
                for key, wanted in selectors.items():
                    actual = record_selector_value(observed, key)
                    point_selector_match = (
                        point_x is not None
                        and point_axis == key
                        and point_x == wanted
                    )
                    if actual is None and not point_selector_match:
                        errors.append(
                            f"{cell_label} selector {key}={wanted} is absent from {evidence_id}"
                        )
                    elif actual is not None and actual != wanted:
                        errors.append(
                            f"{cell_label} selector {key}={wanted} mismatches {evidence_id} value {actual}"
                        )
            if isinstance(estimate_id, str) and estimate_id in estimate_by_id:
                estimate_selectors = estimate_by_id[estimate_id].get("selectors") or {}
                for key, wanted in selectors.items():
                    if estimate_selectors.get(key) != wanted:
                        errors.append(
                            f"{cell_label} selector {key}={wanted} mismatches {estimate_id} value {estimate_selectors.get(key)}"
                        )

    for closure in closures:
        if closure.get("state") not in ALLOWED_STATES:
            errors.append(f"{label}: family closure has invalid state {closure.get('state')}")
        selectors = closure.get("selectors")
        if not isinstance(selectors, dict) or not selectors or any(
            not isinstance(key, str)
            or not SELECTOR_KEY_RE.fullmatch(key)
            or not is_selector_scope(value)
            for key, value in (selectors or {}).items()
        ):
            errors.append(f"{label}: family closure needs scalar selectors")
        if not isinstance(closure.get("reason"), str) or not closure.get("reason"):
            errors.append(f"{label}: family closure needs a reason")
        if not isinstance(closure.get("evidence"), str) or not closure.get("evidence"):
            errors.append(f"{label}: family closure needs evidence")
        if isinstance(selectors, dict):
            selector_revision = selectors.get("revision")
            selector_artifact = selectors.get("artifact_id")
            if (
                selector_revision in artifact_bound_revision_ids
                and selector_artifact is None
            ):
                errors.append(
                    f"{label}: family closure must bind quantized artifact for revision {selector_revision}"
                )
            if selector_artifact is not None:
                if (
                    not isinstance(selector_artifact, str)
                    or selector_artifact not in artifacts_by_id
                ):
                    errors.append(
                        f"{label}: family closure references unknown quantized artifact {selector_artifact}"
                    )
                elif (
                    isinstance(selector_revision, str)
                    and artifact_revision_ids[selector_artifact] != selector_revision
                ):
                    errors.append(
                        f"{label}: family closure artifact {selector_artifact} does not belong to revision {selector_revision}"
                    )

    for rel in local_evidence_paths(family):
        path = safe_repo_path(rel)
        if path is None:
            errors.append(f"{label}: evidence path must stay inside the repository: {rel}")
        elif not path.is_file():
            errors.append(f"{label}: evidence path is not a file: {rel}")
    return errors


def collect_view_series(
    family: dict[str, Any], view: dict[str, Any], metric: str
) -> list[dict[str, Any]]:
    by_id = {
        measurement["id"]: measurement
        for measurement in records(family)
    }
    output: list[dict[str, Any]] = []
    for index, spec in enumerate(view.get("series") or []):
        points: list[dict[str, Any]] = []
        evidence: list[str] = []
        states: set[str] = set()
        for mid in spec.get("measurement_ids") or []:
            measurement = by_id[mid]
            states.add(measurement.get("state", "lab-measured"))
            if measurement.get("state") not in CHARTABLE_STATES:
                continue
            evidence.append(measurement["evidence"])
            if measurement.get("points"):
                for point in measurement["points"]:
                    value = point.get(metric)
                    if isinstance(value, (int, float)):
                        points.append({"x": float(point["x"]), "values": [float(value)]})
            else:
                values = (measurement.get("metrics") or {}).get(metric)
                x_value = nested(measurement, spec.get("x_from", "config.tp"))
                if values and isinstance(x_value, (int, float)):
                    points.append(
                        {
                            "x": float(x_value),
                            "values": [float(value) for value in values],
                        }
                    )
        points.sort(key=lambda point: point["x"])
        if points:
            output.append(
                {
                    "label": spec.get("label", f"series {index + 1}"),
                    "points": points,
                    "state": next(iter(states)),
                    "color": COLORS[index % len(COLORS)],
                    "evidence": list(dict.fromkeys(evidence)),
                }
            )
    return output


def chart_svg(
    family: dict[str, Any], view: dict[str, Any], metric: str, visible: bool
) -> tuple[str, str]:
    series = collect_view_series(family, view, metric)
    if not series:
        return "", ""
    x_values = [point["x"] for item in series for point in item["points"]]
    x_values += [float(value) for value in view.get("missing_x") or []]
    x_values += [float(value) for value in view.get("unsupported_x") or []]
    y_values = [value for item in series for point in item["points"] for value in point["values"]]
    if not x_values or not y_values:
        return "", ""

    width, height = 620, 250
    left, right, top, bottom = 54, 18, 18, 42
    x0, x1 = min(x_values), max(x_values)
    y0 = 0.0
    y1 = max(y_values) * 1.12
    if y1 <= 0:
        y1 = 1.0

    # A log x-axis (view: "x_scale": "log") keeps geometric level sweeps
    # (1, 2, 4, ... 64 users) evenly spaced instead of bunched at the left.
    log_x = view.get("x_scale") == "log"

    def x_key(value: float) -> float:
        if log_x:
            return math.log2(max(value, 1e-9))
        return value

    kx0, kx1 = x_key(x0), x_key(x1)

    def sx(value: float) -> float:
        if kx1 == kx0:
            return (left + width - right) / 2
        return left + (x_key(value) - kx0) / (kx1 - kx0) * (width - left - right)

    def sy(value: float) -> float:
        return top + (1 - (value - y0) / (y1 - y0)) * (height - top - bottom)

    label, unit = METRICS[metric]
    lines = [
        f'<svg class="family-chart" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(view.get("title"))}: {esc(label)}">'
    ]
    for fraction in (0, 0.25, 0.5, 0.75, 1):
        value = y1 * fraction
        y = sy(value)
        lines.append(
            f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}"></line>'
            f'<text class="lbl" x="{left-7}" y="{y+4:.1f}" text-anchor="end">{esc(fmt(value, 1))}</text>'
        )
    for x_value in sorted(set(x_values)):
        lines.append(
            f'<text class="lbl" x="{sx(x_value):.1f}" y="{height-18}" text-anchor="middle">{esc(fmt_x(x_value))}</text>'
        )
    lines.append(
        f'<text class="lbl" x="{left}" y="{height-3}">{esc(view.get("x_label", ""))} · {esc(unit)}</text>'
    )
    for item in series:
        drawable = []
        for point in item["points"]:
            mean = sum(point["values"]) / len(point["values"])
            drawable.append(
                (
                    point["x"],
                    mean,
                    min(point["values"]),
                    max(point["values"]),
                    point["values"],
                )
            )
        path = " ".join(
            f'{"M" if index == 0 else "L"}{sx(x):.1f},{sy(mean):.1f}'
            for index, (x, mean, _low, _high, _values) in enumerate(drawable)
        )
        if not view.get("discrete") and len(drawable) > 1:
            lines.append(
                f'<path d="{path}" fill="none" stroke="{item["color"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>'
            )
        for x, mean, low, high, source_values in drawable:
            if high > low:
                lines.append(
                    f'<line x1="{sx(x):.1f}" y1="{sy(low):.1f}" x2="{sx(x):.1f}" y2="{sy(high):.1f}" stroke="{item["color"]}" stroke-width="5" stroke-linecap="round"></line>'
                )
            measured_values = ", ".join(exact_number(value) for value in source_values)
            value_word = "value" if len(source_values) == 1 else "values"
            tooltip = (
                f'{item["label"]} · {label} ({metric}) · '
                f'{view.get("x_label") or "x"}={exact_number(x)} · '
                f'{value_word}={measured_values} {unit}'
            )
            lines.append(
                f'<circle cx="{sx(x):.1f}" cy="{sy(mean):.1f}" r="4" fill="var(--paper)" stroke="{item["color"]}" stroke-width="2.5">'
                f'<title>{esc(tooltip)}</title></circle>'
            )
    for missing in view.get("missing_x") or []:
        lines.append(
            f'<circle cx="{sx(float(missing)):.1f}" cy="{sy(0):.1f}" r="5" fill="var(--paper)" stroke="var(--muted)" stroke-width="2" stroke-dasharray="2 2"></circle>'
            f'<text class="lbl" x="{sx(float(missing)):.1f}" y="{sy(0)-10:.1f}" text-anchor="middle">gap</text>'
        )
    for unsupported in view.get("unsupported_x") or []:
        x = sx(float(unsupported))
        y = sy(0)
        lines.append(
            f'<path d="M{x-5:.1f},{y-5:.1f} L{x+5:.1f},{y+5:.1f} M{x+5:.1f},{y-5:.1f} L{x-5:.1f},{y+5:.1f}" stroke="var(--muted)" stroke-width="2"></path>'
            f'<text class="lbl" x="{x:.1f}" y="{y-12:.1f}" text-anchor="middle">unsupported</text>'
        )
    lines.append("</svg>")

    summaries = []
    for item in series:
        values = []
        for point in item["points"]:
            low, high = min(point["values"]), max(point["values"])
            shown = fmt(low) if low == high else f"{fmt(low)}–{fmt(high)}"
            values.append(f"{fmt_x(point['x'])}: {shown}")
        summaries.append(f"<b>{esc(item['label'])}</b> " + " · ".join(values))
    return "".join(lines), "<br>".join(summaries)


def view_stat_rows(family: dict[str, Any], view: dict[str, Any]) -> str:
    """Render small views as complete metric rows rather than tiny charts."""

    by_id = {measurement["id"]: measurement for measurement in records(family)}
    rows: list[str] = []
    view_metrics = list(view.get("metrics") or [])
    for series in view.get("series") or []:
        for mid in series.get("measurement_ids") or []:
            measurement = by_id.get(mid)
            if not measurement:
                continue
            source_rows: list[tuple[Any, dict[str, Any]]] = []
            points = measurement.get("points") or []
            if points:
                source_rows.extend(
                    (point.get("x"), point)
                    for point in points
                    if isinstance(point, dict)
                )
            else:
                source_rows.append(
                    (
                        nested(measurement, series.get("x_from", "config.tp")),
                        measurement.get("metrics") or {},
                    )
                )
            for x_value, source in source_rows:
                metric_items = []
                for metric in view_metrics:
                    raw = source.get(metric)
                    values = raw if isinstance(raw, list) else [raw]
                    values = [value for value in values if is_finite_number(value)]
                    if not values:
                        continue
                    low, high = min(values), max(values)
                    shown = fmt(low) if low == high else f"{fmt(low)}–{fmt(high)}"
                    metric_label, unit = METRICS[metric]
                    metric_items.append(
                        f'<span class="stat-metric"><b>{esc(shown)}</b>'
                        f'<span class="u">{esc(unit)}</span>'
                        f'<small>{esc(metric_label)}</small></span>'
                    )
                if not metric_items:
                    continue
                label = str(series.get("label") or measurement.get("variant") or mid)
                if x_value is not None:
                    label += f" · {view.get('x_label') or 'point'} {fmt_x(x_value) if is_finite_number(x_value) else x_value}"
                meta_bits = []
                declared_scope = measurement.get("measurement_class")
                if declared_scope:
                    meta_bits.append(esc(str(declared_scope).replace("-", " ")))
                promotion = measurement.get("promotion_status")
                if promotion:
                    meta_bits.append(esc(str(promotion).replace("-", " ")))
                state = measurement.get("state")
                if state == "lab-screened":
                    meta_bits.append("screened, not fully qualified")
                elif state == "community-measured":
                    meta_bits.append("community measurement")
                elif not meta_bits:
                    meta_bits.append("lab measurement; quality scope in evidence")
                evidence = measurement.get("evidence")
                if evidence:
                    meta_bits.append(
                        f'<a class="inline" href="{esc(evidence_href(evidence))}">evidence</a>'
                    )
                explicitly_superseded = measurement.get("superseded") is True or (
                    isinstance(promotion, str) and "superseded" in promotion.casefold()
                )
                rows.append(
                    f'<div class="stat-row{" is-superseded" if explicitly_superseded else ""}">'
                    f'<span class="l">{esc(label)}</span>'
                    f'<span class="stat-values">{"".join(metric_items)}</span>'
                    f'<span class="m">{" · ".join(meta_bits)}</span></div>'
                )
    return "".join(rows)


def view_point_count(family: dict[str, Any], view: dict[str, Any]) -> int:
    by_id = {measurement["id"]: measurement for measurement in records(family)}
    xs = set()
    for series in view.get("series") or []:
        for mid in series.get("measurement_ids") or []:
            measurement = by_id.get(mid)
            if not measurement:
                continue
            points = measurement.get("points") or []
            if points:
                xs.update(point.get("x") for point in points)
            else:
                xs.add(mid)
    return len(xs)


VIEW_TITLE_WORDS = {
    "strict rapid operating point": "Measured speed (quick lab check)",
    "strict tp4+ep dspark7 suites": "Measured speed on four cards",
    "active-context service profile": "Speed as the conversation grows",
    "qualified short-record history": "Record history",
    "qualified record progression": "How the record improved",
    "historical dflash efficiency evidence": "Draft-model efficiency (earlier runs)",
    "serving repeat": "Repeat runs",
    "active context depth": "Speed as the conversation grows",
    "deployment profiles": "Deployment options",
    "32k endpoint observation": "Speed at a 32K-token conversation",
    "production service observations": "Speed in real service",
    "prompt processing": "Prompt processing speed",
    "measured quantization variants": "Compression options compared",
    "q8 canonical classes": "Q8 prompt classes",
    "quantization and topology profiles": "Compression and card-count options",
    "bf16 kernel-campaign closeout": "Uncompressed (BF16) results",
    "one card beats layer split": "One card vs. a two-card layer split",
    "context-depth profile": "Speed as the conversation grows",
    "measured context profiles": "Speed as the conversation grows",
    "accepted 35b optimization over context": "Tuned 35B speed as the conversation grows",
    "35b stock card count": "35B: stock software by card count",
    "35b accepted-stack batching capacity": "35B: many users at once",
    "measured mini quantization variants": "Compression options compared",
    "tp strict runtime profiles": "Card count (fully checked runs)",
    "tp diagnostic runtime profiles": "Card count (quick checks)",
    "tp changes more than decode": "What changes with card count",
    "pinned e9d1398 mtp depth": "Draft depth (one pinned build)",
    "qwen3.6 mtp ladder": "Qwen3.6 draft-depth ladder",
    "qwen3.6 mtp5 capture screen": "Qwen3.6 draft depth 5 (quick check)",
    "qwen3.6 mtp3 historical vs current": "Qwen3.6 draft depth 3: then vs. now",
    "qwen3.6 q4_0 intrinsic mtp": "Qwen3.6 Q4_0 with its built-in draft",
    "qwen3.6 q4_0 dflash5 top-1 fusion": "Qwen3.6 Q4_0 with a DFlash draft",
    "qwen3.6 ud-q4_k_xl intrinsic mtp depth": "Qwen3.6 UD-Q4_K_XL draft depth",
    "qwen3.6 ud-q4_k_xl deep-mtp policy closure": "Qwen3.6 UD-Q4_K_XL deep draft (closed)",
    "qwen3.8 source-stack anchors": "Qwen3.8 by software build",
    "context x kv cache": "Conversation length x KV cache precision",
    "context \u00d7 kv cache": "Conversation length \u00d7 KV cache precision",
    "context x weight quant": "Conversation length x compression",
    "context \u00d7 weight quant": "Conversation length \u00d7 compression",
    "q5_k_s raw active context": "Q5_K_S as the conversation grows",
    "qwen3.6 q8 target-only context": "Qwen3.6 Q8 (no draft) as the conversation grows",
    "qwen3.6 q8 mtp3 matched control": "Qwen3.6 Q8 with draft depth 3",
    "qwen3.6 q8 long context": "Qwen3.6 Q8 at long context",
    "separately measured sibling variants": "Sibling models compared",
    "tp4 strict and historical identities": "Four-card results: current and earlier",
    "one card serving many users": "One card serving many users",
}


LABEL_WORDS = [
    (re.compile(r"\s*\u00b7\s*TP(\d) a[0-9a-f]{7,} winner overlay", re.I), lambda m: f" \u00b7 {m.group(1)} cards, tuned"),
    (re.compile(r"\bTP(\d)\s+strict result collection", re.I), lambda m: f"{m.group(1)} cards, fully checked"),
    (re.compile(r"\bstrict TP(\d)\b", re.I), lambda m: f"{m.group(1)} cards, fully checked"),
    (re.compile(r"\bTP(\d)\b\s*\u00b7\s*(vLLM XPU|llama\.cpp SYCL) target-only matrix", re.I), lambda m: f"{m.group(1)} card{'s' if m.group(1) != '1' else ''} \u00b7 {m.group(2)}, no draft model"),
    (re.compile(r"\btarget-only\b", re.I), lambda m: "no draft model"),
    (re.compile(r"\bstrict\b", re.I), lambda m: "fully checked"),
    (re.compile(r"\bdossier\b", re.I), lambda m: "record"),
    (re.compile(r"\bcloseout\b", re.I), lambda m: "final results"),
    (re.compile(r"\bscreen\b", re.I), lambda m: "quick check"),
]


def plain_label(text: str) -> str:
    out = str(text or "")
    for pattern, repl in LABEL_WORDS:
        out = pattern.sub(repl, out)
    return re.sub(r"\s{2,}", " ", out).strip()


def plain_view_title(title: str) -> str:
    key = re.sub(r"\s+", " ", str(title or "")).strip().lower()
    return VIEW_TITLE_WORDS.get(key, str(title or ""))


def view_card(family: dict[str, Any], view: dict[str, Any]) -> str:
    as_stats = view_point_count(family, view) < 3
    charts = []
    summaries = []
    fallback_rows = []
    buttons = []
    metric_list = list(view.get("metrics") or [])
    for index, metric in enumerate(metric_list):
        if as_stats:
            break
        svg, summary = chart_svg(family, view, metric, index == 0)
        if not svg:
            continue
        hidden_attr = "" if index == 0 else " hidden"
        charts.append(f'<div data-family-metric="{esc(metric)}"{hidden_attr}>{svg}</div>')
        summaries.append(
            f'<div data-family-summary="{esc(metric)}"{"" if index == 0 else " hidden"}>{summary}</div>'
        )
        label, _unit = METRICS[metric]
        fallback_rows.append(
            f'<tr><th scope="row">{esc(label)}</th><td>{summary}</td></tr>'
        )
        buttons.append(
            f'<button type="button" data-metric-button="{esc(metric)}" aria-pressed="{"true" if index == 0 else "false"}">{esc(label)}</button>'
        )
    if as_stats:
        charts = [view_stat_rows(family, view)]
        summaries = []
        fallback_rows = []
        buttons = []
    if len(buttons) < 2:
        buttons = []
    by_id_states = {measurement["id"]: measurement.get("state") for measurement in records(family)}
    states = {by_id_states.get(mid) for series in view.get("series") or [] for mid in series.get("measurement_ids") or []}
    view_flag = ' <span class="view-flag">\u25c7 screened, experimental</span>' if states and states <= {"lab-screened"} else ""
    evidence = []
    by_id = {
        measurement["id"]: measurement
        for measurement in records(family)
    }
    for series in view.get("series") or []:
        for mid in series.get("measurement_ids") or []:
            evidence.append(by_id[mid]["evidence"])
    evidence = list(dict.fromkeys(evidence))
    links = " · ".join(
        f'<a href="{esc(evidence_href(path))}">evidence {index + 1}</a>'
        for index, path in enumerate(evidence)
    )
    legends = []
    for index, series in enumerate(view.get("series") or []):
        legends.append(
            f'<span><i style="background:{COLORS[index % len(COLORS)]}"></i>{esc(series.get("label"))}</span>'
        )
    if view.get("missing_x"):
        legends.append('<span><i class="gap-line"></i>missing</span>')
    if view.get("unsupported_x"):
        legends.append('<span><i class="gap-line"></i>unsupported</span>')
    no_script_fallback = ""
    if len(fallback_rows) > 1:
        no_script_fallback = (
            '<noscript><table class="metric-fallback">'
            '<caption>All measured metric summaries</caption><tbody>'
            f'{"".join(fallback_rows)}</tbody></table></noscript>'
        )
    return f'''<figure class="chart family-view" data-family-view="{esc(view.get('id'))}">
  <div class="chart-head"><div><h3 title="{esc(view.get('title'))}">{esc(plain_view_title(view.get('title')))}{view_flag}</h3><p>{esc(view.get('subtitle'))}</p></div><div class="metric-switch">{"".join(buttons)}</div></div>
  {"".join(charts)}
  <div class="legend">{"".join(legends)}</div>
  <figcaption>{"".join(summaries)}{no_script_fallback}<span class="proof-links">{links}</span></figcaption>
</figure>'''


def axis_plain_words(axis: dict[str, Any], value: Any) -> str:
    """Translate an axis coordinate into visitor words; codes stay as a tag."""
    key = str(axis.get("key") or "").lower()
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = None
    if key == "tp" and number is not None:
        return f"{number} card{'s' if number != 1 else ''}"
    if key == "mtp" and number is not None:
        return "no speculative decoding" if number == 0 else f"+ speculative decoding (depth {number})"
    return axis_value_label(axis, value)


COMBO_STATE_WORDS = {
    "lab-measured": "\u2713 Measured",
    "lab-screened": "\u25c7 Speed check only",
    "community-measured": "\u25d0 Community",
    "estimated": "\u2248 Estimate",
    "closed": "\u25a0 Closed",
    "quarantined": "\u26a0 Quarantined",
    "unsupported": "\u00d7 Unsupported",
}
COMBO_ORDER = {"lab-measured": 0, "community-measured": 1, "lab-screened": 2, "estimated": 3, "closed": 4, "unsupported": 5, "quarantined": 9}


def coverage_tables(family: dict[str, Any]) -> str:
    """Show classified cells and keep every exact gap available on demand."""
    by_id = {measurement["id"]: measurement for measurement in records(family)}
    estimates = {estimate["id"]: estimate for estimate in family.get("estimates") or []}
    packets = {packet["id"]: packet for packet in family.get("packets") or []}
    blocks = []
    for view in family.get("coverage_views") or []:
        row_axis = coverage_axis(view, "row")
        column_axis = coverage_axis(view, "column")
        items = []
        missing_items: list[str] = []
        for row in row_axis["values"]:
            for column in column_axis["values"]:
                cell = view["cells"][f"{row}:{column}"]
                state = cell["state"]
                if state in {"missing"}:
                    what = f"{axis_plain_words(column_axis, column)}, {axis_plain_words(row_axis, row)}"
                    code = (
                        f'{axis_value_label(column_axis, column)}·'
                        f'{axis_value_label(row_axis, row)}'
                    )
                    reason = str(cell.get("reason") or cell.get("label") or "Not tested yet")
                    missing_items.append(
                        f'<code title="{esc(what)} — {esc(reason)}">{esc(code)}</code>'
                    )
                    continue
                evidence_id = cell.get("evidence_id")
                evidence = (
                    by_id[evidence_id].get("evidence")
                    if evidence_id
                    else cell.get("evidence") or view.get("evidence")
                )
                label_text = str(cell.get("label", ""))
                if evidence_id and cell.get("point_x") is not None:
                    observed = by_id[evidence_id]
                    point = next(
                        point for point in observed.get("points") or []
                        if point.get("x") == cell["point_x"]
                    )
                    label_text = point_metric_label(point)
                elif evidence_id:
                    metrics = by_id[evidence_id].get("metrics") or {}
                    decode_values = metrics.get("decode_tok_s") or []
                    if decode_values:
                        label_text = f"{fmt(max(decode_values))} tok/s"
                estimate_note = ""
                if cell.get("estimate_id"):
                    estimate = estimates[cell["estimate_id"]]
                    interval = estimate["interval"]
                    label_text = (
                        f'\u2248 {fmt(estimate["value"])} {estimate["unit"]} '
                        f'({fmt(interval["low"])}\u2013{fmt(interval["high"])})'
                    )
                    evidence = estimate["record"]
                    engine = estimate.get("engine") or {}
                    estimate_note = f'{engine.get("name", "")} {engine.get("version", "")}'.strip()
                what = f"{axis_plain_words(column_axis, column)}, {axis_plain_words(row_axis, row)}"
                code = (
                    f'{axis_value_label(column_axis, column)}\u00b7'
                    f'{axis_value_label(row_axis, row)}'
                )
                links = []
                packet_id = cell.get("packet_id")
                if packet_id:
                    packet = packets[packet_id]
                    manifest = str(packet.get("manifest", ""))
                    href = (
                        f"{packet_id}.html"
                        if manifest.startswith("packages/") and manifest.endswith("package.json")
                        else evidence_href(manifest)
                    )
                    links.append(f'<a href="{esc(href)}">{"guide" if packet_link_kind(family, packet) == "guide" else "report"}</a>')
                if evidence:
                    links.append(f'<a href="{esc(evidence_href(evidence))}">evidence</a>')
                reason = cell.get("reason") or ""
                if state == "quarantined":
                    reason_text = (reason or "output not usable").rstrip(". ")
                    label_note = label_text.rstrip(". ")
                    dead = f'{esc(reason_text)}. <span class="c-dead">Observed: {esc(label_note)}.</span>'
                    body = (
                        f'<span class="c-what">{esc(what)} <code>{esc(code)}</code> \u2014 {dead}</span>'
                    )
                    value_html = ""
                else:
                    note_bits = []
                    if reason and reason.lower() not in {"", "strict"}:
                        note_bits.append(esc(reason))
                    if estimate_note:
                        note_bits.append(esc(estimate_note))
                    note = (" — " + "; ".join(note_bits)) if note_bits else ""
                    body = f'<span class="c-what">{esc(what)} <code>{esc(code)}</code>{note}</span>'
                    value_html = f'<b class="c-val">{esc(label_text)}</b>' if label_text else ""
                items.append((COMBO_ORDER.get(state, 8), (
                    f'<li class="combo is-{esc(state)}">'
                    f'<span class="c-state">{COMBO_STATE_WORDS.get(state, esc(state))}</span>'
                    f'{body}{value_html}'
                    f'<span class="c-links">{" \u00b7 ".join(links)}</span></li>'
                )))
        items.sort(key=lambda item: item[0])
        gaps = (
            f'<details class="combo-gaps"><summary>{len(missing_items)} untested '
            f'combination{"s" if len(missing_items) != 1 else ""}</summary>'
            f'<div class="gap-chips">{"".join(missing_items)}</div></details>'
            if missing_items
            else ""
        )
        tail = (
            f'<div class="combo-tail">{gaps}<a class="inline" '
            f'href="../families/{esc(family["id"])}.json">Full matrix and exact selectors</a></div>'
        )
        selectors = " · ".join(
            f"{key}={value}" for key, value in (view.get("fixed_selectors") or {}).items()
        )
        scope = str(view.get("fixed") or "")
        if selectors:
            scope = f"{scope} Fixed: {selectors}.".strip()
        block_html = "".join(html for _, html in items)
        classified = (
            f'<ul class="combo-list">{block_html}</ul>'
            if items
            else '<p class="combo-none">No classified combinations in this slice yet.</p>'
        )
        if re.search(r"\b(?:AR|[DPTA])\d", block_html):
            tail = ('<p class="combo-tail">Codes in the rows: D = decode tok/s · P = prefill tok/s · '
                    'T = ms to first token · AR = share of drafted tokens accepted · A = combined tok/s.</p>') + tail
        blocks.append(
            f'<div class="combo-block" data-coverage-view="{esc(view.get("id"))}">'
            f'<h3 class="combo-title">{esc(view.get("label"))}</h3>'
            f'<p class="combo-scope">{esc(scope)}</p>'
            f'{classified}{tail}</div>'
        )
    return "".join(blocks)


def coverage_contract_scorecards(family: dict[str, Any]) -> str:
    """Render dense contracts as totals and axis breakdowns, never cell prose."""
    cards: list[str] = []
    contracts = family.get("coverage_contracts") or []
    aggregate_cells: list[dict[str, Any]] = []
    for contract in contracts:
        cells, _ = expand_coverage_contract(contract)
        aggregate_cells.extend(cells)
        total = len(cells)
        state_counts = {
            state: sum(cell.get("state") == state for cell in cells)
            for state in ALLOWED_STATES
        }
        classified = total - state_counts["missing"]
        measured = sum(state_counts[state] for state in CURVE_STATES)
        retry_count = sum(isinstance(cell.get("retry"), dict) for cell in cells)
        state_rail = "".join(
            f'<span class="is-{esc(state)}"><b>{count}</b> {esc(STATE_GLYPHS[state])}</span>'
            for state in sorted(ALLOWED_STATES)
            if (count := state_counts[state])
        )
        axis_blocks: list[str] = []
        for axis in contract.get("axes") or []:
            key = axis["key"]
            values = []
            for value in axis["values"]:
                selected = [cell for cell in cells if cell["selectors"][key] == value]
                selected_classified = sum(
                    cell.get("state") != "missing" for cell in selected
                )
                selected_states = ", ".join(
                    f"{STATE_GLYPHS[state]} {sum(cell.get('state') == state for cell in selected)}"
                    for state in sorted(ALLOWED_STATES)
                    if any(cell.get("state") == state for cell in selected)
                )
                values.append(
                    f'<span title="{esc(selected_states)}"><b>{esc(axis_value_label(axis, value))}</b> '
                    f'{selected_classified}/{len(selected)}</span>'
                )
            axis_blocks.append(
                f'<div><strong>{esc(axis.get("label"))}</strong>{"".join(values)}</div>'
            )
        description = contract.get("description") or "Exact Cartesian coverage contract."
        fixed = " · ".join(
            f"{key}={value}"
            for key, value in (contract.get("fixed_selectors") or {}).items()
        )
        fixed_html = (
            f'<p class="contract-fixed">Fixed: {esc(fixed)}</p>' if fixed else ""
        )
        cards.append(
            f'<section class="contract-card" data-coverage-contract="{esc(contract.get("id"))}">'
            f'<div class="contract-head"><div><h3 title="{esc(contract.get("label"))}">{esc(plain_label(contract.get("label")))}</h3>'
            f'<p>{esc(description)}</p></div><b>{classified}/{total}</b></div>'
            f'<div class="contract-stats"><span><b>{total}</b> exact cells</span>'
            f'<span><b>{classified}</b> classified</span><span><b>{measured}</b> measured</span>'
            f'<span><b>{state_counts["missing"]}</b> gaps</span>'
            f'<span><b>{retry_count}</b> retry-tagged</span></div>'
            f'<div class="contract-state-rail">{state_rail}</div>'
            f'{fixed_html}'
            f'<details class="contract-filters"><summary>Break down by axis</summary>'
            f'{"".join(axis_blocks)}</details></section>'
        )
    if not cards:
        return ""

    aggregate_counts = {
        state: sum(cell.get("state") == state for cell in aggregate_cells)
        for state in ALLOWED_STATES
    }
    aggregate_total = len(aggregate_cells)
    aggregate_classified = aggregate_total - aggregate_counts["missing"]
    tp_values = {
        cell.get("selectors", {}).get("tp")
        for cell in aggregate_cells
        if "tp" in cell.get("selectors", {})
    }
    aggregate_label = "TP1 coverage" if tp_values == {1} else "Coverage"
    state_order = (
        "lab-measured",
        "estimated",
        "quarantined",
        "missing",
        "lab-screened",
        "community-measured",
        "closed",
        "unsupported",
    )
    state_words = {
        "lab-measured": "measured",
        "estimated": "estimated",
        "quarantined": "quarantined",
        "missing": "missing",
        "lab-screened": "screened",
        "community-measured": "community",
        "closed": "closed",
        "unsupported": "unsupported",
    }
    shown_states = [state for state in state_order if aggregate_counts[state]]
    aria = ", ".join(
        f'{fmt(aggregate_counts[state], 0)} {state_words[state]}'
        for state in shown_states
    )
    rail = "".join(
        f'<span class="is-{esc(state)}" data-coverage-state="{esc(state)}" '
        f'style="flex-grow:{aggregate_counts[state]}" title="{aggregate_counts[state]} '
        f'{esc(state_words[state])}"></span>'
        for state in shown_states
    )
    counts = "".join(
        f'<span class="is-{esc(state)}"><b>{fmt(aggregate_counts[state], 0)}</b> '
        f'{esc(state_words[state])}</span>'
        for state in shown_states
    )
    aggregate = (
        '<section class="contract-overview" data-coverage-aggregate>'
        '<div class="contract-overview-head"><div>'
        f'<span>{esc(aggregate_label)} · {len(contracts)} matrices</span>'
        f'<b>{fmt(aggregate_classified, 0)}/{fmt(aggregate_total, 0)} classified</b>'
        '</div></div>'
        f'<div class="contract-overview-rail" role="img" aria-label="{esc(aria)}">{rail}</div>'
        f'<div class="contract-overview-counts">{counts}</div>'
        '</section>'
    )
    return aggregate + '<div class="contract-grid">' + "".join(cards) + "</div>"


def closure_cards(family: dict[str, Any]) -> str:
    cards = []
    for closure in family.get("family_closures") or []:
        selectors = " · ".join(f"{key}={value}" for key, value in closure["selectors"].items())
        cards.append(
            f'<a class="closure-card is-{esc(closure["state"])}" href="{esc(evidence_href(closure["evidence"]))}">'
            f'<span>{esc(closure["state"])} · {esc(selectors)}</span><b>{esc(closure["reason"])}</b></a>'
        )
    return "".join(cards)


# ML Bottleneck preset per family. A family whose hero run is a model the
# engine does not know gets no projection block (an honest gap), never a
# guess from a sibling.
FAMILY_ML_MODEL = {
    "deepseek-coder-v2": None,            # DeepSeek Coder V2 Lite: no engine preset yet
    "deepseek-v4": "deepseek_v4_flash_reap_180b",
    "gemma-4": "gemma4_26b_a4b",
    "glm-4-7": "glm4.7_flash",
    "laguna-s": "laguna_s_2.1",
    "lfm-2-5": "lfm2.5_2.6b",
    "minimax-m2-7": "minimax_m2.7",
    "mistral-small-3-2": "mistral_small_24b",
    "muse-glimmer": "muse_glimmer_30b",
    "nemotron-3-5": "nemotron3.5_lightning_30b_a3b",
    "nemotron-cascade-2": None,           # Nemotron Cascade 2: no engine preset yet
    "ornith-1-5": "ornith_1.5_35b_a3b",
    "phi-4": "phi4_mini_3.8b",
    "qwen-14b": None,                     # Qwen3 14B: no engine preset yet
    "qwen-27b": "qwen3.8_27b",
    "qwen-30b-a3b": "qwen3_30b_a3b",
    "qwen-35b": "qwen3.6_35b_a3b",
}


def ml_runtime_key(runtime_text: str) -> str:
    text = str(runtime_text or "").lower()
    if "vllm" in text:
        return "vllm"
    if "sglang" in text:
        return "sglang"
    return "llama_cpp"


def ml_quant_label(variant_text: str) -> str:
    """Reduce a measurement's variant text to a quantization label the
    engine parses (first recognisable format token; family default q4)."""
    text = str(variant_text or "")
    for token in ("UD-Q8_K_XL", "UD-Q4_K_XL", "UD-Q4_K_M", "UD-IQ4_XS", "Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0", "Q4_0",
                  "AutoRound INT4", "AutoRound W4A16 INT4", "GPTQ INT4", "AWQ", "Quark W8A8 INT8", "W8A8 INT8", "FP8", "MXFP4", "NVFP4", "INT4", "INT8"):
        if token.lower() in text.lower():
            return {"AutoRound W4A16 INT4": "AutoRound INT4", "W8A8 INT8": "Quark W8A8 INT8", "INT4": "AutoRound INT4"}.get(token, token)
    return "q4"


def ml_spec_label(config: dict[str, Any], variant_text: str) -> str:
    mtp = config.get("mtp")
    if isinstance(mtp, int) and mtp > 0:
        return f"mtp:{mtp}"
    text = str(variant_text or "").lower()
    if "dflash" in text:
        return "dflash:11"
    if "dspark" in text:
        return "dspark:7"
    return "none"


def plain_identity(identity: str) -> str:
    """Drop revision ids and commit hashes from an identity line for prose."""
    parts = [bit.strip() for bit in str(identity).split("\u00b7")]
    kept = []
    for bit in parts:
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*-[0-9a-f]{7,}", bit):
            continue
        bit = re.sub(r"\b[0-9a-f]{7,}(?:/[0-9a-f]{7,})*\b", "", bit).strip(" /")
        if bit:
            kept.append(bit)
    return " \u00b7 ".join(kept)


def family_projection_attrs(family: dict[str, Any], hero: dict[str, Any] | None) -> str:
    """data-ml-* attributes for the shared bridge renderer, built from the
    family's hero measurement: its quant, runtime, card count, and the
    prompt/output shape it actually ran. Empty when unmapped."""
    model_key = FAMILY_ML_MODEL.get(str(family.get("id")))
    if not model_key or not hero:
        return ""
    config = hero.get("config") or {}
    cards = config.get("tp") or config.get("cards") or 1
    workload = str(hero.get("workload") or "")
    prompt_tokens = 128
    output_tokens = 128
    match = re.search(r"p(\d+)\s*/\s*[on](\d+)", workload)
    if match:
        prompt_tokens, output_tokens = int(match.group(1)), int(match.group(2))
    else:
        out_match = re.search(r"(\d+)[- ]token (?:output|responses|answers)", workload)
        if out_match:
            output_tokens = int(out_match.group(1))
    return (
        f' data-ml-model="{esc(model_key)}" data-ml-quant="{esc(ml_quant_label(hero.get("variant")))}"'
        f' data-ml-quant-label="{esc(hero.get("variant") or "")}" data-ml-runtime="{esc(ml_runtime_key(hero.get("runtime")))}"'
        f' data-ml-runtime-label="{esc(hero.get("runtime") or "")}" data-ml-cards="{esc(cards)}"'
        f' data-ml-hardware="Intel Arc Pro B70" data-ml-hardware-label="B70"'
        f' data-ml-spec="{esc(ml_spec_label(config, hero.get("variant")))}"'
        + (' data-ml-strategy="tensor"' if int(cards or 1) > 1 and ml_runtime_key(hero.get("runtime")) == "llama_cpp" else "")
        + f' data-ml-prompt="{prompt_tokens}" data-ml-output="{output_tokens}"'
    )


def packet_link_kind(family: dict[str, Any], packet: dict[str, Any]) -> str:
    """'guide' when a real install route exists (repro guide or package
    manifest), else 'report' (a lab report or raw evidence is NOT a recipe)."""
    guide = str(packet.get("guide") or "")
    if guide.startswith("repro/") or guide.startswith("packages/"):
        return "guide"
    manifest = str(packet.get("manifest") or "")
    if manifest.startswith("packages/") and manifest.endswith("package.json"):
        return "guide"
    if manifest.startswith("repro/") and manifest.endswith("README.md"):
        return "guide"
    return "report"


def package_metric(
    family: dict[str, Any], packet: dict[str, Any]
) -> tuple[str, str, str, float | None, str, bool]:
    manifest = packet.get("manifest", "")
    direct = packet.get("featured_metric")
    if isinstance(direct, dict):
        measurement = next(
            item
            for item in records(family)
            if item.get("id") == direct.get("measurement_id")
        )
        metric_key = direct["metric"]
        if direct.get("sample_index") is not None:
            raw_value = measurement["metrics"][metric_key][direct["sample_index"]]
        else:
            point = next(
                item
                for item in measurement["points"]
                if item.get("x") == direct.get("point_x")
            )
            raw_value = point[metric_key]
        return (
            fmt(raw_value),
            METRICS[metric_key][1],
            evidence_href(measurement["evidence"]),
            float(raw_value),
            str(measurement.get("workload", "")),
            metric_key == "decode_tok_s",
        )
    if not str(manifest).startswith("packages/") or not str(manifest).endswith("package.json"):
        return "—", "", evidence_href(str(manifest)), None, "", False
    package = load_json(ROOT / manifest)
    metric = ((package.get("library") or {}).get("featured_metric") or {})
    raw_value = metric.get("value")
    value = fmt(raw_value)
    unit = metric.get("unit", "tok/s")
    return (
        value,
        unit,
        f"{packet['id']}.html",
        float(raw_value) if is_finite_number(raw_value) else None,
        str(metric.get("scope", "")),
        metric.get("unit") == "tok/s",
    )


def packet_manifest_target(packet: dict[str, Any]) -> tuple[str, str]:
    """Return an honest action label for the packet's best runnable surface."""

    guide = str(packet.get("guide") or "")
    if guide.startswith("repro/"):
        return evidence_href(guide), "Open reproduction guide"
    if guide.startswith("packages/"):
        return evidence_href(guide), "Open deployment guide"
    manifest = str(packet.get("manifest") or "")
    if manifest.startswith("packages/") and manifest.endswith("package.json"):
        return f'{packet["id"]}.html', "Open deployment packet"
    href = evidence_href(manifest)
    if manifest.startswith("repro/") and manifest.endswith("README.md"):
        return href, "Open reproduction guide"
    if manifest.startswith("results/") and manifest.endswith("README.md"):
        return href, "Read the lab report"
    return href, "Open evidence packet"


def preferred_packet(family: dict[str, Any]) -> dict[str, Any] | None:
    """Return the explicitly curated family CTA packet.

    Validation requires the binding whenever packets exist. The deterministic
    fallback is only for defensive rendering of invalid/in-progress data and
    deliberately never considers throughput.
    """

    packets = list(family.get("packets") or [])
    primary_packet_id = family.get("primary_packet_id")
    explicit = next(
        (packet for packet in packets if packet.get("id") == primary_packet_id),
        None,
    )
    if explicit is not None:
        return explicit
    grade_rank = {"A": 0, "B": 1, "C": 2, "D": 3}

    def fallback_rank(packet: dict[str, Any]) -> tuple[int, int]:
        grade = (((packet.get("grades") or {}).get("evidence") or {}).get("grade"))
        return (
            grade_rank.get(str(grade), 4),
            0 if packet_link_kind(family, packet) == "guide" else 1,
        )

    return min(packets, key=fallback_rank) if packets else None


def measurement_identity(measurement: dict[str, Any]) -> str:
    config = measurement.get("config") or {}
    bits = [
        measurement.get("revision"),
        measurement.get("artifact_id"),
        measurement.get("variant"),
        measurement.get("runtime"),
    ]
    tp = config.get("tp") or config.get("cards")
    if tp is not None:
        bits.append(f"TP{tp}")
    if config.get("mtp") is not None:
        bits.append(f'MTP{config["mtp"]}')
    if config.get("graph") is not None:
        bits.append(f'graph {config["graph"]}')
    if config.get("kv") is not None:
        bits.append(f'{config["kv"]} KV')
    if config.get("configured_max_context_tokens") is not None:
        context = config["configured_max_context_tokens"]
        shown = f"{context:,}" if isinstance(context, int) else str(context)
        bits.append(f"max context {shown}")
    if config.get("active_context_tokens") is not None:
        context = config["active_context_tokens"]
        shown = f"{context:,}" if isinstance(context, int) else str(context)
        bits.append(f"active context {shown}")
    if config.get("gpu_memory_utilization") is not None:
        bits.append(f'GPU memory {config["gpu_memory_utilization"]}')
    if config.get("natural_eos") is not None:
        bits.append("natural EOS" if config["natural_eos"] else "fixed output")
    return " · ".join(str(bit) for bit in bits if bit not in (None, ""))


def featured_result_entries(family: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve curated presentation claims; packet metrics are the safe fallback."""

    by_id = {measurement["id"]: measurement for measurement in records(family)}
    configured = family.get("featured_results")
    entries: list[dict[str, Any]] = []
    if isinstance(configured, list) and configured:
        for binding in configured:
            measurement = by_id[binding["measurement_id"]]
            value = selected_metric_value(binding, measurement)
            if value is None:  # Validation rejects this; keep rendering fail-closed.
                continue
            metric = binding["metric"]
            entries.append(
                {
                    "role": binding["role"],
                    "label": binding["label"],
                    "value": value,
                    "unit": METRICS[metric][1],
                    "metric": metric,
                    "href": evidence_href(measurement["evidence"]),
                    "identity": measurement_identity(measurement),
                    "quality_label": binding["quality_label"],
                    "workload": measurement.get("workload") or "",
                    "state": measurement.get("state"),
                    "record_label": measurement.get("id") or "measurement",
                }
            )
        entries.sort(key=lambda item: item["role"] != "hero")
        return entries

    for packet in family.get("packets") or []:
        value, unit, href, raw_value, workload, _opt_eligible = package_metric(
            family, packet
        )
        if raw_value is None or value == "—":
            continue
        grades = packet.get("grades") or {}
        evidence_grade = grades.get("evidence") or {}
        quality_label = (
            f'Evidence {evidence_grade["grade"]} of A–D'
            if evidence_grade.get("grade")
            else str(packet.get("evidence_level") or "Measured packet; see evidence scope")
        )
        identity = " · ".join(
            str(bit)
            for bit in (
                packet.get("revision"),
                packet.get("quantization"),
                packet.get("runtime"),
                f'{packet.get("cards")}× B70' if packet.get("cards") else None,
            )
            if bit not in (None, "")
        )
        entries.append(
            {
                "role": "hero" if not entries else "support",
                "label": packet.get("label") or packet.get("id"),
                "value": raw_value,
                "unit": unit,
                "metric": "decode_tok_s" if unit == "tok/s" else "packet_metric",
                "href": href,
                "identity": identity,
                "quality_label": quality_label,
                "workload": workload,
                "state": "packet",
                "record_label": packet.get("id") or "packet",
            }
        )
    if entries:
        comparable = [entry for entry in entries if entry["unit"] == "tok/s"]
        hero = max(comparable or entries, key=lambda entry: entry["value"])
        for entry in entries:
            entry["role"] = "hero" if entry is hero else "support"
        entries.sort(key=lambda item: item["role"] != "hero")
    return entries


def grade_badge(label: str, value: Any) -> str:
    # No grade -> no badge: an em-dash placeholder is noise, not information.
    if not isinstance(value, dict):
        return ""
    title = f'{value.get("scope", "")} · {value.get("basis", "")}'
    word = {"CAP": "Capability", "EVID": "Evidence"}.get(label, label)
    return (
        f'<span class="curated-grade" tabindex="0" title="{esc(title)}" aria-label="{esc(word)} grade {esc(value.get("grade"))}: {esc(title)}">'
        f'{esc(word)} {esc(value.get("grade"))} <small>of A\u2013D</small></span>'
    )


def packet_cards(family: dict[str, Any]) -> str:
    cards = []
    revisions = {
        revision.get("id"): revision for revision in family.get("weight_revisions") or []
    }
    for packet in family.get("packets") or []:
        value, unit, href, raw_value, workload, opt_eligible = package_metric(family, packet)
        coverage = "".join(f"<span>{esc(item)}</span>" for item in packet.get("coverage") or [])
        projection = packet.get("projection") or {}
        attrs = ""
        headroom = ""
        projection_workload_pinned = all(
            isinstance(projection.get(field), int)
            and not isinstance(projection.get(field), bool)
            and projection.get(field) > 0
            for field in ("prompt_tokens", "output_tokens")
        )
        if projection and value != "—" and projection_workload_pinned and opt_eligible:
            attrs = (
                f' data-family-headroom data-ml-model="{esc(projection.get("model"))}"'
                f' data-ml-quant="{esc(projection.get("quant"))}" data-ml-runtime="{esc(projection.get("runtime"))}"'
                f' data-ml-spec="{esc(projection.get("spec", "none"))}" data-ml-cards="{esc(packet.get("cards", 1))}"'
                f' data-ml-hardware="Intel Arc Pro B70" data-ml-measured="{esc(raw_value)}"'
                f' data-ml-prompt="{esc(projection.get("prompt_tokens"))}" data-ml-output="{esc(projection.get("output_tokens"))}"'
                + (f' data-ml-strategy="{esc(projection.get("strategy"))}"' if projection.get("strategy") else "")
            )
            headroom = '<span class="opt-grade" data-family-headroom-value title="Compares measured speed with the modeled tuned target, not model quality or packet evidence.">projected headroom \u2026</span>'
        elif projection and value != "—":
            headroom = ""
        grades = packet.get("grades") or {}
        revision = revisions.get(packet.get("revision")) or {}
        capability = grades.get("capability") or (revision.get("grades") or {}).get("capability")
        grade_rail = "".join(
            (
                grade_badge("CAP", capability),
                grade_badge("EVID", grades.get("evidence")),
            )
        )
        STATUS_WORDS = {
            "closed research result": "research, closed \u2014 the lab has stopped tuning this configuration for now",
            "candidate": "candidate package",
            "research": "research",
        }
        status_text = STATUS_WORDS.get(str(packet.get("status") or "").lower(), str(packet.get("status") or ""))
        # The measured workload stays visible under the number (honesty: the
        # claim carries its own scope), just small and muted.
        workload_html = (
            f'\n  <small class="packet-workload">{esc(workload)}</small>'
            if workload and value != "—"
            else ""
        )
        report_note = (
            '\n  <small class="packet-note">lab report — documents the result; not a step-by-step install guide</small>'
            if packet_link_kind(family, packet) == "report"
            else ""
        )
        cards_n = packet.get("cards")
        link_kind = packet_link_kind(family, packet)
        if value == "\u2014":
            promise = "Evidence packet"
        elif link_kind == "guide":
            promise = f'Reproduce <b>{esc(value)} {esc(unit)}</b>' + (
                f' on {esc(cards_n)}\u00d7 B70' if cards_n else ""
            )
        else:
            promise = f'Measured evidence: <b>{esc(value)} {esc(unit)}</b>' + (
                f' on {esc(cards_n)}\u00d7 B70' if cards_n else ""
            )
        cards.append(
            f'''<a class="packet-card" href="{esc(href)}"{attrs}>
  <div class="packet-top"><span>{esc(packet.get('revision'))}</span><span class="packet-badges"><b>{esc(packet.get('evidence_level'))}</b>{headroom}</span></div>
  <h3 title="{esc(packet.get('label'))}">{esc(plain_label(packet.get('label')))}</h3>
  <p class="packet-promise">{promise} · {esc(status_text)}</p>{workload_html}{report_note}
  <div class="grade-rail">{grade_rail}</div>
  <div class="coverage-rail">{coverage}</div>
</a>'''
        )
    return "".join(cards)


def family_page(family: dict[str, Any]) -> str:
    source = f"../families/{family['id']}.json"
    signals = family.get("model_signals") or {}
    popularity = signals.get("popularity") or {}
    architecture = family.get("architecture") or {}
    quality = signals.get("quality_evidence") or {}
    fit = signals.get("b70_fit") or {}
    revisions = family.get("weight_revisions") or []
    transfer = family.get("transfer_scope") or {}
    all_views = family.get("views") or []
    initial_view_ids = family.get("initial_view_ids")
    if initial_view_ids:
        by_view_id = {view.get("id"): view for view in all_views}
        initial_views = [by_view_id[view_id] for view_id in initial_view_ids]
        deferred_views = [
            view for view in all_views if view.get("id") not in initial_view_ids
        ]
    else:
        initial_views = all_views
        deferred_views = []
    views = "".join(view_card(family, view) for view in initial_views)
    deferred_views_html = ""
    if deferred_views:
        deferred_cards = "".join(view_card(family, view) for view in deferred_views)
        deferred_views_html = (
            '<details class="more-views"><summary>'
            f'{len(deferred_views)} more evidence views</summary>'
            f'<div class="views-grid">{deferred_cards}</div></details>'
        )
    coverage_contracts = family.get("coverage_contracts") or []
    contract_overview_css = ""
    if coverage_contracts:
        contract_overview_css = """  .contract-overview { border:2px solid var(--ink); padding:12px; margin-bottom:12px; background:var(--surface); }
  .contract-overview-head span { display:block; color:var(--muted); font:700 9.5px var(--mono); text-transform:uppercase; }
  .contract-overview-head b { display:block; margin-top:3px; font:900 23px/1 var(--display); text-transform:uppercase; }
  .contract-overview-rail { display:flex; width:100%; height:9px; margin-top:11px; overflow:hidden; border:1px solid var(--ink); background:var(--paper); }
  .contract-overview-rail .is-lab-measured { background:var(--good); }
  .contract-overview-rail .is-estimated { background:var(--spot); }
  .contract-overview-rail .is-quarantined { background:#a12820; }
  .contract-overview-rail .is-missing { background:var(--line); }
  .contract-overview-rail .is-lab-screened, .contract-overview-rail .is-closed { background:var(--warn); }
  .contract-overview-rail .is-community-measured { background:var(--s2); }
  .contract-overview-rail .is-unsupported { background:var(--muted); }
  .contract-overview-counts { display:flex; flex-wrap:wrap; gap:5px 14px; margin-top:8px; font:10px var(--mono); text-transform:uppercase; }
"""
    deferred_views_css = ""
    if deferred_views:
        deferred_views_css = """  .more-views { margin-top:14px; }
  .more-views > summary { cursor:pointer; font:800 11px var(--mono); text-transform:uppercase; }
  .more-views > .views-grid { margin-top:12px; }
"""
    packets = packet_cards(family)
    coverage_views = family.get("coverage_views") or []
    coverage = coverage_tables(family) if coverage_views else ""
    contract_coverage = (
        coverage_contract_scorecards(family) if coverage_contracts else ""
    )
    closure_items = family.get("family_closures") or []
    closures = closure_cards(family) if closure_items else ""
    lineage = "".join(
        f'<span>{esc(revision.get("label") or revision.get("id"))}'
        + (f' · {esc(revision.get("role"))}' if revision.get("role") else "")
        + "</span>"
        for revision in revisions
    )
    artifacts = [
        artifact
        for revision in revisions
        for artifact in revision.get("quantized_artifacts") or []
        if isinstance(artifact, dict)
    ]
    if artifacts:
        quantization_count = len(
            {artifact.get("quantization") for artifact in artifacts}
        )
        artifact_items = "".join(
            f'<li><code>{esc(artifact.get("id"))}</code> · '
            f'{esc(artifact.get("quantization"))} · '
            f'{esc(artifact.get("repository"))}@'
            f'{esc(artifact.get("revision") or artifact.get("revision_status"))}</li>'
            for artifact in artifacts
        )
        lineage += (
            '<details class="artifact-disclosure"><summary>'
            f'{len(artifacts)} exact artifacts · {quantization_count} quantizations'
            f'</summary><ul>{artifact_items}</ul></details>'
        )
    architecture_bits = []
    if architecture.get("class"):
        architecture_bits.append(str(architecture["class"]))
    if architecture.get("layers") is not None:
        architecture_bits.append(f'{architecture["layers"]} layers')
    if architecture.get("hidden_size") is not None:
        architecture_bits.append(f'{architecture["hidden_size"]} hidden')
    architecture_summary = ", ".join(architecture_bits)
    boundary = str(
        transfer.get("status")
        or "Measurements remain revision- and artifact-specific"
    ).rstrip(". ")
    popularity_value = popularity.get("downloads")
    popularity_scope = popularity.get("scope") or popularity.get("reason") or "not scored"
    if popularity_value is not None:
        popularity_value = compact_count(popularity_value)
    elif popularity.get("snapshots"):
        snapshots = popularity["snapshots"]
        primary_revision = popularity.get("primary_revision")
        primary = next(
            (
                snapshot
                for snapshot in snapshots
                if snapshot.get("revision") == primary_revision
            ),
            snapshots[0],
        )
        popularity_value = compact_count(primary.get("downloads"))
        popularity_scope = (
            f'{primary.get("repository") or primary.get("repo_id") or primary.get("revision")}; '
            f'{fmt(primary.get("likes"), 0)} likes. {popularity_scope}'
        )
    if popularity_value is None:
        popularity_value = "Pending"
    if architecture_summary:
        boundary = f"{architecture_summary}. {boundary}"
    popularity_date = popularity.get("captured_at")
    popularity_detail = (
        f"{popularity_date} · {popularity_scope}"
        if popularity_date
        else str(popularity_scope)
    )
    # Claims are explicit measurement bindings or curated packet metrics. Do
    # not manufacture a headline from an arbitrary maximum or insertion order.
    selected_results = featured_result_entries(family)
    hero_result = next((item for item in selected_results if item.get("role") == "hero"), None)
    headline_html = ""
    if hero_result:
        words = int(round(float(hero_result["value"]) * 0.75)) if hero_result.get("unit") == "tok/s" else None
        hero_detail = " \u00b7 ".join(
            bit for bit in (hero_result.get("identity"), hero_result.get("quality_label")) if bit
        )
        headline_html = (
            f'  <a class="hero-headline" href="{esc(hero_result["href"])}" '
            f'title="{esc(hero_result.get("record_label"))} \u00b7 {esc(hero_result.get("workload"))}">'
            f'<span class="big">{fmt(hero_result["value"])}</span>'
            f'<span class="unit">{esc(hero_result["unit"])}<br>measured</span>'
            + (f'<span class="gloss">&asymp; {words} words a second</span>' if words else "")
            + f'<small>{esc(hero_detail)}</small></a>\n'
        )
    # The same projection block the package pages carry, driven by the hero
    # run's own identity; the bridge fills it client-side.
    hero_measurement = None
    if hero_result:
        hero_measurement = next((m for m in records(family) if m.get("id") == hero_result.get("record_label")), None)
    if hero_result and hero_measurement is None:
        # Packet-derived headline: use the packet's featured measurement, else
        # the family's best lab-measured decode run, so the projection is
        # built from a real recorded identity.
        candidates = [m for m in records(family) if m.get("state") == "lab-measured" and (m.get("metrics") or {}).get("decode_tok_s")]
        if candidates:
            hero_measurement = max(candidates, key=lambda m: max((m.get("metrics") or {}).get("decode_tok_s") or [0]))
    projection_attrs = family_projection_attrs(family, hero_measurement)
    if projection_attrs and hero_result:
        projection_html = f'''
  <div class="section-head"><div><h2 id="projection">How much faster could this get? <span class="badge spec">Projected \u2014 not measured</span></h2><p>The <a class="inline" href="https://mlbottleneck.com/">ML Bottleneck</a> physics engine projects a tuned-run target and the physical ceiling for the headline setup ({esc(plain_identity(hero_result.get("identity") or ""))}). The grade is optimization headroom against the tuned-run target, not model quality.</p></div></div>
  <div id="package-page"{projection_attrs} data-ml-measured="{esc(hero_result["value"])}">
    <div id="package-projection" class="projection" hidden>
      <p class="projection-status" data-projection-status>Loading projections from mlbottleneck.com\u2026</p>
      <div data-package-card></div>
      <div data-package-charts></div>
    </div>
    <noscript><p class="projection-status">Projections need JavaScript; the measured numbers above are static.</p></noscript>
  </div>
'''
    else:
        reason = ("this model is not in the ML Bottleneck catalog yet" if not FAMILY_ML_MODEL.get(str(family.get("id")))
                  else "the family has no curated headline measurement yet")
        projection_html = f'''
  <div class="section-head"><div><h2 id="projection">How much faster could this get? <span class="badge todo">No projection</span></h2></div></div>
  <div class="placeholder"><p>No projection is shown: {esc(reason)}. The measured numbers above stand on their own.</p></div>
'''
    # Many people at once: measured aggregate sweeps where the family has one.
    aggregate_series = [m for m in records(family) if any(p.get("aggregate_tok_s") is not None for p in (m.get("points") or []))]
    if aggregate_series:
        best_series = max(aggregate_series, key=lambda m: max(p.get("aggregate_tok_s") or 0 for p in m.get("points") or []))
        top = max((p for p in best_series.get("points") or []), key=lambda p: p.get("aggregate_tok_s") or 0)
        multiuser_html = f'''
  <div class="section-head"><div><h2 id="multi-user">Many people at once <span class="badge lab">Lab-measured</span></h2><p>{esc(fmt_x(top.get("x")))} simultaneous users share <b>{top["aggregate_tok_s"]:,.0f} combined tok/s</b> on {esc((best_series.get("config") or {}).get("tp") or 1)} card{"s" if ((best_series.get("config") or {}).get("tp") or 1) != 1 else ""} ({esc(best_series.get("variant") or "")}); the full curve is under Measured results and in <a class="inline" href="../learn/multi-user.html">the multi-user report</a>.</p></div></div>
'''
    else:
        multiuser_html = '''
  <div class="section-head"><div><h2 id="multi-user">Many people at once <span class="badge todo">Not measured</span></h2></div></div>
  <div class="placeholder"><p>Multi-user (aggregate) throughput has not been measured for this family. The lab\u2019s one measured sweep so far is in <a class="inline" href="../learn/multi-user.html">the multi-user report</a>; the projection block below includes a projected users curve where a projection exists.</p></div>
'''
    strip_cards = []
    for result in selected_results:
        if result is hero_result:
            continue
        tone = (
            "is-featured"
            if result.get("role") == "hero"
            else "is-screened"
            if result.get("state") == "lab-screened"
            else "is-scoped"
        )
        strip_cards.append(
            f'<a class="result {tone}" href="{esc(result["href"])}" '
            f'title="{esc(result.get("record_label"))} · {esc(result.get("workload"))}">'
            f'<span class="r-kind">{esc(result["label"])}</span>'
            f'<b>{fmt(result["value"])}</b><span class="r-unit">{esc(result["unit"])}</span>'
            f'<span class="r-note">{esc(result.get("identity"))}</span>'
            f'<span class="r-gate">{esc(result.get("quality_label"))}</span></a>'
        )
    strip_html = (
        '<div class="result-strip" aria-label="Curated measured results">'
        + "".join(strip_cards[:5])
        + "</div>"
        if strip_cards
        else ""
    )
    # Prefer a deployment/reproduction surface. Evidence-only families retain
    # an honest action label rather than promising an install guide.
    cta_html = ""
    preferred = preferred_packet(family)
    if preferred:
        cta_href, cta_label = packet_manifest_target(preferred)
        cta_note = ""
        if packet_link_kind(family, preferred) != "guide":
            cta_note = '<span class="cta-note">No step-by-step install guide is published for this model yet.</span>'
        cta_html = (
            f'<div class="family-cta"><a class="button{"" if not cta_note else " secondary"}" href="{esc(cta_href)}">{esc(cta_label)}</a>'
            f'<a class="inline" href="#packets">All packets and recipes</a>{cta_note}</div>'
        )
    measured_count = sum(
        1
        for item in list(family.get("run_measurements") or [])
        + list(family.get("series_measurements") or [])
        if item.get("state") == "lab-measured"
    )
    estimate_count = len(family.get("estimates") or [])
    BAND_WORDS = {
        "four-card measured": "Runs on 4 cards (measured)",
        "one-card measured": "Runs on 1 card (measured)",
        "strict tp4 only": "Full gate, 4-card only",
        "high": "High",
        "pending": "Pending",
    }

    def band_words(value):
        text = str(value or "").strip()
        return BAND_WORDS.get(text.lower(), text[:1].upper() + text[1:].replace("-", " ") if text else "Pending")

    signal_cards = ""
    fit_band = fit.get("band")
    if fit_band:
        signal_cards += f'\n    <div title="{esc(fit.get("scope") or "local deployment fit")}, reviewed {esc(fit.get("reviewed_at") or family.get("updated_at"))}"><dt>B70 fit</dt><dd>{esc(band_words(fit_band))}</dd></div>'
    quality_band = quality.get("band")
    if quality_band:
        signal_cards += f'\n    <div title="{esc(quality.get("scope") or "No family-wide quality score is inferred from speed evidence.")}"><dt>Quality evidence</dt><dd>{esc(band_words(quality_band))}</dd></div>'
    if popularity_value not in (None, "Pending"):
        signal_cards += f'\n    <div title="{esc(popularity_detail)}"><dt>Interest</dt><dd>{esc(popularity_value)}</dd></div>'
    if measured_count:
        signal_cards += f'\n    <div title="Run arms and measured series; every point links to proof"><dt>Measured results</dt><dd>{measured_count}</dd></div>'
    coverage_section = ""
    if coverage_views or coverage_contracts:
        if family.get("collapse_coverage_contracts") and contract_coverage:
            contract_cells = [
                cell
                for contract in coverage_contracts
                for cell in expand_coverage_contract(contract)[0]
            ]
            contract_total = len(contract_cells)
            contract_classified = sum(
                cell.get("state") != "missing" for cell in contract_cells
            )
            contract_label = (
                "contract" if len(coverage_contracts) == 1 else "contracts"
            )
            contract_coverage = (
                '<details class="full-coverage-contracts">'
                f'<summary>Full {fmt(contract_total, 0)}-cell coverage '
                f'{contract_label} · {fmt(contract_classified, 0)} classified</summary>'
                f'{contract_coverage}</details>'
            )
            coverage_content = coverage + contract_coverage
        else:
            coverage_content = contract_coverage + coverage
        coverage_section = f'''
  <div class="section-head"><div><h2>What has been classified</h2><p>Dense scorecards summarize every declared combination; measured slices retain exact evidence links.</p></div></div>
  {coverage_content}
'''
    closures_section = ""
    if closure_items:
        reasons = []
        for closure in closure_items:
            reason = str(closure.get("reason") or "").strip().rstrip(".")
            if not reason:
                continue
            evidence = closure.get("evidence")
            link = f' <a class="inline" href="{esc(evidence_href(str(evidence)))}">evidence</a>' if evidence else ""
            reasons.append(esc(reason) + "." + link)
        closures_section = (
            f'<p class="closure-note"><b>{len(closure_items)} combination{"s" if len(closure_items) != 1 else ""} the lab has stopped pursuing:</b> '
            + " ".join(reasons)
            + f' Exact selectors are in the <a class="inline" href="{esc(source)}">family data</a>.</p>'
        )
    url = f"{SITE}models/{family['id']}.html"
    ld = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": family.get("display_name"),
        "description": family.get("summary"),
        "url": url,
        "dateModified": family.get("updated_at"),
        "creator": {"@type": "Organization", "name": "neural.download lab"},
        "isAccessibleForFree": True,
    }
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(family.get('display_name'))} on Intel Arc Pro B70 — neural.download</title>
{seo_head(url, f"{family.get('display_name')} on Intel Arc Pro B70 — neural.download", f"{family.get('summary')} Every number links to its measured proof.", image=f"{SITE}models/cards/{family['id']}.png", image_alt=f"{family.get('display_name')} measured on Intel Arc Pro B70 — neural.download", depth=1)}
<script type="application/ld+json">{json_for_html_script(ld)}</script>
<link rel="stylesheet" href="../learn/learn.css">
<link rel="preconnect" href="https://mlbottleneck.com">
<style>
  .family-main {{ max-width: 1120px; }}
  .lineage {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }}
  .lineage span {{ padding:5px 8px; border:1px solid rgba(255,255,255,.7); font:700 10px var(--mono); text-transform:uppercase; }}
  .artifact-disclosure {{ flex-basis:100%; font:600 10px var(--mono); }}
  .artifact-disclosure summary {{ cursor:pointer; width:max-content; max-width:100%; padding:5px 8px; border:1px solid rgba(255,255,255,.7); text-transform:uppercase; }}
  .artifact-disclosure ul {{ margin:7px 0 0; padding:8px 10px 8px 28px; background:rgba(255,255,255,.08); line-height:1.6; overflow-wrap:anywhere; }}
  .hero h1 {{ font-size:clamp(22px, 2.6vw, 32px); }}
  .hero h1 {{ font-size:clamp(22px, 2.6vw, 32px); }}
  .hero-headline {{ display:flex; align-items:baseline; gap:10px 14px; flex-wrap:wrap; margin:14px 0 0; color:inherit; text-decoration:none; }}
  .hero .hero-headline .big {{ font:900 clamp(54px, 7vw, 84px)/1 var(--display); color:var(--paper, #fff); }}
  .hero .hero-headline .unit {{ font:700 12px/1.25 var(--mono); text-transform:uppercase; letter-spacing:.05em; color:rgba(255,255,255,.85); }}
  .hero .hero-headline .gloss {{ font-size:13px; color:rgba(255,255,255,.9); }}
  .hero .hero-headline small {{ flex-basis:100%; color:rgba(255,255,255,.75); font-size:12.5px; }}
  .result-strip {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:10px; margin:0 0 14px; }}
  .result {{ display:block; border:2px solid var(--ink); background:var(--paper); padding:11px 12px 9px; }}
  .result.is-featured {{ border-color:var(--spot); }}
  .result:hover {{ border-color:var(--spot); }}
  .result .r-kind {{ display:block; font:700 9.5px var(--mono); text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }}
  .result b {{ font:900 27px/1.15 var(--display); }}
  .result .r-unit {{ margin-left:5px; font:700 10px var(--mono); text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }}
  .result .r-note {{ display:block; font-size:11px; color:var(--muted); }}
  .result .r-gate {{ display:block; margin-top:4px; font:700 9px var(--mono); text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }}
  .result.is-screened .r-gate {{ color:var(--warn); }}
  .family-cta {{ display:flex; align-items:center; gap:14px; margin:0 0 18px; }}
  .family-cta .button {{ display:inline-flex; align-items:center; min-height:38px; padding:8px 14px; border:2px solid var(--ink); background:var(--ink); color:var(--paper); font:700 11px var(--mono); text-transform:uppercase; letter-spacing:.05em; }}
  .family-cta .button:hover {{ background:var(--spot); border-color:var(--spot); color:#fff; }}
  .family-cta .button.secondary {{ background:transparent; color:var(--ink); }}
  .family-cta .button.secondary:hover {{ background:var(--ink); color:var(--paper); }}
  .cta-note {{ font-size:12px; color:var(--muted); }}
  .packet-note {{ display:block; margin-top:4px; font:700 9px var(--mono); text-transform:uppercase; letter-spacing:.05em; color:var(--warn); }}
  .meta-strip {{ display:flex; flex-wrap:wrap; gap:8px 26px; margin:0 0 20px; padding:10px 0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }}
  .meta-strip div {{ cursor:help; }}
  .meta-strip dt {{ font:700 9.5px var(--mono); text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }}
  .meta-strip dd {{ margin:1px 0 0; font-size:12.5px; }}
  .stat-row {{ display:grid; grid-template-columns:minmax(150px,1fr) auto; gap:5px 14px; align-items:baseline; padding:9px 2px; border-bottom:1px solid var(--line); }}
  .stat-values {{ display:flex; flex-wrap:wrap; justify-content:end; gap:8px 14px; }}
  .stat-metric {{ display:grid; grid-template-columns:auto auto; align-items:baseline; column-gap:4px; }}
  .stat-metric small {{ grid-column:1 / -1; color:var(--muted); font:9px var(--mono); text-transform:uppercase; }}
  .stat-row .m {{ text-align:right; }}
  .stat-row:last-child {{ border-bottom:0; }}
  .stat-row b {{ font:900 20px/1 var(--display); }}
  .stat-row .u {{ font:700 10px var(--mono); text-transform:uppercase; color:var(--muted); margin-left:4px; }}
  .stat-row .l {{ font-size:12.5px; }}
  .stat-row .m {{ grid-column:1 / -1; font:11px var(--mono); color:var(--muted); }}
  .stat-row.is-superseded {{ color:var(--muted); }}
  .stat-row.is-superseded b {{ font:700 15px/1 var(--display); color:var(--muted); }}
  .combo-list {{ list-style:none; margin:0; padding:0; border:2px solid var(--ink); background:var(--paper); }}
  .contract-grid {{ display:grid; gap:12px; margin-bottom:14px; }}
{contract_overview_css}  .contract-card {{ border:2px solid var(--ink); background:var(--paper); padding:12px; }}
  .contract-head {{ display:flex; justify-content:space-between; gap:16px; align-items:start; }}
  .contract-head h3 {{ margin:0; font:900 17px/1.1 var(--display); text-transform:uppercase; }}
  .contract-head p {{ margin:4px 0 0; color:var(--muted); font-size:12px; }}
  .contract-head > b {{ font:900 25px/1 var(--display); white-space:nowrap; }}
  .contract-stats, .contract-state-rail {{ display:flex; flex-wrap:wrap; gap:6px 14px; margin-top:10px; font:10px var(--mono); text-transform:uppercase; }}
  .contract-state-rail span {{ padding:3px 6px; border:1px solid var(--line); }}
  .contract-filters {{ margin-top:10px; border-top:1px solid var(--line); padding-top:8px; }}
  .contract-filters summary {{ cursor:pointer; font:700 10px var(--mono); text-transform:uppercase; }}
  .contract-filters div {{ display:flex; flex-wrap:wrap; gap:5px; align-items:center; margin-top:7px; }}
  .contract-filters strong {{ min-width:110px; font:700 10px var(--mono); text-transform:uppercase; }}
  .contract-filters span {{ padding:3px 6px; background:var(--surface); font:9px var(--mono); }}
  .combo {{ display:grid; grid-template-columns:130px 1fr auto auto; gap:4px 12px; align-items:baseline; padding:9px 12px; border-bottom:1px solid var(--line); }}
  .combo:last-child {{ border-bottom:0; }}
  .combo .c-state {{ font:700 9px var(--mono); text-transform:uppercase; letter-spacing:.05em; }}
  .combo.is-lab-measured .c-state {{ color:var(--good); }}
  .combo.is-lab-screened .c-state {{ color:var(--warn); }}
  .combo.is-quarantined .c-state {{ color:#a12820; }}
  .combo .c-what {{ font-size:12.5px; }}
  .combo .c-what code {{ font:8.5px var(--mono); color:var(--muted); border:1px solid var(--line); padding:0 4px; vertical-align:1px; }}
  .combo .c-dead {{ font-size:11.5px; color:var(--muted); font-weight:400; }}
  .combo .c-val {{ font:700 13px var(--mono); white-space:nowrap; }}
  .combo .c-links {{ font:11px var(--mono); white-space:nowrap; }}
  .combo-block + .combo-block {{ margin-top:18px; }}
  .combo-title {{ margin:0 0 5px; font:900 17px/1.1 var(--display); text-transform:uppercase; }}
  .combo-scope {{ margin:0 0 8px; color:var(--muted); font-size:12px; }}
  .combo-tail {{ margin:8px 0 0; color:var(--muted); font-size:12px; }}
  .combo-none {{ margin:0; padding:9px 12px; border:1px solid var(--line); color:var(--muted); font-size:12px; }}
  .combo-gaps {{ margin:0 0 6px; }}
  .combo-gaps summary {{ cursor:pointer; font:700 10px var(--mono); text-transform:uppercase; }}
  .gap-chips {{ display:flex; flex-wrap:wrap; gap:4px; margin-top:6px; }}
  .gap-chips code {{ padding:2px 5px; border:1px solid var(--line); background:var(--surface); font:9px var(--mono); }}
  .full-coverage-contracts {{ margin-top:18px; }}
  .full-coverage-contracts > summary {{ cursor:pointer; font:700 10px var(--mono); text-transform:uppercase; }}
  .full-coverage-contracts > .contract-overview {{ margin-top:10px; }}
  .view-flag {{ font:700 9px var(--mono); letter-spacing:.05em; color:var(--warn); margin-left:8px; vertical-align:2px; }}
  h2, .section-head {{ scroll-margin-top:70px; }}
  @media (max-width:520px) {{
    .combo {{ grid-template-columns:1fr; gap:2px; }}
    .stat-row {{ grid-template-columns:1fr; }}
    .result-strip {{ grid-template-columns:1fr; }}
  }}
  .signal[title] {{ cursor: help; }}
  .placeholder {{ margin:10px 0 22px; padding:12px 16px; border:2px solid var(--line); background:var(--surface); color:var(--muted); }}
  .placeholder p {{ margin:0; font-size:13.5px; }}
  .badge.todo {{ background:var(--surface); color:var(--muted); border-color:var(--muted); }}
  .hr-card {{ border:2px solid var(--ink); background:var(--paper); padding:13px 14px 11px; margin:0 0 12px; }}
  .hr-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:10px; }}
  .hr-card h3 {{ margin:0; font:900 15px var(--display); text-transform:uppercase; }}
  .hr-deploy {{ margin:3px 0 0; color:var(--muted); font:10.5px var(--mono); }}
  .hr-grade {{ flex:0 0 auto; text-align:right; }}
  .hr-grade-letter {{ display:block; font:900 26px/1 var(--display); color:var(--spot-dark); }}
  .hr-grade-note {{ display:block; margin-top:3px; color:var(--muted); font:700 9.5px var(--mono); text-transform:uppercase; letter-spacing:.05em; }}
  .hr-bar-row {{ display:grid; grid-template-columns:108px 1fr 78px; align-items:center; gap:8px; margin:5px 0; font:10.5px var(--mono); }}
  .hr-bar-label {{ color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }}
  .hr-bar-track {{ display:block; height:9px; background:var(--surface); border:1px solid var(--ink); }}
  .hr-bar {{ display:block; height:100%; background:var(--ink); }}
  .hr-bar.is-measured {{ background:var(--spot); }}
  .hr-bar.is-physical {{ background:var(--muted); opacity:.55; }}
  .hr-bar-value {{ text-align:right; font-weight:700; white-space:nowrap; }}
  .hr-bar-value small {{ font-weight:400; color:var(--muted); }}
  .hr-why {{ margin:9px 0 0; color:var(--muted); font-size:12px; }}
  .hr-links {{ margin:7px 0 0; font:10.5px var(--mono); text-transform:uppercase; letter-spacing:.05em; }}
  .hr-links a {{ border-bottom:1px solid currentColor; }}
  .visually-hidden {{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); clip-path:inset(50%); white-space:nowrap; }}
  details.fine {{ margin:0 0 22px; color:var(--muted); font-size:12.5px; }}
  details.fine summary {{ cursor:pointer; font:700 10px var(--mono); text-transform:uppercase; letter-spacing:.06em; }}
  details.fine p {{ margin:6px 0 0; }}
  details.fine .closure-note {{ margin-top:8px; }}
  .signals {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin:0 0 22px; }}
  .signal {{ border:2px solid var(--ink); padding:12px 13px; background:var(--paper); }}
  .signal span {{ display:block; color:var(--muted); font:700 9.5px var(--mono); text-transform:uppercase; letter-spacing:.05em; }}
  .signal b {{ display:block; margin-top:3px; font:900 18px var(--display); text-transform:uppercase; }}
  .signal small {{ display:block; margin-top:4px; color:var(--muted); line-height:1.3; }}
  .section-head {{ display:flex; align-items:end; justify-content:space-between; gap:18px; margin:34px 0 10px; }}
  .section-head h2 {{ margin:0; font:900 25px/1.1 var(--display); text-transform:uppercase; }}
  .section-head p {{ max-width:68ch; margin:0; color:var(--muted); font-size:13px; }}
  .views-grid {{ display:grid; grid-template-columns:1fr; gap:14px; }}
{deferred_views_css}  figure.family-view {{ margin:0; min-width:0; max-width:720px; }}
  .chart-head {{ display:flex; justify-content:space-between; gap:12px; align-items:start; min-height:64px; }}
  .chart-head h3 {{ margin:0; font:900 15px var(--display); text-transform:uppercase; }}
  .chart-head p {{ margin:3px 0 0; color:var(--muted); font-size:11.5px; line-height:1.35; }}
  .metric-switch, .coverage-switch {{ display:flex; flex-wrap:wrap; gap:4px; }}
  .metric-switch {{ justify-content:end; }}
  .metric-switch button, .coverage-switch button {{ appearance:none; border:1px solid var(--ink); padding:4px 7px; background:transparent; color:var(--ink); font:700 9px var(--mono); text-transform:uppercase; cursor:pointer; }}
  .metric-switch button[aria-pressed="true"], .coverage-switch button[aria-selected="true"] {{ background:var(--ink); color:var(--paper); }}
  .family-chart {{ min-height:210px; }}
  .gap-line {{ height:0!important; border-top:2px dashed var(--muted); background:transparent!important; }}
  .metric-fallback {{ width:100%; margin-top:9px; border-collapse:collapse; font-size:11px; }}
  .metric-fallback caption {{ padding-bottom:4px; text-align:left; font:700 9px var(--mono); text-transform:uppercase; }}
  .metric-fallback th, .metric-fallback td {{ padding:5px 7px; border-top:1px solid var(--line); text-align:left; vertical-align:top; }}
  .metric-fallback th {{ width:72px; font:700 9px var(--mono); text-transform:uppercase; }}
  .proof-links {{ display:block; margin-top:5px; }}
  .proof-links a {{ border-bottom:1px solid currentColor; }}
  .coverage-panel > p {{ margin:8px 0 0; color:var(--muted); font:11px var(--mono); }}
  .coverage-table td {{ min-width:130px; white-space:normal; }}
  .coverage-cell > a {{ display:block; color:inherit; text-decoration:none; }}
  .coverage-cell .cell-packet {{ display:inline-block; margin-top:5px; border-bottom:1px solid currentColor; color:var(--muted); font:700 8.5px var(--mono); text-transform:uppercase; }}
  .coverage-cell .state {{ display:block; font:700 9px var(--mono); text-transform:uppercase; }}
  .coverage-cell b {{ display:block; margin-top:3px; font:12px var(--mono); }}
  .is-lab-measured .state, .coverage-legend .is-lab-measured {{ color:var(--good); }}
  .is-lab-screened .state, .coverage-legend .is-lab-screened {{ color:var(--warn); }}
  .is-estimated .state, .coverage-legend .is-estimated {{ color:var(--spot-dark); }}
  .is-quarantined .state, .coverage-legend .is-quarantined {{ color:#a12820; }}
  .is-unsupported .state, .coverage-legend .is-unsupported {{ color:var(--muted); }}
  .is-closed .state, .coverage-legend .is-closed {{ color:var(--warn); }}
  .is-missing .state, .coverage-legend .is-missing {{ color:var(--muted); }}
  .coverage-legend {{ display:flex; flex-wrap:wrap; gap:5px 14px; margin:8px 0 0; font:10px var(--mono); text-transform:uppercase; }}
  .closure-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:8px; }}
  .closure-card {{ display:block; border:1px solid var(--line); border-left:5px solid var(--warn); padding:9px 11px; background:var(--surface); }}
  .closure-card span {{ display:block; margin-bottom:4px; color:var(--muted); font:9px var(--mono); text-transform:uppercase; }}
  .closure-card b {{ font-size:11.5px; line-height:1.3; }}
  .packet-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(255px,1fr)); gap:10px; }}
  .packet-card {{ display:block; border:2px solid var(--ink); padding:12px 13px; background:var(--paper); }}
  .packet-card:hover {{ border-color:var(--spot); }}
  .packet-top {{ display:flex; justify-content:space-between; gap:8px; color:var(--muted); font:700 9px var(--mono); text-transform:uppercase; }}
  .packet-top b {{ color:var(--good); text-align:right; }}
  .packet-badges {{ display:flex; justify-content:end; align-items:center; flex-wrap:wrap; gap:4px 7px; text-align:right; }}
  .opt-grade {{ padding:1px 4px; border:1px solid var(--spot); color:var(--spot-dark); }}
  .opt-grade[data-ready="true"] {{ background:var(--spot); color:#fff; }}
  .packet-card h3 {{ margin:7px 0 5px; font:900 15px/1.15 var(--display); text-transform:uppercase; }}
  .packet-card p {{ margin:0; color:var(--muted); font-size:12px; }}
  .packet-workload {{ display:block; margin-top:5px; color:var(--muted); font:9.5px/1.35 var(--mono); }}
  .grade-rail {{ display:flex; flex-wrap:wrap; gap:4px; margin-top:8px; }}
  .curated-grade {{ padding:2px 5px; border:1px solid var(--ink); font:800 8.5px var(--mono); text-transform:uppercase; }}
  .curated-grade.is-pending {{ border-color:var(--line); color:var(--muted); }}
  .coverage-rail {{ display:flex; flex-wrap:wrap; gap:3px; margin-top:9px; }}
  .coverage-rail span {{ padding:2px 5px; background:var(--surface); border:1px solid var(--line); font:8.5px var(--mono); text-transform:uppercase; }}
  .scope-note {{ margin:12px 0 0; padding:10px 12px; border-left:5px solid var(--spot); background:var(--surface); font-size:12.5px; }}
  @media (max-width:850px) {{ .signals {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .views-grid {{ grid-template-columns:1fr; }} }}
  @media (max-width:520px) {{ .signals {{ grid-template-columns:1fr 1fr; }} .section-head, .chart-head {{ display:block; }} .metric-switch {{ justify-content:start; margin-top:7px; }} }}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="site-nav"><div class="wrap">
  <a class="brand" href="../index.html"><span class="brand-mark" aria-hidden="true">▮▮▮</span>neural.download</a>
  <nav aria-label="Primary"><a href="index.html" aria-current="page">Models</a><a href="../learn.html">Learn</a><a href="../guides.html">Recipes</a><a href="../index.html#lab-speeds">Benchmarks</a><a href="../index.html#contribute">Contribute</a><a class="github" href="https://github.com/steveseguin/b70-optimization-lab">GitHub</a></nav>
</div></div>
<header class="hero"><div class="wrap">
  <p class="breadcrumb"><a href="../index.html">Home</a> / <a href="index.html">Models</a> / {esc(family.get('display_name'))}</p>
  <h1>{esc(family.get('display_name'))}</h1>
  <p>{esc(family.get('summary'))}</p>
{headline_html}  <div class="lineage">{lineage}</div>
</div></header>
<main id="main"><div class="wrap family-main">
{strip_html}{cta_html}
  <dl class="meta-strip" aria-label="Family signals">{signal_cards}</dl>

  <div class="section-head" id="packets"><div><h2>Packets and recipes</h2><p>The deployment variants of this family, at every maturity.</p></div></div>
  <div class="packet-grid">{packets}</div>

{coverage_section}

  <div class="section-head" id="measured"><div><h2>Measured results</h2><p>Every number links to its proof.</p></div><a class="inline" href="{esc(source)}">family data</a></div>
  <div class="views-grid">{views}</div>{deferred_views_html}
  <details class="fine"><summary>Fine print</summary><p>{esc(boundary)}. Measurements, artifact hashes, outputs, quality decisions, and speed stay pinned to their exact recorded identity.</p>{closures_section}</details>
{multiuser_html}{projection_html}
  <div class="related"><h2>Keep going</h2><div class="related-grid"><a href="../guides.html"><b>Recipes</b><span>Filter runnable packets</span></a><a href="../learn/models.html"><b>Choose a model</b><span>Quality and deployment trade-offs</span></a><a href="../learn/hardware.html"><b>Hardware</b><span>Cards, memory, and topology</span></a><a href="{esc(source)}"><b>Family data</b><span>Exact normalized coverage source</span></a></div></div>
</div></main>
<footer><div class="wrap"><span>Unofficial lab, not affiliated with Intel. Measurements link to proof; estimates are labeled.</span><span><a href="../learn.html">Learn</a> · <a href="../guides.html">Recipes</a> · <a href="https://github.com/steveseguin/b70-optimization-lab">GitHub</a></span></div></footer>
<script defer src="../learn/assets/mlbottleneck-bridge.js?v={bridge_version()}"></script>
<script>
(() => {{
  document.querySelectorAll('[data-family-view]').forEach(view => {{
    view.querySelectorAll('[data-metric-button]').forEach(button => button.addEventListener('click', () => {{
      const metric = button.dataset.metricButton;
      view.querySelectorAll('[data-metric-button]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
      view.querySelectorAll('[data-family-metric]').forEach(chart => chart.hidden = chart.dataset.familyMetric !== metric);
      view.querySelectorAll('[data-family-summary]').forEach(summary => summary.hidden = summary.dataset.familySummary !== metric);
    }}));
  }});
  const coverageTabs = Array.from(document.querySelectorAll('[data-coverage-button]'));
  const activateCoverageTab = (button, moveFocus = false) => {{
    const panel = button.dataset.coverageButton;
    coverageTabs.forEach(item => {{
      item.setAttribute('aria-selected', String(item === button));
      item.tabIndex = item === button ? 0 : -1;
    }});
    document.querySelectorAll('[data-coverage-panel]').forEach(item => item.hidden = item.dataset.coveragePanel !== panel);
    if (moveFocus) button.focus();
  }};
  coverageTabs.forEach((button, index) => {{
    button.addEventListener('click', () => activateCoverageTab(button));
    button.addEventListener('keydown', event => {{
      let target = null;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') target = coverageTabs[(index + 1) % coverageTabs.length];
      if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') target = coverageTabs[(index - 1 + coverageTabs.length) % coverageTabs.length];
      if (event.key === 'Home') target = coverageTabs[0];
      if (event.key === 'End') target = coverageTabs[coverageTabs.length - 1];
      if (target) {{ event.preventDefault(); activateCoverageTab(target, true); }}
    }});
  }});
}})();
</script>
</body>
</html>
'''


def generate(check: bool) -> int:
    errors: list[str] = []
    try:
        catalog = load_json(CATALOG)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 1
    if catalog.get("format") != "neural-download-model-family-catalog-v1":
        errors.append("families/catalog.json: unsupported format")
    expected: list[tuple[Path, str]] = []
    family_ids: set[str] = set()
    packet_owners: dict[str, list[str]] = {}
    entries = catalog.get("families")
    if not isinstance(entries, list):
        errors.append("families/catalog.json: families must be a list")
        entries = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"families/catalog.json: families[{index}] must be an object")
            continue
        source = safe_repo_path(entry.get("manifest"))
        if source is None:
            errors.append(
                f"families/catalog.json: families[{index}] manifest must stay inside the repository"
            )
            continue
        try:
            family = load_json(source)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(str(error))
            continue
        family_errors = validate_family(family, source)
        errors.extend(family_errors)
        family_id = family.get("id")
        id_matches = family_id == entry.get("id")
        if not id_matches:
            errors.append(
                f"{source_label(source)}: family id {family_id} does not match catalog id {entry.get('id')}"
            )
        duplicate = isinstance(family_id, str) and family_id in family_ids
        if duplicate:
            errors.append(f"families/catalog.json: duplicate family id {family_id}")
        if isinstance(family_id, str):
            family_ids.add(family_id)
        if family_errors or not id_matches or duplicate or not isinstance(family_id, str):
            continue
        for packet in family.get("packets") or []:
            if isinstance(packet, dict) and isinstance(packet.get("id"), str):
                packet_owners.setdefault(packet["id"], []).append(family_id)
        output = OUT_DIR / f"{family_id}.html"
        rendered = family_page(family)
        expected.append((output, rendered))
    try:
        package_catalog = load_json(PACKAGE_CATALOG)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    else:
        package_entries = package_catalog.get("packages")
        if not isinstance(package_entries, list):
            errors.append("packages/catalog.json: packages must be a list")
            package_entries = []
        published_ids = {
            package.get("id")
            for package in package_entries
            if isinstance(package, dict) and isinstance(package.get("id"), str)
        }
        missing = sorted(published_ids - packet_owners.keys())
        duplicated = sorted(
            packet_id
            for packet_id, owners in packet_owners.items()
            if packet_id in published_ids and len(owners) != 1
        )
        if missing:
            errors.append(
                "families/catalog.json: published packages without a family: " + ", ".join(missing)
            )
        if duplicated:
            errors.append(
                "families/catalog.json: published packages assigned to multiple families: "
                + ", ".join(duplicated)
            )
    registry_summary = {"lanes": 0, "artifacts": 0}
    expected_artifacts, inventory_errors = public_evidence_inventory()
    errors.extend(inventory_errors)
    try:
        coverage_registry = load_json(COVERAGE_REGISTRY)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    else:
        registry_errors, registry_summary = validate_coverage_registry(
            coverage_registry, family_ids, expected_artifacts
        )
        errors.extend(registry_errors)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if check:
        drift = []
        for output, rendered in expected:
            current = output.read_text(encoding="utf-8") if output.exists() else None
            if current != rendered:
                drift.append(str(output.relative_to(ROOT)))
        if drift:
            print("family page drift: " + ", ".join(drift), file=sys.stderr)
            return 1
        print(
            f"family pages current: {len(expected)}; coverage registry: "
            f"{registry_summary['lanes']} canonical lanes / "
            f"{registry_summary['artifacts']} public artifacts"
        )
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for output, rendered in expected:
        output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"wrote {len(expected)} family page(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate and fail if generated pages drift")
    args = parser.parse_args()
    rc = generate(args.check)
    if rc == 0 and not args.check:
        # models/index.html counts every family's packets, so it goes stale the
        # moment a family manifest changes. Regenerating it here means a manifest
        # commit can never leave CI's `git diff --exit-code -- models` red.
        import subprocess

        subprocess.run([sys.executable, str(ROOT / "tools" / "build-model-pages.py")], check=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
