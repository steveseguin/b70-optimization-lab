#!/usr/bin/env python3
"""Run the frozen Qwen3.6 Q4_0 F16-KV TP1 exact-depth curve.

The default mode is inert. ``--check`` performs CPU-only static checks.
``--execute`` requires the exact acknowledgement and a clean pushed ``main``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-q4-0-f16kv-tp1-exact-depth-prereg.json"
BASE_MANIFEST = (
    LANE / "data/2026-08-25-qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-r2.json"
)
BASE_ADAPTER = (
    HERE / "run-20260825-qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-r2.py"
)
BASE_MANIFEST_SHA256 = (
    "90f1a308d61d76e4aa55f4f4346116cd65c9dced59f61fb8b1ab9f04d0fcbf80"
)
BASE_ADAPTER_SHA256 = (
    "9143ee1661c92037b961f55bb2ad1a6b9fbe2f3901bb408b435e050685c80018"
)
CAMPAIGN_ID = "qwen36-q4-0-f16kv-tp1-exact-depth-20260825-r1"
STAGE_ID = "d1-exact-depths"
ACK = f"RUN {CAMPAIGN_ID} {STAGE_ID} r1"
RUN_ROOT = Path(
    "/home/steve/qwen36-matrix-runs/"
    "q4-0-tp1-mtp0-f16kv-exact-depth-20260825-r1"
)
DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)
CANONICAL_LOCKS = [
    "/run/lock/muse-glimmer-gpu-exclusive.lock",
    "/tmp/b70-benchmark.lock",
    "/tmp/b70-gpu0.lock",
    "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = load_module("qwen36_q4_0_q8_r2_f16_reference", BASE_ADAPTER)
ENGINE = BASE.R1
CampaignError = ENGINE.CampaignError
ORIGINAL_METADATA = BASE.R1_METADATA
ORIGINAL_TERMINAL_RECEIPT = BASE.R1_TERMINAL_RECEIPT

ARGV = (
    str(ENGINE.BINARY),
    "-m", str(ENGINE.MODEL), "-dev", "SYCL0", "-ngl", "99",
    "-sm", "layer", "-p", "2048", "-n", "128", "-d",
    "0,2048,4096,8192,16384,24576,32768", "-b", "2048",
    "-ub", "512", "-fa", "on", "-ctk", "f16", "-ctv", "f16",
    "-t", "16", "--poll", "50", "-r", "5", "-o", "json",
)


def load_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CampaignError(f"invalid F16 campaign manifest: {exc}") from exc
    if ENGINE.sha256_file(BASE_MANIFEST) != BASE_MANIFEST_SHA256:
        raise CampaignError("referenced q8 runtime manifest changed")
    if ENGINE.sha256_file(BASE_ADAPTER) != BASE_ADAPTER_SHA256:
        raise CampaignError("referenced q8 lifecycle adapter changed")
    return value


def validate_manifest(value: Mapping[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    model = value.get("model") or {}
    runtime = value.get("runtime") or {}
    reference = value.get("runtime_reference") or {}
    lifecycle = value.get("lifecycle") or {}
    interpretation = value.get("interpretation") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-exact-depth-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors.get("revision") == "qwen3.6-27b"
        and selectors.get("artifact_id")
        == "qwen36-27b-unsloth-mtp-q4-0-20c9c45"
        and selectors.get("quantization") == "Q4_0"
        and selectors.get("runtime_build")
        == "9976-e3546c794-dirty-binary-pinned"
        and selectors.get("tp") == 1
        and selectors.get("mtp") == 0
        and selectors.get("speculation_profile") == "target only"
        and selectors.get("graph_mode") == "off"
        and selectors.get("kv") == "f16"
        and tuple(selectors.get("active_context_tokens") or ()) == DEPTHS
        and model.get("size_bytes") == ENGINE.MODEL_SIZE
        and model.get("sha256") == ENGINE.MODEL_SHA256
        and runtime.get("source_commit") == BASE.SOURCE_COMMIT
        and (runtime.get("binary") or {}).get("sha256") == ENGINE.BINARY_SHA256
        and (runtime.get("implementation") or {}).get("sha256")
        == ENGINE.IMPL_SHA256
        and (runtime.get("sycl_backend") or {}).get("sha256")
        == BASE.SYCL_DSO_SHA256
        and reference.get("manifest_sha256") == BASE_MANIFEST_SHA256
        and reference.get("adapter_sha256") == BASE_ADAPTER_SHA256
        and tuple(value.get("argv") or ()) == ARGV
        and (value.get("environment") or {}).get("GGML_SYCL_ENABLE_GRAPH") == "0"
        and lifecycle.get("output_root") == str(RUN_ROOT)
        and lifecycle.get("output_fstype") == "ext4"
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("required_locks") == CANONICAL_LOCKS
        and lifecycle.get("artifacts_are_create_only") is True
        and interpretation.get("speed_floor") is None
        and interpretation.get("new_quality_gate") is False
        and interpretation.get("cell_gain_on_pass") == 7
        and interpretation.get("historical_featured_speeds_are_immutable") is True
        and interpretation.get("cross_revision_or_quantization_transfer_allowed")
        is False
        and interpretation.get("q8_rows_transfer_allowed") is False
    ):
        raise CampaignError("F16 campaign manifest invariant failed")


def verify_static() -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest = load_manifest()
    validate_manifest(manifest)
    ENGINE.verify_artifact(
        ENGINE.MODEL, ENGINE.MODEL_SIZE, ENGINE.MODEL_SHA256, "model"
    )
    ENGINE.verify_artifact(
        ENGINE.BINARY, ENGINE.BINARY_SIZE, ENGINE.BINARY_SHA256, "llama-bench"
    )
    if ENGINE.sha256_file(ENGINE.PARSER) != ENGINE.PARSER_SHA256:
        raise CampaignError("exact-depth parser changed")
    base_manifest = ENGINE.load_json(BASE.R1_MANIFEST)
    environment = ENGINE.effective_environment(RUN_ROOT)
    libraries = ENGINE.verify_libraries(base_manifest, environment)
    implementation = next(
        (row for row in libraries if row["soname"] == "libllama-bench-impl.so"),
        None,
    )
    sycl = next(
        (row for row in libraries if row["soname"] == "libggml-sycl.so.0"),
        None,
    )
    if implementation is None or implementation["sha256"] != ENGINE.IMPL_SHA256:
        raise CampaignError("exact llama-bench implementation is not effective")
    if sycl is None or sycl["sha256"] != BASE.SYCL_DSO_SHA256:
        raise CampaignError("attested SYCL backend is not the effective DSO")
    BASE.verify_graph_off_attestation()
    return manifest, libraries


def metadata(environment: Mapping[str, str]) -> dict[str, Any]:
    result = ORIGINAL_METADATA(environment)
    result["receipt_id"] = CAMPAIGN_ID
    result["argv"] = list(ARGV)
    result["cell_selectors"]["kv"] = "f16"
    proof = "pre-run exact-DSO static graph-off attestation plus controlled environment"
    result["graph"]["capture"]["source"] = proof
    result["graph"]["replay"]["source"] = proof
    result["graph"]["static_attestation"] = {
        "receipt": "graph-off-attestation.json",
        "sycl_backend_sha256": BASE.SYCL_DSO_SHA256,
        "runtime_stderr_markers_used": False,
    }
    return result


def run_benchmark(run_root: Path, environment: Mapping[str, str]) -> int:
    # Repeat exclusion and graph gates under all four held locks immediately
    # before creating the only GPU subprocess.
    BASE.verify_idle()
    attestation = BASE.verify_graph_off_attestation()
    attestation["campaign_id"] = CAMPAIGN_ID
    attestation["attested_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    ENGINE.create_bytes(
        run_root / "graph-off-attestation.json",
        ENGINE.canonical_bytes(attestation),
    )
    stdout_path = run_root / "llama-bench.json"
    stderr_path = run_root / "llama-bench.stderr.log"
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        result = subprocess.run(
            ARGV,
            check=False,
            stdout=stdout,
            stderr=stderr,
            env=dict(environment),
        )
    if result.returncode != 0:
        raise CampaignError(f"llama-bench failed with rc={result.returncode}")
    try:
        raw = json.loads(stdout_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CampaignError("llama-bench stdout is not valid JSON") from exc
    if not isinstance(raw, list) or not raw:
        raise CampaignError("llama-bench stdout is not a nonempty JSON row array")
    return len(raw)


def terminal_receipt(**kwargs: Any) -> dict[str, Any]:
    result = ORIGINAL_TERMINAL_RECEIPT(**kwargs)
    result["graph_off_attestation"] = {
        "path": "graph-off-attestation.json",
        "sycl_backend_sha256": BASE.SYCL_DSO_SHA256,
        "method": "pre-run exact-DSO static proof plus controlled environment",
        "runtime_stderr_markers_used": False,
    }
    result["q8_rows_reused"] = False
    result["q8_run_roots_touched"] = False
    return result


# Retarget the tested create-only engine lifecycle. These assignments affect
# only this process's imported module and never mutate the referenced packet.
ENGINE.MANIFEST = MANIFEST
ENGINE.CAMPAIGN_ID = CAMPAIGN_ID
ENGINE.STAGE_ID = STAGE_ID
ENGINE.ACK = ACK
ENGINE.RUN_ROOT = RUN_ROOT
ENGINE.ARGV = ARGV
ENGINE.verify_static = verify_static
ENGINE.campaign_locks = BASE.campaign_locks
ENGINE.verify_idle = BASE.verify_idle
ENGINE.metadata = metadata
ENGINE.run_benchmark = run_benchmark
ENGINE.terminal_receipt = terminal_receipt


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="show the inert plan")
    mode.add_argument("--check", action="store_true", help="run CPU-only checks")
    mode.add_argument("--execute", action="store_true", help="launch GPU work")
    parser.add_argument("--ack", default="", help="exact execution acknowledgement")
    return parser


def main() -> int:
    args = make_parser().parse_args()
    try:
        manifest = load_manifest()
        validate_manifest(manifest)
        if args.execute:
            result = ENGINE.execute(args.ack)
        elif args.check:
            _, libraries = verify_static()
            result = {
                "mode": "check",
                "status": "passed",
                "campaign_id": CAMPAIGN_ID,
                "graph_off_attestation": "passed",
                "effective_shared_library_count": len(libraries),
                "writes_performed": False,
            }
        else:
            result = {
                "mode": "plan",
                "status": "planned-not-launched",
                "campaign_id": CAMPAIGN_ID,
                "exact_ack": ACK,
                "run_root": str(RUN_ROOT),
                "declared_depths": list(DEPTHS),
                "measurement_class": "raw-engine",
                "includes_quality_gate": False,
                "writes_performed": False,
            }
    except (CampaignError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
