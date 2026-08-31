#!/usr/bin/env python3
"""Compare production F.linear with grouped GEMM across all 97 HC up weights."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import secrets
import statistics
import time

from safetensors import safe_open
import torch
import torch.nn.functional as F


MODEL = Path("/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8")
MODEL_REVISION = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
MODEL_INDEX_SHA256 = "0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6"
MODEL_CONFIG_SHA256 = "99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d"
WEIGHT_MANIFEST_SHA256 = (
    "da68ed6ed1fa5dba536bd5881799972c6ce079a55a2ca82e1ec8832520a8a5f7"
)
AUTHORITY = Path(
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/"
    "hc-m1-grouped-up-round-robin-authority-seed20260831.json"
)
AUTHORITY_SHA256 = "15af5344c259fa83ffc16ca1755c621a83cce01651119b2c5234c4276a2fcab9"
AUTHORITY_MANIFEST_SHA256 = (
    "78d773b0a4387e2396828c3b360983ab79051f871065377aaf8dba3ef3b1c91e"
)
AUTHORITY_SWEEP_SHA256 = (
    "cbe21f41db001fd54b8b84f782c0a39f894fdc8fa92677fb12e87500e683c5f7"
)
INPUT_DEVICE_MANIFEST_SHA256 = (
    "0cc7b0522f32e6feda641c1e82ff920943251aa750b62f74da0d1d469c3a3db3"
)
LINEAR_DEVICE_MANIFEST_SHA256 = (
    "875f289c2b33e718ee32c2818fb854afa5855472414f1592f93613a3f6576b63"
)
ROWS_PER_EXPERT_SHA256 = (
    "67abdd721024f0ff4e0b3f4c2fc13bc5bad42d0b7851d456d88d203d15aaa450"
)
NORMALIZED_LOADER_SHA256 = (
    "ce2247ccad4f7466ad69dfc9469d9adc5fa41ebe89ac4016570bae9d5e4680c4"
)
AUTHORITY_TOOL_SHA256 = (
    "78e61ca6b8f617280a39b8630c519c8c21f6a9da24c0fcb79387932375c1031f"
)
CORE_SHA256 = "8b0486685e4167a3d9b4970d40635dd75b031792ef27ade71e27a5ae285af3b0"
PAIR_DRIVER_SHA256 = "650efd1e807845f9125150a7390b5c7cf6222d18a136e68d7d2c83f17d8008e7"
STAGE = Path(
    "/mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels"
)
STAGE_MANIFEST_SHA256 = (
    "71e263f19ccc1313bbdc21604b4de5171891454fb7e8e35877af083505522951"
)
RUNTIME_MANIFEST = {
    "_xpu_C.abi3.so": "07cba22dbfef80914784767a556320df87215b2ebc1226716da9d775a3c66dc3",
    "libgrouped_gemm_xe_2.so": (
        "4493c3030b1a53b756953c15e390b740023ee68f16ca8783cb0a5213600f1ac8"
    ),
}
SEED = 20260831
WARMUP_SWEEPS = 100
CYCLES = 31
SWEEPS_PER_CYCLE = 100
EXACTNESS_SWEEPS = 100
GATE = {
    "median_reduction_minimum_percent": 50.0,
    "every_cycle_reduction_minimum_percent": 20.0,
    "median_saving_minimum_ms": 0.75,
    "order_bias_maximum_points": 10.0,
}
EVIDENCE_BASE = Path("/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70")
LOCK_PATHS = (
    Path("/tmp/q38-hc-m1-grouped-gemm-round-robin.lock"),
    Path("/tmp/q38-hc-m1-grouped-gemm-alternating.lock"),
    Path("/tmp/q38-hc-m1-grouped-gemm-pair.lock"),
    Path("/tmp/q38-hc-m1-grouped-gemm.lock"),
)
MIN_HOST_AVAILABLE_BYTES = 100 * 1024**3
MIN_SWAP_FREE_BYTES = 7 * 1024**3
MIN_EVIDENCE_FREE_BYTES = 100 * 1024**3


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def tensor_sha256(tensor: torch.Tensor) -> str:
    return hashlib.sha256(
        tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    ).hexdigest()


def import_local(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)


def normalized_loader(lines: str) -> list[str]:
    return [re.sub(r"\s+\(0x[0-9a-f]+\)$", "", line) for line in lines.splitlines()]


def read_meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        name, raw = line.split(":", maxsplit=1)
        values[name] = int(raw.strip().split()[0]) * 1024
    return values


def verify_host_and_storage() -> dict[str, object]:
    mounts = []
    for line in Path("/proc/mounts").read_text(encoding="utf-8").splitlines():
        source, target, filesystem, options, *_ = line.split()
        if target == "/mnt/usb-models":
            mounts.append((source, filesystem, options))
    if len(mounts) != 1 or mounts[0][0:2] != ("/dev/sda2", "fuseblk"):
        raise RuntimeError(f"unexpected evidence mount identity: {mounts}")
    evidence_stat = os.statvfs(EVIDENCE_BASE)
    evidence_free = evidence_stat.f_bavail * evidence_stat.f_frsize
    if evidence_free < MIN_EVIDENCE_FREE_BYTES:
        raise RuntimeError(f"insufficient evidence-drive free space: {evidence_free}")
    if os.stat(MODEL).st_dev != os.stat("/").st_dev:
        raise RuntimeError("active model is not on the local root/NVMe filesystem")
    memory = read_meminfo()
    if memory["MemAvailable"] < MIN_HOST_AVAILABLE_BYTES:
        raise RuntimeError(f"insufficient host memory: {memory['MemAvailable']}")
    if memory["SwapFree"] < MIN_SWAP_FREE_BYTES:
        raise RuntimeError(f"insufficient free swap: {memory['SwapFree']}")
    return {
        "evidence_source": mounts[0][0],
        "evidence_filesystem": mounts[0][1],
        "evidence_mount": "/mnt/usb-models",
        "evidence_free_bytes": evidence_free,
        "model_on_root_nvme_device": True,
        "mem_available_bytes": memory["MemAvailable"],
        "swap_free_bytes": memory["SwapFree"],
        "minimums": {
            "evidence_free_bytes": MIN_EVIDENCE_FREE_BYTES,
            "mem_available_bytes": MIN_HOST_AVAILABLE_BYTES,
            "swap_free_bytes": MIN_SWAP_FREE_BYTES,
        },
    }


def refuse_visible_render_node_owners() -> None:
    own_pid = os.getpid()
    owners: list[tuple[int, str]] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == own_pid:
            continue
        try:
            descriptors = (proc / "fd").iterdir()
            for descriptor in descriptors:
                try:
                    target = os.readlink(descriptor)
                except (FileNotFoundError, PermissionError, ProcessLookupError):
                    continue
                if target.startswith("/dev/dri/renderD"):
                    owners.append((int(proc.name), target))
                    break
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    if owners:
        raise RuntimeError(f"another process owns a render node: {owners}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", choices=("r1", "r2"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    script = Path(__file__).resolve()
    script_sha256 = sha256(script)
    core_path = script.with_name("benchmark-hc-m1-grouped-gemm.py")
    pair_driver_path = script.with_name("run-hc-m1-grouped-gemm-pair.py")
    if sha256(core_path) != CORE_SHA256:
        raise RuntimeError("frozen HC core helper has drifted")
    if sha256(pair_driver_path) != PAIR_DRIVER_SHA256:
        raise RuntimeError("frozen HC pair driver has drifted")
    core = import_local(core_path, "q38_hc_grouped_core")
    pair_driver = import_local(pair_driver_path, "q38_hc_grouped_pair_driver")

    expected_output = (
        EVIDENCE_BASE / f"hc-m1-grouped-up-round-robin-{args.repeat}-seed20260831.json"
    ).resolve()
    output = args.output.resolve()
    if output != expected_output:
        raise RuntimeError(f"unexpected evidence path: {output}")
    if output.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {output}")
    if os.environ.get("ONEAPI_DEVICE_SELECTOR") != "level_zero:0":
        raise RuntimeError("ONEAPI_DEVICE_SELECTOR must be exactly level_zero:0")
    if (
        os.environ.get("PYTHONNOUSERSITE") != "1"
        or os.environ.get("PYTHONSAFEPATH") != "1"
    ):
        raise RuntimeError("isolated Python environment is required")

    locks = []
    for lock_path in LOCK_PATHS:
        lock = lock_path.open("w", encoding="utf-8")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"component lock is held: {lock_path}") from error
        locks.append(lock)
    core.refuse_active_server()
    host_preflight = verify_host_and_storage()
    refuse_visible_render_node_owners()

    if sha256(AUTHORITY) != AUTHORITY_SHA256:
        raise RuntimeError("control-only authority evidence digest drift")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    expected_authority_fields = {
        "status": "production_authority_frozen",
        "classification": "control_only_97_weight_round_robin_census",
        "model": str(MODEL),
        "model_revision": MODEL_REVISION,
        "model_index_sha256": MODEL_INDEX_SHA256,
        "model_config_sha256": MODEL_CONFIG_SHA256,
        "seed": SEED,
        "control_sweeps": 10,
        "weight_count": 97,
        "weight_manifest_sha256": WEIGHT_MANIFEST_SHA256,
        "authority_manifest_sha256": AUTHORITY_MANIFEST_SHA256,
        "unique_hashes_per_slot": 1,
        "candidate_invocations": 0,
        "tool_sha256": AUTHORITY_TOOL_SHA256,
        "core_sha256": CORE_SHA256,
    }
    for field, expected in expected_authority_fields.items():
        if authority.get(field) != expected:
            raise RuntimeError(f"authority identity mismatch for {field}")
    weight_manifest = authority.get("weight_manifest")
    authorities = authority.get("authorities")
    if not isinstance(weight_manifest, list) or len(weight_manifest) != 97:
        raise RuntimeError("authority weight manifest is not 97 entries")
    if not isinstance(authorities, list) or len(authorities) != 97:
        raise RuntimeError("authority output manifest is not 97 entries")
    if canonical_sha256(weight_manifest) != WEIGHT_MANIFEST_SHA256:
        raise RuntimeError("authority weight manifest content drift")
    if canonical_sha256(authorities) != AUTHORITY_MANIFEST_SHA256:
        raise RuntimeError("authority output manifest content drift")

    stage = STAGE.resolve()
    library, runtime_manifest = core.verify_runtime_stage(stage)
    if runtime_manifest != RUNTIME_MANIFEST:
        raise RuntimeError("runtime-stage manifest entries drifted")
    stage_manifest = stage / "SHA256SUMS"
    if sha256(stage_manifest) != STAGE_MANIFEST_SHA256:
        raise RuntimeError("runtime-stage manifest digest drift")
    loader_closure, sycl_identity = pair_driver.verify_loader_closure(
        stage, os.environ.copy(), runtime_manifest
    )
    normalized_loader_closure = normalized_loader(loader_closure)
    if canonical_sha256(normalized_loader_closure) != NORMALIZED_LOADER_SHA256:
        raise RuntimeError("normalized runtime loader closure drift")
    runpath_evidence = pair_driver.verify_runpaths(stage, runtime_manifest)
    core.load_extension(library)
    if not hasattr(torch.ops._xpu_C, "cutlass_grouped_gemm_interface"):
        raise RuntimeError("runtime extension lacks grouped GEMM")
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("selector must expose exactly one XPU")
    device_name = torch.xpu.get_device_name(0)
    if "Arc" not in device_name or "B70" not in device_name:
        raise RuntimeError(f"selected XPU is not an Arc Pro B70: {device_name}")

    index_path = MODEL / "model.safetensors.index.json"
    config_path = MODEL / "config.json"
    if sha256(index_path) != MODEL_INDEX_SHA256:
        raise RuntimeError("model index digest drift")
    if sha256(config_path) != MODEL_CONFIG_SHA256:
        raise RuntimeError("model config digest drift")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    generator = torch.Generator(device="cpu").manual_seed(SEED)
    weights_cpu: list[torch.Tensor] = []
    inputs_cpu: list[torch.Tensor] = []
    observed_weight_manifest: list[dict[str, str]] = []
    authority_by_slot: dict[str, tuple[str, str]] = {}
    for item in authorities:
        if not isinstance(item, list) or len(item) != 3:
            raise RuntimeError("authority entry identity drift")
        slot, input_hash, output_hash = item
        if not all(isinstance(value, str) for value in item):
            raise RuntimeError("authority entry is not textual")
        if slot in authority_by_slot:
            raise RuntimeError(f"duplicate authority slot: {slot}")
        authority_by_slot[slot] = (input_hash, output_hash)
    for item in weight_manifest:
        if not isinstance(item, dict):
            raise RuntimeError("weight manifest entry is not an object")
        slot = item["slot"]
        name = item["name"]
        shard_name = item["shard"]
        if index["weight_map"].get(name) != shard_name:
            raise RuntimeError(f"model index remapped {slot}")
        with safe_open(MODEL / shard_name, framework="pt", device="cpu") as handle:
            weight = handle.get_tensor(name).contiguous()
        if weight.shape != (10240, 320) or weight.dtype != torch.bfloat16:
            raise RuntimeError(f"unexpected weight identity for {slot}")
        weight_hash = tensor_sha256(weight)
        if weight_hash != item["sha256"]:
            raise RuntimeError(f"weight digest drift for {slot}")
        observed_weight_manifest.append(
            {
                "slot": slot,
                "name": name,
                "shard": shard_name,
                "sha256": weight_hash,
            }
        )
        value = (
            torch.randn((1, 320), dtype=torch.bfloat16, generator=generator) * 0.01
        ).contiguous()
        expected_input_hash, _ = authority_by_slot[slot]
        if tensor_sha256(value) != expected_input_hash:
            raise RuntimeError(f"input authority drift for {slot}")
        weights_cpu.append(weight)
        inputs_cpu.append(value)
    if canonical_sha256(observed_weight_manifest) != WEIGHT_MANIFEST_SHA256:
        raise RuntimeError("live 97-weight manifest digest drift")

    memory_before = int(torch.xpu.memory_allocated(0))
    load_started = time.monotonic()
    weights = [weight.to("xpu") for weight in weights_cpu]
    inputs = [value.to("xpu") for value in inputs_cpu]
    rows_per_expert = torch.ones((1,), dtype=torch.int32, device="xpu")
    torch.xpu.synchronize()
    linear_bank_load_seconds = time.monotonic() - load_started
    memory_after_linear = int(torch.xpu.memory_allocated(0))
    prepack_started = time.monotonic()
    packed = [weight.t().contiguous().unsqueeze(0) for weight in weights]
    torch.xpu.synchronize()
    prepack_seconds = time.monotonic() - prepack_started
    memory_after_packed = int(torch.xpu.memory_allocated(0))
    packed_hashes_before = [tensor_sha256(value) for value in packed]
    input_hashes_before = [tensor_sha256(value) for value in inputs]
    linear_weight_hashes_before = [tensor_sha256(value) for value in weights]
    rows_per_expert_hash_before = tensor_sha256(rows_per_expert)
    input_device_manifest_sha256 = canonical_sha256(
        [
            [item["slot"], value]
            for item, value in zip(weight_manifest, input_hashes_before)
        ]
    )
    linear_device_manifest_sha256 = canonical_sha256(
        [
            [item["slot"], value]
            for item, value in zip(weight_manifest, linear_weight_hashes_before)
        ]
    )
    if input_device_manifest_sha256 != INPUT_DEVICE_MANIFEST_SHA256:
        raise RuntimeError("XPU input-bank authority digest drift")
    if linear_device_manifest_sha256 != LINEAR_DEVICE_MANIFEST_SHA256:
        raise RuntimeError("XPU linear-bank authority digest drift")
    if rows_per_expert_hash_before != ROWS_PER_EXPERT_SHA256:
        raise RuntimeError("grouped row-metadata authority digest drift")
    packed_manifest_sha256 = canonical_sha256(
        [
            [item["slot"], packed_hash]
            for item, packed_hash in zip(weight_manifest, packed_hashes_before)
        ]
    )

    def linear_sweep() -> list[torch.Tensor]:
        return [F.linear(value, weight) for value, weight in zip(inputs, weights)]

    def grouped_sweep() -> list[torch.Tensor]:
        outputs: list[torch.Tensor] = []
        for value, packed_weight in zip(inputs, packed):
            output_value = torch.empty((1, 10240), dtype=torch.bfloat16, device="xpu")
            torch.ops._xpu_C.cutlass_grouped_gemm_interface(
                value,
                packed_weight,
                None,
                None,
                output_value,
                rows_per_expert,
                10240,
                320,
                1,
                False,
                False,
            )
            outputs.append(output_value)
        return outputs

    expected_output_hashes = [
        authority_by_slot[item["slot"]][1] for item in weight_manifest
    ]

    def validate_sweep(values: list[torch.Tensor], label: str) -> str:
        if len(values) != 97:
            raise RuntimeError(f"{label} did not return 97 outputs")
        observed: list[list[str]] = []
        for item, value, expected_hash in zip(
            weight_manifest, values, expected_output_hashes
        ):
            value_cpu = value.detach().cpu()
            if value_cpu.shape != (1, 10240) or value_cpu.dtype != torch.bfloat16:
                raise RuntimeError(f"{label} output identity drift for {item['slot']}")
            if not torch.isfinite(value_cpu.float()).all().item():
                raise RuntimeError(f"{label} output is non-finite for {item['slot']}")
            observed_hash = tensor_sha256(value_cpu)
            if observed_hash != expected_hash:
                raise RuntimeError(f"{label} output differs for {item['slot']}")
            observed.append([item["slot"], observed_hash])
        return canonical_sha256(observed)

    linear_outputs = linear_sweep()
    torch.xpu.synchronize()
    authority_sweep_sha256 = validate_sweep(linear_outputs, "pre-candidate linear")
    if authority_sweep_sha256 != AUTHORITY_SWEEP_SHA256:
        raise RuntimeError("production authority sweep digest drift")
    first_candidate_started = time.monotonic()
    grouped_outputs = grouped_sweep()
    torch.xpu.synchronize()
    first_candidate_sweep_seconds = time.monotonic() - first_candidate_started
    if validate_sweep(grouped_outputs, "first grouped") != authority_sweep_sha256:
        raise RuntimeError("first grouped sweep differs from production authority")

    for warmup in range(WARMUP_SWEEPS):
        if warmup % 2 == 0:
            linear_outputs = linear_sweep()
            grouped_outputs = grouped_sweep()
        else:
            grouped_outputs = grouped_sweep()
            linear_outputs = linear_sweep()
    torch.xpu.synchronize()
    if validate_sweep(linear_outputs, "post-warmup linear") != authority_sweep_sha256:
        raise RuntimeError("post-warmup linear sweep differs from authority")
    if validate_sweep(grouped_outputs, "post-warmup grouped") != authority_sweep_sha256:
        raise RuntimeError("post-warmup grouped sweep differs from authority")

    def timed(invoke) -> tuple[float, list[torch.Tensor]]:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        values: list[torch.Tensor] = []
        for _ in range(SWEEPS_PER_CYCLE):
            values = invoke()
        end.record()
        end.synchronize()
        elapsed_ms = start.elapsed_time(end) / SWEEPS_PER_CYCLE
        if not math.isfinite(elapsed_ms) or elapsed_ms <= 0.0:
            raise RuntimeError(f"invalid full-bank timing: {elapsed_ms}")
        return elapsed_ms, values

    cycles: list[dict[str, object]] = []
    for cycle in range(CYCLES):
        if cycle % 2 == 0:
            order = "linear_grouped"
            linear_ms, linear_outputs = timed(linear_sweep)
            grouped_ms, grouped_outputs = timed(grouped_sweep)
        else:
            order = "grouped_linear"
            grouped_ms, grouped_outputs = timed(grouped_sweep)
            linear_ms, linear_outputs = timed(linear_sweep)
        if (
            validate_sweep(linear_outputs, f"cycle {cycle} linear")
            != authority_sweep_sha256
        ):
            raise RuntimeError(f"cycle {cycle} linear sweep differs from authority")
        if (
            validate_sweep(grouped_outputs, f"cycle {cycle} grouped")
            != authority_sweep_sha256
        ):
            raise RuntimeError(f"cycle {cycle} grouped sweep differs from authority")
        saving_ms = linear_ms - grouped_ms
        cycles.append(
            {
                "cycle": cycle,
                "order": order,
                "linear_full_97_sweep_ms": linear_ms,
                "grouped_full_97_sweep_ms": grouped_ms,
                "saving_ms": saving_ms,
                "latency_reduction_percent": (saving_ms / linear_ms) * 100.0,
                "aggregate_output_sha256": authority_sweep_sha256,
            }
        )

    exactness_sweep_hashes: set[str] = set()
    for repeat in range(EXACTNESS_SWEEPS):
        if repeat % 2 == 0:
            linear_outputs = linear_sweep()
            grouped_outputs = grouped_sweep()
        else:
            grouped_outputs = grouped_sweep()
            linear_outputs = linear_sweep()
        torch.xpu.synchronize()
        linear_hash = validate_sweep(linear_outputs, f"exactness {repeat} linear")
        grouped_hash = validate_sweep(grouped_outputs, f"exactness {repeat} grouped")
        if (
            linear_hash != authority_sweep_sha256
            or grouped_hash != authority_sweep_sha256
        ):
            raise RuntimeError(f"exactness sweep {repeat} differs from authority")
        exactness_sweep_hashes.update((linear_hash, grouped_hash))
    if exactness_sweep_hashes != {authority_sweep_sha256}:
        raise RuntimeError("full-bank outputs were not repeatable")

    reductions = [float(cycle["latency_reduction_percent"]) for cycle in cycles]
    savings = [float(cycle["saving_ms"]) for cycle in cycles]
    linear_times = [float(cycle["linear_full_97_sweep_ms"]) for cycle in cycles]
    grouped_times = [float(cycle["grouped_full_97_sweep_ms"]) for cycle in cycles]
    linear_first = [
        float(cycle["latency_reduction_percent"])
        for cycle in cycles
        if cycle["order"] == "linear_grouped"
    ]
    grouped_first = [
        float(cycle["latency_reduction_percent"])
        for cycle in cycles
        if cycle["order"] == "grouped_linear"
    ]
    median_reduction = statistics.median(reductions)
    minimum_reduction = min(reductions)
    median_saving = statistics.median(savings)
    order_bias = abs(statistics.median(linear_first) - statistics.median(grouped_first))
    passed = (
        median_reduction >= GATE["median_reduction_minimum_percent"]
        and minimum_reduction >= GATE["every_cycle_reduction_minimum_percent"]
        and median_saving >= GATE["median_saving_minimum_ms"]
        and order_bias <= GATE["order_bias_maximum_points"]
    )

    packed_hashes_after = [tensor_sha256(value) for value in packed]
    if packed_hashes_after != packed_hashes_before:
        raise RuntimeError("packed weight bank changed during execution")
    if [tensor_sha256(value) for value in inputs] != input_hashes_before:
        raise RuntimeError("XPU input bank changed during execution")
    if [tensor_sha256(value) for value in weights] != linear_weight_hashes_before:
        raise RuntimeError("XPU linear weight bank changed during execution")
    if tensor_sha256(rows_per_expert) != rows_per_expert_hash_before:
        raise RuntimeError("grouped row metadata changed during execution")
    final_weight_manifest = [
        {
            **item,
            "sha256": tensor_sha256(weight),
        }
        for item, weight in zip(weight_manifest, weights_cpu)
    ]
    if canonical_sha256(final_weight_manifest) != WEIGHT_MANIFEST_SHA256:
        raise RuntimeError("CPU weight bank changed during execution")
    host_postflight = verify_host_and_storage()
    nonce = secrets.token_hex(32)
    stat_tail = Path("/proc/self/stat").read_text(encoding="utf-8").rpartition(") ")[2]
    result = {
        "schema_version": 1,
        "status": "process_gate_passed" if passed else "process_gate_failed",
        "classification": "production_order_97_weight_round_robin_component_gate",
        "repeat": args.repeat,
        "evidence_path": str(output),
        "model": str(MODEL),
        "model_revision": MODEL_REVISION,
        "model_index_sha256": MODEL_INDEX_SHA256,
        "model_config_sha256": MODEL_CONFIG_SHA256,
        "production_order": "layer0-attn,layer0-mlp,...,layer47-attn,layer47-mlp,final",
        "mtp_weights_included": False,
        "weight_count": 97,
        "weight_bank_bytes": 97 * 10240 * 320 * 2,
        "weight_manifest_sha256": WEIGHT_MANIFEST_SHA256,
        "authority_evidence": str(AUTHORITY),
        "authority_evidence_sha256": AUTHORITY_SHA256,
        "authority_manifest_sha256": AUTHORITY_MANIFEST_SHA256,
        "authority_sweep_sha256": authority_sweep_sha256,
        "slot_identities": [
            {
                **item,
                "input_sha256": authority_by_slot[item["slot"]][0],
                "authority_output_sha256": authority_by_slot[item["slot"]][1],
            }
            for item in weight_manifest
        ],
        "seed": SEED,
        "shape": {"m": 1, "n": 10240, "k": 320},
        "dtype": "torch.bfloat16",
        "candidate_output_allocation": "fresh torch.empty per production slot call",
        "candidate_batching": "97 sequential E=1 calls; never E=97",
        "runtime_stage": str(stage),
        "runtime_manifest": runtime_manifest,
        "runtime_manifest_sha256": STAGE_MANIFEST_SHA256,
        "library_sha256": sha256(library),
        "sycl_identity": sycl_identity,
        "loader_closure": loader_closure.splitlines(),
        "normalized_loader_sha256": NORMALIZED_LOADER_SHA256,
        "runpath_evidence": runpath_evidence,
        "device": {
            "selector": os.environ["ONEAPI_DEVICE_SELECTOR"],
            "count": torch.xpu.device_count(),
            "name": device_name,
            "torch": torch.__version__,
        },
        "process_identity": {
            "boot_id": Path("/proc/sys/kernel/random/boot_id")
            .read_text(encoding="utf-8")
            .strip(),
            "pid": os.getpid(),
            "process_start_ticks": int(stat_tail.split()[19]),
            "nonce": nonce,
        },
        "host_preflight": host_preflight,
        "host_postflight": host_postflight,
        "device_state_manifests": {
            "input_bank_sha256": input_device_manifest_sha256,
            "linear_weight_bank_sha256": linear_device_manifest_sha256,
            "packed_weight_bank_sha256": packed_manifest_sha256,
            "rows_per_expert_sha256": rows_per_expert_hash_before,
            "all_unchanged_after_candidate": True,
        },
        "memory": {
            "before_bytes": memory_before,
            "after_linear_bank_bytes": memory_after_linear,
            "after_linear_and_packed_banks_bytes": memory_after_packed,
            "linear_bank_delta_bytes": memory_after_linear - memory_before,
            "packed_bank_delta_bytes": memory_after_packed - memory_after_linear,
            "duplicate_steady_bank_is_endpoint_eligible": False,
        },
        "startup": {
            "linear_bank_load_seconds": linear_bank_load_seconds,
            "prepack_seconds": prepack_seconds,
            "first_candidate_sweep_seconds": first_candidate_sweep_seconds,
            "packed_manifest_sha256": packed_manifest_sha256,
        },
        "repeats": {
            "warmup_sweeps_per_provider": WARMUP_SWEEPS,
            "cycles": CYCLES,
            "sweeps_per_provider_per_cycle": SWEEPS_PER_CYCLE,
            "exactness_sweeps_per_provider": EXACTNESS_SWEEPS,
        },
        "all_97_outputs_exact_and_finite": True,
        "unique_aggregate_output_sha256": len(exactness_sweep_hashes),
        "linear_full_97_sweep_ms": {
            "median": statistics.median(linear_times),
            "p10": percentile(linear_times, 0.10),
            "p90": percentile(linear_times, 0.90),
            "median_per_call_us": statistics.median(linear_times) * 1000.0 / 97,
        },
        "grouped_full_97_sweep_ms": {
            "median": statistics.median(grouped_times),
            "p10": percentile(grouped_times, 0.10),
            "p90": percentile(grouped_times, 0.90),
            "median_per_call_us": statistics.median(grouped_times) * 1000.0 / 97,
        },
        "saving_ms": {
            "median": median_saving,
            "minimum": min(savings),
            "p10": percentile(savings, 0.10),
            "p90": percentile(savings, 0.90),
        },
        "latency_reduction_percent": {
            "median": median_reduction,
            "minimum": minimum_reduction,
            "p10": percentile(reductions, 0.10),
            "p90": percentile(reductions, 0.90),
        },
        "order_bias_points": order_bias,
        "gate": {**GATE, "passed": passed},
        "cycles": cycles,
        "process_gate_passed": passed,
        "source_integration_authorized": False,
        "endpoint_claim_authorized": False,
        "tool_sha256": script_sha256,
        "core_sha256": sha256(core_path),
        "pair_driver_sha256": sha256(pair_driver_path),
    }

    if sha256(script) != script_sha256:
        raise RuntimeError("round-robin tool changed during execution")
    if (
        sha256(core_path) != CORE_SHA256
        or sha256(pair_driver_path) != PAIR_DRIVER_SHA256
    ):
        raise RuntimeError("frozen helper closure changed during execution")
    if sha256(AUTHORITY) != AUTHORITY_SHA256:
        raise RuntimeError("authority evidence changed during execution")
    if (
        sha256(index_path) != MODEL_INDEX_SHA256
        or sha256(config_path) != MODEL_CONFIG_SHA256
    ):
        raise RuntimeError("model identity files changed during execution")
    final_library, final_runtime_manifest = core.verify_runtime_stage(stage)
    if final_library != library or final_runtime_manifest != runtime_manifest:
        raise RuntimeError("runtime stage changed during execution")
    final_loader, final_sycl = pair_driver.verify_loader_closure(
        stage, os.environ.copy(), final_runtime_manifest
    )
    final_runpaths = pair_driver.verify_runpaths(stage, final_runtime_manifest)
    if (
        normalized_loader(final_loader) != normalized_loader_closure
        or final_sycl != sycl_identity
        or final_runpaths != runpath_evidence
    ):
        raise RuntimeError("runtime loader closure changed during execution")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f"{output.name}.tmp-{nonce}")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        verify_host_and_storage()
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps(result, sort_keys=True))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
