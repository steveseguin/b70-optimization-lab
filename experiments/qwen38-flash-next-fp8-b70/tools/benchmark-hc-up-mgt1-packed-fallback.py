#!/usr/bin/env python3
"""Run one frozen real-weight Qwen HC-up M>1 fallback component arm."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import secrets
import statistics
import subprocess
import sys
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
CORE = Path(__file__).with_name("benchmark-hc-m1-grouped-gemm.py")
CORE_SHA256 = "8b0486685e4167a3d9b4970d40635dd75b031792ef27ade71e27a5ae285af3b0"
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
EVIDENCE_BASE = Path("/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70")
SEED = 20260831
RUN_ATTEMPT = 2
EXPECTED_PYTHON_PREFIX = Path("/home/steve/.venvs/vllm-xpu")
M_VALUES = (2, 8, 64, 256, 1024, 4096)
PROVIDERS = ("authority", "packed_view", "matmul", "grouped")
HASH_REPEATS = {2: 100, 8: 100, 64: 30, 256: 10, 1024: 5, 4096: 3}
WARMUPS = {2: 20, 8: 20, 64: 10, 256: 5, 1024: 3, 4096: 2}
ITERATIONS = {2: 1000, 8: 512, 64: 128, 256: 32, 1024: 8, 4096: 2}
TIMED_BATCHES = 11
MIN_XPU_FREE_BYTES = 1024**3
MAX_ARM_PEAK_DELTA_BYTES = 512 * 1024**2
MIN_EVIDENCE_FREE_BYTES = 50 * 1024**3
EXPECTED_NORMALIZED_LOADER_SHA256 = (
    "ce2247ccad4f7466ad69dfc9469d9adc5fa41ebe89ac4016570bae9d5e4680c4"
)
EXPECTED_SYCL = Path("/home/steve/.venvs/vllm-xpu/lib/libsycl.so.8")
EXPECTED_SYCL_SHA256 = (
    "0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f"
)
EXPECTED_LD_LIBRARY_PATH = ":".join(
    (
        str(STAGE),
        "/home/steve/.venvs/vllm-xpu/lib",
        "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib",
        "/opt/intel/oneapi/compiler/2025.3/lib",
        "/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib",
    )
)


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


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def import_core():
    if sha256(CORE) != CORE_SHA256:
        raise RuntimeError("frozen HC component core has drifted")
    spec = importlib.util.spec_from_file_location("q38_hc_mgt1_core", CORE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen helper: {CORE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def production_slots() -> list[tuple[str, str]]:
    slots: list[tuple[str, str]] = []
    for layer in range(48):
        for family in ("attn", "mlp"):
            slots.append(
                (
                    f"{layer:02d}-{family}",
                    "model.language_model.layers."
                    f"{layer}.{family}_hyper_connection."
                    "input_mix_weight_up.weight",
                )
            )
    slots.append(
        (
            "final",
            "model.language_model.hyper_connection_mixer.input_mix_weight_up.weight",
        )
    )
    return slots


def refuse_render_node_owners() -> None:
    allowed = {os.getpid(), os.getppid()}
    owners: list[tuple[int, str]] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) in allowed:
            continue
        try:
            for descriptor in (proc / "fd").iterdir():
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


def verify_evidence_storage() -> dict[str, object]:
    mounts = []
    for line in Path("/proc/mounts").read_text(encoding="utf-8").splitlines():
        source, target, filesystem, options, *_ = line.split()
        if target == "/mnt/usb-models":
            mounts.append((source, filesystem, options))
    if len(mounts) != 1 or mounts[0][0:2] != ("/dev/sda2", "fuseblk"):
        raise RuntimeError(f"unexpected evidence mount identity: {mounts}")
    free = os.statvfs(EVIDENCE_BASE)
    free_bytes = free.f_bavail * free.f_frsize
    if free_bytes < MIN_EVIDENCE_FREE_BYTES:
        raise RuntimeError(f"insufficient evidence-drive free space: {free_bytes}")
    return {
        "source": mounts[0][0],
        "filesystem": mounts[0][1],
        "mount": "/mnt/usb-models",
        "free_bytes": free_bytes,
        "minimum_free_bytes": MIN_EVIDENCE_FREE_BYTES,
    }


def verify_loader_closure() -> dict[str, object]:
    completed = subprocess.run(
        ["ldd", str(STAGE / "_xpu_C.abi3.so")],
        check=True,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    closure = completed.stdout
    if "not found" in closure:
        raise RuntimeError(f"runtime loader dependency missing:\n{closure}")
    expected_grouped = f"libgrouped_gemm_xe_2.so => {STAGE}/libgrouped_gemm_xe_2.so"
    if expected_grouped not in closure:
        raise RuntimeError("grouped GEMM library did not resolve from frozen stage")
    sycl_match = re.search(r"libsycl\.so\.8 => (\S+)", closure)
    if sycl_match is None or "libsycl.so.9" in closure:
        raise RuntimeError("runtime closure is not exclusively SYCL 8")
    sycl_path = Path(sycl_match.group(1)).resolve()
    if (
        sycl_path != EXPECTED_SYCL.resolve()
        or sha256(sycl_path) != EXPECTED_SYCL_SHA256
    ):
        raise RuntimeError(f"unexpected SYCL provider: {sycl_path}")
    normalized = [
        re.sub(r"\s+\(0x[0-9a-f]+\)$", "", line) for line in closure.splitlines()
    ]
    normalized_sha256 = canonical_sha256(normalized)
    if normalized_sha256 != EXPECTED_NORMALIZED_LOADER_SHA256:
        raise RuntimeError("normalized runtime loader closure drift")
    return {
        "normalized_sha256": normalized_sha256,
        "sycl_path": str(sycl_path),
        "sycl_sha256": EXPECTED_SYCL_SHA256,
    }


def atomic_write_json(
    path: Path, value: object, nonce: str, storage_before: dict[str, object]
) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {path}")
    temporary = path.with_name(f".{path.name}.tmp-{nonce}")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        storage_at_link = verify_evidence_storage()
        if storage_at_link["source"] != storage_before["source"]:
            raise RuntimeError("evidence mount source changed before link")
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_parent() -> tuple[int, str]:
    raw_pid = os.environ.get("Q38_HC_MGT1_DRIVER_PID", "")
    nonce = os.environ.get("Q38_HC_MGT1_DRIVER_NONCE", "")
    if not raw_pid.isdigit() or int(raw_pid) != os.getppid():
        raise RuntimeError("worker must be launched by the frozen gate driver")
    if len(nonce) != 64 or any(
        character not in "0123456789abcdef" for character in nonce
    ):
        raise RuntimeError("invalid gate-driver nonce")
    return int(raw_pid), nonce


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope", choices=("smoke", "s1", "s2", "s3", "s3g"), required=True
    )
    parser.add_argument("--repeat", choices=("r1", "r2"))
    parser.add_argument(
        "--slot", choices=tuple(slot for slot, _ in production_slots()), required=True
    )
    parser.add_argument("--m", type=int, choices=M_VALUES, required=True)
    parser.add_argument("--provider", choices=PROVIDERS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.scope == "s3g" and args.provider not in ("authority", "grouped"):
        raise RuntimeError("s3g accepts only authority and grouped providers")

    script = Path(__file__).resolve()
    script_sha256 = sha256(script)
    parent_pid, driver_nonce = validate_parent()
    if args.scope == "smoke":
        if args.repeat is not None or args.slot != "00-attn" or args.m != 2:
            raise RuntimeError("smoke is frozen to 00-attn M2 without a repeat label")
        run_name = f"hc-up-mgt1-packed-fallback-smoke-a{RUN_ATTEMPT}-seed{SEED}"
    else:
        if args.repeat is None:
            raise RuntimeError("staged scope requires --repeat r1 or r2")
        allowed = {
            "s1": args.slot == "00-attn" and args.m in (2, 64),
            "s2": args.slot in ("00-attn", "00-mlp", "24-attn", "47-mlp", "final")
            and args.m in M_VALUES,
            "s3": args.m == 64,
            "s3g": args.m == 64,
        }
        if not allowed[args.scope]:
            raise RuntimeError(f"cell is outside frozen {args.scope} scope")
        run_name = (
            f"hc-up-mgt1-packed-fallback-{args.scope}-{args.repeat}-"
            f"a{RUN_ATTEMPT}-seed{SEED}"
        )
    expected_output = (
        EVIDENCE_BASE
        / run_name
        / "arms"
        / f"{args.slot}-m{args.m}-{args.provider}.json"
    ).resolve()
    output = args.output.resolve()
    if output != expected_output:
        raise RuntimeError(f"unexpected arm evidence path: {output}")
    if output.exists():
        raise RuntimeError(f"refusing to overwrite arm evidence: {output}")
    if Path(sys.prefix) != EXPECTED_PYTHON_PREFIX:
        raise RuntimeError(f"worker must use frozen Python prefix: {sys.prefix}")
    evidence_storage_before = verify_evidence_storage()
    if os.environ.get("ONEAPI_DEVICE_SELECTOR") != "level_zero:0":
        raise RuntimeError("ONEAPI_DEVICE_SELECTOR must be exactly level_zero:0")
    if (
        os.environ.get("PYTHONNOUSERSITE") != "1"
        or os.environ.get("PYTHONSAFEPATH") != "1"
        or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1"
    ):
        raise RuntimeError("isolated Python environment is required")
    if os.environ.get("LD_LIBRARY_PATH") != EXPECTED_LD_LIBRARY_PATH:
        raise RuntimeError(
            "LD_LIBRARY_PATH does not match the frozen component runtime"
        )

    core = import_core()
    core.refuse_active_server()
    refuse_render_node_owners()
    loader_closure_before = verify_loader_closure()
    stage_manifest = STAGE / "SHA256SUMS"
    if sha256(stage_manifest) != STAGE_MANIFEST_SHA256:
        raise RuntimeError("runtime-stage manifest digest drift")
    library, runtime_manifest = core.verify_runtime_stage(STAGE)
    if runtime_manifest != RUNTIME_MANIFEST:
        raise RuntimeError("runtime-stage entries drifted")
    core.load_extension(library)
    if args.provider == "grouped" and not hasattr(
        torch.ops._xpu_C, "cutlass_grouped_gemm_interface"
    ):
        raise RuntimeError("runtime extension lacks grouped GEMM")
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("selector must expose exactly one XPU")
    device_name = torch.xpu.get_device_name(0)
    if "Arc" not in device_name or "B70" not in device_name:
        raise RuntimeError(f"selected device is not an Arc Pro B70: {device_name}")
    free_bytes, total_bytes = torch.xpu.mem_get_info(0)
    if free_bytes < MIN_XPU_FREE_BYTES:
        raise RuntimeError(f"insufficient free XPU memory: {free_bytes}")

    index_path = MODEL / "model.safetensors.index.json"
    config_path = MODEL / "config.json"
    if sha256(index_path) != MODEL_INDEX_SHA256:
        raise RuntimeError("model index digest drift")
    if sha256(config_path) != MODEL_CONFIG_SHA256:
        raise RuntimeError("model config digest drift")
    if sha256(AUTHORITY) != AUTHORITY_SHA256:
        raise RuntimeError("97-weight authority evidence digest drift")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    manifest = authority.get("weight_manifest")
    if not isinstance(manifest, list) or len(manifest) != 97:
        raise RuntimeError("authority weight manifest is incomplete")
    if canonical_sha256(manifest) != WEIGHT_MANIFEST_SHA256:
        raise RuntimeError("authority weight manifest content drift")
    manifest_by_slot = {item["slot"]: item for item in manifest}
    if len(manifest_by_slot) != 97 or args.slot not in manifest_by_slot:
        raise RuntimeError("authority slot identity drift")
    item = manifest_by_slot[args.slot]
    expected_name = dict(production_slots())[args.slot]
    if item.get("name") != expected_name:
        raise RuntimeError(f"authority name drift for {args.slot}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("weight_map", {}).get(expected_name) != item.get("shard"):
        raise RuntimeError(f"model index remapped {args.slot}")
    with safe_open(MODEL / item["shard"], framework="pt", device="cpu") as handle:
        weight_cpu = handle.get_tensor(expected_name).contiguous()
    if weight_cpu.shape != (10240, 320) or weight_cpu.dtype != torch.bfloat16:
        raise RuntimeError(f"unexpected logical weight identity for {args.slot}")
    logical_weight_sha256 = tensor_sha256(weight_cpu)
    if logical_weight_sha256 != item.get("sha256"):
        raise RuntimeError(f"logical weight digest drift for {args.slot}")

    slot_index = [slot for slot, _ in production_slots()].index(args.slot)
    cell_seed = SEED + slot_index * 8192 + args.m
    generator = torch.Generator(device="cpu").manual_seed(cell_seed)
    input_cpu = (
        torch.randn((args.m, 320), dtype=torch.bfloat16, generator=generator) * 0.01
    ).contiguous()
    input_sha256 = tensor_sha256(input_cpu)
    baseline_allocated = int(torch.xpu.memory_allocated(0))
    torch.xpu.reset_peak_memory_stats(0)
    x = input_cpu.to("xpu")
    rows = None
    packed = None
    weight = None
    prepack_seconds = 0.0
    if args.provider == "authority":
        weight = weight_cpu.to("xpu")
        physical_weight = weight
        physical_layout = "nk_contiguous"
    else:
        weight = weight_cpu.to("xpu")
        torch.xpu.synchronize()
        prepack_started = time.monotonic()
        packed = weight.T.contiguous().unsqueeze(0)
        torch.xpu.synchronize()
        prepack_seconds = time.monotonic() - prepack_started
        del weight
        weight = None
        torch.xpu.empty_cache()
        physical_weight = packed
        physical_layout = "ekn_contiguous"
        if args.provider == "grouped":
            rows = torch.tensor([args.m], dtype=torch.int32, device="xpu")
    del weight_cpu
    gc.collect()
    torch.xpu.synchronize()
    physical_weight_sha256_before = tensor_sha256(physical_weight)
    input_device_sha256_before = tensor_sha256(x)
    if input_device_sha256_before != input_sha256:
        raise RuntimeError("host-to-XPU input transfer changed bytes")

    def invoke() -> torch.Tensor:
        if args.provider == "authority":
            assert weight is not None
            return F.linear(x, weight)
        assert packed is not None
        if args.provider == "packed_view":
            return F.linear(x, packed[0].T)
        if args.provider == "matmul":
            return torch.matmul(x, packed[0])
        assert rows is not None
        output_tensor = x.new_empty((args.m, 10240))
        returned = torch.ops._xpu_C.cutlass_grouped_gemm_interface(
            x,
            packed,
            None,
            None,
            output_tensor,
            rows,
            10240,
            320,
            1,
            False,
            False,
        )
        if returned.data_ptr() != output_tensor.data_ptr():
            raise RuntimeError("grouped GEMM did not return its fresh output")
        return output_tensor

    first_started = time.monotonic()
    first = invoke()
    torch.xpu.synchronize()
    first_call_seconds = time.monotonic() - first_started
    first_pointer = first.data_ptr()
    first_hash = tensor_sha256(first)
    del first
    torch.xpu.empty_cache()
    second = invoke()
    torch.xpu.synchronize()
    second_hash = tensor_sha256(second)
    if first_hash != second_hash:
        raise RuntimeError("two sequential provider outputs are not repeatable")
    second_pointer = second.data_ptr()
    del second
    torch.xpu.empty_cache()

    for _ in range(WARMUPS[args.m]):
        warm = invoke()
    torch.xpu.synchronize()
    del warm
    timing_us: list[float] = []
    for _ in range(TIMED_BATCHES):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(ITERATIONS[args.m]):
            timed = invoke()
        end.record()
        end.synchronize()
        timing_us.append(start.elapsed_time(end) * 1000.0 / ITERATIONS[args.m])
        del timed
    if any(not math.isfinite(value) or value <= 0.0 for value in timing_us):
        raise RuntimeError(f"invalid timing samples: {timing_us}")

    output_hashes: set[str] = set()
    final_output_cpu = None
    for _ in range(HASH_REPEATS[args.m]):
        repeated = invoke()
        torch.xpu.synchronize()
        final_output_cpu = repeated.detach().cpu()
        output_hashes.add(tensor_sha256(final_output_cpu))
        del repeated
    if len(output_hashes) != 1 or first_hash not in output_hashes:
        raise RuntimeError("provider output is not bit-repeatable")
    assert final_output_cpu is not None
    if final_output_cpu.shape != (args.m, 10240):
        raise RuntimeError("provider output shape drift")
    if final_output_cpu.dtype != torch.bfloat16:
        raise RuntimeError("provider output dtype drift")
    output_float = final_output_cpu.float()
    if not torch.isfinite(output_float).all().item():
        raise RuntimeError("provider output is non-finite")
    if tensor_sha256(x) != input_device_sha256_before:
        raise RuntimeError("provider mutated its input")
    if tensor_sha256(physical_weight) != physical_weight_sha256_before:
        raise RuntimeError("provider mutated its physical weight")
    if rows is not None:
        rows_cpu = rows.cpu()
        if rows_cpu.tolist() != [args.m] or int(rows_cpu.sum()) != args.m:
            raise RuntimeError("grouped rows-per-expert identity drift")
    peak_allocated = int(torch.xpu.max_memory_allocated(0))
    peak_delta = peak_allocated - baseline_allocated
    if peak_delta > MAX_ARM_PEAK_DELTA_BYTES:
        raise RuntimeError(f"arm exceeded memory cap: {peak_delta}")

    stat_tail = Path("/proc/self/stat").read_text(encoding="utf-8").rpartition(") ")[2]
    result_nonce = secrets.token_hex(32)
    result = {
        "schema_version": 1,
        "status": "component_arm_valid",
        "classification": "real_weight_hc_up_mgt1_packed_fallback_arm",
        "scope": args.scope,
        "repeat": args.repeat,
        "run_attempt": RUN_ATTEMPT,
        "provider": args.provider,
        "slot": args.slot,
        "slot_index": slot_index,
        "weight_name": expected_name,
        "model_shard": item["shard"],
        "model": str(MODEL),
        "model_revision": MODEL_REVISION,
        "model_index_sha256": MODEL_INDEX_SHA256,
        "model_config_sha256": MODEL_CONFIG_SHA256,
        "weight_manifest_sha256": WEIGHT_MANIFEST_SHA256,
        "authority_evidence": str(AUTHORITY),
        "authority_evidence_sha256": AUTHORITY_SHA256,
        "shape": {"m": args.m, "n": 10240, "k": 320},
        "dtype": "torch.bfloat16",
        "seed": SEED,
        "cell_seed": cell_seed,
        "input_sha256": input_sha256,
        "logical_weight_sha256": logical_weight_sha256,
        "physical_weight_sha256": physical_weight_sha256_before,
        "physical_weight_layout": physical_layout,
        "physical_weight_shape": list(physical_weight.shape),
        "physical_weight_stride": list(physical_weight.stride()),
        "output_sha256": next(iter(output_hashes)),
        "unique_output_sha256": len(output_hashes),
        "finite": True,
        "output_statistics": {
            "min": float(output_float.min()),
            "max": float(output_float.max()),
            "mean": float(output_float.mean()),
        },
        "fresh_output_allocation": True,
        "fresh_output_allocation_contract": {
            "authority": "torch.nn.functional.linear return",
            "packed_view": "torch.nn.functional.linear return",
            "matmul": "torch.matmul return",
            "grouped": "x.new_empty before every grouped invocation",
        }[args.provider],
        "sequential_output_data_ptrs": [first_pointer, second_pointer],
        "first_call_seconds": first_call_seconds,
        "prepack_seconds": prepack_seconds,
        "timing_us": {
            "median": statistics.median(timing_us),
            "mean": statistics.mean(timing_us),
            "p10": percentile(timing_us, 0.10),
            "p90": percentile(timing_us, 0.90),
            "samples": timing_us,
        },
        "repeats": {
            "warmups": WARMUPS[args.m],
            "timed_batches": TIMED_BATCHES,
            "iterations_per_batch": ITERATIONS[args.m],
            "hash": HASH_REPEATS[args.m],
        },
        "memory": {
            "free_before_bytes": int(free_bytes),
            "total_bytes": int(total_bytes),
            "allocated_baseline_bytes": baseline_allocated,
            "peak_allocated_bytes": peak_allocated,
            "peak_delta_bytes": peak_delta,
            "peak_delta_cap_bytes": MAX_ARM_PEAK_DELTA_BYTES,
        },
        "runtime_stage": str(STAGE),
        "runtime_manifest": runtime_manifest,
        "runtime_manifest_sha256": STAGE_MANIFEST_SHA256,
        "loader_closure_before": loader_closure_before,
        "device": {
            "selector": "level_zero:0",
            "count": torch.xpu.device_count(),
            "name": device_name,
            "torch": torch.__version__,
        },
        "process_identity": {
            "python_executable": sys.executable,
            "python_prefix": sys.prefix,
            "boot_id": Path("/proc/sys/kernel/random/boot_id")
            .read_text(encoding="utf-8")
            .strip(),
            "pid": os.getpid(),
            "process_start_ticks": int(stat_tail.split()[19]),
            "parent_pid": parent_pid,
            "driver_nonce_sha256": hashlib.sha256(driver_nonce.encode()).hexdigest(),
            "nonce": result_nonce,
        },
        "tool_sha256": script_sha256,
        "source_integration_authorized": False,
        "endpoint_claim_authorized": False,
    }
    if sha256(script) != script_sha256 or sha256(CORE) != CORE_SHA256:
        raise RuntimeError("worker closure changed during execution")
    if (
        sha256(index_path) != MODEL_INDEX_SHA256
        or sha256(config_path) != MODEL_CONFIG_SHA256
    ):
        raise RuntimeError("model identity changed during execution")
    if sha256(AUTHORITY) != AUTHORITY_SHA256:
        raise RuntimeError("authority evidence changed during execution")
    loader_closure_after = verify_loader_closure()
    if loader_closure_after != loader_closure_before:
        raise RuntimeError("runtime loader closure changed during arm")
    result["loader_closure_after"] = loader_closure_after
    result["evidence_storage_before"] = evidence_storage_before
    atomic_write_json(output, result, result_nonce, evidence_storage_before)
    evidence_storage_after = verify_evidence_storage()
    if evidence_storage_after["source"] != evidence_storage_before["source"]:
        raise RuntimeError("evidence mount source changed after arm write")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
