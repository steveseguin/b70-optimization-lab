#!/usr/bin/env python3
"""Run the sealed Qwen3.6 Q4_K_M/q8_0-KV TP1 graph quality battery."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-q4km-q8kv-tp1-sycl-graph-quality-r1-prereg.json"
BASE_MANIFEST = LANE / "data/2026-08-25-qwen36-q4km-f16-tp1-sycl-graph-quality-r1-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260825-qwen36-q4km-f16-tp1-sycl-graph-quality-r1.py"
IMPL_RUNNER = LANE / "scripts/run-20260825-qwen36-q8-q8kv-tp1-sycl-graph-quality-r1.py"
CURVE_RUNNER = LANE / "scripts/run-20260825-qwen36-q4km-q8kv-tp1-sycl-graph-exact-depth-r1.py"
BASE_MANIFEST_SHA256 = "719c238760a1d32584c4ff286f3352b5e943a869ab5db241d94357f3a480695c"
BASE_RUNNER_SHA256 = "975be481da8b4885a84c0b5502ca48f25e1b78bf1bb260118ab75cccad1fdb5b"
IMPL_RUNNER_SHA256 = "1c03886b21a0033a6b0e47468fa15d9983ae43bc6c9ad4d05c6a0dfbd81de8a4"
CAMPAIGN_ID = "qwen36-q4km-q8kv-tp1-sycl-graph-quality-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path(f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}")
PORT = 19440
ALIAS = "qwen36-q4km-q8kv-tp1-graph-quality-r1"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import sealed runner: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASEQ = _load(BASE_RUNNER, "qwen36_q4km_f16_quality_for_q8kv")
CURVE = _load(CURVE_RUNNER, "qwen36_q4km_q8kv_curve_for_quality")
IMPL = _load(IMPL_RUNNER, "qwen36_q8kv_quality_lifecycle_for_q4km")
BASE_MANIFEST_VALUE = copy.deepcopy(BASEQ.load_manifest())
GateError = BASEQ.GateError


def sha256_file(path: Path) -> str:
    return BASEQ.BASEQ.BASEQ.sha256_file(path)


def load_overlay() -> dict[str, Any]:
    value = CURVE.R1.load_json(OVERLAY)
    if not (
        value.get("schema") == "neural.download.qwen36-llama-sycl-graph-q4km-q8kv-quality-overlay.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "sealed-preregistered-not-launched"
        and value.get("base_quality_packet") == {
            "manifest_path": str(BASE_MANIFEST.relative_to(REPO)), "manifest_sha256": BASE_MANIFEST_SHA256,
            "runner_path": str(BASE_RUNNER.relative_to(REPO)), "runner_sha256": BASE_RUNNER_SHA256,
        }
        and value.get("sealed_q8kv_service_lifecycle_implementation", {}).get("path") == str(IMPL_RUNNER.relative_to(REPO))
        and value.get("sealed_q8kv_service_lifecycle_implementation", {}).get("sha256") == IMPL_RUNNER_SHA256
        and value.get("curve_parent", {}).get("campaign_id") == CURVE.CAMPAIGN_ID
        and value.get("curve_parent", {}).get("depths") == CURVE.R1.DEPTHS
        and value.get("execution_identity_delta") == {
            "only_runtime_selector_delta_from_q4km_f16_quality": "selectors.kv and server -ctk/-ctv change from f16 to q8_0; curve/campaign/alias/port/output identities change correspondingly",
            "selectors.kv": "q8_0", "ctk": "q8_0", "ctv": "q8_0", "service_alias": ALIAS, "service_port": PORT,
        }
        and value.get("lifecycle") == {"output_root": str(RUN_ROOT), "exact_ack": ACK, "create_only": True}
        and value.get("authority") == {
            "quality_may_cover_all_seven_q4km_q8kv_curve_cells_on_pass": True,
            "per_depth_quality_reruns_required": False,
            "site_publication_authorized": False,
            "record_or_submission_authorized": False,
            "protected_graph_off_values_may_be_replaced": False,
            "publication_requires_tracked_adjudication_and_separate_ingestion": True,
        }
    ):
        raise GateError("Q4_K_M/q8KV quality overlay invariant failed")
    return value


def _replace(argv: list[str], flag: str, old: str, new: str) -> None:
    if argv.count(flag) != 1 or argv[argv.index(flag) + 1] != old:
        raise GateError(f"sealed Q4_K_M/F16 argv changed at {flag}")
    argv[argv.index(flag) + 1] = new


def load_manifest() -> dict[str, Any]:
    overlay = load_overlay()
    for path, expected in ((BASE_MANIFEST, BASE_MANIFEST_SHA256), (BASE_RUNNER, BASE_RUNNER_SHA256), (IMPL_RUNNER, IMPL_RUNNER_SHA256)):
        if sha256_file(path) != expected:
            raise GateError(f"sealed quality dependency changed: {path}")
    value = copy.deepcopy(BASE_MANIFEST_VALUE)
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] = overlay["purpose"]
    value["curve_parent"] = copy.deepcopy(overlay["curve_parent"])
    value["selectors"]["kv"] = "q8_0"
    argv = value["server_argv"]
    _replace(argv, "--alias", "qwen36-q4km-f16-tp1-graph-quality-r1", ALIAS)
    _replace(argv, "--port", "19439", str(PORT))
    _replace(argv, "-ctk", "f16", "q8_0")
    _replace(argv, "-ctv", "f16", "q8_0")
    value["lifecycle"]["output_root"] = str(RUN_ROOT)
    value["lifecycle"]["exact_ack"] = ACK
    return value


def validate_manifest(value: Mapping[str, Any]) -> None:
    expected = load_manifest()
    if dict(value) != expected:
        raise GateError("Q4_K_M/q8KV synthesized quality manifest changed")
    argv = value["server_argv"]
    if not (
        value["model"] == BASE_MANIFEST_VALUE["model"] == CURVE.load_manifest()["model"]
        and value["selectors"]["artifact_id"] == "qwen36-27b-unsloth-mtp-q4-k-m-5cb35eb"
        and value["selectors"]["quantization"] == "Q4_K_M"
        and value["selectors"]["mtp"] == 0
        and value["selectors"]["kv"] == "q8_0"
        and argv[argv.index("-ctk") + 1] == "q8_0"
        and argv[argv.index("-ctv") + 1] == "q8_0"
        and argv[argv.index("--spec-type") + 1] == "none"
        and value["environment"] == CURVE.load_manifest()["environment"]
    ):
        raise GateError("Q4_K_M/q8KV model or service selectors changed")
    base = copy.deepcopy(BASE_MANIFEST_VALUE)
    reconstructed = copy.deepcopy(dict(value))
    reconstructed["campaign_id"] = base["campaign_id"]
    reconstructed["purpose"] = base["purpose"]
    reconstructed["curve_parent"] = copy.deepcopy(base["curve_parent"])
    reconstructed["selectors"]["kv"] = "f16"
    argv = reconstructed["server_argv"]
    for flag in ("--alias", "--port", "-ctk", "-ctv"):
        argv[argv.index(flag) + 1] = base["server_argv"][base["server_argv"].index(flag) + 1]
    reconstructed["lifecycle"]["output_root"] = base["lifecycle"]["output_root"]
    reconstructed["lifecycle"]["exact_ack"] = base["lifecycle"]["exact_ack"]
    if reconstructed != base:
        raise GateError("Q4_K_M/q8KV packet changes more than KV and corresponding identities")


IMPL.F16 = BASEQ.BASEQ.BASEQ
IMPL.CURVE = CURVE
IMPL.BASE = CURVE.R1.BASE
IMPL.GateError = GateError
IMPL.OVERLAY = OVERLAY
IMPL.CAMPAIGN_ID = CAMPAIGN_ID
IMPL.ACK = ACK
IMPL.RUN_ROOT = RUN_ROOT
IMPL.PORT = PORT
IMPL.ALIAS = ALIAS
IMPL.load_overlay = load_overlay
IMPL.load_manifest = load_manifest
IMPL.validate_manifest = validate_manifest


static_check = IMPL.static_check
execute = IMPL.execute


def plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {"campaign_id": CAMPAIGN_ID, "state": manifest["state"], "default_is_inert": True,
            "output_root": str(RUN_ROOT), "ack": ACK, "request_count": 13, "quantization": "Q4_K_M",
            "kv": "q8_0", "quality_may_cover_all_seven_curve_cells_on_pass": True,
            "site_publication_authorized": False}


IMPL.plan = plan


def main(argv: list[str] | None = None) -> int:
    return IMPL.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
