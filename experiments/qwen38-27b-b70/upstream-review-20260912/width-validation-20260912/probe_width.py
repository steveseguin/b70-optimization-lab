#!/usr/bin/env python3
"""Explicit XPU microprobe; parent must perform preflight before running.

No model or server. One process loads one isolated stock OR candidate library.
Compare outputs, z, conv history, every SSM row after width3->2->3 transitions.
"""

import argparse
import json
from pathlib import Path
import torch
from reference import ref_gdn_attention_spec


def validate_uniform_offsets(offsets, total, capacity):
    lengths = [b - a for a, b in zip(offsets, offsets[1:])]
    if not lengths or offsets[0] != 0 or offsets[-1] != total:
        raise ValueError("invalid query offsets")
    if len(set(lengths)) != 1 or not 0 < lengths[0] <= capacity:
        raise ValueError("ragged/empty/over-capacity speculative width")
    return lengths[0]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--library", type=Path)
    p.add_argument("--arm", choices=["stock", "candidate"])
    p.add_argument("--dtype", choices=["float16", "bfloat16"], default="float16")
    p.add_argument("--cpu-contract-only", action="store_true")
    args = p.parse_args()
    for off in ([0, 1, 4], [0, 3, 4], [0, 0, 4]):
        try:
            validate_uniform_offsets(off, 4, 3)
        except ValueError:
            continue
        raise AssertionError("ragged contract accepted")
    assert validate_uniform_offsets([0, 2, 4], 4, 3) == 2
    if args.cpu_contract_only:
        print(
            "PASS: ragged lengths [1,3],[3,1],[0,4] rejected by harness; no device initialized"
        )
        return
    if args.library is None or args.arm is None:
        p.error("--library and --arm required for XPU")
    torch.ops.load_library(str(args.library))
    dtype = getattr(torch, args.dtype)
    device = "xpu:0"
    torch.manual_seed(7429)
    # Same head dims and ratio as upstream tests, small physical cache (12MiB).
    nh, nv, d, batch, cap, width, slots = 16, 32, 128, 2, 3, 4, 12
    qkv = (2 * nh + nv) * d

    def rand(*shape):
        return torch.randn(*shape, dtype=dtype, device=device) * 0.5

    conv = rand(slots, width - 2 + cap, qkv)
    ssm = rand(slots, nv, d, d)
    rc, rs = conv.clone(), ssm.clone()
    weights, bias = rand(qkv, width), rand(qkv)
    alog = rand(nv).float()
    dt = rand(nv)
    idx = torch.arange(batch * cap, dtype=torch.int32, device=device).reshape(
        batch, cap
    )
    results = []
    # Prior acceptance3 while shrinking exercises column2/row2 input history.
    for step, (active, accepted_values) in enumerate(
        [(3, [0, 1]), (2, [3, 2]), (3, [2, 1])]
    ):
        total = batch * active
        offsets = list(range(0, total + 1, active))
        validate_uniform_offsets(offsets, total, cap)
        query = torch.tensor(offsets, dtype=torch.int32, device=device)
        tokens = torch.randperm(total, device=device).to(torch.int32)
        accepted = torch.tensor(accepted_values, dtype=torch.int32, device=device)
        states = rand(total, (2 * nh + 2 * nv) * d)
        ba = rand(total, 2 * nv)
        out = torch.zeros(total, nv, d, dtype=dtype, device=device)
        z = torch.zeros_like(out)
        rout, rz = torch.zeros_like(out), torch.zeros_like(out)
        ssm_before = ssm.clone()
        try:
            intermediate = torch.ops.width_review.conv(
                z,
                states,
                ba,
                nh,
                nv,
                d,
                d,
                conv,
                weights,
                bias,
                "silu",
                0,
                0,
                batch,
                query,
                tokens,
                idx,
                accepted,
                total,
                1,
                True,
            )
            torch.ops.width_review.delta(
                out,
                *intermediate,
                nv,
                d,
                alog,
                dt,
                ssm,
                0,
                0,
                batch,
                query,
                tokens,
                idx,
                accepted,
                total,
                1,
            )
            torch.xpu.synchronize()
        except RuntimeError as exc:
            if args.arm == "stock" and active < cap and "spec_token" in str(exc):
                results.append(
                    {
                        "step": step,
                        "active_width": active,
                        "expected_stock_rejection": str(exc),
                    }
                )
                print(json.dumps(results, indent=2))
                return
            raise
        ref_gdn_attention_spec(
            rout,
            rz,
            states,
            ba,
            nh,
            nv,
            d,
            d,
            rc,
            rs,
            weights,
            bias,
            "silu",
            alog,
            dt,
            batch,
            query,
            tokens,
            idx,
            accepted,
            total,
            1,
            True,
        )
        touched = set(range(active)) | set(range(cap, cap + active))
        untouched = [slot for slot in range(slots) if slot not in touched]
        assert torch.equal(ssm[untouched], ssm_before[untouched]), (
            "untouched SSM slots changed"
        )
        checks = {}
        for name, actual, expected in [
            ("output", out, rout),
            ("z", z, rz),
            ("conv", conv, rc),
            ("ssm", ssm, rs),
        ]:
            assert torch.isfinite(actual).all(), name
            max_error = float((actual.float() - expected.float()).abs().max())
            # Explicit numerical screening tolerance; require exact cache writes for conv/z.
            torch.testing.assert_close(
                actual,
                expected,
                rtol=0 if name in ["conv", "z"] else 0.02,
                atol=0 if name in ["conv", "z"] else 0.02,
            )
            metric_actual = actual[sorted(touched)] if name == "ssm" else actual
            metric_expected = expected[sorted(touched)] if name == "ssm" else expected
            ref_norm = float(torch.linalg.vector_norm(metric_expected.float()))
            error_norm = float(
                torch.linalg.vector_norm(
                    metric_actual.float() - metric_expected.float()
                )
            )
            relative_l2 = error_norm / max(ref_norm, 1e-30)
            if name in ["output", "ssm"]:
                assert ref_norm > 0 and relative_l2 <= (
                    0.005 if dtype == torch.float16 else 0.02
                ), (
                    name,
                    ref_norm,
                    relative_l2,
                )
            checks[name] = {
                "reference_l2": ref_norm,
                "relative_l2_error": relative_l2,
                "max_abs_error": max_error,
                "exact": bool(torch.equal(actual, expected)),
            }
        results.append(
            {
                "step": step,
                "active_width": active,
                "accepted": accepted_values,
                "checks": checks,
            }
        )
    if args.arm == "stock":
        raise AssertionError("stock unexpectedly accepted reduced width")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
