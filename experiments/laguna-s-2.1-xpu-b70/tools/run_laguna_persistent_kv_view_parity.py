#!/usr/bin/env python3
"""Non-timing, one-card q2..q8 FA2 parity packet for persistent KV views."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import torch

VLLM_ROOT = Path("/home/steve/src/laguna-vllm-runtime-graph-20260724")
VLLM_COMMIT = "5da4a8ccdde0abe77d2dd2abda7b6a12bc74c01a"
KERNEL_ROOT = Path("/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727")
KERNEL_COMMIT = "4772f727590c51b72add79350b913d098cf67872"
KERNELS = {
    "_C.abi3.so": "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2",
    "_xpu_C.abi3.so": "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8",
    "_moe_C.abi3.so": "6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b",
    "libgrouped_gemm_xe_2.so": (
        "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96"
    ),
}
ATTENTION_CASES = {
    "full": {"query_heads": 12, "window_size": None},
    "sliding": {"query_heads": 18, "window_size": (511, 0)},
}
Q_WIDTHS = tuple(range(2, 9))
NUM_PAGES = 16
KV_LENGTH = 577


def die(message: str) -> None:
    raise SystemExit(f"Laguna persistent KV-view parity: {message}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tensor_sha256(tensor: torch.Tensor) -> str:
    raw = tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


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
    if commit != expected or status:
        die(f"{label} source identity drift: commit={commit} dirty={bool(status)}")


def write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        0o600,
    )
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                die("short parity-record write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, choices=range(4), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.out.exists() or args.out.is_symlink():
        die("fresh output is required")
    parent = args.out.parent
    metadata = parent.lstat()
    if (
        parent.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or not parent.resolve(strict=True).is_relative_to(Path("/mnt/fast-ai"))
    ):
        die("output parent must be an owner-private internal-NVMe directory")
    if os.environ.get("ONEAPI_DEVICE_SELECTOR") != "level_zero:0":
        die("ONEAPI_DEVICE_SELECTOR must expose one post-affinity device")
    if os.environ.get("ZE_AFFINITY_MASK") != str(args.rank):
        die("physical-card affinity drift")

    import vllm
    import vllm_xpu_kernels
    from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func
    from vllm.v1.attention.backend import AttentionType
    from vllm.v1.attention.backends.flash_attn import FlashAttentionImpl

    if Path(vllm.__file__).resolve().parents[1] != VLLM_ROOT:
        die("vLLM import origin drift")
    git_identity(VLLM_ROOT, VLLM_COMMIT, "vLLM")
    git_identity(KERNEL_ROOT, KERNEL_COMMIT, "kernel")
    kernel_package = Path(vllm_xpu_kernels.__file__).resolve().parent
    if kernel_package != (KERNEL_ROOT / "vllm_xpu_kernels").resolve():
        die("kernel import origin drift")
    kernel_identity = {}
    for name, expected in KERNELS.items():
        path = kernel_package / name
        actual = sha256_file(path)
        if actual != expected:
            die(f"kernel binary drift: {name}")
        kernel_identity[name] = {"path": str(path), "sha256": actual}

    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        die(
            "exactly one visible XPU is required: "
            f"available={torch.xpu.is_available()} count={torch.xpu.device_count()}"
        )
    torch.xpu.set_device(0)
    device = torch.device("xpu:0")
    generator = torch.Generator(device=device).manual_seed(70100 + args.rank)
    combined_cache = torch.randn(
        (NUM_PAGES, 2, 64, 256),
        device=device,
        dtype=torch.bfloat16,
        generator=generator,
    )
    rows: list[dict[str, Any]] = []
    for case_index, (case, config) in enumerate(ATTENTION_CASES.items()):
        impl_args = {
            "num_heads": config["query_heads"],
            "head_size": 128,
            "scale": 1 / (128**0.5),
            "num_kv_heads": 2,
            "alibi_slopes": None,
            "sliding_window": 512 if case == "sliding" else None,
            "kv_cache_dtype": "bfloat16",
            "attn_type": AttentionType.DECODER,
        }
        os.environ["VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS"] = "0"
        control_impl = FlashAttentionImpl(**impl_args)
        os.environ["VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS"] = "1"
        candidate_impl = FlashAttentionImpl(**impl_args)
        if control_impl._xpu_persistent_kv_cache_views is not None:
            die(f"{case} selector-off path unexpectedly created persistent state")
        if candidate_impl._xpu_persistent_kv_cache_views is None:
            die(f"{case} selector-on path did not create persistent state")
        control = control_impl._get_kv_cache_views_for_forward(combined_cache)
        candidate = candidate_impl._get_kv_cache_views_for_forward(combined_cache)
        repeated = candidate_impl._get_kv_cache_views_for_forward(combined_cache)
        if not all(left is right for left, right in zip(candidate, repeated)):
            die(f"{case} selector-on views did not retain object identity")
        control_version = control_impl.vllm_flash_attn_version
        candidate_version = candidate_impl.vllm_flash_attn_version
        if (
            control_version is None
            or candidate_version is None
            or control_version != candidate_version
        ):
            die(f"{case} selector paths disagree on FlashAttention version")

        for q_width in Q_WIDTHS:
            query_generator = torch.Generator(device=device).manual_seed(
                90000 + args.rank * 1000 + case_index * 100 + q_width
            )
            query = torch.randn(
                (q_width, config["query_heads"], 128),
                device=device,
                dtype=torch.bfloat16,
                generator=query_generator,
            )
            cu_seqlens_q = torch.arange(
                q_width + 1,
                device=device,
                dtype=torch.int32,
            )
            seqused_k = (
                KV_LENGTH
                - q_width
                + torch.arange(
                    1,
                    q_width + 1,
                    device=device,
                    dtype=torch.int32,
                )
            )
            block_table = (
                torch.arange(
                    NUM_PAGES,
                    device=device,
                    dtype=torch.int32,
                )
                .expand(q_width, -1)
                .contiguous()
            )
            outputs = []
            for impl, (key_cache, value_cache) in (
                (control_impl, control),
                (candidate_impl, candidate),
            ):
                output = torch.empty_like(query)
                flash_attn_varlen_func(
                    q=query,
                    k=key_cache,
                    v=value_cache,
                    out=output,
                    cu_seqlens_q=cu_seqlens_q,
                    max_seqlen_q=1,
                    seqused_k=seqused_k,
                    max_seqlen_k=KV_LENGTH,
                    softmax_scale=impl.scale,
                    causal=False,
                    alibi_slopes=None,
                    window_size=config["window_size"],
                    block_table=block_table,
                    softcap=0.0,
                    scheduler_metadata=None,
                    fa_version=impl.vllm_flash_attn_version,
                    q_descale=None,
                    k_descale=None,
                    v_descale=None,
                    num_splits=0,
                    s_aux=None,
                )
                outputs.append(output)
            torch.xpu.synchronize()
            control_output, candidate_output = outputs
            control_hash = tensor_sha256(control_output)
            candidate_hash = tensor_sha256(candidate_output)
            equal = torch.equal(control_output, candidate_output)
            if not equal or control_hash != candidate_hash:
                die(f"{case} q={q_width} output mismatch")
            rows.append(
                {
                    "case": case,
                    "q": q_width,
                    "bitwise_equal": equal,
                    "control_sha256": control_hash,
                    "candidate_sha256": candidate_hash,
                    "control_fa_version": control_version,
                    "candidate_fa_version": candidate_version,
                }
            )

    write_exclusive(
        args.out,
        {
            "schema": "laguna-persistent-kv-view-attention-parity-v1",
            "status": "pass",
            "rank": args.rank,
            "device_name": torch.xpu.get_device_name(0),
            "visible_xpus": torch.xpu.device_count(),
            "vllm_root": str(VLLM_ROOT),
            "vllm_commit": VLLM_COMMIT,
            "kernel_root": str(KERNEL_ROOT),
            "kernel_commit": KERNEL_COMMIT,
            "kernel_identity": kernel_identity,
            "control_selector": 0,
            "candidate_selector": 1,
            "control_state_absent": True,
            "candidate_state_present": True,
            "candidate_view_identity_reused": True,
            "non_timing": True,
            "q_outputs": rows,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
