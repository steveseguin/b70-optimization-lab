#!/usr/bin/env python3
"""The deliberately late-imported native half of the M8 Phase-A harness.

This file is *not* an executable.  The Phase-A runner imports it only after it
has authenticated the two packets, consumed its inherited one-shot capability,
retained every input and library descriptor, and durably sealed a pre-import
checkpoint.  Keep imports here standard-library-only: importing this module is
not itself an accelerator action.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import statistics
import uuid
from pathlib import Path
from typing import Any


TOKENS, TOPK, HIDDEN, RANKS = 8, 10, 3072, 4
LAYERS, PRE_EPOCHS, POST_EPOCHS = 47, 256, 32
WARM_CYCLES, ABBA_BLOCKS, CYCLES_PER_ARM = 20, 31, 64
LIBRARIES_TO_LOAD = (
    "libgdn_attn_kernels_xe_2.so", "libgrouped_gemm_xe_2.so",
    "libgrouped_gemm_xe_default.so", "libmhc_kernels_xe_2.so", "libmqa_logits_kernels_xe_2.so",
    "shared-_C.abi3.so", "shared-_xpu_C.abi3.so", "candidate-_moe_C.abi3.so",
)
DEPENDENCY_LIBRARIES = LIBRARIES_TO_LOAD[:5]
_DEPENDENCY_HANDLES: list[Any] = []


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def _sha_fd(fd: int) -> tuple[str, os.stat_result]:
    before = os.fstat(fd)
    digest = hashlib.sha256()
    position = 0
    while position < before.st_size:
        block = os.pread(fd, min(1024 * 1024, before.st_size - position), position)
        require(block, "short descriptor read")
        digest.update(block)
        position += len(block)
    after = os.fstat(fd)
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "retained descriptor changed")
    return digest.hexdigest(), after


def _uuid_bytes(value: Any) -> bytes:
    """Normalize all Torch UUID representations without accepting text guesswork."""
    try:
        # The accepted runtime is deliberately the installed Torch private XPU
        # representation, not an opportunistic text/bytes fallback.
        require(type(value).__module__ == "torch._C" and type(value).__name__ == "_XPUuuid",
                "unexpected Torch XPU UUID type")
        raw_value = getattr(value, "bytes")
        require(isinstance(raw_value, list) and len(raw_value) == 16,
                "unsupported Torch UUID object")
        require(all(isinstance(item, int) and 0 <= item <= 255 for item in raw_value),
                "malformed Torch UUID bytes")
        raw = bytes(raw_value)
        text = str(value).lower()
        require(text == str(uuid.UUID(bytes=raw)).lower(), "Torch UUID text/bytes disagree")
        return raw
    except (AttributeError, TypeError, ValueError) as error:
        raise RuntimeError("malformed Torch UUID") from error


def _runtime_card_binding(torch: Any, physical: dict[str, Any]) -> dict[str, Any]:
    require(torch.__version__ == "2.12.0+xpu" and torch.xpu.is_available(), "Torch/XPU identity drift")
    require(os.environ.get("ONEAPI_DEVICE_SELECTOR") == "level_zero:0" and
            os.environ.get("ZE_AFFINITY_MASK") == str(physical["physical_rank"]), "logical selector/affinity drift")
    require(torch.xpu.device_count() == 1 and torch.xpu.current_device() == 0,
            "one visible/reindexed XPU required")
    bdf = physical["bdf"]
    drm = Path(physical["drm_card"])
    require(drm.name.startswith("card") and drm.exists(), "DRM card absent")
    sysfs = (Path("/sys/class/drm") / drm.name / "device").resolve(strict=True)
    require(sysfs.name == bdf and (sysfs / "vendor").read_text().strip() == "0x8086" and
            (sysfs / "device").read_text().strip() == "0xe223", "DRM/B70 BDF binding")
    properties = torch.xpu.get_device_properties(0)
    require(getattr(properties, "name", None) == "Intel(R) Arc(TM) Pro B70 Graphics", "B70 runtime name")
    probe = torch.empty((1,), dtype=torch.uint8, device="xpu:0")
    require(str(probe.device) == "xpu:0" and probe.numel() == 1, "logical xpu:0 probe")
    raw = _uuid_bytes(properties.uuid)
    reversed_uuid = str(uuid.UUID(bytes=raw[::-1])).lower()
    require(reversed_uuid == physical["xpu_smi_uuid"].lower(), "reverse-byte UUID/XPU-SMI binding")
    return {
        "physical_rank": physical["physical_rank"], "bdf": bdf,
        "drm_card": str(drm), "vendor": "0x8086", "device": "0xe223", "torch_version": torch.__version__,
        "device_name": properties.name, "oneapi_device_selector": os.environ["ONEAPI_DEVICE_SELECTOR"],
        "ze_affinity_mask": os.environ["ZE_AFFINITY_MASK"], "logical_probe": "xpu:0",
        "torch_uuid_bytes_hex": raw.hex(), "xpu_smi_uuid": reversed_uuid,
        "uuid_mapping": "xpu_smi_uuid_is_reverse_of_torch_level_zero_bytes",
    }


def _load_sealed_libraries(torch: Any, library_fds: dict[str, int], libraries: dict[str, Any]) -> dict[str, Any]:
    """Load only objects already pinned by directory FD and verify /proc mappings."""
    observed: dict[str, Any] = {}
    for name in LIBRARIES_TO_LOAD:
        record = libraries[name]
        fd = library_fds[name]
        digest, metadata = _sha_fd(fd)
        require(digest == record["sha256"] and metadata.st_size == record["bytes"],
                f"sealed library drift: {name}")
        proc_path = f"/proc/self/fd/{fd}"
        if name in DEPENDENCY_LIBRARIES:
            # The extension has DT_NEEDED=$ORIGIN references.  A /proc/fd path
            # does not offer sibling discovery, so retain and global-load every
            # exact dependency before loading the three dispatcher extensions.
            handle = ctypes.CDLL(proc_path, mode=ctypes.RTLD_GLOBAL | ctypes.RTLD_NOW)
            _DEPENDENCY_HANDLES.append(handle)
            observed[name] = {"sha256": digest, "bytes": metadata.st_size,
                              "dev": metadata.st_dev, "inode": metadata.st_ino,
                              "loaded_via": proc_path, "rtld_global": True}
            continue
        torch.ops.load_library(proc_path)
        observed[name] = {"sha256": digest, "bytes": metadata.st_size,
                          "dev": metadata.st_dev, "inode": metadata.st_ino,
                          "loaded_via": proc_path, "rtld_global": False}
    mapped: dict[str, int] = {name: 0 for name in LIBRARIES_TO_LOAD}
    for line in Path("/proc/self/maps").read_text(encoding="utf-8", errors="strict").splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6:
            continue
        mapped_path = fields[5].removesuffix(" (deleted)")
        name = Path(mapped_path).name
        if name not in mapped:
            continue
        expected_meta = os.fstat(library_fds[name])
        try:
            actual_meta = os.stat(mapped_path, follow_symlinks=False)
        except OSError as error:
            raise RuntimeError(f"cannot stat mapped sealed library: {name}") from error
        require((actual_meta.st_dev, actual_meta.st_ino) == (expected_meta.st_dev, expected_meta.st_ino),
                f"unsealed or replaced native mapping: {name}")
        mapped[name] += 1
    require(all(count > 0 for count in mapped.values()), "sealed library mapping missing")
    for value in observed.values():
        value["mapping_verified"] = True
    require(hasattr(torch.ops._moe_C, "moe_gather") and
            hasattr(torch.ops._moe_C, "laguna_m8_moe_gather_sharded") and
            hasattr(torch.ops._C, "laguna_m8_scale_add") and
            hasattr(torch.ops._xpu_C, "rank_order_bf16_sum") and
            hasattr(torch.ops._C, "fused_add_rms_norm"), "required sealed op absent")
    return observed


def _raw(tensor: Any, torch: Any) -> bytes:
    return tensor.detach().contiguous().to("cpu").view(torch.uint8).numpy().tobytes()


def _hash(tensor: Any, torch: Any) -> str:
    return hashlib.sha256(_raw(tensor, torch)).hexdigest()


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
        "nan": int(nan.sum().item()), "nan_payloads_sha256": hashlib.sha256(payload).hexdigest(),
    }


def _compare(left: Any, right: Any, torch: Any) -> dict[str, Any]:
    left_raw, right_raw = _raw(left, torch), _raw(right, torch)
    left_class, right_class = _classification(left, torch), _classification(right, torch)
    raw_equal = left_raw == right_raw
    has_nan = left_class["nan"] or right_class["nan"]
    finite_equal = None if has_nan else bool(torch.equal(left.detach().to("cpu"), right.detach().to("cpu")))
    passed = raw_equal and left_class == right_class and (has_nan or finite_equal is True)
    return {"left_raw_bf16_le_sha256": hashlib.sha256(left_raw).hexdigest(),
            "right_raw_bf16_le_sha256": hashlib.sha256(right_raw).hexdigest(),
            "raw_uint16_equal": raw_equal, "left_classification": left_class,
            "right_classification": right_class, "torch_equal": finite_equal,
            "nan_policy": "raw_bits_and_classification" if has_nan else "torch_equal_and_raw_bits",
            "passed": passed}


def _tensor_from_epoch(torch: Any, retained: dict[str, Any], name: str, epoch: int) -> Any:
    record, fd = retained["records"][name], retained["fds"][name]
    shape, dtype = record["shape"], record["dtype"]
    expected = {
        "route_rows": ("<u2", [288, 80, 3072]),
        "weights": ("<u4", [288, 8, 10]),
        "scale_add_input": ("<u2", [288, 8, 3072]),
        "four_rank_tail": ("<u2", [288, 3, 8, 3072]),
        "residual_input": ("<u2", [288, 8, 3072]),
        "norm_weight": ("<u2", [288, 3072]),
    }[name]
    require((dtype, shape) == expected, f"fixture dtype/shape identity drift: {name}")
    width = {"<u2": 2, "<u4": 4}[dtype]
    count = 1
    for item in shape[1:]:
        count *= item
    metadata = os.fstat(fd)
    require(metadata.st_size == 288 * count * width, f"fixture byte size identity drift: {name}")
    raw = os.pread(fd, count * width, epoch * count * width)
    require(len(raw) == count * width, f"short retained fixture epoch: {name}/{epoch}")
    require(hashlib.sha256(raw).hexdigest() == record["per_epoch_sha256"][epoch],
            f"fixture epoch hash drift: {name}/{epoch}")
    # A bytearray is deliberate: torch.frombuffer rejects immutable buffers and
    # its lifetime is then independently owned by this tensor.
    tensor_dtype = torch.uint16 if dtype == "<u2" else torch.uint32
    return torch.frombuffer(bytearray(raw), dtype=tensor_dtype).reshape(shape[1:])


def _item(torch: Any, retained: dict[str, Any], epoch: int) -> dict[str, Any]:
    cpu = {name: _tensor_from_epoch(torch, retained, name, epoch) for name in retained["records"]}
    route_map = torch.frombuffer(bytearray(retained["route_map"]), dtype=torch.int32).reshape(TOKENS, TOPK)
    return {
        "epoch": epoch, "routes": cpu["route_rows"].view(torch.bfloat16).to("xpu"),
        "weights": cpu["weights"].view(torch.float32).to("xpu"),
        "shared": cpu["scale_add_input"].view(torch.bfloat16).to("xpu"),
        "tail": cpu["four_rank_tail"].view(torch.bfloat16).to("xpu"),
        "residual": cpu["residual_input"].view(torch.bfloat16).to("xpu"),
        "norm": cpu["norm_weight"].view(torch.bfloat16).to("xpu"),
        "route_map": route_map.to("xpu"),
        "input_hashes": {name: hashlib.sha256(_raw(value, torch)).hexdigest()
                         for name, value in cpu.items()} | {"canonical_route_map": hashlib.sha256(retained["route_map"]).hexdigest()},
    }


def _input_hashes(item: dict[str, Any], torch: Any) -> dict[str, str]:
    return {"route_rows": _hash(item["routes"], torch), "weights": _hash(item["weights"], torch),
            "scale_add_input": _hash(item["shared"], torch), "four_rank_tail": _hash(item["tail"], torch),
            "residual_input": _hash(item["residual"], torch), "norm_weight": _hash(item["norm"], torch),
            "canonical_route_map": _hash(item["route_map"], torch)}


def _gather_control(out: Any, item: dict[str, Any], torch: Any) -> None:
    torch.ops._moe_C.moe_gather(out, item["routes"], item["weights"], item["route_map"], 64)


def _gather_candidate(out: Any, item: dict[str, Any], torch: Any) -> None:
    torch.ops._moe_C.laguna_m8_moe_gather_sharded(out, item["routes"], item["weights"], 64)


def _downstream(gathered: Any, item: dict[str, Any], torch: Any) -> dict[str, Any]:
    scaled = torch.empty_like(gathered)
    torch.ops._C.laguna_m8_scale_add(scaled, item["shared"], gathered)
    rank_input = torch.empty((RANKS, TOKENS, HIDDEN), dtype=torch.bfloat16, device="xpu")
    rank_input[0].copy_(scaled)
    rank_input[1:].copy_(item["tail"])
    reduced = torch.ops._xpu_C.rank_order_bf16_sum(rank_input)
    hidden, residual = reduced.clone(), item["residual"].clone()
    torch.ops._C.fused_add_rms_norm(hidden, residual, item["norm"], 1.0e-6)
    return {"scale_add": scaled, "rank_order_bf16_sum": reduced,
            "fused_add_rms_norm_hidden": hidden, "fused_add_rms_norm_residual": residual}


def _exact_epoch(item: dict[str, Any], torch: Any) -> dict[str, Any]:
    before = _input_hashes(item, torch)
    control, candidate, repeat = (torch.empty((TOKENS, HIDDEN), dtype=torch.bfloat16, device="xpu") for _ in range(3))
    _gather_control(control, item, torch)
    _gather_candidate(candidate, item, torch)
    _gather_candidate(repeat, item, torch)
    left, right = _downstream(control, item, torch), _downstream(candidate, item, torch)
    comparisons = {"gather": _compare(control, candidate, torch),
                   "candidate_repeat": _compare(candidate, repeat, torch)}
    for name in left:
        comparisons[name] = _compare(left[name], right[name], torch)
    after = _input_hashes(item, torch)
    return {"epoch": item["epoch"], "input_before": before, "input_after": after,
            "outputs": {"control_gather": _hash(control, torch), "candidate_gather": _hash(candidate, torch),
                        "candidate_repeat": _hash(repeat, torch),
                        **{name: _hash(value, torch) for name, value in left.items()},
                        **{f"candidate_{name}": _hash(value, torch) for name, value in right.items()}},
            "raw_bf16_classification": _classification(control, torch), "comparisons": comparisons,
            "passed": before == item["input_hashes"] and after == before and all(value["passed"] for value in comparisons.values())}


def _timing(items: list[dict[str, Any]], torch: Any) -> dict[str, Any]:
    require(len(items) == PRE_EPOCHS, "timing corpus must be 256 prebuilt epochs")
    control = [torch.empty((TOKENS, HIDDEN), dtype=torch.bfloat16, device="xpu") for _ in range(LAYERS)]
    candidate = [torch.empty_like(control[0]) for _ in range(LAYERS)]
    def cycle(use_candidate: bool, indexes: tuple[int, ...]) -> None:
        for slot, index in enumerate(indexes):
            (_gather_candidate if use_candidate else _gather_control)(candidate[slot] if use_candidate else control[slot], items[index], torch)
    warm = tuple(range(LAYERS))
    # Warmup intentionally contains exactly the selected primitive, not scale/add,
    # allocation, CPU work, hashing, or a synchronisation inside a cycle.
    for _ in range(WARM_CYCLES):
        cycle(False, warm)
    torch.xpu.synchronize()
    for _ in range(WARM_CYCLES):
        cycle(True, warm)
    torch.xpu.synchronize()
    def arm(use_candidate: bool, indexes: tuple[int, ...]) -> int:
        torch.xpu.synchronize()
        start, end = torch.xpu.Event(enable_timing=True), torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(CYCLES_PER_ARM):
            cycle(use_candidate, indexes)
        end.record()
        end.synchronize()
        ns = round(float(start.elapsed_time(end)) * 1_000_000)
        require(ns > 0, "nonpositive device event interval")
        return ns
    blocks: list[dict[str, Any]] = []
    for block in range(ABBA_BLOCKS):
        indexes = tuple((block * LAYERS + slot) % PRE_EPOCHS for slot in range(LAYERS))
        a1, b1, b2, a2 = arm(False, indexes), arm(True, indexes), arm(True, indexes), arm(False, indexes)
        # Exactness after each block is outside all events and checks each of the
        # 47 selected outputs, catching a late overwrite or dispatch drift.
        exact = [_compare(control[slot], candidate[slot], torch) for slot in range(LAYERS)]
        require(all(row["passed"] for row in exact), f"timed output mismatch block {block}")
        control_ms = (a1 + a2) / (2 * CYCLES_PER_ARM) / 1_000_000
        candidate_ms = (b1 + b2) / (2 * CYCLES_PER_ARM) / 1_000_000
        blocks.append({"block": block, "fixture_indices": list(indexes), "A1_control_elapsed_ns": a1,
                       "B1_candidate_elapsed_ns": b1, "B2_candidate_elapsed_ns": b2, "A2_control_elapsed_ns": a2,
                       "paired_control_ms_per_47_layer_cycle": control_ms,
                       "paired_candidate_ms_per_47_layer_cycle": candidate_ms,
                       "saving_ms_per_47_layer_cycle": control_ms - candidate_ms,
                       "selected_gather_launches": {"control": LAYERS, "candidate": LAYERS},
                       "post_block_raw_exactness": exact})
    savings = [row["saving_ms_per_47_layer_cycle"] for row in blocks]
    wins, median = sum(value > 0.0 for value in savings), statistics.median(savings)
    return {"clock": "torch.xpu.Event device elapsed time", "warm_cycles_per_arm": WARM_CYCLES,
            "blocks": ABBA_BLOCKS, "arm_order": "A-B-B-A", "cycles_per_arm": CYCLES_PER_ARM,
            "layers_per_cycle": LAYERS, "rotation": "(block*47)%256", "cpu_work_inside_event_interval": False,
            "selected_gather_launches_per_cycle": {"control": LAYERS, "candidate": LAYERS},
            "control_geometry": {"workgroups": 8, "simd32_subgroups": 64},
            "candidate_geometry": {"workgroups": 48, "simd32_subgroups": 96},
            "blocks_detail": blocks, "candidate_block_wins": wins,
            "median_saving_ms_per_cycle": median,
            "passed": wins >= 28 and median >= 0.08}


def _recheck_retained(retained: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, fd in retained["library_fds"].items():
        digest, meta = _sha_fd(fd)
        result[f"library:{name}"] = {"sha256": digest, "dev": meta.st_dev, "inode": meta.st_ino,
                                      "bytes": meta.st_size}
    for name, fd in retained["fds"].items():
        digest, meta = _sha_fd(fd)
        record = retained["records"][name]
        require(digest == record["sha256"], f"retained whole fixture drift: {name}")
        result[name] = {"sha256": digest, "dev": meta.st_dev, "inode": meta.st_ino, "bytes": meta.st_size}
    route_digest, route_meta = _sha_fd(retained["route_map_fd"])
    require(route_digest == retained["route_map_sha256"], "retained route-map drift")
    result["canonical_route_map"] = {"sha256": route_digest, "dev": route_meta.st_dev,
                                      "inode": route_meta.st_ino, "bytes": route_meta.st_size}
    for name in ("bundle_fd", "fixture_fd"):
        metadata = os.fstat(retained[name])
        expected = retained["directory_identity"]["bundle" if name == "bundle_fd" else "fixture"]
        require((metadata.st_dev, metadata.st_ino) == (expected["dev"], expected["inode"]),
                f"retained parent directory changed: {name}")
    return result


def run_phase_a_campaign(context: dict[str, Any]) -> dict[str, Any]:
    """Execute the fixed, already-authorized card program; no retry path exists."""
    import torch  # The first torch/native import is intentionally here.
    common, retained = context["common"], context["retained"]
    physical = common["cards"][context["rank"]]
    binding = _runtime_card_binding(torch, physical)
    native = _load_sealed_libraries(torch, retained["library_fds"], common["native_bundle"]["libraries"])
    before_retained = _recheck_retained(retained)
    pre_items = [_item(torch, retained, epoch) for epoch in range(PRE_EPOCHS)]
    pre = [_exact_epoch(item, torch) for item in pre_items]
    require(all(row["passed"] for row in pre), "pre-timing raw exactness failed")
    timing = _timing(pre_items, torch)
    require(timing["passed"], "timing threshold failed")
    post = [_exact_epoch(_item(torch, retained, epoch), torch) for epoch in range(PRE_EPOCHS, PRE_EPOCHS + POST_EPOCHS)]
    require(all(row["passed"] for row in post), "post-timing raw exactness failed")
    after_retained = _recheck_retained(retained)
    require(before_retained == after_retained, "fixture descriptor identity changed during campaign")
    return {"runtime_binding": binding, "native_modules": native, "retained_fixture_before": before_retained,
            "retained_fixture_after": after_retained, "pre_epochs": pre, "post_epochs": post, "timing": timing}
