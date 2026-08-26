#!/usr/bin/env python3
"""Create-only b2dd/1e90 AutoRound INT4 TP2 exact-depth/quality packet."""

from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
SELF = Path(__file__).resolve()
MANIFEST = LANE / "data/2026-08-26-qwen38-b2dd9ce73d-tp2-exact-depth-quality-r1-prereg.json"
NOTE = LANE / "notes/2026-08-26-qwen38-b2dd9ce73d-tp2-exact-depth-quality-r1-preregistration.md"
BASE_RUNNER = LANE / "scripts/run-20260825-qwen38-b2dd9ce73d-tp1-exact-depth-r1.py"
PARENT = LANE / "data/2026-08-25-qwen38-b2dd9ce73d-tp2-zero-overlay-r1-prereg.json"
CAMPAIGN_ID = "qwen38-b2dd9ce73d-tp2-exact-depth-quality-20260826-r1"
STAGE_ID = "d2-exact-depths"
ROOT_R1 = Path("/home/steve/qwen38-current-main-runs/tp2-exact-depth-b2dd9ce73d-20260826-r1/01-exact-depths")
CACHE_R1 = Path("/home/steve/qwen38-current-main-runs/tp2-exact-depth-cache-b2dd9ce73d-20260826-r1/01-exact-depths")
PORT_R1 = 20878
DEPTHS = (2048, 4096, 8192, 16384, 24576, 32768)
MAX_MODEL_LEN = 32896
TP = 2
GPUS = "0,1"
GPU_MEMORY_UTILIZATION = "0.90"
BASELINE = Path(
    "/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/"
    "tp2-mtp0-f16-graph-natural-eos-replay-b-baseline-quality/quality.json"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = load_module(BASE_RUNNER, "qwen38_b2dd_tp1_exact_depth_base_for_tp2")
CampaignError = BASE.CampaignError
COMMON = BASE.COMMON
BASE_STAGE_ENVIRONMENT = BASE.stage_environment
FIXTURE = BASE.FIXTURE
FIXTURE_SHA256 = BASE.FIXTURE_SHA256
MODEL = BASE.MODEL
MODEL_REVISION = BASE.MODEL_REVISION
MODEL_MANIFEST = BASE.MODEL_MANIFEST
MODEL_VERIFIER = BASE.MODEL_VERIFIER
QUALITY_HELPER = BASE.QUALITY_HELPER
RUNNER = BASE.RUNNER
PROTECTED_MANIFEST = BASE.PROTECTED_MANIFEST
PROTECTED_VALUES_SHA256 = BASE.PROTECTED_VALUES_SHA256
IMAGE_TAG = BASE.IMAGE_TAG
IMAGE_ID = BASE.IMAGE_ID
SOURCE_IDENTITY_SHA256 = BASE.SOURCE_IDENTITY_SHA256
VLLM_HEAD = BASE.VLLM_HEAD
KERNEL_HEAD = BASE.KERNEL_HEAD


DEPENDENCIES = {
    MANIFEST: "33d3db1798e859183f4f07f5887e0968dc0dd89d1ce455933a479ee76239341a",
    NOTE: "3ec606127d66186c397a3b6915c75a5333c65e7e50b66cbc1eb3ee408321ac42",
    BASE_RUNNER: "7ca55b38bb581a48b690c5816b97137c0311ea9c87be034947950bdd02182778",
    PARENT: "23117ded88c53ca358def6f317ad1ca573b9c2957dba353f6505c987ecfcbadb",
    BASE.BUILD_RECORD: "d56dc84c1137d741042b2e295c6b1f6a40bf28a3c56e0c52761dd725e3a5caa0",
    BASE.COMMON_PATH: "daffc2782871f9499fd09133ee4fa6eb5cd6e626a19204ea1c6361471c6ab351",
    RUNNER: "cb2bfd95e7ad9956dae5bc22ccfa575c8742847c963143291a21505533598202",
    BASE.DEPTH_HELPER: "8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067",
    FIXTURE: FIXTURE_SHA256,
    MODEL_MANIFEST: "731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8",
    MODEL_VERIFIER: "5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9",
    QUALITY_HELPER: "67e65fc342393e5ae6903a332c929b3a2693e1f943c8a819b8447284fe835f6d",
    BASELINE: "0ba49be19bbb081023259ce290f87990d3e26038e461d136862631442a63bc48",
    PROTECTED_MANIFEST: "4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454",
}


def sha256_file(path: Path) -> str:
    return BASE.sha256_file(path)


def load_json(path: Path) -> dict[str, Any]:
    return BASE.load_json(path)


def layout(attempt: int):
    if attempt < 1 or attempt > 99:
        raise CampaignError("attempt must be between 1 and 99")
    suffix = f"r{attempt}"
    output = Path(re.sub(r"r1(?=/)", suffix, str(ROOT_R1), count=1))
    cache = Path(re.sub(r"r1(?=/)", suffix, str(CACHE_R1), count=1))
    return BASE.Layout(output, cache, PORT_R1 + (attempt - 1) * 10)


def verify_dependencies() -> dict[str, str]:
    observed = {str(path): BASE._require_hash(path, digest) for path, digest in DEPENDENCIES.items()}
    value = load_json(MANIFEST)
    run = value.get("run_identity") or {}
    contract = value.get("exact_depth_contract") or {}
    lifecycle = value.get("lifecycle") or {}
    frozen = value.get("frozen_interpretation") or {}
    identity_parent = value.get("identity_parent") or {}
    if not (
        value.get("state") == "preregistered-not-launched"
        and value.get("campaign_id") == CAMPAIGN_ID
        and run.get("image_tag") == IMAGE_TAG
        and run.get("image_id") == IMAGE_ID
        and run.get("source_identity_sha256") == SOURCE_IDENTITY_SHA256
        and run.get("vllm_head") == VLLM_HEAD
        and run.get("xpu_kernel_head") == KERNEL_HEAD
        and run.get("model_revision") == MODEL_REVISION
        and run.get("tensor_parallel_size") == TP
        and run.get("gpu_affinity") == GPUS
        and run.get("mtp_depth") == 0
        and run.get("kv_cache_dtype") == "float16"
        and run.get("graph_mode") == "FULL_AND_PIECEWISE"
        and run.get("max_model_len") == MAX_MODEL_LEN
        and run.get("gpu_memory_utilization") == 0.9
        and run.get("pythonhashseed") == "unset"
        and contract.get("fixture_sha256") == FIXTURE_SHA256
        and tuple(contract.get("measured_depths") or ()) == DEPTHS
        and (contract.get("depth_zero") or {}).get("state_after_campaign") == "missing"
        and contract.get("configured_capacity_is_not_active_context") is True
        and lifecycle.get("default_is_inert") is True
        and lifecycle.get("create_only") is True
        and frozen.get("speed_floor") is None
        and frozen.get("nonzero_exact_context_cells_authorized_if_all_gates_pass") == 6
        and frozen.get("depth_zero_cells_authorized") == 0
        and identity_parent.get("lowering_or_replacement_allowed") is False
        and frozen.get("protected_decode_values")
        == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]
    ):
        raise CampaignError("TP2 exact-depth manifest invariant failed")
    parent = load_json(PARENT)
    parent_run = parent.get("frozen_identity") or {}
    topology = parent.get("topology") or {}
    comparisons = parent.get("protected_speed_comparisons_tok_s") or {}
    parent_baseline = parent.get("frozen_inputs") or {}
    if not (
        parent.get("state") == "preregistered-not-launched"
        and parent_run.get("vllm_commit") == VLLM_HEAD
        and parent_run.get("xpu_kernel_commit") == KERNEL_HEAD
        and parent_run.get("image_id") == IMAGE_ID
        and parent_run.get("source_identity_sha256") == SOURCE_IDENTITY_SHA256
        and parent_run.get("overlay") == "none"
        and topology.get("tensor_parallel") == 2
        and topology.get("gpus") == GPUS
        and topology.get("mtp_depth") == 0
        and topology.get("kv_cache_dtype") == "float16"
        and topology.get("gpu_memory_utilization") == 0.9
        and (topology.get("graph") or {}).get("mode") == "FULL_AND_PIECEWISE"
        and (topology.get("graph") or {}).get("capture_sizes") == [1, 2]
        and parent_baseline.get("quality_baseline_sha256") == DEPENDENCIES[BASELINE]
        and comparisons.get("diagnostic_captured_high") == 48.950458800865434
        and comparisons.get("strict_floor") == 49.01965141150585
        and comparisons.get("accepted_overlay_diagnostic") == 49.05894025767351
        and comparisons.get("accepted_overlay_strict") == 49.00935245117815
        and comparisons.get("speed_controls_execution") is False
        and comparisons.get("lowering_or_replacement_allowed") is False
    ):
        raise CampaignError("frozen b2dd TP2 identity parent changed")
    build = load_json(BASE.BUILD_RECORD)
    both = (build.get("images") or {}).get("both_current_zero_overlay") or {}
    if not (
        (build.get("vllm") or {}).get("head") == VLLM_HEAD
        and (build.get("kernel") or {}).get("head") == KERNEL_HEAD
        and both.get("image_id") == IMAGE_ID
        and both.get("static_preflight_passed") is True
    ):
        raise CampaignError("b2dd build identity changed")
    model = load_json(MODEL_MANIFEST)
    if model.get("revision") != MODEL_REVISION or (model.get("identity") or {}).get("quantization") != "AutoRound INT4 W4A16":
        raise CampaignError("AutoRound model identity changed")
    protected = load_json(PROTECTED_MANIFEST)
    canonical = json.dumps(protected.get("protected_target_only_decode_tok_s"), sort_keys=True, separators=(",", ":")) + "\n"
    if hashlib.sha256(canonical.encode()).hexdigest() != PROTECTED_VALUES_SHA256:
        raise CampaignError("protected speed ledger changed")
    return observed


def stage_environment() -> dict[str, str]:
    env = BASE_STAGE_ENVIRONMENT()
    env["GPU_MEM_UTIL"] = GPU_MEMORY_UTILIZATION
    env["QUALITY_BASELINE_JSON"] = str(BASELINE)
    env.pop("PYTHONHASHSEED", None)
    return env


@contextlib.contextmanager
def tp2_campaign_locks():
    paths = [Path("/run/lock/muse-glimmer-gpu-exclusive.lock"), Path("/tmp/b70-benchmark.lock")]
    paths.extend(Path(f"/run/user/{os.getuid()}/qwen36-b70-gpu-leases/gpu{index}.lock") for index in range(2))
    handles = []
    try:
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = path.open("a+")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise CampaignError(f"TP2 campaign lock is held: {path}") from exc
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            handle.close()


def _expected_extra() -> str:
    return json.dumps(
        ["--pipeline-parallel-size", "1", "--data-parallel-size", "1", "--enable-chunked-prefill", "--async-scheduling", "--compilation-config", '{"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2}'],
        separators=(",", ":"),
    )


def verify_exact_run_identity(output: Path, *, launch_head: str, expected_cache: Path) -> dict[str, Any]:
    identity = BASE._identity_env(output)
    expected = {
        "lab_git_head": launch_head, "tp": "2", "gpus": GPUS, "mtp": "0", "kv": "f16",
        "max_model_len": str(MAX_MODEL_LEN), "gpu_memory_utilization": GPU_MEMORY_UTILIZATION,
        "cache_policy": "fresh", "cache_dir": str(expected_cache), "pull_source_image": "0",
        "source_image_tag": IMAGE_TAG, "source_image_repository": "neural-download/vllm-openai-xpu",
        "expected_image_id": IMAGE_ID, "tag_image_id": IMAGE_ID, "resolved_image_id": IMAGE_ID,
        "registry_digest": IMAGE_ID, "source_identity_path": "/opt/neural-download/source-identity.json",
        "expected_source_identity_sha256": SOURCE_IDENTITY_SHA256, "vllm_xpu_graph": "1",
        "require_graph_capture": "1", "pythonhashseed": "unset", "natural_eos": "0",
        "return_token_ids": "1", "quality": "1", "quality_require_baseline": "1",
        "quality_baseline_json": str(BASELINE), "quality_baseline_sha256": DEPENDENCIES[BASELINE],
        "prompt_ids": "all", "extra_vllm_args_json": _expected_extra(),
    }
    mismatches = {key: {"expected": item, "observed": identity.get(key)} for key, item in expected.items() if identity.get(key) != item}
    if mismatches:
        raise CampaignError(f"exact TP2 run identity mismatch: {mismatches}")
    if (output / "image-id.txt").read_text(encoding="utf-8").strip() != IMAGE_ID:
        raise CampaignError("run image ID mismatch")
    source = load_json(output / "source-identity.json")
    if sha256_file(output / "source-identity.json") != SOURCE_IDENTITY_SHA256 or (source.get("vllm") or {}).get("head") != VLLM_HEAD or (source.get("kernel") or {}).get("head") != KERNEL_HEAD:
        raise CampaignError("embedded source identity mismatch")
    expected_args = [
        MODEL, "--host", "0.0.0.0", "--port", "8000", "--trust-remote-code",
        "--served-model-name", "qwen38-rolling-nightly-strict", "--tensor-parallel-size", "2",
        "--max-model-len", str(MAX_MODEL_LEN), "--max-num-seqs", "1", "--max-num-batched-tokens", "1024",
        "--gpu-memory-utilization", GPU_MEMORY_UTILIZATION, "--dtype", "float16", "--reasoning-parser", "qwen3",
        "--default-chat-template-kwargs", '{"enable_thinking": false}', "--enable-prompt-tokens-details",
        "--no-enable-prefix-caching", "--pipeline-parallel-size", "1", "--data-parallel-size", "1",
        "--enable-chunked-prefill", "--async-scheduling", "--compilation-config",
        '{"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2}',
    ]
    if (output / "server-args.txt").read_text(encoding="utf-8").splitlines() != expected_args:
        raise CampaignError("TP2 server argv differs from preregistration")
    startup = (output / "server-startup.log").read_text(encoding="utf-8", errors="replace")
    rank_rows = {int(match.group(1)) for match in re.finditer(r"world_size=2 rank=([01]) local_rank=\1", startup)}
    if rank_rows != {0, 1} or "world_size=2, local_world_size=2" not in startup:
        raise CampaignError("both TP workers were not proven in startup log")
    recorded = {}
    for line in (output / "input-files.sha256").read_text(encoding="utf-8").splitlines():
        digest, separator, path = line.partition("  ")
        if not separator:
            raise CampaignError("invalid input hash line")
        recorded[path] = digest
    expected_inputs = {
        str(MODEL_MANIFEST): DEPENDENCIES[MODEL_MANIFEST], str(FIXTURE): FIXTURE_SHA256,
        str(SELF): sha256_file(SELF), str(QUALITY_HELPER): DEPENDENCIES[QUALITY_HELPER],
        str(MODEL_VERIFIER): DEPENDENCIES[MODEL_VERIFIER], str(RUNNER): DEPENDENCIES[RUNNER],
    }
    if recorded != expected_inputs:
        raise CampaignError("strict runner input manifest differs from TP2 frozen inputs")
    return {"passed": True, "image_id": IMAGE_ID, "vllm_head": VLLM_HEAD, "xpu_kernel_head": KERNEL_HEAD, "model_revision": MODEL_REVISION, "tp": 2, "gpus": [0, 1], "worker_ranks": [0, 1], "mtp_depth": 0, "kv_cache_dtype": "float16", "graph_mode": "FULL_AND_PIECEWISE", "max_model_len": MAX_MODEL_LEN}


def execute(attempt: int, acknowledgement: str) -> int:
    expected_ack = f"RUN {CAMPAIGN_ID} {STAGE_ID} r{attempt}"
    if acknowledgement != expected_ack:
        raise CampaignError(f"exact acknowledgement required: {expected_ack}")
    dependencies = verify_dependencies()
    run = layout(attempt)
    env = stage_environment()
    args = [str(RUNNER), "0", "f16", str(MAX_MODEL_LEN), GPUS, str(run.port), str(run.output), str(FIXTURE), str(run.cache)]
    runner_rc, cleanup_passed = 125, False
    with tp2_campaign_locks():
        launch_head = COMMON.git_clean_pushed_main()
        BASE.verify_local_image_available()
        BASE.ensure_idle(run)
        runner_rc = subprocess.run(args, cwd=REPO, env=env, check=False).returncode
        try:
            COMMON.ensure_post_cleanup(run.port)
            cleanup_passed = True
        except CampaignError:
            cleanup_passed = False
    if not run.output.is_dir():
        raise CampaignError(f"strict runner did not create output: {run.output}")
    state, gates = BASE.evaluate(run.output, runner_rc, launch_head=launch_head, expected_cache=run.cache)
    gates["post_cleanup_passed"] = cleanup_passed
    if not cleanup_passed:
        state = "quarantined"
    try:
        git_state = COMMON.git_post_run_snapshot(launch_head)
    except CampaignError as exc:
        git_state = {"launch_head": launch_head, "local_lab_unchanged": False, "post_run_check_error": str(exc), "remote_movement_is_non_gating_after_launch": True}
    gates["local_lab_unchanged"] = git_state.get("local_lab_unchanged") is True
    if not gates["local_lab_unchanged"]:
        state = "quarantined"
    receipt = {
        "schema": "neural.download.qwen38-tp2-exact-depth-quality-stage-receipt.v1",
        "campaign_id": CAMPAIGN_ID, "stage_id": STAGE_ID, "attempt": attempt, "state": state,
        "terminal": True, "receipt_complete": True, "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "output": str(run.output), "cache": str(run.cache), "port": run.port, "lab_git_head": launch_head,
        "git_state": git_state, "gates": gates, "evidence_sha256": BASE.evidence_hashes(run.output),
        "frozen_dependency_sha256": dependencies, "launcher_sha256_at_launch": sha256_file(SELF),
        "context_semantics": {"measured_nonzero_depths": (gates.get("exact_depth_battery", {}).get("passed_depths") or []), "depth_zero_state": "missing", "configured_capacity_is_not_active_context": True, "quality_workloads_fill_no_exact_context_cell": True},
        "authority": {"nonzero_exact_context_cells": 6 if state == "passed" else 0, "depth_zero_cells": 0, "other_cells": 0, "protected_or_headline_replacement": False, "localmaxxing_submission": False},
        "protected_speed_evidence": {"manifest_sha256": DEPENDENCIES[PROTECTED_MANIFEST], "canonical_values_sha256": PROTECTED_VALUES_SHA256, "identity_parent_sha256": DEPENDENCIES[PARENT], "historical_values_are_immutable": True, "speed_floor": None, "this_profile_replaces_no_historical_result": True},
    }
    destination = BASE.atomic_receipt(run.output, receipt)
    print(json.dumps({"campaign_id": CAMPAIGN_ID, "stage": STAGE_ID, "attempt": attempt, "state": state, "terminal": True, "receipt": str(destination)}, sort_keys=True))
    return 0 if state == "passed" else 20


def plan_payload(attempt: int) -> dict[str, Any]:
    run = layout(attempt)
    return {"campaign_id": CAMPAIGN_ID, "stage_id": STAGE_ID, "attempt": attempt, "state": "preregistered-not-launched", "default_is_inert": True, "gpu_actions": 0, "server_count": 1, "tp": 2, "gpus": [0, 1], "depths": list(DEPTHS), "depth_zero_state": "missing", "configured_capacity_is_not_active_context": True, "output": str(run.output), "cache": str(run.cache), "port": run.port, "ack": f"RUN {CAMPAIGN_ID} {STAGE_ID} r{attempt}", "speed_floor": None, "nonzero_cells_if_all_gates_pass": 6, "historical_values_are_immutable": True}


# Rebind the passed TP1 exact-depth implementation to this sealed TP2 identity.
for name, item in {
    "SELF": SELF, "MANIFEST": MANIFEST, "NOTE": NOTE, "CAMPAIGN_ID": CAMPAIGN_ID,
    "STAGE_ID": STAGE_ID, "ROOT_R1": ROOT_R1, "CACHE_R1": CACHE_R1, "PORT_R1": PORT_R1,
    "DEPTHS": DEPTHS, "MAX_MODEL_LEN": MAX_MODEL_LEN, "BASELINE": BASELINE,
    "DEPENDENCIES": DEPENDENCIES, "layout": layout, "verify_dependencies": verify_dependencies,
    "stage_environment": stage_environment, "verify_exact_run_identity": verify_exact_run_identity,
    "execute": execute, "plan_payload": plan_payload,
}.items():
    setattr(BASE, name, item)


def main(argv: Iterable[str] | None = None) -> int:
    return BASE.main(None if argv is None else list(argv))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CampaignError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
