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
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
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
    "quarantined": "Quarantined: it ran, but failed a quality gate; kept for the record, do not use",
    "unsupported": "The runtime or hardware cannot run this combination",
    "missing": "Not tested yet",
}
ALLOWED_GRADES = {"A", "B", "C", "D"}
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SELECTOR_KEY_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
POINT_METRIC_PREFIX = {
    "decode_tok_s": "D",
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
    view: dict[str, Any], row: Any, column: Any
) -> dict[str, Any]:
    selectors = dict(view.get("fixed_selectors") or {})
    selectors[coverage_axis(view, "row")["key"]] = row
    selectors[coverage_axis(view, "column")["key"]] = column
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
    if measurement.get("state") not in CURVE_STATES:
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


def validate_family(family: dict[str, Any], source: Path) -> list[str]:
    label = source_label(source)
    errors: list[str] = []
    if family.get("format") != "neural-download-model-family-v1":
        errors.append(f"{label}: unsupported format")
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
    estimates = object_list(family.get("estimates"), f"{label}: estimates", errors)
    views = object_list(family.get("views"), f"{label}: views", errors)
    coverage_views = object_list(
        family.get("coverage_views"), f"{label}: coverage_views", errors
    )
    closures = object_list(
        family.get("family_closures"), f"{label}: family_closures", errors
    )

    revision_ids: set[str] = set()
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
            if states - CURVE_STATES:
                errors.append(
                    f"{label}: view {view_id} series {series.get('label')} uses non-curve states {sorted(states - CURVE_STATES)}"
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
                effective_cell_selectors(coverage, row_value, column_value)
                if row_value is not None and column_value is not None
                else {}
            )
            if isinstance(packet_id, str) and packet_id in packet_by_id:
                packet = packet_by_id[packet_id]
                packet_claims = {
                    "revision": packet.get("revision"),
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

            selector_strict = named_axes or bool(fixed_selectors)
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
            if measurement.get("state") not in CURVE_STATES:
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

    def sx(value: float) -> float:
        if x1 == x0:
            return (left + width - right) / 2
        return left + (value - x0) / (x1 - x0) * (width - left - right)

    def sy(value: float) -> float:
        return top + (1 - (value - y0) / (y1 - y0)) * (height - top - bottom)

    label, unit = METRICS[metric]
    hidden = "" if visible else " hidden"
    lines = [
        f'<svg class="family-chart" data-family-metric="{esc(metric)}"{hidden} viewBox="0 0 {width} {height}" role="img" aria-label="{esc(view.get("title"))}: {esc(label)}">'
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
            drawable.append((point["x"], mean, min(point["values"]), max(point["values"])))
        path = " ".join(
            f'{"M" if index == 0 else "L"}{sx(x):.1f},{sy(mean):.1f}'
            for index, (x, mean, _low, _high) in enumerate(drawable)
        )
        if not view.get("discrete") and len(drawable) > 1:
            lines.append(
                f'<path d="{path}" fill="none" stroke="{item["color"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>'
            )
        for x, mean, low, high in drawable:
            if high > low:
                lines.append(
                    f'<line x1="{sx(x):.1f}" y1="{sy(low):.1f}" x2="{sx(x):.1f}" y2="{sy(high):.1f}" stroke="{item["color"]}" stroke-width="5" stroke-linecap="round"></line>'
                )
            lines.append(
                f'<circle cx="{sx(x):.1f}" cy="{sy(mean):.1f}" r="4" fill="var(--paper)" stroke="{item["color"]}" stroke-width="2.5"></circle>'
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


def view_card(family: dict[str, Any], view: dict[str, Any]) -> str:
    charts = []
    summaries = []
    buttons = []
    for index, metric in enumerate(view.get("metrics") or []):
        svg, summary = chart_svg(family, view, metric, index == 0)
        if not svg:
            continue
        charts.append(svg)
        summaries.append(
            f'<div data-family-summary="{esc(metric)}"{"" if index == 0 else " hidden"}>{summary}</div>'
        )
        label, _unit = METRICS[metric]
        buttons.append(
            f'<button type="button" data-metric-button="{esc(metric)}" aria-pressed="{"true" if index == 0 else "false"}">{esc(label)}</button>'
        )
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
    return f'''<figure class="chart family-view" data-family-view="{esc(view.get('id'))}">
  <div class="chart-head"><div><h3>{esc(view.get('title'))}</h3><p>{esc(view.get('subtitle'))}</p></div><div class="metric-switch">{"".join(buttons)}</div></div>
  {"".join(charts)}
  <div class="legend">{"".join(legends)}</div>
  <figcaption>{"".join(summaries)}<span class="proof-links">{links}</span></figcaption>
</figure>'''


def coverage_tables(family: dict[str, Any]) -> str:
    by_id = {measurement["id"]: measurement for measurement in records(family)}
    estimates = {estimate["id"]: estimate for estimate in family.get("estimates") or []}
    packets = {packet["id"]: packet for packet in family.get("packets") or []}
    buttons = []
    tables = []
    state_labels = STATE_GLYPHS
    for index, view in enumerate(family.get("coverage_views") or []):
        row_axis = coverage_axis(view, "row")
        column_axis = coverage_axis(view, "column")
        tab_id = f'coverage-tab-{view.get("id")}'
        panel_id = f'coverage-panel-{view.get("id")}'
        buttons.append(
            f'<button type="button" role="tab" id="{esc(tab_id)}" aria-controls="{esc(panel_id)}" data-coverage-button="{esc(view.get("id"))}" aria-selected="{"true" if index == 0 else "false"}" tabindex="{0 if index == 0 else -1}">{esc(view.get("label"))}</button>'
        )
        head = "".join(
            f'<th scope="col">{esc(axis_value_label(column_axis, column))}</th>'
            for column in column_axis["values"]
        )
        rows = []
        for row in row_axis["values"]:
            cells = []
            for column in column_axis["values"]:
                cell = view["cells"][f"{row}:{column}"]
                state = cell["state"]
                title = state_labels[state]
                evidence_id = cell.get("evidence_id")
                estimate_id = cell.get("estimate_id")
                evidence = (
                    by_id[evidence_id].get("evidence")
                    if evidence_id
                    else cell.get("evidence") or view.get("evidence")
                )
                label_text = str(cell.get("label", ""))
                if evidence_id and cell.get("point_x") is not None:
                    observed = by_id[evidence_id]
                    point = next(
                        point
                        for point in observed.get("points") or []
                        if point.get("x") == cell["point_x"]
                    )
                    label_text = point_metric_label(point)
                estimate_note = ""
                if estimate_id:
                    estimate = estimates[estimate_id]
                    interval = estimate["interval"]
                    label_text = (
                        f'≈ {fmt(estimate["value"])} {estimate["unit"]} '
                        f'({fmt(interval["low"])}–{fmt(interval["high"])})'
                    )
                    evidence = estimate["record"]
                    estimate_note = (
                        f'{estimate["engine"]["name"]} {estimate["engine"]["version"]}; '
                        f'snapshot {estimate["engine"]["snapshot_sha256"]}'
                    )
                glyph = title.split(" ", 1)[0]
                meaning = STATE_MEANING.get(state, title)
                body = (
                    f'<span class="state" title="{esc(meaning)}">{esc(glyph)}'
                    f'<span class="visually-hidden">{esc(title.split(" ", 1)[1] if " " in title else title)}</span></span>'
                    f'<b>{esc(label_text)}</b>'
                )
                if evidence:
                    body = f'<a href="{esc(evidence_href(evidence))}" aria-label="{esc(title)}: {esc(label_text)}; open record">{body}</a>'
                packet_link = ""
                packet_id = cell.get("packet_id")
                if packet_id:
                    packet = packets[packet_id]
                    manifest = str(packet.get("manifest", ""))
                    href = (
                        f"{packet_id}.html"
                        if manifest.startswith("packages/") and manifest.endswith("package.json")
                        else evidence_href(manifest)
                    )
                    packet_link = f'<a class="cell-packet" href="{esc(href)}">packet</a>'
                cells.append(
                    f'<td class="coverage-cell is-{esc(state)}" title="{esc(cell.get("reason") or estimate_note or view.get("decision_note") or meaning)}">{body}{packet_link}</td>'
                )
            rows.append(
                f'<tr><th scope="row">{esc(axis_value_label(row_axis, row))}</th>{"".join(cells)}</tr>'
            )
        selectors = " · ".join(
            f"{key}={value}" for key, value in (view.get("fixed_selectors") or {}).items()
        )
        scope = str(view.get("fixed") or "")
        if selectors:
            scope = f"{scope} Fixed: {selectors}."
        table_label = f'{view.get("label")} {row_axis["label"]} by {column_axis["label"]} coverage'
        tables.append(
            f'<div class="coverage-panel" role="tabpanel" id="{esc(panel_id)}" aria-labelledby="{esc(tab_id)}" data-coverage-panel="{esc(view.get("id"))}"{"" if index == 0 else " hidden"}><p>{esc(scope)}</p><div class="scroller" tabindex="0" role="region" aria-label="{esc(table_label)}"><table class="data coverage-table"><thead><tr><th>{esc(row_axis["label"])} / {esc(column_axis["label"])}</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>'
        )
    legend = "".join(
        f'<span class="is-{esc(state)}">{esc(label)}</span>' for state, label in state_labels.items()
    )
    return f'<div class="coverage-switch" role="tablist" aria-label="Coverage slices">{"".join(buttons)}</div>{"".join(tables)}<div class="coverage-legend">{legend}</div>'


def closure_cards(family: dict[str, Any]) -> str:
    cards = []
    for closure in family.get("family_closures") or []:
        selectors = " · ".join(f"{key}={value}" for key, value in closure["selectors"].items())
        cards.append(
            f'<a class="closure-card is-{esc(closure["state"])}" href="{esc(evidence_href(closure["evidence"]))}">'
            f'<span>{esc(closure["state"])} · {esc(selectors)}</span><b>{esc(closure["reason"])}</b></a>'
        )
    return "".join(cards)


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


def grade_badge(label: str, value: Any) -> str:
    if not isinstance(value, dict):
        return f'<span class="curated-grade is-pending" tabindex="0" title="Not graded yet" aria-label="{esc(label)} not graded yet">{esc(label)} —</span>'
    title = f'{value.get("scope", "")} · {value.get("basis", "")}'
    return (
        f'<span class="curated-grade" tabindex="0" title="{esc(title)}" aria-label="{esc(label)} grade {esc(value.get("grade"))}: {esc(title)}">'
        f'{esc(label)} {esc(value.get("grade"))}</span>'
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
            headroom = '<span class="opt-grade" data-family-headroom-value title="Projected optimization grade is loading; this compares measured speed with the modeled tuned target, not model quality or packet evidence.">OPT …</span>'
        elif projection and value != "—":
            headroom = '<span class="opt-grade" title="OPT is withheld until this measured workload has explicit prompt and output token selectors.">OPT —</span>'
        grades = packet.get("grades") or {}
        revision = revisions.get(packet.get("revision")) or {}
        capability = grades.get("capability") or (revision.get("grades") or {}).get("capability")
        grade_rail = "".join(
            (
                grade_badge("CAP", capability),
                grade_badge("EVID", grades.get("evidence")),
            )
        )
        metric_text = f"{value} {unit}".strip()
        workload_html = (
            f'\n  <small class="packet-workload">{esc(workload)}</small>'
            if workload
            else ""
        )
        cards.append(
            f'''<a class="packet-card" href="{esc(href)}"{attrs}>
  <div class="packet-top"><span>{esc(packet.get('revision'))}</span><span class="packet-badges"><b>{esc(packet.get('evidence_level'))}</b>{headroom}</span></div>
  <h3>{esc(packet.get('label'))}</h3>
  <p><strong>{esc(metric_text)}</strong>{" measured headline" if value != "—" else " evidence packet"} · {esc(packet.get('status'))}</p>{workload_html}
  <div class="grade-rail">{grade_rail}</div>
  <div class="coverage-rail">{coverage}</div>
</a>'''
        )
    return "".join(cards)


def family_page(family: dict[str, Any]) -> str:
    signals = family.get("model_signals") or {}
    popularity = signals.get("popularity") or {}
    architecture = family.get("architecture") or {}
    quality = signals.get("quality_evidence") or {}
    fit = signals.get("b70_fit") or {}
    revisions = family.get("weight_revisions") or []
    transfer = family.get("transfer_scope") or {}
    views = "".join(view_card(family, view) for view in family.get("views") or [])
    packets = packet_cards(family)
    coverage_views = family.get("coverage_views") or []
    coverage = coverage_tables(family) if coverage_views else ""
    closure_items = family.get("family_closures") or []
    closures = closure_cards(family) if closure_items else ""
    lineage = "".join(
        f'<span>{esc(revision.get("label") or revision.get("id"))}'
        + (f' · {esc(revision.get("role"))}' if revision.get("role") else "")
        + "</span>"
        for revision in revisions
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
    # The one number a visitor came for: the best fully-gated measured
    # decode rate in the family, linked to its evidence.
    best = None
    for measurement in records(family):
        if measurement.get("state") != "lab-measured":
            continue
        metrics = measurement.get("metrics") or {}
        values = list(metrics.get("decode_tok_s") or [])
        for point in measurement.get("points") or []:
            if point.get("decode_tok_s") is not None:
                values.append(point["decode_tok_s"])
        if not values:
            continue
        # The current promoted reference outranks historical highs.
        current = "current" in str(measurement.get("promotion_status") or "")
        candidate = (current, max(values), measurement)
        if best is None or (candidate[0], candidate[1]) > (best[0], best[1]):
            best = candidate
    headline_html = ""
    if best:
        _, peak, measurement = best
        runtime_words = " ".join(str(measurement.get("runtime") or "").split()[:2])
        label_bits = [bit for bit in (measurement.get("variant"), runtime_words) if bit]
        evidence = (measurement.get("evidence") or {}).get("primary") if isinstance(measurement.get("evidence"), dict) else None
        headline_html = (
            '  <div class="hero-headline"><span class="big">' + fmt(peak) + '</span>'
            '<span class="unit">tok/s measured</span>'
            '<small>' + esc(" · ".join(label_bits)) + ' · single user, full quality gate</small></div>\n'
        )
    coverage_section = ""
    if coverage_views:
        coverage_section = f'''
  <div class="section-head"><div><h2>Combination coverage</h2><p>One cell per combination &mdash; hover a mark for what it means.</p></div></div>
  {coverage}
'''
    closures_section = ""
    if closure_items:
        closures_section = f'''
  <div class="section-head"><div><h2>Scoped closures</h2><p>Rejected combinations, scoped to the exact selectors shown.</p></div></div>
  <div class="closure-grid">{closures}</div>
'''
    url = f"{SITE}models/{family['id']}.html"
    source = f"../families/{family['id']}.json"
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
    measured_count = sum(
        1
        for item in list(family.get("run_measurements") or [])
        + list(family.get("series_measurements") or [])
        if item.get("state") == "lab-measured"
    )
    estimate_count = len(family.get("estimates") or [])
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(family.get('display_name'))} coverage — neural.download</title>
<meta name="description" content="{esc(family.get('summary'))} Measured topology, context, speed-up, quantization, prefill, TTFT, quality, and packet coverage without merging revision identities.">
<link rel="canonical" href="{esc(url)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{esc(url)}">
<meta property="og:title" content="{esc(family.get('display_name'))} coverage — neural.download">
<meta property="og:description" content="Measured deployment coverage across the axes users actually choose.">
<meta property="og:image" content="{SITE}og-image.png">
<meta name="theme-color" content="#f6f1e5">
<script type="application/ld+json">{json_for_html_script(ld)}</script>
<link rel="stylesheet" href="../learn/learn.css">
<link rel="preconnect" href="https://mlbottleneck.com">
<style>
  .family-main {{ max-width: 1120px; }}
  .lineage {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }}
  .lineage span {{ padding:5px 8px; border:1px solid rgba(255,255,255,.7); font:700 10px var(--mono); text-transform:uppercase; }}
  .hero-headline {{ display:flex; align-items:baseline; gap:10px 14px; flex-wrap:wrap; margin:12px 0 0; }}
  .hero .hero-headline .big {{ font:900 46px/1 var(--display); color:var(--paper, #fff); }}
  .hero .hero-headline .unit {{ font:700 12px var(--mono); text-transform:uppercase; letter-spacing:.05em; color:rgba(255,255,255,.85); }}
  .hero .hero-headline small {{ flex-basis:100%; color:rgba(255,255,255,.75); font-size:12.5px; }}
  .signal[title] {{ cursor: help; }}
  .visually-hidden {{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); clip-path:inset(50%); white-space:nowrap; }}
  details.fine {{ margin:0 0 22px; color:var(--muted); font-size:12.5px; }}
  details.fine summary {{ cursor:pointer; font:700 10px var(--mono); text-transform:uppercase; letter-spacing:.06em; }}
  details.fine p {{ margin:6px 0 0; }}
  .signals {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin:0 0 22px; }}
  .signal {{ border:2px solid var(--ink); padding:12px 13px; background:var(--paper); }}
  .signal span {{ display:block; color:var(--muted); font:700 9.5px var(--mono); text-transform:uppercase; letter-spacing:.05em; }}
  .signal b {{ display:block; margin-top:3px; font:900 18px var(--display); text-transform:uppercase; }}
  .signal small {{ display:block; margin-top:4px; color:var(--muted); line-height:1.3; }}
  .section-head {{ display:flex; align-items:end; justify-content:space-between; gap:18px; margin:34px 0 10px; }}
  .section-head h2 {{ margin:0; font:900 25px/1.1 var(--display); text-transform:uppercase; }}
  .section-head p {{ max-width:68ch; margin:0; color:var(--muted); font-size:13px; }}
  .views-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }}
  figure.family-view {{ margin:0; min-width:0; }}
  .chart-head {{ display:flex; justify-content:space-between; gap:12px; align-items:start; min-height:64px; }}
  .chart-head h3 {{ margin:0; font:900 15px var(--display); text-transform:uppercase; }}
  .chart-head p {{ margin:3px 0 0; color:var(--muted); font-size:11.5px; line-height:1.35; }}
  .metric-switch, .coverage-switch {{ display:flex; flex-wrap:wrap; gap:4px; }}
  .metric-switch {{ justify-content:end; }}
  .metric-switch button, .coverage-switch button {{ appearance:none; border:1px solid var(--ink); padding:4px 7px; background:transparent; color:var(--ink); font:700 9px var(--mono); text-transform:uppercase; cursor:pointer; }}
  .metric-switch button[aria-pressed="true"], .coverage-switch button[aria-selected="true"] {{ background:var(--ink); color:var(--paper); }}
  .family-chart {{ min-height:210px; }}
  .gap-line {{ height:0!important; border-top:2px dashed var(--muted); background:transparent!important; }}
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
  <nav aria-label="Primary"><a href="../index.html">Home</a><a href="index.html" aria-current="page">Models</a><a href="../learn.html">Learn</a><a href="../guides.html">Guide library</a><a href="../index.html#lab-speeds">Benchmarks</a><a class="github" href="https://github.com/steveseguin/b70-optimization-lab">GitHub</a></nav>
</div></div>
<header class="hero"><div class="wrap">
  <p class="breadcrumb"><a href="../index.html">Home</a> / <a href="index.html">Models</a> / {esc(family.get('name'))}</p>
  <h1>{esc(family.get('display_name'))}</h1>
  <p>{esc(family.get('summary'))}</p>
{headline_html}
  <div class="lineage">{lineage}</div>
</div></header>
<main id="main"><div class="wrap family-main">
  <div class="signals" aria-label="Family signals">
    <div class="signal" title="{esc(fit.get('scope') or 'local deployment fit')}, reviewed {esc(fit.get('reviewed_at') or family.get('updated_at'))}"><span>B70 fit</span><b>{esc(fit.get('band') or 'Pending')}</b></div>
    <div class="signal" title="{esc(quality.get('scope') or 'No family-wide quality score is inferred from speed evidence.')}"><span>Quality evidence</span><b>{esc(str(quality.get('band') or 'Pending').replace('-', ' '))}</b></div>
    <div class="signal" title="{esc(popularity_detail)}"><span>Interest</span><b>{esc(popularity_value)}</b></div>
    <div class="signal" title="Run arms and measured series; every point links to proof"><span>Evidence slices</span><b>{measured_count}</b></div>
    <div class="signal" title="Versioned gap estimates only; live OPT grades stay separate"><span>Stored estimates</span><b>{estimate_count}</b></div>
  </div>
  <details class="fine"><summary>Transfer boundary</summary><p>{esc(boundary)}. Measurements, artifact hashes, outputs, quality decisions, and speed stay pinned to their exact recorded identity.</p></details>

  <div class="section-head"><div><h2>Measured slices</h2><p>Every point links to its proof; the buttons switch metric.</p></div><a class="inline" href="{esc(source)}">family data</a></div>
  <div class="views-grid">{views}</div>

{coverage_section}{closures_section}

  <div class="section-head"><div><h2>Packets and recipes</h2><p>The deployment variants of this family, at every maturity.</p></div></div>
  <div class="packet-grid">{packets}</div>

  <div class="related"><h2>Keep going</h2><div class="related-grid"><a href="../guides.html"><b>Guide library</b><span>Filter runnable packets</span></a><a href="../learn/models.html"><b>Choose a model</b><span>Quality and deployment trade-offs</span></a><a href="../learn/hardware.html"><b>Hardware</b><span>Cards, memory, and topology</span></a><a href="{esc(source)}"><b>Family data</b><span>Exact normalized coverage source</span></a></div></div>
</div></main>
<footer><div class="wrap"><span>Unofficial lab, not affiliated with Intel. Measurements link to proof; estimates are labeled.</span><span><a href="../learn.html">Learn</a> · <a href="../guides.html">Guide library</a> · <a href="https://github.com/steveseguin/b70-optimization-lab">GitHub</a></span></div></footer>
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
    return generate(args.check)


if __name__ == "__main__":
    raise SystemExit(main())
