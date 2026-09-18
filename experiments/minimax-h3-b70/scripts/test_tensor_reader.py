#!/usr/bin/env python3
"""The pread tensor reader returns exactly what `safe_open(...).get_tensor(...)` returns.

    /mnt/fast-ai/venvs/minimax-h3-cpu/bin/python test_tensor_reader.py

CPU only, no GPU, no watchdog needed: the largest file this touches is a few MB (the ConvRot
rotation is 64 KiB; a VAE shard, if present, is read one small tensor at a time and anything over
`MAX_REAL_TENSOR_BYTES` is skipped).  It never opens the 27 GB encoder or the 40 GB denoiser.

Why it exists
-------------
`B70_H3_LOADER=pread` (the default since 2026-09-18) replaces `safetensors.safe_open` in both load
loops of `run_h3_t2v.py`, because a `safe_open` handle keeps the whole file mapped and RssFile
therefore grows with every byte touched (sessions 6/7: 6.29-6.35 GiB at a 6 GiB budget, a NO-GO
against the < 6 GiB rule in `notes/2026-09-18-first-light-plan.md`).  A loader swap is only
allowed to change *where the bytes live*, never *what the bytes are*, so that is what this checks:
`torch.equal`, bitwise, on every tensor of a synthetic file covering the dtypes both checkpoints
use (BF16 / F16 / F32 / I8 / U8 / BOOL / I64), on leading-row slices (the qkv split and the SwiGLU
half swap are row slices), and on real safetensors files on disk.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile

import torch
from safetensors import safe_open
from safetensors.torch import save_file

HERE = pathlib.Path(__file__).resolve().parent
MAX_REAL_TENSOR_BYTES = 64 * 2**20
REAL_FILES = [
    HERE.parent / "data" / "convrot-hadamard-256.safetensors",
    pathlib.Path("/mnt/fast-ai/llm-models/minimax-h3/vae/diffusion_pytorch_model-00001-of-00003.safetensors"),
]


def load_runner():
    spec = importlib.util.spec_from_file_location("run_h3_t2v", HERE / "run_h3_t2v.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_h3_t2v"] = module
    spec.loader.exec_module(module)
    return module


rt = load_runner()

FAILURES: list[str] = []


def check(ok: bool, what: str) -> None:
    print(f"  {'ok   ' if ok else 'FAIL '} {what}")
    if not ok:
        FAILURES.append(what)


def make_synthetic(path: pathlib.Path) -> dict:
    """Every dtype the two checkpoints use, plus a scalar, a 1-row tensor and an odd row count."""
    g = torch.Generator().manual_seed(20260918)
    tensors = {
        "bf16.2d": (torch.randn(37, 5, generator=g) * 7).to(torch.bfloat16),
        "bf16.qkv_like": (torch.randn(24, 8, generator=g)).to(torch.bfloat16),
        "f16.2d": (torch.randn(6, 4, generator=g)).to(torch.float16),
        "f32.1d": torch.randn(13, generator=g),
        "f32.scalar": torch.tensor(3.14159, dtype=torch.float32),
        "i8.2d": torch.randint(-128, 127, (256, 256), generator=g, dtype=torch.int8),
        "u8.2d": torch.randint(0, 255, (9, 3), generator=g, dtype=torch.uint8),
        "bool.1d": torch.tensor([True, False, True, True, False]),
        "i64.2d": torch.randint(-(2**40), 2**40, (5, 3), generator=g, dtype=torch.int64),
        "bf16.onerow": (torch.randn(1, 16, generator=g)).to(torch.bfloat16),
    }
    save_file(tensors, str(path))
    return tensors


def compare_file(path: pathlib.Path, keys: list[str] | None = None, label: str = "") -> None:
    """Every tensor of `path`, pread vs safe_open, bitwise."""
    header = rt.read_header(path)
    keys = keys if keys is not None else list(header)
    with safe_open(str(path), framework="pt") as ref, rt.PreadTensorReader(path) as got:
        for key in keys:
            want = ref.get_tensor(key)
            have = got.get_tensor(key)
            same = (have.dtype == want.dtype and tuple(have.shape) == tuple(want.shape)
                    and torch.equal(have, want))
            check(same, f"{label}{key} {tuple(want.shape)} {want.dtype}")
            got.release(key)  # must not disturb anything, and must not raise


def test_synthetic(tmp: pathlib.Path) -> None:
    path = tmp / "synthetic.safetensors"
    tensors = make_synthetic(path)

    print("synthetic file, every tensor, pread vs safe_open:")
    compare_file(path)

    print("synthetic file, values also match what was saved:")
    with rt.PreadTensorReader(path) as reader:
        for key, want in tensors.items():
            check(torch.equal(reader.get_tensor(key), want), f"{key} round-trips")

    print("leading-row slices (the qkv split / SwiGLU half swap read these):")
    with safe_open(str(path), framework="pt") as ref, rt.PreadTensorReader(path) as got:
        for key, rows in (("bf16.2d", (0, 37)), ("bf16.2d", (5, 31)), ("bf16.qkv_like", (0, 8)),
                          ("bf16.qkv_like", (8, 16)), ("bf16.qkv_like", (16, 24)),
                          ("i8.2d", (128, 256)), ("i64.2d", (2, 5)), ("bf16.onerow", (0, 1))):
            want = ref.get_tensor(key)[rows[0] : rows[1]]
            have = got.get_tensor(key, rows)
            check(have.dtype == want.dtype and tuple(have.shape) == tuple(want.shape)
                  and torch.equal(have, want), f"{key}[{rows[0]}:{rows[1]}]")
            got.release(key, rows)

    print("the SwiGLU half swap, end to end, both loaders:")
    with rt.PreadTensorReader(path) as got, rt.MmapTensorReader(path) as mm:
        for reader, name in ((got, "pread"), (mm, "mmap")):
            t = reader.get_tensor("bf16.qkv_like")
            half = t.shape[0] // 2
            swapped = torch.cat((t[half:], t[:half]), dim=0)
            want = tensors["bf16.qkv_like"]
            wanted = torch.cat((want[half:], want[:half]), dim=0)
            check(torch.equal(swapped, wanted), f"{name} half swap")

    print("the mmap reader is still the safe_open path:")
    with safe_open(str(path), framework="pt") as ref, rt.MmapTensorReader(path) as mm:
        for key in tensors:
            check(torch.equal(mm.get_tensor(key), ref.get_tensor(key)), f"mmap {key}")
        check(torch.equal(mm.get_tensor("i8.2d", (0, 128)), ref.get_tensor("i8.2d")[0:128]),
              "mmap i8.2d[0:128]")

    print("the two readers agree with each other:")
    with rt.PreadTensorReader(path) as a, rt.MmapTensorReader(path) as b:
        check(all(torch.equal(a.get_tensor(k), b.get_tensor(k)) for k in tensors),
              "pread == mmap on every synthetic tensor")
        check(a.keys() == b.keys() == list(rt.read_header(path)), "same key order as the header")

    print("open_tensor_reader picks the loader:")
    check(rt.LOADER == "pread", "B70_H3_LOADER defaults to pread")
    with rt.open_tensor_reader(path) as r:
        check(isinstance(r, rt.PreadTensorReader), "default -> PreadTensorReader")
    with rt.open_tensor_reader(path, loader="mmap") as r:
        check(isinstance(r, rt.MmapTensorReader), "loader='mmap' -> MmapTensorReader")
    try:
        rt.open_tensor_reader(path, loader="nonsense")
    except ValueError:
        check(True, "an unknown loader name raises")
    else:
        check(False, "an unknown loader name raises")

    print("the header's data start is where the tensors really are:")
    header, data_start = rt.read_header_and_data_start(path)
    raw = path.read_bytes()
    entry = header["i8.2d"]
    begin, end = entry["data_offsets"]
    check(raw[data_start + begin : data_start + end]
          == tensors["i8.2d"].numpy().tobytes(), "i8.2d bytes sit at data_start + data_offsets")


def test_real_files() -> None:
    for path in REAL_FILES:
        if not path.exists():
            print(f"real file (skipped, not on this host): {path}")
            continue
        header = rt.read_header(path)
        keys = [k for k in header if rt.tensor_bytes(header[k]) <= MAX_REAL_TENSOR_BYTES][:8]
        total = sum(rt.tensor_bytes(header[k]) for k in keys)
        print(f"real file: {path.name}, {len(keys)} tensors, {total / 2**20:.1f} MiB read")
        compare_file(path, keys, label=f"{path.name}: ")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="h3-tensor-reader-") as tmp:
        test_synthetic(pathlib.Path(tmp))
    test_real_files()
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s)")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all checks passed: the pread reader is bitwise identical to safe_open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
