#!/usr/bin/env python3
"""Fail-closed authorization contract for the Laguna four-card component gate.

This module is deliberately CPU-only: it validates immutable stage-zero
evidence and the packet shape, but it never imports torch, enumerates devices,
or creates a campaign root.  The coordinator is the only process allowed to
acquire a component campaign root after a packet-only authorization child.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import analyze_laguna_shared_gate_mm_stage0 as stage0_analyzer
import gate_laguna_shared_gate_mm_stage0 as stage0

MAIN = Path("/home/steve/llm-optimizations")
ARTIFACT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
PYTHON = Path("/home/steve/.venvs/deepseek-v4-xpu/bin/python")
FORMAT = "laguna-shared-gate-m8-four-card-component-authorization-v2"
RUNNER_STATE = "READY_COMPONENT_EXECUTION"
PREREG = stage0.PREREG_PATH

CARDS = {
    0: {
        "logical_device_id": 0,
        "uuid": "00000000-0000-0023-0000-0000e2238086",
        "pci_bdf_address": "0000:23:00.0",
        "drm_device": "/dev/dri/card3",
    },
    1: {
        "logical_device_id": 1,
        "uuid": "00000000-0000-0027-0000-0000e2238086",
        "pci_bdf_address": "0000:27:00.0",
        "drm_device": "/dev/dri/card4",
    },
    2: {
        "logical_device_id": 2,
        "uuid": "00000000-0000-0043-0000-0000e2238086",
        "pci_bdf_address": "0000:43:00.0",
        "drm_device": "/dev/dri/card0",
    },
    3: {
        "logical_device_id": 3,
        "uuid": "00000000-0000-0047-0000-0000e2238086",
        "pci_bdf_address": "0000:47:00.0",
        "drm_device": "/dev/dri/card2",
    },
}
TOOLS = {
    "contract": "experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_shared_gate_mm_component.py",
    "runner": "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_shared_gate_mm_component.py",
    "analyzer": "experiments/laguna-s-2.1-xpu-b70/tools/analyze_laguna_shared_gate_mm_component.py",
    "coordinator": "experiments/laguna-s-2.1-xpu-b70/tools/orchestrate_laguna_shared_gate_mm_component.py",
    "launcher": "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_shared_gate_mm_component.sh",
    "cpu_tests": "experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_shared_gate_mm_component.py",
    "coordinator_cpu_tests": "experiments/laguna-s-2.1-xpu-b70/tools/test_orchestrate_laguna_shared_gate_mm_component.py",
    **{f"stage0_{name}": path for name, path in stage0.TOOL_PATHS.items()},
}
TOOL_STATES = {
    "contract": "CPU_ONLY_REVIEWED",
    "runner": RUNNER_STATE,
    "analyzer": RUNNER_STATE,
    "coordinator": RUNNER_STATE,
    "launcher": RUNNER_STATE,
    "cpu_tests": "CPU_ONLY_REVIEWED",
    "coordinator_cpu_tests": "CPU_ONLY_REVIEWED",
    **{f"stage0_{name}": stage0.TOOL_STATES[name] for name in stage0.TOOL_PATHS},
}
RUNTIME_DEPENDENCIES = {
    "runner": [
        "contract",
        "coordinator",
        "runner",
        "stage0_fixture_generator",
        "stage0_runtime_adapter",
        "stage0_result_analyzer",
    ],
    "analyzer": [
        "contract",
        "analyzer",
        "coordinator",
        "stage0_fixture_generator",
        "stage0_result_analyzer",
    ],
    "coordinator": [
        "contract",
        "coordinator",
        "runner",
        "analyzer",
        "stage0_fixture_generator",
        "stage0_runtime_adapter",
        "stage0_result_analyzer",
    ],
    "launcher": ["contract", "coordinator", "launcher"],
}
N64 = {"rows": 8, "k": 3072, "n": 256, "weights": 47, "weight_bytes": 1572864}
PROTOCOL = {
    **N64,
    "exact_epochs_before": 128,
    "exact_epochs_after": 32,
    "warm_cycles_per_arm": 20,
    "abba_blocks": 31,
    "cycles_per_arm_per_block": 64,
    "eviction_bytes_per_arm": 134217728,
    "synchronization": "arm_boundaries_only",
    "arm_order": "A-B-B-A",
    "minimum_wins": 28,
    "minimum_median_saving_ms": 0.15,
    "timed_scope": "isolated_gate_projection_only",
    "control": "literal_stride_zero_B8_M1_bfloat16_bmm",
    "candidate": "native_M8_K3072_N256_bfloat16_mm",
}
FALSE_ACTIONS = {
    "counter_tooling_construction_authorized": False,
    "counter_execution_authorized": False,
    "endpoint_authorized": False,
    "service_authorized": False,
    "model_generation_authorized": False,
    "payload_authorized": False,
    "submission_authorized": False,
    "network_authorized": False,
    "reboot_authorized": False,
}
SEALED_STAGE0 = {
    "authorization_commit": "bbcfb67ea462dbcfd976dfd33281a8e7735f87d6",
    "tools_commit": "155d647e480c45da9b8f198df9965c432c311650",
    "packet_repo_path": "data/laguna-s-2.1-shared-gate-m8-stage0-authorization.json",
    "packet_sha256": "f959416c19c0e2fa34834f2ea3cda7eb846f49c2fd38b2c0ae520834b9a02bdf",
    "packet_canonical_sha256": "2184e190408effa1440b7eef3502e81b178fbac4d2c21b400ce7f9debf61d819",
    "fixture_sha256": "d0ca468f33e1e53f1858ce5e712a611600b7238213108664ef6ec19c32ec58a8",
    "result_sha256": "8180b03fc05a0b519e49a04b9cae078829a33c708853883d7820bd9d1a016bd7",
    "checkpoint_sha256": {
        "pre-tensor-identity-checkpoint.json": "3f85d9f95838a9eec0f4a44b871565e5223f39f6f8e223cfc460656688424c92",
        "runtime-card0-binding-checkpoint.json": "21f729b6fa772ea869422fc938ab0634e816d6d04d84128b777797ee5a71652c",
        "tensor-work-started-checkpoint.json": "7788bd0b3ae59365e3730309690b132b62f32da8f557b8c961ffe14770b540b4",
        "dispatch-proof.json": "700bcd10e7d9342359e09c03e650e84b0a35291f47be0f957516db4ea4b4f8f2",
        "constructor-scope-proof.json": "196229c14d38588fdc00f0b49d59d63a0d1c65443c2c7f723ed35cf1eed8cda8",
    },
}


def require(ok: bool, why: str) -> None:
    if not ok:
        raise RuntimeError(why)


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


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _is_commit(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(c in "0123456789abcdef" for c in value)
    )


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _strict(value: object, fields: set[str], name: str) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == fields, f"{name} schema drift")
    return value


def _absolute_non_usb(path: Path, *, exists: bool = False) -> Path:
    stage0.require_nvme_artifact_path(path, must_exist=exists)
    require(path.is_absolute(), "all component paths must be absolute")
    require(
        not any(part in {"..", "."} for part in path.parts), "path aliases forbidden"
    )
    try:
        rel = path.relative_to(ARTIFACT)
    except ValueError as error:
        raise RuntimeError("artifact path is outside internal NVMe root") from error
    require(rel.parts and not path.is_symlink(), "invalid component artifact path")
    if exists:
        require(
            path.exists() and not path.is_symlink(),
            "required component artifact absent/symlinked",
        )
        resolved = path.resolve(strict=True)
        require(
            resolved.is_relative_to(ARTIFACT.resolve(strict=True)),
            "artifact symlink escape",
        )
    target = path if exists else path.parent
    lines = subprocess.run(
        [
            "findmnt",
            "--noheadings",
            "--output",
            "SOURCE,FSTYPE",
            "--target",
            str(target),
        ],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    require(
        [stage0.NVME_SOURCE, stage0.NVME_FSTYPE] in [line.split() for line in lines],
        "component path is not internal NVMe ext4",
    )
    return path


def _stage0_packet_from_git() -> dict[str, Any]:
    require(
        git(MAIN, "rev-parse", SEALED_STAGE0["authorization_commit"] + "^")
        == SEALED_STAGE0["tools_commit"],
        "sealed stage-zero parent drift",
    )
    changed = git(
        MAIN,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        SEALED_STAGE0["authorization_commit"],
    ).splitlines()
    require(
        changed == [SEALED_STAGE0["packet_repo_path"]],
        "sealed stage-zero authorization was not packet-only",
    )
    raw = subprocess.run(
        [
            "git",
            "-C",
            str(MAIN),
            "show",
            f"{SEALED_STAGE0['authorization_commit']}:{SEALED_STAGE0['packet_repo_path']}",
        ],
        check=True,
        capture_output=True,
    ).stdout
    require(
        hashlib.sha256(raw).hexdigest() == SEALED_STAGE0["packet_sha256"],
        "sealed stage-zero packet Git object drift",
    )
    packet = json.loads(raw)
    require(
        raw == canonical(packet) + b"\n", "sealed stage-zero packet is noncanonical"
    )
    return packet


def validate_stage0_evidence(result_path: Path, fixture_path: Path) -> dict[str, Any]:
    """Validate immutable stage-zero Git/evidence objects without consulting HEAD."""
    _absolute_non_usb(result_path, exists=True)
    _absolute_non_usb(fixture_path, exists=True)
    require(
        sha(result_path) == SEALED_STAGE0["result_sha256"],
        "sealed stage-zero result bytes drift",
    )
    require(
        sha(fixture_path) == SEALED_STAGE0["fixture_sha256"],
        "sealed stage-zero fixture bytes drift",
    )
    packet = _stage0_packet_from_git()
    for name, record in packet["tools"].items():
        historical = subprocess.run(
            [
                "git",
                "-C",
                str(MAIN),
                "show",
                f"{SEALED_STAGE0['tools_commit']}:{record['path']}",
            ],
            check=True,
            capture_output=True,
        ).stdout
        require(
            hashlib.sha256(historical).hexdigest() == record["sha256"],
            f"sealed stage-zero tool blob drift: {name}",
        )
        live = MAIN / record["path"]
        require(
            live.is_file() and not live.is_symlink() and sha(live) == record["sha256"],
            f"live stage-zero tool differs from sealed tools A: {name}",
        )
    fixture = json.loads(fixture_path.read_text())
    result = json.loads(result_path.read_text())
    stage0.validate_fixture_manifest(fixture)
    stage0.validate_authorization(packet, fixture)
    # Schema validation checks all 128 raw-BF16 result entries against the
    # canonical fixture, while intentionally avoiding live-HEAD lineage.
    stage0_analyzer.validate_schema_for_cpu_tests(result, fixture, packet)
    require(
        result["status"] == "stage0_exactness_pass"
        and result["passed"] is True
        and result["terminal"] is True,
        "stage-zero result is not a complete exact pass",
    )
    require(
        result["authorization_packet"]
        == {
            "path": packet["packet_path"],
            "sha256": SEALED_STAGE0["packet_canonical_sha256"],
        },
        "stage-zero packet binding drift",
    )
    authorization_path = MAIN / SEALED_STAGE0["packet_repo_path"]
    require(
        authorization_path.read_bytes() == canonical(packet) + b"\n",
        "working stage-zero packet differs from frozen Git object",
    )
    # This production durability checker intentionally excludes its live-HEAD
    # host-state routine: stage zero's auth child B is historical now.
    stage0_analyzer._validate_evidence_files(
        result,
        fixture,
        packet,
        fixture_path=fixture_path,
        authorization_path=authorization_path,
        result_path=result_path,
    )
    root = result_path.parent
    expected_map = {
        "stage0-result.json": SEALED_STAGE0["result_sha256"],
        **SEALED_STAGE0["checkpoint_sha256"],
        **{
            f"epochs/epoch-{index:03d}.json": hashlib.sha256(
                canonical(entry) + b"\n"
            ).hexdigest()
            for index, entry in enumerate(result["epochs"])
        },
    }
    found_map: dict[str, str] = {}
    found_dirs: set[str] = set()
    for path in root.rglob("*"):
        require(not path.is_symlink(), f"sealed stage-zero symlink drift: {path}")
        if path.is_dir():
            found_dirs.add(str(path.relative_to(root)))
        else:
            require(path.is_file(), f"sealed stage-zero nonregular entry: {path}")
            found_map[str(path.relative_to(root))] = sha(path)
    # The complete path->hash manifest is derived only from result bytes whose
    # SHA is frozen above; it binds every one of the 128 durable epoch files.
    require(found_map == expected_map, "sealed stage-zero full evidence manifest drift")
    expected_dirs = {
        "epochs",
        "runtime",
        "runtime/cache",
        "runtime/cache/huggingface",
        "runtime/cache/numba",
        "runtime/cache/pycache",
        "runtime/cache/sycl",
        "runtime/cache/torchinductor",
        "runtime/cache/transformers",
        "runtime/cache/triton",
        "runtime/cache/vllm",
        "runtime/cache/xdg",
        "runtime/cache/xdg-config",
        "runtime/cache/xdg-data",
        "runtime/cache/xdg-state",
        "runtime/cache/xdg/neo_compiler_cache",
        "runtime/home",
        "runtime/tmp",
    }
    require(found_dirs == expected_dirs, "sealed stage-zero directory inventory drift")
    for name, digest in SEALED_STAGE0["checkpoint_sha256"].items():
        require(
            sha(root / name) == digest,
            f"sealed stage-zero checkpoint/proof drift: {name}",
        )
    evidence_fields = {
        "pre-tensor-identity-checkpoint.json": (
            "observed_pre_tensor_identity",
            "pre_tensor_identity",
        ),
        "runtime-card0-binding-checkpoint.json": (
            "runtime_card0_binding",
            "runtime_card0_binding",
        ),
        "constructor-scope-proof.json": ("proof", "constructor_scope_proof"),
        "dispatch-proof.json": ("proof", "dispatch_proof"),
    }
    for name, (evidence_key, result_key) in evidence_fields.items():
        require(
            json.loads((root / name).read_text())[evidence_key] == result[result_key],
            f"stage-zero durable evidence drift: {name}",
        )
    return result


def environment(root: str, rank: int) -> dict[str, str]:
    require(rank in CARDS, "invalid component rank")
    env = stage0.expected_environment(root)
    # `level_zero:0` is the one-device view *after* the physical card mask.
    env.update(
        {
            "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
            "ZE_AFFINITY_MASK": str(rank),
            "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "1",
            "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
        }
    )
    return env


def coordinator_environment(root: str) -> dict[str, str]:
    env = stage0.expected_environment(root)
    env.update(
        {
            "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
            "ZE_AFFINITY_MASK": "0",
            "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "1",
            "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
        }
    )
    return env


def _packet_paths(
    packet_path: Path, output_root: Path, fixture: Path, stage0_result: Path
) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    runner = str(MAIN / TOOLS["runner"])
    for rank, physical in CARDS.items():
        root = output_root / f"card{rank}"
        cards.append(
            {
                "rank": rank,
                "physical": physical,
                "output_root": str(root),
                "result": str(root / "component-result.json"),
                "environment": environment(str(root), rank),
                "runner_argv": [
                    str(PYTHON),
                    runner,
                    "--authorization",
                    str(packet_path),
                    "--fixture",
                    str(fixture),
                    "--rank",
                    str(rank),
                ],
            }
        )
    analyzer = str(MAIN / TOOLS["analyzer"])
    aggregate = str(output_root / "component-aggregate.json")
    terminal = str(output_root / "campaign-terminal.json")
    manifest = str(output_root / "component-final-manifest.json")
    preflight_failure = str(
        output_root.parent / f"{output_root.name}-preflight-failure.json"
    )
    common = [
        "--authorization",
        str(packet_path),
        *sum((["--card-result", card["result"]] for card in cards), []),
    ]
    return {
        "cards": cards,
        "coordinator_argv": [
            str(PYTHON),
            str(MAIN / TOOLS["coordinator"]),
            "--authorization",
            str(packet_path),
            "--fixture",
            str(fixture),
            "--stage0-result",
            str(stage0_result),
        ],
        "analyzer_argv": [str(PYTHON), analyzer, *common, "--out", aggregate],
        "finalizer_argv": [
            str(PYTHON),
            analyzer,
            "--finalize",
            *common,
            "--aggregate",
            aggregate,
            "--campaign-terminal",
            terminal,
            "--final-manifest",
            manifest,
        ],
        "final_verifier_argv": [
            str(PYTHON),
            analyzer,
            "--verify-final",
            *common,
            "--aggregate",
            aggregate,
            "--campaign-terminal",
            terminal,
            "--final-manifest",
            manifest,
        ],
        "aggregate_path": aggregate,
        "campaign_terminal_path": terminal,
        "final_manifest_path": manifest,
        "preflight_failure_path": preflight_failure,
    }


def template(
    *,
    fixture: Path,
    stage0_result: Path,
    output_root: Path,
    hashes: dict[str, str],
    packet_path: Path,
) -> dict[str, Any]:
    _absolute_non_usb(fixture, exists=True)
    _absolute_non_usb(stage0_result, exists=True)
    _absolute_non_usb(output_root)
    require(
        output_root.parent.is_dir() and not output_root.parent.is_symlink(),
        "campaign parent must preexist as a non-symlink directory",
    )
    require(not output_root.exists(), "campaign root must be fresh")
    preflight_failure = (
        output_root.parent / f"{output_root.name}-preflight-failure.json"
    )
    require(
        not preflight_failure.exists() and not preflight_failure.is_symlink(),
        "campaign preflight-failure path must be fresh",
    )
    require(
        packet_path.is_absolute()
        and packet_path.parent == MAIN / "data"
        and not packet_path.exists(),
        "packet must be a fresh tracked main-repo data path",
    )
    validate_stage0_evidence(stage0_result, fixture)
    paths = _packet_paths(packet_path, output_root, fixture, stage0_result)
    packet = {
        "format": FORMAT,
        "phase": "four_card_component",
        "packet_path": str(packet_path),
        "preregistration": {"path": PREREG, "sha256": stage0.PREREG_SHA256},
        "tools": {
            name: {"path": path, "sha256": hashes[name], "state": TOOL_STATES[name]}
            for name, path in TOOLS.items()
        },
        "runtime_dependencies": RUNTIME_DEPENDENCIES,
        "source": {
            "main_tools_commit": hashes["main_tools_commit"],
            "vllm_commit": stage0.EXPECTED_VLLM_COMMIT,
            "kernel_commit": stage0.EXPECTED_KERNEL_COMMIT,
            "files": {path: hashes[path] for path in stage0.SOURCE_PATHS},
        },
        "stage0": {
            "certificate": dict(SEALED_STAGE0),
            "result_path": str(stage0_result),
            "result_sha256": sha(stage0_result),
            "fixture_path": str(fixture),
            "fixture_sha256": sha(fixture),
            "required_status": "stage0_exactness_pass",
        },
        "boot_id": stage0.EXPECTED_BOOT_ID,
        "runtime": stage0.EXPECTED_RUNTIME_OBSERVED_IDENTITY,
        "binaries": dict(stage0.EXPECTED_BINARY_SHA256),
        "model": {
            "config_path": "/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json",
            "config_sha256": stage0.EXPECTED_MODEL_CONFIG_SHA256,
            "target_revision": "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb",
            "dflash_revision": "5e07c246915c86dc6920fead03d019989224f2ba",
        },
        "protocol": PROTOCOL,
        "campaign_root": str(output_root),
        "coordinator_environment": coordinator_environment(str(output_root)),
        "cards": paths["cards"],
        "coordinator_argv": paths["coordinator_argv"],
        "analyzer_argv": paths["analyzer_argv"],
        "finalizer_argv": paths["finalizer_argv"],
        "final_verifier_argv": paths["final_verifier_argv"],
        "aggregate_path": paths["aggregate_path"],
        "campaign_terminal_path": paths["campaign_terminal_path"],
        "final_manifest_path": paths["final_manifest_path"],
        "preflight_failure_path": paths["preflight_failure_path"],
        "authorization_tracking": {
            "repository": str(MAIN),
            "packet_repo_path": str(packet_path.relative_to(MAIN)),
            "tools_commit": hashes["main_tools_commit"],
            "required_commit_shape": "one_clean_auth_only_child",
        },
        "downstream": dict(FALSE_ACTIONS),
    }
    validate(packet)
    return packet


def validate(packet: dict[str, Any]) -> None:
    expected = {
        "format",
        "phase",
        "packet_path",
        "preregistration",
        "tools",
        "runtime_dependencies",
        "source",
        "stage0",
        "boot_id",
        "runtime",
        "binaries",
        "model",
        "protocol",
        "campaign_root",
        "coordinator_environment",
        "cards",
        "coordinator_argv",
        "analyzer_argv",
        "finalizer_argv",
        "final_verifier_argv",
        "aggregate_path",
        "campaign_terminal_path",
        "final_manifest_path",
        "preflight_failure_path",
        "authorization_tracking",
        "downstream",
    }
    _strict(packet, expected, "component authorization")
    require(
        packet["format"] == FORMAT and packet["phase"] == "four_card_component",
        "packet format/phase drift",
    )
    require(
        packet["preregistration"] == {"path": PREREG, "sha256": stage0.PREREG_SHA256},
        "preregistration drift",
    )
    require(
        packet["protocol"] == PROTOCOL and packet["downstream"] == FALSE_ACTIONS,
        "protocol/action escalation",
    )
    require(
        packet["boot_id"] == stage0.EXPECTED_BOOT_ID
        and packet["runtime"] == stage0.EXPECTED_RUNTIME_OBSERVED_IDENTITY
        and packet["binaries"] == stage0.EXPECTED_BINARY_SHA256,
        "runtime/binary identity drift",
    )
    require(
        packet["model"]
        == {
            "config_path": "/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json",
            "config_sha256": stage0.EXPECTED_MODEL_CONFIG_SHA256,
            "target_revision": "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb",
            "dflash_revision": "5e07c246915c86dc6920fead03d019989224f2ba",
        },
        "model identity drift",
    )
    require(
        Path(packet["packet_path"]).is_absolute()
        and Path(packet["packet_path"]).parent == MAIN / "data",
        "packet path drift",
    )
    campaign_root = Path(packet["campaign_root"])
    _absolute_non_usb(campaign_root)
    require(
        campaign_root.parent.is_dir() and not campaign_root.parent.is_symlink(),
        "campaign parent must preexist as a non-symlink directory",
    )
    _absolute_non_usb(Path(packet["preflight_failure_path"]))
    source = _strict(
        packet["source"],
        {"main_tools_commit", "vllm_commit", "kernel_commit", "files"},
        "source",
    )
    require(
        _is_commit(source["main_tools_commit"])
        and source["vllm_commit"] == stage0.EXPECTED_VLLM_COMMIT
        and source["kernel_commit"] == stage0.EXPECTED_KERNEL_COMMIT,
        "source commits drift",
    )
    require(
        isinstance(source["files"], dict)
        and set(source["files"]) == set(stage0.SOURCE_PATHS)
        and all(_is_sha(value) for value in source["files"].values()),
        "source file identities drift",
    )
    require(set(packet["tools"]) == set(TOOLS), "component tool set drift")
    for name, record in packet["tools"].items():
        _strict(record, {"path", "sha256", "state"}, f"tool {name}")
        require(
            record["path"] == TOOLS[name]
            and record["state"] == TOOL_STATES[name]
            and _is_sha(record["sha256"]),
            f"tool identity drift: {name}",
        )
    require(
        packet["runtime_dependencies"] == RUNTIME_DEPENDENCIES,
        "runtime imported-tool dependency drift",
    )
    stage = _strict(
        packet["stage0"],
        {
            "certificate",
            "result_path",
            "result_sha256",
            "fixture_path",
            "fixture_sha256",
            "required_status",
        },
        "stage-zero certificate",
    )
    require(
        stage["certificate"] == SEALED_STAGE0
        and stage["required_status"] == "stage0_exactness_pass"
        and stage["result_sha256"] == SEALED_STAGE0["result_sha256"]
        and stage["fixture_sha256"] == SEALED_STAGE0["fixture_sha256"],
        "stage-zero certificate drift",
    )
    validate_stage0_evidence(Path(stage["result_path"]), Path(stage["fixture_path"]))
    tracking = _strict(
        packet["authorization_tracking"],
        {"repository", "packet_repo_path", "tools_commit", "required_commit_shape"},
        "authorization tracking",
    )
    require(
        tracking
        == {
            "repository": str(MAIN),
            "packet_repo_path": str(Path(packet["packet_path"]).relative_to(MAIN)),
            "tools_commit": source["main_tools_commit"],
            "required_commit_shape": "one_clean_auth_only_child",
        },
        "authorization tracking drift",
    )
    require(
        packet["coordinator_environment"]
        == coordinator_environment(packet["campaign_root"]),
        "coordinator environment drift",
    )
    require(
        isinstance(packet["cards"], list)
        and [card.get("rank") for card in packet["cards"]] == [0, 1, 2, 3],
        "fixed card order drift",
    )
    canonical_paths = _packet_paths(
        Path(packet["packet_path"]),
        Path(packet["campaign_root"]),
        Path(stage["fixture_path"]),
        Path(stage["result_path"]),
    )
    require(
        packet["cards"] == canonical_paths["cards"]
        and packet["coordinator_argv"] == canonical_paths["coordinator_argv"]
        and packet["analyzer_argv"] == canonical_paths["analyzer_argv"]
        and packet["finalizer_argv"] == canonical_paths["finalizer_argv"]
        and packet["final_verifier_argv"] == canonical_paths["final_verifier_argv"]
        and packet["aggregate_path"] == canonical_paths["aggregate_path"]
        and packet["campaign_terminal_path"]
        == canonical_paths["campaign_terminal_path"]
        and packet["final_manifest_path"] == canonical_paths["final_manifest_path"]
        and packet["preflight_failure_path"]
        == canonical_paths["preflight_failure_path"],
        "packet final-seal argv/path drift",
    )
    require(
        len({card["physical"]["uuid"] for card in packet["cards"]}) == 4
        and len({card["physical"]["pci_bdf_address"] for card in packet["cards"]}) == 4,
        "physical card duplication",
    )


def frozen_hashes(fixture: Path, stage0_result: Path) -> dict[str, str]:
    validate_stage0_evidence(stage0_result, fixture)
    require(
        git(MAIN, "status", "--porcelain=v1", "--untracked-files=all") == "",
        "main tooling checkout must be clean for tools commit C",
    )
    vllm = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
    kernels = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
    for repo, commit in (
        (vllm, stage0.EXPECTED_VLLM_COMMIT),
        (kernels, stage0.EXPECTED_KERNEL_COMMIT),
    ):
        require(
            git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""
            and git(repo, "rev-parse", "HEAD") == commit,
            "source checkout not frozen",
        )
    result = {name: sha(MAIN / path) for name, path in TOOLS.items()}
    result.update({path: sha(vllm / path) for path in stage0.SOURCE_PATHS})
    result["main_tools_commit"] = git(MAIN, "rev-parse", "HEAD")
    return result


def validate_execution_packet(packet: dict[str, Any], authorization: Path) -> None:
    """Pre-root live checks; all evidence checks above are immutable-object based."""
    require(
        authorization.is_absolute()
        and authorization.is_file()
        and not authorization.is_symlink(),
        "authorization must be an absolute regular file",
    )
    raw = authorization.read_bytes()
    require(raw == canonical(packet) + b"\n", "authorization is not canonical bytes")
    validate(packet)
    campaign_parent = Path(packet["campaign_root"]).parent
    require(
        campaign_parent.is_dir() and not campaign_parent.is_symlink(),
        "campaign parent is absent or unsafe before device discovery",
    )
    require(
        not Path(packet["campaign_root"]).exists()
        and not Path(packet["campaign_root"]).is_symlink(),
        "campaign root must be fresh before coordinator acquisition",
    )
    require(
        not Path(packet["preflight_failure_path"]).exists()
        and not Path(packet["preflight_failure_path"]).is_symlink(),
        "campaign preflight-failure path is not fresh",
    )
    require(
        str(authorization) == packet["packet_path"],
        "authorization argv differs from packet",
    )
    require(
        git(MAIN, "status", "--porcelain=v1", "--untracked-files=all") == "",
        "main checkout must be clean at execution",
    )
    head = git(MAIN, "rev-parse", "HEAD")
    tracking = packet["authorization_tracking"]
    require(
        git(MAIN, "rev-parse", head + "^") == tracking["tools_commit"],
        "authorization is not child D of tools commit C",
    )
    require(
        git(MAIN, "diff-tree", "--no-commit-id", "--name-only", "-r", head).splitlines()
        == [tracking["packet_repo_path"]],
        "authorization child D is not packet-only",
    )
    tracked = subprocess.run(
        ["git", "-C", str(MAIN), "show", f"{head}:{tracking['packet_repo_path']}"],
        check=True,
        capture_output=True,
    ).stdout
    require(tracked == raw, "executed authorization differs from Git object D")
    for name, record in packet["tools"].items():
        require(
            sha(MAIN / record["path"]) == record["sha256"], f"tool hash drift: {name}"
        )
    vllm = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
    kernels = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
    for repo, commit in (
        (vllm, packet["source"]["vllm_commit"]),
        (kernels, packet["source"]["kernel_commit"]),
    ):
        require(
            git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""
            and git(repo, "rev-parse", "HEAD") == commit,
            "source checkout drift at execution",
        )
    for relative, digest in packet["source"]["files"].items():
        require(sha(vllm / relative) == digest, f"vLLM source hash drift: {relative}")
    require(
        Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        == packet["boot_id"],
        "boot identity drift",
    )
    require(
        sha(Path(packet["model"]["config_path"])) == packet["model"]["config_sha256"],
        "model config drift",
    )
    require(
        sys.executable == packet["runtime"]["python_executable"]
        and sys.version == packet["runtime"]["python_version"],
        "Python runtime identity drift",
    )
    for record in packet["runtime"]["files"].values():
        path = Path(record["path"])
        require(
            path.is_file()
            and path.resolve(strict=True) == Path(record["resolved_path"])
            and sha(path) == record["sha256"],
            "runtime file identity drift",
        )
    binary_paths = {
        "_C.abi3.so": kernels / "vllm_xpu_kernels/_C.abi3.so",
        "_xpu_C.abi3.so": kernels / "vllm_xpu_kernels/_xpu_C.abi3.so",
        "_moe_C.abi3.so": kernels / "vllm_xpu_kernels/_moe_C.abi3.so",
        "libgrouped_gemm_xe_2.so": kernels / "vllm_xpu_kernels/libgrouped_gemm_xe_2.so",
    }
    for filename, path in binary_paths.items():
        require(
            path.is_file() and sha(path) == packet["binaries"][filename],
            f"binary hash drift: {filename}",
        )
    for card in packet["cards"]:
        physical = card["physical"]
        device = (
            Path("/sys/class/drm") / Path(physical["drm_device"]).name / "device"
        ).resolve(strict=True)
        require(
            device.name == physical["pci_bdf_address"]
            and (device / "vendor").read_text().strip() == "0x8086"
            and (device / "device").read_text().strip() == "0xe223",
            "full physical card mapping drift",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-authorization", action="store_true")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--stage0-result", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--packet-path", type=Path, required=True)
    args = parser.parse_args()
    require(args.print_authorization, "contract only prints a reviewable authorization")
    print(
        canonical(
            template(
                fixture=args.fixture,
                stage0_result=args.stage0_result,
                output_root=args.output_root,
                packet_path=args.packet_path,
                hashes=frozen_hashes(args.fixture, args.stage0_result),
            )
        ).decode()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
