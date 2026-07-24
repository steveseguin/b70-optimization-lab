#!/usr/bin/env python3
"""CPU-only authority packet builder for Laguna gate+up cold counters.

This is the authoritative shared contract for the later runner and analyzer.
It never imports torch, starts unitrace, enumerates an XPU, or creates a
campaign root; it only durably creates one previously absent packet under data/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAIN = Path("/home/steve/llm-optimizations")
TOOLS = MAIN / "experiments/laguna-s-2.1-xpu-b70/tools"
ARTIFACT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
RUNS = ARTIFACT / "runs"
COMPONENT_ROOT = RUNS / "shared-gate-up-m8-component-4cef996c9-20260724T051216Z"
COMPONENT_MANIFEST = COMPONENT_ROOT / "component-final-manifest.json"
COMPONENT_SUMMARY = (
    MAIN / "data/laguna-s-2.1-shared-gate-up-m8-component-pass-20260724.json"
)
CONTRACT_NOTE = (
    TOOLS.parent
    / "notes/2026-07-24-shared-gate-up-native-m8-mm-counter-tooling-contract.md"
)
MODEL_CONFIG = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json")
VLLM = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
KERNELS = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
PTI = Path("/home/steve/src/pti-gpu")
UNITRACE = PTI / "build-unitrace/unitrace"

EXPECTED = {
    "component_manifest_sha256": "8aa2a45a8bcc31c5d2e84e5f55568ad43144ebd6c380d6d914cf91f77d10a10d",
    "component_summary_sha256": "59f2427875283e540fcd7ebe5f679bb2ea6acff2aac868771026e1c692e2d15a",
    "component_summary_commit": "4c673235149659d232a52143f9eded33997c44d7",
    "tooling_note_sha256": "68bb6a4ba34f48c383cee3c33525acdd17f1fde5d4c5b456e9b6da866a0d5542",
    "vllm_commit": "503f7784cf9d1704109b1e4650427fb4f417d604",
    "kernel_commit": "c59aaadbbfd350c2b5f4ad663e247c2811ae3181",
    "pti_commit": "a5bab309f4ffdd78bd127035c46f5f75371160f8",
    "unitrace_sha256": "5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a",
    "boot_id": "0b7f98a5-e50a-46a5-81ea-15938b55317a",
    "model_config_sha256": "9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6",
    "nvme_source": "/dev/nvme0n1p2",
    "nvme_fstype": "ext4",
    "metric_header_sha256": "2f1add0fd583d68e3f9dfe9cd34577f25de4aff28e0a2c203ccaab1c567ce438",
}
CARDS = [
    {
        "rank": 0,
        "uuid": "00000000-0000-0023-0000-0000e2238086",
        "pci_bdf_address": "0000:23:00.0",
        "drm_device": "/dev/dri/card3",
        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
    },
    {
        "rank": 1,
        "uuid": "00000000-0000-0027-0000-0000e2238086",
        "pci_bdf_address": "0000:27:00.0",
        "drm_device": "/dev/dri/card4",
        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
    },
    {
        "rank": 2,
        "uuid": "00000000-0000-0043-0000-0000e2238086",
        "pci_bdf_address": "0000:43:00.0",
        "drm_device": "/dev/dri/card0",
        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
    },
    {
        "rank": 3,
        "uuid": "00000000-0000-0047-0000-0000e2238086",
        "pci_bdf_address": "0000:47:00.0",
        "drm_device": "/dev/dri/card2",
        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
    },
]
RUNTIME_FILES = {
    "python": Path("/home/steve/.venvs/deepseek-v4-xpu/bin/python"),
    "libtorch_xpu": Path(
        "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages/torch/lib/libtorch_xpu.so"
    ),
    "level_zero_loader": Path("/lib/x86_64-linux-gnu/libze_loader.so.1"),
    "level_zero_driver": Path("/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1"),
}
RUNTIME_SHA256 = {
    "python": "202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8",
    "libtorch_xpu": "63b7a56723482bc35d31842f442f6e903ef0b7fbd741c1a4ae309123bbc90572",
    "level_zero_loader": "0fe232b18985ae078dd546b57bc6d11bacf1030834c0544f7e3feb53ed71c1d0",
    "level_zero_driver": "26fa68779adb03b200a8c3001cf81e59fc9a3d63e0f38627ec0005ffce574e7a",
}
MANDATORY_TOOLS = {
    "authorization_gate": "experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_shared_gate_up_mm_counters.py",
    "authorization_gate_tests": "experiments/laguna-s-2.1-xpu-b70/tools/test_gate_laguna_shared_gate_up_mm_counters.py",
    "fixture": "experiments/laguna-s-2.1-xpu-b70/tools/profile_laguna_shared_gate_up_mm_counter_fixture.py",
    "fixture_tests": "experiments/laguna-s-2.1-xpu-b70/tools/test_profile_laguna_shared_gate_up_mm_counter_fixture.py",
    "parser": "experiments/laguna-s-2.1-xpu-b70/tools/laguna_shared_gate_up_counter_parser.py",
    "parser_tests": "experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_shared_gate_up_counter_parser.py",
    "runner": "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_shared_gate_up_mm_counters.py",
    "runner_tests": "experiments/laguna-s-2.1-xpu-b70/tools/test_run_laguna_shared_gate_up_mm_counters.py",
    "analyzer": "experiments/laguna-s-2.1-xpu-b70/tools/analyze_laguna_shared_gate_up_mm_counters.py",
    "analyzer_tests": "experiments/laguna-s-2.1-xpu-b70/tools/test_analyze_laguna_shared_gate_up_mm_counters.py",
    "component_contract": "experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_shared_gate_up_mm_component.py",
    "component_runtime": "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_shared_gate_up_mm_component.py",
    "stage0_contract": "experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_shared_gate_up_mm_stage0.py",
    "stage0_runtime": "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_shared_gate_up_mm_stage0.py",
}
ARMS = ("A1", "B1", "B2", "A2")
AUXILIARY_TIMING_CALLS = {
    "zeCommandListAppendMemoryCopy(D2M)[1572864]": 2,
    "zeCommandListAppendMemoryCopy(M2D)[1572864]": 2,
    "zeCommandListAppendMemoryCopy(D2M)[49152]": 1,
    "zeCommandListAppendMemoryCopy(M2D)[49152]": 1,
    "zeCommandListAppendMemoryCopy(D2M)[4096]": 26,
}
HOST_TOOLS = {
    "sudo": Path("/usr/bin/sudo"),
    "env": Path("/usr/bin/env"),
    "timeout": Path("/usr/bin/timeout"),
    "kill": Path("/usr/bin/kill"),
    "xpu_smi": Path("/usr/bin/xpu-smi"),
    "findmnt": Path("/usr/bin/findmnt"),
}
KERNEL_BINARIES = {
    "_C": KERNELS / "vllm_xpu_kernels/_C.abi3.so",
    "_xpu_C": KERNELS / "vllm_xpu_kernels/_xpu_C.abi3.so",
    "_moe_C": KERNELS / "vllm_xpu_kernels/_moe_C.abi3.so",
    "libgrouped_gemm_xe_2": (KERNELS / "vllm_xpu_kernels/libgrouped_gemm_xe_2.so"),
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def clean_git_identity(
    repo: Path, expected_commit: str, *, include_untracked: bool = True
) -> dict[str, Any]:
    status = git(
        repo,
        "status",
        "--porcelain=v1",
        "--untracked-files=all" if include_untracked else "--untracked-files=no",
    )
    commit = git(repo, "rev-parse", "HEAD")
    require(
        not status and commit == expected_commit,
        f"sealed repository identity drift: {repo}",
    )
    return {
        "path": str(repo),
        "commit": commit,
        "tracked_clean": True,
        "untracked_included": include_untracked,
        "status_sha256": hashlib.sha256(status.encode()).hexdigest(),
    }


def require_nvme() -> None:
    found = subprocess.run(
        [
            "findmnt",
            "--noheadings",
            "--output",
            "SOURCE,FSTYPE",
            "--target",
            str(ARTIFACT),
        ],
        capture_output=True,
        text=True,
    )
    require(
        found.returncode == 0
        and found.stdout.strip()
        == f"{EXPECTED['nvme_source']} {EXPECTED['nvme_fstype']}",
        "Laguna artifact root is not the sealed local NVMe/ext4 mount",
    )


def tracked_bytes(path: Path) -> bytes:
    relative = path.relative_to(MAIN)
    return subprocess.run(
        ["git", "-C", str(MAIN), "show", f"HEAD:{relative}"],
        check=True,
        capture_output=True,
    ).stdout


def component_evidence() -> dict[str, Any]:
    require_nvme()
    require(
        COMPONENT_ROOT.is_dir()
        and not COMPONENT_ROOT.is_symlink()
        and COMPONENT_MANIFEST.is_file()
        and not COMPONENT_MANIFEST.is_symlink(),
        "component evidence root/manifest is missing or aliased",
    )
    require(
        sha(COMPONENT_MANIFEST) == EXPECTED["component_manifest_sha256"],
        "component final-manifest hash drift",
    )
    require(
        COMPONENT_SUMMARY.is_file()
        and not COMPONENT_SUMMARY.is_symlink()
        and sha(COMPONENT_SUMMARY) == EXPECTED["component_summary_sha256"],
        "component pass summary hash drift",
    )
    require(
        git(
            MAIN,
            "log",
            "-1",
            "--format=%H",
            "--",
            str(COMPONENT_SUMMARY.relative_to(MAIN)),
        )
        == EXPECTED["component_summary_commit"]
        and tracked_bytes(COMPONENT_SUMMARY) == COMPONENT_SUMMARY.read_bytes(),
        "component pass summary is not tracked frozen bytes",
    )
    summary = json.loads(COMPONENT_SUMMARY.read_text())
    require(
        summary.get("status")
        == "component_final_seal_passed_counter_tooling_construction_authorized"
        and summary.get("component_passed") is True,
        "component pass predecessor drift",
    )
    identity, campaign = summary.get("identity", {}), summary.get("campaign", {})
    require(
        identity.get("vllm_commit") == EXPECTED["vllm_commit"]
        and identity.get("kernel_commit") == EXPECTED["kernel_commit"]
        and identity.get("boot_id") == EXPECTED["boot_id"]
        and campaign.get("final_manifest", {}).get("sha256")
        == EXPECTED["component_manifest_sha256"],
        "component final-manifest/identity binding drift",
    )
    observed = [
        {
            "rank": row.get("rank"),
            "uuid": row.get("physical_uuid"),
            "pci_bdf_address": row.get("physical_bdf"),
        }
        for row in summary.get("cards", [])
    ]
    expected = [
        {
            "rank": row["rank"],
            "uuid": row["uuid"],
            "pci_bdf_address": row["pci_bdf_address"],
        }
        for row in CARDS
    ]
    require(observed == expected, "component physical-card binding drift")
    return {
        "root": str(COMPONENT_ROOT),
        "final_manifest": {
            "path": str(COMPONENT_MANIFEST),
            "sha256": sha(COMPONENT_MANIFEST),
        },
        "summary": {
            "path": str(COMPONENT_SUMMARY),
            "sha256": sha(COMPONENT_SUMMARY),
            "last_commit": EXPECTED["component_summary_commit"],
        },
    }


def mandatory_tools() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for name, relative in MANDATORY_TOOLS.items():
        path = MAIN / relative
        require(
            path.is_file()
            and not path.is_symlink()
            and path.resolve().is_relative_to(TOOLS),
            f"mandatory tool missing or aliased: {name}",
        )
        result[name] = {"path": relative, "sha256": sha(path)}
    note = CONTRACT_NOTE
    require(
        note.is_file()
        and not note.is_symlink()
        and sha(note) == EXPECTED["tooling_note_sha256"]
        and tracked_bytes(note) == note.read_bytes(),
        "tooling-contract note drift",
    )
    result["tooling_contract_note"] = {
        "path": str(note.relative_to(MAIN)),
        "sha256": sha(note),
    }
    return result


def runtime_identity() -> dict[str, Any]:
    repositories = {
        "vllm": clean_git_identity(VLLM, EXPECTED["vllm_commit"]),
        "kernels": clean_git_identity(KERNELS, EXPECTED["kernel_commit"]),
        "pti": clean_git_identity(PTI, EXPECTED["pti_commit"], include_untracked=False),
    }
    files: dict[str, dict[str, Any]] = {}
    for name, path in RUNTIME_FILES.items():
        resolved = path.resolve(strict=True)
        require(
            resolved.is_file() and sha(path) == RUNTIME_SHA256[name],
            f"runtime file hash drift: {name}",
        )
        files[name] = {
            "path": str(path),
            "resolved_path": str(resolved),
            "symlink": path.is_symlink(),
            "sha256": RUNTIME_SHA256[name],
        }
    require(
        UNITRACE.is_file()
        and not UNITRACE.is_symlink()
        and sha(UNITRACE) == EXPECTED["unitrace_sha256"],
        "unitrace binary hash drift",
    )
    require(
        sha(MODEL_CONFIG) == EXPECTED["model_config_sha256"], "model config hash drift"
    )
    require(
        Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        == EXPECTED["boot_id"]
        and Path("/proc/sys/kernel/tainted").read_text().strip() == "0",
        "boot or kernel-taint drift",
    )
    host_tools = {}
    for name, path in HOST_TOOLS.items():
        require(path.is_file() and not path.is_symlink(), f"host tool drift: {name}")
        host_tools[name] = {"path": str(path), "sha256": sha(path)}
    kernel_binaries = {}
    for name, path in KERNEL_BINARIES.items():
        require(
            path.is_file() and not path.is_symlink(),
            f"kernel binary drift: {name}",
        )
        kernel_binaries[name] = {"path": str(path), "sha256": sha(path)}
    return {
        "repositories": repositories,
        "runtime_files": files,
        "host_tools": host_tools,
        "kernel_binaries": kernel_binaries,
        "unitrace": {
            "path": str(UNITRACE),
            "sha256": EXPECTED["unitrace_sha256"],
        },
        "model": {
            "config_path": str(MODEL_CONFIG),
            "config_sha256": EXPECTED["model_config_sha256"],
            "target_revision": "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb",
            "dflash_revision": "5e07c246915c86dc6920fead03d019989224f2ba",
        },
        "boot_id": EXPECTED["boot_id"],
        "kernel_taint": "0",
        "cards": CARDS,
        "storage": {
            "artifact_root": str(ARTIFACT),
            "runs_root": str(RUNS),
            "source": EXPECTED["nvme_source"],
            "fstype": EXPECTED["nvme_fstype"],
            "external_usb_role": "backup_only",
            "usb_allowed": False,
        },
    }


def arm_environment(arm_dir: Path, rank: int) -> dict[str, str]:
    # This import is CPU-only; the component contract only builds the frozen map.
    import gate_laguna_shared_gate_up_mm_component as component

    environment = component.environment(str(arm_dir), rank)
    require(
        environment.get("VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM") == "1"
        and environment.get("VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM") == "0"
        and environment.get("VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM") == "0",
        "selector exclusivity drift",
    )
    return environment


def child_command_template() -> list[str]:
    return [
        "/usr/bin/sudo",
        "-S",
        "-p",
        "",
        "-E",
        "--",
        "/usr/bin/env",
        "-i",
        "{sorted_child_environment_assignments}",
        "/usr/bin/timeout",
        "--signal=TERM",
        "--kill-after=5s",
        "180s",
        str(UNITRACE),
        "--device-timing",
        "--metric-query",
        "--group",
        "ComputeBasic",
        "--include-kernels",
        "gemm_kernel",
        "--verbose",
        "--pid",
        "--devices-to-sample",
        "0",
        "--output",
        "unitrace",
        RUNTIME_FILES["python"].as_posix(),
        str(TOOLS / "profile_laguna_shared_gate_up_mm_counter_fixture.py"),
        "--rank",
        "{rank}",
        "--arm",
        "{treatment}",
        "--expected-fixture-sha256",
        "{fixture_sha256}",
        "--authorization-sha256",
        "{authorization_sha256}",
        "--protocol-sha256",
        "{protocol_sha256}",
        "--out",
        "{fixture_output}",
    ]


PROTOCOL = {
    "card_order": [0, 1, 2, 3],
    "card_execution": "sequential",
    "arms": list(ARMS),
    "arm_treatments": {
        "A1": "control",
        "A2": "control",
        "B1": "candidate",
        "B2": "candidate",
    },
    "pairs_per_arm": 13,
    "selected_gemm_calls": 26,
    "discard_pair_indices": [0, 1],
    "retained_pair_indices": list(range(2, 13)),
    "retained_pairs": 11,
    "retained_gemm_samples": 22,
    "completion_bounded_before_and_after_each_pair": True,
    "eviction_bytes_before_each_pair": 134217728,
    "control": "separate ordered stride-zero B8/M1 BF16 BMM gate then up",
    "candidate": "separate ordered native M8 BF16 MM gate then up",
    "forbidden": [
        "merged_N512",
        "logical_B16",
        "concatenation",
        "packing",
        "custom_fusion",
        "reorder",
        "overlap",
        "shared_down_MM",
    ],
    "exactness": {
        "direct_counter": ["gate", "up"],
        "component_evidence_only": [
            "gate_repeat",
            "up_repeat",
            "gate_silu",
            "bf16_multiply",
            "shared_down",
            "shared_routed_add",
            "fixed_rank_reduction",
        ],
    },
    "unitrace": {
        "argv_template": child_command_template(),
        "outer_timeout_seconds": 200,
        "term_grace_seconds": 5,
        "kill_grace_seconds": 5,
        "root_timeout_seconds": 180,
        "metric_group": "ComputeBasic",
        "kernel_selector": "gemm_kernel",
        "selected_kernel_identity": "one exact verbose SIMD16 gemm_kernel name per arm; bare selector is forbidden as emitted identity",
        "timing_summary_rows": 6,
        "selected_gemm_calls": 26,
        "auxiliary_timing_name_to_calls": AUXILIARY_TIMING_CALLS,
        "row_order_significant": False,
        "metric_header_sha256": EXPECTED["metric_header_sha256"],
        "metric_pair_id_semantics": "strictly increasing unique IDs; rows 2*i and 2*i+1 are consecutive gate/up IDs; gaps between pairs are permitted only for the eviction kernel",
    },
}
ACCEPTANCE = {
    "raw_bit_exact_all_arms": True,
    "both_matched_pairs_candidate_gpu_time_lower_per_card": True,
    "per_card_aggregate_candidate_gpu_time_lower": True,
    "global_aggregate_candidate_gpu_time_lower": True,
    "global_cannot_rescue": True,
    "maximum_gpu_memory_read_regression_fraction": 0.02,
    "maximum_lsc_read_regression_fraction": 0.02,
    "maximum_thread_occupancy_decrease_percentage_points": 0.5,
    "maximum_xve_active_decrease_percentage_points": 0.5,
    "maximum_xve_stall_increase_percentage_points": 0.5,
    "all_validity_split_overrun_lost_inconsistent_proxies_zero": True,
    "spill_slm_partial_write_lsc_write_proxies_zero": True,
}


def expected_actions(propose_execution: bool) -> dict[str, bool]:
    return {
        "component_passed": propose_execution,
        "tooling_frozen": propose_execution,
        "counter_execution_authorized": propose_execution,
        "counter_execution_performed": False,
        "counter_gate_evaluated": False,
        "endpoint_preregistration_construction_authorized": False,
        "endpoint_authorized": False,
        "service_authorized": False,
        "model_generation_authorized": False,
        "model_generation_performed": False,
        "network_authorized": False,
        "network_access_performed": False,
        "payload_authorized": False,
        "payload_created": False,
        "submission_authorized": False,
        "submission_performed": False,
        "reboot_authorized": False,
    }


def campaign_paths(root: Path, *, require_fresh: bool = True) -> dict[str, Any]:
    preflight_failure = root.parent / f"{root.name}-preflight-failure.json"
    require(
        root.is_absolute()
        and root.parent == RUNS
        and re.fullmatch(r"shared-gate-up-m8-counters-[0-9]{8}T[0-9]{6}Z", root.name)
        is not None
        and (not require_fresh or not root.exists())
        and (not require_fresh or not root.is_symlink()),
        "campaign root must be a fresh direct canonical local-NVMe runs child",
    )
    if require_fresh:
        require(
            not preflight_failure.exists() and not preflight_failure.is_symlink(),
            "campaign preflight-failure path is not fresh",
        )
    arms = []
    for card in CARDS:
        for arm in ARMS:
            arm_dir = root / f"card{card['rank']}" / arm
            arms.append(
                {
                    "rank": card["rank"],
                    "arm": arm,
                    "arm_dir": str(arm_dir),
                    "fixture_output": str(arm_dir / "fixture.json"),
                    "environment": arm_environment(arm_dir, card["rank"]),
                }
            )
    return {
        "root": str(root),
        "preflight_failure": str(preflight_failure),
        "intent": str(root / "campaign.intent.json"),
        "abandoned": str(root / "campaign.abandoned.json"),
        "open": str(root / "campaign.open.json"),
        "complete": str(root / "campaign.complete.json"),
        "analysis": str(root / "analysis.json"),
        "terminal": str(root / "campaign-terminal.json"),
        "final_manifest": str(root / "counter-final-manifest.json"),
        "arms": arms,
    }


def durable_exclusive_json(path: Path, value: dict[str, Any]) -> None:
    require(
        path.parent == MAIN / "data" and not path.exists() and not path.is_symlink(),
        "packet path must be fresh directly under data/",
    )
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644
    )
    try:
        payload = canonical(value) + b"\n"
        pending = memoryview(payload)
        while pending:
            written = os.write(descriptor, pending)
            require(written > 0, "short authorization packet write")
            pending = pending[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except BaseException:
        raise


def build_packet(
    packet_path: Path, campaign_root: Path, propose_execution: bool
) -> dict[str, Any]:
    require(
        packet_path.is_absolute()
        and packet_path.parent == MAIN / "data"
        and packet_path.suffix == ".json",
        "packet path must be an absolute direct data JSON child",
    )
    component = component_evidence()
    tools, identity, paths = (
        mandatory_tools(),
        runtime_identity(),
        campaign_paths(campaign_root),
    )
    main_status = git(MAIN, "status", "--porcelain=v1", "--untracked-files=all")
    require(
        not main_status,
        "authorization packet construction requires a clean frozen tooling commit",
    )
    tools_commit = git(MAIN, "rev-parse", "HEAD")
    actions = expected_actions(propose_execution)
    return {
        "format": "laguna-shared-gate-up-m8-counter-authorization-v2",
        "phase": "cold_counter",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "packet_path": str(packet_path),
        "component_evidence": component,
        "tooling": tools,
        "identity": identity,
        "campaign": paths,
        "protocol": PROTOCOL,
        "acceptance": ACCEPTANCE,
        "actions": actions,
        "authorization_tracking": {
            "repository": str(MAIN),
            "packet_repo_path": str(packet_path.relative_to(MAIN)),
            "tools_commit": tools_commit,
            "runner_requirement": (
                "runner must require this exact packet as the clean immediate "
                "packet-only Git child of the committed tool freeze"
            ),
        },
        "fail_closed": {
            "no_rerun": True,
            "no_sample_selection": True,
            "counter_failure_state": "counter-failed-stop-before-endpoint",
            "offline_parser_repair_requires_separate_authorization": True,
            "counter_reexecution_after_sealed_capture": False,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--packet-path", type=Path, required=True)
    ap.add_argument("--campaign-root", type=Path, required=True)
    ap.add_argument(
        "--propose-execution",
        action="store_true",
        help="freeze only counter authority; all downstream actions remain false",
    )
    args = ap.parse_args()
    try:
        packet_path = args.packet_path.resolve(strict=False)
        campaign_root = args.campaign_root.resolve(strict=False)
        durable_exclusive_json(
            packet_path,
            build_packet(packet_path, campaign_root, args.propose_execution),
        )
        return 0
    except Exception as error:
        print(f"FAIL-CLOSED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
