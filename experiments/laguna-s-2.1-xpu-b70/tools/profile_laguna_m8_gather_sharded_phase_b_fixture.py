#!/usr/bin/env python3
"""Direct-call 13x47 MoeGather fixture for the packeted Phase-B profiler.

Torch is intentionally imported only after the caller has supplied a canonical
packet, Phase-A aggregate success, binary-bundle digest, and one-card mapping.
It loads the immutable bundle directly -- never the mutable development tree
or a vLLM package -- and executes no model/service code.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import importlib
import json
import os
import re
import stat
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

counters: Any = None
phase_a: Any = None
phase_a_analysis: Any = None
SOURCE_TOOL_IDENTITIES: dict[str, Any] | None = None

ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
FIXTURE_ROOT = ROOT / "evidence/m8-gather-sharded-fixtures-30b043b2b-20260724T1050Z"
MANIFEST = FIXTURE_ROOT / "manifest.json"
LAYERS, CYCLES = 47, 13
FIXTURE_OUTPUT_MODE = 0o644  # root-owned child evidence; enclosing arm directory is 0700
BODY_KEYS = {"phase", "common", "common_binding_sha256", "phase_a_binding", "output_root", "cards", "protocol", "counter_gates", "counter_header", "tools", "counter_tools", "temporal_control"}
PTI_COMMIT = "a5bab309f4ffdd78bd127035c46f5f75371160f8"
UNITRACE = Path("/home/steve/src/pti-gpu/build-unitrace/unitrace")
COUNTER_TOOL_IDENTITIES = {
    "unitrace": (UNITRACE, "5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a"),
    "libunitrace_tool": (UNITRACE.parent / "libunitrace_tool.so", "00f9e1c95f1b53f1466f15dafa97ddcd709899ad7ca2869626456deb5e177e04"),
    "level_zero_loader": (Path("/usr/lib/x86_64-linux-gnu/libze_loader.so.1.28.2"), "0fe232b18985ae078dd546b57bc6d11bacf1030834c0544f7e3feb53ed71c1d0"),
    "level_zero_driver": (Path("/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1.15.38308"), "26fa68779adb03b200a8c3001cf81e59fc9a3d63e0f38627ec0005ffce574e7a"),
}
TOOL_FILENAMES = {
    "runner": "run_laguna_m8_gather_sharded_phase_b.py",
    "analyzer": "analyze_laguna_m8_gather_sharded_phase_b.py",
    "fixture": "profile_laguna_m8_gather_sharded_phase_b_fixture.py",
    "counter_parser": "laguna_m8_gather_sharded_counter_parser.py",
    "tests": "test_laguna_m8_gather_sharded_phase_b.py",
    "operational_preflight": "preflight_laguna_m8_gather_sharded_operational.py",
}

def expected_environment(rank: int, arm_root: Path) -> dict[str, str]:
    require(0 <= rank < 4 and arm_root.is_absolute(), "environment rank/root")
    private = arm_root / "scratch/runtime"
    cache = private / "cache"
    environment = {
        "HOME": str(private / "home"), "HF_HOME": str(cache / "huggingface"), "NUMBA_CACHE_DIR": str(cache / "numba"),
        "PYTHONPYCACHEPREFIX": str(cache / "pycache"), "SYCL_CACHE_DIR": str(cache / "sycl"),
        "TORCHINDUCTOR_CACHE_DIR": str(cache / "torchinductor"), "TRANSFORMERS_CACHE": str(cache / "transformers"),
        "TRITON_CACHE_DIR": str(cache / "triton"), "VLLM_CACHE_ROOT": str(cache / "vllm"),
        "XDG_CACHE_HOME": str(cache / "xdg-cache"), "XDG_CONFIG_HOME": str(cache / "xdg-config"),
        "XDG_DATA_HOME": str(cache / "xdg-data"), "XDG_STATE_HOME": str(cache / "xdg-state"),
        "TEMP": str(private / "tmp"), "TMP": str(private / "tmp"), "TMPDIR": str(private / "tmp"),
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "PYTHONPATH": str(phase_a.TOOLS_ROOT),
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "PYTHONSAFEPATH": "1",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "VLLM_NO_USAGE_STATS": "1", "LD_PRELOAD": "", "LD_LIBRARY_PATH": "",
        "ACTIVE_REQUESTS": "1", "DP": "1", "EP": "4", "PP": "1", "TP": "4", "MKL_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
        "ZE_AFFINITY_MASK": str(rank), "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
        "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED": "1", "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE": "0",
        "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
        "VLLM_XPU_LAGUNA_M8_GRAPH": "0", "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
        "XPU_GRAPH": "0", "VLLM_XPU_ENABLE_XPU_GRAPH": "0", "VLLM_XPU_FORCE_GRAPH_WITH_COMM": "0", "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE": "0",
        "VLLM_XPU_GDN_NATIVE_FALLBACK": "0", "VLLM_USE_V1": "0", "VLLM_USE_AOT_COMPILE": "0", "TORCH_COMPILE_DISABLE": "1", "TORCHINDUCTOR_DISABLE": "1",
        "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0", "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0", "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0", "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0", "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "0", "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM": "0",
        "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1", "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1", "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1", "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1", "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64", "VLLM_XPU_EXACT_SPEC_ATTN": "1", "VLLM_XPU_RUN_DEVICE_TESTS": "0",
        "VLLM_XPU_LAGUNA_PARITY_PROBE": "0", "VLLM_XPU_LAGUNA_PARITY_RETURN_STAGE": "0", "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS": "7",
    }
    require(environment == phase_a.expected_environment(rank, arm_root), "Phase-A/B exact environment drift")
    return environment

def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def application_environment_contract(rank: int, arm_root: Path, session: str, unitrace_tool: str, version: str) -> dict[str, str]:
    base = expected_environment(rank, arm_root)
    base.pop("LD_PRELOAD")
    internals = {
        "UNITRACE_DeviceTiming": "1", "UNITRACE_Verbose": "1", "UNITRACE_Pid": "1",
        "UNITRACE_LogToFile": "1", "UNITRACE_LogFilename": "unitrace", "UNITRACE_StartPaused": "1",
        "UNITRACE_MetricQuery": "1", "UNITRACE_MetricGroup": "ComputeBasic", "UNITRACE_DevicesToSampleArg": "0",
        "UNITRACE_DevicesToSample": "0", "UNITRACE_IncludeKernels": "MoeGather", "UNITRACE_FollowChildProcess": "0",
        "UNITRACE_Session": session, "UNITRACE_SamplingInterval": "50", "UNITRACE_ChromeEventBufferSize": "-1",
        "UNITRACE_LD_PRELOAD_OLD": "", "ZE_ENABLE_TRACING_LAYER": "1", "ZET_ENABLE_METRICS": "1", "ZES_ENABLE_SYSMAN": "1",
    }
    return {**base, **internals, "UNITRACE_VERSION": version}


def validate_recorded_application_environment(environment: object, rank: int, arm_root: Path, session: str, unitrace_tool: str, pti_commit: str) -> dict[str, str]:
    require(isinstance(environment, dict) and all(isinstance(key, str) and isinstance(value, str) for key, value in environment.items()), "application environment schema")
    version = environment.get("UNITRACE_VERSION", "")
    require(isinstance(pti_commit, str) and len(pti_commit) == 40 and pti_commit[:8] in version and "(" in version and version.endswith(")"), "unitrace version/commit environment drift")
    require(environment == application_environment_contract(rank, arm_root, session, unitrace_tool, version), "application environment differs from env-i plus known unitrace internals")
    forbidden = ("GRAPH", "CAPTURE", "COMPILE", "DYNAMO")
    base = expected_environment(rank, arm_root)
    require(all(key in base or not any(token in key.upper() for token in forbidden) for key in environment), "unallowlisted graph/capture/compile environment variable")
    return {key: environment[key] for key in sorted(environment)}


def validate_application_environment(rank: int, arm_root: Path, session: str, unitrace_tool: str, pti_commit: str) -> dict[str, str]:
    return validate_recorded_application_environment(dict(os.environ), rank, arm_root, session, unitrace_tool, pti_commit)


def verify_unitrace_mapping(unitrace_tool: str, expected_sha256: str) -> dict[str, Any]:
    path = Path(unitrace_tool)
    require(path.is_absolute() and path.is_file() and sha(path) == expected_sha256, "unitrace tool file identity drift")
    descriptor = os.open("/proc/self/maps", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        chunks = bytearray()
        while len(chunks) <= 16 * 1024 * 1024:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            chunks.extend(block)
        raw = bytes(chunks)
    finally:
        os.close(descriptor)
    require(len(raw) <= 16 * 1024 * 1024, "oversized process maps")
    mapped = [line for line in raw.decode("utf-8", "strict").splitlines() if line.endswith(" " + str(path)) or line.endswith(str(path))]
    require(bool(mapped), "sealed libunitrace_tool is not mapped in profiled process")
    return {"path": str(path), "sha256": expected_sha256, "mapped": True, "matching_map_entries": len(mapped)}

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def sha(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    before = os.fstat(descriptor)
    require(stat.S_ISREG(before.st_mode), f"not a retained regular file: {path}")
    digest = hashlib.sha256()
    try:
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode), f"retained file changed during hash: {path}")
    return digest.hexdigest()

def read_canonical(path: Path, maximum: int = 16 * 1024 * 1024) -> tuple[dict[str, Any], bytes]:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size <= maximum, "unsafe packet/evidence JSON")
        result = bytearray()
        while len(result) < info.st_size:
            block = os.read(fd, min(1024 * 1024, info.st_size - len(result)))
            require(bool(block), "short JSON read")
            result.extend(block)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "JSON changed during retained read")
    raw = bytes(result)
    value = json.loads(raw)
    require(isinstance(value, dict) and raw == canonical(value) + b"\n", "noncanonical JSON")
    return value, raw


def bootstrap_sealed_tool_stage(args: argparse.Namespace) -> None:
    """Validate the packet-bound stage before importing any project module."""
    global SOURCE_TOOL_IDENTITIES, counters, phase_a, phase_a_analysis
    require(counters is None and phase_a is None and phase_a_analysis is None, "tool modules already imported")
    stage = args.tool_stage
    require(
        isinstance(stage, Path)
        and stage.is_absolute()
        and not stage.is_symlink()
        and stage.resolve(strict=True) == stage,
        "unsafe tool stage",
    )
    script = Path(__file__).resolve(strict=True)
    require(script.parent == stage and script.name == TOOL_FILENAMES["fixture"], "fixture is not executing from its sealed stage")
    packet_path = args.packet
    require(packet_path.is_absolute() and not packet_path.is_symlink(), "unsafe bootstrap packet path")
    packet, packet_raw = read_canonical(packet_path)
    require(hashlib.sha256(packet_raw).hexdigest() == args.packet_sha256, "bootstrap Phase-B packet SHA drift")
    body = packet.get("body")
    require(isinstance(body, dict) and isinstance(body.get("tools"), dict), "bootstrap Phase-B body/tool schema")
    binding = body.get("phase_a_binding")
    require(isinstance(binding, dict), "bootstrap Phase-A binding schema")
    phase_a_path = Path(binding.get("authorization_path", ""))
    phase_a_packet, _phase_a_raw = read_canonical(phase_a_path)
    phase_a_body = phase_a_packet.get("body")
    require(
        isinstance(phase_a_body, dict)
        and phase_a_packet.get("paired_phase_b_packet_sha256") == args.packet_sha256
        and hashlib.sha256(canonical(phase_a_body) + b"\n").hexdigest() == binding.get("phase_a_body_sha256"),
        "bootstrap Phase-A mutual binding drift",
    )
    expected = {
        "phase_b": body["tools"],
        "phase_a": {
            "runner": phase_a_body["runner"],
            "analyzer": phase_a_body["analyzer"],
        },
    }
    closure, _closure_raw = read_canonical(stage / "tool-closure.json")
    require(
        isinstance(closure, dict)
        and set(closure) == {"format", "source_identities", "staged_files"}
        and closure["format"] == "laguna-m8-gather-sharded-phase-b-tool-closure-v1"
        and closure["source_identities"] == expected,
        "tool closure identity drift",
    )
    staged_files = closure["staged_files"]
    require(
        isinstance(staged_files, dict) and set(staged_files) == {"phase_b", "phase_a"},
        "tool closure staged-file schema",
    )
    for family, identities in expected.items():
        mapping = staged_files[family]
        require(isinstance(mapping, dict) and set(mapping) == set(identities), f"{family} staged-file roles")
        for role, identity in identities.items():
            require(
                isinstance(identity, dict)
                and set(identity) == {"path", "sha256"}
                and _sha(identity["sha256"]),
                f"{family}/{role} source identity",
            )
            name = mapping[role]
            require(
                isinstance(name, str)
                and name == Path(identity["path"]).name
                and "/" not in name
                and "\\" not in name,
                f"{family}/{role} staged name",
            )
            staged = stage / name
            metadata = os.stat(staged, follow_symlinks=False)
            require(
                stat.S_ISREG(metadata.st_mode)
                and stat.S_IMODE(metadata.st_mode) == 0o444
                and not staged.is_symlink()
                and sha(staged) == identity["sha256"],
                f"{family}/{role} staged source drift",
            )
    SOURCE_TOOL_IDENTITIES = expected
    sys.path.insert(0, str(stage))
    counters = importlib.import_module("laguna_m8_gather_sharded_counter_parser")
    phase_a = importlib.import_module("run_laguna_m8_gather_sharded_phase_a")
    phase_a_analysis = importlib.import_module("analyze_laguna_m8_gather_sharded_phase_a")
    require(
        Path(counters.__file__).resolve(strict=True).parent == stage
        and Path(phase_a.__file__).resolve(strict=True).parent == stage
        and Path(phase_a_analysis.__file__).resolve(strict=True).parent == stage,
        "project helper imported outside sealed stage",
    )

def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)

def _full_sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def expected_tools() -> dict[str, dict[str, str]]:
    require(
        isinstance(SOURCE_TOOL_IDENTITIES, dict)
        and set(SOURCE_TOOL_IDENTITIES) == {"phase_b", "phase_a"},
        "sealed tool closure was not bootstrapped",
    )
    identities = SOURCE_TOOL_IDENTITIES["phase_b"]
    require(
        isinstance(identities, dict) and set(identities) == set(TOOL_FILENAMES),
        "sealed Phase-B tool closure schema",
    )
    return {
        role: {"path": identities[role]["path"], "sha256": identities[role]["sha256"]}
        for role in TOOL_FILENAMES
    }


def counter_tool_identity() -> dict[str, Any]:
    identity = {
        role: {"path": str(path), "sha256": expected_sha}
        for role, (path, expected_sha) in COUNTER_TOOL_IDENTITIES.items()
    }
    for role, (path, expected_sha) in COUNTER_TOOL_IDENTITIES.items():
        require(path.is_file() and not path.is_symlink() and sha(path) == expected_sha, f"{role} identity drift")
    commit = subprocess.run(
        ["/usr/bin/git", "-c", f"safe.directory={UNITRACE.parents[1]}", "-C", str(UNITRACE.parents[1]), "rev-parse", "HEAD"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    require(commit.returncode == 0 and commit.stdout.strip() == PTI_COMMIT, "PTI commit drift")
    return {
        "unitrace": identity["unitrace"],
        "libunitrace_tool": identity["libunitrace_tool"],
        "pti_commit": PTI_COMMIT,
        "level_zero_loader": identity["level_zero_loader"],
        "level_zero_driver": identity["level_zero_driver"],
    }


def temporal_control_identity() -> dict[str, Any]:
    source_root = Path("/home/steve/src/pti-gpu/tools/unitrace")
    source_paths = {
        "README.md": source_root / "README.md",
        "unitrace.cc": source_root / "src/unitrace.cc",
        "unicontrol.h": source_root / "src/unicontrol.h",
        "shared_memory.h": source_root / "src/utils/shared_memory.h",
    }
    return {
        "pti_commit": PTI_COMMIT,
        "source_files": {
            name: {"path": str(path), "sha256": sha(path)}
            for name, path in source_paths.items()
        },
        "session_pattern": "Laguna<ARM>Card<RANK><32-lowercase-hex>",
        "session_minimum_bits": 128,
        "session_count": 16,
        "shm_prefix": "/uctrl",
        "prelaunch_shm_absent": True,
        "start_paused": True,
        "follow_child_process": 0,
        "capture_sequence": ["resume", "13x47_selected_gather", "xpu_synchronize", "pause", "stop"],
        "resume_acknowledgement": "[INFO] Session {session} is resumed\n",
        "pause_acknowledgement": "[INFO] Session {session} is paused\n",
        "stop_acknowledgement": "[INFO] Session {session} is stopped and can no longer be paused or resumed\n",
        "post_stop_shm_unlinked": True,
        "normal_return_and_metric_flush_required": True,
        "graph_capture_compile_apis_allowed": False,
    }


def validate_bindings(packet: dict[str, Any], packet_path: Path, packet_sha: str, aggregate: dict[str, Any], aggregate_path: Path, aggregate_sha: str, rank: int, arm: str) -> dict[str, Any]:
    """Independently verify the v3 pair, predecessor, and shared host state."""
    require(arm in counters.ARMS and rank in range(4), "invalid rank/arm")
    require(set(packet) == {"format", "packet_path", "body"} and packet.get("format") == "laguna-m8-gather-sharded-phase-b-authorization-v3" and packet.get("packet_path") == str(packet_path) and _full_sha(canonical(packet) + b"\n") == packet_sha, "Phase-B packet identity drift")
    phase_a.validate_phase_b_packet_shape(packet, packet_path, verify_artifacts=True)
    body = packet["body"]
    require(isinstance(body, dict) and set(body) == BODY_KEYS and body.get("phase") == "B", "Phase-B body schema")
    common = phase_a.validate_common(body["common"])
    phase_a.verify_common_artifacts(common)
    common_sha = phase_a.common_hash(common)
    require(body.get("common_binding_sha256") == common_sha, "shared common digest drift")
    protocol = body.get("protocol")
    require(protocol == {"cycles": 13, "layers_per_cycle": 47, "raw_selected_rows": 611, "discard_cycles": [0, 1], "retained_selected_rows": 517, "arm_order": ["A1", "B1", "B2", "A2"], "unitrace_inner_timeout_seconds": 900, "runner_outer_timeout_seconds": 930, "pre_arm_strict_idle_seconds": 65, "pre_arm_idle_sample_interval_seconds": 5, "pre_arm_idle_min_samples": 14, "same_boot_required": True, "fresh_private_runtime_per_arm": True}, "frozen Phase-B protocol drift")
    require(body.get("counter_gates") == {"gpu_memory_per_field_max_ratio": 1.02, "gpu_memory_total_max_ratio": 1.02, "lsc_per_field_max_ratio": 1.02, "lsc_total_max_ratio": 1.02, "xve_active_max_decline_pp": 0.5, "thread_occupancy_max_decline_pp": 0.5, "xve_stall_max_increase_pp": 0.5, "no_global_rescue": True}, "counter gate drift")
    require(body.get("counter_header") == {"fields": 86, "sha256": counters.METRIC_HEADER_SHA256}, "counter header drift")
    require(body.get("tools") == expected_tools(), "full Phase-B tool identity drift")
    require(body.get("counter_tools") == counter_tool_identity(), "counter tool identity drift")
    require(body.get("temporal_control") == temporal_control_identity(), "temporal-control source/contract drift")
    binding = body.get("phase_a_binding")
    required = {"authorization_path", "phase_a_body_sha256", "phase_a_runner_path", "phase_a_runner_sha256", "aggregate_path", "aggregate_format", "required_status", "required_passed", "common_binding_sha256"}
    require(isinstance(binding, dict) and set(binding) == required and binding["aggregate_path"] == str(aggregate_path) and binding["aggregate_format"] == "laguna-m8-gather-sharded-phase-a-aggregate-v3" and binding["required_status"] == "component_timing_pass_pending_mandatory_counters" and binding["required_passed"] is True and binding["common_binding_sha256"] == common_sha, "Phase-A aggregate/mutual binding drift")
    phase_a_path = Path(binding["authorization_path"])
    phase_a_packet, phase_a_raw = read_canonical(phase_a_path)
    phase_a.validate_phase_a_packet(phase_a_packet, phase_a_path, verify_artifacts=True)
    require(phase_a_packet["paired_phase_b_packet_sha256"] == packet_sha and _full_sha(canonical(phase_a_packet["body"]) + b"\n") == binding["phase_a_body_sha256"] and phase_a_packet["body"]["common"] == common and phase_a_packet["body"]["common_binding_sha256"] == common_sha, "Phase-A wrapper/body is not mutually bound")
    phase_a.verify_mutual_packets(phase_a_packet, packet)
    require(Path(binding["phase_a_runner_path"]).is_file() and sha(Path(binding["phase_a_runner_path"])) == binding["phase_a_runner_sha256"], "Phase-A runner identity drift")
    require(aggregate.get("format") == binding["aggregate_format"] and aggregate.get("status") == binding["required_status"] and aggregate.get("passed") is True and aggregate.get("packet_path") == str(phase_a_path) and aggregate.get("packet_sha256") == _full_sha(phase_a_raw) and _full_sha(canonical(aggregate) + b"\n") == aggregate_sha, "Phase-A aggregate identity drift")
    entries = aggregate.get("card_results")
    require(isinstance(entries, list) and len(entries) == 4, "Phase-A four-card evidence missing")
    result_paths: list[Path] = []
    for card_rank, entry in enumerate(entries):
        require(isinstance(entry, dict) and set(entry) == {"rank", "path", "sha256"} and entry["rank"] == card_rank and _sha(entry["sha256"]), "Phase-A card result entry drift")
        result_path = Path(entry["path"])
        result, raw_result = read_canonical(result_path, 128 * 1024 * 1024)
        require(_full_sha(raw_result) == entry["sha256"], "Phase-A card result hash drift")
        phase_a.validate_card_result(result, phase_a_packet, card_rank)
        result_paths.append(result_path)
    require(phase_a_analysis.validate(phase_a_path, _full_sha(phase_a_raw), result_paths) == aggregate, "Phase-A aggregate/card/cross-card evidence recomputation drift")
    cards = body.get("cards")
    root = Path(body["output_root"])
    require(root.is_absolute() and root.parent == ROOT / "runs", "Phase-B output root drift")
    require(isinstance(cards, list) and len(cards) == 4, "four-card Phase-B binding drift")
    for card_rank, card in enumerate(cards):
        require(isinstance(card, dict) and set(card) == {"rank", "output_root", "environments", "sessions"} and card["rank"] == card_rank and card["output_root"] == str(root / f"card{card_rank}") and isinstance(card["environments"], dict) and set(card["environments"]) == set(counters.ARMS) and isinstance(card["sessions"], dict) and set(card["sessions"]) == set(counters.ARMS), "Phase-B card/output/environment binding drift")
        for card_arm in counters.ARMS:
            arm_root = root / f"card{card_rank}" / card_arm
            require(card["environments"][card_arm] == expected_environment(card_rank, arm_root), "Phase-B fresh arm environment drift")
    sessions = [card["sessions"][name] for card in cards for name in counters.ARMS]
    require(len(set(sessions)) == 16 and all(re.fullmatch(rf"Laguna{name}Card{card_rank}[0-9a-f]{{32}}", cards[card_rank]["sessions"][name] or "") for card_rank in range(4) for name in counters.ARMS), "session uniqueness/entropy drift")
    selected_root = root / f"card{rank}" / arm
    expected_env = cards[rank]["environments"][arm]
    for key in ("HOME", "HF_HOME", "NUMBA_CACHE_DIR", "PYTHONPYCACHEPREFIX", "SYCL_CACHE_DIR", "TORCHINDUCTOR_CACHE_DIR", "TRANSFORMERS_CACHE", "TRITON_CACHE_DIR", "VLLM_CACHE_ROOT", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "TEMP", "TMP", "TMPDIR"):
        private = Path(expected_env[key])
        require(private.is_absolute() and private.is_relative_to(selected_root) and private.is_dir() and not private.is_symlink() and private.resolve(strict=True) == private, "Phase-B private arm environment root drift")
    counter_tools = body["counter_tools"]
    observed_environment = validate_application_environment(rank, selected_root, cards[rank]["sessions"][arm], counter_tools["libunitrace_tool"]["path"], counter_tools["pti_commit"])
    unitrace_mapping = verify_unitrace_mapping(counter_tools["libunitrace_tool"]["path"], counter_tools["libunitrace_tool"]["sha256"])
    fixture = common.get("fixture")
    require(isinstance(fixture, dict) and fixture.get("manifest") == str(MANIFEST) and _sha(fixture.get("manifest_sha256")) and sha(MANIFEST) == fixture["manifest_sha256"], "fixture manifest binding drift")
    bundle = common.get("native_bundle")
    require(isinstance(bundle, dict) and set(bundle["libraries"]) == {"shared-_C.abi3.so", "shared-_xpu_C.abi3.so", "candidate-_moe_C.abi3.so", "libgdn_attn_kernels_xe_2.so", "libgrouped_gemm_xe_2.so", "libgrouped_gemm_xe_default.so", "libmhc_kernels_xe_2.so", "libmqa_logits_kernels_xe_2.so"}, "native bundle inventory drift")
    libraries = bundle["libraries"]
    for record in libraries.values():
        library = Path(record.get("path", "")) if isinstance(record, dict) else Path()
        require(isinstance(record, dict) and isinstance(record.get("mode"), int) and library.is_absolute() and library.is_relative_to(ROOT) and library.is_file() and not library.is_symlink() and _sha(record.get("sha256")) and sha(library) == record["sha256"] and (library.stat().st_mode & 0o777) == record["mode"], "native library digest/mode drift")
    return {"card": common["cards"][rank], "phase_card": cards[rank], "fixture": fixture, "bundle": bundle, "environment": expected_env, "observed_environment": observed_environment, "unitrace_mapping": unitrace_mapping, "common": common}

def _epoch_bytes(record: dict[str, Any]) -> int:
    width = {"<u2": 2, "<u4": 4}[record["dtype"]]
    total = width
    for dimension in record["shape"][1:]:
        total *= dimension
    return total


def _signature(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
    return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns, stat.S_IMODE(metadata.st_mode))


def _pread_exact(descriptor: int, size: int, offset: int) -> bytes:
    result = bytearray()
    while len(result) < size:
        block = os.pread(descriptor, size - len(result), offset + len(result))
        require(bool(block), "short descriptor-bound fixture read")
        result.extend(block)
    return bytes(result)


def _hash_fd(descriptor: int, size: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while offset < size:
        block = os.pread(descriptor, min(1024 * 1024, size - offset), offset)
        require(bool(block), "short descriptor-bound fixture hash")
        digest.update(block)
        offset += len(block)
    return digest.hexdigest()


def _open_fixture_fds(fixture_binding: dict[str, Any], bundle_binding: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(fixture_binding["root"])
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    descriptors: dict[str, int] = {}
    try:
        expected_paths = {
            "manifest": Path(fixture_binding["manifest"]),
            "canonical_route_map": Path(fixture_binding["canonical_route_map"]["path"]),
            "route_rows": Path(fixture_binding["records"]["route_rows"]["path"]),
            "weights": Path(fixture_binding["records"]["weights"]["path"]),
        }
        for name, path in expected_paths.items():
            require(path.parent == root and path.name not in {"", ".", ".."} and "/" not in path.name, f"unsafe fixture component: {name}")
            descriptor = os.open(path.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=root_fd)
            metadata = os.fstat(descriptor)
            require(stat.S_ISREG(metadata.st_mode), f"fixture component is not regular: {name}")
            descriptors[name] = descriptor
        manifest_metadata = os.fstat(descriptors["manifest"])
        manifest_raw = _pread_exact(descriptors["manifest"], manifest_metadata.st_size, 0)
        require(hashlib.sha256(manifest_raw).hexdigest() == fixture_binding["manifest_sha256"], "descriptor-bound fixture manifest hash drift")
        manifest = json.loads(manifest_raw)
        require(isinstance(manifest, dict) and manifest_raw == canonical(manifest) + b"\n", "descriptor-bound fixture manifest canonical drift")
        state = {
            "root_fd": root_fd,
            "root_signature": _signature(os.fstat(root_fd)),
            "descriptors": descriptors,
            "signatures": {name: _signature(os.fstat(descriptor)) for name, descriptor in descriptors.items()},
            "manifest": manifest,
            "dependency_handles": [],
        }
        state["initial_validation"] = _validate_fixture_fds(state, fixture_binding)
        if bundle_binding is not None:
            bundle_root = Path(bundle_binding["root"])
            bundle_root_fd = os.open(bundle_root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
            library_descriptors: dict[str, int] = {}
            try:
                for name, record in bundle_binding["libraries"].items():
                    require(Path(record["path"]).parent == bundle_root and Path(record["path"]).name == name, f"unsafe bundle component: {name}")
                    descriptor = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=bundle_root_fd)
                    require(stat.S_ISREG(os.fstat(descriptor).st_mode), f"bundle component is not regular: {name}")
                    library_descriptors[name] = descriptor
                state.update({
                    "bundle_root_fd": bundle_root_fd,
                    "bundle_root_signature": _signature(os.fstat(bundle_root_fd)),
                    "library_descriptors": library_descriptors,
                    "library_signatures": {name: _signature(os.fstat(descriptor)) for name, descriptor in library_descriptors.items()},
                })
                state["initial_bundle_validation"] = _validate_bundle_fds(state, bundle_binding)
            except BaseException:
                for descriptor in library_descriptors.values():
                    os.close(descriptor)
                os.close(bundle_root_fd)
                raise
        return state
    except BaseException:
        for descriptor in descriptors.values():
            os.close(descriptor)
        os.close(root_fd)
        raise


def _validate_fixture_fds(state: dict[str, Any], fixture_binding: dict[str, Any]) -> dict[str, Any]:
    require(_signature(os.fstat(state["root_fd"])) == state["root_signature"], "fixture root descriptor changed")
    descriptors, signatures = state["descriptors"], state["signatures"]
    require(all(_signature(os.fstat(descriptors[name])) == signatures[name] for name in descriptors), "fixture descriptor identity changed")
    evidence: dict[str, Any] = {}
    manifest_size = signatures["manifest"][2]
    require(_hash_fd(descriptors["manifest"], manifest_size) == fixture_binding["manifest_sha256"], "retained fixture manifest changed")
    for name in ("route_rows", "weights"):
        record = fixture_binding["records"][name]
        descriptor, size = descriptors[name], signatures[name][2]
        width = _epoch_bytes(record)
        require(size == width * 288 and _hash_fd(descriptor, size) == record["sha256"], f"retained fixture whole hash drift: {name}")
        observed_epochs = []
        for epoch, expected in enumerate(record["per_epoch_sha256"]):
            digest = hashlib.sha256(_pread_exact(descriptor, width, epoch * width)).hexdigest()
            require(digest == expected, f"retained fixture epoch hash drift: {name}/{epoch}")
            observed_epochs.append(digest)
        evidence[name] = {"sha256": record["sha256"], "per_epoch_sha256": observed_epochs}
    map_record = fixture_binding["canonical_route_map"]
    map_size = signatures["canonical_route_map"][2]
    require(map_size == 320 and _hash_fd(descriptors["canonical_route_map"], map_size) == map_record["sha256"], "retained canonical route map drift")
    evidence["canonical_route_map"] = {"sha256": map_record["sha256"], "bytes": map_size}
    return evidence


def _validate_bundle_fds(state: dict[str, Any], bundle_binding: dict[str, Any]) -> dict[str, Any]:
    require(_signature(os.fstat(state["bundle_root_fd"])) == state["bundle_root_signature"], "bundle root descriptor changed")
    evidence: dict[str, Any] = {}
    for name, descriptor in state["library_descriptors"].items():
        signature = state["library_signatures"][name]
        require(_signature(os.fstat(descriptor)) == signature, f"bundle descriptor identity changed: {name}")
        record = bundle_binding["libraries"][name]
        digest = _hash_fd(descriptor, signature[2])
        require(digest == record["sha256"] and signature[2] == record["bytes"] and signature[4] == 0o444, f"retained bundle identity drift: {name}")
        evidence[name] = {"sha256": digest, "dev": signature[0], "inode": signature[1], "bytes": signature[2], "mode": signature[4]}
    return evidence


def _close_fixture_fds(state: dict[str, Any]) -> None:
    for descriptor in state.get("library_descriptors", {}).values():
        os.close(descriptor)
    if isinstance(state.get("bundle_root_fd"), int):
        os.close(state["bundle_root_fd"])
    for descriptor in state["descriptors"].values():
        os.close(descriptor)
    os.close(state["root_fd"])


def _load_epochs(torch: Any, manifest: dict[str, Any], state: dict[str, Any]) -> tuple[list[tuple[Any, Any]], Any]:
    tensors = manifest["tensors"]
    routes, weights = tensors["route_rows"], tensors["weights"]
    require(manifest["epochs"] >= LAYERS and manifest["geometry"] == {"tokens": 8, "topk": 10, "hidden": 3072, "ranks": 4}, "production fixture geometry drift")
    result: list[tuple[Any, Any]] = []
    for index in range(LAYERS):
        route_bytes = _pread_exact(state["descriptors"]["route_rows"], _epoch_bytes(routes), index * _epoch_bytes(routes))
        weight_bytes = _pread_exact(state["descriptors"]["weights"], _epoch_bytes(weights), index * _epoch_bytes(weights))
        require(hashlib.sha256(route_bytes).hexdigest() == routes["epoch_sha256"][index] and hashlib.sha256(weight_bytes).hexdigest() == weights["epoch_sha256"][index], f"descriptor-bound loaded epoch changed: {index}")
        route_cpu = torch.frombuffer(bytearray(route_bytes), dtype=torch.bfloat16).reshape(80, 3072)
        weight_cpu = torch.frombuffer(bytearray(weight_bytes), dtype=torch.float32).reshape(8, 10)
        result.append((route_cpu.to("xpu").contiguous(), weight_cpu.to("xpu").contiguous()))
    map_bytes = _pread_exact(state["descriptors"]["canonical_route_map"], 320, 0)
    require(hashlib.sha256(map_bytes).hexdigest() == manifest["canonical_route_map"]["sha256"], "descriptor-bound loaded route map changed")
    route_map = torch.frombuffer(bytearray(map_bytes), dtype=torch.int32).reshape(8, 10).to("xpu").contiguous()
    return result, route_map


def _load_sealed_libraries(torch: Any, state: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    dependencies = (
        "libgdn_attn_kernels_xe_2.so", "libgrouped_gemm_xe_2.so",
        "libgrouped_gemm_xe_default.so", "libmhc_kernels_xe_2.so",
        "libmqa_logits_kernels_xe_2.so",
    )
    extensions = ("shared-_C.abi3.so", "shared-_xpu_C.abi3.so", "candidate-_moe_C.abi3.so")
    loaded: dict[str, Any] = {}
    for name in dependencies:
        descriptor = state["library_descriptors"][name]
        record = bundle["libraries"][name]
        digest = _hash_fd(descriptor, os.fstat(descriptor).st_size)
        require(digest == record["sha256"], f"dependency changed before load: {name}")
        handle = ctypes.CDLL(f"/proc/self/fd/{descriptor}", mode=ctypes.RTLD_GLOBAL | ctypes.RTLD_NOW)
        state["dependency_handles"].append(handle)
        loaded[name] = {"loaded_via": f"/proc/self/fd/{descriptor}", "sha256": digest, "rtld_global": True}
    for name in extensions:
        descriptor = state["library_descriptors"][name]
        expected = os.fstat(descriptor)
        record = bundle["libraries"][name]
        path = Path(record["path"])
        actual = os.stat(path, follow_symlinks=False)
        digest = _hash_fd(descriptor, expected.st_size)
        require(stat.S_ISREG(actual.st_mode) and (actual.st_dev, actual.st_ino, actual.st_size) == (expected.st_dev, expected.st_ino, expected.st_size) and digest == record["sha256"], f"extension path does not resolve to retained inode: {name}")
        torch.ops.load_library(str(path))
        loaded[name] = {"loaded_via": str(path), "sha256": digest, "retained_inode_confirmed_before_load": True}
    descriptor = os.open("/proc/self/maps", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        chunks = bytearray()
        while len(chunks) <= 16 * 1024 * 1024:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            chunks.extend(block)
        require(len(chunks) <= 16 * 1024 * 1024, "oversized process maps")
    finally:
        os.close(descriptor)
    mapped = {name: 0 for name in (*dependencies, *extensions)}
    for line in bytes(chunks).decode("utf-8", "strict").splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6:
            continue
        mapped_path = fields[5].removesuffix(" (deleted)")
        name = Path(mapped_path).name
        if name not in mapped:
            continue
        expected = os.fstat(state["library_descriptors"][name])
        actual = os.stat(mapped_path, follow_symlinks=False)
        require((actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino), f"same-basename unsealed native mapping: {name}")
        mapped[name] += 1
    require(all(count > 0 for count in mapped.values()), "one or more retained native mappings missing")
    for name in loaded:
        loaded[name]["mapping_segments"] = mapped[name]
        loaded[name]["mapping_verified"] = True
    require(hasattr(torch.ops._moe_C, "moe_gather") and hasattr(torch.ops._moe_C, "laguna_m8_moe_gather_sharded"), "required sealed gather ops absent")
    return {"libraries": loaded, "same_basename_extras": False, "all_eight_mapped": True}


def _raw_bytes(tensor: Any, torch: Any) -> bytes:
    return tensor.detach().contiguous().to("cpu").view(torch.uint8).numpy().tobytes()


def _tensor_hash(tensor: Any, torch: Any) -> str:
    return hashlib.sha256(_raw_bytes(tensor, torch)).hexdigest()


def _classification(tensor: Any, torch: Any) -> dict[str, Any]:
    bits = tensor.detach().contiguous().to("cpu").view(torch.uint16).to(torch.int32)
    exponent, fraction, sign = bits & 0x7F80, bits & 0x007F, bits & 0x8000
    nan = (exponent == 0x7F80) & (fraction != 0)
    payload = fraction[nan].to(torch.uint8).numpy().tobytes()
    return {
        "positive_zero": int(((exponent == 0) & (fraction == 0) & (sign == 0)).sum().item()),
        "negative_zero": int(((exponent == 0) & (fraction == 0) & (sign != 0)).sum().item()),
        "subnormal": int(((exponent == 0) & (fraction != 0)).sum().item()),
        "finite_normal": int(((exponent != 0) & (exponent != 0x7F80)).sum().item()),
        "infinity": int(((exponent == 0x7F80) & (fraction == 0)).sum().item()),
        "nan": int(nan.sum().item()),
        "nan_payloads_sha256": hashlib.sha256(payload).hexdigest(),
    }


def _input_hashes(torch: Any, epochs: list[tuple[Any, Any]], route_map: Any) -> dict[str, Any]:
    return {
        "route_rows": [_tensor_hash(routes, torch) for routes, _weights in epochs],
        "weights": [_tensor_hash(weights, torch) for _routes, weights in epochs],
        "canonical_route_map": _tensor_hash(route_map, torch),
    }


def _output_record(torch: Any, tensor: Any, cycle: int, layer: int) -> dict[str, Any]:
    cpu = tensor.detach().contiguous().to("cpu")
    raw = cpu.view(torch.uint8).numpy().tobytes()
    return {"cycle": cycle, "layer": layer, "raw_bf16_le_sha256": hashlib.sha256(raw).hexdigest(), "classification": _classification(cpu, torch)}


def _parse_runtime_uuid(raw_uuid_value: Any) -> tuple[uuid.UUID, bytes]:
    try:
        if isinstance(raw_uuid_value, str):
            runtime_uuid = uuid.UUID(raw_uuid_value)
            raw_uuid = runtime_uuid.bytes
        elif type(raw_uuid_value).__module__ == "torch._C" and type(raw_uuid_value).__name__ == "_XPUuuid":
            octets = raw_uuid_value.bytes
            require(type(octets) is list and len(octets) == 16 and all(type(value) is int and 0 <= value <= 255 for value in octets), "Torch runtime XPU UUID octets drift")
            raw_uuid = bytes(octets)
            runtime_uuid = uuid.UUID(bytes=raw_uuid)
            require(str(raw_uuid_value).lower() == str(runtime_uuid).lower(), "Torch runtime XPU UUID text/bytes disagree")
        elif isinstance(raw_uuid_value, (bytes, bytearray, memoryview)):
            raw_uuid = bytes(raw_uuid_value)
            require(len(raw_uuid) == 16, "runtime XPU UUID is not 16 bytes")
            runtime_uuid = uuid.UUID(bytes=raw_uuid)
        else:
            raise TypeError("unsupported runtime XPU UUID type")
    except (TypeError, ValueError, AttributeError) as exc:
        raise RuntimeError("runtime XPU UUID is malformed") from exc
    return runtime_uuid, raw_uuid


def _read_small_text(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode) and 0 <= before.st_size <= 4096, f"unsafe retained sysfs file: {path}")
        raw = os.pread(descriptor, 4096, 0)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        f"sysfs identity changed while reading: {path}",
    )
    return raw.decode("ascii", "strict").strip()


def _verify_runtime_card(torch: Any, card: dict[str, Any]) -> dict[str, Any]:
    require(torch.xpu.is_available() and torch.xpu.device_count() == 1 and torch.xpu.current_device() == 0, "one-visible-device isolation drift")
    require(torch.xpu.get_device_name(0) == "Intel(R) Arc(TM) Pro B70 Graphics", "visible XPU name drift")
    require(isinstance(card, dict) and set(card) == {"physical_rank", "xpu_smi_uuid", "bdf", "drm_card"}, "flat common-card schema drift")
    prop = torch.xpu.get_device_properties(0)
    torch_uuid, torch_raw = _parse_runtime_uuid(prop.uuid)
    reversed_raw = torch_raw[::-1]
    runtime_uuid = str(uuid.UUID(bytes=reversed_raw)).lower()
    require(runtime_uuid == card["xpu_smi_uuid"], "Torch reverse-byte UUID does not bind selected card")
    drm = Path(card["drm_card"])
    drm_stat = os.stat(drm, follow_symlinks=False)
    sysfs = (Path("/sys/class/drm") / drm.name / "device").resolve(strict=True)
    require(stat.S_ISCHR(drm_stat.st_mode) and sysfs.name == card["bdf"] and _read_small_text(sysfs / "vendor").lower() == "0x8086" and _read_small_text(sysfs / "device").lower() == "0xe223", "runtime DRM/BDF/vendor/device drift")
    return {"visible_device_count": 1, "current_device": 0, "logical_device": "xpu:0", "device_name": "Intel(R) Arc(TM) Pro B70 Graphics", "xpu_smi_uuid": runtime_uuid, "runtime_uuid_bytes_hex": reversed_raw.hex(), "torch_runtime_uuid": str(torch_uuid).lower(), "torch_runtime_uuid_bytes_hex": torch_raw.hex(), "runtime_uuid_mapping": "xpu_smi_uuid_is_reverse_of_torch_level_zero_bytes", "bdf": card["bdf"], "drm_card": str(drm), "pci_vendor": "0x8086", "pci_device": "0xe223"}


def _control(unitrace: Path, descriptor: int, action: str, session: str) -> dict[str, Any]:
    require(action in {"resume", "pause", "stop"} and re.fullmatch(r"[A-Za-z0-9]{40,64}", session) is not None, "unsafe/high-entropy temporal-control request")
    before = os.fstat(descriptor)
    require(stat.S_ISREG(before.st_mode) and _hash_fd(descriptor, before.st_size) == COUNTER_TOOL_IDENTITIES["unitrace"][1], "retained unitrace descriptor drift")
    display_command = [str(unitrace), f"--{action}", session]
    command = [f"/proc/self/fd/{descriptor}", f"--{action}", session]
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        pass_fds=(descriptor,),
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=30)
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.output or b"", error.stderr or b""
        try:
            os.killpg(process.pid, 9)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired as reap_error:
            raise RuntimeError("unitrace temporal-control process did not reap after SIGKILL") from reap_error
        raise RuntimeError(f"unitrace {action} timed out")
    after = os.fstat(descriptor)
    require(_signature(before) == _signature(after) and _hash_fd(descriptor, after.st_size) == COUNTER_TOOL_IDENTITIES["unitrace"][1], "retained unitrace descriptor changed")
    acknowledgement = (f"[INFO] Session {session} is stopped and can no longer be paused or resumed\n" if action == "stop" else f"[INFO] Session {session} is {action}d\n").encode()
    require(process.returncode == 0 and stdout == b"" and stderr == acknowledgement, f"unitrace {action} acknowledgement missing/drifted")
    retained = {"sha256": COUNTER_TOOL_IDENTITIES["unitrace"][1], "dev": before.st_dev, "inode": before.st_ino, "bytes": before.st_size, "mode": stat.S_IMODE(before.st_mode)}
    return {"command": display_command, "executed_via_retained_fd": True, "retained_identity": retained, "returncode": process.returncode, "expected_stderr_utf8": acknowledgement.decode(), "stdout_base64": base64.b64encode(stdout).decode("ascii"), "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_base64": base64.b64encode(stderr).decode("ascii"), "stderr_sha256": hashlib.sha256(stderr).hexdigest()}

def run(args: argparse.Namespace) -> dict[str, Any]:
    packet_path, aggregate_path = args.packet.resolve(strict=True), args.phase_a_aggregate.resolve(strict=True)
    packet, raw_packet = read_canonical(packet_path)
    aggregate, raw_aggregate = read_canonical(aggregate_path)
    require(hashlib.sha256(raw_packet).hexdigest() == args.packet_sha256 and hashlib.sha256(raw_aggregate).hexdigest() == args.phase_a_aggregate_sha256, "argument SHA mismatch")
    binding = validate_bindings(packet, packet_path, args.packet_sha256, aggregate, aggregate_path, args.phase_a_aggregate_sha256, args.rank, args.arm)
    require(args.session == binding["phase_card"]["sessions"][args.arm], "session argument differs from packet")
    require(args.unitrace == Path(packet["body"]["counter_tools"]["unitrace"]["path"]), "unitrace argument differs from packet")
    out = args.out
    expected_out = Path(binding["phase_card"]["output_root"]) / args.arm / "fixture.json"
    require(out == expected_out and out.is_absolute() and out.parent.is_dir() and not out.parent.is_symlink() and out.parent.resolve(strict=True) == out.parent and not out.exists() and not out.is_symlink(), "unsafe/unbound fixture output")
    runtime_identity = binding["common"]["runtime_identity"]["observed_identity"]
    require(Path(sys.executable) == Path(runtime_identity["python_executable"]), "profile interpreter differs from packet runtime")
    unitrace_descriptor = os.open(args.unitrace, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    state: dict[str, Any] | None = None
    resumed = paused = stopped = False
    try:
        state = _open_fixture_fds(binding["fixture"], binding["bundle"])
        manifest = state["manifest"]
        import torch  # noqa: PLC0415 -- authorization and retained-FD full fixture validation precede native import
        require(torch.__version__ == runtime_identity["torch_version"] and Path(torch.__file__).resolve(strict=True) == Path(runtime_identity["files"]["torch_init"]["resolved_path"]), "imported Torch differs from packet runtime")
        runtime = _verify_runtime_card(torch, binding["card"])
        native_load = _load_sealed_libraries(torch, state, binding["bundle"])
        epochs, route_map = _load_epochs(torch, manifest, state)
        inputs_before = _input_hashes(torch, epochs, route_map)
        outputs = [[torch.empty((8, 3072), dtype=torch.bfloat16, device="xpu") for _ in range(LAYERS)] for _ in range(CYCLES)]
        torch.xpu.synchronize()
        resume = _control(args.unitrace, unitrace_descriptor, "resume", args.session)
        resumed = True
        selected = 0
        with torch.no_grad():
            for cycle in range(CYCLES):
                for index, (routes, weights) in enumerate(epochs):
                    if counters.ARMS[args.arm] == "control":
                        torch.ops._moe_C.moe_gather(outputs[cycle][index], routes, weights, route_map, 64)
                    else:
                        torch.ops._moe_C.laguna_m8_moe_gather_sharded(outputs[cycle][index], routes, weights, 64)
                    selected += 1
            torch.xpu.synchronize()
        pause = _control(args.unitrace, unitrace_descriptor, "pause", args.session)
        paused = True
        stop = _control(args.unitrace, unitrace_descriptor, "stop", args.session)
        stopped = True
        require(selected == counters.RAW_ROWS, "selected gather call count drift")
        inputs_after = _input_hashes(torch, epochs, route_map)
        require(inputs_after == inputs_before, "device route/weight/map inputs changed across capture")
        output_evidence = [_output_record(torch, outputs[cycle][layer], cycle, layer) for cycle in range(CYCLES) for layer in range(LAYERS)]
        require(len(output_evidence) == counters.RAW_ROWS, "output evidence count drift")
        post_validation = _validate_fixture_fds(state, binding["fixture"])
        require(post_validation == state["initial_validation"], "fixture descriptor validation changed across arm")
        post_bundle_validation = _validate_bundle_fds(state, binding["bundle"])
        require(post_bundle_validation == state["initial_bundle_validation"], "bundle descriptor validation changed across arm")
        payload = {"format": "laguna-m8-gather-sharded-phase-b-fixture-v3", "status": "complete", "pid": os.getpid(), "rank": args.rank, "arm": args.arm, "packet_sha256": args.packet_sha256, "phase_a_aggregate_sha256": args.phase_a_aggregate_sha256, "selected_kernel": counters.KERNELS[counters.ARMS[args.arm]], "cycles": CYCLES, "layers_per_cycle": LAYERS, "selected_gather_calls": selected, "epoch_range": [0, 46], "capture_scope": "resume_then_only_13x47_selected_gathers_then_final_xpu_synchronize_then_pause_then_stop_unlink", "runtime": runtime, "application_environment": binding["observed_environment"], "application_environment_sha256": hashlib.sha256(canonical(binding["observed_environment"]) + b"\n").hexdigest(), "unitrace_mapping": binding["unitrace_mapping"], "fixture_fd_validation": {"before": state["initial_validation"], "after": post_validation, "retained_through_stop": True}, "native_closure": {"load": native_load, "before": state["initial_bundle_validation"], "after": post_bundle_validation, "retained_through_stop": True}, "input_integrity": {"before": inputs_before, "after": inputs_after, "passed": True}, "output_evidence": output_evidence, "session": args.session, "resume": resume, "pause": pause, "stop": stop}
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, FIXTURE_OUTPUT_MODE)
        try:
            os.fchmod(fd, FIXTURE_OUTPUT_MODE)
            data = canonical(payload) + b"\n"
            offset = 0
            while offset < len(data):
                wrote = os.write(fd, data[offset:])
                require(wrote > 0, "short fixture evidence write")
                offset += wrote
            os.fsync(fd)
        finally:
            os.close(fd)
        directory = os.open(out.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return payload
    finally:
        if resumed and not stopped:
            if not paused:
                try:
                    _control(args.unitrace, unitrace_descriptor, "pause", args.session)
                except BaseException:
                    pass
            try:
                _control(args.unitrace, unitrace_descriptor, "stop", args.session)
            except BaseException:
                pass
        os.close(unitrace_descriptor)
        if state is not None:
            _close_fixture_fds(state)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--phase-a-aggregate", type=Path, required=True)
    parser.add_argument("--phase-a-aggregate-sha256", required=True)
    parser.add_argument("--rank", type=int, required=True)
    parser.add_argument("--arm", choices=("A1", "B1", "B2", "A2"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--unitrace", type=Path, required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--tool-stage", type=Path, required=True)
    args = parser.parse_args()
    bootstrap_sealed_tool_stage(args)
    print(json.dumps(run(args), sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
