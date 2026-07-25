#!/usr/bin/env python3
"""Offline fail-closed analyzer for the DFlash context-KV component gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

EXPECTED_COMMIT = "4459910e2ac5a7b552887fc0a3f3e3cf9a4701c0"
EXPECTED_KERNEL = "4772f727590c51b72add79350b913d098cf67872"
EXPECTED_MODEL = "0850e39b5c079a9f1a9bafed729a4545b088a91876541d010d871f6d6d8bf909"
EXPECTED_CONFIG = "6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926"
EXPECTED_WIDTHS = list(range(1, 9))
EXPECTED_BRANCHES = {"actual_no_bias": False, "synthetic_bias": True}
EXPECTED_DEVICES = (
    (0, "/dev/dri/card3", "0000:23:00.0", "00000000-0000-0023-0000-0000e2238086"),
    (1, "/dev/dri/card4", "0000:27:00.0", "00000000-0000-0027-0000-0000e2238086"),
    (2, "/dev/dri/card0", "0000:43:00.0", "00000000-0000-0043-0000-0000e2238086"),
    (3, "/dev/dri/card2", "0000:47:00.0", "00000000-0000-0047-0000-0000e2238086"),
)
EXPECTED_KERNEL_HASHES = {
    "_C.abi3.so": "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2",
    "_xpu_C.abi3.so": "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8",
    "_moe_C.abi3.so": "6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b",
}
AUTHORIZATION_ROOT = Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations"
)
HEX = set("0123456789abcdef")
TOOLS = (
    Path(
        "/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/"
        "run_laguna_dflash_context_kv_component.sh"
    ),
    Path(
        "/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/"
        "create_laguna_dflash_context_kv_consumption.py"
    ),
    Path(
        "/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/"
        "run_laguna_dflash_context_kv_component.py"
    ),
    Path(
        "/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/"
        "analyze_laguna_dflash_context_kv_component.py"
    ),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Laguna context-KV analyzer: {message}")


def valid_sha(value: Any, length: int = 64) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in HEX for character in value)
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def contiguous_stride(shape: list[int]) -> list[int]:
    stride = []
    value = 1
    for size in reversed(shape):
        stride.append(value)
        value *= size
    return list(reversed(stride))


def physical_mapping(payload: Any, label: str) -> list[tuple[Any, Any, Any, Any]]:
    require(isinstance(payload, dict), f"{label}: discovery payload is not an object")
    observed = payload.get("device_list")
    require(isinstance(observed, list), f"{label}: device_list is absent")
    rows = []
    for row in observed:
        require(isinstance(row, dict), f"{label}: device row is not an object")
        if (
            row.get("device_function_type") == "physical"
            and row.get("device_name") == "Intel(R) Arc(TM) Pro B70 Graphics"
        ):
            rows.append(
                (
                    row.get("device_id"),
                    row.get("drm_device"),
                    row.get("pci_bdf_address"),
                    row.get("uuid"),
                )
            )
    return rows


def validate_physical_mapping(
    payload: Any,
    expected: list[tuple[Any, Any, Any, Any]],
    label: str,
) -> list[tuple[Any, Any, Any, Any]]:
    observed = physical_mapping(payload, label)
    require(observed == expected, f"{label}: physical mapping drift")
    return observed


def validate_tensor_record(
    record: Any,
    *,
    shape: list[int],
    label: str,
) -> None:
    require(isinstance(record, dict), f"{label}: tensor record absent")
    require(record.get("shape") == shape, f"{label}: shape drift")
    require(record.get("stride") == contiguous_stride(shape), f"{label}: stride drift")
    require(record.get("dtype") == "torch.bfloat16", f"{label}: dtype drift")
    require(record.get("device") == "xpu:0", f"{label}: device drift")
    require(record.get("nbytes") == math.prod(shape) * 2, f"{label}: nbytes drift")
    require(
        isinstance(record.get("data_ptr"), int) and record["data_ptr"] > 0,
        f"{label}: pointer invalid",
    )
    require(record.get("storage_offset") == 0, f"{label}: storage offset drift")
    require(valid_sha(record.get("sha256")), f"{label}: digest invalid")


def validate_comparison(
    comparison: Any,
    *,
    shape: list[int],
    label: str,
) -> None:
    require(isinstance(comparison, dict), f"{label}: comparison absent")
    require(comparison.get("equal") is True, f"{label}: equality false")
    validate_tensor_record(comparison.get("actual"), shape=shape, label=label)
    require(
        comparison["actual"]["sha256"] == comparison.get("expected_sha256"),
        f"{label}: actual/expected digest mismatch",
    )


def write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
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
            require(written > 0, "short analysis write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def validate_preimport(
    root: Path,
    result: dict[str, Any],
    rank: int,
    main_commit: str,
) -> None:
    preimport = Path(result.get("preimport_path", ""))
    require(
        preimport == root / "cards" / f"rank{rank}.preimport.json"
        and preimport.is_file()
        and not preimport.is_symlink()
        and (preimport.stat().st_mode & 0o777) == 0o600
        and valid_sha(result.get("preimport_sha256"))
        and hashlib.sha256(preimport.read_bytes()).hexdigest()
        == result["preimport_sha256"],
        f"rank {rank} preimport seal drift",
    )
    record = json.loads(preimport.read_text())
    require(
        record.get("schema") == "laguna-dflash-context-kv-preimport-v1"
        and record.get("rank") == rank
        and record.get("main_commit") == main_commit
        and record.get("vllm_commit") == EXPECTED_COMMIT
        and record.get("kernel_commit") == EXPECTED_KERNEL
        and record.get("model_sha256") == EXPECTED_MODEL
        and record.get("config_sha256") == EXPECTED_CONFIG,
        f"rank {rank} preimport identity drift",
    )
    require(
        record.get("consumption_marker") == result.get("consumption_marker")
        and record.get("consumption_marker_sha256")
        == result.get("consumption_marker_sha256"),
        f"rank {rank} preimport consumption linkage drift",
    )
    require(
        record.get("forbidden_actions")
        == {
            "generation": False,
            "service": False,
            "network": False,
            "timing": False,
            "submission": False,
        },
        f"rank {rank} preimport authority drift",
    )
    environment = record.get("environment")
    require(
        isinstance(environment, dict)
        and environment.get("ONEAPI_DEVICE_SELECTOR") == "level_zero:0"
        and environment.get("ZE_AFFINITY_MASK") == str(rank)
        and environment.get("VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE") == "1",
        f"rank {rank} preimport environment drift",
    )
    require(
        valid_sha(record.get("worker_sha256"))
        and isinstance(record.get("source_sha256"), dict)
        and all(valid_sha(value) for value in record["source_sha256"].values()),
        f"rank {rank} preimport source hashes invalid",
    )


def validate_campaign_identity(root: Path, main_commit: str) -> None:
    identity = root / "identity.txt"
    consumed = root / "consumed.txt"
    require(
        identity.is_file()
        and not identity.is_symlink()
        and consumed.is_file()
        and not consumed.is_symlink(),
        "campaign identity/consumption seal absent",
    )
    lines = identity.read_text().splitlines()
    require(
        lines[:5]
        == [
            "schema=laguna-dflash-context-kv-component-campaign-v1",
            "purpose=exactness-only component; generation=false; timing=false; "
            "endpoint=false; submission=false",
            f"vllm={EXPECTED_COMMIT}",
            f"kernels={EXPECTED_KERNEL}",
            f"main={main_commit}",
        ],
        "campaign identity header drift",
    )
    require(len(lines) == 5 + len(TOOLS), "campaign tool manifest length drift")
    for line, tool in zip(lines[5:], TOOLS):
        parts = line.split()
        require(
            len(parts) == 2 and parts[0] == sha256_file(tool) and parts[1] == str(tool),
            f"campaign tool identity drift: {tool.name}",
        )
    require(
        consumed.read_text() == f"consumed=true\nmain={main_commit}\n",
        "campaign consumption seal drift",
    )


def validate_external_consumption(
    root: Path,
    result: dict[str, Any],
    main_commit: str,
) -> None:
    marker = Path(result.get("consumption_marker", ""))
    identity_sha = sha256_file(root / "identity.txt")
    require(
        marker.parent == AUTHORIZATION_ROOT
        and marker.is_file()
        and not marker.is_symlink()
        and (marker.stat().st_mode & 0o777) == 0o400
        and valid_sha(result.get("consumption_marker_sha256"))
        and sha256_file(marker) == result["consumption_marker_sha256"],
        "external packet consumption marker drift",
    )
    record = json.loads(marker.read_text())
    require(
        record
        == {
            "schema": "laguna-dflash-context-kv-component-consumption-v1",
            "main_commit": main_commit,
            "vllm_commit": EXPECTED_COMMIT,
            "kernel_commit": EXPECTED_KERNEL,
            "run_root": str(root),
            "packet_sha256": identity_sha,
        },
        "external packet consumption contents drift",
    )


def validate_capture_rejection(result: dict[str, Any], rank: int) -> None:
    record = result.get("capture_rejection")
    require(isinstance(record, dict), f"rank {rank} capture rejection absent")
    pointers_before = record.get("workspace_pointers_before")
    pointers_after = record.get("workspace_pointers_after")
    hashes_before = record.get("workspace_hashes_before")
    hashes_after = record.get("workspace_hashes_after")
    cache_before = record.get("cache_hashes_before")
    cache_after = record.get("cache_hashes_after")
    require(
        record.get("eager_false_before") is True
        and record.get("capture_true") is True
        and record.get("eager_false_after") is True
        and record.get("rejection_type") == "RuntimeError"
        and record.get("rejection_message")
        == "Laguna DFlash context-KV workspace is forbidden during capture"
        and record.get("workspace_widths_before_after") == [[1], [1]],
        f"rank {rank} capture-state/rejection drift",
    )
    require(
        isinstance(pointers_before, list)
        and len(pointers_before) == 4
        and len(set(pointers_before)) == 4
        and all(isinstance(pointer, int) and pointer > 0 for pointer in pointers_before)
        and pointers_after == pointers_before,
        f"rank {rank} capture pointer mutation",
    )
    require(
        isinstance(hashes_before, list)
        and len(hashes_before) == 4
        and all(valid_sha(value) for value in hashes_before)
        and hashes_after == hashes_before
        and isinstance(cache_before, list)
        and len(cache_before) == 6
        and all(valid_sha(value) for value in cache_before)
        and cache_after == cache_before
        and isinstance(record.get("context_sha256_before_after"), list)
        and len(record["context_sha256_before_after"]) == 2
        and valid_sha(record["context_sha256_before_after"][0])
        and record["context_sha256_before_after"][0]
        == record["context_sha256_before_after"][1],
        f"rank {rank} capture state mutation",
    )


def validate_weight_source(result: dict[str, Any], rank: int) -> None:
    source = result.get("weight_source")
    require(
        isinstance(source, list) and len(source) == 6,
        f"rank {rank} weight source absent",
    )
    q_width = 72 * 128 // 4
    for layer, record in enumerate(source):
        require(
            record.get("layer") == layer
            and record.get("qkv_name") == f"layers.{layer}.self_attn.qkv_proj.weight"
            and record.get("qkv_shape") == [11264, 3072]
            and record.get("local_qkv_shape") == [q_width + 512, 3072]
            and record.get("local_q_rows") == [rank * q_width, (rank + 1) * q_width]
            and record.get("local_k_rows")
            == [9216 + rank * 256, 9216 + (rank + 1) * 256]
            and record.get("local_v_rows")
            == [10240 + rank * 256, 10240 + (rank + 1) * 256]
            and all(
                valid_sha(record.get(field))
                for field in (
                    "local_qkv_sha256",
                    "local_kv_sha256",
                    "input_norm_sha256",
                    "k_norm_sha256",
                )
            ),
            f"rank {rank}/layer {layer} checkpoint slice drift",
        )
    proof = result.get("buffer_build_proof")
    require(
        isinstance(proof, dict)
        and proof.get("builder") == "DFlashLagunaModel._build_context_kv_buffers"
        and proof.get("has_bias") is False
        and proof.get("q_size") == 2304,
        f"rank {rank} actual buffer builder proof drift",
    )
    require(
        result.get("checkpoint_qkv_bias_keys") == []
        and proof.get("layer_kv_sha256")
        == [record["local_kv_sha256"] for record in source]
        and proof.get("layer_input_norm_sha256")
        == [record["input_norm_sha256"] for record in source]
        and proof.get("layer_k_norm_sha256")
        == [record["k_norm_sha256"] for record in source],
        f"rank {rank} checkpoint-to-builder digest linkage drift",
    )
    validate_tensor_record(
        proof.get("kv_weights"),
        shape=[6, 512, 3072],
        label=f"rank {rank} built KV weights",
    )
    validate_tensor_record(
        proof.get("input_norms"),
        shape=[6, 3072],
        label=f"rank {rank} built input norms",
    )
    validate_tensor_record(
        proof.get("k_norms"),
        shape=[6, 128],
        label=f"rank {rank} built K norms",
    )


def validate_branch(branch: Any, rank: int) -> tuple[str, dict[tuple[int, int], str]]:
    require(isinstance(branch, dict), f"rank {rank} branch absent")
    name = branch.get("branch")
    require(name in EXPECTED_BRANCHES, f"rank {rank} unknown branch")
    require(
        branch.get("bias") is EXPECTED_BRANCHES[name],
        f"rank {rank}/{name} bias marker drift",
    )
    rows = branch.get("rows")
    require(isinstance(rows, list) and len(rows) == 16, f"rank {rank}/{name} row count")
    matrix = {(row.get("width"), row.get("repeat")) for row in rows}
    require(
        matrix == {(width, repeat) for width in EXPECTED_WIDTHS for repeat in range(2)},
        f"rank {rank}/{name} matrix coverage drift",
    )
    require(
        branch.get("workspace_widths") == EXPECTED_WIDTHS
        and branch.get("fallback_widths") == [9],
        f"rank {rank}/{name} workspace/fallback drift",
    )
    pointer_map = branch.get("workspace_pointers")
    require(isinstance(pointer_map, dict), f"rank {rank}/{name} pointer map absent")
    contexts: dict[tuple[int, int], str] = {}
    for row in rows:
        width = row["width"]
        repeat = row["repeat"]
        coordinate = (width, repeat)
        context_hash = row.get("context_sha256")
        require(
            coordinate not in contexts and valid_sha(context_hash),
            f"rank {rank}/{name} context evidence drift",
        )
        contexts[coordinate] = context_hash
        pointers = row.get("workspace_pointers")
        require(
            isinstance(pointers, list)
            and len(pointers) == 4
            and len(set(pointers)) == 4
            and all(isinstance(pointer, int) and pointer > 0 for pointer in pointers)
            and pointer_map.get(str(width)) == pointers,
            f"rank {rank}/{name}/C{width}/r{repeat} pointer drift",
        )
        require(
            row.get("warnings") == [],
            f"rank {rank}/{name}/C{width}/r{repeat} warning evidence drift",
        )
        boundaries = row.get("boundaries")
        expected_shapes = {
            "normed_context": [6, width, 3072],
            "flat": [6, width, 512],
            "projected_k": [6, width, 2, 128],
            "projected_v": [6, width, 2, 128],
            "normalized_k": [6, width, 2, 128],
            "rope_k": [6, width, 2, 128],
        }
        require(
            isinstance(boundaries, dict) and set(boundaries) == set(expected_shapes),
            f"rank {rank}/{name} boundary coverage drift",
        )
        for boundary, shape in expected_shapes.items():
            validate_comparison(
                boundaries[boundary],
                shape=shape,
                label=f"rank {rank}/{name}/C{width}/r{repeat}/{boundary}",
            )
        caches = row.get("cache_layers")
        require(
            isinstance(caches, list) and len(caches) == 6,
            f"rank {rank}/{name} cache coverage drift",
        )
        for layer, cache in enumerate(caches):
            validate_comparison(
                cache,
                shape=[4, 2, 16, 256],
                label=f"rank {rank}/{name}/C{width}/r{repeat}/cache{layer}",
            )
    require(
        len(set(contexts.values())) == 16,
        f"rank {rank}/{name} contexts are not all fresh",
    )
    return name, contexts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(
        not args.out.exists() and not args.out.is_symlink(),
        "fresh output required",
    )
    canonical_root = args.root.resolve(strict=True)
    require(
        canonical_root.is_relative_to(
            Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs")
        )
        and args.out.parent.resolve(strict=True) == canonical_root,
        "analysis paths are outside the canonical NVMe campaign root",
    )

    results = []
    mappings = []
    main_commit = None
    for rank in range(4):
        path = args.root / "cards" / f"rank{rank}.json"
        require(
            path.is_file()
            and not path.is_symlink()
            and (path.stat().st_mode & 0o777) == 0o600,
            f"missing or unsafe rank {rank}",
        )
        result = json.loads(path.read_text())
        require(
            result.get("schema") == "laguna-dflash-context-kv-component-v1"
            and result.get("status") == "exact_component_pass"
            and result.get("rank") == rank,
            f"rank {rank} status/schema drift",
        )
        observed_main = result.get("main_commit")
        require(valid_sha(observed_main, 40), f"rank {rank} main commit invalid")
        main_commit = observed_main if main_commit is None else main_commit
        require(observed_main == main_commit, f"rank {rank} main commit drift")
        require(
            result.get("vllm_commit") == EXPECTED_COMMIT
            and result.get("kernel_commit") == EXPECTED_KERNEL
            and result.get("model_sha256") == EXPECTED_MODEL
            and result.get("config_sha256") == EXPECTED_CONFIG
            and result.get("kernel_identity") == EXPECTED_KERNEL_HASHES,
            f"rank {rank} source identity drift",
        )
        require(
            result.get("vllm_root")
            == "/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725"
            and result.get("kernel_root")
            == "/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727"
            and result.get("model_root")
            == "/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4",
            f"rank {rank} source root drift",
        )
        require(
            result.get("non_timing") is True
            and all(
                result.get(name) is False
                for name in ("generation", "service", "network", "submission")
            ),
            f"rank {rank} forbidden-action marker drift",
        )
        require(
            result.get("visible_xpus") == 1
            and result.get("capture_api")
            == {"present": True, "eager_before": False, "eager_after": False},
            f"rank {rank} runtime gate drift",
        )
        validate_capture_rejection(result, rank)
        require(
            result.get("required_widths") == EXPECTED_WIDTHS
            and result.get("repeats") == 2
            and valid_sha(result.get("synthetic_bias_sha256")),
            f"rank {rank} matrix/bias evidence drift",
        )
        branches = result.get("branches")
        require(
            isinstance(branches, list) and len(branches) == 2,
            f"rank {rank} branch count drift",
        )
        branch_contexts = {}
        for branch in branches:
            name, contexts = validate_branch(branch, rank)
            require(name not in branch_contexts, f"rank {rank} duplicate branch")
            branch_contexts[name] = contexts
        require(
            set(branch_contexts) == set(EXPECTED_BRANCHES)
            and branch_contexts["actual_no_bias"] == branch_contexts["synthetic_bias"],
            f"rank {rank} branch coverage/input drift",
        )
        require(
            result.get("weight_hashes_before") == result.get("weight_hashes_after"),
            f"rank {rank} weight mutation",
        )
        proof = result.get("buffer_build_proof", {})
        require(
            result.get("weight_hashes_before")
            == {
                "kv_weights": proof.get("kv_weights", {}).get("sha256"),
                "input_norms": proof.get("input_norms", {}).get("sha256"),
                "k_norms": proof.get("k_norms", {}).get("sha256"),
            },
            f"rank {rank} builder/runtime weight linkage drift",
        )
        validate_weight_source(result, rank)
        validate_preimport(args.root, result, rank, main_commit)
        validate_external_consumption(args.root, result, main_commit)
        selected = result["device_discovery"]["selected"]
        expected_device = EXPECTED_DEVICES[rank]
        require(
            (
                selected.get("device_id"),
                selected.get("drm_device"),
                selected.get("pci_bdf_address"),
                selected.get("uuid"),
            )
            == expected_device,
            f"rank {rank} physical binding drift",
        )
        require(
            result["device_discovery"].get("unfiltered_path")
            == str(args.root / "device-discovery.json"),
            f"rank {rank} filtered/unfiltered discovery linkage drift",
        )
        unfiltered_path = args.root / "device-discovery.json"
        filtered_path = args.root / "cards" / f"rank{rank}.device-discovery.json"
        require(
            unfiltered_path.is_file()
            and not unfiltered_path.is_symlink()
            and filtered_path.is_file()
            and not filtered_path.is_symlink()
            and result["device_discovery"].get("filtered_path") == str(filtered_path)
            and valid_sha(result["device_discovery"].get("unfiltered_sha256"))
            and valid_sha(result["device_discovery"].get("filtered_sha256"))
            and sha256_file(unfiltered_path)
            == result["device_discovery"]["unfiltered_sha256"]
            and sha256_file(filtered_path)
            == result["device_discovery"]["filtered_sha256"],
            f"rank {rank} discovery artifact identity drift",
        )
        parsed_unfiltered = validate_physical_mapping(
            json.loads(unfiltered_path.read_text()),
            list(EXPECTED_DEVICES),
            f"rank {rank} unfiltered",
        )
        parsed_filtered = validate_physical_mapping(
            json.loads(filtered_path.read_text()),
            [expected_device],
            f"rank {rank} filtered",
        )
        reported_unfiltered = [
            (
                row.get("device_id"),
                row.get("drm_device"),
                row.get("pci_bdf_address"),
                row.get("uuid"),
            )
            for row in result["device_discovery"].get("unfiltered_mapping", [])
        ]
        reported_filtered = [
            (
                row.get("device_id"),
                row.get("drm_device"),
                row.get("pci_bdf_address"),
                row.get("uuid"),
            )
            for row in result["device_discovery"].get("filtered_mapping", [])
        ]
        require(
            reported_unfiltered == parsed_unfiltered
            and reported_filtered == parsed_filtered,
            f"rank {rank} discovery artifact semantics drift",
        )
        mappings.append(expected_device)
        results.append(
            {
                "rank": rank,
                "status": result["status"],
                "selected_device": selected,
                "actual_rows": 16,
                "synthetic_bias_rows": 16,
            }
        )
    require(len(set(mappings)) == 4, "physical cards are not distinct")
    require(main_commit is not None, "main commit was not established")
    validate_campaign_identity(args.root, main_commit)
    write_exclusive(
        args.out,
        {
            "schema": "laguna-dflash-context-kv-component-analysis-v1",
            "status": "exact_four_card_component_pass",
            "authority": "component_only_no_endpoint_or_benchmark",
            "main_commit": main_commit,
            "vllm_commit": EXPECTED_COMMIT,
            "kernel_commit": EXPECTED_KERNEL,
            "cards": results,
        },
    )
    print("exact_four_card_component_pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
