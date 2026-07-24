#!/usr/bin/env python3
"""Fail-closed, offline verifier for the four-card shared-gate component.

This module deliberately has two entry points.  ``validate_schema_for_cpu_tests``
only exercises the self-contained evidence grammar using synthetic objects.
``validate_production`` additionally binds the packet and every artifact to the
live, clean, immutable repositories and host identity.  A unit-test fixture is
never a production certificate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

import analyze_laguna_shared_gate_mm_stage0 as stage0_analyzer
import gate_laguna_shared_gate_mm_component as c
import gate_laguna_shared_gate_mm_stage0 as stage0
import orchestrate_laguna_shared_gate_mm_component as coordinator


MAIN = c.MAIN
VLLM = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
KERNEL = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
RESULT_NAME = "component-result.json"
AGGREGATE_NAME = "component-aggregate.json"
PRE_COUNT, POST_COUNT, SLOT_COUNT = 128, 32, 47


def require(ok: bool, why: str) -> None:
    if not ok:
        raise RuntimeError(why)


def canonical(value: Any) -> bytes:
    return c.canonical(value)


def sha(path: Path) -> str:
    return c.sha(path)


def git(repo: Path, *args: str) -> str:
    return c.git(repo, *args)


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(x in "0123456789abcdef" for x in value)
    )


def _read_canonical(path: Path, label: str) -> dict[str, Any]:
    require(
        path.is_file() and not path.is_symlink(),
        f"{label} is missing or a symlink: {path}",
    )
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} is not JSON: {path}") from error
    require(
        isinstance(value, dict) and raw == canonical(value) + b"\n",
        f"{label} bytes are not canonical: {path}",
    )
    return value


def _clean(repo: Path, commit: str) -> None:
    require(
        git(repo, "status", "--porcelain=v1", "--untracked-files=all") == "",
        f"dirty checkout: {repo}",
    )
    require(git(repo, "rev-parse", "HEAD") == commit, f"commit drift: {repo}")


def _packet_lineage(packet: dict[str, Any], authorization: Path) -> str:
    """Bind execution to one clean auth-only child of the frozen tools commit."""
    require(
        authorization.read_bytes() == canonical(packet) + b"\n",
        "authorization is not canonical bytes",
    )
    track = packet["authorization_tracking"]
    require(track["repository"] == str(MAIN), "authorization repository drift")
    require(
        packet["source"]["main_tools_commit"] == track["tools_commit"],
        "packet tools/source commit split",
    )
    require(
        git(MAIN, "status", "--porcelain=v1", "--untracked-files=all") == "",
        "main checkout is not clean",
    )
    head = git(MAIN, "rev-parse", "HEAD")
    require(
        git(MAIN, "rev-parse", f"{head}^") == track["tools_commit"],
        "authorization is not child of frozen tools",
    )
    changed = git(
        MAIN, "diff-tree", "--no-commit-id", "--name-only", "-r", head
    ).splitlines()
    require(
        changed == [track["packet_repo_path"]], "authorization child is not packet-only"
    )
    tracked = subprocess.run(
        ["git", "-C", str(MAIN), "show", f"{head}:{track['packet_repo_path']}"],
        check=True,
        capture_output=True,
    ).stdout
    require(
        tracked == authorization.read_bytes(), "executed packet differs from Git object"
    )
    return head


def _runtime_and_sources(packet: dict[str, Any]) -> None:
    _clean(VLLM, packet["source"]["vllm_commit"])
    _clean(KERNEL, packet["source"]["kernel_commit"])
    for name, record in packet["tools"].items():
        require(
            set(record) == {"path", "sha256", "state"} and _is_sha(record["sha256"]),
            f"tool metadata drift: {name}",
        )
        require(
            sha(MAIN / record["path"]) == record["sha256"], f"tool bytes drift: {name}"
        )
    for relative, digest in packet["source"]["files"].items():
        require(
            _is_sha(digest) and sha(VLLM / relative) == digest,
            f"vLLM source bytes drift: {relative}",
        )
    runtime = packet["runtime"]
    require(
        sys.executable == runtime["python_executable"]
        and sys.version == runtime["python_version"],
        "analyzer Python identity drift",
    )
    for name, record in runtime["files"].items():
        path = Path(record["path"])
        require(
            path.is_file()
            and str(path.resolve(strict=True)) == record["resolved_path"]
            and sha(path) == record["sha256"],
            f"runtime file drift: {name}",
        )
    binary_paths = {
        "_C.abi3.so": KERNEL / "vllm_xpu_kernels/_C.abi3.so",
        "_xpu_C.abi3.so": KERNEL / "vllm_xpu_kernels/_xpu_C.abi3.so",
        "_moe_C.abi3.so": KERNEL / "vllm_xpu_kernels/_moe_C.abi3.so",
        "libgrouped_gemm_xe_2.so": KERNEL / "vllm_xpu_kernels/libgrouped_gemm_xe_2.so",
    }
    require(set(packet["binaries"]) == set(binary_paths), "binary inventory drift")
    for name, path in binary_paths.items():
        require(sha(path) == packet["binaries"][name], f"binary drift: {name}")
    model = packet["model"]
    require(
        sha(Path(model["config_path"])) == model["config_sha256"],
        "model config drift",
    )
    require(
        Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        == packet["boot_id"],
        "boot changed",
    )


def _stage0(packet: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    info = packet["stage0"]
    require(
        info["certificate"] == c.SEALED_STAGE0
        and info["required_status"] == "stage0_exactness_pass",
        "stage-zero certificate drift",
    )
    result_path, fixture_path = Path(info["result_path"]), Path(info["fixture_path"])
    require(
        sha(result_path) == info["result_sha256"] == c.SEALED_STAGE0["result_sha256"],
        "stage-zero result drift",
    )
    require(
        sha(fixture_path)
        == info["fixture_sha256"]
        == c.SEALED_STAGE0["fixture_sha256"],
        "stage-zero fixture drift",
    )
    # The contract checks immutable auth-only stage-zero lineage, all 128 raw
    # epochs, and every sealed checkpoint/proof hash rather than trusting a
    # Boolean certificate.
    c.validate_stage0_evidence(result_path, fixture_path)
    fixture = _read_canonical(fixture_path, "stage-zero fixture")
    stage0.validate_fixture_manifest(fixture)
    result = _read_canonical(result_path, "stage-zero result")
    require(
        result.get("status") == "stage0_exactness_pass"
        and result.get("passed") is True,
        "stage-zero was not an exact pass",
    )
    cert = c.SEALED_STAGE0
    raw_packet = subprocess.run(
        [
            "git",
            "-C",
            str(MAIN),
            "show",
            f"{cert['authorization_commit']}:{cert['packet_repo_path']}",
        ],
        check=True,
        capture_output=True,
    ).stdout
    require(
        hashlib.sha256(raw_packet).hexdigest() == cert["packet_sha256"],
        "stage-zero packet Git bytes drift",
    )
    try:
        stage0_packet = json.loads(raw_packet)
    except ValueError as error:
        raise RuntimeError("sealed stage-zero Git packet is not JSON") from error
    require(
        raw_packet == stage0.canonical_json_bytes(stage0_packet) + b"\n",
        "sealed stage-zero packet is not canonical",
    )
    require(
        stage0.packet_digest(stage0_packet) == cert["packet_canonical_sha256"],
        "stage-zero packet canonical digest drift",
    )
    stage0.validate_authorization(stage0_packet, fixture)
    require(
        stage0_packet["fixture"]["file_sha256"] == cert["fixture_sha256"],
        "stage-zero packet/fixture split",
    )
    # Component analysis imports the stage-zero contract and BF16 oracle.  Bind
    # their *live* bytes to the sealed historical tools commit as well as
    # validating the stage-zero packet's own tool records against those blobs.
    for name, record in stage0_packet["tools"].items():
        blob = subprocess.run(
            [
                "git",
                "-C",
                str(MAIN),
                "show",
                f"{cert['tools_commit']}:{record['path']}",
            ],
            check=True,
            capture_output=True,
        ).stdout
        require(
            hashlib.sha256(blob).hexdigest() == record["sha256"],
            f"sealed stage-zero tool blob drift: {name}",
        )
    for relative in (
        "gate_laguna_shared_gate_mm_stage0.py",
        "analyze_laguna_shared_gate_mm_stage0.py",
    ):
        tool = MAIN / "experiments/laguna-s-2.1-xpu-b70/tools" / relative
        historical = subprocess.run(
            [
                "git",
                "-C",
                str(MAIN),
                "show",
                f"{cert['tools_commit']}:experiments/laguna-s-2.1-xpu-b70/tools/{relative}",
            ],
            check=True,
            capture_output=True,
        ).stdout
        require(
            sha(tool) == hashlib.sha256(historical).hexdigest(),
            f"live imported stage-zero dependency drift: {relative}",
        )
    return fixture, result


def _strict_tree(root: Path, expected: set[str]) -> None:
    require(root.is_dir() and not root.is_symlink(), "campaign root missing or symlink")
    actual: set[str] = set()
    actual_dirs: set[str] = set()
    for base, dirs, files in os.walk(root, topdown=True, followlinks=False):
        base_path = Path(base)
        for name in list(dirs):
            child = base_path / name
            require(not child.is_symlink(), f"symlinked artifact directory: {child}")
            actual_dirs.add(str(child.relative_to(root)))
        for name in files:
            child = base_path / name
            require(
                not child.is_symlink() and child.is_file(),
                f"nonregular/symlink artifact: {child}",
            )
            actual.add(str(child.relative_to(root)))
    require(
        actual == expected,
        f"artifact inventory drift: expected={sorted(expected)} actual={sorted(actual)}",
    )
    expected_dirs = {
        str(parent)
        for path in expected
        for parent in Path(path).parents
        if str(parent) != "."
    }
    require(
        actual_dirs == expected_dirs,
        f"artifact directory inventory drift: expected={sorted(expected_dirs)} actual={sorted(actual_dirs)}",
    )


def _checkpoint_paths(result: dict[str, Any]) -> list[str]:
    paths = result.get("checkpoints")
    require(
        isinstance(paths, list)
        and all(
            isinstance(x, str)
            and x
            and not Path(x).is_absolute()
            and ".." not in Path(x).parts
            for x in paths
        ),
        "checkpoint path schema drift",
    )
    require(
        len(paths) == 166 and len(set(paths)) == 166,
        "checkpoint count/uniqueness drift",
    )
    expected = [
        "pre-tensor-identity-checkpoint.json",
        "tensor-work-started-checkpoint.json",
        "runtime-card-binding-checkpoint.json",
        "constructor-scope-proof.json",
        "dispatch-proof.json",
        *[f"pre-epochs/epoch-{i:03d}.json" for i in range(PRE_COUNT)],
        "timing.json",
        *[f"post-epochs/epoch-{i:03d}.json" for i in range(POST_COUNT)],
    ]
    require(paths == expected, "checkpoint inventory/order drift")
    return paths


def _checkpoints(
    root: Path, result: dict[str, Any], packet_digest: str, rank: int
) -> dict[str, dict[str, Any]]:
    paths = _checkpoint_paths(result)
    hashes = result.get("checkpoint_sha256")
    require(
        isinstance(hashes, dict)
        and set(hashes) == set(paths)
        and all(_is_sha(x) for x in hashes.values()),
        "checkpoint hash manifest drift",
    )
    values: dict[str, dict[str, Any]] = {}
    for rel in paths:
        value = _read_canonical(root / rel, f"checkpoint {rel}")
        require(sha(root / rel) == hashes[rel], f"checkpoint hash drift: {rel}")
        require(
            value.get("packet_sha256") == packet_digest and value.get("rank") == rank,
            f"checkpoint packet/rank binding drift: {rel}",
        )
        values[rel] = value
    # Each result-owned evidence value must be exactly the durable byte payload
    # recorded at its named checkpoint, so neither side can be self-reported.
    require(
        values["runtime-card-binding-checkpoint.json"]
        == result["runtime_card_binding"],
        "runtime-card-binding checkpoint/result split",
    )
    require(
        values["constructor-scope-proof.json"] == result["constructor_scope_proof"],
        "constructor checkpoint/result split",
    )
    require(
        values["dispatch-proof.json"] == result["dispatch_proof"],
        "dispatch checkpoint/result split",
    )
    require(values["timing.json"] == result["timing"], "timing checkpoint/result split")
    for phase, entries in (
        ("pre", result["pre_exactness"]),
        ("post", result["post_exactness"]),
    ):
        for envelope in entries:
            entry = envelope.get("entry") if isinstance(envelope, dict) else None
            require(
                isinstance(entry, dict) and isinstance(entry.get("epoch"), int),
                f"{phase} checkpoint envelope epoch drift",
            )
            rel = f"{phase}-epochs/epoch-{entry['epoch']:03d}.json"
            require(
                values[rel] == envelope,
                f"{phase} epoch checkpoint/result split: {entry['epoch']}",
            )
    return values


def _epoch(entry: Any, fixture_epoch: dict[str, Any]) -> str:
    require(isinstance(entry, dict), "epoch evidence is not an object")
    # Reuse the full stage-zero BF16 oracle: it decodes every raw tensor,
    # checks each canonical hash, recomputes comparisons, and checks input and
    # layer-weight immutability against the immutable fixture epoch.
    equal, unique_gate_hash = stage0_analyzer._epoch(entry, fixture_epoch)
    require(equal, f"raw exactness mismatch at epoch {fixture_epoch['epoch']}")
    return unique_gate_hash


def _exactness(result: dict[str, Any], fixture: dict[str, Any]) -> dict[str, str]:
    pre, post = result.get("pre_exactness"), result.get("post_exactness")
    require(
        isinstance(pre, list)
        and len(pre) == PRE_COUNT
        and isinstance(post, list)
        and len(post) == POST_COUNT,
        "exactness epoch count drift",
    )
    packet_digest, rank = result["packet_sha256"], result["rank"]

    def unwrap(envelope: Any, index: int, phase: str) -> dict[str, Any]:
        require(
            isinstance(envelope, dict)
            and set(envelope) == {"packet_sha256", "rank", "entry"}
            and envelope["packet_sha256"] == packet_digest
            and envelope["rank"] == rank
            and isinstance(envelope["entry"], dict),
            f"{phase} epoch envelope drift: {index}",
        )
        return envelope["entry"]

    pre_entries = [unwrap(value, index, "pre") for index, value in enumerate(pre)]
    post_entries = [unwrap(value, index, "post") for index, value in enumerate(post)]
    pre_hashes = [
        _epoch(entry, fixture["epochs"][index])
        for index, entry in enumerate(pre_entries)
    ]
    post_hashes = [
        _epoch(entry, fixture["epochs"][index])
        for index, entry in enumerate(post_entries)
    ]
    require(
        len(set(pre_hashes)) == PRE_COUNT,
        "pre exactness did not cover 128 unique fixture outputs",
    )
    require(
        len(set(post_hashes)) == POST_COUNT,
        "post exactness did not cover 32 unique fixture outputs",
    )
    for index in range(POST_COUNT):
        require(
            canonical(post[index]) == canonical(pre[index]),
            f"post exact replay differs from pre epoch {index}",
        )
    return {
        "pre_fixture": hashlib.sha256(
            "".join(x["fixture_epoch_sha256"] for x in pre_entries).encode()
        ).hexdigest(),
        "pre_output": hashlib.sha256("".join(pre_hashes).encode()).hexdigest(),
        "post_fixture": hashlib.sha256(
            "".join(x["fixture_epoch_sha256"] for x in post_entries).encode()
        ).hexdigest(),
        "post_output": hashlib.sha256("".join(post_hashes).encode()).hexdigest(),
    }


def _finite_number(value: object, label: str) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{label} is not numeric",
    )
    result = float(value)
    require(
        math.isfinite(result) and result > 0.0, f"{label} must be finite and positive"
    )
    return result


def _slots(value: object, name: str) -> None:
    require(
        isinstance(value, list)
        and len(value) == SLOT_COUNT
        and len(set(value)) == SLOT_COUNT,
        f"timing {name} slots are not 47 distinct entries",
    )
    require(
        all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in value),
        f"timing {name} slot identity drift",
    )


def _positive_int(value: object, label: str) -> int:
    require(
        isinstance(value, int) and not isinstance(value, bool) and value > 0,
        f"{label} must be a positive integer",
    )
    return value


def _metadata(
    value: object,
    *,
    label: str,
    shape: list[int],
    stride: list[int],
    raw_sha256: str | None = None,
) -> dict[str, Any]:
    expected = {
        "data_ptr",
        "shape",
        "stride",
        "dtype",
        "numel",
        "element_size",
    }
    if raw_sha256 is not None:
        expected.add("raw_bf16_le_sha256")
    require(isinstance(value, dict) and set(value) == expected, f"{label} schema drift")
    require(
        _positive_int(value["data_ptr"], f"{label} data_ptr") == value["data_ptr"]
        and value["shape"] == shape
        and value["stride"] == stride
        and value["dtype"] == "torch.bfloat16"
        and value["numel"] == math.prod(shape)
        and value["element_size"] == 2,
        f"{label} metadata drift",
    )
    if raw_sha256 is not None:
        require(
            value["raw_bf16_le_sha256"] == raw_sha256,
            f"{label} raw BF16 digest drift",
        )
    return value


def _fixture_tensor(epoch: dict[str, Any], label: str) -> dict[str, Any]:
    matches = [record for record in epoch["tensors"] if record["label"] == label]
    require(len(matches) == 1, f"fixture timing tensor missing: {label}")
    return matches[0]


def _timing_slot(
    value: object, fixture_epoch: dict[str, Any], index: int
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    require(
        isinstance(value, dict)
        and set(value)
        == {
            "slot",
            "rows",
            "weight",
            "rows_bmm",
            "weight_t",
            "expanded",
            "control",
            "candidate",
        }
        and value["slot"] == index,
        f"timing slot schema/order drift: {index}",
    )
    rows_fixture = _fixture_tensor(fixture_epoch, "hidden_input")
    weight_fixture = _fixture_tensor(fixture_epoch, "gate_weight")
    rows_shape = rows_fixture["shape"]
    weight_shape = weight_fixture["shape"]
    raw_rows = rows_fixture["raw_bf16_le_sha256"]
    raw_weight = weight_fixture["raw_bf16_le_sha256"]
    control_value = value["control"]
    candidate_value = value["candidate"]
    control_raw = (
        control_value.get("raw_bf16_le_sha256")
        if isinstance(control_value, dict)
        else None
    )
    candidate_raw = (
        candidate_value.get("raw_bf16_le_sha256")
        if isinstance(candidate_value, dict)
        else None
    )
    require(
        _is_sha(control_raw)
        and _is_sha(candidate_raw)
        and control_raw == candidate_raw,
        f"timing control/candidate raw output drift: {index}",
    )
    rows = _metadata(
        value["rows"],
        label=f"timing rows {index}",
        shape=rows_shape,
        stride=[rows_shape[1], 1],
        raw_sha256=raw_rows,
    )
    weight = _metadata(
        value["weight"],
        label=f"timing weight {index}",
        shape=weight_shape,
        stride=[weight_shape[1], 1],
        raw_sha256=raw_weight,
    )
    rows_bmm = _metadata(
        value["rows_bmm"],
        label=f"timing rows_bmm {index}",
        shape=[rows_shape[0], 1, rows_shape[1]],
        stride=[rows_shape[1], rows_shape[1], 1],
    )
    weight_t = _metadata(
        value["weight_t"],
        label=f"timing weight_t {index}",
        shape=[weight_shape[1], weight_shape[0]],
        stride=[1, weight_shape[1]],
    )
    expanded = _metadata(
        value["expanded"],
        label=f"timing expanded {index}",
        shape=[rows_shape[0], weight_shape[1], weight_shape[0]],
        stride=[0, 1, weight_shape[1]],
    )
    control = _metadata(
        value["control"],
        label=f"timing control {index}",
        shape=[rows_shape[0], 1, weight_shape[0]],
        stride=[weight_shape[0], weight_shape[0], 1],
        raw_sha256=control_raw,
    )
    candidate = _metadata(
        value["candidate"],
        label=f"timing candidate {index}",
        shape=[rows_shape[0], weight_shape[0]],
        stride=[weight_shape[0], 1],
        raw_sha256=candidate_raw,
    )
    require(
        rows_bmm["data_ptr"] == rows["data_ptr"]
        and weight_t["data_ptr"] == weight["data_ptr"]
        and expanded["data_ptr"] == weight["data_ptr"],
        f"timing view storage drift: {index}",
    )
    return rows, weight, control, candidate


def _timing(timing: Any, fixture: dict[str, Any]) -> dict[str, Any]:
    require(isinstance(timing, dict), "missing timing evidence")
    protocol = c.PROTOCOL
    fixed = {
        "timing_label": "allocation_free_isolated_gate_GEMM_primitive",
        "target_layers_per_cycle": protocol["weights"],
        "weight_bytes_each": protocol["weight_bytes"],
        "distinct_weights": protocol["weights"],
        "preallocated_identical_inputs": True,
        "output_ring_slots_per_arm": protocol["weights"],
        "distinct_preallocated_output_buffers": True,
        "warm_cycles_per_arm": protocol["warm_cycles_per_arm"],
        "blocks": protocol["abba_blocks"],
        "cycles_per_arm_per_block": protocol["cycles_per_arm_per_block"],
        "calls_per_arm": protocol["weights"] * protocol["cycles_per_arm_per_block"],
        "eviction_bytes_once_per_arm": protocol["eviction_bytes_per_arm"],
        "synchronization": protocol["synchronization"],
        "arm_order": protocol["arm_order"],
    }
    for key, expected in fixed.items():
        require(timing.get(key) == expected, f"timing protocol drift: {key}")
    require(
        set(timing)
        == set(fixed)
        | {
            "packet_sha256",
            "rank",
            "passed",
            "candidate_block_wins",
            "median_saving_ms_per_cycle",
            "buffer_proof",
            "preflight_proof",
            "blocks_detail",
        },
        "timing evidence schema drift",
    )
    buffer = timing.get("buffer_proof")
    require(
        isinstance(buffer, dict)
        and set(buffer)
        == {
            "input_slots",
            "weight_slots",
            "control_output_slots",
            "candidate_output_slots",
            "control_layout",
            "candidate_layout",
            "pre_timing_slots",
            "post_timing_slots",
            "nonalias",
        },
        "timing buffer proof schema drift",
    )
    for name in (
        "input_slots",
        "weight_slots",
        "control_output_slots",
        "candidate_output_slots",
    ):
        _slots(buffer[name], name)
    require(len(fixture["epochs"]) >= SLOT_COUNT, "fixture timing corpus is short")
    pre_slots = buffer["pre_timing_slots"]
    post_slots = buffer["post_timing_slots"]
    require(
        isinstance(pre_slots, list)
        and isinstance(post_slots, list)
        and len(pre_slots) == len(post_slots) == SLOT_COUNT,
        "timing slot-proof count drift",
    )
    live_slots: list[int] = []
    for index, (pre, post) in enumerate(zip(pre_slots, post_slots, strict=True)):
        pre_rows, pre_weight, pre_control, pre_candidate = _timing_slot(
            pre, fixture["epochs"][index], index
        )
        post_rows, post_weight, post_control, post_candidate = _timing_slot(
            post, fixture["epochs"][index], index
        )
        metadata_keys = (
            "data_ptr",
            "shape",
            "stride",
            "dtype",
            "numel",
            "element_size",
        )
        for before, after, label in (
            (pre_rows, post_rows, "rows"),
            (pre_weight, post_weight, "weight"),
            (pre_control, post_control, "control output"),
            (pre_candidate, post_candidate, "candidate output"),
        ):
            require(
                {key: after[key] for key in metadata_keys}
                == {key: before[key] for key in metadata_keys},
                f"timing post-{label} metadata drift: {index}",
            )
            require(
                before["raw_bf16_le_sha256"] == after["raw_bf16_le_sha256"],
                f"timing post-{label} raw digest drift: {index}",
            )
        live_slots.extend(
            (
                pre_rows["data_ptr"],
                pre_weight["data_ptr"],
                pre_control["data_ptr"],
                pre_candidate["data_ptr"],
            )
        )
    require(
        len(set(live_slots)) == len(live_slots) and buffer["nonalias"] is True,
        "timing live storage aliases",
    )
    require(
        len({slot["rows"]["raw_bf16_le_sha256"] for slot in pre_slots}) == SLOT_COUNT
        and len({slot["weight"]["raw_bf16_le_sha256"] for slot in pre_slots})
        == SLOT_COUNT,
        "timing fixture inputs/weights are not 47 distinct frozen tensors",
    )
    require(
        buffer["input_slots"] == sorted(pre["rows"]["data_ptr"] for pre in pre_slots)
        and buffer["weight_slots"]
        == sorted(pre["weight"]["data_ptr"] for pre in pre_slots)
        and buffer["control_output_slots"]
        == sorted(pre["control"]["data_ptr"] for pre in pre_slots)
        and buffer["candidate_output_slots"]
        == sorted(pre["candidate"]["data_ptr"] for pre in pre_slots),
        "timing slot list/proof split",
    )
    require(
        buffer["control_layout"]
        == {
            key: pre_slots[0]["control"][key]
            for key in ("data_ptr", "shape", "stride", "dtype", "numel", "element_size")
        }
        and buffer["candidate_layout"]
        == {
            key: pre_slots[0]["candidate"][key]
            for key in ("data_ptr", "shape", "stride", "dtype", "numel", "element_size")
        },
        "timing output layout proof split",
    )
    preflight = timing.get("preflight_proof")
    require(
        isinstance(preflight, list) and len(preflight) == SLOT_COUNT,
        "timing preflight count drift",
    )
    for index, proof in enumerate(preflight):
        require(
            isinstance(proof, dict)
            and proof
            == {
                "slot": index,
                "control_out_supplied_ptr": pre_slots[index]["control"]["data_ptr"],
                "control_out_returned_ptr": pre_slots[index]["control"]["data_ptr"],
                "candidate_out_supplied_ptr": pre_slots[index]["candidate"]["data_ptr"],
                "candidate_out_returned_ptr": pre_slots[index]["candidate"]["data_ptr"],
                "literal_raw_uint16_equal": True,
                "control_out_raw_uint16_equal": True,
                "candidate_out_raw_uint16_equal": True,
                "input_metadata_unchanged": True,
                "weight_metadata_unchanged": True,
                "output_metadata_unchanged": True,
            },
            f"timing preflight proof drift: {index}",
        )
    blocks = timing.get("blocks_detail")
    require(
        isinstance(blocks, list) and len(blocks) == protocol["abba_blocks"],
        "ABBA block count drift",
    )
    saves: list[float] = []
    for index, block in enumerate(blocks):
        require(
            isinstance(block, dict)
            and set(block)
            == {
                "block",
                "rotation",
                "slot_order",
                "A1_control_elapsed_ns",
                "A1_control_ms",
                "B1_candidate_elapsed_ns",
                "B1_candidate_ms",
                "B2_candidate_elapsed_ns",
                "B2_candidate_ms",
                "A2_control_elapsed_ns",
                "A2_control_ms",
                "paired_control_ms",
                "paired_candidate_ms",
                "saving_ms",
            }
            and block["block"] == index,
            "ABBA block schema/order drift",
        )
        rotation = (index * 11) % SLOT_COUNT
        require(
            block["rotation"] == rotation
            and block["slot_order"]
            == [(rotation + slot) % SLOT_COUNT for slot in range(SLOT_COUNT)],
            f"ABBA slot rotation/order drift: {index}",
        )
        a1_ns, b1_ns, b2_ns, a2_ns = (
            _positive_int(block[key], f"ABBA {index} {key}")
            for key in (
                "A1_control_elapsed_ns",
                "B1_candidate_elapsed_ns",
                "B2_candidate_elapsed_ns",
                "A2_control_elapsed_ns",
            )
        )
        a1, b1, b2, a2 = (
            _finite_number(block[key], f"ABBA {index} {key}")
            for key in (
                "A1_control_ms",
                "B1_candidate_ms",
                "B2_candidate_ms",
                "A2_control_ms",
            )
        )
        require(
            a1 == a1_ns / protocol["cycles_per_arm_per_block"] / 1_000_000
            and b1 == b1_ns / protocol["cycles_per_arm_per_block"] / 1_000_000
            and b2 == b2_ns / protocol["cycles_per_arm_per_block"] / 1_000_000
            and a2 == a2_ns / protocol["cycles_per_arm_per_block"] / 1_000_000,
            f"ABBA raw-ns conversion drift: {index}",
        )
        control, candidate, saving = (
            float(block[key])
            for key in ("paired_control_ms", "paired_candidate_ms", "saving_ms")
        )
        require(
            all(math.isfinite(x) for x in (control, candidate, saving)),
            f"ABBA derived nonfinite: {index}",
        )
        expected_control, expected_candidate = (
            (a1_ns + a2_ns) / 2.0 / protocol["cycles_per_arm_per_block"] / 1_000_000,
            (b1_ns + b2_ns) / 2.0 / protocol["cycles_per_arm_per_block"] / 1_000_000,
        )
        require(
            abs(control - expected_control) <= 1e-12
            and abs(candidate - expected_candidate) <= 1e-12
            and abs(saving - (control - candidate)) <= 1e-12,
            f"ABBA recomputation drift: {index}",
        )
        saves.append(saving)
    wins, median = sum(x > 0.0 for x in saves), statistics.median(saves)
    require(
        timing.get("candidate_block_wins") == wins
        and isinstance(timing.get("median_saving_ms_per_cycle"), (int, float))
        and not isinstance(timing["median_saving_ms_per_cycle"], bool)
        and math.isfinite(float(timing["median_saving_ms_per_cycle"]))
        and abs(float(timing["median_saving_ms_per_cycle"]) - median) <= 1e-12,
        "reported timing aggregate drift",
    )
    require(
        wins >= protocol["minimum_wins"]
        and median >= protocol["minimum_median_saving_ms"],
        "timing did not clear frozen win/median thresholds",
    )
    require(timing.get("passed") is True, "timing self-report is not pass")
    return {"wins": wins, "median_saving_ms": median}


def _observed(
    result: dict[str, Any], packet: dict[str, Any], rank: int, packet_digest: str
) -> None:
    card = packet["cards"][rank]
    observed = result.get("observed")
    require(
        isinstance(observed, dict)
        and set(observed)
        == {
            "argv",
            "environment",
            "main_identity",
            "vllm_identity",
            "kernel_identity",
            "runtime",
            "binaries",
            "model",
            "boot_id",
            "card_binding",
        },
        "observed identity schema drift",
    )
    require(
        observed["environment"] == card["environment"]
        and observed["argv"] == card["runner_argv"],
        "observed argv/environment drift",
    )
    for name, repo, commit in (
        ("main_identity", MAIN, git(MAIN, "rev-parse", "HEAD")),
        ("vllm_identity", VLLM, packet["source"]["vllm_commit"]),
        ("kernel_identity", KERNEL, packet["source"]["kernel_commit"]),
    ):
        value = observed[name]
        require(
            value
            == {
                "path": str(repo),
                "commit": commit,
                "clean": True,
                "status_porcelain": [],
                "status_sha256": hashlib.sha256(b"").hexdigest(),
            },
            f"observed {name} drift",
        )
    require(
        observed["runtime"] == packet["runtime"]
        and observed["binaries"] == packet["binaries"]
        and observed["model"] == packet["model"]
        and observed["boot_id"] == packet["boot_id"],
        "observed host identity drift",
    )
    physical = card["physical"]
    campaign_start_path = (
        Path(packet["campaign_root"]) / "campaign-start-checkpoint.json"
    )
    campaign_start = _read_canonical(campaign_start_path, "campaign start")
    require(
        campaign_start.get("packet_sha256") == packet_digest
        and campaign_start.get("packet_path") == packet["packet_path"],
        "observed campaign-start packet binding drift",
    )
    device_preflight = campaign_start.get("device_preflight")
    coordinator.validate_device_preflight(device_preflight, packet)
    filtered_probe = device_preflight["filtered"][rank]
    expected_pre_tensor_binding = {
        "packet_sha256": packet_digest,
        "rank": rank,
        "oneapi_device_selector": "level_zero:0",
        "ze_affinity_mask": str(rank),
        "logical_device_id": 0,
        "physical": physical,
        "sysfs": {
            "drm_device": physical["drm_device"],
            "pci_bdf_address": physical["pci_bdf_address"],
            "vendor": "0x8086",
            "device": "0xe223",
        },
        "sealed_device_preflight": {
            "campaign_start_path": str(campaign_start_path),
            "campaign_start_sha256": sha(campaign_start_path),
            "device_preflight_sha256": hashlib.sha256(
                canonical(device_preflight)
            ).hexdigest(),
            "unfiltered_stdout_sha256": device_preflight["unfiltered"]["stdout_sha256"],
            "filtered_stdout_sha256": filtered_probe["stdout_sha256"],
        },
    }
    require(
        observed["card_binding"] == expected_pre_tensor_binding,
        "observed pre-tensor per-card mapping drift",
    )
    expected_runtime_binding = {
        **expected_pre_tensor_binding,
        "visible_device_count": 1,
        "current_device": 0,
        "device_name": stage0.EXPECTED_DEVICE_NAME,
        "tensor_device": "xpu:0",
        "torch_version": packet["runtime"]["torch_version"],
        "runtime_uuid": physical["uuid"],
        "runtime_uuid_bytes_hex": physical["uuid"].replace("-", ""),
    }
    runtime_binding = result.get("runtime_card_binding")
    require(
        runtime_binding
        == {
            "format": "laguna-shared-gate-m8-component-runtime-card-binding-v1",
            "packet_sha256": packet_digest,
            "rank": rank,
            "binding": expected_runtime_binding,
        },
        "runtime Torch UUID/card binding drift",
    )
    actual = result.get("actual_forward_proof")
    require(
        isinstance(actual, dict)
        and set(actual) == {"binding", "scope", "packet_sha256", "rank"}
        and actual["binding"] == expected_runtime_binding
        and actual["packet_sha256"] == packet_digest
        and actual["rank"] == rank,
        "actual-forward card binding drift",
    )
    sealed_stage0 = _read_canonical(
        Path(packet["stage0"]["result_path"]), "sealed stage-zero result"
    )
    expected_scope = sealed_stage0["constructor_scope_proof"]
    require(actual["scope"] == expected_scope, "actual-forward constructor scope drift")
    dispatch = result.get("dispatch_proof")
    require(
        isinstance(dispatch, dict)
        and set(dispatch) == {"packet_sha256", "rank", "proof"}
        and dispatch["packet_sha256"] == packet_digest
        and dispatch["rank"] == rank,
        "dispatch packet binding drift",
    )
    stage0_analyzer.validate_dispatch_proof(dispatch["proof"])
    scope = result.get("constructor_scope_proof")
    require(
        isinstance(scope, dict)
        and set(scope) == {"packet_sha256", "rank", "scope"}
        and scope["packet_sha256"] == packet_digest
        and scope["rank"] == rank,
        "constructor packet binding drift",
    )
    require(scope["scope"] == actual["scope"], "constructor/actual scope split")


def validate_schema_for_cpu_tests(
    result: dict[str, Any], fixture: dict[str, Any], packet: dict[str, Any]
) -> dict[str, Any]:
    """Pure evidence grammar validator.  Does *not* grant production acceptance."""
    c.validate(packet)
    stage0.validate_fixture_manifest(fixture)
    rank = result.get("rank")
    require(isinstance(rank, int) and rank in range(4), "rank drift")
    card = packet["cards"][rank]
    required = {
        "format",
        "status",
        "passed",
        "rank",
        "physical",
        "packet_path",
        "packet_sha256",
        "downstream",
        "tensor_work_started",
        "checkpoints",
        "checkpoint_sha256",
        "constructor_scope_proof",
        "dispatch_proof",
        "actual_forward_proof",
        "runtime_card_binding",
        "observed",
        "pre_exactness",
        "timing",
        "post_exactness",
        "failure",
    }
    require(
        set(result) == required
        and result["format"] == "laguna-shared-gate-m8-four-card-component-result-v1",
        "result schema/format drift",
    )
    packet_digest = hashlib.sha256(canonical(packet) + b"\n").hexdigest()
    require(
        result["physical"] == card["physical"]
        and result["packet_path"] == packet["packet_path"]
        and result["packet_sha256"] == packet_digest
        and result["downstream"] == c.FALSE_ACTIONS
        and result["tensor_work_started"] is True
        and result["status"] == "component-card-pass"
        and result["passed"] is True
        and result["failure"] is None,
        "result identity/status/action drift",
    )
    _checkpoint_paths(result)
    exact = _exactness(result, fixture)
    timing = _timing(result["timing"], fixture)
    return {"rank": rank, "exact": exact, "timing": timing}


def validate_card(
    packet: dict[str, Any], fixture: dict[str, Any], rank: int, path: Path
) -> dict[str, Any]:
    card = packet["cards"][rank]
    root = Path(card["output_root"])
    require(
        path == Path(card["result"]) == root / RESULT_NAME,
        "result path/card root drift",
    )
    result = _read_canonical(path, f"card {rank} result")
    analysis = validate_schema_for_cpu_tests(result, fixture, packet)
    packet_digest = sha(Path(packet["packet_path"]))
    require(
        result["packet_sha256"] == packet_digest, "result packet file binding drift"
    )
    _observed(result, packet, rank, packet_digest)
    checkpoints = _checkpoints(root, result, packet_digest, rank)
    require(
        checkpoints["pre-tensor-identity-checkpoint.json"]
        == {
            "format": "laguna-shared-gate-m8-component-pre-tensor-v2",
            "packet_sha256": packet_digest,
            "rank": rank,
            "tensor_work_started": False,
            "observed": result["observed"],
        },
        "pre-tensor checkpoint drift",
    )
    require(
        checkpoints["tensor-work-started-checkpoint.json"]
        == {
            "format": "laguna-shared-gate-m8-component-tensor-start-v2",
            "packet_sha256": packet_digest,
            "rank": rank,
            "tensor_work_started": True,
        },
        "tensor-start checkpoint drift",
    )
    require(
        checkpoints["runtime-card-binding-checkpoint.json"]
        == result["runtime_card_binding"],
        "runtime-card-binding checkpoint drift",
    )
    return {
        "rank": rank,
        "uuid": card["physical"]["uuid"],
        "bdf": card["physical"]["pci_bdf_address"],
        "runtime_uuid": result["runtime_card_binding"]["binding"]["runtime_uuid"],
        "boot_id": result["observed"]["boot_id"],
        "fixture": analysis["exact"]["pre_fixture"],
        "output": analysis["exact"]["pre_output"],
        "post_fixture": analysis["exact"]["post_fixture"],
        "post_output": analysis["exact"]["post_output"],
        "timing": analysis["timing"],
        "result_sha256": sha(path),
    }


def _coordinator_evidence(
    packet: dict[str, Any], campaign: Path, *, final: bool = False
) -> set[str]:
    """Validate coordinator-owned durable files already present before analysis."""
    require(
        not Path(packet["preflight_failure_path"]).exists()
        and not Path(packet["preflight_failure_path"]).is_symlink(),
        "successful campaign has a preserved pre-root failure",
    )
    packet_digest = sha(Path(packet["packet_path"]))
    start = _read_canonical(
        campaign / "campaign-start-checkpoint.json", "campaign start"
    )
    require(
        set(start)
        == {
            "format",
            "status",
            "created_utc",
            "packet_path",
            "packet_sha256",
            "rank_order",
            "device_preflight",
            "downstream",
        }
        and start["format"] == "laguna-shared-gate-m8-component-campaign-start-v1"
        and start["status"] == "campaign_root_acquired_before_rank_execution"
        and isinstance(start["created_utc"], str)
        and start["created_utc"].endswith("Z")
        and start["packet_path"] == packet["packet_path"]
        and start["packet_sha256"] == packet_digest
        and start["rank_order"] == [0, 1, 2, 3]
        and start["downstream"] == c.FALSE_ACTIONS,
        "campaign-start binding/schema drift",
    )
    coordinator.validate_device_preflight(start["device_preflight"], packet)
    files = {"campaign-start-checkpoint.json"}
    for card in packet["cards"]:
        rank = card["rank"]
        name = f"rank-{rank}-terminal.json"
        terminal = _read_canonical(campaign / name, f"rank {rank} terminal")
        require(
            set(terminal)
            == {
                "format",
                "rank",
                "completed_utc",
                "argv",
                "environment",
                "exit_code",
                "result_path",
                "result_present",
                "result_sha256",
                "status",
                "downstream",
            }
            and terminal["format"] == "laguna-shared-gate-m8-component-leg-terminal-v1"
            and terminal["rank"] == rank
            and isinstance(terminal["completed_utc"], str)
            and terminal["completed_utc"].endswith("Z")
            and terminal["argv"] == card["runner_argv"]
            and terminal["environment"] == card["environment"]
            and terminal["exit_code"] == 0
            and terminal["result_path"] == card["result"]
            and terminal["result_present"] is True
            and terminal["result_sha256"] == sha(Path(card["result"]))
            and terminal["status"] == "rank_zero_exit"
            and terminal["downstream"] == c.FALSE_ACTIONS,
            f"rank {rank} terminal binding/schema drift",
        )
        files.add(name)
    terminal_path = Path(packet["campaign_terminal_path"])
    if not final:
        require(
            not terminal_path.exists(),
            "campaign terminal must not predate aggregate analysis",
        )
    else:
        terminal = _read_canonical(terminal_path, "campaign terminal")
        aggregate = Path(packet["aggregate_path"])
        expected_hashes = {
            str(card["rank"]): sha(Path(card["result"])) for card in packet["cards"]
        }
        require(
            set(terminal)
            == {
                "format",
                "status",
                "completed_utc",
                "failed_rank",
                "analyzer_invoked",
                "analyzer_argv",
                "analyzer_exit_code",
                "packet_sha256",
                "aggregate_path",
                "aggregate_sha256",
                "rank_result_sha256",
                "downstream",
            }
            and terminal["format"]
            == "laguna-shared-gate-m8-component-campaign-terminal-v1"
            and terminal["status"] == "component_aggregate_pending_final_seal"
            and isinstance(terminal["completed_utc"], str)
            and terminal["completed_utc"].endswith("Z")
            and terminal["failed_rank"] is None
            and terminal["analyzer_invoked"] is True
            and terminal["analyzer_argv"] == packet["analyzer_argv"]
            and terminal["analyzer_exit_code"] == 0
            and terminal["packet_sha256"] == sha(Path(packet["packet_path"]))
            and terminal["aggregate_path"] == str(aggregate)
            and terminal["aggregate_sha256"] == sha(aggregate)
            and terminal["rank_result_sha256"] == expected_hashes
            and terminal["downstream"] == c.FALSE_ACTIONS,
            "campaign terminal final-seal binding/schema drift",
        )
        files.add(terminal_path.name)
    return files


def _cross_card_invariants(packet: dict[str, Any], cards: list[dict[str, Any]]) -> None:
    require(
        len({x["uuid"] for x in cards})
        == len({x["runtime_uuid"] for x in cards})
        == len({x["bdf"] for x in cards})
        == 4,
        "physical/runtime card duplication",
    )
    require(
        all(x["uuid"] == x["runtime_uuid"] for x in cards),
        "Torch runtime UUID differs from frozen physical UUID",
    )
    require(
        len({x["boot_id"] for x in cards})
        == 1
        == len({packet["boot_id"] for _ in cards}),
        "cards do not share one frozen boot",
    )
    require(
        len({x["fixture"] for x in cards})
        == len({x["output"] for x in cards})
        == len({x["post_fixture"] for x in cards})
        == len({x["post_output"] for x in cards})
        == 1,
        "cross-card exact aggregate drift",
    )


def validate_production(
    packet: dict[str, Any], authorization: Path, card_results: list[Path], out: Path
) -> tuple[str, list[dict[str, Any]]]:
    """Production-only acceptance, including live immutable-host verification."""
    c.validate(packet)
    require(
        authorization == Path(packet["packet_path"]),
        "authorization argv differs from packet",
    )
    head = _packet_lineage(packet, authorization)
    _runtime_and_sources(packet)
    fixture, _ = _stage0(packet)
    require(
        len(card_results) == 4
        and card_results == [Path(card["result"]) for card in packet["cards"]],
        "card results must use frozen rank order",
    )
    campaign = Path(packet["campaign_root"])
    require(
        out == campaign / AGGREGATE_NAME and not out.exists() and not out.is_symlink(),
        "aggregate path must be fresh frozen campaign aggregate",
    )
    cards = [
        validate_card(packet, fixture, rank, path)
        for rank, path in enumerate(card_results)
    ]
    expected_files = _coordinator_evidence(packet, campaign)
    for card in packet["cards"]:
        prefix = Path(card["output_root"]).relative_to(campaign)
        result = _read_canonical(Path(card["result"]), "result inventory")
        expected_files.add(str(prefix / RESULT_NAME))
        expected_files.update(str(prefix / rel) for rel in _checkpoint_paths(result))
    # out is not written yet: remove its future name from the immediate tree check.
    _strict_tree(campaign, expected_files - {AGGREGATE_NAME})
    _cross_card_invariants(packet, cards)

    # Close the source/card/evidence race immediately before the caller seals
    # the aggregate.  The second pass is intentionally semantic, not just a
    # second path/hash inventory.
    require(
        _packet_lineage(packet, authorization) == head,
        "authorization lineage changed during aggregate validation",
    )
    _runtime_and_sources(packet)
    fixture_final, _ = _stage0(packet)
    final_cards = [
        validate_card(packet, fixture_final, rank, path)
        for rank, path in enumerate(card_results)
    ]
    require(final_cards == cards, "card evidence changed during aggregate validation")
    final_expected = _coordinator_evidence(packet, campaign)
    for card in packet["cards"]:
        prefix = Path(card["output_root"]).relative_to(campaign)
        result = _read_canonical(Path(card["result"]), "final result inventory")
        final_expected.add(str(prefix / RESULT_NAME))
        final_expected.update(str(prefix / rel) for rel in _checkpoint_paths(result))
    require(
        final_expected == expected_files,
        "campaign evidence inventory changed during aggregate validation",
    )
    _strict_tree(campaign, final_expected)
    _cross_card_invariants(packet, final_cards)
    return head, final_cards


def _validate_aggregate(
    packet: dict[str, Any], head: str, cards: list[dict[str, Any]], path: Path
) -> dict[str, Any]:
    aggregate = _read_canonical(path, "component aggregate")
    require(
        set(aggregate)
        == {
            "format",
            "status",
            "passed",
            "authorization_head",
            "packet_sha256",
            "cards",
            "downstream",
        }
        and aggregate["format"]
        == "laguna-shared-gate-m8-four-card-component-aggregate-v2"
        and aggregate["status"] == "component_aggregate_pending_final_seal"
        and aggregate["passed"] is True
        and aggregate["authorization_head"] == head
        and aggregate["packet_sha256"] == sha(Path(packet["packet_path"]))
        and aggregate["cards"] == cards
        and aggregate["downstream"] == c.FALSE_ACTIONS,
        "aggregate pending-final-seal semantics drift",
    )
    return aggregate


def _final_cards(
    packet: dict[str, Any], authorization: Path
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Repeat the complete live/source/card validation before final sealing."""
    c.validate(packet)
    require(
        authorization == Path(packet["packet_path"]),
        "finalizer authorization argv drift",
    )
    head = _packet_lineage(packet, authorization)
    _runtime_and_sources(packet)
    fixture, _ = _stage0(packet)
    cards = [
        validate_card(packet, fixture, rank, Path(card["result"]))
        for rank, card in enumerate(packet["cards"])
    ]
    _cross_card_invariants(packet, cards)
    campaign = Path(packet["campaign_root"])
    expected = _coordinator_evidence(packet, campaign, final=True)
    for card in packet["cards"]:
        prefix = Path(card["output_root"]).relative_to(campaign)
        result = _read_canonical(Path(card["result"]), "final result inventory")
        expected.add(str(prefix / RESULT_NAME))
        expected.update(str(prefix / rel) for rel in _checkpoint_paths(result))
    expected.add(Path(packet["aggregate_path"]).name)
    return head, cards, {"campaign": campaign, "expected": expected}


def _pre_manifest_hashes(
    campaign: Path, expected: set[str], *, final_manifest: Path | None = None
) -> dict[str, str]:
    actual_expected = set(expected)
    if final_manifest is not None:
        require(final_manifest.parent == campaign, "final manifest escapes campaign")
        actual_expected.add(final_manifest.name)
    _strict_tree(campaign, actual_expected)
    return {relative: sha(campaign / relative) for relative in sorted(expected)}


def finalize_production(
    packet: dict[str, Any],
    authorization: Path,
    card_results: list[Path],
    aggregate: Path,
    campaign_terminal: Path,
    final_manifest: Path,
) -> dict[str, Any]:
    require(
        card_results == [Path(card["result"]) for card in packet["cards"]],
        "finalizer card argv order drift",
    )
    require(
        aggregate == Path(packet["aggregate_path"])
        and campaign_terminal == Path(packet["campaign_terminal_path"])
        and final_manifest == Path(packet["final_manifest_path"]),
        "finalizer path argv drift",
    )
    require(
        not final_manifest.exists() and not final_manifest.is_symlink(),
        "final manifest path is not fresh",
    )
    head, cards, state = _final_cards(packet, authorization)
    _validate_aggregate(packet, head, cards, aggregate)
    pre_hashes = _pre_manifest_hashes(state["campaign"], state["expected"])
    final_head, final_cards, final_state = _final_cards(packet, authorization)
    require(
        final_head == head
        and final_cards == cards
        and final_state["campaign"] == state["campaign"]
        and final_state["expected"] == state["expected"],
        "source/card/tree state changed during finalization",
    )
    _validate_aggregate(packet, final_head, final_cards, aggregate)
    final_pre_hashes = _pre_manifest_hashes(
        final_state["campaign"], final_state["expected"]
    )
    require(
        final_pre_hashes == pre_hashes,
        "pre-manifest evidence bytes changed during finalization",
    )
    return {
        "format": "laguna-shared-gate-m8-four-card-component-final-manifest-v1",
        "status": "component_final_seal_passed_counter_tooling_construction_authorized",
        "passed": True,
        "packet_path": packet["packet_path"],
        "packet_sha256": sha(authorization),
        "authorization_head": final_head,
        "aggregate_path": str(aggregate),
        "aggregate_sha256": sha(aggregate),
        "campaign_terminal_path": str(campaign_terminal),
        "campaign_terminal_sha256": sha(campaign_terminal),
        "finalizer_argv": packet["finalizer_argv"],
        "final_verifier_argv": packet["final_verifier_argv"],
        "pre_manifest_sha256": final_pre_hashes,
        "downstream": {
            **c.FALSE_ACTIONS,
            "counter_tooling_construction_authorized": True,
        },
    }


def verify_final_production(
    packet: dict[str, Any],
    authorization: Path,
    card_results: list[Path],
    aggregate: Path,
    campaign_terminal: Path,
    final_manifest: Path,
) -> None:
    require(
        card_results == [Path(card["result"]) for card in packet["cards"]],
        "final verifier card argv order drift",
    )
    require(
        aggregate == Path(packet["aggregate_path"])
        and campaign_terminal == Path(packet["campaign_terminal_path"])
        and final_manifest == Path(packet["final_manifest_path"]),
        "final verifier path argv drift",
    )
    head, cards, state = _final_cards(packet, authorization)
    _validate_aggregate(packet, head, cards, aggregate)
    manifest = _read_canonical(final_manifest, "component final manifest")
    expected_downstream = {
        **c.FALSE_ACTIONS,
        "counter_tooling_construction_authorized": True,
    }
    expected = {
        "format": "laguna-shared-gate-m8-four-card-component-final-manifest-v1",
        "status": "component_final_seal_passed_counter_tooling_construction_authorized",
        "passed": True,
        "packet_path": packet["packet_path"],
        "packet_sha256": sha(authorization),
        "authorization_head": head,
        "aggregate_path": str(aggregate),
        "aggregate_sha256": sha(aggregate),
        "campaign_terminal_path": str(campaign_terminal),
        "campaign_terminal_sha256": sha(campaign_terminal),
        "finalizer_argv": packet["finalizer_argv"],
        "final_verifier_argv": packet["final_verifier_argv"],
        "downstream": expected_downstream,
    }
    require(
        set(manifest) == set(expected) | {"pre_manifest_sha256"}
        and all(manifest[key] == value for key, value in expected.items()),
        "final manifest schema/identity drift",
    )
    pre_hashes = _pre_manifest_hashes(
        state["campaign"], state["expected"], final_manifest=final_manifest
    )
    require(
        manifest["pre_manifest_sha256"] == pre_hashes,
        "final manifest pre-tree hash map drift",
    )
    _strict_tree(state["campaign"], state["expected"] | {final_manifest.name})


def _exclusive_json(path: Path, value: dict[str, Any]) -> None:
    c._absolute_non_usb(path)
    require(
        path.parent.is_dir() and not path.parent.is_symlink(),
        "analyzer output parent must already exist",
    )
    payload = canonical(value) + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        offset = 0
        while offset < len(payload):
            wrote = os.write(fd, payload[offset:])
            require(wrote > 0, "short write while sealing aggregate")
            offset += wrote
        os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--card-result", action="append", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--verify-final", action="store_true")
    parser.add_argument("--aggregate", type=Path)
    parser.add_argument("--campaign-terminal", type=Path)
    parser.add_argument("--final-manifest", type=Path)
    args = parser.parse_args()
    require(
        not (args.finalize and args.verify_final),
        "analyzer modes are mutually exclusive",
    )
    packet = _read_canonical(args.authorization, "authorization")
    require(
        dict(os.environ) == packet["coordinator_environment"],
        "analyzer process environment differs from frozen coordinator environment",
    )
    if args.finalize or args.verify_final:
        require(
            args.out is None
            and args.aggregate is not None
            and args.campaign_terminal is not None
            and args.final_manifest is not None,
            "final-seal analyzer arguments drift",
        )
        expected = (
            packet["finalizer_argv"] if args.finalize else packet["final_verifier_argv"]
        )
        require(
            sys.argv == expected[1:], "final-seal analyzer argv differs from packet"
        )
        if args.finalize:
            manifest = finalize_production(
                packet,
                args.authorization,
                args.card_result,
                args.aggregate,
                args.campaign_terminal,
                args.final_manifest,
            )
            _exclusive_json(args.final_manifest, manifest)
            print(
                json.dumps(
                    {"passed": True, "final_manifest": str(args.final_manifest)},
                    sort_keys=True,
                )
            )
            return 0
        verify_final_production(
            packet,
            args.authorization,
            args.card_result,
            args.aggregate,
            args.campaign_terminal,
            args.final_manifest,
        )
        print(
            json.dumps(
                {"passed": True, "verified_final_manifest": str(args.final_manifest)},
                sort_keys=True,
            )
        )
        return 0
    require(
        args.out is not None
        and args.aggregate is None
        and args.campaign_terminal is None
        and args.final_manifest is None,
        "initial analyzer arguments drift",
    )
    require(
        sys.argv == packet["analyzer_argv"][1:],
        "initial analyzer argv differs from packet",
    )
    head, cards = validate_production(
        packet, args.authorization, args.card_result, args.out
    )
    aggregate = {
        "format": "laguna-shared-gate-m8-four-card-component-aggregate-v2",
        "status": "component_aggregate_pending_final_seal",
        "passed": True,
        "authorization_head": head,
        "packet_sha256": sha(args.authorization),
        "cards": cards,
        "downstream": c.FALSE_ACTIONS,
    }
    _exclusive_json(args.out, aggregate)
    print(json.dumps({"passed": True, "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
