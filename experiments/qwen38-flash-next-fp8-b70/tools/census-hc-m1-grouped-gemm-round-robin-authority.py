#!/usr/bin/env python3
"""Freeze production F.linear authorities for all 97 MTP0 HC up projections."""

from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets

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
CORE_SHA256 = "8b0486685e4167a3d9b4970d40635dd75b031792ef27ade71e27a5ae285af3b0"
SEED = 20260831
CONTROL_SWEEPS = 10
OUTPUT = Path(
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/"
    "hc-m1-grouped-up-round-robin-authority-seed20260831.json"
)
EXPECTED_LD_LIBRARY_PATH = ":".join(
    (
        "/mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels",
        "/home/steve/.venvs/vllm-xpu/lib",
        "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib",
        "/opt/intel/oneapi/compiler/2025.3/lib",
        "/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib",
    )
)
LOCK_PATHS = (
    Path("/tmp/q38-hc-m1-grouped-gemm-round-robin.lock"),
    Path("/tmp/q38-hc-m1-grouped-gemm-alternating.lock"),
    Path("/tmp/q38-hc-m1-grouped-gemm-pair.lock"),
    Path("/tmp/q38-hc-m1-grouped-gemm.lock"),
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


def import_core():
    path = Path(__file__).with_name("benchmark-hc-m1-grouped-gemm.py")
    if sha256(path) != CORE_SHA256:
        raise RuntimeError("frozen HC core helper has drifted")
    spec = importlib.util.spec_from_file_location("q38_hc_grouped_core", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


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


def main() -> None:
    script = Path(__file__).resolve()
    script_sha256 = sha256(script)
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite authority evidence: {OUTPUT}")
    if os.environ.get("ONEAPI_DEVICE_SELECTOR") != "level_zero:0":
        raise RuntimeError("ONEAPI_DEVICE_SELECTOR must be exactly level_zero:0")
    if (
        os.environ.get("PYTHONNOUSERSITE") != "1"
        or os.environ.get("PYTHONSAFEPATH") != "1"
    ):
        raise RuntimeError("isolated Python environment is required")
    if os.environ.get("LD_LIBRARY_PATH") != EXPECTED_LD_LIBRARY_PATH:
        raise RuntimeError(
            "LD_LIBRARY_PATH does not match the frozen component runtime"
        )
    core, core_path = import_core()
    locks = []
    for lock_path in LOCK_PATHS:
        lock = lock_path.open("w", encoding="utf-8")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"component lock is held: {lock_path}") from error
        locks.append(lock)
    core.refuse_active_server()
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
    weight_manifest: list[dict[str, str]] = []
    for slot, name in production_slots():
        shard_name = index["weight_map"].get(name)
        if not isinstance(shard_name, str):
            raise RuntimeError(f"model index omits target weight: {name}")
        with safe_open(MODEL / shard_name, framework="pt", device="cpu") as handle:
            weight = handle.get_tensor(name).contiguous()
        if weight.shape != (10240, 320) or weight.dtype != torch.bfloat16:
            raise RuntimeError(f"unexpected weight identity for {slot}: {weight.shape}")
        weight_hash = tensor_sha256(weight)
        weight_manifest.append(
            {
                "slot": slot,
                "name": name,
                "shard": shard_name,
                "sha256": weight_hash,
            }
        )
        weights_cpu.append(weight)
        inputs_cpu.append(
            (
                torch.randn((1, 320), dtype=torch.bfloat16, generator=generator) * 0.01
            ).contiguous()
        )
    if len(weight_manifest) != 97:
        raise RuntimeError("production MTP0 HC up slot count is not 97")
    if canonical_sha256(weight_manifest) != WEIGHT_MANIFEST_SHA256:
        raise RuntimeError("97-weight manifest digest drift")

    memory_before = int(torch.xpu.memory_allocated(0))
    weights = [weight.to("xpu") for weight in weights_cpu]
    inputs = [value.to("xpu") for value in inputs_cpu]
    torch.xpu.synchronize()
    memory_after_load = int(torch.xpu.memory_allocated(0))
    authority_hashes: list[list[str]] = []
    observed: list[set[str]] = [set() for _ in weight_manifest]
    for _ in range(CONTROL_SWEEPS):
        outputs = [F.linear(value, weight) for value, weight in zip(inputs, weights)]
        torch.xpu.synchronize()
        for position, output in enumerate(outputs):
            output_cpu = output.detach().cpu()
            if output_cpu.shape != (1, 10240) or output_cpu.dtype != torch.bfloat16:
                raise RuntimeError(f"control output identity drift at slot {position}")
            if not torch.isfinite(output_cpu.float()).all().item():
                raise RuntimeError(f"control output is non-finite at slot {position}")
            observed[position].add(tensor_sha256(output_cpu))
    for item, input_cpu, hashes in zip(weight_manifest, inputs_cpu, observed):
        if len(hashes) != 1:
            raise RuntimeError(
                f"control is not repeatable for {item['slot']}: {hashes}"
            )
        authority_hashes.append(
            [item["slot"], tensor_sha256(input_cpu), next(iter(hashes))]
        )
    authority_manifest_sha256 = canonical_sha256(authority_hashes)
    stat_tail = Path("/proc/self/stat").read_text(encoding="utf-8").rpartition(") ")[2]
    nonce = secrets.token_hex(32)
    result = {
        "schema_version": 1,
        "status": "production_authority_frozen",
        "classification": "control_only_97_weight_round_robin_census",
        "model": str(MODEL),
        "model_revision": MODEL_REVISION,
        "model_index_sha256": MODEL_INDEX_SHA256,
        "model_config_sha256": MODEL_CONFIG_SHA256,
        "seed": SEED,
        "control_sweeps": CONTROL_SWEEPS,
        "production_order": "layer0-attn,layer0-mlp,...,layer47-attn,layer47-mlp,final",
        "mtp_weights_included": False,
        "weight_count": len(weight_manifest),
        "weight_bytes_each": 10240 * 320 * 2,
        "weight_bank_bytes": len(weight_manifest) * 10240 * 320 * 2,
        "weight_manifest_sha256": WEIGHT_MANIFEST_SHA256,
        "weight_manifest": weight_manifest,
        "authority_manifest_sha256": authority_manifest_sha256,
        "authorities": authority_hashes,
        "all_authorities_finite": True,
        "unique_hashes_per_slot": 1,
        "xpu_memory": {
            "before_bytes": memory_before,
            "after_control_bank_load_bytes": memory_after_load,
            "delta_bytes": memory_after_load - memory_before,
        },
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
        "tool_sha256": script_sha256,
        "core_sha256": sha256(core_path),
        "candidate_invocations": 0,
        "source_integration_authorized": False,
        "endpoint_claim_authorized": False,
    }
    if sha256(script) != script_sha256 or sha256(core_path) != CORE_SHA256:
        raise RuntimeError("authority tool closure changed during execution")
    if sha256(index_path) != MODEL_INDEX_SHA256:
        raise RuntimeError("model index changed during execution")
    if sha256(config_path) != MODEL_CONFIG_SHA256:
        raise RuntimeError("model config changed during execution")
    final_manifest = [
        {
            **item,
            "sha256": tensor_sha256(weight),
        }
        for item, weight in zip(weight_manifest, weights_cpu)
    ]
    if canonical_sha256(final_manifest) != WEIGHT_MANIFEST_SHA256:
        raise RuntimeError("CPU weight bank changed during census")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_name(f"{OUTPUT.name}.tmp-{nonce}")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
