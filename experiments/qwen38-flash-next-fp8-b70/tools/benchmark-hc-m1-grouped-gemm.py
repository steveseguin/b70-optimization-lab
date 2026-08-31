#!/usr/bin/env python3
"""Screen the existing Xe2 grouped GEMM on real Qwen HC M=1 weights."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import statistics
import time

from safetensors import safe_open
import torch
import torch.nn.functional as F


EXPECTED_MODEL_REVISION = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
EXPECTED_MODEL_INDEX_SHA256 = (
    "0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6"
)
EXPECTED_CONFIG_SHA256 = (
    "99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d"
)
EXPECTED_SHARD_SHA256 = {
    "model-00001-of-00131.safetensors": (
        "774f0ceeadb40d165f2b3ff397d5f3840e6ca8fcb8f3d39d8acb4fea9e52c941"
    ),
    "model-00118-of-00131.safetensors": (
        "2d06ec9c1726f42bfc9ce0bbb47129917d8ab373c88eed4e758fb6940c92ad4a"
    ),
}
EXPECTED_LOGICAL_WEIGHT_SHA256 = {
    (0, "down"): "bff35df460770a5108d4dea52153322a4857358d5d2d6eb6a54c206d775735a1",
    (0, "up"): "6e87eb16e95e4e24cb83f3852d4200bdff7da87d8e8989022fe8012b88c2f978",
    (47, "down"): "367e391d0d9cf602d124ffe3c7a50ab9d48ed373569fe5ad8f1e3fa14f91831b",
    (47, "up"): "b910a9626f2a671a614e42eb0c4ad6c6a6c62ad6b787693ff127d564303062ae",
}
EXPECTED_PHYSICAL_WEIGHT_SHA256 = {
    (
        0,
        "down",
        "linear",
    ): "d0e4a87a9b06bf2b873e788e111a2c7b91e570bc813de641dfa48423b0cf6fc8",
    (
        0,
        "down",
        "grouped",
    ): "d8c0551681da4a7b5283cc0473f5c7e9cd14241df62dfe84282aa8753ef74d65",
    (
        0,
        "up",
        "linear",
    ): "6e87eb16e95e4e24cb83f3852d4200bdff7da87d8e8989022fe8012b88c2f978",
    (
        0,
        "up",
        "grouped",
    ): "6e87eb16e95e4e24cb83f3852d4200bdff7da87d8e8989022fe8012b88c2f978",
    (
        47,
        "down",
        "linear",
    ): "514e437bf03c8b84eb63bae9d9a812be5ed42c1b97f1967a3dac1d8fd75ac7cb",
    (
        47,
        "down",
        "grouped",
    ): "7e680ab1038ecf9ff7db32991df54e79701054642479f4ca8b11b29359bade24",
    (
        47,
        "up",
        "linear",
    ): "b910a9626f2a671a614e42eb0c4ad6c6a6c62ad6b787693ff127d564303062ae",
    (
        47,
        "up",
        "grouped",
    ): "b910a9626f2a671a614e42eb0c4ad6c6a6c62ad6b787693ff127d564303062ae",
}
LOCK_PATH = Path("/tmp/q38-hc-m1-grouped-gemm.lock")
LOADER_SUFFIX = (
    "/home/steve/.venvs/vllm-xpu/lib",
    "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib",
    "/opt/intel/oneapi/compiler/2025.3/lib",
    "/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib",
)


def load_extension(path: Path) -> None:
    spec = importlib.util.spec_from_file_location("vllm_xpu_kernels._xpu_C", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load extension: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tensor_sha256(tensor: torch.Tensor) -> str:
    return hashlib.sha256(
        tensor.contiguous().view(torch.uint8).cpu().numpy().tobytes()
    ).hexdigest()


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def load_weight(
    model: Path, layer: int, projection: str, provider: str
) -> tuple[torch.Tensor, torch.Tensor, Path, tuple[str, ...]]:
    prefix = f"model.language_model.layers.{layer}.attn_hyper_connection."
    index = json.loads((model / "model.safetensors.index.json").read_text())
    if projection == "down":
        names = (
            f"{prefix}input_mix_weight_down.weight",
            f"{prefix}block_inject_weight.weight",
        )
    else:
        names = (f"{prefix}input_mix_weight_up.weight",)
    shards = {index["weight_map"][name] for name in names}
    if len(shards) != 1:
        raise RuntimeError(f"HC projection spans unexpected shards: {sorted(shards)}")
    shard = model / shards.pop()
    with safe_open(shard, framework="pt", device="cpu") as handle:
        tensors = [handle.get_tensor(name) for name in names]
    if projection == "down":
        logical_weight = torch.cat(tuple(tensors), dim=0).contiguous()
        if logical_weight.shape != (324, 10240):
            raise RuntimeError(f"unexpected logical down shape: {logical_weight.shape}")
        physical_width = 336 if provider == "linear" else 352
        padding_width = physical_width - logical_weight.shape[0]
        padding = torch.zeros((padding_width, 10240), dtype=torch.bfloat16)
        weight = torch.cat((logical_weight, padding), dim=0).contiguous()
        if weight.shape != (physical_width, 10240):
            raise RuntimeError(f"unexpected merged down shape: {weight.shape}")
        if torch.count_nonzero(weight[324:]).item() != 0:
            raise RuntimeError("down-projection physical padding is not all zero")
    else:
        logical_weight = tensors[0].contiguous()
        weight = logical_weight
        if weight.shape != (10240, 320):
            raise RuntimeError(f"unexpected up shape: {weight.shape}")
    logical_hash = tensor_sha256(logical_weight)
    expected_logical_hash = EXPECTED_LOGICAL_WEIGHT_SHA256[(layer, projection)]
    if logical_hash != expected_logical_hash:
        raise RuntimeError(
            f"unexpected logical weight digest: {logical_hash} != {expected_logical_hash}"
        )
    physical_hash = tensor_sha256(weight)
    expected_physical_hash = EXPECTED_PHYSICAL_WEIGHT_SHA256[
        (layer, projection, provider)
    ]
    if physical_hash != expected_physical_hash:
        raise RuntimeError(
            "unexpected physical weight digest: "
            f"{physical_hash} != {expected_physical_hash}"
        )
    return weight, logical_weight, shard, names


def verify_runtime_stage(stage: Path) -> tuple[Path, dict[str, str]]:
    stage = stage.resolve()
    manifest = stage / "SHA256SUMS"
    if not manifest.is_file():
        raise RuntimeError(f"runtime stage has no SHA256SUMS: {stage}")
    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        name = name.removeprefix("*")
        path = stage / name
        if not path.is_file():
            raise RuntimeError(f"runtime-stage file is missing: {path}")
        if path.is_symlink():
            raise RuntimeError(f"runtime-stage file may not be a symlink: {path}")
        actual = file_sha256(path)
        if actual != expected:
            raise RuntimeError(
                f"runtime-stage digest mismatch for {name}: {actual} != {expected}"
            )
        entries[name] = actual
    required = {"_xpu_C.abi3.so", "libgrouped_gemm_xe_2.so"}
    if not required.issubset(entries):
        raise RuntimeError(
            f"runtime stage omits required files: {sorted(required - entries.keys())}"
        )
    staged_libraries = {path.name for path in stage.glob("*.so")}
    manifested_libraries = {name for name in entries if name.endswith(".so")}
    if staged_libraries != manifested_libraries:
        raise RuntimeError(
            "runtime-stage shared objects and manifest differ: "
            f"files={sorted(staged_libraries)} "
            f"manifest={sorted(manifested_libraries)}"
        )
    expected_loader_path = ":".join((str(stage), *LOADER_SUFFIX))
    if os.environ.get("LD_LIBRARY_PATH") != expected_loader_path:
        raise RuntimeError("LD_LIBRARY_PATH does not match the frozen component path")
    return stage / "_xpu_C.abi3.so", entries


def refuse_active_server() -> None:
    needles = (
        b"vllm serve",
        b"vllm.entrypoints.openai.api_server",
        b"VLLM::Engine",
        b"VLLM::Worker",
        b"qwen38-flash-next-fp8-tp",
    )
    own_pid = os.getpid()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == own_pid:
            continue
        try:
            command = (proc / "cmdline").read_bytes().replace(b"\0", b" ")
            comm = (proc / "comm").read_bytes()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        process_text = command + b" " + comm
        if any(needle in process_text for needle in needles):
            raise RuntimeError(f"active model/server process detected: pid {proc.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-stage", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--layer", type=int, choices=(0, 47), required=True)
    parser.add_argument("--projection", choices=("down", "up"), required=True)
    parser.add_argument("--provider", choices=("linear", "grouped"), required=True)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--warmups", type=int, default=100)
    parser.add_argument("--timed-batches", type=int, default=21)
    parser.add_argument("--iterations-per-batch", type=int, default=100)
    parser.add_argument("--hash-repeats", type=int, default=100)
    args = parser.parse_args()

    if args.model_revision != EXPECTED_MODEL_REVISION:
        raise RuntimeError(f"unexpected model revision: {args.model_revision}")
    if os.environ.get("ONEAPI_DEVICE_SELECTOR") != "level_zero:0":
        raise RuntimeError("ONEAPI_DEVICE_SELECTOR must be exactly level_zero:0")
    if (
        os.environ.get("PYTHONNOUSERSITE") != "1"
        or os.environ.get("PYTHONSAFEPATH") != "1"
    ):
        raise RuntimeError("isolated Python environment is required")
    refuse_active_server()
    lock_handle = LOCK_PATH.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise RuntimeError(f"component-run lock is held: {LOCK_PATH}") from error

    library, runtime_manifest = verify_runtime_stage(args.runtime_stage)
    load_extension(library)
    if not hasattr(torch.ops._xpu_C, "cutlass_grouped_gemm_interface"):
        raise RuntimeError("runtime extension lacks cutlass_grouped_gemm_interface")
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("selector must expose exactly one XPU")
    device_name = torch.xpu.get_device_name(0)
    if "Arc(TM) Pro B70" not in device_name and "Arc Pro B70" not in device_name:
        raise RuntimeError(f"selected XPU is not an Arc Pro B70: {device_name}")
    model = args.model.resolve()
    index_path = model / "model.safetensors.index.json"
    config_path = model / "config.json"
    index_sha256 = file_sha256(index_path)
    config_sha256 = file_sha256(config_path)
    if index_sha256 != EXPECTED_MODEL_INDEX_SHA256:
        raise RuntimeError(f"unexpected model index digest: {index_sha256}")
    if config_sha256 != EXPECTED_CONFIG_SHA256:
        raise RuntimeError(f"unexpected model config digest: {config_sha256}")
    weight_cpu, logical_weight_cpu, shard, weight_names = load_weight(
        model, args.layer, args.projection, args.provider
    )
    shard_sha256 = file_sha256(shard)
    if shard_sha256 != EXPECTED_SHARD_SHA256.get(shard.name):
        raise RuntimeError(
            f"unexpected model shard digest: {shard.name} {shard_sha256}"
        )
    n, k = weight_cpu.shape
    if args.provider == "grouped" and (n % 32 != 0 or k % 32 != 0):
        raise RuntimeError(f"grouped-GEMM N/K are not 32-aligned: N={n} K={k}")
    generator = torch.Generator(device="cpu").manual_seed(args.seed)
    x_cpu = torch.randn((1, k), dtype=torch.bfloat16, generator=generator) * 0.01
    x = x_cpu.to("xpu")
    weight = weight_cpu.to("xpu")
    packed = weight.t().contiguous().unsqueeze(0)
    grouped_output = torch.empty((1, n), dtype=torch.bfloat16, device="xpu")
    rows_per_expert = torch.ones((1,), dtype=torch.int32, device="xpu")

    def invoke() -> torch.Tensor:
        if args.provider == "linear":
            return F.linear(x, weight)
        torch.ops._xpu_C.cutlass_grouped_gemm_interface(
            x,
            packed,
            None,
            None,
            grouped_output,
            rows_per_expert,
            n,
            k,
            1,
            False,
            False,
        )
        return grouped_output

    compile_started = time.monotonic()
    output = invoke()
    torch.xpu.synchronize()
    first_call_seconds = time.monotonic() - compile_started
    for _ in range(args.warmups):
        output = invoke()
    torch.xpu.synchronize()

    timing_us: list[float] = []
    for _ in range(args.timed_batches):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations_per_batch):
            output = invoke()
        end.record()
        end.synchronize()
        timing_us.append(start.elapsed_time(end) * 1000.0 / args.iterations_per_batch)
    if any(not math.isfinite(value) or value <= 0.0 for value in timing_us):
        raise RuntimeError(f"invalid timing sample: {timing_us}")

    consumed_width = 324 if args.projection == "down" else n
    full_hashes: set[str] = set()
    consumed_hashes: set[str] = set()
    discarded_nonzero_repeats = 0
    for _ in range(args.hash_repeats):
        output = invoke()
        torch.xpu.synchronize()
        repeat_output = output.cpu()
        full_hashes.add(tensor_sha256(repeat_output))
        consumed_hashes.add(tensor_sha256(repeat_output[:, :consumed_width]))
        if torch.count_nonzero(repeat_output[:, consumed_width:]).item() != 0:
            discarded_nonzero_repeats += 1
    output_cpu = output.cpu()
    consumed_output = output_cpu[:, :consumed_width].contiguous()
    discarded_output = output_cpu[:, consumed_width:].contiguous()
    output_float = consumed_output.float()
    finite = bool(torch.isfinite(output_float).all())
    if not finite:
        raise RuntimeError("HC projection returned non-finite output")
    if len(consumed_hashes) != 1:
        raise RuntimeError(
            f"HC consumed projection was not repeatable: {len(consumed_hashes)} hashes"
        )
    if discarded_nonzero_repeats:
        raise RuntimeError(
            "discarded padded output was nonzero in "
            f"{discarded_nonzero_repeats} repeats"
        )

    print(
        json.dumps(
            {
                "schema_version": 1,
                "status": "component_arm_valid",
                "provider": args.provider,
                "layer": args.layer,
                "projection": args.projection,
                "shape": {"m": 1, "n": n, "k": k},
                "seed": args.seed,
                "input_sha256": tensor_sha256(x_cpu),
                "input_dtype": str(x.dtype),
                "logical_weight_sha256": tensor_sha256(logical_weight_cpu),
                "logical_weight_layout_nk": list(logical_weight_cpu.shape),
                "weight_sha256": tensor_sha256(weight_cpu),
                "weight_names": list(weight_names),
                "weight_dtype": str(weight.dtype),
                "weight_layout_nk": list(weight.shape),
                "packed_layout_ekn": list(packed.shape),
                "runtime_stage": str(args.runtime_stage.resolve()),
                "runtime_manifest": runtime_manifest,
                "runtime_manifest_sha256": file_sha256(
                    args.runtime_stage.resolve() / "SHA256SUMS"
                ),
                "loader_environment": {
                    "ld_library_path": os.environ["LD_LIBRARY_PATH"],
                    "python_no_user_site": os.environ.get("PYTHONNOUSERSITE"),
                    "python_safe_path": os.environ.get("PYTHONSAFEPATH"),
                },
                "library": str(library),
                "library_sha256": file_sha256(library),
                "model": str(model),
                "model_revision": args.model_revision,
                "model_index_sha256": index_sha256,
                "model_config_sha256": config_sha256,
                "model_shard": shard.name,
                "model_shard_sha256": shard_sha256,
                "device": {
                    "selector": os.environ["ONEAPI_DEVICE_SELECTOR"],
                    "count": torch.xpu.device_count(),
                    "name": device_name,
                    "torch": torch.__version__,
                },
                "first_call_seconds": first_call_seconds,
                "finite": finite,
                "max_abs": float(output_float.abs().max()),
                "unique_consumed_output_sha256": len(consumed_hashes),
                "unique_full_output_sha256": len(full_hashes),
                "full_output_sha256_values": sorted(full_hashes),
                "consumed_width": consumed_width,
                "alignment": {
                    "grouped_nk_multiple": 32,
                    "padding_width": n - consumed_width,
                },
                "discarded_output_all_zero": bool(discarded_nonzero_repeats == 0),
                "discarded_output_nonzero_repeats": discarded_nonzero_repeats,
                "discarded_output_sha256": tensor_sha256(discarded_output),
                "consumed_output_sha256": tensor_sha256(consumed_output),
                "timing_us": {
                    "median": statistics.median(timing_us),
                    "mean": statistics.mean(timing_us),
                    "p10": percentile(timing_us, 0.10),
                    "p90": percentile(timing_us, 0.90),
                    "samples": timing_us,
                },
                "repeats": {
                    "warmups": args.warmups,
                    "timed_batches": args.timed_batches,
                    "iterations_per_batch": args.iterations_per_batch,
                    "hash": args.hash_repeats,
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
