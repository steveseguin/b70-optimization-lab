#!/usr/bin/env python3
"""Run the sealed Qwen3.6 Q4_K_M/F16 TP1 graph quality battery."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-q4km-f16-tp1-sycl-graph-quality-r1-prereg.json"
BASE_MANIFEST = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-sycl-graph-quality-r1-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260825-qwen36-mtpq8-f16-tp1-sycl-graph-quality-r1.py"
IMPL_RUNNER = LANE / "scripts/run-20260825-qwen36-q8-q8kv-tp1-sycl-graph-quality-r1.py"
CURVE_RUNNER = LANE / "scripts/run-20260825-qwen36-q4km-f16-tp1-sycl-graph-exact-depth-r1.py"
BASE_MANIFEST_SHA256 = "2b4b9adc17c65ccf60669d95604398de44afb74a9ef1c818909eb5e190a642ca"
BASE_RUNNER_SHA256 = "5d342a3dceb2f2cfda63e2a95872eeaae59a911f1cdf24c9ae170e5eab8f4db7"
IMPL_RUNNER_SHA256 = "1c03886b21a0033a6b0e47468fa15d9983ae43bc6c9ad4d05c6a0dfbd81de8a4"
CAMPAIGN_ID = "qwen36-q4km-f16-tp1-sycl-graph-quality-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path(f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}")
PORT = 19439
ALIAS = "qwen36-q4km-f16-tp1-graph-quality-r1"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import sealed runner: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASEQ = _load(BASE_RUNNER, "qwen36_mtpq8_f16_quality_for_q4km")
CURVE = _load(CURVE_RUNNER, "qwen36_q4km_f16_curve_for_quality")
IMPL = _load(IMPL_RUNNER, "qwen36_service_quality_lifecycle_for_q4km")
BASE_MANIFEST_VALUE = copy.deepcopy(BASEQ.load_manifest())
GateError = BASEQ.GateError


def sha256_file(path: Path) -> str:
    return BASEQ.BASEQ.sha256_file(path)


def load_overlay() -> dict[str, Any]:
    value = CURVE.R1.load_json(OVERLAY)
    delta = value.get("model_identity_delta") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-sycl-graph-q4km-f16-quality-overlay.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "sealed-preregistered-not-launched"
        and value.get("base_quality_packet") == {
            "manifest_path": str(BASE_MANIFEST.relative_to(REPO)), "manifest_sha256": BASE_MANIFEST_SHA256,
            "runner_path": str(BASE_RUNNER.relative_to(REPO)), "runner_sha256": BASE_RUNNER_SHA256,
        }
        and value.get("sealed_service_lifecycle_implementation", {}).get("path") == str(IMPL_RUNNER.relative_to(REPO))
        and value.get("sealed_service_lifecycle_implementation", {}).get("sha256") == IMPL_RUNNER_SHA256
        and value.get("curve_parent", {}).get("campaign_id") == CURVE.CAMPAIGN_ID
        and value.get("curve_parent", {}).get("depths") == CURVE.R1.DEPTHS
        and delta.get("artifact_id") == "qwen36-27b-unsloth-mtp-q4-k-m-5cb35eb"
        and delta.get("quantization") == "Q4_K_M"
        and delta.get("service_alias") == ALIAS
        and delta.get("service_port") == PORT
        and delta.get("model") == CURVE.load_manifest()["model"]
        and value.get("lifecycle") == {"output_root": str(RUN_ROOT), "exact_ack": ACK, "create_only": True}
        and value.get("authority") == {
            "quality_may_cover_all_seven_q4km_f16_curve_cells_on_pass": True,
            "per_depth_quality_reruns_required": False,
            "site_publication_authorized": False,
            "record_or_submission_authorized": False,
            "protected_graph_off_values_may_be_replaced": False,
            "publication_requires_tracked_adjudication_and_separate_ingestion": True,
        }
    ):
        raise GateError("Q4_K_M/F16 quality overlay invariant failed")
    return value


def _replace(argv: list[str], flag: str, old: str, new: str) -> None:
    if argv.count(flag) != 1 or argv[argv.index(flag) + 1] != old:
        raise GateError(f"sealed base argv changed at {flag}")
    argv[argv.index(flag) + 1] = new


def load_manifest() -> dict[str, Any]:
    overlay = load_overlay()
    for path, expected in ((BASE_MANIFEST, BASE_MANIFEST_SHA256), (BASE_RUNNER, BASE_RUNNER_SHA256), (IMPL_RUNNER, IMPL_RUNNER_SHA256)):
        if sha256_file(path) != expected:
            raise GateError(f"sealed quality dependency changed: {path}")
    value = copy.deepcopy(BASE_MANIFEST_VALUE)
    delta = overlay["model_identity_delta"]
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] = overlay["purpose"]
    value["curve_parent"] = copy.deepcopy(overlay["curve_parent"])
    value["selectors"]["artifact_id"] = delta["artifact_id"]
    value["selectors"]["quantization"] = delta["quantization"]
    value["model"] = copy.deepcopy(delta["model"])
    argv = value["server_argv"]
    _replace(argv, "-m", BASE_MANIFEST_VALUE["model"]["path"], value["model"]["path"])
    _replace(argv, "--alias", "qwen36-mtpq8-f16-tp1-graph-quality-r1", ALIAS)
    _replace(argv, "--port", "19436", str(PORT))
    value["lifecycle"]["output_root"] = str(RUN_ROOT)
    value["lifecycle"]["exact_ack"] = ACK
    value["raw_terminal_writer_caveat"] = copy.deepcopy(overlay["raw_terminal_writer_caveat"])
    value["authority"]["publication_requires_tracked_adjudication_and_separate_ingestion"] = True
    return value


def validate_manifest(value: Mapping[str, Any]) -> None:
    expected = load_manifest()
    if dict(value) != expected:
        raise GateError("Q4_K_M/F16 synthesized quality manifest changed")
    argv = value["server_argv"]
    if not (
        value["model"] == CURVE.load_manifest()["model"]
        and value["selectors"]["artifact_id"] == "qwen36-27b-unsloth-mtp-q4-k-m-5cb35eb"
        and value["selectors"]["quantization"] == "Q4_K_M"
        and value["selectors"]["mtp"] == 0
        and value["selectors"]["kv"] == "f16"
        and argv[argv.index("-ctk") + 1] == "f16"
        and argv[argv.index("-ctv") + 1] == "f16"
        and argv[argv.index("--spec-type") + 1] == "none"
        and value["environment"] == CURVE.load_manifest()["environment"]
    ):
        raise GateError("Q4_K_M/F16 identity or preserved service selectors changed")
    base = copy.deepcopy(BASE_MANIFEST_VALUE)
    reconstructed = copy.deepcopy(dict(value))
    reconstructed["campaign_id"] = base["campaign_id"]
    reconstructed["purpose"] = base["purpose"]
    reconstructed["curve_parent"] = copy.deepcopy(base["curve_parent"])
    reconstructed["selectors"]["artifact_id"] = base["selectors"]["artifact_id"]
    reconstructed["selectors"]["quantization"] = base["selectors"]["quantization"]
    reconstructed["model"] = copy.deepcopy(base["model"])
    argv = reconstructed["server_argv"]
    for flag in ("-m", "--alias", "--port"):
        argv[argv.index(flag) + 1] = base["server_argv"][base["server_argv"].index(flag) + 1]
    reconstructed["lifecycle"]["output_root"] = base["lifecycle"]["output_root"]
    reconstructed["lifecycle"]["exact_ack"] = base["lifecycle"]["exact_ack"]
    reconstructed.pop("raw_terminal_writer_caveat", None)
    reconstructed["authority"].pop("publication_requires_tracked_adjudication_and_separate_ingestion", None)
    if reconstructed != base:
        raise GateError("Q4_K_M/F16 packet changes more than complete model and corresponding identities")


def static_check():
    manifest = load_manifest()
    validate_manifest(manifest)
    CURVE.R1.static_check()
    parent = manifest["curve_parent"]
    paths = {key: IMPL.verify_ref(parent[key], f"curve {key}") for key in ("preregistration", "runner", "terminal_receipt", "exact_depth_receipt", "metadata", "graph_evidence")}
    terminal = CURVE.R1.load_json(paths["terminal_receipt"])
    receipt = CURVE.R1.load_json(paths["exact_depth_receipt"])
    if not (
        terminal.get("campaign_id") == parent["campaign_id"]
        and terminal.get("state") == "passed-raw-graph-cells-quality-pending"
        and terminal.get("cleanup_passed") is True
        and terminal.get("launched_depths") == parent["depths"]
        and terminal.get("protected_graph_off_values_replaced") is False
        and receipt.get("status") == "passed"
        and (receipt.get("gate") or {}).get("exact_cell_ready") is True
        and len(receipt.get("cells") or []) == 7
        and all((cell.get("selectors") or {}).get("artifact_id") == manifest["selectors"]["artifact_id"] for cell in receipt.get("cells") or [])
        and all((cell.get("selectors") or {}).get("kv") == "f16" for cell in receipt.get("cells") or [])
    ):
        raise GateError("Q4_K_M/F16 curve parent is not a passed seven-cell packet")
    runtime = manifest["runtime"]
    server = IMPL.verify_ref(runtime["server"], "llama-server", size=True)
    IMPL.verify_ref(runtime["server_impl"], "server implementation")
    IMPL.verify_ref(runtime["graph_backend"], "graph backend", size=True)
    quality = manifest["quality"]
    IMPL.verify_ref(quality["helper"], "quality helper")
    IMPL.verify_ref(quality["python"], "quality Python")
    tokenizer = Path(quality["tokenizer"]["path"])
    if sha256_file(tokenizer / "tokenizer.json") != quality["tokenizer"]["tokenizer_json_sha256"] or sha256_file(tokenizer / "tokenizer_config.json") != quality["tokenizer"]["tokenizer_config_sha256"]:
        raise GateError("tokenizer identity changed")
    for item in manifest["source"]["patch_chain_in_order"]:
        IMPL.verify_ref(item, "source patch")
    environment = CURVE.R1.BASE.oneapi_environment(RUN_ROOT, manifest["environment"])
    libraries = CURVE.R1.BASE.effective_libraries(server, environment)
    closure = runtime["server_effective_shared_libraries"]
    if len(libraries) != closure["count"] or BASEQ.BASEQ.canonical_sha256(libraries) != closure["canonical_json_sha256"]:
        raise GateError("server DSO closure changed")
    return manifest, environment, libraries


IMPL.F16 = BASEQ.BASEQ
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
IMPL.static_check = static_check


execute = IMPL.execute


def plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "campaign_id": CAMPAIGN_ID,
        "state": manifest["state"],
        "default_is_inert": True,
        "output_root": str(RUN_ROOT),
        "ack": ACK,
        "request_count": 13,
        "quantization": "Q4_K_M",
        "kv": "f16",
        "quality_may_cover_all_seven_curve_cells_on_pass": True,
        "site_publication_authorized": False,
    }


IMPL.plan = plan


def main(argv: list[str] | None = None) -> int:
    return IMPL.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
