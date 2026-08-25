#!/usr/bin/env python3
"""Model-identity overlay for the sealed target-Q8/F16 R4 graph curve."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-sycl-graph-exact-depth-r1-prereg.json"
BASE_MANIFEST = LANE / "data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r4-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r4.py"
OFF_MANIFEST = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-exact-depth-prereg.json"
OFF_RESULT = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-exact-depth-result.json"
BASE_MANIFEST_SHA256 = "32ffe76461abcfe2b57606d9d25cb3240f3b6705e0bdcacc6d52465d355b070b"
BASE_RUNNER_SHA256 = "ed3deb0c739dcadab97c26532b8bd4549178932c1926a9a0338d383e985f4602"
OFF_MANIFEST_SHA256 = "d4cd3fe61fc1e78ecdf4f2bffbcb8db808d484dcdb0d03fa170a83a213af5089"
OFF_RESULT_SHA256 = "bec6f1427a0fd02b029522af54eccaa320e86eedc4e0b7d12d1b1c3effdb7b7e"
CAMPAIGN_ID = "qwen36-mtpq8-f16-tp1-sycl-graph-exact-depth-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path(f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}")
ARTIFACT_ID = "qwen36-27b-unsloth-mtp-q8-0-5cb35eb"
MODEL_PATH = Path("/mnt/usb-models/models/qwen36-27b-mtp-q8-gguf/Qwen3.6-27B-Q8_0.gguf")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_base():
    spec = importlib.util.spec_from_file_location("qwen36_q8_f16_graph_r4_for_mtpq8", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import sealed R4 runner: {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_base()
R1 = BASE.R1
GateError = BASE.GateError
BASE_LOAD_MANIFEST = BASE.load_manifest


def load_overlay() -> dict[str, Any]:
    value = R1.load_json(OVERLAY)
    base = value.get("base") or {}
    reference = value.get("accepted_graph_off_embedded_mtp_reference") or {}
    delta = value.get("model_identity_delta") or {}
    model = delta.get("model") or {}
    preserved = value.get("preserved") or {}
    lifecycle = value.get("lifecycle") or {}
    authority = value.get("authority") or {}
    expected_chain = [
        "1a8589f894fde7d87aac35c59bc81e3701bf7f6d9ba54f35808ae262325d7892",
        "1575acc5ee07b37eb98186a09d201a895d36501c223dc114110a43ee08f4e0a3",
        "3def9e5eeb42d9bd1dc4b0c759092572db178651ecafc5255943753bd8b485f6",
    ]
    if not (
        value.get("schema") == "neural.download.qwen36-llama-sycl-graph-embedded-mtp-q8-model-overlay.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and value.get("sealing_status") == "sealed"
        and base == {
            "manifest_path": str(BASE_MANIFEST.relative_to(REPO)),
            "manifest_sha256": BASE_MANIFEST_SHA256,
            "runner_path": str(BASE_RUNNER.relative_to(REPO)),
            "runner_sha256": BASE_RUNNER_SHA256,
        }
        and reference.get("manifest_path") == str(OFF_MANIFEST.relative_to(REPO))
        and reference.get("manifest_sha256") == OFF_MANIFEST_SHA256
        and reference.get("result_path") == str(OFF_RESULT.relative_to(REPO))
        and reference.get("result_sha256") == OFF_RESULT_SHA256
        and reference.get("measurement_id") == "q36-mtpq8-tp1-kv-f16-context"
        and delta.get("from_artifact_id") == "qwen36-27b-unsloth-q8-0-82d411a"
        and delta.get("to_artifact_id") == ARTIFACT_ID
        and model.get("repository") == "unsloth/Qwen3.6-27B-MTP-GGUF"
        and model.get("revision") == "5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace"
        and model.get("path") == str(MODEL_PATH)
        and model.get("size_bytes") == 29047084160
        and model.get("sha256") == "9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8"
        and model.get("direct_sha256") == model.get("sha256")
        and model.get("ordinary_sha256") == model.get("sha256")
        and model.get("embedded_mtp_capability") is True
        and delta.get("mtp_selector", {}).get("value") == 0
        and [item.get("sha256") for item in value.get("source_patch_chain_in_order", [])] == expected_chain
        and preserved == {
            "contexts": R1.DEPTHS,
            "tp": 1,
            "mtp": 0,
            "kv": "f16",
            "graph_on_cache8": True,
            "source_backend_build_and_32_dso_closure": True,
            "three_patch_chain": True,
            "environment_and_verbose_argv": True,
            "phase_aware_prefill_and_decode_gates": True,
            "create_only_lifecycle": True,
        }
        and lifecycle == {"output_root": str(RUN_ROOT), "exact_ack": ACK}
        and authority == {
            "raw_cells_require_all_existing_gates": True,
            "quality_gate_required_before_publication": True,
            "site_publication_authorized": False,
            "record_or_submission_authorized": False,
            "quality_claim_authorized": False,
            "graph_estimates_forbidden": True,
            "protected_graph_off_values_must_not_be_replaced": True,
            "speed_floor": None,
        }
    ):
        raise GateError("embedded-MTP Q8 graph overlay invariant failed")
    return value


def load_manifest() -> dict[str, Any]:
    overlay = load_overlay()
    for path, expected, label in (
        (BASE_MANIFEST, BASE_MANIFEST_SHA256, "R4 manifest"),
        (BASE_RUNNER, BASE_RUNNER_SHA256, "R4 runner"),
        (OFF_MANIFEST, OFF_MANIFEST_SHA256, "graph-off manifest"),
        (OFF_RESULT, OFF_RESULT_SHA256, "graph-off result"),
    ):
        if sha256_file(path) != expected:
            raise GateError(f"sealed {label} changed")
    value = copy.deepcopy(BASE_LOAD_MANIFEST())
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] += " This sibling changes only to the checksum-pinned embedded-MTP Q8 model while keeping MTP disabled."
    value["selectors"]["artifact_id"] = ARTIFACT_ID
    value["model"] = copy.deepcopy(overlay["model_identity_delta"]["model"])
    argv = value["argv_template"]
    model_index = argv.index("-m") + 1
    if argv[model_index] != BASE_LOAD_MANIFEST()["model"]["path"]:
        raise GateError("sealed R4 model argv changed")
    argv[model_index] = str(MODEL_PATH)
    value["lifecycle"]["output_root"] = str(RUN_ROOT)
    value["lifecycle"]["exact_ack"] = ACK
    value["interpretation"]["fill_only"] = "the seven embedded-MTP Q8_0 artifact TP1/MTP0/SYCL-graph/F16-KV cells only"
    return value


def validate_manifest(value: Mapping[str, Any]) -> None:
    expected = load_manifest()
    if dict(value) != expected:
        raise GateError("synthesized embedded-MTP manifest differs from sealed overlay")
    base = BASE_LOAD_MANIFEST()
    if not (
        value["selectors"]["mtp"] == 0
        and value["selectors"]["kv"] == "f16"
        and value["selectors"]["active_context_tokens"] == R1.DEPTHS
        and value["environment"] == base["environment"]
        and value["runtime"] == base["runtime"]
        and value["source"] == base["source"]
        and value["graph_evidence"] == base["graph_evidence"]
        and value["argv_template"][-3:] == ["-v", "-o", "json"]
    ):
        raise GateError("non-model graph identity changed")
    reconstructed = copy.deepcopy(dict(value))
    reconstructed["campaign_id"] = base["campaign_id"]
    reconstructed["purpose"] = base["purpose"]
    reconstructed["selectors"]["artifact_id"] = base["selectors"]["artifact_id"]
    reconstructed["model"] = copy.deepcopy(base["model"])
    reconstructed["argv_template"][reconstructed["argv_template"].index("-m") + 1] = base["model"]["path"]
    reconstructed["lifecycle"]["output_root"] = base["lifecycle"]["output_root"]
    reconstructed["lifecycle"]["exact_ack"] = base["lifecycle"]["exact_ack"]
    reconstructed["interpretation"]["fill_only"] = base["interpretation"]["fill_only"]
    if reconstructed != base:
        raise GateError("overlay changes more than model and create-only lifecycle identity")


R1.MANIFEST = OVERLAY
R1.CAMPAIGN_ID = CAMPAIGN_ID
R1.ACK = ACK
R1.RUN_ROOT = RUN_ROOT
R1.load_manifest = load_manifest
R1.validate_manifest = validate_manifest


def main(argv: list[str] | None = None) -> int:
    return R1.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
