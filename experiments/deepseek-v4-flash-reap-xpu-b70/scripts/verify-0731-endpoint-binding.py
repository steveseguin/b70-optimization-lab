#!/usr/bin/env python3
"""Bind a 0731 qualification request to the intended live server process tree."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


MODEL = "deepseek-v4-flash-0731-reap-k160"
REVISION = "ddc04540efda3d2a0788b129f1fad828ddc19b60"
MODEL_ROOT = Path("/mnt/usb-models/llm-models/DeepSeek-V4-Flash-0731-REAP")
VLLM_COMMIT = "264c7f2f7df21ddeeab32ecca0353133344f1ac9"
KERNEL_COMMIT = "31315673737d95da0f79179c8f755260ef02c1d6"
ONECCL_COMMIT = "48fda4f0e074db005596d6899d5227d3f0316c12"
ONECCL_SHA256 = "53de2b6d65265803d64773546c1166ceed4ae43737f0fded776f5847b4b461c9"
MANIFEST_SHA256 = "d51c588c90ceb04182c2e7d54cb4d448864025920b937dabe8c8572b07af9d72"
VALIDATION_SHA256 = "5db933e6b7c9cda3df3b5c6f9116be06ff250672da6e72b02f35f244c4dccbe3"
VLLM_CLI = "/home/steve/.venvs/deepseek-v4-xpu/bin/vllm"
VLLM_CLI_SHA256 = "d16721cbe3e6bef44881b6b45ce64d9362a82bec4748754bd91ec85704c243fb"
PYTHON = "/home/steve/.venvs/deepseek-v4-xpu/bin/python"
PYTHON_SHA256 = "202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8"
KERNEL_BINARY_SHA256 = "c0597c1db9d1e684462adce681101957e7a969baab3c0c71fb748ca7fd8c24e9"
VLLM_TREE = Path("/home/steve/src/deepseek-v4-vllm-record-baseline-264c7f2f7")
KERNEL_TREE = Path("/home/steve/src/deepseek-v4-xpu-kernels-record-313156737")
ONECCL_TREE = Path("/home/steve/src/oneccl-2021.17.2-b70-sizegate")
KERNEL_BINARY = KERNEL_TREE / "vllm_xpu_kernels/_xpu_C.abi3.so"
ONECCL_BINARY = Path(
    "/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib/libccl.so.1"
)

ZERO_IDENTITY_KEYS = (
    "vllm_xpu_v4_direct_fp8_attn",
    "vllm_xpu_v4_split_fp8_attn",
    "vllm_xpu_v4_fp8_wo_a",
    "vllm_xpu_v4_inplace_allreduce",
    "vllm_xpu_v4_inplace_allreduce_m2",
    "vllm_xpu_v4_segmented_allreduce_max_m",
    "vllm_xpu_dpep_allreduce",
    "vllm_xpu_dpep_switch_sync",
    "vllm_xpu_dpep_native",
    "vllm_xpu_v4_mhc_norm_fusion",
    "vllm_xpu_v4_tp4_ring_mhc_post",
    "vllm_xpu_v4_tp4_ring_mhc_post_pre",
    "vllm_xpu_v4_mhc_pre_m1_single_kernel",
    "vllm_xpu_v4_mhc_post_pre_m1_single_kernel",
    "vllm_xpu_v4_mhc_post_pre_m2_single_kernel",
    "vllm_xpu_v4_mhc_post_pre_m1_rms",
    "vllm_xpu_v4_mhc_post_pre_fixed_width_max_m",
    "vllm_xpu_v4_shared_expert_fused_act_quant",
    "vllm_xpu_v4_shared_expert_fused_act_quant_max_m",
    "vllm_xpu_v4_m2_routed_clamp_silu",
    "vllm_xpu_moe_output_alias",
    "vllm_xpu_v4_m1_biased_topk",
    "vllm_xpu_v4_m1_router_norm",
    "vllm_xpu_v4_m2_router_norm",
    "vllm_xpu_v4_m1_direct_routed_moe",
    "vllm_xpu_v4_m2_route_direct_compact",
    "vllm_xpu_v4_direct_routed_moe_allow_256_expert_fallback",
    "vllm_xpu_v4_router_norm_max_m",
    "vllm_xpu_v4_native_dual_rmsnorm",
    "vllm_xpu_v4_fused_qnorm_rope_kv_insert",
    "vllm_xpu_v4_fused_qnorm_rope_kv_insert_max_m",
    "vllm_xpu_v4_compressor_m2_row_exact",
    "vllm_xpu_v4_compressor_m2_batched_exact",
    "vllm_xpu_v4_compressor_batched_exact_max_m",
    "vllm_xpu_v4_compressor_row_exact_max_m",
    "vllm_xpu_v4_forward_device_sync",
    "vllm_xpu_expert_map_round_robin",
    "vllm_xpu_v4_block_fp8_w8a16",
    "vllm_xpu_v4_block_fp8_w8a16_max_m",
    "vllm_xpu_native_mhc",
    "vllm_xpu_dspark_disable_draft_graph",
    "vllm_xpu_dspark_piecewise_draft_graph",
    "vllm_xpu_dspark_exact_query_capture",
    "vllm_xpu_dspark_piecewise_sample_graph",
    "vllm_xpu_dspark_fused_context_wkv",
    "vllm_xpu_dspark_replicated_markov",
    "vllm_xpu_greedy_fused_rejection",
    "vllm_xpu_greedy_sharded_target_argmax",
    "vllm_xpu_dspark_fixed_m7_target_inputs",
    "vllm_xpu_dspark_fixed_m8_target_builder",
    "vllm_xpu_dspark_persistent_markov",
    "vllm_xpu_dspark_persistent_markov_width_screen",
    "vllm_xpu_dspark_replicated_markov_w1",
    "vllm_xpu_dspark_markov_w2_dpas",
    "vllm_xpu_v4_mhc_post_pre_m8_dpas",
    "vllm_xpu_v4_mhc_post_pre_m8_pairtile",
    "vllm_xpu_dspark_sharded_markov_argmax",
    "vllm_xpu_dspark_host_markov_argmax",
    "vllm_xpu_dspark_ipc_event_markov_argmax",
    "vllm_xpu_dspark_ipc_event_markov7_bundle",
    "vllm_xpu_dspark_direct_draft_output",
    "vllm_xpu_dspark_greedy_copy_elision",
)

STATIC_IDENTITY = {
    "run_preflight": "1",
    "model_revision": REVISION,
    "served_model_name": MODEL,
    "artifact_manifest_file": "SHA256SUMS",
    "verify_manifest": "0",
    "vllm_commit": VLLM_COMMIT,
    "vllm_tree": "/home/steve/src/deepseek-v4-vllm-record-baseline-264c7f2f7",
    "vllm_cli": VLLM_CLI,
    "vllm_cli_sha256": VLLM_CLI_SHA256,
    "python_executable": PYTHON,
    "python_executable_sha256": PYTHON_SHA256,
    "kernel_commit": KERNEL_COMMIT,
    "kernel_tree": "/home/steve/src/deepseek-v4-xpu-kernels-record-313156737",
    "kernel_binary_sha256": KERNEL_BINARY_SHA256,
    "oneccl_source_worktree_head": ONECCL_COMMIT,
    "oneccl_runtime_selected_sha256": ONECCL_SHA256,
    "oneccl": "/home/steve/.venvs/deepseek-v4-xpu",
    "oneccl_lib": "/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib",
    "oneccl_source_tree": "/home/steve/src/oneccl-2021.17.2-b70-sizegate",
    "oneccl_runtime_default_lib": "/home/steve/.venvs/deepseek-v4-xpu/lib/libccl.so.1",
    "oneccl_runtime_default_sha256": "ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3",
    "oneccl_runtime_selected_lib": "/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib/libccl.so.1",
    "oneccl_runtime_selected_resolved_lib": "/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib/libccl.so.1.0",
    "oneapi_device_selector": "level_zero:*",
    "ze_affinity_mask": "0,1,2,3",
    "xpu_graph": "0",
    "vllm_xpu_enable_xpu_graph": "0",
    "vllm_xpu_force_graph_with_comm": "0",
    "vllm_xpu_graph_noop_comm_capture": "0",
    "compilation_config": '{"cudagraph_mode":"NONE"}',
    "vllm_target_device": "xpu",
    "enforce_eager": "1",
    "expert_parallel": "1",
    "tensor_parallel_size": "4",
    "pipeline_parallel_size": "1",
    "data_parallel_size": "1",
    "data_parallel_size_local": "1",
    "kv_cache_dtype": "fp8",
    "block_size": "256",
    "prefix_caching": "0",
    "vllm_xpu_fused_moe_use_ref": "0",
    "vllm_xpu_fused_moe_use_mxfp4_fp8": "0",
    "vllm_xpu_log_fp8_linear_shapes": "0",
    "vllm_xpu_use_sampler_kernel": "1",
    "vllm_xpu_v4_block_fp8_w8a16_shapes": "",
    "vllm_xpu_mxfp4_small_m_n": "64",
    "vllm_xpu_v4_direct_fp8_block_h": "16",
    "vllm_xpu_v4_direct_fp8_num_warps": "8",
    "vllm_xpu_v4_split_fp8_block_h": "16",
    "vllm_xpu_v4_split_fp8_qk_num_warps": "8",
    "vllm_xpu_v4_split_fp8_pv_num_warps": "4",
    "vllm_xpu_v4_capture_cycle_width": "2",
    "vllm_xpu_v4_capture_cycle_dir": "",
    "vllm_xpu_v4_divergence_capture_dir": "",
    "vllm_xpu_v4_divergence_stages": "layer_out",
    "vllm_xpu_v4_divergence_layers": "all",
    "vllm_xpu_v4_divergence_mode": "hash",
    "vllm_xpu_v4_divergence_max_records": "2048",
    "vllm_custom_scopes_for_profiling": "0",
    "vllm_xpu_dspark_confidence_gate_threshold": "unset",
    "vllm_xpu_dspark_draft_prefix_cap": "0",
    "vllm_xpu_dspark_ipc_event_count": "unset",
    "vllm_xpu_dspark_ipc_event_socket": "unset",
    "vllm_xpu_dspark_host_markov_shm": "unset",
    "dspark_spec_tokens": "unset",
    "dspark_kv_cache_memory_bytes": "125829120",
    "gpu_memory_utilization": "0.95",
    "oneccl_force_preload": "1",
    "ld_preload": "/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib/libccl.so.1.0",
    "ccl_atl_transport": "ofi",
    "ccl_topo_p2p_access": "1",
    "ccl_enable_sycl_kernels": "default",
    "ccl_allreduce": "default",
    "ccl_allgather": "default",
    "ccl_allgatherv": "default",
    "ccl_reduce_scatter": "default",
    "ccl_sycl_allreduce_ll": "ring",
    "ccl_sycl_allreduce_ll_threshold": "4096",
    "ccl_sycl_allreduce_arc": "0",
    "b70_oneccl_sycl_max_bytes": "disabled",
    "b70_oneccl_sycl_allreduce_max_bytes": "131072",
    "b70_oneccl_sycl_allgather_max_bytes": "disabled",
    "b70_oneccl_sycl_reduce_scatter_max_bytes": "disabled",
    "b70_oneccl_mhc_threads": "default",
    "b70_oneccl_mhc_explicit_barrier": "0",
    "ccl_topo_fabric_vertex_connection_check": "default",
    "fi_tcp_iface": "eno1",
    "ccl_kvs_iface": "eno1",
    "ccl_kernel_path": "/home/steve/.venvs/deepseek-v4-xpu/lib/ccl/kernels",
    "ccl_worker_count": "unset",
    "ccl_ze_ipc_exchange": "unset",
    "pythonpath": "/home/steve/src/deepseek-v4-vllm-record-baseline-264c7f2f7:/home/steve/src/deepseek-v4-xpu-kernels-record-313156737",
    "vllm_multi_stream_gemm_token_threshold": "1024",
    "triton_cache_autotuning": "1",
    "vllm_triton_force_first_config": "0",
    "vllm_extra_args": "--enable-prompt-tokens-details --kv-cache-memory 125829120",
    "package_torch": "2.12.0+xpu",
    "package_triton-xpu": "3.7.1",
    "package_vllm": "0.1.dev1172+g4a6fd8747.xpu",
    "package_vllm-xpu-kernels": "0.1.11.dev53+g744a8b4",
    "package_oneccl": "2021.17.2",
}
STATIC_IDENTITY.update({key: "0" for key in ZERO_IDENTITY_KEYS})


class BindingError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_identity(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise BindingError(f"cannot read identity: {exc}") from exc
    values: dict[str, str] = {}
    for number, line in enumerate(lines, 1):
        if not line or "=" not in line:
            raise BindingError(f"malformed identity line {number}")
        key, value = line.split("=", 1)
        if not re.fullmatch(r"[a-z0-9_.-]+", key) or key in values:
            raise BindingError(f"invalid or duplicate identity key: {key!r}")
        values[key] = value
    return values


def git_output(tree: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(tree), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise BindingError(f"cannot verify source tree {tree}: {exc}") from exc
    return completed.stdout.strip()


def verify_live_runtime_files() -> None:
    files = {
        Path(VLLM_CLI): VLLM_CLI_SHA256,
        Path(PYTHON): PYTHON_SHA256,
        KERNEL_BINARY: KERNEL_BINARY_SHA256,
        ONECCL_BINARY: ONECCL_SHA256,
    }
    for path, expected in files.items():
        if sha256(path) != expected:
            raise BindingError(f"live runtime file hash changed: {path}")
    for tree, expected in (
        (VLLM_TREE, VLLM_COMMIT),
        (KERNEL_TREE, KERNEL_COMMIT),
        (ONECCL_TREE, ONECCL_COMMIT),
    ):
        if git_output(tree, "rev-parse", "HEAD") != expected:
            raise BindingError(f"live source head changed: {tree}")
    for tree in (VLLM_TREE, KERNEL_TREE):
        if git_output(tree, "status", "--porcelain"):
            raise BindingError(f"live source tree is dirty: {tree}")
    for args in (("diff", "--quiet"), ("diff", "--cached", "--quiet")):
        git_output(ONECCL_TREE, *args)


def read_environ(path: Path) -> dict[str, str]:
    try:
        parts = [part for part in path.read_bytes().split(b"\0") if part]
        rows = [part.decode("utf-8").split("=", 1) for part in parts]
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise BindingError(f"cannot read launcher environment: {exc}") from exc
    result: dict[str, str] = {}
    for row in rows:
        if len(row) != 2 or row[0] in result:
            raise BindingError("malformed or duplicate launcher environment")
        result[row[0]] = row[1]
    return result


def parse_stat(path: Path) -> tuple[int, int]:
    try:
        raw = path.read_text(encoding="ascii")
        end = raw.rindex(")")
        tail = raw[end + 2 :].split()
        return int(tail[1]), int(tail[19])
    except (OSError, ValueError, IndexError) as exc:
        raise BindingError(f"cannot parse process stat {path}") from exc


def process_tree(proc_root: Path, launcher: int) -> set[int]:
    parents: dict[int, int] = {}
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            parent, _ = parse_stat(entry / "stat")
        except BindingError:
            continue
        parents[int(entry.name)] = parent
    if launcher not in parents:
        raise BindingError("recorded launcher process is not live")
    result = {launcher}
    changed = True
    while changed:
        changed = False
        for pid, parent in parents.items():
            if parent in result and pid not in result:
                result.add(pid)
                changed = True
    return result


def socket_inodes(proc_root: Path, pids: set[int]) -> dict[str, list[int]]:
    owners: dict[str, list[int]] = {}
    for pid in sorted(pids):
        fd_root = proc_root / str(pid) / "fd"
        try:
            entries = list(fd_root.iterdir())
        except OSError:
            continue
        for entry in entries:
            try:
                target = os.readlink(entry)
            except OSError:
                continue
            match = re.fullmatch(r"socket:\[(\d+)\]", target)
            if match:
                owners.setdefault(match.group(1), []).append(pid)
    return owners


def proc_pids(proc_root: Path) -> set[int]:
    try:
        return {int(entry.name) for entry in proc_root.iterdir() if entry.name.isdigit()}
    except OSError as exc:
        raise BindingError(f"cannot enumerate process tree: {exc}") from exc


def listening_inodes(proc_root: Path, host: str, port: int) -> set[str]:
    if host != "127.0.0.1":
        raise BindingError("only the frozen IPv4 loopback listener is permitted")
    wanted = f"0100007F:{port:04X}"
    result: set[str] = set()
    path = proc_root / "net" / "tcp"
    try:
        lines = path.read_text(encoding="ascii").splitlines()[1:]
    except OSError as exc:
        raise BindingError(f"cannot read IPv4 listener table: {exc}") from exc
    for line in lines:
        fields = line.split()
        if len(fields) > 9 and fields[3] == "0A" and fields[1].upper() == wanted:
            result.add(fields[9])
    return result


def expected_argv(port: int, mode: str, model_root: Path) -> list[str]:
    context = "256" if mode == "smoke" else "2048"
    return [
        VLLM_CLI,
        "serve",
        str(model_root),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--served-model-name",
        MODEL,
        "--dtype",
        "auto",
        "--tensor-parallel-size",
        "4",
        "--data-parallel-size",
        "1",
        "--data-parallel-size-local",
        "1",
        "--pipeline-parallel-size",
        "1",
        "--distributed-executor-backend",
        "mp",
        "--enable-expert-parallel",
        "--all2all-backend",
        "allgather_reducescatter",
        "--max-model-len",
        context,
        "--max-num-batched-tokens",
        context,
        "--max-num-seqs",
        "1",
        "--gpu-memory-utilization",
        "0.95",
        "--kv-cache-dtype",
        "fp8",
        "--block-size",
        "256",
        "--tokenizer-mode",
        "deepseek_v4",
        "--reasoning-parser",
        "deepseek_v4",
        "--tool-call-parser",
        "deepseek_v4",
        "--enable-auto-tool-choice",
        "--no-enable-prefix-caching",
        "--generation-config",
        "vllm",
        "--enforce-eager",
        "--enable-prompt-tokens-details",
        "--kv-cache-memory",
        "125829120",
    ]


def read_cmdline(path: Path) -> list[str]:
    try:
        return [part.decode("utf-8") for part in path.read_bytes().split(b"\0") if part]
    except (OSError, UnicodeDecodeError) as exc:
        raise BindingError(f"cannot read launcher command line: {exc}") from exc


def validate(
    identity_path: Path,
    base_url: str,
    validation_summary: Path,
    mode: str,
    proc_root: Path = Path("/proc"),
    model_root: Path = MODEL_ROOT,
    baseline_path: Path | None = None,
) -> dict[str, object]:
    if identity_path.is_symlink() or validation_summary.is_symlink():
        raise BindingError("identity and validation receipt must not be symlinks")
    identity_path = identity_path.resolve()
    validation_summary = validation_summary.resolve()
    model_root = model_root.resolve()
    identity_digest = sha256(identity_path)
    validation_digest = sha256(validation_summary)
    identity = load_identity(identity_path)
    for key, expected in STATIC_IDENTITY.items():
        if identity.get(key) != expected:
            raise BindingError(
                f"identity mismatch for {key}: {identity.get(key)!r} != {expected!r}"
            )
    dynamic_keys = {
        "launcher_pid",
        "host_boot_id",
        "process_start_ticks",
        "host",
        "port",
        "preflight_log_sha256",
        "model",
        "artifact_manifest_sha256",
        "full_validation_summary",
        "full_validation_summary_sha256",
        "max_model_len",
        "max_num_batched_tokens",
        "vllm_xpu_v4_capture_cycle_arm_file",
        "vllm_xpu_v4_divergence_arm_file",
        "ld_library_path",
        "vllm_cache_root",
        "torchinductor_cache_dir",
        "deepseek_0731_target_profile",
        "argv",
    }
    missing = sorted((set(STATIC_IDENTITY) | dynamic_keys) - set(identity))
    unexpected = sorted(set(identity) - set(STATIC_IDENTITY) - dynamic_keys)
    if missing or unexpected:
        raise BindingError(
            f"identity key contract mismatch: missing={missing}, unexpected={unexpected}"
        )

    if identity.get("model") != str(model_root):
        raise BindingError("model root does not match the pinned 0731 artifact")
    if identity.get("deepseek_0731_target_profile") != mode:
        raise BindingError("launcher profile does not match qualification mode")
    if identity.get("full_validation_summary") != str(validation_summary):
        raise BindingError("validation receipt path does not match the active launch")
    if validation_digest != VALIDATION_SHA256:
        raise BindingError("validation receipt is not the pinned passing receipt")
    if identity.get("full_validation_summary_sha256") != validation_digest:
        raise BindingError("validation receipt hash does not match the active launch")
    manifest = model_root / "SHA256SUMS"
    manifest_digest = sha256(manifest)
    if manifest_digest != MANIFEST_SHA256:
        raise BindingError("artifact manifest is not the pinned 0731 manifest")
    if identity.get("artifact_manifest_sha256") != manifest_digest:
        raise BindingError("artifact manifest hash mismatch")

    run_dir = identity_path.parent
    if identity.get("preflight_log_sha256") != sha256(run_dir / "preflight.log"):
        raise BindingError("preflight receipt hash mismatch")
    if identity.get("vllm_xpu_v4_capture_cycle_arm_file") != str(
        run_dir / "disabled-cycle-capture.arm"
    ):
        raise BindingError("capture arm path is not frozen to this run")
    if identity.get("vllm_xpu_v4_divergence_arm_file") != str(
        run_dir / "disabled-divergence.arm"
    ):
        raise BindingError("divergence arm path is not frozen to this run")
    expected_run_label = "canary" if mode == "smoke" else "full"
    run_match = re.fullmatch(
        rf"target-eager-{expected_run_label}-(\d{{8}}T\d{{6}}Z)", run_dir.name
    )
    if not run_match:
        raise BindingError("run directory does not match the frozen 0731 naming contract")
    cache_prefix = (
        "/mnt/fast-ai/vllm-cache-exp/deepseek-v4-flash-0731-reap-"
        f"{REVISION}/target-eager-{run_match.group(1)}"
    )
    if identity.get("vllm_cache_root") != f"{cache_prefix}/vllm":
        raise BindingError("vLLM cache root is not isolated to this attempt")
    if identity.get("torchinductor_cache_dir") != f"{cache_prefix}/torchinductor":
        raise BindingError("TorchInductor cache root is not isolated to this attempt")
    library_prefix = (
        "/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib:"
        "/home/steve/.venvs/deepseek-v4-xpu/lib:"
    )
    if not identity.get("ld_library_path", "").startswith(library_prefix):
        raise BindingError("selected runtime libraries are not first in LD_LIBRARY_PATH")

    try:
        max_model_len = int(identity["max_model_len"])
        max_batched = int(identity["max_num_batched_tokens"])
    except (KeyError, ValueError) as exc:
        raise BindingError("invalid context identity") from exc
    if mode == "smoke" and (max_model_len, max_batched) != (256, 256):
        raise BindingError("smoke mode requires the frozen 256/256 identity")
    if mode == "full" and (max_model_len, max_batched) != (2048, 2048):
        raise BindingError("full mode requires the frozen 2048/2048 identity")

    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise BindingError("base URL must be an unadorned local HTTP endpoint")
    try:
        port = parsed.port
    except ValueError as exc:
        raise BindingError("invalid base URL port") from exc
    if port is None or identity.get("port") != str(port):
        raise BindingError("base URL port does not match identity")
    if identity.get("host") != "127.0.0.1":
        raise BindingError("identity host must be the frozen IPv4 loopback address")

    try:
        recorded_argv = shlex.split(identity["argv"])
    except ValueError as exc:
        raise BindingError("cannot parse recorded launcher arguments") from exc
    frozen_argv = expected_argv(port, mode, model_root)
    if recorded_argv != frozen_argv:
        raise BindingError("recorded launcher arguments do not match the frozen arm")
    verify_live_runtime_files()

    boot_path = proc_root / "sys/kernel/random/boot_id"
    try:
        boot_id = boot_path.read_text(encoding="ascii").strip()
    except OSError as exc:
        raise BindingError("cannot read host boot identity") from exc
    if identity.get("host_boot_id") != boot_id:
        raise BindingError("host boot identity changed")
    try:
        launcher = int(identity["launcher_pid"])
        expected_ticks = int(identity["process_start_ticks"])
    except (KeyError, ValueError) as exc:
        raise BindingError("invalid launcher process identity") from exc
    _, actual_ticks = parse_stat(proc_root / str(launcher) / "stat")
    if actual_ticks != expected_ticks:
        raise BindingError("launcher process start identity changed")
    live_cmdline = read_cmdline(proc_root / str(launcher) / "cmdline")
    if len(live_cmdline) < len(frozen_argv) or live_cmdline[-len(frozen_argv) :] != frozen_argv:
        raise BindingError("live launcher arguments do not match the frozen arm")
    live_environment = read_environ(proc_root / str(launcher) / "environ")
    expected_environment = {key.upper(): "0" for key in ZERO_IDENTITY_KEYS}
    expected_environment.update(
        {
            "MODEL_PATH": str(model_root),
            "MODEL_REVISION": REVISION,
            "SERVED_MODEL_NAME": MODEL,
            "DEEPSEEK_0731_VALIDATION_SUMMARY": str(validation_summary),
            "DEEPSEEK_0731_TARGET_PROFILE": mode,
            "VLLM_TARGET_DEVICE": "xpu",
            "ONEAPI_DEVICE_SELECTOR": "level_zero:*",
            "ZE_AFFINITY_MASK": "0,1,2,3",
            "XPU_GRAPH": "0",
            "VLLM_XPU_ENABLE_XPU_GRAPH": "0",
            "VLLM_XPU_FORCE_GRAPH_WITH_COMM": "0",
            "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE": "0",
            "COMPILATION_CONFIG": '{"cudagraph_mode":"NONE"}',
            "ENFORCE_EAGER": "1",
            "TP_SIZE": "4",
            "PP_SIZE": "1",
            "DP_SIZE": "1",
            "DP_SIZE_LOCAL": "1",
            "MAX_MODEL_LEN": str(max_model_len),
            "MAX_NUM_BATCHED_TOKENS": str(max_batched),
            "GPU_MEMORY_UTILIZATION": "0.95",
            "VLLM_XPU_FUSED_MOE_USE_REF": "0",
            "VLLM_XPU_FUSED_MOE_USE_MXFP4_FP8": "0",
            "VLLM_XPU_USE_SAMPLER_KERNEL": "1",
            "VLLM_XPU_LOG_FP8_LINEAR_SHAPES": "0",
            "VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES": "",
            "VLLM_XPU_MXFP4_SMALL_M_N": "64",
            "VLLM_XPU_V4_DIRECT_FP8_BLOCK_H": "16",
            "VLLM_XPU_V4_DIRECT_FP8_NUM_WARPS": "8",
            "VLLM_XPU_V4_SPLIT_FP8_BLOCK_H": "16",
            "VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS": "8",
            "VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS": "4",
            "VLLM_CUSTOM_SCOPES_FOR_PROFILING": "0",
            "VLLM_XPU_V4_CAPTURE_CYCLE_WIDTH": "2",
            "VLLM_XPU_V4_CAPTURE_CYCLE_DIR": "",
            "VLLM_XPU_V4_CAPTURE_CYCLE_ARM_FILE": identity[
                "vllm_xpu_v4_capture_cycle_arm_file"
            ],
            "VLLM_XPU_V4_DIVERGENCE_CAPTURE_DIR": "",
            "VLLM_XPU_V4_DIVERGENCE_ARM_FILE": identity[
                "vllm_xpu_v4_divergence_arm_file"
            ],
            "VLLM_XPU_V4_DIVERGENCE_STAGES": "layer_out",
            "VLLM_XPU_V4_DIVERGENCE_LAYERS": "all",
            "VLLM_XPU_V4_DIVERGENCE_MODE": "hash",
            "VLLM_XPU_V4_DIVERGENCE_MAX_RECORDS": "2048",
            "VLLM_XPU_DSPARK_CONFIDENCE_GATE_THRESHOLD": "",
            "VLLM_XPU_DSPARK_DRAFT_PREFIX_CAP": "0",
            "DSPARK_KV_CACHE_MEMORY_BYTES": "125829120",
            "VLLM_EXTRA_ARGS": "--enable-prompt-tokens-details --kv-cache-memory 125829120",
            "VLLM_MULTI_STREAM_GEMM_TOKEN_THRESHOLD": "1024",
            "TRITON_CACHE_AUTOTUNING": "1",
            "VLLM_TRITON_FORCE_FIRST_CONFIG": "0",
            "VLLM_CACHE_ROOT": identity["vllm_cache_root"],
            "TORCHINDUCTOR_CACHE_DIR": identity["torchinductor_cache_dir"],
            "ONECCL_INSTALL_DIR": "/home/steve/.venvs/deepseek-v4-xpu",
            "ONECCL_LIB_DIR": STATIC_IDENTITY["oneccl_lib"],
            "ONECCL_SOURCE_TREE": STATIC_IDENTITY["oneccl_source_tree"],
            "ONECCL_FORCE_PRELOAD": "1",
            "CCL_ROOT": "/home/steve/.venvs/deepseek-v4-xpu",
            "CCL_ATL_TRANSPORT": "ofi",
            "CCL_TOPO_P2P_ACCESS": "1",
            "CCL_SYCL_ALLREDUCE_LL": "ring",
            "CCL_SYCL_ALLREDUCE_LL_THRESHOLD": "4096",
            "CCL_SYCL_ALLREDUCE_ARC": "0",
            "B70_ONECCL_SYCL_MAX_BYTES": "",
            "B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES": "131072",
            "B70_ONECCL_SYCL_ALLGATHER_MAX_BYTES": "",
            "B70_ONECCL_SYCL_REDUCE_SCATTER_MAX_BYTES": "",
            "CCL_KERNEL_PATH": STATIC_IDENTITY["ccl_kernel_path"],
            "FI_TCP_IFACE": "eno1",
            "CCL_KVS_IFACE": "eno1",
            "LD_PRELOAD": STATIC_IDENTITY["ld_preload"],
            "LD_LIBRARY_PATH": identity["ld_library_path"],
            "PYTHONPATH": STATIC_IDENTITY["pythonpath"],
            "RUN_PREFLIGHT": "1",
            "VERIFY_MANIFEST": "0",
        }
    )
    mismatched_environment = sorted(
        key for key, expected in expected_environment.items()
        if live_environment.get(key) != expected
    )
    forbidden_environment = sorted(
        key for key in (
            "DSPARK_SPEC_TOKENS",
            "VLLM_XPU_DSPARK_HOST_MARKOV_SHM",
            "VLLM_XPU_DSPARK_IPC_EVENT_COUNT",
            "VLLM_XPU_DSPARK_IPC_EVENT_SOCKET",
            "CCL_WORKER_COUNT",
            "CCL_ZE_IPC_EXCHANGE",
            "CCL_ENABLE_SYCL_KERNELS",
            "CCL_ALLREDUCE",
            "CCL_ALLGATHER",
            "CCL_ALLGATHERV",
            "CCL_REDUCE_SCATTER",
            "B70_ONECCL_MHC_THREADS",
            "B70_ONECCL_MHC_EXPLICIT_BARRIER",
            "CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK",
        )
        if key in live_environment
    )
    if mismatched_environment or forbidden_environment:
        raise BindingError(
            "live launcher environment changed: "
            f"mismatched={mismatched_environment}, forbidden={forbidden_environment}"
        )

    descendants = process_tree(proc_root, launcher)
    listeners = listening_inodes(proc_root, "127.0.0.1", port)
    if len(listeners) != 1:
        raise BindingError("the exact endpoint must have exactly one listener socket")
    all_owners = socket_inodes(proc_root, proc_pids(proc_root))
    owner_pids = sorted({pid for inode in listeners for pid in all_owners.get(inode, [])})
    if not owner_pids or not set(owner_pids).issubset(descendants):
        raise BindingError("the exact listener is not owned solely by the attested process tree")

    if sha256(identity_path) != identity_digest or sha256(validation_summary) != validation_digest:
        raise BindingError("identity or validation receipt changed during binding")
    result = {
        "schema": "deepseek-v4-0731-endpoint-binding-v1",
        "status": "pass",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "model": MODEL,
        "revision": REVISION,
        "base_url": base_url.rstrip("/"),
        "identity": str(identity_path),
        "identity_sha256": identity_digest,
        "validation_summary": str(validation_summary),
        "validation_summary_sha256": validation_digest,
        "launcher_pid": launcher,
        "process_start_ticks": actual_ticks,
        "host_boot_id": boot_id,
        "listener_port": port,
        "listener_host": "127.0.0.1",
        "listener_socket_inodes": sorted(listeners, key=int),
        "listener_owner_pids": owner_pids,
        "process_tree_pids": sorted(descendants),
        "max_model_len": max_model_len,
        "max_num_batched_tokens": max_batched,
    }
    if baseline_path is not None:
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BindingError(f"cannot read binding baseline: {exc}") from exc
        stable_fields = (
            "identity_sha256",
            "validation_summary_sha256",
            "launcher_pid",
            "process_start_ticks",
            "host_boot_id",
            "listener_host",
            "listener_port",
            "listener_socket_inodes",
            "listener_owner_pids",
        )
        changed = [field for field in stable_fields if baseline.get(field) != result.get(field)]
        if changed:
            raise BindingError(f"endpoint binding changed from baseline: {changed}")
        result["baseline"] = str(baseline_path.resolve())
        result["baseline_sha256"] = sha256(baseline_path)
    return result


def atomic_json(path: Path, value: object) -> None:
    if path.exists() or path.is_symlink():
        raise BindingError(f"refusing to overwrite binding report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        os.unlink(temporary)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--validation-summary", type=Path, required=True)
    parser.add_argument("--mode", choices=("smoke", "full"), required=True)
    parser.add_argument("--model-root", type=Path, default=MODEL_ROOT)
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"))
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = validate(
        args.identity,
        args.base_url,
        args.validation_summary,
        args.mode,
        args.proc_root,
        args.model_root,
        args.baseline,
    )
    atomic_json(args.out, result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BindingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
