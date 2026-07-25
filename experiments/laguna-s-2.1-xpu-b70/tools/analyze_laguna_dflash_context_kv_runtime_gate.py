#!/usr/bin/env python3
"""Fail-closed analysis for the non-timing TP4 context-KV runtime gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import analyze_laguna_m8_actual_offline_gate as raw_gate
from run_laguna_dflash_context_kv_runtime_arm import (
    DRAFT_MODEL,
    DRAFT_REVISION,
    EVIDENCE_ARM,
    MAX_TOKENS,
    MODEL_MANIFEST_SHA256,
    PROMPT,
    PROMPT_ID,
    RECORDED_ENVIRONMENT,
    RPC_DIRS,
    SCHEMA as DRIVER_SCHEMA,
    SEED,
    TARGET_MODEL,
    TARGET_REVISION,
    VLLM_COMMIT,
    digest_json,
    file_manifest,
    frozen_environment,
)


SCHEMA = "laguna-dflash-context-kv-runtime-analysis-v1"
KERNEL_COMMIT = "4772f727590c51b72add79350b913d098cf67872"
TEACHER = Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/"
    "bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json"
)
TEACHER_SHA256 = "d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1"
SUITE = Path(
    "/home/steve/llm-optimizations/"
    "experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"
)
SUITE_SHA256 = "9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638"
CANDIDATE_SOURCE = Path(
    "/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725/"
    "vllm/model_executor/models/laguna_dflash.py"
)
CANDIDATE_SOURCE_SHA256 = (
    "9569f9329fb50361623c53e6d3b1b10dee7ec8a0214142ded8cf88c5ec4eabd4"
)
RAW_ANALYZER_SHA256 = (
    "43526f74042d221b75895dc4760bf6664c32a51b247d317c13bcc941ce3a46fa"
)
RAW_ANALYZER = Path(raw_gate.__file__).resolve()
HEX = set("0123456789abcdef")
AUTHORIZATION_ROOT = Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations"
)
EXPECTED_DEVICES = [
    {
        "device_function_type": "physical",
        "device_id": 0,
        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
        "device_type": "GPU",
        "drm_device": "/dev/dri/card3",
        "pci_bdf_address": "0000:23:00.0",
        "pci_device_id": "0xe223",
        "uuid": "00000000-0000-0023-0000-0000e2238086",
        "vendor_name": "Intel(R) Corporation",
    },
    {
        "device_function_type": "physical",
        "device_id": 1,
        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
        "device_type": "GPU",
        "drm_device": "/dev/dri/card4",
        "pci_bdf_address": "0000:27:00.0",
        "pci_device_id": "0xe223",
        "uuid": "00000000-0000-0027-0000-0000e2238086",
        "vendor_name": "Intel(R) Corporation",
    },
    {
        "device_function_type": "physical",
        "device_id": 2,
        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
        "device_type": "GPU",
        "drm_device": "/dev/dri/card0",
        "pci_bdf_address": "0000:43:00.0",
        "pci_device_id": "0xe223",
        "uuid": "00000000-0000-0043-0000-0000e2238086",
        "vendor_name": "Intel(R) Corporation",
    },
    {
        "device_function_type": "physical",
        "device_id": 3,
        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
        "device_type": "GPU",
        "drm_device": "/dev/dri/card2",
        "pci_bdf_address": "0000:47:00.0",
        "pci_device_id": "0xe223",
        "uuid": "00000000-0000-0047-0000-0000e2238086",
        "vendor_name": "Intel(R) Corporation",
    },
]


def die(message: str) -> None:
    raise ValueError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        die(f"cannot stat {path}: {exc}")
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        die(f"{path}: expected regular non-symlink JSON")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot load {path}: {exc}")
    if not isinstance(value, dict):
        die(f"{path}: expected JSON object")
    return value


def validate_private_nvme_dir(path: Path) -> None:
    try:
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
        nvme = Path("/mnt/fast-ai").resolve(strict=True)
    except OSError as exc:
        die(f"cannot inspect private NVMe directory {path}: {exc}")
    if (
        path != resolved
        or path.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != os.getuid()
        or not resolved.is_relative_to(nvme)
        or resolved == nvme
        or metadata.st_dev != nvme.stat().st_dev
    ):
        die(f"{path}: private NVMe directory identity drift")


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                die("short analysis write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def reject_timing_fields(value: Any, context: str = "root") -> None:
    forbidden = ("elapsed", "latency", "throughput", "tok_s", "timestamp", "ttft")
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in forbidden):
                die(f"{context}: forbidden timing field {key!r}")
            reject_timing_fields(item, f"{context}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_timing_fields(item, f"{context}[{index}]")


def valid_sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in HEX for character in value)
    )


def git_blob_sha(repo: Path, commit: str, path: Path) -> str:
    relative = path.resolve().relative_to(repo.resolve())
    content = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{commit}:{relative}"]
    )
    return hashlib.sha256(content).hexdigest()


def validate_idle(path: Path) -> None:
    value = load_json(path)
    idle = value.get("idle")
    if (
        value.get("format")
        != "laguna-m8-gather-sharded-operational-preflight-v2"
        or value.get("status") != "passed"
        or not isinstance(idle, dict)
        or idle.get("accepted_mode") != "self_observer_rows"
        or idle.get("device_ids") != [0, 1, 2, 3]
        or idle.get("row_count") != 4
        or value.get("xpu_smi", {}).get("resolved_path") != "/usr/bin/xpu-smi"
        or value.get("xpu_smi", {}).get("sha256")
        != "2b5b128edf28b38da8637413fe8bfe3a4a40e8113210ba9ddaed945bd56d826e"
    ):
        die(f"{path}: strict four-card idle proof failed")


def validate_cleanup(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        die(f"cannot read cleanup status {path}: {exc}")
    if lines != ["status=0", "worker_status=0", "idle_status=0"]:
        die(f"{path}: cleanup status drift")


def validate_empty_worker_report(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        die(f"cannot stat worker report {path}: {exc}")
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_size != 0
    ):
        die(f"{path}: surviving worker evidence")


def validate_evidence_manifest(root: Path) -> str:
    manifest_path = root / "evidence-manifest.sha256"
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        die(f"cannot read evidence manifest: {exc}")
    entries: dict[str, str] = {}
    for line in lines:
        try:
            digest, path_text = line.split("  ", 1)
        except ValueError as exc:
            raise ValueError("malformed evidence manifest line") from exc
        path = Path(path_text)
        if (
            not valid_sha(digest)
            or not path.is_absolute()
            or not path.resolve(strict=True).is_relative_to(root)
            or path.is_symlink()
            or path_text in entries
        ):
            die("invalid evidence manifest entry")
        entries[path_text] = digest
        if sha256_file(path) != digest:
            die(f"evidence manifest digest drift: {path}")

    expected_paths = {
        root / "identity.txt",
        root / "consumption-creator.stdout",
        root / "device-discovery.json",
        root / "pre-idle.json",
        root / "final-idle.json",
        root / "pre-workers.txt",
        root / "final-workers.txt",
    }
    for treatment in ("control", "candidate"):
        arm_root = root / treatment
        expected_paths.update(
            {
                arm_root / "driver.json",
                arm_root / "driver.stdout",
                arm_root / "driver.stderr",
                arm_root / "pre-idle.json",
                arm_root / "post-idle.json",
                arm_root / "cleanup-status.txt",
                arm_root / "pre-workers.txt",
                arm_root / "post-workers.txt",
            }
        )
        expected_paths.update(
            path
            for evidence_root in (
                arm_root / "evidence",
                arm_root / "dflash-lifecycle",
            )
            for path in evidence_root.rglob("*")
            if path.is_file()
        )
    if set(entries) != {str(path) for path in expected_paths}:
        missing = sorted(
            str(path) for path in expected_paths - {Path(p) for p in entries}
        )
        extra = sorted(
            str(Path(p))
            for p in set(entries) - {str(path) for path in expected_paths}
        )
        die(f"evidence manifest file-set drift: missing={missing} extra={extra}")
    return sha256_file(manifest_path)


def validate_campaign_identity(root: Path) -> dict[str, Any]:
    identity_path = root / "identity.txt"
    try:
        lines = identity_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        die(f"cannot read campaign identity: {exc}")
    if len(lines) < 16:
        die("campaign identity is incomplete")
    fixed = {
        "schema": "laguna-dflash-context-kv-runtime-campaign-v1",
        "purpose": (
            "two-arm TP4 integration exactness; timing=false; "
            "benchmark=false; submission=false"
        ),
        "vllm": VLLM_COMMIT,
        "kernels": KERNEL_COMMIT,
        "order": "control,candidate",
        "sole_treatment": "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE",
        "calls_per_arm": "1",
        "max_tokens": str(MAX_TOKENS),
        "warmups": "0",
        "retries": "0",
    }
    parsed: dict[str, str] = {}
    sha_start = None
    for index, line in enumerate(lines):
        if len(line) >= 66 and line[64:66] == "  ":
            sha_start = index
            break
        if "=" not in line:
            die("campaign identity key/value line drift")
        key, value = line.split("=", 1)
        if key in parsed:
            die("campaign identity duplicate key")
        parsed[key] = value
    if sha_start is None or set(parsed) != set(fixed) | {"main"}:
        die("campaign identity fields drift")
    if any(parsed[key] != value for key, value in fixed.items()):
        die("campaign identity value drift")
    main_commit = parsed["main"]
    if not (
        len(main_commit) == 40
        and all(character in HEX for character in main_commit)
    ):
        die("campaign main commit is invalid")

    repo = Path("/home/steve/llm-optimizations")
    vllm_repo = Path(
        "/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725"
    )
    if (
        subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
        ).strip()
        != main_commit
        or subprocess.check_output(
            ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"],
            text=True,
        )
        != ""
        or subprocess.check_output(
            ["git", "-C", str(vllm_repo), "rev-parse", "HEAD"], text=True
        ).strip()
        != VLLM_COMMIT
        or subprocess.check_output(
            [
                "git",
                "-C",
                str(vllm_repo),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            text=True,
        )
        != ""
    ):
        die("live committed source identity drift")

    expected_paths = [
        Path(
            "/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/"
            f"tools/{name}"
        )
        for name in (
            "run_laguna_dflash_context_kv_runtime_gate.sh",
            "run_laguna_dflash_context_kv_runtime_arm.py",
            "analyze_laguna_dflash_context_kv_runtime_gate.py",
            "create_laguna_dflash_context_kv_runtime_consumption.py",
            "analyze_laguna_m8_actual_offline_gate.py",
            "capture_laguna_m8_idle_snapshot.py",
            "laguna_nvme_paths.sh",
        )
    ] + [SUITE, TEACHER, CANDIDATE_SOURCE]
    expected_paths.append(
        Path(
            "/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/"
            "notes/2026-07-25-dflash-context-kv-tp4-runtime-preregistration.md"
        )
    )
    digest_lines = lines[sha_start:]
    digests: dict[Path, str] = {}
    for line in digest_lines:
        try:
            digest, path_text = line.split("  ", 1)
        except ValueError as exc:
            raise ValueError("campaign identity digest line drift") from exc
        path = Path(path_text)
        if not valid_sha(digest) or path in digests:
            die("campaign identity digest drift")
        digests[path] = digest
    if set(digests) != set(expected_paths):
        die("campaign identity path set drift")
    for path, digest in digests.items():
        if sha256_file(path) != digest:
            die(f"campaign live file digest drift: {path}")
        if path.is_relative_to(repo) and git_blob_sha(repo, main_commit, path) != digest:
            die(f"campaign main-commit blob drift: {path}")
        if path == CANDIDATE_SOURCE and (
            git_blob_sha(vllm_repo, VLLM_COMMIT, path) != digest
        ):
            die("campaign candidate source blob drift")

    packet_sha256 = sha256_file(identity_path)
    marker = AUTHORIZATION_ROOT / (
        "laguna-dflash-context-kv-runtime-"
        f"{main_commit}-{packet_sha256}.consumed.json"
    )
    marker_value = load_json(marker)
    if (
        marker.is_symlink()
        or stat.S_IMODE(marker.lstat().st_mode) != 0o400
        or marker_value
        != {
            "schema": "laguna-dflash-context-kv-runtime-consumption-v1",
            "main_commit": main_commit,
            "vllm_commit": VLLM_COMMIT,
            "kernel_commit": KERNEL_COMMIT,
            "run_root": str(root),
            "packet_sha256": packet_sha256,
            "authority": "one_non_timing_tp4_selector_off_on_exactness_gate",
        }
        or (root / "consumption-creator.stdout").read_text(encoding="utf-8")
        != f"{marker}\n"
    ):
        die("external packet consumption binding drift")
    return {
        "main_commit": main_commit,
        "packet_sha256": packet_sha256,
        "marker": str(marker),
        "identity_sha256": packet_sha256,
    }


def validate_operational_evidence(root: Path) -> dict[str, Any]:
    discovery = load_json(root / "device-discovery.json")
    if discovery != {"device_list": EXPECTED_DEVICES}:
        die("physical B70 discovery identity drift")
    validate_idle(root / "pre-idle.json")
    validate_idle(root / "final-idle.json")
    validate_empty_worker_report(root / "pre-workers.txt")
    validate_empty_worker_report(root / "final-workers.txt")
    for treatment in ("control", "candidate"):
        validate_idle(root / treatment / "pre-idle.json")
        validate_idle(root / treatment / "post-idle.json")
        validate_cleanup(root / treatment / "cleanup-status.txt")
        validate_empty_worker_report(root / treatment / "pre-workers.txt")
        validate_empty_worker_report(root / treatment / "post-workers.txt")
    return {
        "devices": EXPECTED_DEVICES,
        "idle_snapshots": 6,
        "cleanup_statuses": 2,
        "empty_worker_reports": 6,
    }


def expected_engine_config() -> dict[str, Any]:
    return {
        "model": str(TARGET_MODEL),
        "revision": TARGET_REVISION,
        "tokenizer": str(TARGET_MODEL),
        "tokenizer_revision": TARGET_REVISION,
        "trust_remote_code": True,
        "dtype": "bfloat16",
        "tensor_parallel_size": 4,
        "data_parallel_size": 1,
        "pipeline_parallel_size": 1,
        "distributed_executor_backend": "mp",
        "enable_expert_parallel": True,
        "all2all_backend": "allgather_reducescatter",
        "max_model_len": 8192,
        "max_num_batched_tokens": 8192,
        "max_num_seqs": 1,
        "block_size": 64,
        "kv_cache_dtype": "bfloat16",
        "gpu_memory_utilization": 0.90,
        "enable_prefix_caching": False,
        "async_scheduling": False,
        "generation_config": "vllm",
        "enforce_eager": False,
    }


def expected_compilation_config() -> dict[str, Any]:
    return {
        "mode": "NONE",
        "cudagraph_mode": "PIECEWISE",
        "cudagraph_capture_sizes": [8],
        "max_cudagraph_capture_size": 8,
    }


def expected_speculative_config() -> dict[str, Any]:
    return {
        "method": "dflash",
        "model": str(DRAFT_MODEL),
        "revision": DRAFT_REVISION,
        "num_speculative_tokens": 7,
        "draft_sample_method": "greedy",
        "rejection_sample_method": "standard",
    }


def validate_driver(
    treatment: str, arm_root: Path, driver: dict[str, Any]
) -> dict[str, Any]:
    required = {
        "chat_template_kwargs",
        "compilation_config",
        "draft_model",
        "draft_revision",
        "engine_config",
        "evidence_canonical_sha256",
        "environment",
        "evidence_dir",
        "evidence_file_sha256",
        "finish_reason",
        "ignore_eos",
        "lifecycle_trace_dir",
        "lifecycle_trace_manifest",
        "lifecycle_trace_manifest_sha256",
        "max_tokens",
        "model",
        "model_manifest_sha256",
        "nonbenchmark",
        "num_cached_tokens",
        "offline_only",
        "prompt_id",
        "prompt_sha256",
        "prompt_token_ids",
        "prompt_token_ids_sha256",
        "retry_count",
        "rpc_dir",
        "runtime",
        "schema",
        "seed",
        "selector",
        "single_chat_call",
        "speculative_config",
        "target_revision",
        "text",
        "text_sha256",
        "token_ids",
        "token_ids_sha256",
        "treatment",
        "usage",
        "warmup_calls",
        "worker_identities",
        "worker_identity_calls",
    }
    if set(driver) != required:
        die(f"{treatment}: driver fields drift")
    selector = 1 if treatment == "candidate" else 0
    token_ids = driver["token_ids"]
    prompt_token_ids = driver["prompt_token_ids"]
    text = driver["text"]
    if (
        driver["schema"] != DRIVER_SCHEMA
        or driver["treatment"] != treatment
        or driver["selector"] != selector
        or driver["offline_only"] is not True
        or driver["nonbenchmark"] is not True
        or driver["single_chat_call"] is not True
        or driver["worker_identity_calls"] != 1
        or driver["warmup_calls"] != 0
        or driver["retry_count"] != 0
        or driver["prompt_id"] != PROMPT_ID
        or driver["prompt_sha256"] != hashlib.sha256(PROMPT.encode()).hexdigest()
        or driver["max_tokens"] != MAX_TOKENS
        or driver["seed"] != SEED
        or driver["ignore_eos"] is not True
        or driver["chat_template_kwargs"] != {"enable_thinking": False}
        or driver["model"] != str(TARGET_MODEL)
        or driver["draft_model"] != str(DRAFT_MODEL)
        or driver["target_revision"] != TARGET_REVISION
        or driver["draft_revision"] != DRAFT_REVISION
        or driver["model_manifest_sha256"] != MODEL_MANIFEST_SHA256
        or driver["engine_config"] != expected_engine_config()
        or driver["compilation_config"] != expected_compilation_config()
        or driver["speculative_config"] != expected_speculative_config()
        or driver["num_cached_tokens"] != 0
        or driver["finish_reason"] != "length"
        or not isinstance(token_ids, list)
        or len(token_ids) != MAX_TOKENS
        or not all(isinstance(item, int) and not isinstance(item, bool) for item in token_ids)
        or driver["token_ids_sha256"] != digest_json(token_ids)
        or not isinstance(prompt_token_ids, list)
        or not prompt_token_ids
        or not all(
            isinstance(item, int) and not isinstance(item, bool)
            for item in prompt_token_ids
        )
        or driver["prompt_token_ids_sha256"] != digest_json(prompt_token_ids)
        or not isinstance(text, str)
        or not text
        or driver["text_sha256"] != hashlib.sha256(text.encode()).hexdigest()
        or driver["evidence_dir"] != str(arm_root / "evidence")
        or driver["rpc_dir"] != str(RPC_DIRS[treatment])
        or driver["lifecycle_trace_dir"] != str(arm_root / "dflash-lifecycle")
    ):
        die(f"{treatment}: invalid cold/config/output provenance")
    usage = driver["usage"]
    if usage != {
        "prompt_tokens": len(prompt_token_ids),
        "completion_tokens": MAX_TOKENS,
        "cached_tokens": 0,
    }:
        die(f"{treatment}: usage drift")
    runtime = driver["runtime"]
    if (
        not isinstance(runtime, dict)
        or set(runtime) != {"vllm_commit", "vllm_module", "vllm_root"}
        or runtime["vllm_commit"] != VLLM_COMMIT
        or runtime["vllm_root"]
        != "/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725"
        or not isinstance(runtime["vllm_module"], str)
        or not runtime["vllm_module"].startswith(runtime["vllm_root"] + "/")
    ):
        die(f"{treatment}: runtime identity drift")
    environment = driver["environment"]
    if not isinstance(environment, dict) or set(environment) != set(
        RECORDED_ENVIRONMENT
    ):
        die(f"{treatment}: environment allowlist drift")
    expected_environment = frozen_environment(
        treatment,
        arm_root / "evidence",
        arm_root / "dflash-lifecycle",
        Path(driver["rpc_dir"]),
    )
    if environment != expected_environment:
        die(f"{treatment}: treatment/evidence environment drift")
    identities = driver["worker_identities"]
    expected_identity_fields = {
        "distributed_backend",
        "global_rank",
        "global_world_size",
        "model_class",
        "tp_rank",
        "tp_world_size",
        "xpu_device",
        "xpu_device_name",
    }
    if (
        not isinstance(identities, list)
        or len(identities) != 4
        or any(
            not isinstance(identity, dict)
            or set(identity) != expected_identity_fields
            or identity["global_rank"] != rank
            or identity["global_world_size"] != 4
            or identity["tp_rank"] != rank
            or identity["tp_world_size"] != 4
            or identity["xpu_device"] != rank
            or identity["distributed_backend"] != "xccl"
            or identity["xpu_device_name"] != "Intel(R) Arc(TM) Pro B70 Graphics"
            or identity["model_class"] != "LagunaForCausalLM"
            for rank, identity in enumerate(identities)
        )
    ):
        die(f"{treatment}: TP4/XCCL worker identity drift")
    lifecycle_manifest = driver["lifecycle_trace_manifest"]
    trace_root = arm_root / "dflash-lifecycle"
    if (
        not isinstance(lifecycle_manifest, dict)
        or not lifecycle_manifest
        or lifecycle_manifest != file_manifest(trace_root)
        or driver["lifecycle_trace_manifest_sha256"]
        != digest_json(lifecycle_manifest)
    ):
        die(f"{treatment}: DFlash lifecycle manifest drift")
    reject_timing_fields(driver, treatment)
    return driver


def normalize_treatment(driver: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(driver, sort_keys=True))
    value["treatment"] = "<treatment>"
    value["selector"] = "<selector>"
    value["environment"]["VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE"] = (
        "<selector>"
    )
    value["environment"]["VLLM_XPU_LAGUNA_M8_EVIDENCE_ROOT"] = "<evidence>"
    value["environment"][
        "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_RUNTIME_TRACE_ROOT"
    ] = "<lifecycle>"
    value["environment"]["VLLM_RPC_BASE_PATH"] = "<rpc>"
    value["evidence_dir"] = "<evidence>"
    value["lifecycle_trace_dir"] = "<lifecycle>"
    value["lifecycle_trace_manifest"] = "<lifecycle>"
    value["lifecycle_trace_manifest_sha256"] = "<lifecycle>"
    value["rpc_dir"] = "<rpc>"
    value["runtime"]["vllm_module"] = "<module>"
    value["token_ids"] = "<output>"
    value["token_ids_sha256"] = "<output>"
    value["text"] = "<output>"
    value["text_sha256"] = "<output>"
    return value


def teacher_prefix() -> tuple[list[int], dict[str, Any]]:
    if sha256_file(TEACHER) != TEACHER_SHA256:
        die("canonical q1 teacher hash drift")
    if sha256_file(SUITE) != SUITE_SHA256:
        die("realistic suite hash drift")
    teacher = load_json(TEACHER)
    suite = load_json(SUITE)
    prompts = suite.get("prompts")
    rows = teacher.get("rows")
    if (
        not isinstance(prompts, list)
        or not prompts
        or prompts[0] != {"id": PROMPT_ID, "prompt": PROMPT}
        or not isinstance(rows, list)
        or not rows
    ):
        die("frozen prompt/teacher structure drift")
    row = rows[0]
    tokens = row.get("token_ids") if isinstance(row, dict) else None
    if (
        row.get("prompt_id") != PROMPT_ID
        or row.get("prompt_sha256") != hashlib.sha256(PROMPT.encode()).hexdigest()
        or row.get("cached_tokens") != 0
        or not isinstance(tokens, list)
        or len(tokens) < MAX_TOKENS
        or not all(isinstance(item, int) and not isinstance(item, bool) for item in tokens)
    ):
        die("canonical q1 teacher row drift")
    prefix = tokens[:MAX_TOKENS]
    return prefix, {
        "path": str(TEACHER),
        "sha256": TEACHER_SHA256,
        "prompt_id": PROMPT_ID,
        "prefix_tokens": MAX_TOKENS,
        "prefix_sha256": digest_json(prefix),
    }


def validate_raw(
    treatment: str, arm_root: Path, driver: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, int]]:
    evidence_root = arm_root / "evidence"
    evidence_file = evidence_root / "evidence.json"
    stored = load_json(evidence_file)
    recomputed = raw_gate.aggregate_recorder_root(EVIDENCE_ARM, evidence_root)
    if (
        stored != recomputed
        or driver["evidence_canonical_sha256"] != digest_json(recomputed)
        or driver["evidence_file_sha256"] != sha256_file(evidence_file)
    ):
        die(f"{treatment}: stored raw aggregate differs from recorder files")
    counts = {
        rank: len(events)
        for rank, events in recomputed["rank_events"].items()
    }
    if set(counts) != {"0", "1", "2", "3"} or any(
        count < raw_gate.MIN_EVENTS_PER_RANK for count in counts.values()
    ):
        die(f"{treatment}: incomplete four-rank speculative event stream")
    return recomputed, counts


def validate_trace_signature(
    value: Any,
    *,
    rank: int,
    num_ctx: int,
    kind: str,
) -> dict[str, Any]:
    fields = {
        "data_ptr",
        "device",
        "dtype",
        "nbytes",
        "sha256",
        "shape",
        "storage_offset",
        "stride",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or not isinstance(value["data_ptr"], int)
        or value["data_ptr"] <= 0
        or value["storage_offset"] < 0
        or value["device"] != f"xpu:{rank}"
        or not valid_sha(value["sha256"])
        or not isinstance(value["shape"], list)
        or not isinstance(value["stride"], list)
        or len(value["shape"]) != len(value["stride"])
        or not isinstance(value["nbytes"], int)
        or value["nbytes"] <= 0
    ):
        die(f"rank {rank}: invalid {kind} trace signature")
    if kind == "context_states" and (
        value["dtype"] != "torch.bfloat16"
        or value["shape"] != [num_ctx, 3072]
    ):
        die(f"rank {rank}: context-state trace shape/dtype drift")
    if kind in {"context_positions", "slot_mapping"} and (
        value["dtype"] != "torch.int64" or value["shape"] != [num_ctx]
    ):
        die(f"rank {rank}: {kind} trace shape/dtype drift")
    return value


def validate_lifecycle_trace(
    treatment: str,
    arm_root: Path,
) -> dict[str, Any]:
    trace_root = arm_root / "dflash-lifecycle"
    files = sorted(trace_root.iterdir())
    expected_fields = {
        "context_positions",
        "context_states",
        "event_index",
        "expected_cache_update_count",
        "num_ctx",
        "precompute_returned",
        "projection",
        "rank",
        "schema",
        "selector_enabled",
        "slot_mapping_signatures",
    }
    events_by_rank: dict[int, list[dict[str, Any]]] = {
        rank: [] for rank in range(4)
    }
    for path in files:
        if path.is_symlink() or not path.is_file():
            die(f"{treatment}: lifecycle trace contains a non-regular file")
        event = load_json(path)
        rank = event.get("rank")
        index = event.get("event_index")
        if (
            not isinstance(rank, int)
            or rank not in events_by_rank
            or not isinstance(index, int)
            or index < 0
            or path.name != f"rank{rank}-event{index:05d}.json"
            or set(event) != expected_fields
            or event["schema"] != "laguna-dflash-context-kv-runtime-trace-v1"
            or event["selector_enabled"] is not (treatment == "candidate")
            or event["precompute_returned"] is not True
            or not isinstance(event["num_ctx"], int)
            or not 0 < event["num_ctx"] <= 8
        ):
            die(f"{treatment}: malformed lifecycle event {path.name}")
        num_ctx = event["num_ctx"]
        validate_trace_signature(
            event["context_states"],
            rank=rank,
            num_ctx=num_ctx,
            kind="context_states",
        )
        validate_trace_signature(
            event["context_positions"],
            rank=rank,
            num_ctx=num_ctx,
            kind="context_positions",
        )
        slots = event["slot_mapping_signatures"]
        if (
            not isinstance(slots, list)
            or len(slots) not in {0, 1, 6}
            or event["expected_cache_update_count"] not in {0, 6}
            or (event["expected_cache_update_count"] == 0) != (len(slots) == 0)
        ):
            die(f"{treatment}: expected cache-update mapping witness drift")
        for signature in slots:
            validate_trace_signature(
                signature,
                rank=rank,
                num_ctx=num_ctx,
                kind="slot_mapping",
            )
        projection = event["projection"]
        projection_fields = {
            "branch",
            "capturing",
            "workspace_reused",
            "workspace_signatures",
        }
        if not isinstance(projection, dict) or set(projection) != projection_fields:
            die(f"{treatment}: projection witness fields drift")
        if treatment == "control":
            if projection != {
                "branch": "incumbent",
                "capturing": False,
                "workspace_reused": None,
                "workspace_signatures": None,
            }:
                die("control: workspace branch unexpectedly observed")
        else:
            signatures = projection["workspace_signatures"]
            if (
                projection["branch"] != "workspace"
                or projection["capturing"] is not False
                or not isinstance(projection["workspace_reused"], bool)
                or not isinstance(signatures, list)
                or len(signatures) != 4
            ):
                die("candidate: workspace branch witness drift")
            expected_shapes = [
                [6, num_ctx, 3072],
                [6, num_ctx, 1536],
                [2, 6, num_ctx, 6, 128],
                [6, num_ctx, 6, 128],
            ]
            pointers: set[int] = set()
            for signature, shape in zip(signatures, expected_shapes, strict=True):
                if (
                    not isinstance(signature, dict)
                    or set(signature)
                    != {
                        "data_ptr",
                        "device",
                        "dtype",
                        "shape",
                        "storage_offset",
                        "stride",
                    }
                    or signature["shape"] != shape
                    or signature["dtype"] != "torch.bfloat16"
                    or signature["device"] != f"xpu:{rank}"
                    or not isinstance(signature["data_ptr"], int)
                    or signature["data_ptr"] <= 0
                    or signature["data_ptr"] in pointers
                ):
                    die("candidate: workspace signature drift")
                pointers.add(signature["data_ptr"])
        reject_timing_fields(event, f"{treatment}.rank{rank}.event{index}")
        events_by_rank[rank].append(event)

    counts = {rank: len(events) for rank, events in events_by_rank.items()}
    if not files or len(set(counts.values())) != 1 or any(
        count < 2 for count in counts.values()
    ):
        die(f"{treatment}: lifecycle ranks/counts drift")
    normalized: dict[int, list[dict[str, Any]]] = {}
    reused_precompute: dict[int, int] = {}
    returned_precompute_calls: dict[int, int] = {}
    for rank, events in events_by_rank.items():
        if [event["event_index"] for event in events] != list(range(len(events))):
            die(f"{treatment}: rank {rank} lifecycle event sequence drift")
        workspace_by_width: dict[int, list[dict[str, Any]]] = {}
        normalized[rank] = []
        for event in events:
            width = event["num_ctx"]
            projection = event["projection"]
            normalized[rank].append(
                {
                    "num_ctx": width,
                    "context_states": {
                        key: event["context_states"][key]
                        for key in ("dtype", "nbytes", "sha256", "shape", "stride")
                    },
                    "context_positions": {
                        key: event["context_positions"][key]
                        for key in ("dtype", "nbytes", "sha256", "shape", "stride")
                    },
                    "slot_mapping_signatures": [
                        {
                            key: signature[key]
                            for key in (
                                "dtype",
                                "nbytes",
                                "sha256",
                                "shape",
                                "stride",
                            )
                        }
                        for signature in event["slot_mapping_signatures"]
                    ],
                    "expected_cache_update_count": event[
                        "expected_cache_update_count"
                    ],
                }
            )
            if treatment == "candidate":
                signatures = projection["workspace_signatures"]
                previous = workspace_by_width.get(width)
                if previous is None:
                    if projection["workspace_reused"] is not False:
                        die(
                            f"candidate: rank {rank} first C{width} call marked reused"
                        )
                    workspace_by_width[width] = signatures
                elif (
                    projection["workspace_reused"] is not True
                    or signatures != previous
                ):
                    die(f"candidate: rank {rank} C{width} workspace identity drift")
        returned_precompute_calls[rank] = sum(
            event["expected_cache_update_count"] == 6 for event in events
        )
        reused_precompute[rank] = sum(
            event["expected_cache_update_count"] == 6
            and event["projection"]["workspace_reused"] is True
            for event in events
        )
        if returned_precompute_calls[rank] < 1:
            die(f"{treatment}: rank {rank} lacks a mapped precompute return")
        if treatment == "candidate" and reused_precompute[rank] < 1:
            die(f"candidate: rank {rank} lacks an actual workspace reuse")
    return {
        "counts": counts,
        "returned_precompute_calls": returned_precompute_calls,
        "reused_precompute_calls": reused_precompute,
        "normalized": normalized,
    }


def compare_raw_extensions(
    control: dict[str, Any],
    candidate: dict[str, Any],
) -> None:
    for rank in ("0", "1", "2", "3"):
        left = control["rank_events"][rank]
        right = candidate["rank_events"][rank]
        if len(left) != len(right):
            die(f"raw extension: rank {rank} event count drift")
        for ordinal, (a, b) in enumerate(zip(left, right, strict=True)):
            if a["collectives"] != b["collectives"]:
                die(f"raw extension: rank {rank} event {ordinal} collectives differ")
            graph_a = a["graph"]
            graph_b = b["graph"]
            normalized_a = {
                key: value
                for key, value in graph_a.items()
                if key != "descriptor"
            }
            normalized_b = {
                key: value
                for key, value in graph_b.items()
                if key != "descriptor"
            }
            if normalized_a != normalized_b:
                die(
                    f"raw extension: rank {rank} event {ordinal} graph structure differs"
                )


def validate_output_accounting(
    drivers: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    terminal_overrun: dict[str, dict[str, dict[str, Any]]] = {}
    for treatment in ("control", "candidate"):
        output = drivers[treatment]["token_ids"]
        expected = output[1:]
        terminal_overrun[treatment] = {}
        for rank in ("0", "1", "2", "3"):
            events = evidence[treatment]["rank_events"][rank]
            event_emissions = [event["emitted_ids"] for event in events]
            if not event_emissions or any(not ids for ids in event_emissions):
                die(f"{treatment}: rank {rank} has an empty M8 emission event")
            emitted = [token for ids in event_emissions for token in ids]
            if len(emitted) < len(expected) or emitted[: len(expected)] != expected:
                die(
                    f"{treatment}: rank {rank} public output after initial M1 "
                    "is not an exact prefix of the raw M8 emission stream"
                )
            before_final = sum(len(ids) for ids in event_emissions[:-1])
            if len(expected) <= before_final:
                die(
                    f"{treatment}: rank {rank} excluded emissions are not "
                    "confined to the final M8 verifier event"
                )
            tail = emitted[len(expected) :]
            if len(tail) > 7:
                die(
                    f"{treatment}: rank {rank} final verifier overrun exceeds "
                    "the frozen seven-token speculative depth"
                )
            terminal_overrun[treatment][rank] = {
                "ids": tail,
                "source_event_index": len(events) - 1,
            }
    if terminal_overrun["control"] != terminal_overrun["candidate"]:
        die("terminal verifier-overrun emissions differ across treatments")
    return terminal_overrun


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve(strict=True)
    if (
        root != args.root
        or not root.is_relative_to(
            Path(
                "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs"
            ).resolve(strict=True)
        )
        or args.out != root / "analysis.json"
        or args.out.exists()
        or args.out.is_symlink()
    ):
        die("analysis root/output identity drift")
    validate_private_nvme_dir(root)
    for treatment in ("control", "candidate"):
        arm_root = root / treatment
        validate_private_nvme_dir(arm_root)
        validate_private_nvme_dir(arm_root / "evidence")
        validate_private_nvme_dir(arm_root / "dflash-lifecycle")
    if sha256_file(CANDIDATE_SOURCE) != CANDIDATE_SOURCE_SHA256:
        die("candidate DFlash source hash drift")
    if RAW_ANALYZER != Path(
        "/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/"
        "tools/analyze_laguna_m8_actual_offline_gate.py"
    ) or sha256_file(RAW_ANALYZER) != RAW_ANALYZER_SHA256:
        die("raw evidence analyzer identity drift")

    campaign = validate_campaign_identity(root)
    operations = validate_operational_evidence(root)
    evidence_manifest_sha256 = validate_evidence_manifest(root)
    drivers: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    event_counts: dict[str, dict[str, int]] = {}
    lifecycle: dict[str, dict[str, Any]] = {}
    for treatment in ("control", "candidate"):
        arm_root = root / treatment
        drivers[treatment] = validate_driver(
            treatment, arm_root, load_json(arm_root / "driver.json")
        )
        evidence[treatment], event_counts[treatment] = validate_raw(
            treatment, arm_root, drivers[treatment]
        )
        lifecycle[treatment] = validate_lifecycle_trace(treatment, arm_root)

    if normalize_treatment(drivers["control"]) != normalize_treatment(
        drivers["candidate"]
    ):
        die("driver identity differs outside the frozen selector treatment")
    if (
        drivers["control"]["prompt_token_ids"]
        != drivers["candidate"]["prompt_token_ids"]
        or drivers["control"]["token_ids"] != drivers["candidate"]["token_ids"]
        or drivers["control"]["text"] != drivers["candidate"]["text"]
        or drivers["control"]["finish_reason"]
        != drivers["candidate"]["finish_reason"]
    ):
        die("selector-off/on public output differs")

    expected_tokens, teacher = teacher_prefix()
    for treatment, driver in drivers.items():
        if driver["token_ids"] != expected_tokens:
            die(f"{treatment}: output differs from canonical q1 teacher prefix")

    raw_gate.compare(
        evidence["control"],
        evidence["candidate"],
        "context-KV selector off/on",
    )
    compare_raw_extensions(evidence["control"], evidence["candidate"])
    if lifecycle["control"]["normalized"] != lifecycle["candidate"]["normalized"]:
        die("DFlash lifecycle context/slot/expected-update trace differs")
    terminal_overrun = validate_output_accounting(drivers, evidence)
    accepted_counts = {
        treatment: sorted(
            {
                event["acceptance"]["accepted_draft_count"]
                for events in aggregate["rank_events"].values()
                for event in events
            }
        )
        for treatment, aggregate in evidence.items()
    }
    if accepted_counts["control"] != accepted_counts["candidate"]:
        die("accepted-prefix coverage differs across treatments")

    result = {
        "schema": SCHEMA,
        "status": "bounded_single_request_tp4_integration_exactness_pass",
        "authority": (
            "bounded_integration_exactness_only_no_benchmark_or_submission"
        ),
        "candidate": {
            "vllm_commit": VLLM_COMMIT,
            "kernel_commit": KERNEL_COMMIT,
            "source": str(CANDIDATE_SOURCE),
            "source_sha256": CANDIDATE_SOURCE_SHA256,
            "selector": "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE",
        },
        "campaign": campaign,
        "operations": operations,
        "evidence_manifest_sha256": evidence_manifest_sha256,
        "teacher": teacher,
        "treatments": {
            "control": 0,
            "candidate": 1,
            "sole_semantic_delta": (
                "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE"
            ),
        },
        "public_output": {
            "prompt_token_ids_sha256": drivers["control"][
                "prompt_token_ids_sha256"
            ],
            "token_ids_sha256": drivers["control"]["token_ids_sha256"],
            "text_sha256": drivers["control"]["text_sha256"],
            "completion_tokens": MAX_TOKENS,
            "cached_tokens": 0,
            "teacher_prefix_exact": True,
            "selector_off_on_exact": True,
        },
        "raw_trace": {
            "four_rank_exact": True,
            "event_counts": event_counts,
            "accepted_draft_counts_observed": accepted_counts["control"],
            "compared_fields": [
                "draft_proposal_ids",
                "target_rejection_sampled_token_ids",
                "accepted_draft_count",
                "first_rejected_draft_index",
                "emitted_ids_before_and_after_bookkeeping",
                "target_hidden",
                "attention_inputs_outputs",
                "live_slot_routing",
                "collective_outputs",
                "normalized_graph_structure",
            ],
            "public_output_after_initial_m1_is_exact_raw_emission_prefix": True,
            "excluded_terminal_verifier_overrun_ids": terminal_overrun["control"],
        },
        "workspace_execution_proof": {
            "selector_on_recorded": True,
            "dflash_precompute_returned_with_six_expected_updates": lifecycle[
                "candidate"
            ][
                "returned_precompute_calls"
            ],
            "workspace_reuse_precompute_returned_calls": lifecycle["candidate"][
                "reused_precompute_calls"
            ],
            "control_lifecycle_event_counts": lifecycle["control"]["counts"],
            "candidate_lifecycle_event_counts": lifecycle["candidate"]["counts"],
            "workspace_branch_observed_on_every_rank": True,
            "capture_false_on_every_workspace_call": True,
            "frozen_source_branch_sha256": CANDIDATE_SOURCE_SHA256,
            "component_width_proof": (
                "data/laguna-s-2.1-dflash-context-kv-component-20260725.json"
            ),
        },
        "excluded_claims": {
            "model_performance_measurements": "absent",
            "endpoint_benchmark": "not_run",
            "record": "not_claimed",
            "localmaxxing_submission": "not_authorized",
        },
        "next_authority": "design_only_cold_graph_crossover",
    }
    reject_timing_fields(result, "analysis")
    write_exclusive(args.out, result)
    print(
        "Laguna DFlash context-KV runtime analysis: "
        "bounded_single_request_tp4_integration_exactness_pass"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        raise SystemExit(f"Laguna context-KV runtime analyzer: {exc}") from exc
