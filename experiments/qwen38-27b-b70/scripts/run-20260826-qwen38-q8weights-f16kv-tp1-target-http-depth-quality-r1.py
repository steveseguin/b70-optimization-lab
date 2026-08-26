#!/usr/bin/env python3
"""Create-only Q8_0-weight/F16-KV sibling of the passed Q5_K_S HTTP curve."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
OVERLAY = LANE / "data/2026-08-26-qwen38-q8weights-f16kv-tp1-target-http-depth-quality-r1-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260826-qwen38-q5ks-f16kv-tp1-target-http-depth-quality-r1.py"
VALIDATOR = LANE / "scripts/validate-20260826-qwen38-q8weights-f16kv-tp1-target-http-depth-quality-r1.py"
CAMPAIGN_ID = "qwen38-q8weights-f16kv-tp1-target-http-depth-quality-20260826-r1"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)
ARM = "target-mtp0"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = load_module(BASE_RUNNER, "qwen38_q5ks_f16_base_for_q8weights")
GateError = BASE.GateError
CORE = BASE.CORE
EXPECTED_CLEANUP = BASE.EXPECTED_CLEANUP
BASE_LOAD = BASE.load_manifest
BASE_EXECUTION = BASE.Execution
BASE_VALUE = copy.deepcopy(BASE_LOAD())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO / path


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"JSON root must be object: {path}")
    return value


def load_overlay() -> dict[str, Any]:
    value = load_json(OVERLAY)
    selectors = value.get("selectors") or {}
    execution = value.get("execution_contract") or {}
    lifecycle = value.get("lifecycle") or {}
    frozen = value.get("frozen_interpretation") or {}
    if not (
        value.get("schema") == "neural.download.qwen38-q8weights-f16kv-target-http-depth-quality-sibling-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors == {
            "revision": "qwen3.8-27b-current-weights",
            "target_quantization": "Q8_0",
            "tp": 1,
            "mtp": 0,
            "active_context_tokens": list(DEPTHS),
            "target_kv": "f16",
            "graph_mode": "off",
            "fit": "off",
            "transport": "HTTP /v1/completions",
        }
        and execution.get("arm") == ARM
        and execution.get("fresh_server_lifetimes") == 1
        and execution.get("depth_order") == list(DEPTHS)
        and execution.get("completion_tokens_per_depth") == 128
        and execution.get("quality_after_all_depths") is True
        and execution.get("require_q5_f16_base_passed") is True
        and execution.get("require_existing_q8_raw_and_quality_evidence") is True
        and execution.get("require_exact_model_sha256_before_any_operational_action") is True
        and lifecycle == {
            "output_root": f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}",
            "exact_ack": ACK,
            "default_is_inert": True,
            "requires_clean_pushed_main": True,
            "create_only": True,
        }
        and frozen.get("speed_floor") is None
        and frozen.get("target_only_q8weights_f16_serving_curve_cells_if_all_gates_pass") == 7
        and all(frozen.get(key) == 0 for key in (
            "other_weight_quantization_cells_authorized",
            "q8_kv_cells_authorized",
            "speculative_cells_authorized",
            "tp2_or_tp4_cells_authorized",
            "graph_cells_authorized",
            "prefill_cells_authorized",
        ))
        and frozen.get("headline_or_protected_replacement_authorized") is False
        and frozen.get("protected_decode_values")
        == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]
    ):
        raise GateError("Q8_0-weight/F16 sibling overlay invariant failed")
    return value


def verify_base(value: dict[str, Any]) -> None:
    base = value["base"]
    for key in ("manifest", "runner", "validator", "result", "terminal", "identity"):
        path = resolve(base[key])
        if not path.is_file() or sha256_file(path) != base[f"{key}_sha256"]:
            raise GateError(f"sealed Q5/F16 base changed: {path}")
    terminal = load_json(resolve(base["terminal"]))
    result = load_json(resolve(base["result"]))
    identity = load_json(resolve(base["identity"]))
    authority = terminal.get("authority") or {}
    runtime = identity.get("runtime") or {}
    if not (
        terminal.get("status") == base["required_status"]
        and result.get("status") == "passed"
        and result.get("classification") == "grade-c-f16kv-exact-depth-serving-curve-with-full-qwen38-quality-battery"
        and authority.get("target_only_f16_serving_curve_cells") == 7
        and identity.get("campaign_id") == terminal.get("campaign_id")
        and all(runtime.get(key) == BASE_VALUE["runtime"][key]
                for key in ("binary", "binary_sha256", "source_commit", "reported_version"))
        and runtime.get("local_dsos") == BASE_VALUE["runtime"]["effective_local_shared_libraries"]
    ):
        raise GateError("passed Q5/F16 runtime/workload base invariant failed")

    manifest_path = resolve(value["model_manifest"]["path"])
    if not manifest_path.is_file() or sha256_file(manifest_path) != value["model_manifest"]["sha256"]:
        raise GateError("sealed Q8_0 model manifest changed")
    manifest = load_json(manifest_path)
    files = manifest.get("lfs_files") or []
    if not (
        manifest.get("repository") == value["model"]["repository"]
        and manifest.get("revision") == value["model"]["revision"]
        and len(files) == 1
        and files[0].get("path") == Path(value["model"]["path"]).name
        and files[0].get("bytes") == value["model"]["size_bytes"]
        and files[0].get("sha256") == value["model"]["sha256"]
    ):
        raise GateError("Q8_0 model identity manifest invariant failed")

    raw_info = value["existing_raw_evidence"]
    raw_path = resolve(raw_info["path"])
    if not raw_path.is_file() or sha256_file(raw_path) != raw_info["sha256"]:
        raise GateError("sealed Q8_0/F16 raw evidence changed")
    raw = load_json(raw_path)
    rows = [row for row in raw.get("rows", []) if isinstance(row, dict) and row.get("n_gen") == 128]
    if not (
        raw.get("classification") == raw_info["classification"]
        and [row.get("n_depth") for row in rows] == list(DEPTHS)
        and len(rows) == 7
        and all(row.get("type_k") == "f16" and row.get("type_v") == "f16" for row in rows)
        and all(row.get("build_commit") == raw_info["build_commit_short"] for row in rows)
        and all(Path(str(row.get("model_filename"))).name == Path(value["model"]["path"]).name for row in rows)
    ):
        raise GateError("Q8_0/F16 raw curve identity failed")

    quality_info = value["existing_quality_evidence"]
    for path_key in ("preregistration", "qualification"):
        path = resolve(quality_info[path_key])
        if not path.is_file() or sha256_file(path) != quality_info[f"{path_key}_sha256"]:
            raise GateError(f"sealed Q8_0 quality evidence changed: {path}")
    quality_prereg = load_json(resolve(quality_info["preregistration"]))
    qualification = load_json(resolve(quality_info["qualification"]))
    checks = qualification.get("checks") or {}
    if not (
        quality_prereg.get("model", {}).get("sha256") == value["model"]["sha256"]
        and quality_prereg.get("service", {}).get("kv") == "F16 K and V"
        and quality_prereg.get("service", {}).get("mtp") == 0
        and quality_prereg.get("service", {}).get("graph") == "off"
        and qualification.get("classification") == quality_info["classification"]
        and all(checks.get(key) is True for key in (
            "pass_all", "exact_cases_7_of_7", "repeat_hash_8_of_8",
            "long_context_needle", "cached_tokens_explicit_zero",
        ))
    ):
        raise GateError("Q8_0/F16 prior quality identity failed")


def load_manifest() -> dict[str, Any]:
    overlay = load_overlay()
    verify_base(overlay)
    value = copy.deepcopy(BASE_VALUE)
    value.update({
        "schema": "neural.download.qwen38-q8weights-f16kv-target-http-depth-quality-prereg.v1",
        "campaign_id": CAMPAIGN_ID,
        "state": "preregistered-not-launched",
        "purpose": overlay["purpose"],
        "model": copy.deepcopy(overlay["model"]),
        "model_manifest": copy.deepcopy(overlay["model_manifest"]),
        "parent": copy.deepcopy(overlay["base"]),
        "existing_raw_evidence": copy.deepcopy(overlay["existing_raw_evidence"]),
        "existing_quality_evidence": copy.deepcopy(overlay["existing_quality_evidence"]),
        "selectors": copy.deepcopy(overlay["selectors"]),
        "execution_contract": copy.deepcopy(overlay["execution_contract"]),
        "storage_state_at_preparation": copy.deepcopy(overlay["storage_state_at_preparation"]),
        "frozen_interpretation": copy.deepcopy(overlay["frozen_interpretation"]),
    })
    value["server_contract"].update(overlay["server_contract"])
    value["lifecycle"].update(overlay["lifecycle"])
    validate_manifest(value)
    return value


def validate_manifest(value: dict[str, Any]) -> None:
    overlay = load_overlay()
    if not (
        value.get("campaign_id") == CAMPAIGN_ID
        and value.get("model") == overlay["model"]
        and value.get("runtime") == BASE_VALUE["runtime"]
        and value.get("fixture") == BASE_VALUE["fixture"]
        and value.get("clients") == BASE_VALUE["clients"]
        and value.get("selectors") == overlay["selectors"]
        and value.get("execution_contract") == overlay["execution_contract"]
        and value.get("frozen_interpretation") == overlay["frozen_interpretation"]
        and value.get("server_contract", {}).get("cache_type_k") == "f16"
        and value.get("server_contract", {}).get("cache_type_v") == "f16"
        and value.get("server_contract", {}).get("spec_type") == "none"
    ):
        raise GateError("effective Q8_0-weight/F16 manifest invariant failed")


def merged_manifest(value: dict[str, Any]) -> dict[str, Any]:
    return BASE.merged_manifest(value)


class Execution(BASE_EXECUTION):
    pass


def model_presence(value: dict[str, Any]) -> tuple[bool, str]:
    path = Path(value["model"]["path"])
    if not path.is_file():
        return False, "missing"
    if path.is_symlink():
        return False, "symlink-not-authorized"
    if path.stat().st_size != value["model"]["size_bytes"]:
        return False, "size-mismatch"
    return True, "present-exact-size-full-hash-pending-execute"


def require_model_before_operational_action(value: dict[str, Any]) -> None:
    present, disposition = model_presence(value)
    if not present:
        raise GateError(f"Q8_0 model preflight failed before operational action: {disposition}")
    path = Path(value["model"]["path"])
    if sha256_file(path) != value["model"]["sha256"]:
        raise GateError("Q8_0 model preflight failed before operational action: SHA-256 mismatch")


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(value)
    verify_base(load_overlay())
    pristine = load_module(BASE_RUNNER, "qwen38_q5ks_f16_pristine_for_q8weights_static")
    pristine.static_check(pristine.load_manifest())
    argv = Execution(merged_manifest(value)).server_argv()
    if not (
        argv[argv.index("-m") + 1] == value["model"]["path"]
        and argv[argv.index("--spec-type") + 1] == "none"
        and "--spec-draft-model" not in argv
        and argv[argv.index("-ctk") + 1] == "f16"
        and argv[argv.index("-ctv") + 1] == "f16"
        and argv[argv.index("-fit") + 1] == "off"
    ):
        raise GateError("effective Q8_0-weight/F16 target-only argv invariant failed")
    present, disposition = model_presence(value)
    return {
        "schema": "neural.download.qwen38-q8weights-f16kv-target-http-depth-quality-plan.v1",
        "mode": "check",
        "default_is_inert": True,
        "gpu_actions": 0,
        "network_requests": 0,
        "output_writes": 0,
        "campaign_id": CAMPAIGN_ID,
        "exact_ack": ACK,
        "arm": ARM,
        "fresh_server_lifetimes": 1,
        "depths": list(DEPTHS),
        "quality_batteries": 1,
        "target_only_q8weights_f16_cells_if_valid": 7,
        "model_present_and_exact_size": present,
        "model_preflight": disposition,
        "launch_ready": present,
        "server_argv": argv,
    }


# Reuse the audited Q5/F16 create-only lifecycle with this sealed model sibling.
for module in (BASE, BASE.BASE):
    module.OVERLAY = OVERLAY
    module.MANIFEST = OVERLAY
    module.VALIDATOR = VALIDATOR
    module.CAMPAIGN_ID = CAMPAIGN_ID
    module.ACK = ACK
    module.DEPTHS = DEPTHS
    module.ARM = ARM
    module.Execution = Execution
    module.load_manifest = load_manifest
    module.validate_manifest = validate_manifest
    module.static_check = static_check


def main() -> int:
    # Exact-ack execution must prove the large artifact before the inherited
    # lifecycle can acquire locks, inspect a render node, or create a run root.
    if "--execute" in sys.argv and "--ack" in sys.argv:
        index = sys.argv.index("--ack")
        if index + 1 < len(sys.argv) and sys.argv[index + 1] == ACK:
            try:
                require_model_before_operational_action(load_manifest())
            except (GateError, OSError, ValueError, json.JSONDecodeError) as exc:
                print(f"{Path(sys.argv[0]).name}: error: {exc}", file=sys.stderr)
                return 2
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
