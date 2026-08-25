#!/usr/bin/env python3
"""Validate the frozen Qwen3.6 Q4_K_M MTP1 parent sentinel artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


CAMPAIGN_ID = "qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r1"
RECEIPT_SCHEMA = "openai-token-depth-benchmark-v1"
TERMINAL_SCHEMA = "neural.download.qwen36-llama-mtp1-parent-sentinel-terminal.v1"
ACCEPTANCE_RE = re.compile(
    r"draft acceptance\s*=\s*([0-9.]+)\s*\(\s*(\d+) accepted\s*/\s*(\d+) generated\)"
)


class GateError(RuntimeError):
    """Raised when a frozen sentinel gate fails."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError(f"{path} must contain a JSON object")
    return value


def require(condition: bool, label: str, checks: dict[str, bool]) -> None:
    checks[label] = bool(condition)


def cached_counts(quality: dict[str, Any]) -> list[int | None]:
    rows: list[dict[str, Any]] = []
    rows.extend(
        item for item in quality.get("exact_cases", []) if isinstance(item, dict)
    )
    repeat = quality.get("repeat_case")
    if isinstance(repeat, dict):
        rows.extend(
            item for item in repeat.get("runs", []) if isinstance(item, dict)
        )
    long_context = quality.get("long_context_case")
    if isinstance(long_context, dict):
        rows.append(long_context)

    result: list[int | None] = []
    for row in rows:
        usage = row.get("usage")
        details = (
            usage.get("prompt_tokens_details")
            if isinstance(usage, dict)
            and isinstance(usage.get("prompt_tokens_details"), dict)
            else {}
        )
        value = details.get("cached_tokens")
        result.append(value if type(value) is int else None)
    return result


def acceptance_rows(server_log: Path) -> list[dict[str, Any]]:
    try:
        text = server_log.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise GateError(f"cannot read {server_log}: {exc}") from exc
    rows = []
    for match in ACCEPTANCE_RE.finditer(text):
        rows.append(
            {
                "ratio": float(match.group(1)),
                "accepted": int(match.group(2)),
                "generated": int(match.group(3)),
            }
        )
    return rows


def validate_receipt(
    value: dict[str, Any], *, model: str, fixture_sha256: str
) -> dict[str, Any]:
    identity = value.get("run_identity") or {}
    fixture = value.get("fixture") or {}
    gate = value.get("gate") or {}
    metric = value.get("metric_window") or {}
    response = value.get("response") or {}
    if not (
        value.get("schema") == RECEIPT_SCHEMA
        and value.get("status") == "passed"
        and gate.get("passed") is True
        and identity.get("model") == model
        and identity.get("depth") == 8192
        and identity.get("active_context_tokens") == 8192
        and identity.get("configured_context_capacity") == 12288
        and identity.get("case_id") == "depth-8192"
        and identity.get("max_tokens") == 128
        and identity.get("metric_events") == 100
        and identity.get("metric_intervals") == 99
        and fixture.get("fixture_sha256") == fixture_sha256
        and fixture.get("prompt_token_ids_sha256")
        == "6baa17bea14f0ecad7e4edf54a05256eafaef1d447a447569fd303371c671741"
        and metric.get("timestamped_events") == 100
        and metric.get("inter_token_intervals") == 99
        and isinstance(metric.get("conventional_99_interval_tok_s"), (int, float))
        and math.isfinite(float(metric["conventional_99_interval_tok_s"]))
        and float(metric["conventional_99_interval_tok_s"]) > 0
        and isinstance(response.get("output_token_ids_sha256"), str)
        and len(response["output_token_ids_sha256"]) == 64
    ):
        raise GateError("exact-depth receipt invariant failed")
    return {
        "serving_decode_tok_s_99_interval": float(
            metric["conventional_99_interval_tok_s"]
        ),
        "output_token_ids_sha256": response["output_token_ids_sha256"],
        "receipt_sha256": None,
    }


def validate(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    checks: dict[str, bool] = {}
    require(
        manifest.get("schema")
        == "neural.download.qwen36-llama-mtp1-parent-sentinel-prereg.v1",
        "manifest_schema",
        checks,
    )
    require(manifest.get("campaign_id") == CAMPAIGN_ID, "campaign_id", checks)
    require(manifest.get("state") == "preregistered-not-launched", "state", checks)
    require(
        manifest.get("frozen_interpretation", {}).get("speed_floor") is None,
        "no_speed_floor",
        checks,
    )
    require(
        manifest.get("frozen_interpretation", {}).get("cell_gain_on_sentinel_pass")
        == 0,
        "sentinel_does_not_fill_cells",
        checks,
    )

    model_alias = "qwen36-q4km-f16-tp1"
    fixture_sha = manifest["fixture"]["sha256"]
    control_path = root / "control-mtp0/exact-depth.json"
    candidate_path = root / "candidate-mtp1/exact-depth.json"
    quality_path = root / "candidate-mtp1/quality.json"
    control_log = root / "control-mtp0/server.log"
    candidate_log = root / "candidate-mtp1/server.log"
    required = [control_path, candidate_path, quality_path, control_log, candidate_log]
    require(all(path.is_file() for path in required), "required_artifacts", checks)
    if not checks["required_artifacts"]:
        missing = [str(path) for path in required if not path.is_file()]
        raise GateError("missing required artifacts: " + ", ".join(missing))

    control = validate_receipt(
        load_json(control_path), model=model_alias, fixture_sha256=fixture_sha
    )
    candidate = validate_receipt(
        load_json(candidate_path), model=model_alias, fixture_sha256=fixture_sha
    )
    control["receipt_sha256"] = sha256_file(control_path)
    candidate["receipt_sha256"] = sha256_file(candidate_path)
    require(True, "control_exact_depth_passed", checks)
    require(True, "candidate_exact_depth_passed", checks)
    require(
        control["output_token_ids_sha256"]
        == candidate["output_token_ids_sha256"],
        "candidate_target_output_parity",
        checks,
    )

    control_acceptance = acceptance_rows(control_log)
    candidate_acceptance = acceptance_rows(candidate_log)
    require(not control_acceptance, "control_has_no_draft_acceptance", checks)
    require(bool(candidate_acceptance), "candidate_has_draft_acceptance", checks)
    first_acceptance = candidate_acceptance[0] if candidate_acceptance else None
    require(
        first_acceptance is not None and first_acceptance["generated"] > 0,
        "candidate_exact_request_generated_drafts",
        checks,
    )
    require(
        first_acceptance is not None and first_acceptance["accepted"] > 0,
        "candidate_exact_request_accepted_drafts",
        checks,
    )

    quality = load_json(quality_path)
    counts = cached_counts(quality)
    require(quality.get("pass_all") is True, "quality_suite_passed", checks)
    require(len(counts) == 7, "quality_request_count_is_seven", checks)
    require(bool(counts) and all(value == 0 for value in counts), "quality_cache_zero", checks)
    require(
        quality.get("repeat_case", {}).get("repeats") == 2,
        "quality_repeat_count",
        checks,
    )
    require(
        quality.get("long_context_case", {}).get("pass") is True,
        "quality_8k_needle_passed",
        checks,
    )

    passed = all(checks.values())
    return {
        "schema": TERMINAL_SCHEMA,
        "campaign_id": CAMPAIGN_ID,
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "status": "passed-expand-mtp1-depth-curve" if passed else "failed-do-not-expand",
        "gate": {"passed": passed, "checks": checks},
        "measurement_class": "HTTP serving; conventional 99-interval streamed token-ID decode",
        "speed_floor": None,
        "control": control,
        "candidate": candidate,
        "candidate_vs_control_ratio": (
            candidate["serving_decode_tok_s_99_interval"]
            / control["serving_decode_tok_s_99_interval"]
        ),
        "candidate_first_exact_request_draft_counters": first_acceptance,
        "candidate_all_request_draft_counters": candidate_acceptance,
        "quality": {
            "result_sha256": sha256_file(quality_path),
            "request_count": len(counts),
            "cached_tokens": counts,
            "pass_all": quality.get("pass_all"),
        },
        "interpretation": (
            "Prepare a separate preregistered seven-depth MTP1 HTTP-serving curve. "
            "This sentinel fills no matrix cell and its rate is not a raw-engine metric."
            if passed
            else "Do not expand MTP1 from this packet; preserve the failed artifacts."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.root, args.manifest)
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2, sort_keys=True)
                stream.write("\n")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["gate"]["passed"] else 2
    except (GateError, KeyError, OSError, ValueError, ZeroDivisionError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
