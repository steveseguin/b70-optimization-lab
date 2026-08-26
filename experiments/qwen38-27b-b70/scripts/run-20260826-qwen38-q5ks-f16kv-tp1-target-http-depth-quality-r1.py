#!/usr/bin/env python3
"""Create-only F16-KV sibling of the passed Q5_K_S target HTTP curve."""

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
OVERLAY = LANE / "data/2026-08-26-qwen38-q5ks-f16kv-tp1-target-http-depth-quality-r1-prereg.json"
BASE_RUNNER_PATH = LANE / "scripts/run-20260825-qwen38-q5ks-q8kv-tp1-target-http-depth-quality-r1.py"
VALIDATOR = LANE / "scripts/validate-20260826-qwen38-q5ks-f16kv-tp1-target-http-depth-quality-r1.py"
CAMPAIGN_ID = "qwen38-q5ks-f16kv-tp1-target-http-depth-quality-20260826-r1"
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


BASE = load_module(BASE_RUNNER_PATH, "qwen38_q5ks_q8kv_target_depth_base_for_f16")
GateError = BASE.GateError
CORE = BASE.CORE
EXPECTED_CLEANUP = BASE.EXPECTED_CLEANUP
BASE_LOAD_MANIFEST = BASE.load_manifest
SEALED_BASE_VALUE = copy.deepcopy(BASE_LOAD_MANIFEST())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"JSON root must be an object: {path}")
    return value


def referenced_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO / path


def load_overlay() -> dict[str, Any]:
    value = load_json(OVERLAY)
    selectors = value.get("selectors") or {}
    execution = value.get("execution_contract") or {}
    lifecycle = value.get("lifecycle") or {}
    frozen = value.get("frozen_interpretation") or {}
    if not (
        value.get("schema") == "neural.download.qwen38-q5ks-f16kv-target-http-depth-quality-sibling-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors == {
            "revision": "qwen3.8-27b-current-weights", "target_quantization": "UD-Q5_K_S",
            "tp": 1, "mtp": 0, "active_context_tokens": list(DEPTHS), "target_kv": "f16",
            "graph_mode": "off", "fit": "off", "transport": "HTTP /v1/completions",
        }
        and execution.get("arm") == ARM
        and execution.get("fresh_server_lifetimes") == 1
        and execution.get("depth_order") == list(DEPTHS)
        and execution.get("quality_after_all_depths") is True
        and execution.get("require_q8_sibling_base_passed") is True
        and lifecycle == {
            "output_root": f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}",
            "exact_ack": ACK, "default_is_inert": True,
            "requires_clean_pushed_main": True, "create_only": True,
        }
        and frozen.get("speed_floor") is None
        and frozen.get("target_only_f16_serving_curve_cells_if_all_gates_pass") == 7
        and all(frozen.get(key) == 0 for key in (
            "speculative_cells_authorized", "q8_kv_cells_authorized",
            "tp2_or_tp4_cells_authorized", "graph_cells_authorized", "prefill_cells_authorized",
        ))
        and frozen.get("headline_or_protected_replacement_authorized") is False
        and frozen.get("protected_decode_values")
        == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]
    ):
        raise GateError("F16-KV sibling overlay invariant failed")
    return value


def verify_base(overlay: dict[str, Any]) -> None:
    base = overlay["base"]
    for key in ("manifest", "runner", "validator", "result", "terminal", "identity"):
        path = referenced_path(base[key])
        if not path.is_file() or sha256_file(path) != base[f"{key}_sha256"]:
            raise GateError(f"sealed Q8-KV base changed: {path}")
    terminal = load_json(referenced_path(base["terminal"]))
    result = load_json(referenced_path(base["result"]))
    identity = load_json(referenced_path(base["identity"]))
    authority = terminal.get("authority") or {}
    selectors = authority.get("target_only_selectors") or {}
    if not (
        terminal.get("status") == base["required_status"]
        and result.get("classification") == "grade-c-exact-depth-serving-curve-with-full-qwen38-quality-battery"
        and ((result.get("raw_artifacts") or {}).get("sha256") or {}).get("terminal-receipt.json")
        == base["terminal_sha256"]
        and terminal.get("campaign_id") == "qwen38-q5ks-q8kv-tp1-target-http-depth-quality-20260825-r1"
        and authority.get("target_only_serving_curve_cells") == 7
        and selectors.get("target_kv") == "q8_0"
        and selectors.get("mtp") == 0 and selectors.get("tp") == 1
        and identity.get("campaign_id") == terminal.get("campaign_id")
    ):
        raise GateError("passed Q8-KV sibling base invariant failed")
    evidence = overlay["existing_f16_evidence"]
    evidence_path = referenced_path(evidence["path"])
    if not evidence_path.is_file() or sha256_file(evidence_path) != evidence["sha256"]:
        raise GateError("sealed F16 raw evidence changed")
    raw = load_json(evidence_path)
    variant = (raw.get("variants") or {}).get(evidence["variant"]) or {}
    if not (
        raw.get("depths") == list(DEPTHS)
        and "KV f16" in str(raw.get("protocol"))
        and variant.get("file") == "Qwen3.8-27B-UD-Q5_K_S.gguf"
        and variant.get("sha256_16") == "d8d62ffcf84d4265"
        and len(variant.get("decode_tg128", [])) == 7
    ):
        raise GateError("existing F16 raw curve identity failed")


def load_manifest() -> dict[str, Any]:
    overlay = load_overlay()
    verify_base(overlay)
    value = copy.deepcopy(SEALED_BASE_VALUE)
    value["schema"] = "neural.download.qwen38-q5ks-f16kv-target-http-depth-quality-prereg.v1"
    value["campaign_id"] = CAMPAIGN_ID
    value["state"] = "preregistered-not-launched"
    value["purpose"] = overlay["purpose"]
    value["parent"] = copy.deepcopy(overlay["base"])
    value["existing_f16_evidence"] = copy.deepcopy(overlay["existing_f16_evidence"])
    value["selectors"] = copy.deepcopy(overlay["selectors"])
    value["server_contract"].update(overlay["server_contract"])
    value["execution_contract"] = copy.deepcopy(overlay["execution_contract"])
    value["lifecycle"].update(overlay["lifecycle"])
    value["frozen_interpretation"] = copy.deepcopy(overlay["frozen_interpretation"])
    validate_manifest(value)
    return value


def validate_manifest(value: dict[str, Any]) -> None:
    if not (
        value.get("campaign_id") == CAMPAIGN_ID
        and value.get("selectors") == load_overlay()["selectors"]
        and value.get("server_contract", {}).get("cache_type_k") == "f16"
        and value.get("server_contract", {}).get("cache_type_v") == "f16"
        and value.get("server_contract", {}).get("spec_type") == "none"
        and value.get("execution_contract") == load_overlay()["execution_contract"]
        and value.get("lifecycle", {}).get("output_root") == f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}"
        and value.get("frozen_interpretation") == load_overlay()["frozen_interpretation"]
    ):
        raise GateError("effective F16-KV manifest invariant failed")


def merged_manifest(value: dict[str, Any]) -> dict[str, Any]:
    return BASE.merged_manifest(value)


class Execution(BASE.Execution):
    def server_argv(self) -> list[str]:
        argv = super().server_argv()
        for flag in ("-ctk", "-ctv"):
            if argv.count(flag) != 1 or argv[argv.index(flag) + 1] != "q8_0":
                raise GateError(f"sealed Q8-KV {flag} selector changed")
            argv[argv.index(flag) + 1] = "f16"
        return argv


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(value)
    verify_base(load_overlay())
    pristine = load_module(BASE_RUNNER_PATH, "qwen38_q5ks_q8kv_target_depth_pristine_static")
    pristine.static_check(pristine.load_manifest())
    argv = Execution(merged_manifest(value)).server_argv()
    if not (
        argv[argv.index("--spec-type") + 1] == "none"
        and "--spec-draft-model" not in argv
        and argv[argv.index("-ctk") + 1] == "f16"
        and argv[argv.index("-ctv") + 1] == "f16"
        and argv[argv.index("-fit") + 1] == "off"
    ):
        raise GateError("effective F16 target-only argv invariant failed")
    return {
        "schema": "neural.download.qwen38-q5ks-f16kv-target-http-depth-quality-plan.v1",
        "mode": "check", "default_is_inert": True,
        "gpu_actions": 0, "network_requests": 0, "output_writes": 0,
        "campaign_id": CAMPAIGN_ID, "exact_ack": ACK, "arm": ARM,
        "fresh_server_lifetimes": 1, "depths": list(DEPTHS),
        "quality_batteries": 1, "target_only_f16_cells_if_valid": 7,
        "server_argv": argv,
    }


# Reuse the already-audited create-only execution and lifecycle implementation.
# The imported module is private to this process; only its sealed globals change.
BASE.MANIFEST = OVERLAY
BASE.VALIDATOR = VALIDATOR
BASE.CAMPAIGN_ID = CAMPAIGN_ID
BASE.ACK = ACK
BASE.DEPTHS = DEPTHS
BASE.ARM = ARM
BASE.Execution = Execution
BASE.load_manifest = load_manifest
BASE.validate_manifest = validate_manifest
BASE.static_check = static_check


def main() -> int:
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
