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
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "families" / "catalog.json"
PACKAGE_CATALOG = ROOT / "packages" / "catalog.json"
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


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def fmt(value: float | int | None, digits: int = 2) -> str:
    if value is None:
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


def nested(item: dict[str, Any], dotted: str) -> Any:
    current: Any = item
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def evidence_href(path: str) -> str:
    if path.startswith(("https://", "http://")):
        return path
    return GITHUB + path


def bridge_version() -> str:
    return hashlib.sha1(BRIDGE.read_bytes()).hexdigest()[:10]


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)}: root must be an object")
    return value


def local_evidence_paths(value: Any, key: str | None = None):
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from local_evidence_paths(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from local_evidence_paths(child, key)
    elif key in {"evidence", "manifest", "model_manifest"} and isinstance(value, str):
        if not value.startswith(("https://", "http://")):
            yield value


def validate_family(family: dict[str, Any], source: Path) -> list[str]:
    label = str(source.relative_to(ROOT))
    errors: list[str] = []
    if family.get("format") != "neural-download-model-family-v1":
        errors.append(f"{label}: unsupported format")
    if not family.get("id") or not family.get("name"):
        errors.append(f"{label}: id and name are required")

    packet_ids: set[str] = set()
    for packet in family.get("packets") or []:
        packet_id = packet.get("id")
        if not packet_id:
            errors.append(f"{label}: packet without id")
            continue
        if packet_id in packet_ids:
            errors.append(f"{label}: duplicate packet id {packet_id}")
        packet_ids.add(packet_id)
        manifest = packet.get("manifest", "")
        if str(manifest).startswith("packages/") and str(manifest).endswith("package.json"):
            try:
                package = load_json(ROOT / manifest)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                errors.append(str(error))
            else:
                if package.get("id") != packet_id:
                    errors.append(
                        f"{label}: packet {packet_id} does not match manifest id {package.get('id')}"
                    )

    all_measurements = list(family.get("run_measurements") or []) + list(
        family.get("series_measurements") or []
    )
    measurement_ids: set[str] = set()
    for measurement in all_measurements:
        mid = measurement.get("id")
        if not mid:
            errors.append(f"{label}: measurement without id")
            continue
        if mid in measurement_ids:
            errors.append(f"{label}: duplicate measurement id {mid}")
        measurement_ids.add(mid)
        if measurement.get("state") not in ALLOWED_STATES:
            errors.append(f"{label}: {mid} has invalid state {measurement.get('state')}")
        if not measurement.get("evidence"):
            errors.append(f"{label}: {mid} lacks evidence")
        metrics = measurement.get("metrics")
        points = measurement.get("points")
        if not metrics and not points:
            errors.append(f"{label}: {mid} has no metrics or points")
        if isinstance(metrics, dict):
            for metric, values in metrics.items():
                if metric not in METRICS:
                    errors.append(f"{label}: {mid} uses unknown metric {metric}")
                if not isinstance(values, list) or not values or any(
                    not isinstance(value, (int, float)) for value in values
                ):
                    errors.append(f"{label}: {mid}.{metric} must be a non-empty numeric list")
        if isinstance(points, list):
            for index, point in enumerate(points):
                if not isinstance(point, dict) or not isinstance(point.get("x"), (int, float)):
                    errors.append(f"{label}: {mid}.points[{index}] needs numeric x")
                    continue
                if not any(metric in point for metric in METRICS):
                    errors.append(f"{label}: {mid}.points[{index}] has no recognized metric")

    for view in family.get("views") or []:
        for metric in view.get("metrics") or []:
            if metric not in METRICS:
                errors.append(f"{label}: view {view.get('id')} uses unknown metric {metric}")
        for series in view.get("series") or []:
            states = set()
            for mid in series.get("measurement_ids") or []:
                if mid not in measurement_ids:
                    errors.append(f"{label}: view {view.get('id')} references missing {mid}")
                else:
                    states.add(next(item.get("state") for item in all_measurements if item.get("id") == mid))
            if len(states) > 1:
                errors.append(
                    f"{label}: view {view.get('id')} series {series.get('label')} mixes states {sorted(states)}"
                )

    for coverage in family.get("coverage_views") or []:
        expected = {
            f"{row}:{column}"
            for row in coverage.get("rows") or []
            for column in coverage.get("columns") or []
        }
        cells = coverage.get("cells") or {}
        if set(cells) != expected:
            errors.append(
                f"{label}: coverage {coverage.get('id')} cells do not exactly match rows×columns"
            )
        for cell_id, cell in cells.items():
            if cell.get("state") not in ALLOWED_STATES:
                errors.append(
                    f"{label}: coverage {coverage.get('id')} cell {cell_id} has invalid state"
                )
            evidence_id = cell.get("evidence_id")
            if evidence_id and evidence_id not in measurement_ids:
                errors.append(
                    f"{label}: coverage {coverage.get('id')} cell {cell_id} references missing {evidence_id}"
                )
            if cell.get("state") in {"lab-measured", "community-measured", "estimated"} and not evidence_id:
                errors.append(
                    f"{label}: coverage {coverage.get('id')} cell {cell_id} needs a measurement evidence_id"
                )
            if cell.get("state") == "lab-screened" and not (evidence_id or cell.get("evidence") or coverage.get("evidence")):
                errors.append(
                    f"{label}: coverage {coverage.get('id')} screened cell {cell_id} lacks evidence"
                )

    for closure in family.get("family_closures") or []:
        if closure.get("state") not in ALLOWED_STATES:
            errors.append(f"{label}: family closure has invalid state {closure.get('state')}")
        if not closure.get("selectors") or not closure.get("reason") or not closure.get("evidence"):
            errors.append(f"{label}: family closure needs selectors, reason, and evidence")

    for rel in local_evidence_paths(family):
        if not (ROOT / rel).exists():
            errors.append(f"{label}: evidence path does not exist: {rel}")
    return errors


def collect_view_series(
    family: dict[str, Any], view: dict[str, Any], metric: str
) -> list[dict[str, Any]]:
    by_id = {
        measurement["id"]: measurement
        for measurement in list(family.get("run_measurements") or [])
        + list(family.get("series_measurements") or [])
    }
    output: list[dict[str, Any]] = []
    for index, spec in enumerate(view.get("series") or []):
        points: list[dict[str, Any]] = []
        evidence: list[str] = []
        states: set[str] = set()
        for mid in spec.get("measurement_ids") or []:
            measurement = by_id[mid]
            states.add(measurement.get("state", "lab-measured"))
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
        dash = ' stroke-dasharray="7 5"' if item["state"] == "estimated" else ""
        if not view.get("discrete") and len(drawable) > 1:
            lines.append(
                f'<path d="{path}" fill="none" stroke="{item["color"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"{dash}></path>'
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
        for measurement in list(family.get("run_measurements") or [])
        + list(family.get("series_measurements") or [])
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
    by_id = {
        measurement["id"]: measurement
        for measurement in list(family.get("run_measurements") or [])
        + list(family.get("series_measurements") or [])
    }
    buttons = []
    tables = []
    state_labels = {
        "lab-measured": "● measured",
        "lab-screened": "△ screened",
        "community-measured": "◐ community",
        "estimated": "≈ estimate",
        "closed": "■ closed",
        "quarantined": "! quarantine",
        "unsupported": "× unsupported",
        "missing": "○ missing",
    }
    for index, view in enumerate(family.get("coverage_views") or []):
        buttons.append(
            f'<button type="button" data-coverage-button="{esc(view.get("id"))}" aria-pressed="{"true" if index == 0 else "false"}">{esc(view.get("label"))}</button>'
        )
        head = "".join(f"<th scope=\"col\">TP{column}</th>" for column in view["columns"])
        rows = []
        for row in view["rows"]:
            cells = []
            for column in view["columns"]:
                cell = view["cells"][f"{row}:{column}"]
                state = cell["state"]
                title = state_labels[state]
                evidence_id = cell.get("evidence_id")
                evidence = (
                    by_id[evidence_id].get("evidence")
                    if evidence_id
                    else cell.get("evidence") or view.get("evidence")
                )
                body = f'<span class="state">{esc(title)}</span><b>{esc(cell.get("label", ""))}</b>'
                if evidence:
                    body = f'<a href="{esc(evidence_href(evidence))}" aria-label="{esc(title)}: {esc(cell.get("label", ""))}; open evidence">{body}</a>'
                cells.append(
                    f'<td class="coverage-cell is-{esc(state)}" title="{esc(cell.get("reason") or view.get("decision_note") or "")}">{body}</td>'
                )
            rows.append(f'<tr><th scope="row">MTP{row}</th>{"".join(cells)}</tr>')
        tables.append(
            f'<div class="coverage-panel" data-coverage-panel="{esc(view.get("id"))}"{"" if index == 0 else " hidden"}><p>{esc(view.get("fixed"))}</p><div class="scroller" tabindex="0" role="region" aria-label="{esc(view.get("label"))} TP and MTP coverage"><table class="data coverage-table"><thead><tr><th>MTP / TP</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>'
        )
    legend = "".join(
        f'<span class="is-{esc(state)}">{esc(label)}</span>' for state, label in state_labels.items()
    )
    return f'<div class="coverage-switch">{"".join(buttons)}</div>{"".join(tables)}<div class="coverage-legend">{legend}</div>'


def closure_cards(family: dict[str, Any]) -> str:
    cards = []
    for closure in family.get("family_closures") or []:
        selectors = " · ".join(f"{key}={value}" for key, value in closure["selectors"].items())
        cards.append(
            f'<a class="closure-card is-{esc(closure["state"])}" href="{esc(evidence_href(closure["evidence"]))}">'
            f'<span>{esc(closure["state"])} · {esc(selectors)}</span><b>{esc(closure["reason"])}</b></a>'
        )
    return "".join(cards)


def package_metric(packet: dict[str, Any]) -> tuple[str, str, str, float | None]:
    manifest = packet.get("manifest", "")
    if not str(manifest).startswith("packages/") or not str(manifest).endswith("package.json"):
        return "—", "", evidence_href(str(manifest)), None
    package = load_json(ROOT / manifest)
    metric = ((package.get("library") or {}).get("featured_metric") or {})
    raw_value = metric.get("value")
    value = fmt(raw_value)
    unit = metric.get("unit", "tok/s")
    return value, unit, f"{packet['id']}.html", float(raw_value) if isinstance(raw_value, (int, float)) else None


def packet_cards(family: dict[str, Any]) -> str:
    cards = []
    for packet in family.get("packets") or []:
        value, unit, href, raw_value = package_metric(packet)
        coverage = "".join(f"<span>{esc(item)}</span>" for item in packet.get("coverage") or [])
        projection = packet.get("projection") or {}
        attrs = ""
        headroom = ""
        if projection and value != "—":
            attrs = (
                f' data-family-headroom data-ml-model="{esc(projection.get("model"))}"'
                f' data-ml-quant="{esc(projection.get("quant"))}" data-ml-runtime="{esc(projection.get("runtime"))}"'
                f' data-ml-spec="{esc(projection.get("spec", "none"))}" data-ml-cards="{esc(packet.get("cards", 1))}"'
                f' data-ml-hardware="Intel Arc Pro B70" data-ml-measured="{esc(raw_value)}"'
                + (f' data-ml-strategy="{esc(projection.get("strategy"))}"' if projection.get("strategy") else "")
            )
            headroom = '<span class="opt-grade" data-family-headroom-value title="Projected optimization headroom is loading; this is not model quality or packet evidence.">OPT …</span>'
        cards.append(
            f'''<a class="packet-card" href="{esc(href)}"{attrs}>
  <div class="packet-top"><span>{esc(packet.get('revision'))}</span><span class="packet-badges"><b>{esc(packet.get('evidence_level'))}</b>{headroom}</span></div>
  <h3>{esc(packet.get('label'))}</h3>
  <p><strong>{esc(value)} {esc(unit)}</strong>{" measured headline" if value != "—" else " evidence packet"} · {esc(packet.get('status'))}</p>
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
    boundary = transfer.get("status") or "Measurements remain revision- and artifact-specific"
    popularity_value = popularity.get("downloads")
    if popularity_value is None and popularity.get("snapshots"):
        popularity_value = f'{len(popularity["snapshots"])} repo snapshots'
    if popularity_value is None:
        popularity_value = "Pending"
    if architecture_summary:
        boundary = f"{architecture_summary}. {boundary}"
    coverage_section = ""
    if coverage_views:
        coverage_section = f'''
  <div class="section-head"><div><h2>Combination coverage</h2><p>A compact decision map replaces near-duplicate result rows. Closed and quarantined cells are coverage, not blanks.</p></div></div>
  {coverage}
'''
    closures_section = ""
    if closure_items:
        closures_section = f'''
  <div class="section-head"><div><h2>Scoped closures</h2><p>Impossible and rejected combinations apply only to the exact selectors shown.</p></div></div>
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
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<link rel="stylesheet" href="../learn/learn.css">
<link rel="preconnect" href="https://mlbottleneck.com">
<style>
  .family-main {{ max-width: 1120px; }}
  .lineage {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }}
  .lineage span {{ padding:5px 8px; border:1px solid rgba(255,255,255,.7); font:700 10px var(--mono); text-transform:uppercase; }}
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
  .metric-switch button[aria-pressed="true"], .coverage-switch button[aria-pressed="true"] {{ background:var(--ink); color:var(--paper); }}
  .family-chart {{ min-height:210px; }}
  .gap-line {{ height:0!important; border-top:2px dashed var(--muted); background:transparent!important; }}
  .proof-links {{ display:block; margin-top:5px; }}
  .proof-links a {{ border-bottom:1px solid currentColor; }}
  .coverage-panel > p {{ margin:8px 0 0; color:var(--muted); font:11px var(--mono); }}
  .coverage-table td {{ min-width:130px; white-space:normal; }}
  .coverage-cell > a {{ display:block; color:inherit; text-decoration:none; }}
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
  <p class="eyebrow">Model family coverage · measured cells, honest gaps</p>
  <h1>{esc(family.get('display_name'))}</h1>
  <p>{esc(family.get('summary'))}</p>
  <div class="lineage">{lineage}</div>
</div></header>
<main id="main"><div class="wrap family-main">
  <div class="signals" aria-label="Family signals">
    <div class="signal"><span>B70 fit</span><b>{esc(fit.get('band') or 'Pending')}</b><small>{esc(fit.get('scope') or 'local deployment fit')}, reviewed {esc(fit.get('reviewed_at') or family.get('updated_at'))}</small></div>
    <div class="signal"><span>Quality evidence</span><b>{esc(str(quality.get('band') or 'Pending').replace('-', ' '))}</b><small>{esc(quality.get('scope') or 'No family-wide quality score is inferred from speed evidence.')}</small></div>
    <div class="signal"><span>Interest snapshot</span><b>{esc(popularity_value)}</b><small>{esc(popularity.get('captured_at') or popularity.get('reason') or 'not scored')}</small></div>
    <div class="signal"><span>Evidence slices</span><b>{measured_count}</b><small>run arms and measured series; every point links to proof</small></div>
    <div class="signal"><span>Stored estimates</span><b>{estimate_count}</b><small>versioned gap estimates only; live OPT grades stay separate</small></div>
  </div>
  <p class="scope-note"><strong>Transfer boundary:</strong> {esc(boundary)}. Measurements, artifact hashes, outputs, quality decisions, and speed stay pinned to their exact recorded identity.</p>

  <div class="section-head"><div><h2>Measured slices</h2><p>Metric switches change the question without changing the configuration. Whiskers retain every captured repeat; no missing point is interpolated.</p></div><a class="inline" href="{source}">family data</a></div>
  <div class="views-grid">{views}</div>

{coverage_section}{closures_section}

  <div class="section-head"><div><h2>Packets and recipes</h2><p>Quantizations are deployment variants inside this family. Lower-maturity packets stay visible with their evidence boundary instead of disappearing.</p></div></div>
  <div class="packet-grid">{packets}</div>

  <div class="related"><h2>Keep going</h2><div class="related-grid"><a href="../guides.html"><b>Guide library</b><span>Filter runnable packets</span></a><a href="../learn/models.html"><b>Choose a model</b><span>Quality and deployment trade-offs</span></a><a href="../learn/hardware.html"><b>Hardware</b><span>Cards, memory, and topology</span></a><a href="{source}"><b>Family data</b><span>Exact normalized coverage source</span></a></div></div>
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
  document.querySelectorAll('[data-coverage-button]').forEach(button => button.addEventListener('click', () => {{
    const panel = button.dataset.coverageButton;
    document.querySelectorAll('[data-coverage-button]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    document.querySelectorAll('[data-coverage-panel]').forEach(item => item.hidden = item.dataset.coveragePanel !== panel);
  }}));
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
    for entry in catalog.get("families") or []:
        source = ROOT / entry.get("manifest", "")
        try:
            family = load_json(source)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(str(error))
            continue
        errors.extend(validate_family(family, source))
        family_id = family.get("id")
        if family_id != entry.get("id"):
            errors.append(
                f"{source.relative_to(ROOT)}: family id {family_id} does not match catalog id {entry.get('id')}"
            )
        if family_id in family_ids:
            errors.append(f"families/catalog.json: duplicate family id {family_id}")
        family_ids.add(family_id)
        for packet in family.get("packets") or []:
            packet_owners.setdefault(packet.get("id"), []).append(family_id)
        output = OUT_DIR / f"{family['id']}.html"
        rendered = family_page(family)
        expected.append((output, rendered))
    try:
        package_catalog = load_json(PACKAGE_CATALOG)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    else:
        published_ids = {package.get("id") for package in package_catalog.get("packages") or []}
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
        print(f"family pages current: {len(expected)}")
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
