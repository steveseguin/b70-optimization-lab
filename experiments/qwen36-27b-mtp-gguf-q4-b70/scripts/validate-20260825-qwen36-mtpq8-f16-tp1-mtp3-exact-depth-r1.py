#!/usr/bin/env python3
"""Validate the embedded-Q8 MTP3/F16 TP1 seven-depth serving curve."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Any


CAMPAIGN_ID = "qwen36-mtpq8-f16-tp1-mtp3-exact-depth-20260825-r1"
MANIFEST_SCHEMA = "neural.download.qwen36-llama-mtp3-exact-depth-prereg.v1"
TERMINAL_SCHEMA = "neural.download.qwen36-llama-mtp3-exact-depth-terminal.v1"
RECEIPT_SCHEMA = "openai-token-depth-benchmark-v1"
DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)


class GateError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError(f"{path} must contain a JSON object")
    return value


def quality_cached_counts(value: dict[str, Any]) -> list[int | None]:
    rows = [row for row in value.get("exact_cases", []) if isinstance(row, dict)]
    repeat = value.get("repeat_case")
    if isinstance(repeat, dict):
        rows.extend(row for row in repeat.get("runs", []) if isinstance(row, dict))
    long_context = value.get("long_context_case")
    if isinstance(long_context, dict):
        rows.append(long_context)
    counts: list[int | None] = []
    for row in rows:
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), dict) else {}
        count = details.get("cached_tokens")
        counts.append(count if type(count) is int else None)
    return counts


def validate_depth_receipt(value: dict[str, Any], *, depth: int, model: str,
                           fixture_sha: str, prompt_sha: str, capacity: int) -> dict[str, Any]:
    identity = value.get("run_identity") or {}
    fixture = value.get("fixture") or {}
    metric = value.get("metric_window") or {}
    response = value.get("response") or {}
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), dict) else {}
    output_hash = response.get("output_token_ids_sha256")
    checks = {
        "schema": value.get("schema") == RECEIPT_SCHEMA,
        "status": value.get("status") == "passed" and (value.get("gate") or {}).get("passed") is True,
        "model": identity.get("model") == model,
        "depth": identity.get("depth") == depth and identity.get("active_context_tokens") == depth,
        "capacity": identity.get("configured_context_capacity") == capacity and capacity >= depth + 128,
        "case": identity.get("case_id") == f"depth-{depth}",
        "shape": identity.get("max_tokens") == 128 and identity.get("metric_events") == 100 and identity.get("metric_intervals") == 99,
        "fixture": fixture.get("fixture_sha256") == fixture_sha and fixture.get("prompt_token_ids_sha256") == prompt_sha,
        "metric": metric.get("timestamped_events") == 100 and metric.get("inter_token_intervals") == 99 and isinstance(metric.get("conventional_99_interval_tok_s"), (int, float)) and math.isfinite(float(metric.get("conventional_99_interval_tok_s", 0))) and float(metric.get("conventional_99_interval_tok_s", 0)) > 0,
        "cache_zero": details.get("cached_tokens") == 0,
        "output_hash": isinstance(output_hash, str) and len(output_hash) == 64,
    }
    if not all(checks.values()):
        raise GateError(f"depth {depth} receipt invariant failed: {checks}")
    return {
        "depth": depth,
        "serving_decode_tok_s_99_interval": float(metric["conventional_99_interval_tok_s"]),
        "output_token_ids_sha256": output_hash,
        "cached_tokens": details["cached_tokens"],
    }


def flag_value(argv: list[str], flag: str) -> str | None:
    try:
        return argv[argv.index(flag) + 1]
    except (ValueError, IndexError):
        return None


def validate(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    checks: dict[str, bool] = {}
    selectors = manifest.get("selectors") or {}
    runtime = manifest.get("runtime") or {}
    server = manifest.get("server_contract") or {}
    fixture = manifest.get("fixture") or {}
    lifecycle = manifest.get("lifecycle") or {}
    libraries = runtime.get("effective_local_shared_libraries")
    checks["manifest_identity"] = (
        manifest.get("schema") == MANIFEST_SCHEMA
        and manifest.get("campaign_id") == CAMPAIGN_ID
        and manifest.get("state") == "preregistered-not-launched"
        and selectors.get("active_context_tokens") == list(DEPTHS)
        and selectors.get("candidate_mtp") == 3
        and selectors.get("control_mtp") == 0
        and selectors.get("graph_mode") == "off"
        and selectors.get("target_kv") == selectors.get("draft_kv") == "f16"
    )
    checks["frozen_authority"] = (
        manifest.get("frozen_interpretation", {}).get("speed_floor") is None
        and manifest.get("frozen_interpretation", {}).get("cell_gain_if_all_gates_pass") == 7
        and manifest.get("frozen_interpretation", {}).get("graph_claim_authorized") is False
        and manifest.get("frozen_interpretation", {}).get("site_or_family_edit_authorized_before_result_and_quality_review") is False
    )
    checks["runtime_closure_declared"] = isinstance(libraries, list) and len(libraries) == 8
    required = [root / "identity.json", root / "control-mtp0/server.log",
                root / "candidate-mtp3/server.log", root / "control-mtp0/cleanup.json",
                root / "candidate-mtp3/cleanup.json", root / "candidate-mtp3/quality.json"]
    for arm in ("control-mtp0", "candidate-mtp3"):
        required.append(root / arm / "models.json")
        for depth in DEPTHS:
            required.append(root / arm / f"depth-{depth}" / "exact-depth.json")
    for depth in DEPTHS:
        required.append(root / "candidate-mtp3" / f"depth-{depth}" / "draft-counters.json")
    if not all(path.is_file() for path in required):
        raise GateError("missing required artifacts: " + ", ".join(str(p) for p in required if not p.is_file()))

    identity = load_json(root / "identity.json")
    checks["primary_identity"] = (
        identity.get("campaign_id") == CAMPAIGN_ID
        and identity.get("git_head") == identity.get("origin_main")
        and identity.get("model", {}).get("sha256") == manifest["model"]["sha256"]
        and identity.get("runtime", {}).get("binary_sha256") == runtime.get("binary_sha256")
        and identity.get("runtime", {}).get("manifest_sha256") == runtime.get("manifest_sha256")
        and identity.get("fixture_sha256") == fixture.get("sha256")
    )
    captured_dsos = identity.get("runtime", {}).get("local_dsos")
    checks["runtime_dso_closure"] = isinstance(libraries, list) and captured_dsos == libraries
    argv = identity.get("server_argv") or {}
    control_argv = argv.get("control-mtp0") if isinstance(argv.get("control-mtp0"), list) else []
    candidate_argv = argv.get("candidate-mtp3") if isinstance(argv.get("candidate-mtp3"), list) else []
    checks["server_contract"] = (
        flag_value(control_argv, "--spec-type") == "none"
        and flag_value(candidate_argv, "--spec-type") == "draft-mtp"
        and flag_value(candidate_argv, "--spec-draft-n-max") == "3"
        and flag_value(candidate_argv, "--spec-draft-n-min") == "0"
        and flag_value(candidate_argv, "--spec-draft-type-k") == "f16"
        and flag_value(candidate_argv, "--spec-draft-type-v") == "f16"
        and flag_value(candidate_argv, "-ctk") == flag_value(candidate_argv, "-ctv") == "f16"
        and flag_value(candidate_argv, "-c") == str(server["context_capacity"])
        and "--no-context-shift" in candidate_argv
        and "--ctx-checkpoints" in candidate_argv
        and flag_value(candidate_argv, "--ctx-checkpoints") == "0"
    )
    env = identity.get("runtime_environment") or {}
    checks["graph_off"] = env.get("GGML_SYCL_ENABLE_GRAPH") == "0" and env.get("GGML_SYCL_GRAPH_CACHE_SIZE") == "0"

    for arm in ("control-mtp0", "candidate-mtp3"):
        models = load_json(root / arm / "models.json").get("data")
        checks[f"{arm}_alias"] = isinstance(models, list) and any(isinstance(row, dict) and row.get("id") == server["model_alias"] for row in models)
        cleanup = load_json(root / arm / "cleanup.json")
        checks[f"{arm}_cleanup"] = cleanup == {"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}

    controls: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    counter_rows: list[dict[str, Any]] = []
    prompt_hashes = fixture["prompt_token_ids_sha256"]
    for index, depth in enumerate(DEPTHS):
        control_path = root / "control-mtp0" / f"depth-{depth}" / "exact-depth.json"
        candidate_path = root / "candidate-mtp3" / f"depth-{depth}" / "exact-depth.json"
        control = validate_depth_receipt(load_json(control_path), depth=depth,
                                         model=server["model_alias"], fixture_sha=fixture["sha256"],
                                         prompt_sha=prompt_hashes[index], capacity=server["context_capacity"])
        candidate = validate_depth_receipt(load_json(candidate_path), depth=depth,
                                           model=server["model_alias"], fixture_sha=fixture["sha256"],
                                           prompt_sha=prompt_hashes[index], capacity=server["context_capacity"])
        control["receipt_sha256"] = sha256_file(control_path)
        candidate["receipt_sha256"] = sha256_file(candidate_path)
        controls.append(control); candidates.append(candidate)
        checks[f"depth_{depth}_target_output_parity"] = control["output_token_ids_sha256"] == candidate["output_token_ids_sha256"]
        counter = load_json(root / "candidate-mtp3" / f"depth-{depth}" / "draft-counters.json")
        new_rows = counter.get("new_rows")
        row = new_rows[0] if isinstance(new_rows, list) and len(new_rows) == 1 and isinstance(new_rows[0], dict) else {}
        generated, accepted, ratio = row.get("generated"), row.get("accepted"), row.get("ratio")
        conserved = (
            counter.get("depth") == depth and counter.get("rows_after") == counter.get("rows_before", -2) + 1
            and type(generated) is int and type(accepted) is int and isinstance(ratio, (int, float))
            and generated > 0 and 0 < accepted <= generated
            and math.isclose(float(ratio), accepted / generated, rel_tol=0, abs_tol=5.1e-5)
        )
        checks[f"depth_{depth}_draft_engaged_conserved"] = conserved
        counter_rows.append({"depth": depth, "generated": generated, "accepted": accepted, "ratio": ratio, "conserved": conserved})

    quality_path = root / "candidate-mtp3/quality.json"
    quality = load_json(quality_path)
    counts = quality_cached_counts(quality)
    checks["quality_passed"] = quality.get("pass_all") is True
    checks["quality_request_count"] = len(counts) == 7
    checks["quality_cache_zero"] = len(counts) == 7 and all(count == 0 for count in counts)
    checks["quality_repeat_count"] = quality.get("repeat_case", {}).get("repeats") == 2
    checks["quality_29400_needle"] = (
        quality.get("long_context_case", {}).get("requested_context_tokens") == 29400
        and quality.get("long_context_case", {}).get("pass") is True
    )
    passed = all(checks.values())
    return {
        "schema": TERMINAL_SCHEMA,
        "campaign_id": CAMPAIGN_ID,
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "status": "passed-seven-cells-quality-pending-review" if passed else "failed-preserve-do-not-publish",
        "gate": {"passed": passed, "checks": checks},
        "measurement_class": "HTTP serving; conventional 99-interval streamed token-ID decode",
        "speed_floor": None,
        "control_mtp0": controls,
        "candidate_mtp3": candidates,
        "candidate_draft_counters": counter_rows,
        "quality": {"result_sha256": sha256_file(quality_path), "request_count": len(counts), "cached_tokens": counts, "pass_all": quality.get("pass_all")},
        "authority": {"matrix_cells_if_reviewed": 7 if passed else 0, "site_publication": False, "graph_claim": False, "headline_or_protected_replacement": False, "localmaxxing_submission": False},
        "interpretation": "Preserve and independently review all seven scoped MTP3/F16/graph-off cells." if passed else "Preserve this bounded failure; no cell or speed is authorized.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.root, args.manifest)
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2, sort_keys=True); stream.write("\n")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["gate"]["passed"] else 2
    except (GateError, KeyError, OSError, ValueError, ZeroDivisionError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
