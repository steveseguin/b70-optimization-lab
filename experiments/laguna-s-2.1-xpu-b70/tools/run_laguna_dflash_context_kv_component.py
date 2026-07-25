#!/usr/bin/env python3
"""Exactness-only, one-card Laguna DFlash context-KV component gate.

This is not a benchmark and never instantiates a service or generates tokens.
It exercises the frozen candidate helper with the real rank-local DFlash
checkpoint slices, then checks every BF16 boundary through RoPE and cache
writes against the allocating incumbent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace
from typing import Any

MAIN_ROOT = Path("/home/steve/llm-optimizations")
VLLM_ROOT = Path("/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725")
VLLM_COMMIT = "4459910e2ac5a7b552887fc0a3f3e3cf9a4701c0"
KERNEL_ROOT = Path("/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727")
KERNEL_COMMIT = "4772f727590c51b72add79350b913d098cf67872"
MODEL_ROOT = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4")
MODEL_FILE = MODEL_ROOT / "model.safetensors"
MODEL_SHA256 = "0850e39b5c079a9f1a9bafed729a4545b088a91876541d010d871f6d6d8bf909"
CONFIG_FILE = MODEL_ROOT / "config.json"
CONFIG_SHA256 = "6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926"
KERNELS = {
    "_C.abi3.so": "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2",
    "_xpu_C.abi3.so": "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8",
    "_moe_C.abi3.so": "6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b",
}
DEVICES = (
    {
        "device_id": 0,
        "drm_device": "/dev/dri/card3",
        "pci_bdf_address": "0000:23:00.0",
        "uuid": "00000000-0000-0023-0000-0000e2238086",
    },
    {
        "device_id": 1,
        "drm_device": "/dev/dri/card4",
        "pci_bdf_address": "0000:27:00.0",
        "uuid": "00000000-0000-0027-0000-0000e2238086",
    },
    {
        "device_id": 2,
        "drm_device": "/dev/dri/card0",
        "pci_bdf_address": "0000:43:00.0",
        "uuid": "00000000-0000-0043-0000-0000e2238086",
    },
    {
        "device_id": 3,
        "drm_device": "/dev/dri/card2",
        "pci_bdf_address": "0000:47:00.0",
        "uuid": "00000000-0000-0047-0000-0000e2238086",
    },
)
LAYERS = 6
HIDDEN = 3072
TOTAL_Q = 72 * 128
TOTAL_KV = 8 * 128
LOCAL_KV_HEADS = 2
HEAD_DIM = 128
LOCAL_KV = LOCAL_KV_HEADS * HEAD_DIM
WIDTHS = tuple(range(1, 9))
REPEATS = 2
AUTHORIZATION_ROOT = Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations"
)


def die(message: str) -> None:
    raise SystemExit(f"Laguna DFlash context-KV component: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        die(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tensor_bytes(tensor: torch.Tensor) -> bytes:
    torch.xpu.synchronize()
    return tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()


def tensor_record(tensor: torch.Tensor) -> dict[str, Any]:
    raw = tensor_bytes(tensor)
    return {
        "shape": list(tensor.shape),
        "stride": list(tensor.stride()),
        "dtype": str(tensor.dtype),
        "device": str(tensor.device),
        "data_ptr": tensor.data_ptr(),
        "storage_offset": tensor.storage_offset(),
        "nbytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def assert_raw_equal(
    label: str,
    actual: torch.Tensor,
    expected: torch.Tensor,
) -> dict[str, Any]:
    require(actual.shape == expected.shape, f"{label}: shape mismatch")
    require(actual.stride() == expected.stride(), f"{label}: stride mismatch")
    torch.xpu.synchronize()
    equal = torch.equal(
        actual.contiguous().view(torch.int16),
        expected.contiguous().view(torch.int16),
    )
    actual_record = tensor_record(actual)
    expected_record = tensor_record(expected)
    require(equal, f"{label}: raw BF16 mismatch")
    require(
        actual_record["sha256"] == expected_record["sha256"],
        f"{label}: digest mismatch",
    )
    return {
        "equal": True,
        "actual": actual_record,
        "expected_sha256": expected_record["sha256"],
    }


def git_identity(root: Path, expected: str, label: str) -> None:
    commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    status = subprocess.check_output(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        text=True,
    )
    require(
        commit == expected and not status,
        f"{label} identity drift: commit={commit} dirty={bool(status)}",
    )


def validated_config() -> dict[str, Any]:
    config = json.loads(CONFIG_FILE.read_text())
    require(
        config.get("architectures") == ["DFlashLagunaForCausalLM"]
        and config.get("hidden_size") == HIDDEN
        and config.get("num_hidden_layers") == LAYERS
        and config.get("num_attention_heads") == 72
        and config.get("num_key_value_heads") == 8
        and config.get("head_dim") == HEAD_DIM
        and config.get("attention_bias") is False
        and config.get("torch_dtype") == "bfloat16"
        and config.get("layer_types") == ["sliding_attention"] * LAYERS,
        "DFlash config contract drift",
    )
    return config


def validate_device_discovery(rank: int) -> dict[str, Any]:
    completed = subprocess.run(
        ["/usr/bin/xpu-smi", "discovery", "-j"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    payload = json.loads(completed.stdout)
    observed = payload.get("device_list")
    require(isinstance(observed, list), "xpu-smi discovery schema drift")
    physical = [
        {
            "device_id": row.get("device_id"),
            "drm_device": row.get("drm_device"),
            "pci_bdf_address": row.get("pci_bdf_address"),
            "uuid": row.get("uuid"),
        }
        for row in observed
        if row.get("device_function_type") == "physical"
        and row.get("device_name") == "Intel(R) Arc(TM) Pro B70 Graphics"
    ]
    require(physical == list(DEVICES), "four-card physical mapping drift")
    require(physical[rank] == DEVICES[rank], "selected physical-card drift")
    sysfs = Path("/sys/class/drm") / Path(DEVICES[rank]["drm_device"]).name / "device"
    require(
        sysfs.resolve(strict=True).name == DEVICES[rank]["pci_bdf_address"],
        "selected DRM-to-BDF binding drift",
    )
    return {
        "mapping": physical,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
        "selected": physical[rank],
    }


def load_rank_weights(
    rank: int,
    device: torch.device,
) -> tuple[list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]], list[dict[str, Any]]]:
    layers = []
    source: list[dict[str, Any]] = []
    with safe_open(MODEL_FILE, framework="pt", device="cpu") as checkpoint:
        bias_keys = sorted(
            key
            for key in checkpoint.keys()
            if key.startswith("layers.") and key.endswith(".self_attn.qkv_proj.bias")
        )
        require(not bias_keys, "checkpoint unexpectedly contains QKV bias")
        for layer in range(LAYERS):
            qkv_name = f"layers.{layer}.self_attn.qkv_proj.weight"
            input_name = f"layers.{layer}.input_layernorm.weight"
            knorm_name = f"layers.{layer}.self_attn.k_norm.weight"
            qkv = checkpoint.get_tensor(qkv_name)
            require(
                qkv.shape == (TOTAL_Q + 2 * TOTAL_KV, HIDDEN)
                and qkv.dtype == torch.bfloat16,
                f"{qkv_name} identity drift",
            )
            q_width = TOTAL_Q // 4
            q_start = rank * q_width
            k_start = TOTAL_Q + rank * LOCAL_KV
            v_start = TOTAL_Q + TOTAL_KV + rank * LOCAL_KV
            local_q = qkv[q_start : q_start + q_width].contiguous()
            local_kv = torch.cat(
                (
                    qkv[k_start : k_start + LOCAL_KV],
                    qkv[v_start : v_start + LOCAL_KV],
                ),
                dim=0,
            ).contiguous()
            local_qkv = torch.cat((local_q, local_kv), dim=0).contiguous()
            input_norm = checkpoint.get_tensor(input_name).contiguous()
            k_norm = checkpoint.get_tensor(knorm_name).contiguous()
            require(
                input_norm.shape == (HIDDEN,)
                and k_norm.shape == (HEAD_DIM,)
                and input_norm.dtype == torch.bfloat16
                and k_norm.dtype == torch.bfloat16,
                f"layer {layer} norm identity drift",
            )
            source.append(
                {
                    "layer": layer,
                    "qkv_name": qkv_name,
                    "qkv_shape": list(qkv.shape),
                    "local_q_rows": [q_start, q_start + q_width],
                    "local_k_rows": [k_start, k_start + LOCAL_KV],
                    "local_v_rows": [v_start, v_start + LOCAL_KV],
                    "local_qkv_shape": list(local_qkv.shape),
                    "local_qkv_sha256": hashlib.sha256(
                        local_qkv.view(torch.uint8).numpy().tobytes()
                    ).hexdigest(),
                    "local_kv_sha256": hashlib.sha256(
                        local_kv.view(torch.uint8).numpy().tobytes()
                    ).hexdigest(),
                    "input_norm_name": input_name,
                    "input_norm_sha256": hashlib.sha256(
                        input_norm.view(torch.uint8).numpy().tobytes()
                    ).hexdigest(),
                    "k_norm_name": knorm_name,
                    "k_norm_sha256": hashlib.sha256(
                        k_norm.view(torch.uint8).numpy().tobytes()
                    ).hexdigest(),
                }
            )
            layers.append(
                (
                    local_qkv.to(device),
                    input_norm.to(device),
                    k_norm.to(device),
                )
            )
    return layers, source


def build_actual_context_buffers(
    layers: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    laguna_dflash: Any,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, Any]]:
    builder = laguna_dflash.DFlashLagunaModel.__new__(laguna_dflash.DFlashLagunaModel)
    nn.Module.__init__(builder)
    builder._context_kv_workspace_enabled = False
    builder._context_kv_workspaces = {}
    builder.layers = [
        SimpleNamespace(input_layernorm=SimpleNamespace(weight=input_norm))
        for _, input_norm, _ in layers
    ]
    q_width = TOTAL_Q // 4
    attentions = [
        SimpleNamespace(
            q_size=q_width,
            qkv_proj=SimpleNamespace(weight=local_qkv, bias=None),
            k_norm=SimpleNamespace(weight=k_norm),
        )
        for local_qkv, _, k_norm in layers
    ]
    builder._build_context_kv_buffers(attentions, has_bias=False)
    proof = {
        "builder": "DFlashLagunaModel._build_context_kv_buffers",
        "has_bias": False,
        "q_size": q_width,
        "kv_weights": tensor_record(builder._kv_weights),
        "input_norms": tensor_record(builder._input_layernorm_weights),
        "k_norms": tensor_record(builder._k_norm_weights),
        "layer_kv_sha256": [
            tensor_record(builder._kv_weights[layer])["sha256"]
            for layer in range(LAYERS)
        ],
        "layer_input_norm_sha256": [
            tensor_record(builder._input_layernorm_weights[layer])["sha256"]
            for layer in range(LAYERS)
        ],
        "layer_k_norm_sha256": [
            tensor_record(builder._k_norm_weights[layer])["sha256"]
            for layer in range(LAYERS)
        ],
    }
    return (
        builder._kv_weights,
        builder._input_layernorm_weights,
        builder._k_norm_weights,
        proof,
    )


def make_model(
    *,
    enabled: bool,
    kv_weights: torch.Tensor,
    input_norms: torch.Tensor,
    k_norms: torch.Tensor,
    bias: torch.Tensor | None,
    rope: Any,
    cache_impl: Any,
    device: torch.device,
    laguna_dflash: Any,
) -> Any:
    model = laguna_dflash.DFlashLagunaModel.__new__(laguna_dflash.DFlashLagunaModel)
    nn.Module.__init__(model)
    model._context_kv_workspace_enabled = enabled
    model._context_kv_workspaces = {}
    model._context_kv_projected_k_key = None
    model._kv_weights = kv_weights
    model._kv_biases = bias
    model._input_layernorm_weights = input_norms
    model._k_norm_weights = k_norms
    model._rms_norm_eps = 1e-6
    weights = [kv_weights, input_norms, k_norms]
    if bias is not None:
        weights.append(bias)
    model._context_kv_weight_signatures = (
        tuple(laguna_dflash._tensor_signature(tensor) for tensor in weights)
        if enabled
        else None
    )
    model._num_attn_layers = LAYERS
    model._kv_size = LOCAL_KV
    model._head_dim = HEAD_DIM
    model._num_kv_heads = LOCAL_KV_HEADS
    model._rope_head_size = rope.head_size
    model._rope_cos_sin_cache = rope.cos_sin_cache.to(
        device=device,
        dtype=torch.bfloat16,
    )
    model._rope_is_neox = rope.is_neox_style
    model._attn_layers = []
    for _ in range(LAYERS):
        model._attn_layers.append(
            SimpleNamespace(
                kv_cache=torch.full(
                    (4, 2, 16, 2 * HEAD_DIM),
                    -3.25,
                    dtype=torch.bfloat16,
                    device=device,
                ),
                impl=cache_impl,
                _k_scale=torch.tensor(1.0, device=device),
                _v_scale=torch.tensor(1.0, device=device),
            )
        )
    return model


def reference_boundaries(
    model: Any,
    context: torch.Tensor,
    ops: Any,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    normed = torch.empty(
        (LAYERS, context.shape[0], HIDDEN),
        dtype=torch.bfloat16,
        device=context.device,
    )
    ops.rms_norm(
        normed,
        context.unsqueeze(0).expand(LAYERS, -1, -1),
        model._input_layernorm_weights,
        model._rms_norm_eps,
    )
    flat = torch.bmm(normed, model._kv_weights.transpose(1, 2))
    if model._kv_biases is not None:
        flat += model._kv_biases[:, None, :]
    packed = (
        flat.view(LAYERS, context.shape[0], 2, LOCAL_KV_HEADS, HEAD_DIM)
        .permute(2, 0, 1, 3, 4)
        .contiguous()
    )
    k_normed = torch.empty_like(packed[0])
    ops.rms_norm(
        k_normed,
        packed[0],
        model._k_norm_weights,
        model._rms_norm_eps,
    )
    return normed, flat, packed, k_normed


def apply_rope(
    tensor: torch.Tensor,
    positions: torch.Tensor,
    model: Any,
    ops: Any,
) -> None:
    flat = tensor.view(LAYERS * positions.numel(), LOCAL_KV)
    ops.rotary_embedding(
        positions.repeat(LAYERS),
        flat,
        None,
        model._rope_head_size,
        model._rope_cos_sin_cache,
        model._rope_is_neox,
    )


def write_caches(
    model: Any,
    k: torch.Tensor,
    v: torch.Tensor,
    slots: torch.Tensor,
) -> None:
    for layer_index, layer in enumerate(model._attn_layers):
        layer.impl.do_kv_cache_update(
            layer,
            k[layer_index],
            v[layer_index],
            layer.kv_cache,
            slots,
        )


def run_branch(
    *,
    rank: int,
    branch: str,
    bias: torch.Tensor | None,
    kv_weights: torch.Tensor,
    input_norms: torch.Tensor,
    k_norms: torch.Tensor,
    rope: Any,
    cache_impl: Any,
    device: torch.device,
    laguna_dflash: Any,
    ops: Any,
) -> dict[str, Any]:
    control = make_model(
        enabled=False,
        kv_weights=kv_weights,
        input_norms=input_norms,
        k_norms=k_norms,
        bias=bias,
        rope=rope,
        cache_impl=cache_impl,
        device=device,
        laguna_dflash=laguna_dflash,
    )
    candidate = make_model(
        enabled=True,
        kv_weights=kv_weights,
        input_norms=input_norms,
        k_norms=k_norms,
        bias=bias,
        rope=rope,
        cache_impl=cache_impl,
        device=device,
        laguna_dflash=laguna_dflash,
    )
    rows: list[dict[str, Any]] = []
    saved_pointers: dict[int, list[int]] = {}
    for width in WIDTHS:
        for repeat in range(REPEATS):
            generator = torch.Generator(device=device).manual_seed(
                750000 + rank * 10000 + width * 100 + repeat
            )
            context = torch.randn(
                (width, HIDDEN),
                generator=generator,
                dtype=torch.bfloat16,
                device=device,
            )
            context_before = tensor_record(context)
            normed, flat, packed, k_normed = reference_boundaries(
                control,
                context,
                ops,
            )
            with warnings.catch_warnings(record=True) as observed_warnings:
                warnings.simplefilter("always")
                actual_k, actual_v = candidate._project_context_kv(
                    context,
                    width,
                    LAYERS,
                    LOCAL_KV_HEADS,
                    HEAD_DIM,
                )
            require(
                not observed_warnings,
                f"{branch}/C{width}/r{repeat}: candidate emitted a warning",
            )
            actual_k_normed = candidate._normalize_context_k(actual_k)
            workspace = next(
                value
                for key, value in candidate._context_kv_workspaces.items()
                if key[3] == width
            )
            workspace.validate()
            pointers = [
                workspace.normed_context_states.data_ptr(),
                workspace.all_kv_flat.data_ptr(),
                workspace.all_kv.data_ptr(),
                workspace.all_k_normed.data_ptr(),
            ]
            if width in saved_pointers:
                require(
                    pointers == saved_pointers[width],
                    f"{branch}/C{width}: workspace pointers drifted",
                )
            else:
                saved_pointers[width] = pointers
            require(
                len(set(pointers)) == 4,
                f"{branch}/C{width}: workspace buffers alias",
            )
            boundaries = {
                "normed_context": assert_raw_equal(
                    f"{branch}/C{width}/r{repeat}/normed",
                    workspace.normed_context_states,
                    normed,
                ),
                "flat": assert_raw_equal(
                    f"{branch}/C{width}/r{repeat}/flat",
                    workspace.all_kv_flat,
                    flat,
                ),
                "projected_k": assert_raw_equal(
                    f"{branch}/C{width}/r{repeat}/K",
                    actual_k,
                    packed[0],
                ),
                "projected_v": assert_raw_equal(
                    f"{branch}/C{width}/r{repeat}/V",
                    actual_v,
                    packed[1],
                ),
                "normalized_k": assert_raw_equal(
                    f"{branch}/C{width}/r{repeat}/Knorm",
                    actual_k_normed,
                    k_normed,
                ),
            }
            positions = (
                torch.arange(width, dtype=torch.int64, device=device) + 17 + repeat * 19
            )
            expected_rope = k_normed
            apply_rope(expected_rope, positions, control, ops)
            apply_rope(actual_k_normed, positions, candidate, ops)
            boundaries["rope_k"] = assert_raw_equal(
                f"{branch}/C{width}/r{repeat}/rope",
                actual_k_normed,
                expected_rope,
            )
            slots = torch.arange(
                5 + repeat * 16,
                5 + repeat * 16 + width,
                dtype=torch.int64,
                device=device,
            )
            write_caches(control, expected_rope, packed[1], slots)
            write_caches(candidate, actual_k_normed, actual_v, slots)
            cache_records = []
            for layer_index, (actual_layer, expected_layer) in enumerate(
                zip(candidate._attn_layers, control._attn_layers)
            ):
                cache_records.append(
                    assert_raw_equal(
                        f"{branch}/C{width}/r{repeat}/cache{layer_index}",
                        actual_layer.kv_cache,
                        expected_layer.kv_cache,
                    )
                )
            require(
                tensor_record(context)["sha256"] == context_before["sha256"],
                f"{branch}/C{width}/r{repeat}: context mutated",
            )
            rows.append(
                {
                    "width": width,
                    "repeat": repeat,
                    "context_sha256": context_before["sha256"],
                    "workspace_pointers": pointers,
                    "warnings": [],
                    "boundaries": boundaries,
                    "cache_layers": cache_records,
                }
            )

    existing = {
        key: tuple(value.signatures)
        for key, value in candidate._context_kv_workspaces.items()
    }
    for width in (9,):
        generator = torch.Generator(device=device).manual_seed(
            880000 + rank * 100 + width
        )
        context = torch.randn(
            (width, HIDDEN),
            generator=generator,
            dtype=torch.bfloat16,
            device=device,
        )
        expected = reference_boundaries(control, context, ops)
        actual_k, actual_v = candidate._project_context_kv(
            context,
            width,
            LAYERS,
            LOCAL_KV_HEADS,
            HEAD_DIM,
        )
        actual_knorm = candidate._normalize_context_k(actual_k)
        assert_raw_equal(f"{branch}/fallback-C{width}/K", actual_k, expected[2][0])
        assert_raw_equal(f"{branch}/fallback-C{width}/V", actual_v, expected[2][1])
        assert_raw_equal(
            f"{branch}/fallback-C{width}/Knorm",
            actual_knorm,
            expected[3],
        )
        require(
            {
                key: tuple(value.signatures)
                for key, value in candidate._context_kv_workspaces.items()
            }
            == existing,
            f"{branch}/C{width}: fallback mutated workspace registry",
        )

    return {
        "branch": branch,
        "bias": bias is not None,
        "rows": rows,
        "workspace_widths": sorted(key[3] for key in candidate._context_kv_workspaces),
        "workspace_pointers": saved_pointers,
        "fallback_widths": [9],
    }


def run_capture_rejection(
    *,
    rank: int,
    kv_weights: torch.Tensor,
    input_norms: torch.Tensor,
    k_norms: torch.Tensor,
    rope: Any,
    cache_impl: Any,
    device: torch.device,
    laguna_dflash: Any,
) -> dict[str, Any]:
    candidate = make_model(
        enabled=True,
        kv_weights=kv_weights,
        input_norms=input_norms,
        k_norms=k_norms,
        bias=None,
        rope=rope,
        cache_impl=cache_impl,
        device=device,
        laguna_dflash=laguna_dflash,
    )
    generator = torch.Generator(device=device).manual_seed(995000 + rank)
    initial_context = torch.randn(
        (1, HIDDEN),
        generator=generator,
        dtype=torch.bfloat16,
        device=device,
    )
    initial_k, _ = candidate._project_context_kv(
        initial_context,
        1,
        LAYERS,
        LOCAL_KV_HEADS,
        HEAD_DIM,
    )
    candidate._normalize_context_k(initial_k)
    workspace = next(iter(candidate._context_kv_workspaces.values()))
    workspace.validate()
    tensors = (
        workspace.normed_context_states,
        workspace.all_kv_flat,
        workspace.all_kv,
        workspace.all_k_normed,
    )
    pointers_before = [tensor.data_ptr() for tensor in tensors]
    hashes_before = [tensor_record(tensor)["sha256"] for tensor in tensors]
    cache_hashes_before = [
        tensor_record(layer.kv_cache)["sha256"] for layer in candidate._attn_layers
    ]
    capture_context = torch.randn(
        (2, HIDDEN),
        generator=generator,
        dtype=torch.bfloat16,
        device=device,
    )
    capture_context_sha256 = tensor_record(capture_context)["sha256"]
    marker = torch.ones((1,), dtype=torch.float32, device=device)
    marker.add_(0)
    torch.xpu.synchronize()
    graph = torch.xpu.XPUGraph()
    capture_true = False
    rejection_type = None
    rejection_message = None
    with torch.xpu.graph(graph):
        capture_true = bool(torch.xpu.is_current_stream_capturing())
        try:
            candidate._project_context_kv(
                capture_context,
                2,
                LAYERS,
                LOCAL_KV_HEADS,
                HEAD_DIM,
            )
        except RuntimeError as error:
            rejection_type = type(error).__name__
            rejection_message = str(error)
        marker.add_(0)
    torch.xpu.synchronize()
    require(capture_true, "capture-state API did not report true inside capture")
    require(
        rejection_type == "RuntimeError"
        and rejection_message
        == "Laguna DFlash context-KV workspace is forbidden during capture",
        "candidate did not fail closed inside capture",
    )
    require(
        sorted(key[3] for key in candidate._context_kv_workspaces) == [1],
        "capture rejection allocated a new workspace",
    )
    workspace.validate()
    pointers_after = [tensor.data_ptr() for tensor in tensors]
    hashes_after = [tensor_record(tensor)["sha256"] for tensor in tensors]
    cache_hashes_after = [
        tensor_record(layer.kv_cache)["sha256"] for layer in candidate._attn_layers
    ]
    require(
        pointers_after == pointers_before
        and hashes_after == hashes_before
        and cache_hashes_after == cache_hashes_before,
        "capture rejection mutated workspace or cache state",
    )
    require(
        tensor_record(capture_context)["sha256"] == capture_context_sha256,
        "capture rejection mutated its context input",
    )
    return {
        "eager_false_before": True,
        "capture_true": capture_true,
        "rejection_type": rejection_type,
        "rejection_message": rejection_message,
        "workspace_widths_before_after": [[1], [1]],
        "workspace_pointers_before": pointers_before,
        "workspace_pointers_after": pointers_after,
        "workspace_hashes_before": hashes_before,
        "workspace_hashes_after": hashes_after,
        "cache_hashes_before": cache_hashes_before,
        "cache_hashes_after": cache_hashes_after,
        "context_sha256_before_after": [
            capture_context_sha256,
            tensor_record(capture_context)["sha256"],
        ],
        "eager_false_after": torch.xpu.is_current_stream_capturing() is False,
    }


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
            require(written > 0, "short result write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, choices=range(4), required=True)
    parser.add_argument("--main-commit", required=True)
    parser.add_argument("--consumption-marker", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    require(
        not args.out.exists() and not args.out.is_symlink(), "fresh output required"
    )
    parent = args.out.parent
    metadata = parent.lstat()
    require(
        not parent.is_symlink()
        and stat.S_ISDIR(metadata.st_mode)
        and stat.S_IMODE(metadata.st_mode) == 0o700
        and parent.resolve(strict=True).is_relative_to(Path("/mnt/fast-ai")),
        "output parent must be owner-private internal NVMe",
    )
    require(
        os.environ.get("ONEAPI_DEVICE_SELECTOR") == "level_zero:0"
        and os.environ.get("ZE_AFFINITY_MASK") == str(args.rank),
        "one-card affinity contract drift",
    )
    require(
        os.environ.get("VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE") == "1",
        "candidate selector must be explicitly enabled",
    )
    require(
        len(args.main_commit) == 40
        and all(character in "0123456789abcdef" for character in args.main_commit),
        "main commit argument is not a full SHA",
    )
    require(
        args.consumption_marker.parent == AUTHORIZATION_ROOT
        and args.consumption_marker.is_file()
        and not args.consumption_marker.is_symlink()
        and (args.consumption_marker.stat().st_mode & 0o777) == 0o400,
        "external one-shot consumption marker drift",
    )
    consumption = json.loads(args.consumption_marker.read_text())
    require(
        consumption.get("schema") == "laguna-dflash-context-kv-component-consumption-v1"
        and consumption.get("main_commit") == args.main_commit
        and consumption.get("vllm_commit") == VLLM_COMMIT
        and consumption.get("kernel_commit") == KERNEL_COMMIT
        and consumption.get("run_root") == str(parent.parent)
        and isinstance(consumption.get("packet_sha256"), str)
        and len(consumption["packet_sha256"]) == 64,
        "external one-shot consumption contents drift",
    )
    consumption_sha256 = sha256_file(args.consumption_marker)
    git_identity(MAIN_ROOT, args.main_commit, "main")
    git_identity(VLLM_ROOT, VLLM_COMMIT, "vLLM")
    git_identity(KERNEL_ROOT, KERNEL_COMMIT, "kernel")
    require(sha256_file(MODEL_FILE) == MODEL_SHA256, "DFlash weights drift")
    require(sha256_file(CONFIG_FILE) == CONFIG_SHA256, "DFlash config drift")
    config = validated_config()
    discovery = validate_device_discovery(args.rank)
    preimport_path = parent / f"rank{args.rank}.preimport.json"
    write_exclusive(
        preimport_path,
        {
            "schema": "laguna-dflash-context-kv-preimport-v1",
            "rank": args.rank,
            "main_commit": args.main_commit,
            "vllm_commit": VLLM_COMMIT,
            "kernel_commit": KERNEL_COMMIT,
            "argv": sys.argv,
            "python_executable": sys.executable,
            "python_version": sys.version,
            "environment": {
                name: os.environ.get(name)
                for name in (
                    "ONEAPI_DEVICE_SELECTOR",
                    "ZE_AFFINITY_MASK",
                    "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE",
                    "PYTHONPATH",
                    "LD_LIBRARY_PATH",
                )
            },
            "worker_sha256": sha256_file(Path(__file__).resolve()),
            "source_sha256": {
                "vllm/envs.py": sha256_file(VLLM_ROOT / "vllm/envs.py"),
                "vllm/model_executor/models/laguna_dflash.py": sha256_file(
                    VLLM_ROOT / "vllm/model_executor/models/laguna_dflash.py"
                ),
            },
            "model_sha256": MODEL_SHA256,
            "config_sha256": CONFIG_SHA256,
            "consumption_marker": str(args.consumption_marker),
            "consumption_marker_sha256": consumption_sha256,
            "device_discovery": discovery,
            "forbidden_actions": {
                "generation": False,
                "service": False,
                "network": False,
                "timing": False,
                "submission": False,
            },
        },
    )

    global torch, safe_open, nn
    import torch
    from safetensors import safe_open
    from torch import nn
    import vllm
    import vllm_xpu_kernels
    from vllm import _custom_ops as ops
    from vllm.config import VllmConfig, set_current_vllm_config
    from vllm.model_executor.layers.rotary_embedding import get_rope
    from vllm.model_executor.models import laguna_dflash
    from vllm.v1.attention.backend import AttentionType
    from vllm.v1.attention.backends.flash_attn import FlashAttentionImpl

    require(
        Path(vllm.__file__).resolve().parents[1] == VLLM_ROOT,
        "vLLM import origin drift",
    )
    kernel_package = Path(vllm_xpu_kernels.__file__).resolve().parent
    require(
        kernel_package == (KERNEL_ROOT / "vllm_xpu_kernels").resolve(),
        "kernel import origin drift",
    )
    kernel_identity = {}
    for name, expected in KERNELS.items():
        path = kernel_package / name
        actual = sha256_file(path)
        require(actual == expected, f"kernel binary drift: {name}")
        kernel_identity[name] = actual

    require(
        torch.xpu.is_available() and torch.xpu.device_count() == 1,
        "exactly one visible XPU is required",
    )
    require(
        hasattr(torch.xpu, "is_current_stream_capturing"),
        "installed torch lacks XPU capture-state API",
    )
    torch.xpu.set_device(0)
    require(
        torch.xpu.is_current_stream_capturing() is False,
        "component must run outside stream capture",
    )
    device = torch.device("xpu:0")
    require(
        "Arc(TM) Pro B70" in torch.xpu.get_device_name(0),
        "visible torch device is not a B70",
    )
    layer_fixtures, weight_source = load_rank_weights(
        args.rank,
        device,
    )
    kv_weights, input_norms, k_norms, buffer_build_proof = build_actual_context_buffers(
        layer_fixtures, laguna_dflash
    )
    del layer_fixtures
    weight_hashes_before = {
        "kv_weights": tensor_record(kv_weights)["sha256"],
        "input_norms": tensor_record(input_norms)["sha256"],
        "k_norms": tensor_record(k_norms)["sha256"],
    }

    with set_current_vllm_config(VllmConfig()):
        rope = get_rope(
            HEAD_DIM,
            max_position=config["max_position_embeddings"],
            rope_parameters=config["rope_parameters"],
        )
    cache_impl = FlashAttentionImpl.__new__(FlashAttentionImpl)
    cache_impl.attn_type = AttentionType.DECODER
    cache_impl.head_size = HEAD_DIM
    cache_impl.kv_cache_dtype = "bfloat16"
    capture_rejection = run_capture_rejection(
        rank=args.rank,
        kv_weights=kv_weights,
        input_norms=input_norms,
        k_norms=k_norms,
        rope=rope,
        cache_impl=cache_impl,
        device=device,
        laguna_dflash=laguna_dflash,
    )
    no_bias = run_branch(
        rank=args.rank,
        branch="actual_no_bias",
        bias=None,
        kv_weights=kv_weights,
        input_norms=input_norms,
        k_norms=k_norms,
        rope=rope,
        cache_impl=cache_impl,
        device=device,
        laguna_dflash=laguna_dflash,
        ops=ops,
    )
    bias_generator = torch.Generator(device=device).manual_seed(990000 + args.rank)
    synthetic_bias = torch.randn(
        (LAYERS, 2 * LOCAL_KV),
        generator=bias_generator,
        dtype=torch.bfloat16,
        device=device,
    )
    synthetic_bias_sha256 = tensor_record(synthetic_bias)["sha256"]
    with_bias = run_branch(
        rank=args.rank,
        branch="synthetic_bias",
        bias=synthetic_bias,
        kv_weights=kv_weights,
        input_norms=input_norms,
        k_norms=k_norms,
        rope=rope,
        cache_impl=cache_impl,
        device=device,
        laguna_dflash=laguna_dflash,
        ops=ops,
    )
    weight_hashes_after = {
        "kv_weights": tensor_record(kv_weights)["sha256"],
        "input_norms": tensor_record(input_norms)["sha256"],
        "k_norms": tensor_record(k_norms)["sha256"],
    }
    require(weight_hashes_after == weight_hashes_before, "static weights mutated")
    require(
        tensor_record(synthetic_bias)["sha256"] == synthetic_bias_sha256,
        "synthetic bias mutated",
    )
    require(
        torch.xpu.is_current_stream_capturing() is False,
        "capture state changed during component",
    )

    result = {
        "schema": "laguna-dflash-context-kv-component-v1",
        "status": "exact_component_pass",
        "rank": args.rank,
        "non_timing": True,
        "generation": False,
        "service": False,
        "network": False,
        "submission": False,
        "visible_xpus": torch.xpu.device_count(),
        "device_name": torch.xpu.get_device_name(0),
        "device_discovery": discovery,
        "main_commit": args.main_commit,
        "preimport_path": str(preimport_path),
        "preimport_sha256": sha256_file(preimport_path),
        "capture_api": {
            "present": True,
            "eager_before": False,
            "eager_after": False,
        },
        "capture_rejection": capture_rejection,
        "consumption_marker": str(args.consumption_marker),
        "consumption_marker_sha256": consumption_sha256,
        "vllm_root": str(VLLM_ROOT),
        "vllm_commit": VLLM_COMMIT,
        "kernel_root": str(KERNEL_ROOT),
        "kernel_commit": KERNEL_COMMIT,
        "kernel_identity": kernel_identity,
        "model_root": str(MODEL_ROOT),
        "model_sha256": MODEL_SHA256,
        "config_sha256": CONFIG_SHA256,
        "weight_source": weight_source,
        "checkpoint_qkv_bias_keys": [],
        "buffer_build_proof": buffer_build_proof,
        "weight_hashes_before": weight_hashes_before,
        "weight_hashes_after": weight_hashes_after,
        "synthetic_bias_sha256": synthetic_bias_sha256,
        "branches": [no_bias, with_bias],
        "required_widths": list(WIDTHS),
        "repeats": REPEATS,
    }
    write_exclusive(args.out, result)
    print(json.dumps({"status": result["status"], "rank": args.rank}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
