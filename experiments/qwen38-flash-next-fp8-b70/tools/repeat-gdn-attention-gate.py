#!/usr/bin/env python3
"""Fixed-input repeatability gate for the staged XPU GDN core operator.

Calls ``torch.ops._xpu_C.gdn_attention`` from the staged runtime exactly as
``vllm/_xpu_ops.py`` does for Qwen3.8 Flash-Next at TP4 (4 key heads, 12
value heads, 128-dim heads, conv width 4 per rank, ``reorder_input=True``)
and checks that byte-identical inputs give byte-identical outputs and cache
states across repeats. Every case restores the same initial conv/ssm state
before each repeat, so any hash spread is kernel non-repeatability.

Cases (single sequence, cache slot 1):

- ``prefill8``: one 8-token prefill chunk from zero state (the depth-8 probe
  shape; XE2 chunk path with padding).
- ``prefill64_state``: one 64-token chunk from a non-zero initial state
  (every later chunked-prefill step).
- ``chunked2048``: 32 sequential 64-token chunks from zero state, hashing
  each chunk output and the final states (the 2048-token prompt).
- ``decode1``: one decode token from a non-zero state (native launcher).
- ``decode128``: 128 sequential decode tokens carrying state.

The gate refuses to run beside a model server. Run it twice in fresh
processes and compare the per-case hashes for cross-process repeatability.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
import time

import torch

TP = 4
NUM_K_HEADS = 16
NUM_V_HEADS = 48
HEAD_K = 128
HEAD_V = 128
CONV_WIDTH = 4
KH = NUM_K_HEADS // TP
VH = NUM_V_HEADS // TP
QKVZ_WIDTH = KH * (2 * HEAD_K + 2 * HEAD_V * (NUM_V_HEADS // NUM_K_HEADS))
BA_WIDTH = KH * (2 * (NUM_V_HEADS // NUM_K_HEADS))
CONV_DIM = KH * (2 * HEAD_K + HEAD_V * (NUM_V_HEADS // NUM_K_HEADS))
CACHE_SLOTS = 4
SLOT = 1
CASES = ("prefill8", "prefill64_state", "chunked2048", "decode1", "decode128")


def refuse_active_model_server() -> None:
    out = subprocess.run(
        ["pgrep", "-af", "vllm serve|VLLM::|EngineCore"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    me = {str(os.getpid()), str(os.getppid())}
    rows = [
        line
        for line in out.splitlines()
        if line.split(maxsplit=1)[0] not in me and "pgrep" not in line
    ]
    if rows:
        print("FAIL: a model server is active; refusing to share the GPUs", file=sys.stderr)
        for row in rows[:5]:
            print("  " + row[:160], file=sys.stderr)
        sys.exit(3)


def sha(*tensors: torch.Tensor) -> str:
    h = hashlib.sha256()
    for t in tensors:
        h.update(t.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes())
    return h.hexdigest()


class Fixture:
    def __init__(self, seed: int, device: torch.device) -> None:
        g = torch.Generator(device="cpu").manual_seed(seed)
        self.device = device

        def bf(*shape: int, scale: float = 1.0) -> torch.Tensor:
            return (torch.randn(*shape, generator=g) * scale).to(torch.bfloat16).to(device)

        self.qkvz = bf(2048, QKVZ_WIDTH)
        self.ba = bf(2048, BA_WIDTH)
        self.conv_weights = bf(CONV_DIM, CONV_WIDTH, scale=0.3)
        self.conv_bias = bf(CONV_DIM, scale=0.1)
        self.A_log = torch.log(
            torch.rand(VH, generator=g) * 15 + 1
        ).to(torch.float32).to(device)
        self.dt_bias = bf(VH, scale=0.1)
        self.conv_state_init = bf(CACHE_SLOTS, CONV_WIDTH - 1, CONV_DIM, scale=0.5)
        self.ssm_state_init = bf(CACHE_SLOTS, VH, HEAD_V, HEAD_K, scale=0.1)

    def states(self, zero: bool) -> tuple[torch.Tensor, torch.Tensor]:
        if zero:
            return (
                torch.zeros_like(self.conv_state_init),
                torch.zeros_like(self.ssm_state_init),
            )
        return self.conv_state_init.clone(), self.ssm_state_init.clone()

    def step(
        self,
        qkvz: torch.Tensor,
        ba: torch.Tensor,
        conv_state: torch.Tensor,
        ssm_state: torch.Tensor,
        *,
        num_prefills: int,
        num_decodes: int,
        has_initial_state: bool,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        tokens = qkvz.shape[0]
        out = torch.zeros((tokens, VH, HEAD_V), dtype=torch.bfloat16, device=self.device)
        z = torch.zeros_like(out)
        torch.ops._xpu_C.gdn_attention(
            out,
            z,
            qkvz.contiguous(),
            ba.contiguous(),
            NUM_K_HEADS,
            NUM_V_HEADS,
            HEAD_K,
            HEAD_V,
            conv_state,
            ssm_state,
            self.conv_weights,
            self.conv_bias,
            "silu",
            self.A_log,
            self.dt_bias,
            num_prefills,
            num_decodes,
            torch.tensor([has_initial_state], dtype=torch.bool, device=self.device),
            torch.tensor([0, tokens], dtype=torch.int32, device=self.device),
            torch.tensor([SLOT], dtype=torch.int32, device=self.device),
            tokens,
            TP,
            True,
        )
        return out, z


def run_case(fx: Fixture, case: str) -> tuple[str, float]:
    h = hashlib.sha256()
    max_abs = 0.0

    def absorb(out: torch.Tensor, z: torch.Tensor) -> None:
        nonlocal max_abs
        h.update(sha(out, z).encode())
        max_abs = max(max_abs, float(out.float().abs().max()))

    if case == "prefill8":
        conv, ssm = fx.states(zero=True)
        out, z = fx.step(fx.qkvz[:8], fx.ba[:8], conv, ssm, num_prefills=1, num_decodes=0, has_initial_state=False)
        torch.xpu.synchronize()
        absorb(out, z)
    elif case == "prefill64_state":
        conv, ssm = fx.states(zero=False)
        out, z = fx.step(fx.qkvz[64:128], fx.ba[64:128], conv, ssm, num_prefills=1, num_decodes=0, has_initial_state=True)
        torch.xpu.synchronize()
        absorb(out, z)
    elif case == "chunked2048":
        conv, ssm = fx.states(zero=True)
        for i in range(32):
            sl = slice(64 * i, 64 * (i + 1))
            out, z = fx.step(fx.qkvz[sl], fx.ba[sl], conv, ssm, num_prefills=1, num_decodes=0, has_initial_state=i > 0)
            torch.xpu.synchronize()
            absorb(out, z)
    elif case == "decode1":
        conv, ssm = fx.states(zero=False)
        out, z = fx.step(fx.qkvz[100:101], fx.ba[100:101], conv, ssm, num_prefills=0, num_decodes=1, has_initial_state=True)
        torch.xpu.synchronize()
        absorb(out, z)
    elif case == "decode128":
        conv, ssm = fx.states(zero=False)
        for i in range(128):
            out, z = fx.step(fx.qkvz[200 + i : 201 + i], fx.ba[200 + i : 201 + i], conv, ssm, num_prefills=0, num_decodes=1, has_initial_state=True)
            torch.xpu.synchronize()
            absorb(out, z)
    else:
        raise ValueError(case)
    h.update(sha(conv[SLOT], ssm[SLOT]).encode())
    return h.hexdigest(), max_abs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=50)
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--out", required=True)
    parser.add_argument("--allow-server", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 1000:
        raise ValueError("repeats must be between 1 and 1000")
    cases = [c for c in args.cases.split(",") if c]
    for c in cases:
        if c not in CASES:
            raise ValueError(f"unknown case {c}")
    if not args.allow_server:
        refuse_active_model_server()

    module = importlib.import_module("vllm_xpu_kernels._xpu_C")
    device = torch.device("xpu:0")
    torch.xpu.set_device(device)
    fx = Fixture(args.seed, device)

    report: dict[str, object] = {
        "schema_version": 1,
        "pid": os.getpid(),
        "kernel_module": module.__file__,
        "device_name": torch.xpu.get_device_name(0),
        "seed": args.seed,
        "repeats": args.repeats,
        "shapes": {
            "tp": TP,
            "k_heads_per_rank": KH,
            "v_heads_per_rank": VH,
            "qkvz_width": QKVZ_WIDTH,
            "ba_width": BA_WIDTH,
            "conv_dim": CONV_DIM,
            "conv_width": CONV_WIDTH,
        },
        "cases": {},
    }
    ok = True
    with torch.inference_mode():
        for case in cases:
            hashes: list[str] = []
            max_abs = 0.0
            t0 = time.monotonic()
            for _ in range(args.repeats):
                digest, m = run_case(fx, case)
                hashes.append(digest)
                max_abs = max(max_abs, m)
            unique = sorted(set(hashes))
            row = {
                "repeats": args.repeats,
                "unique_hashes": len(unique),
                "hash_first": hashes[0],
                "hashes_unique": unique[:8],
                "max_abs_out": max_abs,
                "finite": max_abs == max_abs and max_abs != float("inf"),
                "seconds": round(time.monotonic() - t0, 3),
            }
            report["cases"][case] = row  # type: ignore[index]
            print(
                f"{case}: unique={len(unique)}/{args.repeats} first={hashes[0][:16]} "
                f"max_abs={max_abs:.4g} {row['seconds']}s",
                flush=True,
            )
            ok = ok and len(unique) == 1 and row["finite"]
    report["all_cases_repeatable_in_process"] = ok
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(("PASS" if ok else "FAIL") + f": in-process repeatability, receipt {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
