#!/usr/bin/env python3
"""Create-only Q8_0-weight/Q8_0-KV sibling of the sealed F16 packet."""

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
OVERLAY = LANE / "data/2026-08-26-qwen38-q8weights-q8kv-tp1-target-http-depth-quality-r1-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260826-qwen38-q8weights-f16kv-tp1-target-http-depth-quality-r1.py"
VALIDATOR = LANE / "scripts/validate-20260826-qwen38-q8weights-q8kv-tp1-target-http-depth-quality-r1.py"
CAMPAIGN_ID = "qwen38-q8weights-q8kv-tp1-target-http-depth-quality-20260826-r1"
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


BASE = load_module(BASE_RUNNER, "qwen38_q8weights_f16_base_for_q8weights_q8kv")
GateError = BASE.GateError
EXPECTED_CLEANUP = BASE.EXPECTED_CLEANUP
BASE_EXECUTION = BASE.Execution
PARENT_OVERLAY = copy.deepcopy(BASE.load_overlay())
BASE_VALUE = copy.deepcopy(BASE.load_manifest())


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
        value.get("schema") == "neural.download.qwen38-q8weights-q8kv-target-http-depth-quality-sibling-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors == {
            "revision": "qwen3.8-27b-current-weights",
            "target_quantization": "Q8_0",
            "tp": 1,
            "mtp": 0,
            "active_context_tokens": list(DEPTHS),
            "target_kv": "q8_0",
            "graph_mode": "off",
            "fit": "off",
            "transport": "HTTP /v1/completions",
        }
        and execution.get("arm") == ARM
        and execution.get("fresh_server_lifetimes") == 1
        and execution.get("depth_order") == list(DEPTHS)
        and execution.get("completion_tokens_per_depth") == 128
        and execution.get("quality_after_all_depths") is True
        and execution.get("require_cached_tokens_zero_everywhere") is True
        and execution.get("require_q8weights_f16_packet_bound") is True
        and execution.get("require_exact_model_sha256_before_any_operational_action") is True
        and execution.get("require_cleanup") is True
        and lifecycle == {
            "output_root": f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}",
            "exact_ack": ACK,
            "default_is_inert": True,
            "requires_clean_pushed_main": True,
            "create_only": True,
        }
        and frozen.get("speed_floor") is None
        and frozen.get("target_only_q8weights_q8kv_serving_curve_cells_if_all_gates_pass") == 7
        and frozen.get("f16_kv_cells_authorized") == 0
        and frozen.get("other_weight_quantization_cells_authorized") == 0
        and frozen.get("speculative_cells_authorized") == 0
        and frozen.get("tp2_or_tp4_cells_authorized") == 0
        and frozen.get("graph_cells_authorized") == 0
        and frozen.get("prefill_cells_authorized") == 0
        and frozen.get("estimate_replacement_authorized_only_for_exact_same_selectors") is True
        and frozen.get("headline_or_protected_replacement_authorized") is False
        and frozen.get("localmaxxing_submission_authorized") is False
        and frozen.get("protected_decode_values")
        == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]
    ):
        raise GateError("Q8_0-weight/Q8_0-KV sibling overlay invariant failed")
    return value


def verify_base(value: dict[str, Any]) -> None:
    base = value["base"]
    for key in ("manifest", "runner", "validator"):
        path = resolve(base[key])
        if not path.is_file() or sha256_file(path) != base[f"{key}_sha256"]:
            raise GateError(f"sealed Q8_0-weight/F16-KV parent changed: {path}")
    parent_overlay = load_json(resolve(base["manifest"]))
    if not (
        parent_overlay == PARENT_OVERLAY
        and parent_overlay.get("state") == base["required_state"]
        and parent_overlay.get("model") == value["model"]
        and parent_overlay.get("model_manifest") == value["model_manifest"]
        and (parent_overlay.get("selectors") or {}).get("target_kv") == "f16"
        and (parent_overlay.get("selectors") or {}).get("target_quantization") == "Q8_0"
    ):
        raise GateError("sealed Q8_0-weight/F16-KV parent identity failed")

    # The parent itself binds and revalidates the passed Q5/F16 runtime,
    # complete DSO closure, fixture, clients, Q8 artifact manifest, and prior
    # Q8 evidence. Re-run that complete static provenance check here.
    BASE.verify_base(parent_overlay)


def load_manifest() -> dict[str, Any]:
    overlay = load_overlay()
    verify_base(overlay)
    value = copy.deepcopy(BASE_VALUE)
    value.update({
        "schema": "neural.download.qwen38-q8weights-q8kv-target-http-depth-quality-prereg.v1",
        "campaign_id": CAMPAIGN_ID,
        "state": "preregistered-not-launched",
        "purpose": overlay["purpose"],
        "model": copy.deepcopy(overlay["model"]),
        "model_manifest": copy.deepcopy(overlay["model_manifest"]),
        "parent": copy.deepcopy(overlay["base"]),
        "identity_delta": copy.deepcopy(overlay["identity_delta"]),
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
        and value.get("model_manifest") == overlay["model_manifest"]
        and value.get("runtime") == BASE_VALUE["runtime"]
        and value.get("fixture") == BASE_VALUE["fixture"]
        and value.get("clients") == BASE_VALUE["clients"]
        and value.get("selectors") == overlay["selectors"]
        and value.get("execution_contract") == overlay["execution_contract"]
        and value.get("frozen_interpretation") == overlay["frozen_interpretation"]
        and value.get("server_contract", {}).get("cache_type_k") == "q8_0"
        and value.get("server_contract", {}).get("cache_type_v") == "q8_0"
        and value.get("server_contract", {}).get("spec_type") == "none"
    ):
        raise GateError("effective Q8_0-weight/Q8_0-KV manifest invariant failed")


def merged_manifest(value: dict[str, Any]) -> dict[str, Any]:
    return BASE.merged_manifest(value)


class Execution(BASE_EXECUTION):
    def server_argv(self) -> list[str]:
        argv = super().server_argv()
        for flag in ("-ctk", "-ctv"):
            if argv.count(flag) != 1 or argv[argv.index(flag) + 1] != "f16":
                raise GateError(f"sealed Q8_0-weight/F16 parent {flag} selector changed")
            argv[argv.index(flag) + 1] = "q8_0"
        return argv


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
    if sha256_file(Path(value["model"]["path"])) != value["model"]["sha256"]:
        raise GateError("Q8_0 model preflight failed before operational action: SHA-256 mismatch")


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(value)
    verify_base(load_overlay())
    pristine = load_module(BASE_RUNNER, "qwen38_q8weights_f16_pristine_for_q8weights_q8kv_static")
    pristine.static_check(pristine.load_manifest())
    argv = Execution(merged_manifest(value)).server_argv()
    if not (
        argv[argv.index("-m") + 1] == value["model"]["path"]
        and argv[argv.index("--spec-type") + 1] == "none"
        and "--spec-draft-model" not in argv
        and argv[argv.index("-ctk") + 1] == "q8_0"
        and argv[argv.index("-ctv") + 1] == "q8_0"
        and argv[argv.index("-fit") + 1] == "off"
    ):
        raise GateError("effective Q8_0-weight/Q8_0-KV target-only argv invariant failed")
    present, disposition = model_presence(value)
    return {
        "schema": "neural.download.qwen38-q8weights-q8kv-target-http-depth-quality-plan.v1",
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
        "target_only_q8weights_q8kv_cells_if_valid": 7,
        "model_present_and_exact_size": present,
        "model_preflight": disposition,
        "launch_ready": present,
        "server_argv": argv,
    }


# Reuse the audited create-only lifecycle, changing only the sealed KV selector.
for module in (BASE.BASE, BASE.BASE.BASE):
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
    # A correct execution acknowledgement must prove the large model before
    # the inherited lifecycle can acquire locks, inspect GPUs, or create output.
    if "--execute" in sys.argv and "--ack" in sys.argv:
        index = sys.argv.index("--ack")
        if index + 1 < len(sys.argv) and sys.argv[index + 1] == ACK:
            try:
                require_model_before_operational_action(load_manifest())
            except (GateError, OSError, ValueError, json.JSONDecodeError) as exc:
                print(f"{Path(sys.argv[0]).name}: error: {exc}", file=sys.stderr)
                return 2
    return BASE.BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
