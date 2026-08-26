#!/usr/bin/env python3
"""Validate embedded-Q8/Q8-KV exact-8K MTP0-4 route sentinel artifacts."""

from __future__ import annotations

import argparse, datetime as dt, importlib.util, json, math, sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-r1.py"
R3_VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3.py"
CAMPAIGN_ID = "qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-20260825-r1"; DEPTH = 8192; ROUTES = (0, 1, 2, 3, 4)
ARMS = {0: "control-mtp0", 1: "candidate-mtp1", 2: "candidate-mtp2", 3: "candidate-mtp3", 4: "candidate-mtp4"}
EXPECTED_CLEANUP = {"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}


class GateError(RuntimeError): pass


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise GateError(str(path))
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


RUNNER = load(RUNNER_PATH, "qwen36_q8kv_route_runner_for_validator")
R3V = load(R3_VALIDATOR_PATH, "qwen36_mtp3_r3_validator_for_q8kv_route")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise GateError(str(path))
    return value


def flag_value(argv: list[str], flag: str) -> str | None:
    try: return argv[argv.index(flag) + 1]
    except (ValueError, IndexError): return None


def validate_counter(value: dict[str, Any]) -> dict[str, Any]:
    rows = value.get("new_rows"); row = rows[0] if isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict) else {}
    generated, accepted, ratio = row.get("generated"), row.get("accepted"), row.get("ratio")
    passed = value.get("depth") == DEPTH and value.get("rows_after") == value.get("rows_before", -2) + 1 and type(generated) is int and type(accepted) is int and isinstance(ratio, (int, float)) and generated > 0 and 0 < accepted <= generated and math.isclose(float(ratio), accepted / generated, rel_tol=0, abs_tol=5.1e-5)
    return {"passed": passed, "generated": generated, "accepted": accepted, "ratio": ratio}


def validate(root: Path, manifest_path: Path) -> dict[str, Any]:
    overlay = load_json(manifest_path); RUNNER.validate_overlay(overlay); RUNNER.verify_parents(overlay); manifest = RUNNER.merged_manifest(overlay); identity = load_json(root / "identity.json")
    checks = {
        "manifest_identity": manifest["campaign_id"] == CAMPAIGN_ID and manifest["selectors"]["target_kv"] == manifest["selectors"]["draft_kv"] == "q8_0",
        "primary_identity": identity.get("campaign_id") == CAMPAIGN_ID and identity.get("git_head") == identity.get("origin_main") and identity.get("model", {}).get("sha256") == manifest["model"]["sha256"] and identity.get("runtime", {}).get("binary_sha256") == manifest["runtime"]["binary_sha256"] and identity.get("fixture_sha256") == manifest["fixture"]["sha256"],
        "parent_identity": identity.get("parent_hashes") == {"f16_terminal": overlay["parents"]["successful_f16_expansion"]["terminal_sha256"], "q8kv_target_result": overlay["parents"]["q8kv_target_only"]["result_sha256"]},
        "dso_closure": identity.get("runtime", {}).get("local_dsos") == manifest["runtime"]["effective_local_shared_libraries"],
        "graph_off": identity.get("runtime_environment", {}).get("GGML_SYCL_ENABLE_GRAPH") == "0" and identity.get("runtime_environment", {}).get("GGML_SYCL_GRAPH_CACHE_SIZE") == "0",
        "frozen_authority": manifest["frozen_interpretation"]["site_publication_authorized"] is False and manifest["frozen_interpretation"]["headline_or_protected_replacement_authorized"] is False,
    }
    argv_by_arm = identity.get("server_argv") if isinstance(identity.get("server_argv"), dict) else {}
    for mtp in ROUTES:
        argv = argv_by_arm.get(ARMS[mtp]) if isinstance(argv_by_arm.get(ARMS[mtp]), list) else []
        common = flag_value(argv, "-ctk") == flag_value(argv, "-ctv") == "q8_0" and flag_value(argv, "--alias") == manifest["server_contract"]["model_alias"]
        route = flag_value(argv, "--spec-type") == "none" if mtp == 0 else flag_value(argv, "--spec-type") == "draft-mtp" and flag_value(argv, "--spec-draft-n-max") == str(mtp) and flag_value(argv, "--spec-draft-type-k") == flag_value(argv, "--spec-draft-type-v") == "q8_0"
        checks[f"{ARMS[mtp]}_argv"] = common and route
    summaries = []; control_hash = None; all_cleanup = True
    for mtp in ROUTES:
        arm = ARMS[mtp]; arm_root = root / arm
        for path in (arm_root / "server.log", arm_root / "cleanup.json", arm_root / "arm-result.json"):
            if not path.is_file(): raise GateError(f"missing {path}")
        cleanup = load_json(arm_root / "cleanup.json"); result = load_json(arm_root / "arm-result.json"); clean = cleanup == EXPECTED_CLEANUP and result.get("cleanup") == EXPECTED_CLEANUP; all_cleanup = all_cleanup and clean
        completed = result.get("status") == "completed-awaiting-validation" and result.get("error") is None
        models_path = arm_root / "models.json"; models = load_json(models_path).get("data") if models_path.is_file() else None; alias = isinstance(models, list) and any(isinstance(r, dict) and r.get("id") == manifest["server_contract"]["model_alias"] for r in models)
        receipt_path = arm_root / "depth-8192/exact-depth.json"
        try:
            receipt = R3V.validate_depth_receipt(load_json(receipt_path), depth=DEPTH, model=manifest["server_contract"]["model_alias"], fixture_sha=manifest["fixture"]["sha256"], prompt_sha=manifest["fixture"]["prompt_token_ids_sha256"][3], capacity=manifest["server_contract"]["context_capacity"]) if completed and receipt_path.is_file() else {}
            exact = receipt.get("output_token_ids_sha256") == manifest["sealed_8k_target_output_sha256"]
        except Exception: receipt = {}; exact = False
        if mtp == 0: control_hash = receipt.get("output_token_ids_sha256") if exact else None; parity = exact; counter = None; draft = True
        else:
            parity = exact and control_hash is not None and receipt.get("output_token_ids_sha256") == control_hash
            cp = arm_root / "depth-8192/draft-counters.json"; counter = validate_counter(load_json(cp)) if completed and cp.is_file() else {"passed": False, "generated": None, "accepted": None, "ratio": None}; draft = counter["passed"]
        passed = completed and clean and alias and exact and parity and draft
        summaries.append({"arm": arm, "mtp": mtp, "passed": passed, "status": "passed-route-gates" if passed else "failed-route-local-preserve", "error": result.get("error"), "cleanup_passed": clean, "target_output_parity": parity, "receipt": receipt, "draft_counters": counter, "receipt_sha256": RUNNER.F16.ROUTE_R2.sha256_file(receipt_path) if receipt_path.is_file() else None})
    by = {r["mtp"]: r for r in summaries}; checks["all_arm_cleanup"] = all_cleanup; checks["mtp0_control"] = by[0]["passed"]; screen = all(checks.values()); eligible = [m for m in (1, 2, 3, 4) if screen and by[m]["passed"]]
    return {"schema": "neural.download.qwen36-llama-mtp-q8kv-route-8k-terminal.v1", "campaign_id": CAMPAIGN_ID, "created_at_utc": dt.datetime.now(dt.UTC).isoformat(), "status": "completed-valid-q8kv-route-screen-pending-review" if screen else "failed-invalid-control-frame-do-not-expand", "screen_gate": {"passed": screen, "checks": checks}, "arms": summaries, "authority": {"routes_eligible_for_separately_preregistered_q8kv_curve": eligible, "curve_depths": [0, 2048, 4096, 8192, 16384, 24576, 32768] if eligible else [], "site_publication": False, "graph_claim": False, "headline_or_protected_replacement": False, "localmaxxing_submission": False}, "interpretation": "Only listed routes may receive separate q8-KV curves; preserve all failures and all F16/protected values." if screen else "Control/shared frame failed; no route may expand."}


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--root", required=True, type=Path); p.add_argument("--manifest", required=True, type=Path); p.add_argument("--output", type=Path); a = p.parse_args()
    try:
        result = validate(a.root, a.manifest)
        if a.output:
            with a.output.open("x", encoding="utf-8") as s: json.dump(result, s, indent=2, sort_keys=True); s.write("\n")
        print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["screen_gate"]["passed"] else 2
    except (GateError, KeyError, OSError, ValueError, json.JSONDecodeError) as exc: p.error(str(exc))
    return 2


if __name__ == "__main__": raise SystemExit(main())
