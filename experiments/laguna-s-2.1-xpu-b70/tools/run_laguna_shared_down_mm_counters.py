#!/usr/bin/env python3
"""Fail-closed four-card cold unitrace runner for Laguna shared-down MM."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAIN_REPO = Path("/home/steve/llm-optimizations")
TOOLS_DIR = MAIN_REPO / "experiments/laguna-s-2.1-xpu-b70/tools"
RUNNER = TOOLS_DIR / "run_laguna_shared_down_mm_counters.py"
FIXTURE = TOOLS_DIR / "profile_laguna_shared_down_mm_counter_fixture.py"
ANALYZER = TOOLS_DIR / "analyze_laguna_shared_down_mm_counters.py"
COUNTER_TEST = TOOLS_DIR / "test_analyze_laguna_shared_down_mm_counters.py"
GATE = TOOLS_DIR / "gate_laguna_shared_down_mm.py"
COMPONENT_ANALYZER = TOOLS_DIR / "analyze_laguna_shared_down_mm_component.py"
AUTHORIZATION_RELATIVE = Path(
    "data/laguna-s-2.1-shared-down-m8-counter-authorization-20260723.json"
)
AUTHORIZATION_PATH = MAIN_REPO / AUTHORIZATION_RELATIVE
COMPONENT_SUMMARY_RELATIVE = Path(
    "data/laguna-s-2.1-shared-down-m8-component-pass-20260723.json"
)
COMPONENT_SUMMARY = MAIN_REPO / COMPONENT_SUMMARY_RELATIVE
COMPONENT_AGGREGATE = Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/"
    "shared-down-m8-component-20260723T155703Z/aggregate.json"
)
ARTIFACT_ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
RUNS_ROOT = ARTIFACT_ROOT / "runs"
NVME_MOUNT = Path("/mnt/fast-ai")
NVME_SOURCE = "/dev/nvme0n1p2"
NVME_FSTYPE = "ext4"
VLLM_REPO = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
KERNEL_REPO = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
PTI_REPO = Path("/home/steve/src/pti-gpu")
UNITRACE = PTI_REPO / "build-unitrace/unitrace"
PYTHON = Path("/home/steve/.venvs/deepseek-v4-xpu/bin/python")
SUDO = Path("/usr/bin/sudo")
ENV = Path("/usr/bin/env")
XPU_SMI = Path("/usr/bin/xpu-smi")
TIMEOUT = Path("/usr/bin/timeout")
KILL = Path("/usr/bin/kill")
SUDO_PASSWORD_FILE = Path("/home/steve/SUDOPASSWORD.txt")
EXPECTED_HOST_TOOLS = {
    "sudo": {
        "path": str(SUDO),
        "sha256": ("136f2e48b0295b9fc595b8259cf2411ac43f27ddbfe02b956649ddaa2e92b9fa"),
    },
    "env": {
        "path": str(ENV),
        "sha256": ("0aefff8f912fb75716c5d4de3b6acde93edbe8fa280fc8ee895c1226d3e373ef"),
    },
    "timeout": {
        "path": str(TIMEOUT),
        "sha256": ("4fccd5b0192653a2446b745d5385ea547b78e466150e07ade9e2caff2b7f4e08"),
    },
    "xpu_smi": {
        "path": str(XPU_SMI),
        "sha256": ("2b5b128edf28b38da8637413fe8bfe3a4a40e8113210ba9ddaed945bd56d826e"),
    },
    "kill": {
        "path": str(KILL),
        "sha256": ("65ce2f8116bbafd0e82875d126d811d051a7aff3d0e732412c1fac9055f766dc"),
    },
}

EXPECTED_GATE_SHA256 = (
    "df8496f1f405e8b786dff0b96b7c320944c5d0133cce0bfcc2e36150ab1e0f12"
)
EXPECTED_COMPONENT_ANALYZER_SHA256 = (
    "945810c50eeeea99f532c3e62ee5bf289677e3706d80965f966400bfab35911b"
)
EXPECTED_COMPONENT_SUMMARY_SHA256 = (
    "4984b0b16c2e12f7fab95aa137e8d59cf0162a1f2074a6630ce12722c6fd67f7"
)
EXPECTED_COMPONENT_AGGREGATE_SHA256 = (
    "ea71971b368ce9b9e930577b673e983124b0e5686d5d780fc241ac4104f2a1d6"
)
EXPECTED_UNITRACE_SHA256 = (
    "5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a"
)
EXPECTED_PYTHON_SHA256 = (
    "202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8"
)
EXPECTED_TORCH_VERSION = "2.12.0+xpu"
TORCH_PACKAGE = Path(
    "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages/torch"
)
EXPECTED_TORCH_FILES = {
    "__init__": {
        "path": str(TORCH_PACKAGE / "__init__.py"),
        "sha256": ("d9dfff4b75d46e4c75572200a3466b70231d05b0318e38ac1bd121789165fb49"),
    },
    "_C": {
        "path": str(TORCH_PACKAGE / "_C.cpython-312-x86_64-linux-gnu.so"),
        "sha256": ("deff36272fed31705b74c8f1da372baaaf659c0229d3ce57daab8894e6dc7e84"),
    },
    "libtorch_xpu": {
        "path": str(TORCH_PACKAGE / "lib/libtorch_xpu.so"),
        "sha256": ("63b7a56723482bc35d31842f442f6e903ef0b7fbd741c1a4ae309123bbc90572"),
    },
    "libtorch_cpu": {
        "path": str(TORCH_PACKAGE / "lib/libtorch_cpu.so"),
        "sha256": ("bbf261729e5f190124060318435d9aa39cbb17a12377f2fb999ac6f531125315"),
    },
    "libtorch": {
        "path": str(TORCH_PACKAGE / "lib/libtorch.so"),
        "sha256": ("b5a183867725fb49b7262172c15f94d51fa1e393d34e43d4cdc5d328cd037ab6"),
    },
    "libc10": {
        "path": str(TORCH_PACKAGE / "lib/libc10.so"),
        "sha256": ("1231da9267e3d80bfb0affc3116fc88fff26fa201d83e0c41f46efb6d300736a"),
    },
    "libc10_xpu": {
        "path": str(TORCH_PACKAGE / "lib/libc10_xpu.so"),
        "sha256": ("7ab1b1f2ab4a25ea9364b614fe43f264b3d0eb0786a3af93be74f4769394df12"),
    },
}
EXPECTED_UNITRACE_COMMIT = "a5bab309f4ffdd78bd127035c46f5f75371160f8"
EXPECTED_VLLM_COMMIT = "75d4660463407975c16bd33711499ca560bf2034"
EXPECTED_KERNEL_COMMIT = "c59aaadbbfd350c2b5f4ad663e247c2811ae3181"
EXPECTED_BOOT_ID = "0b7f98a5-e50a-46a5-81ea-15938b55317a"
EXPECTED_DEVICE_NAME = "Intel(R) Arc(TM) Pro B70 Graphics"
EXPECTED_COMPONENT_FIXTURE_SHA256 = (
    "3e28840809747843474a15f7858db9b7d1d4d70b4fbe71c47c7a2aa117eeff90"
)
EXPECTED_COMPONENT_OUTPUT_SHA256 = (
    "ae8c34ea1bb5904466a702412a1ccc1f6843d3bed05e948f079e82647b4f33a7"
)
MODEL_CONFIG = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json")
EXPECTED_MODEL_CONFIG_SHA256 = (
    "9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6"
)
EXPECTED_RUNTIME_BINARIES = {
    "_C": {
        "path": str(KERNEL_REPO / "vllm_xpu_kernels/_C.abi3.so"),
        "sha256": ("126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2"),
    },
    "_xpu_C": {
        "path": str(KERNEL_REPO / "vllm_xpu_kernels/_xpu_C.abi3.so"),
        "sha256": ("f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8"),
    },
    "_moe_C": {
        "path": str(KERNEL_REPO / "vllm_xpu_kernels/_moe_C.abi3.so"),
        "sha256": ("0057b266d567731a9f9f592cefd9103bbf027ebb83c876d26c17ffb09994a3a0"),
    },
    "libgrouped_gemm_xe_2": {
        "path": str(KERNEL_REPO / "vllm_xpu_kernels/libgrouped_gemm_xe_2.so"),
        "sha256": ("fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96"),
    },
}
EXPECTED_PHYSICAL_DEVICES = {
    0: {
        "device_id": 0,
        "uuid": "00000000-0000-0023-0000-0000e2238086",
        "pci_bdf_address": "0000:23:00.0",
        "drm_device": "/dev/dri/card3",
    },
    1: {
        "device_id": 1,
        "uuid": "00000000-0000-0027-0000-0000e2238086",
        "pci_bdf_address": "0000:27:00.0",
        "drm_device": "/dev/dri/card4",
    },
    2: {
        "device_id": 2,
        "uuid": "00000000-0000-0043-0000-0000e2238086",
        "pci_bdf_address": "0000:43:00.0",
        "drm_device": "/dev/dri/card0",
    },
    3: {
        "device_id": 3,
        "uuid": "00000000-0000-0047-0000-0000e2238086",
        "pci_bdf_address": "0000:47:00.0",
        "drm_device": "/dev/dri/card2",
    },
}
RECORD_ENVIRONMENT = {
    "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "1",
    "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
    "VLLM_XPU_EXACT_SPEC_ATTN": "1",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
    "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
    "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
    "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
    "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
    "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
    "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
    "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
    "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0",
    "VLLM_XPU_ENABLE_XPU_GRAPH": "0",
    "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
    "VLLM_XPU_FORCE_GRAPH_WITH_COMM": "0",
    "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE": "0",
    "XPU_GRAPH": "0",
    "VLLM_USE_AOT_COMPILE": "0",
}
ARMS = ("A1", "B1", "B2", "A2")
RANKS = (0, 1, 2, 3)
CALLS = 13
DISCARDED_ROWS = (0, 1)
EVICTION_BYTES = 128 * 1024 * 1024
KERNEL_SELECTOR = "gemm_kernel"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_argument(value: str) -> str:
    normalized = value.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise argparse.ArgumentTypeError("expected a 64-digit SHA-256")
    return normalized


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return sha256_bytes(encoded)


def run_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def checked_stdout(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: int = 30,
) -> str:
    result = run_command(command, env=env, timeout=timeout)
    require(
        result.returncode == 0,
        f"command failed ({result.returncode}): {command!r}: {result.stderr.strip()}",
    )
    return result.stdout


def git_identity(repo: Path, *, require_clean: bool) -> dict[str, Any]:
    commit = checked_stdout(["git", "-C", str(repo), "rev-parse", "HEAD"]).strip()
    status_text = checked_stdout(
        [
            "git",
            "-C",
            str(repo),
            "status",
            "--porcelain=v1",
            "--untracked-files=all" if repo != PTI_REPO else "--untracked-files=no",
        ]
    )
    if require_clean:
        require(not status_text.strip(), f"dirty repository: {repo}")
    return {
        "path": str(repo),
        "commit": commit,
        "clean": not status_text.strip(),
        "status_sha256": sha256_bytes(status_text.encode()),
        "status_lines": status_text.splitlines(),
    }


def _decode_mount_field(value: str) -> str:
    return re.sub(
        r"\\([0-7]{3})",
        lambda match: chr(int(match.group(1), 8)),
        value,
    )


def local_nvme_mount_identity() -> dict[str, str]:
    candidates: list[tuple[int, str, str, str]] = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        before, separator, after = line.partition(" - ")
        require(bool(separator), "malformed /proc/self/mountinfo row")
        left = before.split()
        right = after.split()
        require(len(left) >= 6 and len(right) >= 2, "short mountinfo row")
        mount_point = _decode_mount_field(left[4])
        try:
            NVME_MOUNT.relative_to(Path(mount_point))
        except ValueError:
            continue
        candidates.append(
            (len(mount_point), mount_point, right[0], _decode_mount_field(right[1]))
        )
    require(bool(candidates), "no mount identity for /mnt/fast-ai")
    _length, mount_point, filesystem, source = max(candidates)
    require(
        filesystem == NVME_FSTYPE and source == NVME_SOURCE,
        "Laguna live artifact mount is not frozen NVMe/ext4",
    )
    require(
        ARTIFACT_ROOT.resolve() == ARTIFACT_ROOT
        and RUNS_ROOT.resolve() == RUNS_ROOT
        and os.stat(ARTIFACT_ROOT).st_dev == os.stat(NVME_MOUNT).st_dev,
        "Laguna artifact root resolved-path/device drift",
    )
    return {
        "target": str(NVME_MOUNT),
        "mount_point": mount_point,
        "source": source,
        "filesystem": filesystem,
    }


def atomic_exclusive_json(path: Path, value: dict[str, Any]) -> None:
    encoded = (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o644,
    )
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def write_bytes_exclusive(path: Path, data: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o644,
    )
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def expected_protocol() -> dict[str, Any]:
    return {
        "cards": list(RANKS),
        "card_order": "sequential",
        "arms_per_card": list(ARMS),
        "arm_treatments": {
            "A1": "control",
            "B1": "candidate",
            "B2": "candidate",
            "A2": "control",
        },
        "fresh_process_per_arm": True,
        "private_output_directory_per_arm": True,
        "selected_calls_per_arm": CALLS,
        "eviction_bytes_before_each_selected_call": EVICTION_BYTES,
        "completion_boundary_before_each_selected_call": True,
        "completion_boundary_after_each_selected_call": True,
        "discarded_selected_rows": list(DISCARDED_ROWS),
        "analyzed_selected_rows": CALLS - len(DISCARDED_ROWS),
        "fixture_epoch": 30_000,
        "fixture_rank_invariant": True,
        "unitrace": {
            "metric_group": "ComputeBasic",
            "metric_mode": "--metric-query",
            "device_timing": True,
            "kernel_selector": KERNEL_SELECTOR,
            "verbose_kernel_names": True,
            "pid_suffix": True,
            "device_to_sample": 0,
            "follow_child_process_flag_present": False,
            "output_prefix": "unitrace",
            "root_timeout_seconds": 180,
            "root_timeout_kill_after_seconds": 5,
            "runner_timeout_seconds": 200,
            "runner_timeout_process_group_term_seconds": 5,
            "runner_timeout_process_group_kill_seconds": 5,
            "argv_template": packet_command_template(),
        },
    }


def expected_acceptance() -> dict[str, Any]:
    return {
        "matched_pair_scope": "gpu-time-only",
        "both_matched_pair_candidate_gpu_times_lower_per_card": True,
        "per_card_aggregate_scope": "gpu-time-plus-full-metric-guardrails",
        "per_card_aggregate_candidate_gpu_time_lower": True,
        "global_four_card_aggregate_scope": "gpu-time-only",
        "global_four_card_aggregate_candidate_gpu_time_lower": True,
        "maximum_gpu_memory_read_regression_fraction": 0.02,
        "maximum_lsc_read_regression_fraction": 0.02,
        "maximum_xve_stall_increase_percentage_points": 0.5,
        "maximum_xve_active_decrease_percentage_points": 0.5,
        "maximum_thread_occupancy_decrease_percentage_points": 0.5,
        "all_validity_split_overrun_lost_inconsistent_proxies_zero": True,
        "spill_slm_partial_write_and_lsc_write_proxies_zero": True,
        "all_fixture_output_hashes_raw_exact": True,
    }


def expected_component_evidence() -> dict[str, Any]:
    return {
        "tracked_summary": {
            "path": str(COMPONENT_SUMMARY_RELATIVE),
            "sha256": EXPECTED_COMPONENT_SUMMARY_SHA256,
        },
        "aggregate": {
            "path": str(COMPONENT_AGGREGATE),
            "sha256": EXPECTED_COMPONENT_AGGREGATE_SHA256,
            "status": "component-passed-counter-tooling-freeze-next",
            "component_passed": True,
            "aggregate_fixture_sha256": EXPECTED_COMPONENT_FIXTURE_SHA256,
            "aggregate_output_sha256": EXPECTED_COMPONENT_OUTPUT_SHA256,
        },
    }


def expected_identities() -> dict[str, Any]:
    return {
        "boot_id": EXPECTED_BOOT_ID,
        "host_tools": EXPECTED_HOST_TOOLS,
        "model_config": {
            "path": str(MODEL_CONFIG),
            "sha256": EXPECTED_MODEL_CONFIG_SHA256,
        },
        "runtime_binaries": EXPECTED_RUNTIME_BINARIES,
        "vllm": {
            "path": str(VLLM_REPO),
            "commit": EXPECTED_VLLM_COMMIT,
        },
        "kernels": {
            "path": str(KERNEL_REPO),
            "commit": EXPECTED_KERNEL_COMMIT,
        },
        "unitrace_source": {
            "path": str(PTI_REPO),
            "commit": EXPECTED_UNITRACE_COMMIT,
        },
        "python": {
            "path": str(PYTHON),
            "sha256": EXPECTED_PYTHON_SHA256,
        },
        "torch": {
            "version": EXPECTED_TORCH_VERSION,
            "files": EXPECTED_TORCH_FILES,
        },
        "physical_devices": [EXPECTED_PHYSICAL_DEVICES[rank] for rank in RANKS],
        "record_environment": {
            **RECORD_ENVIRONMENT,
            "PYTHONPATH": f"{VLLM_REPO}:{KERNEL_REPO}",
        },
    }


def required_tool_paths() -> dict[str, Path]:
    return {
        "runner": RUNNER,
        "fixture": FIXTURE,
        "analyzer": ANALYZER,
        "counter_test": COUNTER_TEST,
        "gate": GATE,
        "component_analyzer": COMPONENT_ANALYZER,
        "unitrace": UNITRACE,
    }


def validate_component_evidence() -> None:
    require(
        sha256_file(COMPONENT_SUMMARY) == EXPECTED_COMPONENT_SUMMARY_SHA256,
        "tracked component summary SHA drift",
    )
    require(
        sha256_file(COMPONENT_AGGREGATE) == EXPECTED_COMPONENT_AGGREGATE_SHA256,
        "component aggregate SHA drift",
    )
    aggregate = json.loads(COMPONENT_AGGREGATE.read_text())
    expected_aggregate_checks = {
        "all_cards_recomputed_pass": True,
        "analyzer_main_matches_cards": True,
        "exact_declared_ranks": True,
        "four_distinct_physical_bdfs": True,
        "four_distinct_physical_uuids": True,
        "frozen_kernel_commit": True,
        "frozen_vllm_commit": True,
        "identical_fixture_aggregate": True,
        "identical_output_aggregate": True,
        "one_boot": True,
        "one_clean_main_commit": True,
    }
    require(
        aggregate.get("format") == "laguna-shared-down-mm-four-card-component-v2"
        and aggregate.get("status") == "component-passed-counter-tooling-freeze-next"
        and aggregate.get("passed") is True
        and aggregate.get("component_passed") is True
        and aggregate.get("counter_tooling_construction_authorized") is True
        and aggregate.get("counter_execution_authorized") is False
        and aggregate.get("counter_gate_evaluated") is False
        and aggregate.get("endpoint_authorized") is False
        and aggregate.get("model_generation_performed") is False
        and aggregate.get("aggregate_fixture_sha256")
        == EXPECTED_COMPONENT_FIXTURE_SHA256
        and aggregate.get("aggregate_output_sha256")
        == EXPECTED_COMPONENT_OUTPUT_SHA256,
        "component aggregate authorization/exactness contract drift",
    )
    require(
        aggregate.get("aggregate_checks") == expected_aggregate_checks
        and aggregate.get("declared_ranks") == list(RANKS)
        and aggregate.get("required_ranks") == list(RANKS)
        and aggregate.get("frozen_identity")
        == {
            "harness_sha256": EXPECTED_GATE_SHA256,
            "vllm_commit": EXPECTED_VLLM_COMMIT,
            "kernel_commit": EXPECTED_KERNEL_COMMIT,
            "binary_sha256": {
                name: value["sha256"]
                for name, value in EXPECTED_RUNTIME_BINARIES.items()
            },
        }
        and aggregate.get("analyzer", {}).get("path") == str(COMPONENT_ANALYZER)
        and aggregate.get("analyzer", {}).get("sha256")
        == EXPECTED_COMPONENT_ANALYZER_SHA256
        and aggregate.get("analyzer", {}).get("expected_sha256")
        == EXPECTED_COMPONENT_ANALYZER_SHA256,
        "component aggregate recomputation/source contract drift",
    )
    cards = aggregate.get("cards")
    require(
        isinstance(cards, list) and len(cards) == len(RANKS),
        "component aggregate card closure drift",
    )
    for rank, card in zip(RANKS, cards, strict=True):
        expected_path = COMPONENT_AGGREGATE.parent / f"card{rank}.json"
        expected_device = EXPECTED_PHYSICAL_DEVICES[rank]
        require(
            isinstance(card, dict)
            and card.get("rank") == rank
            and card.get("path") == str(expected_path)
            and isinstance(card.get("sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", card["sha256"]) is not None
            and expected_path.is_file()
            and not expected_path.is_symlink()
            and sha256_file(expected_path) == card["sha256"]
            and card.get("passed") is True
            and card.get("boot_id") == EXPECTED_BOOT_ID
            and card.get("physical_uuid") == expected_device["uuid"]
            and card.get("physical_bdf") == expected_device["pci_bdf_address"]
            and card.get("vllm_commit") == EXPECTED_VLLM_COMMIT
            and card.get("kernel_commit") == EXPECTED_KERNEL_COMMIT
            and card.get("aggregate_fixture_sha256")
            == EXPECTED_COMPONENT_FIXTURE_SHA256
            and card.get("aggregate_output_sha256") == EXPECTED_COMPONENT_OUTPUT_SHA256,
            f"component card {rank} closure drift",
        )


def validate_authorization(
    path: Path,
    expected_sha256: str,
) -> tuple[dict[str, Any], str]:
    require(
        path.is_absolute()
        and not path.is_symlink()
        and path.resolve(strict=True) == AUTHORIZATION_PATH,
        "authorization must be the exact tracked counter packet path",
    )
    packet_sha256 = sha256_file(path)
    require(packet_sha256 == expected_sha256, "authorization packet SHA mismatch")

    main_identity = git_identity(MAIN_REPO, require_clean=True)
    tracked = run_command(
        [
            "git",
            "-C",
            str(MAIN_REPO),
            "ls-files",
            "--error-unmatch",
            str(AUTHORIZATION_RELATIVE),
        ]
    )
    require(tracked.returncode == 0, "authorization packet is not Git tracked")
    committed_bytes = subprocess.run(
        [
            "git",
            "-C",
            str(MAIN_REPO),
            "show",
            f"HEAD:{AUTHORIZATION_RELATIVE}",
        ],
        check=True,
        capture_output=True,
    ).stdout
    require(
        committed_bytes == path.read_bytes(),
        "authorization packet differs from committed HEAD bytes",
    )

    packet = json.loads(path.read_text())
    require(
        set(packet)
        == {
            "format",
            "created_utc",
            "experiment",
            "component_evidence",
            "identities",
            "tools",
            "protocol",
            "acceptance",
            "authorization",
        },
        "authorization packet top-level schema drift",
    )
    require(
        packet.get("format")
        == "laguna-shared-down-m8-counter-execution-authorization-v1"
        and packet.get("experiment")
        == {
            "model": "poolside/Laguna-S-2.1-INT4",
            "treatment": "shared-expert down projection native M=8 BF16 MM only",
            "selector": "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=1",
        }
        and packet.get("component_evidence") == expected_component_evidence()
        and packet.get("identities") == expected_identities()
        and packet.get("protocol") == expected_protocol()
        and packet.get("acceptance") == expected_acceptance()
        and packet.get("authorization")
        == {
            "component_passed": True,
            "counter_tooling_construction_authorized": True,
            "counter_execution_authorized": True,
            "counter_gate_evaluated": False,
            "endpoint_preregistration_construction_authorized": False,
            "endpoint_authorized": False,
            "model_generation_authorized": False,
            "model_generation_performed": False,
            "payload_created": False,
            "localmaxxing_submission_authorized": False,
            "localmaxxing_submission_made": False,
        },
        "authorization packet frozen contract drift",
    )
    tools = packet.get("tools")
    required_paths = required_tool_paths()
    require(
        isinstance(tools, dict) and set(tools) == set(required_paths),
        "authorization tool set drift",
    )
    for name, tool_path in required_paths.items():
        entry = tools.get(name)
        require(
            isinstance(entry, dict)
            and set(entry) == {"path", "sha256"}
            and entry.get("path") == str(tool_path)
            and isinstance(entry.get("sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
            and tool_path.is_file()
            and sha256_file(tool_path) == entry["sha256"],
            f"authorization tool identity drift: {name}",
        )
    require(
        tools["gate"]["sha256"] == EXPECTED_GATE_SHA256
        and tools["component_analyzer"]["sha256"] == EXPECTED_COMPONENT_ANALYZER_SHA256
        and tools["unitrace"]["sha256"] == EXPECTED_UNITRACE_SHA256,
        "immutable gate/component/unitrace identity drift",
    )
    require(
        main_identity["clean"] is True,
        "main repository must remain clean after authorization validation",
    )
    validate_component_evidence()
    return packet, packet_sha256


def source_preflight(packet: dict[str, Any]) -> dict[str, Any]:
    repositories = {
        "main": git_identity(MAIN_REPO, require_clean=True),
        "vllm": git_identity(VLLM_REPO, require_clean=True),
        "kernels": git_identity(KERNEL_REPO, require_clean=True),
        "unitrace_source": git_identity(PTI_REPO, require_clean=True),
    }
    require(
        repositories["vllm"]["commit"] == EXPECTED_VLLM_COMMIT
        and repositories["kernels"]["commit"] == EXPECTED_KERNEL_COMMIT
        and repositories["unitrace_source"]["commit"] == EXPECTED_UNITRACE_COMMIT,
        "source commit drift",
    )
    require(
        sha256_file(MODEL_CONFIG) == EXPECTED_MODEL_CONFIG_SHA256,
        "model config SHA drift",
    )
    for name, expected in EXPECTED_RUNTIME_BINARIES.items():
        binary_path = Path(expected["path"])
        require(
            binary_path.is_file() and sha256_file(binary_path) == expected["sha256"],
            f"runtime binary SHA drift: {name}",
        )
    require(
        PYTHON.is_file() and sha256_file(PYTHON) == EXPECTED_PYTHON_SHA256,
        "Python interpreter SHA drift",
    )
    for name, expected in EXPECTED_HOST_TOOLS.items():
        host_tool = Path(expected["path"])
        require(
            host_tool.is_file() and sha256_file(host_tool) == expected["sha256"],
            f"host tool SHA drift: {name}",
        )
    for name, expected in EXPECTED_TORCH_FILES.items():
        torch_path = Path(expected["path"])
        require(
            torch_path.is_file() and sha256_file(torch_path) == expected["sha256"],
            f"Torch/XPU runtime file SHA drift: {name}",
        )
    current_tools = {
        name: {
            "path": str(path),
            "sha256": sha256_file(path),
        }
        for name, path in required_tool_paths().items()
    }
    require(current_tools == packet["tools"], "tool bytes drift after authorization")
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    kernel_taint = Path("/proc/sys/kernel/tainted").read_text().strip()
    require(boot_id == EXPECTED_BOOT_ID, f"boot identity drift: {boot_id}")
    require(kernel_taint == "0", f"kernel taint drift: {kernel_taint}")
    return {
        "captured_utc": utc_now(),
        "repositories": repositories,
        "tools": current_tools,
        "python": expected_identities()["python"],
        "torch": expected_identities()["torch"],
        "host_tools": expected_identities()["host_tools"],
        "boot_id": boot_id,
        "kernel_taint": kernel_taint,
    }


def xpu_environment(rank: int | None) -> dict[str, str]:
    environment = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if rank is not None:
        environment["ZE_AFFINITY_MASK"] = str(rank)
        environment["ONEAPI_DEVICE_SELECTOR"] = "level_zero:0"
    return environment


def xpu_discovery(rank: int) -> dict[str, Any]:
    filtered_text = checked_stdout(
        [str(XPU_SMI), "discovery", "-j"],
        env=xpu_environment(rank),
        timeout=15,
    )
    unfiltered_text = checked_stdout(
        [str(XPU_SMI), "discovery", "-j"],
        env=xpu_environment(None),
        timeout=15,
    )
    filtered = json.loads(filtered_text)
    unfiltered = json.loads(unfiltered_text)
    filtered_devices = filtered.get("device_list")
    unfiltered_devices = unfiltered.get("device_list")
    require(
        isinstance(filtered_devices, list) and len(filtered_devices) == 1,
        "affinity-filtered discovery must expose one device",
    )
    require(
        isinstance(unfiltered_devices, list) and len(unfiltered_devices) == 4,
        "unfiltered discovery must expose four devices",
    )
    visible = filtered_devices[0]
    physical = next(
        (
            device
            for device in unfiltered_devices
            if isinstance(device, dict) and device.get("device_id") == rank
        ),
        None,
    )
    expected = EXPECTED_PHYSICAL_DEVICES[rank]
    require(
        isinstance(visible, dict)
        and visible.get("device_id") == 0
        and isinstance(physical, dict),
        "filtered/unfiltered physical-device binding is malformed",
    )
    for field, expected_value in expected.items():
        require(
            physical.get(field) == expected_value,
            f"physical rank {rank} {field} drift",
        )
    for field in ("uuid", "pci_bdf_address", "drm_device", "device_name"):
        require(
            visible.get(field) == physical.get(field),
            f"filtered rank {rank} {field} binding drift",
        )
    require(
        visible.get("device_name") == EXPECTED_DEVICE_NAME,
        f"physical rank {rank} device-name drift",
    )
    return {
        "rank": rank,
        "expected": expected,
        "filtered": filtered,
        "unfiltered": unfiltered,
        "uuid_bdf_binding_exact": True,
        "filtered_sha256": sha256_bytes(filtered_text.encode()),
        "unfiltered_sha256": sha256_bytes(unfiltered_text.encode()),
    }


def xpu_idle_proof() -> dict[str, Any]:
    text = checked_stdout(
        [str(XPU_SMI), "ps"],
        env=xpu_environment(None),
        timeout=15,
    )
    lines = [line.split() for line in text.splitlines() if line.strip()]
    require(
        bool(lines) and lines[0][:5] == ["PID", "Command", "DeviceID", "SHR", "MEM"],
        "invalid xpu-smi ps header",
    )
    rows = lines[1:]
    require(len(rows) == 4, f"expected four xpu-smi self rows, got {len(rows)}")
    seen: dict[int, int] = {}
    for row in rows:
        require(len(row) >= 5, "short xpu-smi ps row")
        require(row[1] == "xpu-smi", f"non-idle XPU client observed: {row}")
        require(re.fullmatch(r"[0-3]", row[2]) is not None, "bad XPU device id")
        device = int(row[2])
        seen[device] = seen.get(device, 0) + 1
    require(
        seen == {0: 1, 1: 1, 2: 1, 3: 1},
        f"xpu-smi idle self-row mapping drift: {seen}",
    )
    return {
        "passed": True,
        "captured_utc": utc_now(),
        "sha256": sha256_bytes(text.encode()),
        "text": text,
        "rows": len(rows),
        "only_xpu_smi_self_rows": True,
    }


def verify_sudo_password_file() -> dict[str, Any]:
    require(
        SUDO_PASSWORD_FILE.is_file() and not SUDO_PASSWORD_FILE.is_symlink(),
        "sudo password file path/type drift",
    )
    metadata = SUDO_PASSWORD_FILE.stat()
    require(
        stat.S_IMODE(metadata.st_mode) == 0o600,
        "sudo password file must be owner-only mode 0600",
    )
    require(
        metadata.st_uid == os.getuid() and metadata.st_size > 0,
        "sudo password file owner/size drift",
    )
    return {
        "path": str(SUDO_PASSWORD_FILE),
        "mode": "0600",
        "uid": metadata.st_uid,
        "regular_file": True,
        "content_not_recorded": True,
    }


def arm_runtime_paths(arm_dir: Path) -> dict[str, Path]:
    return {
        "HOME": arm_dir / "runtime/home",
        "TMPDIR": arm_dir / "runtime/tmp",
        "TMP": arm_dir / "runtime/tmp",
        "TEMP": arm_dir / "runtime/tmp",
        "XDG_CACHE_HOME": arm_dir / "runtime/cache/xdg",
        "XDG_CONFIG_HOME": arm_dir / "runtime/cache/xdg-config",
        "XDG_DATA_HOME": arm_dir / "runtime/cache/xdg-data",
        "XDG_STATE_HOME": arm_dir / "runtime/cache/xdg-state",
        "SYCL_CACHE_DIR": arm_dir / "runtime/cache/sycl",
        "TORCHINDUCTOR_CACHE_DIR": arm_dir / "runtime/cache/torchinductor",
        "TRITON_CACHE_DIR": arm_dir / "runtime/cache/triton",
        "NUMBA_CACHE_DIR": arm_dir / "runtime/cache/numba",
        "HF_HOME": arm_dir / "runtime/cache/huggingface",
        "TRANSFORMERS_CACHE": arm_dir / "runtime/cache/transformers",
        "VLLM_CACHE_ROOT": arm_dir / "runtime/cache/vllm",
        "PYTHONPYCACHEPREFIX": arm_dir / "runtime/cache/pycache",
    }


def child_environment_assignments(rank: int, arm_dir: Path) -> list[str]:
    values = {
        **RECORD_ENVIRONMENT,
        "ZE_AFFINITY_MASK": str(rank),
        "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
        "PYTHONPATH": f"{VLLM_REPO}:{KERNEL_REPO}",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }
    values.update(
        {name: str(path) for name, path in arm_runtime_paths(arm_dir).items()}
    )
    return [f"{name}={values[name]}" for name in sorted(values)]


def build_unitrace_command(
    *,
    rank: int,
    arm: str,
    arm_dir: Path,
    fixture_sha256: str,
) -> list[str]:
    treatment = "control" if arm.startswith("A") else "candidate"
    fixture_output = arm_dir / "fixture.json"
    return [
        str(SUDO),
        "-S",
        "-p",
        "",
        "-E",
        "--",
        str(ENV),
        "-i",
        *child_environment_assignments(rank, arm_dir),
        str(TIMEOUT),
        "--signal=TERM",
        "--kill-after=5s",
        "180s",
        str(UNITRACE),
        "--device-timing",
        "--metric-query",
        "--group",
        "ComputeBasic",
        "--include-kernels",
        KERNEL_SELECTOR,
        "--verbose",
        "--pid",
        "--devices-to-sample",
        "0",
        "--output",
        "unitrace",
        str(PYTHON),
        str(FIXTURE),
        "--rank",
        str(rank),
        "--arm",
        treatment,
        "--expected-fixture-sha256",
        fixture_sha256,
        "--out",
        str(fixture_output),
    ]


def packet_command_template() -> list[str]:
    arm_dir = Path("{arm_dir}")
    template = build_unitrace_command(
        rank=0,
        arm="A1",
        arm_dir=arm_dir,
        fixture_sha256="{fixture_sha256}",
    )
    template = [
        value.replace("ZE_AFFINITY_MASK=0", "ZE_AFFINITY_MASK={rank}")
        for value in template
    ]
    template[template.index("--rank") + 1] = "{rank}"
    template[template.index("--arm") + 1] = "{treatment}"
    return template


def validate_packet_command_template(packet: dict[str, Any]) -> None:
    template = packet["protocol"]["unitrace"].get("argv_template")
    expected = packet_command_template()
    require(template == expected, "unitrace argv template drift")


def profiler_outputs(arm_dir: Path) -> tuple[Path, Path, str]:
    names = sorted(
        path.name
        for path in arm_dir.iterdir()
        if path.is_file() and path.name.startswith("unitrace")
    )
    require(len(names) == 2, f"expected two unitrace output files, got {names}")
    timing_matches = [re.fullmatch(r"unitrace\.([0-9]+)", name) for name in names]
    metric_matches = [
        re.fullmatch(r"unitrace\.metrics\.([0-9]+)", name) for name in names
    ]
    timing = [match for match in timing_matches if match is not None]
    metrics = [match for match in metric_matches if match is not None]
    require(
        len(timing) == len(metrics) == 1 and timing[0].group(1) == metrics[0].group(1),
        f"unitrace timing/metrics PID suffix mismatch: {names}",
    )
    suffix = timing[0].group(1)
    timing_path = arm_dir / f"unitrace.{suffix}"
    metrics_path = arm_dir / f"unitrace.metrics.{suffix}"
    require(
        timing_path.is_file()
        and metrics_path.is_file()
        and not timing_path.is_symlink()
        and not metrics_path.is_symlink(),
        "unitrace outputs are missing, nonregular, or symlinked",
    )
    return timing_path, metrics_path, suffix


def process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def signal_process_group(
    process_group_id: int,
    signal_number: signal.Signals,
    *,
    sudo_password_file: Path | None,
) -> None:
    try:
        os.killpg(process_group_id, signal_number)
        return
    except ProcessLookupError:
        return
    except PermissionError:
        require(
            sudo_password_file is not None,
            "process group requires privileged cleanup but no sudo input is pinned",
        )
    signal_name = signal_number.name.removeprefix("SIG")
    with sudo_password_file.open("rb") as password_handle:
        cleanup = subprocess.run(
            [
                str(SUDO),
                "-S",
                "-p",
                "",
                "--",
                str(KILL),
                "--signal",
                signal_name,
                "--",
                f"-{process_group_id}",
            ],
            stdin=password_handle,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=xpu_environment(None),
            check=False,
            timeout=10,
        )
    require(
        cleanup.returncode == 0 or not process_group_exists(process_group_id),
        "privileged process-group cleanup failed",
    )


def run_bounded_process_group(
    command: list[str],
    *,
    stdin_path: Path | None,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: float,
    term_grace_seconds: float,
    kill_grace_seconds: float,
) -> tuple[bytes, bytes, int]:
    input_path = stdin_path if stdin_path is not None else Path(os.devnull)
    with input_path.open("rb") as input_handle:
        process = subprocess.Popen(
            command,
            stdin=input_handle,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            start_new_session=True,
        )
        process_group_id = os.getpgid(process.pid)
        require(
            process_group_id == process.pid,
            "profiler supervisor did not create a private process group",
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            require(
                process.returncode is not None, "profiler supervisor was not reaped"
            )
            return stdout, stderr, process.returncode
        except subprocess.TimeoutExpired:
            signal_process_group(
                process_group_id,
                signal.SIGTERM,
                sudo_password_file=stdin_path,
            )
            try:
                stdout, stderr = process.communicate(timeout=term_grace_seconds)
            except subprocess.TimeoutExpired:
                signal_process_group(
                    process_group_id,
                    signal.SIGKILL,
                    sudo_password_file=stdin_path,
                )
                stdout, stderr = process.communicate(timeout=kill_grace_seconds)
            if process_group_exists(process_group_id):
                signal_process_group(
                    process_group_id,
                    signal.SIGKILL,
                    sudo_password_file=stdin_path,
                )
            deadline = time.monotonic() + kill_grace_seconds
            while (
                process_group_exists(process_group_id) and time.monotonic() < deadline
            ):
                time.sleep(0.02)
            require(
                not process_group_exists(process_group_id),
                "outer-timeout process group survived TERM/KILL cleanup",
            )
            require(process.poll() is not None, "timed-out supervisor was not reaped")
            return stdout, stderr, 124


def run_arm(
    *,
    root: Path,
    rank: int,
    arm: str,
    packet: dict[str, Any],
    packet_sha256: str,
    protocol_sha256: str,
) -> dict[str, Any]:
    treatment = "control" if arm.startswith("A") else "candidate"
    arm_dir = root / f"card{rank}" / arm
    arm_dir.mkdir(parents=True, mode=0o700)
    for runtime_path in set(arm_runtime_paths(arm_dir).values()):
        runtime_path.mkdir(parents=True, mode=0o700, exist_ok=True)

    preflight_path = arm_dir / "preflight.json"
    try:
        preflight = {
            "format": "laguna-shared-down-mm-counter-arm-preflight-v1",
            "status": "passed",
            "captured_utc": utc_now(),
            "rank": rank,
            "arm": arm,
            "treatment": treatment,
            "authorization_path": str(AUTHORIZATION_PATH),
            "authorization_sha256": packet_sha256,
            "protocol_sha256": protocol_sha256,
            "source": source_preflight(packet),
            "physical_device": xpu_discovery(rank),
            "idle": xpu_idle_proof(),
            "mount": local_nvme_mount_identity(),
            "sudo_password_file": verify_sudo_password_file(),
        }
        atomic_exclusive_json(preflight_path, preflight)
    except Exception as error:
        atomic_exclusive_json(
            arm_dir / "arm.error.json",
            {
                "format": "laguna-shared-down-mm-counter-arm-error-v1",
                "status": "preflight-error",
                "failed_utc": utc_now(),
                "rank": rank,
                "arm": arm,
                "treatment": treatment,
                "authorization_path": str(AUTHORIZATION_PATH),
                "authorization_sha256": packet_sha256,
                "protocol_sha256": protocol_sha256,
                "stage": "source-device-idle-preflight",
                "error": repr(error),
                "counter_execution_performed": False,
                "counter_gate_evaluated": False,
                "endpoint_authorized": False,
                "model_generation_performed": False,
                "payload_created": False,
                "localmaxxing_submission_made": False,
            },
        )
        raise

    fixture_sha256 = packet["tools"]["fixture"]["sha256"]
    command = build_unitrace_command(
        rank=rank,
        arm=arm,
        arm_dir=arm_dir,
        fixture_sha256=fixture_sha256,
    )
    outer_environment = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    stdout_path = arm_dir / "stdout.log"
    stderr_path = arm_dir / "stderr.log"
    stdout = b""
    stderr = b""
    returncode: int | None = None
    try:
        stdout, stderr, returncode = run_bounded_process_group(
            command,
            stdin_path=SUDO_PASSWORD_FILE,
            cwd=arm_dir,
            env=outer_environment,
            timeout_seconds=200,
            term_grace_seconds=5,
            kill_grace_seconds=5,
        )
        write_bytes_exclusive(stdout_path, stdout)
        write_bytes_exclusive(stderr_path, stderr)
        fixture_path = arm_dir / "fixture.json"
        require(returncode == 0, f"unitrace arm exited {returncode}")
        require(
            fixture_path.is_file() and not fixture_path.is_symlink(),
            "fixture evidence missing or symlinked",
        )
        timing_path, metrics_path, pid_suffix = profiler_outputs(arm_dir)
        fixture = json.loads(fixture_path.read_text())
        require(
            fixture.get("status") == "fixture-complete"
            and fixture.get("rank") == rank
            and fixture.get("arm") == treatment,
            "fixture rank/treatment/status drift",
        )
        require(
            isinstance(fixture.get("identity"), dict)
            and isinstance(fixture["identity"].get("pid"), int)
            and str(fixture["identity"]["pid"]) == pid_suffix,
            "unitrace output PID suffix does not bind the fixture process",
        )
        evidence_files = (
            preflight_path,
            stdout_path,
            stderr_path,
            fixture_path,
            timing_path,
            metrics_path,
        )
        files = {
            path.name: {
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in evidence_files
        }
        manifest: dict[str, Any] = {
            "format": "laguna-shared-down-mm-counter-arm-manifest-v1",
            "status": "complete",
            "completed_utc": utc_now(),
            "rank": rank,
            "arm": arm,
            "treatment": treatment,
            "authorization_path": str(AUTHORIZATION_PATH),
            "authorization_sha256": packet_sha256,
            "protocol_sha256": protocol_sha256,
            "command": command,
            "cwd": str(arm_dir),
            "returncode": returncode,
            "unitrace_output_pid_suffix": pid_suffix,
            "runtime_subtree": {
                "path": str(arm_dir / "runtime"),
                "evidence_file_hashing_excluded": True,
                "reason": "fresh per-arm compiler/cache/temp contents are non-counter evidence",
                "required_directories": {
                    name: str(path) for name, path in arm_runtime_paths(arm_dir).items()
                },
            },
            "files": files,
            "fixture": fixture,
            "counter_execution_performed": True,
            "counter_gate_evaluated": False,
            "endpoint_preregistration_construction_authorized": False,
            "endpoint_authorized": False,
            "model_generation_performed": False,
            "payload_created": False,
            "localmaxxing_submission_made": False,
        }
        manifest_path = arm_dir / "manifest.json"
        atomic_exclusive_json(manifest_path, manifest)
        return {
            "rank": rank,
            "arm": arm,
            "treatment": treatment,
            "path": str(manifest_path),
            "sha256": sha256_file(manifest_path),
        }
    except Exception as error:
        for log_path, content in (
            (stdout_path, stdout),
            (stderr_path, stderr),
        ):
            if not log_path.exists():
                try:
                    write_bytes_exclusive(log_path, content)
                except OSError:
                    pass
        try:
            post_failure_idle: dict[str, Any] = {
                "status": "idle",
                "evidence": xpu_idle_proof(),
            }
        except Exception as idle_error:
            post_failure_idle = {
                "status": "not-idle-or-unavailable",
                "error": repr(idle_error),
            }
        error_path = arm_dir / "arm.error.json"
        error_payload = {
            "format": "laguna-shared-down-mm-counter-arm-error-v1",
            "status": "partial-error",
            "failed_utc": utc_now(),
            "rank": rank,
            "arm": arm,
            "treatment": treatment,
            "authorization_path": str(AUTHORIZATION_PATH),
            "authorization_sha256": packet_sha256,
            "protocol_sha256": protocol_sha256,
            "command": command,
            "cwd": str(arm_dir),
            "returncode": returncode,
            "error": repr(error),
            "post_failure_idle": post_failure_idle,
            "preserved_files": {
                path.name: sha256_file(path)
                for path in sorted(arm_dir.iterdir())
                if path.is_file()
            },
            "counter_execution_performed": returncode is not None,
            "counter_gate_evaluated": False,
            "endpoint_authorized": False,
            "model_generation_performed": False,
            "payload_created": False,
            "localmaxxing_submission_made": False,
        }
        atomic_exclusive_json(error_path, error_payload)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--authorization-json", type=Path, required=True)
    parser.add_argument(
        "--expected-authorization-sha256",
        type=sha256_argument,
        required=True,
    )
    args = parser.parse_args()

    packet, packet_sha256 = validate_authorization(
        args.authorization_json,
        args.expected_authorization_sha256,
    )
    validate_packet_command_template(packet)
    mount = local_nvme_mount_identity()
    verify_sudo_password_file()
    source = source_preflight(packet)

    root = args.campaign_root
    require(root.is_absolute(), "campaign root must be absolute")
    require(
        re.fullmatch(
            r"shared-down-m8-counters-[0-9]{8}T[0-9]{6}Z",
            root.name,
        )
        is not None,
        "campaign root basename must be a frozen UTC timestamp form",
    )
    resolved_root = root.resolve(strict=False)
    require(
        resolved_root == root
        and resolved_root.parent == RUNS_ROOT
        and not root.exists()
        and not root.is_symlink(),
        "campaign root must be a new direct child of the local-NVMe runs root",
    )
    root.mkdir(mode=0o755)
    protocol_sha256 = canonical_sha256(packet["protocol"])
    open_manifest: dict[str, Any] = {
        "format": "laguna-shared-down-mm-counter-campaign-open-v1",
        "status": "open",
        "created_utc": utc_now(),
        "campaign_root": str(root),
        "authorization_path": str(AUTHORIZATION_PATH),
        "authorization_sha256": packet_sha256,
        "authorization": packet["authorization"],
        "protocol": packet["protocol"],
        "protocol_sha256": protocol_sha256,
        "acceptance": packet["acceptance"],
        "tools": packet["tools"],
        "component_evidence": packet["component_evidence"],
        "source": source,
        "mount": mount,
        "planned_cards": list(RANKS),
        "planned_arms_per_card": list(ARMS),
        "counter_execution_performed": False,
        "counter_gate_evaluated": False,
        "endpoint_preregistration_construction_authorized": False,
        "endpoint_authorized": False,
        "model_generation_performed": False,
        "payload_created": False,
        "localmaxxing_submission_made": False,
    }
    open_path = root / "campaign.open.json"
    atomic_exclusive_json(open_path, open_manifest)

    arm_manifests: list[dict[str, Any]] = []
    card_manifests: list[dict[str, Any]] = []
    try:
        for rank in RANKS:
            card_arms: list[dict[str, Any]] = []
            for arm in ARMS:
                arm_entry = run_arm(
                    root=root,
                    rank=rank,
                    arm=arm,
                    packet=packet,
                    packet_sha256=packet_sha256,
                    protocol_sha256=protocol_sha256,
                )
                arm_manifests.append(arm_entry)
                card_arms.append(arm_entry)
            card_path = root / f"card{rank}" / "card.manifest.json"
            card_payload = {
                "format": "laguna-shared-down-mm-counter-card-manifest-v1",
                "status": "complete",
                "completed_utc": utc_now(),
                "rank": rank,
                "authorization_sha256": packet_sha256,
                "protocol_sha256": protocol_sha256,
                "arms": card_arms,
                "counter_execution_performed": True,
                "counter_gate_evaluated": False,
                "endpoint_preregistration_construction_authorized": False,
                "endpoint_authorized": False,
                "model_generation_performed": False,
                "payload_created": False,
                "localmaxxing_submission_made": False,
            }
            atomic_exclusive_json(card_path, card_payload)
            card_manifests.append(
                {
                    "rank": rank,
                    "path": str(card_path),
                    "sha256": sha256_file(card_path),
                }
            )

        complete_path = root / "campaign.complete.json"
        complete_payload = {
            "format": "laguna-shared-down-mm-counter-campaign-complete-v1",
            "status": "complete",
            "completed_utc": utc_now(),
            "campaign_root": str(root),
            "authorization_path": str(AUTHORIZATION_PATH),
            "authorization_sha256": packet_sha256,
            "protocol_sha256": protocol_sha256,
            "campaign_open": {
                "path": str(open_path),
                "sha256": sha256_file(open_path),
            },
            "cards": card_manifests,
            "arms": arm_manifests,
            "counter_execution_performed": True,
            "counter_gate_evaluated": False,
            "endpoint_preregistration_construction_authorized": False,
            "endpoint_authorized": False,
            "model_generation_performed": False,
            "payload_created": False,
            "localmaxxing_submission_made": False,
        }
        atomic_exclusive_json(complete_path, complete_payload)
        print(
            json.dumps(
                {
                    "status": "complete",
                    "campaign_root": str(root),
                    "campaign_complete_sha256": sha256_file(complete_path),
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:
        error_path = root / "campaign.error.json"
        error_payload = {
            "format": "laguna-shared-down-mm-counter-campaign-error-v1",
            "status": "partial-error",
            "failed_utc": utc_now(),
            "campaign_root": str(root),
            "authorization_path": str(AUTHORIZATION_PATH),
            "authorization_sha256": packet_sha256,
            "protocol_sha256": protocol_sha256,
            "campaign_open": {
                "path": str(open_path),
                "sha256": sha256_file(open_path),
            },
            "completed_cards": card_manifests,
            "completed_arms": arm_manifests,
            "error": repr(error),
            "counter_gate_evaluated": False,
            "endpoint_authorized": False,
            "model_generation_performed": False,
            "payload_created": False,
            "localmaxxing_submission_made": False,
        }
        atomic_exclusive_json(error_path, error_payload)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
