#!/usr/bin/env python3
"""Fail-closed TP1 target-only aggregate-decode ladder for Qwen3.8 27B."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
SELF = Path(__file__).resolve()
MANIFEST = LANE / "data/2026-08-25-qwen38-b2dd9ce73d-tp1-target-concurrency-r1.json"
NOTE = LANE / "notes/2026-08-25-qwen38-b2dd9ce73d-tp1-target-concurrency-preregistration.md"
HARNESS = REPO / "experiments/ornith-15-b70/scripts/vllm-persistent-decode-sweep.py"
HARNESS_TEST = REPO / "experiments/ornith-15-b70/scripts/test_vllm_persistent_decode_sweep.py"
LAUNCHER_TEST = LANE / "scripts/test_qwen38_b2dd_tp1_target_concurrency.py"
MODEL_MANIFEST = REPO / "repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
MODEL_VERIFIER = REPO / "repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
BUILD_RECORD = LANE / "data/2026-08-24-qwen38-b2dd9ce73d-absolute-current-main-build.json"
COMMON_PATH = LANE / "scripts/run-20260825-qwen38-tp1-parent-sentinel-stage.py"

CAMPAIGN_ID = "qwen38-b2dd9ce73d-tp1-target-concurrency-20260825-r1"
STAGE_ID = "c1-eager-target-ladder"
MODEL = Path("/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan")
IMAGE_TAG = "neural-download/vllm-openai-xpu:vllm-b2dd9ce73d-kernel-1e90ffa672-official"
IMAGE_ID = "sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296"
SOURCE_IDENTITY_SHA256 = "2a0ee74968dd68ba15b31eeef3e404807d125e6e52a0e96d25e8b955bd4ae0a0"
ROOT_R1 = Path(
    "/home/steve/qwen38-current-main-runs/"
    "tp1-target-concurrency-b2dd9ce73d-20260825-r1/01-eager-target-ladder"
)
CACHE_R1 = Path(
    "/home/steve/qwen38-current-main-runs/"
    "tp1-target-concurrency-cache-b2dd9ce73d-20260825-r1/01-eager-target-ladder"
)
CONTAINER_R1 = "qwen38-b2dd-tp1-concurrency-r1"
BATCH_SIZES = (1, 2, 4, 8, 16, 32, 64)


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


COMMON = _load_module("qwen38_concurrency_common", COMMON_PATH)
CampaignError = COMMON.CampaignError

DEPENDENCIES = {
    MANIFEST: "bc838d8f7f889bcde7e71e3791d3817c6089128185172de53643f4ac6560967e",
    NOTE: "b20e151f58869bfb15ac7af4e52191473561c94471a5c63aa8992a0d9882a25d",
    HARNESS: "bf63bb5a1f636e9d6268885b112e8c67ca9de379414a764c1bce4d8a21c55849",
    HARNESS_TEST: "d430c7edcebe9d72f1dadd0488c4dacacb4c8f23c70b76fd6ccd46d72a487c9b",
    LAUNCHER_TEST: "fcde87fff6bfe792e790ef2f7a16218aabde89e891e9babc2dc04aa3bd0f348a",
    MODEL_MANIFEST: "731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8",
    MODEL_VERIFIER: "5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9",
    BUILD_RECORD: "d56dc84c1137d741042b2e295c6b1f6a40bf28a3c56e0c52761dd725e3a5caa0",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise CampaignError(f"refusing to overwrite {path}")
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def layout(attempt: int) -> tuple[Path, Path, str]:
    if attempt < 1 or attempt > 99:
        raise CampaignError("attempt must be between 1 and 99")
    suffix = f"r{attempt}"
    output = Path(str(ROOT_R1).replace("-r1/", f"-{suffix}/", 1))
    cache = Path(str(CACHE_R1).replace("-r1/", f"-{suffix}/", 1))
    container = CONTAINER_R1.replace("-r1", f"-{suffix}")
    return output, cache, container


def verify_dependencies() -> dict[str, str]:
    observed: dict[str, str] = {}
    for path, expected in DEPENDENCIES.items():
        if not path.is_file():
            raise CampaignError(f"missing frozen dependency: {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise CampaignError(f"frozen dependency changed: {path} ({actual})")
        observed[str(path.relative_to(REPO))] = actual

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    identity = manifest.get("run_identity") or {}
    contract = manifest.get("measurement_contract") or {}
    execution = manifest.get("execution") or {}
    if not (
        manifest.get("state") == "preregistered-not-launched"
        and manifest.get("campaign_id") == CAMPAIGN_ID
        and identity.get("image_tag") == IMAGE_TAG
        and identity.get("image_id") == IMAGE_ID
        and identity.get("source_identity_sha256") == SOURCE_IDENTITY_SHA256
        and identity.get("tensor_parallel_size") == 1
        and identity.get("gpu_affinity") == "0"
        and identity.get("mtp_depth") == 0
        and identity.get("graph_mode") == "off"
        and identity.get("resolved_kv_precision") == "float16"
        and tuple(contract.get("batch_sizes") or ()) == BATCH_SIZES
        and contract.get("input_tokens_per_request") == 128
        and contract.get("output_tokens_per_request") == 512
        and contract.get("repeats") == 2
        and contract.get("sequential_oracle_for_every_request") is True
        and contract.get("record_complete_output_token_ids") is True
        and execution.get("measuring_host_required") is True
        and execution.get("two_b70_15gib_host_full_model_forbidden") is True
    ):
        raise CampaignError("campaign manifest invariant failed")

    build = json.loads(BUILD_RECORD.read_text(encoding="utf-8"))
    both = (build.get("images") or {}).get("both_current_zero_overlay") or {}
    if not (
        both.get("tag") == IMAGE_TAG
        and both.get("image_id") == IMAGE_ID
        and both.get("static_preflight_passed") is True
    ):
        raise CampaignError("build record no longer binds the exact image")
    return observed


def verify_measuring_host() -> dict[str, Any]:
    discovery = COMMON.command(
        ["env", "-u", "ONEAPI_DEVICE_SELECTOR", "-u", "ZE_AFFINITY_MASK", "xpu-smi", "discovery", "-j"]
    )
    payload = COMMON.require_ok(discovery, "xpu-smi discovery")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CampaignError("xpu-smi discovery returned invalid JSON") from exc
    devices = value.get("device_list") or []
    b70s = [item for item in devices if "Arc(TM) Pro B70" in item.get("device_name", "")]
    if len(b70s) != 4:
        raise CampaignError(
            f"this campaign requires the four-B70 measuring host, found {len(b70s)}"
        )
    available_kib = None
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            available_kib = int(line.split()[1])
            break
    if available_kib is None or available_kib < 64 * 1024 * 1024:
        raise CampaignError("at least 64 GiB MemAvailable is required before launch")
    return {"xpu_smi": value, "mem_available_kib": available_kib}


def verify_image() -> None:
    result = COMMON.docker_command(["image", "inspect", "--format", "{{.Id}}", IMAGE_TAG])
    observed = COMMON.require_ok(result, "exact image inspection")
    if observed != IMAGE_ID:
        raise CampaignError(f"image tag resolves to {observed}, expected {IMAGE_ID}")


def ensure_idle(output: Path, cache: Path, container: str) -> None:
    if output.exists() or cache.exists():
        raise CampaignError(f"fresh output/cache already exists: {output} or {cache}")
    for label, path in (("output", output), ("cache", cache)):
        ancestor = COMMON.nearest_existing(path.parent)
        fstype = COMMON.require_ok(
            COMMON.command(["findmnt", "-n", "-o", "FSTYPE", "-T", str(ancestor)]),
            f"{label} filesystem",
        )
        if fstype != "ext4":
            raise CampaignError(f"{label} root must be ext4, got {fstype}")
    containers = COMMON.require_ok(COMMON.docker_command(["ps", "-q"]), "Docker scan")
    if containers:
        raise CampaignError("a Docker container is already running")
    existing = COMMON.docker_command(["ps", "-a", "--filter", f"name=^{container}$", "-q"])
    if existing.returncode != 0 or existing.stdout.strip():
        raise CampaignError(f"container name is unavailable: {container}")
    processes = COMMON.command(["pgrep", "-af", r"[E]ngineCore|[v]llm serve|[l]lama-server"])
    if processes.returncode not in (0, 1):
        raise CampaignError("model-process scan failed")
    if processes.returncode == 0 and processes.stdout.strip():
        raise CampaignError("a model process is already running")
    if COMMON.render_users():
        raise CampaignError("a process already owns a render node")


def docker_args(output: Path, cache: Path, container: str) -> list[str]:
    return [
        "run",
        "--rm",
        "--name",
        container,
        "--network=none",
        "--device",
        "/dev/dri",
        "--group-add",
        "44",
        "--group-add",
        "992",
        "--ipc=host",
        "--shm-size",
        "16g",
        "--ulimit",
        "memlock=-1:-1",
        "-v",
        "/dev/dri/by-path:/dev/dri/by-path:ro",
        "-v",
        f"{MODEL}:{MODEL}:ro",
        "-v",
        f"{HARNESS}:/opt/neural-download/vllm-persistent-decode-sweep.py:ro",
        "-v",
        f"{output}:/out",
        "-v",
        f"{cache}:/cache",
        "-e",
        "CCL_ZE_IPC_EXCHANGE=sockets",
        "-e",
        "ONEAPI_DEVICE_SELECTOR=level_zero:0",
        "-e",
        "ZE_AFFINITY_MASK=0",
        "-e",
        "PYTHONHASHSEED=0",
        "-e",
        "VLLM_NO_USAGE_STATS=1",
        "-e",
        "VLLM_XPU_ENABLE_XPU_GRAPH=0",
        "-e",
        "VLLM_CACHE_ROOT=/cache/vllm",
        "-e",
        "TORCHINDUCTOR_CACHE_DIR=/cache/torchinductor",
        "-e",
        "TRITON_CACHE_DIR=/cache/triton",
        "-e",
        "XDG_CACHE_HOME=/cache/xdg",
        "--entrypoint",
        "/usr/bin/timeout",
        IMAGE_ID,
        "10800",
        "/opt/venv/bin/python",
        "/opt/neural-download/vllm-persistent-decode-sweep.py",
        "--model",
        str(MODEL),
        "--output",
        "/out/sweep.json",
        "--batch-sizes",
        ",".join(map(str, BATCH_SIZES)),
        "--input-tokens",
        "128",
        "--output-tokens",
        "512",
        "--warmup-tokens",
        "16",
        "--repeats",
        "2",
        "--temperature",
        "0",
        "--seed",
        "20260825",
        "--max-model-len",
        "1024",
        "--max-num-seqs",
        "64",
        "--max-num-batched-tokens",
        "8192",
        "--kv-cache-dtype",
        "auto",
        "--gpu-memory-utilization",
        "0.90",
        "--tensor-parallel-size",
        "1",
        "--async-scheduling",
        "--sequential-oracle",
        "--record-token-ids",
        "--quality-smoke",
    ]


def ensure_post_cleanup() -> None:
    containers = COMMON.require_ok(
        COMMON.docker_command(["ps", "-q"]), "post-run Docker scan"
    )
    if containers:
        raise CampaignError("a Docker container remains after the campaign")
    processes = COMMON.command(
        ["pgrep", "-af", r"[E]ngineCore|[v]llm serve|[l]lama-server"]
    )
    if processes.returncode not in (0, 1):
        raise CampaignError("post-run model-process scan failed")
    if processes.returncode == 0 and processes.stdout.strip():
        raise CampaignError("a model process remains after the campaign")
    if COMMON.render_users():
        raise CampaignError("a process still owns a render node after the campaign")


def validate_result(output: Path, docker_rc: int) -> tuple[str, dict[str, Any]]:
    path = output / "sweep.json"
    gates: dict[str, Any] = {"docker_return_code": docker_rc}
    if not path.is_file():
        gates["result"] = {"passed": False, "reason": "sweep.json missing"}
        return "quarantined", gates
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        gates["result"] = {"passed": False, "reason": f"invalid JSON: {exc}"}
        return "quarantined", gates

    config = result.get("config") or {}
    arms = result.get("arms") or []
    oracle = result.get("sequential_oracle") or []
    smoke = result.get("quality_smoke") or []
    expected_pairs = [(batch, repeat) for batch in BATCH_SIZES for repeat in range(2)]
    observed_pairs = [(arm.get("batch_size"), arm.get("repeat")) for arm in arms]
    identity_ok = (
        result.get("schema") == "neural-download-vllm-decode-sweep-v1"
        and result.get("completed") is True
        and config.get("model") == str(MODEL)
        and config.get("batch_sizes") == list(BATCH_SIZES)
        and config.get("input_tokens") == 128
        and config.get("output_tokens") == 512
        and config.get("repeats") == 2
        and config.get("max_model_len") == 1024
        and config.get("max_num_seqs") == 64
        and config.get("max_num_batched_tokens") == 8192
        and config.get("kv_cache_dtype") == "auto"
        and config.get("tensor_parallel_size") == 1
        and config.get("speculative_tokens") == 0
        and config.get("graph") is False
        and config.get("sequential_oracle") is True
        and config.get("record_token_ids") is True
    )
    completeness_ok = (
        observed_pairs == expected_pairs
        and len(oracle) == 64
        and [item.get("request_index") for item in oracle] == list(range(64))
        and len(smoke) == 68
        and all(item.get("literal_match") is True for item in smoke)
    )
    timing_ok = all(
        arm.get("request_metrics_timestamps_valid") is True
        and isinstance(arm.get("aggregate_decode_tok_s"), (int, float))
        and arm.get("aggregate_decode_tok_s") > 0
        and arm.get("generated_output_tokens") == arm.get("batch_size") * 512
        for arm in arms
    )
    sequential = [arm.get("sequential_oracle_comparison") or {} for arm in arms]
    repeat_comparisons = [arm.get("repeat0_comparison") or {} for arm in arms if arm.get("repeat") == 1]
    sequential_exact = bool(sequential) and all(
        item.get("identical_requests") == item.get("requests") for item in sequential
    )
    repeats_exact = len(repeat_comparisons) == len(BATCH_SIZES) and all(
        item.get("identical_requests") == item.get("requests")
        for item in repeat_comparisons
    )
    gates.update(
        {
            "result": {"passed": identity_ok, "completed": result.get("completed")},
            "completeness": {"passed": completeness_ok, "arms": len(arms), "oracle_requests": len(oracle), "quality_rows": len(smoke)},
            "timing": {"passed": timing_ok},
            "sequential_oracle_exact": sequential_exact,
            "repeat_exact": repeats_exact,
            "sequential_oracle_comparisons": sequential,
            "repeat0_comparisons": repeat_comparisons,
            "speed_floor_applied": False,
        }
    )
    if docker_rc != 0 or not (identity_ok and completeness_ok and timing_ok):
        return "quarantined", gates
    if sequential_exact and repeats_exact:
        return "complete-exact", gates
    return "measured-output-variant", gates


def execute(attempt: int, acknowledgement: str) -> int:
    expected_ack = f"RUN {CAMPAIGN_ID} {STAGE_ID} r{attempt}"
    if acknowledgement != expected_ack:
        raise CampaignError(f"exact acknowledgement required: {expected_ack}")
    dependencies = verify_dependencies()
    output, cache, container = layout(attempt)
    docker_rc = 125
    cleanup_passed = False
    with COMMON.campaign_locks():
        launch_head = COMMON.git_clean_pushed_main()
        host_identity = verify_measuring_host()
        verify_image()
        ensure_idle(output, cache, container)
        output.mkdir(parents=True)
        cache.mkdir(parents=True)
        atomic_json(output / "host-identity.json", host_identity)
        model_verify = subprocess.run(
            [
                sys.executable,
                str(MODEL_VERIFIER),
                str(MODEL_MANIFEST),
                str(MODEL),
                "--json",
                str(output / "model-direct-and-ordinary-verify.json"),
            ],
            cwd=REPO,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        (output / "model-verification.log").write_text(
            model_verify.stdout, encoding="utf-8"
        )
        if model_verify.returncode != 0:
            receipt = {
                "schema": "neural.download.qwen38-target-concurrency-stage-receipt.v1",
                "campaign_id": CAMPAIGN_ID,
                "stage_id": STAGE_ID,
                "attempt": attempt,
                "state": "quarantined",
                "terminal": True,
                "reason": "direct-and-ordinary model verification failed",
                "model_verifier_return_code": model_verify.returncode,
                "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
                "frozen_dependency_sha256": dependencies,
                "launcher_sha256_at_launch": sha256_file(SELF),
            }
            atomic_json(output / "stage-receipt.json", receipt)
            return 20
        args = docker_args(output, cache, container)
        (output / "docker-args.json").write_text(
            json.dumps(args, indent=2) + "\n", encoding="utf-8"
        )
        result = COMMON.docker_command(args)
        docker_rc = result.returncode
        (output / "sweep.stdout.log").write_text(result.stdout, encoding="utf-8")
        (output / "sweep.stderr.log").write_text(result.stderr, encoding="utf-8")
        try:
            ensure_post_cleanup()
            cleanup_passed = True
        except CampaignError:
            cleanup_passed = False

    state, gates = validate_result(output, docker_rc)
    gates["post_cleanup_passed"] = cleanup_passed
    if not cleanup_passed:
        state = "quarantined"
    try:
        git_state = COMMON.git_post_run_snapshot(launch_head)
    except CampaignError as exc:
        git_state = {"local_lab_unchanged": False, "error": str(exc)}
    gates["local_lab_unchanged"] = git_state.get("local_lab_unchanged") is True
    if not gates["local_lab_unchanged"]:
        state = "quarantined"
    evidence = {
        path.name: sha256_file(path)
        for path in output.iterdir()
        if path.is_file() and path.name != "stage-receipt.json"
    }
    receipt = {
        "schema": "neural.download.qwen38-target-concurrency-stage-receipt.v1",
        "campaign_id": CAMPAIGN_ID,
        "stage_id": STAGE_ID,
        "attempt": attempt,
        "state": state,
        "terminal": True,
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "output": str(output),
        "cache": str(cache),
        "lab_git_head": launch_head,
        "git_state": git_state,
        "gates": gates,
        "evidence_sha256": evidence,
        "frozen_dependency_sha256": dependencies,
        "launcher_sha256_at_launch": sha256_file(SELF),
        "interpretation": {
            "direct_measurement_only": True,
            "no_interpolation_or_extrapolation": True,
            "raw_engine_sequences_are_not_http_users": True,
            "speed_floor": None,
            "historical_results_replaced": False,
        },
        "next_action": (
            "Profile the measured saturation region and preregister a separate graph treatment"
            if state in {"complete-exact", "measured-output-variant"}
            else "Preserve this terminal attempt; investigate the failed gate before any new rN"
        ),
    }
    atomic_json(output / "stage-receipt.json", receipt)
    print(json.dumps({"campaign_id": CAMPAIGN_ID, "state": state, "receipt": str(output / "stage-receipt.json")}, sort_keys=True))
    return 0 if state in {"complete-exact", "measured-output-variant"} else 20


def plan(attempt: int) -> dict[str, Any]:
    output, cache, container = layout(attempt)
    return {
        "campaign_id": CAMPAIGN_ID,
        "stage_id": STAGE_ID,
        "attempt": attempt,
        "state": "preregistered-not-launched",
        "launch_performed": False,
        "output": str(output),
        "cache": str(cache),
        "container": container,
        "batch_sizes": list(BATCH_SIZES),
        "ack": f"RUN {CAMPAIGN_ID} {STAGE_ID} r{attempt}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--plan", action="store_true")
    actions.add_argument("--execute", action="store_true")
    parser.add_argument("--stage", choices=(STAGE_ID,))
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--ack", default="")
    args = parser.parse_args()
    if not (args.check or args.plan or args.execute):
        parser.print_help()
        return 0
    if args.check:
        print(json.dumps({"status": "PASS", "launch_performed": False, "dependencies": verify_dependencies()}, sort_keys=True))
        return 0
    if args.plan:
        print(json.dumps(plan(args.attempt), indent=2, sort_keys=True))
        return 0
    if args.stage != STAGE_ID:
        parser.error(f"--execute requires --stage {STAGE_ID}")
    return execute(args.attempt, args.ack)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CampaignError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
