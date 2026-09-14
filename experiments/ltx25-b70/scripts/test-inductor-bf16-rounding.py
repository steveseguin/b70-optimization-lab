#!/usr/bin/env python3
"""CPU-only, tiny pointwise numerics screen; not an LTX or XPU qualification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    # Process-local compiler limits. No server or machine settings are changed.
    os.environ["TORCHINDUCTOR_COMPILE_THREADS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    with tempfile.TemporaryDirectory(prefix="ltx-cpu-rounding-") as cache:
        os.environ["TORCHINDUCTOR_CACHE_DIR"] = cache
        os.environ["TRITON_CACHE_DIR"] = str(Path(cache) / "triton")
        import torch
        import torch._inductor.config as config

        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True, warn_only=False)

        def pointwise(x, shift, scale, denominator):
            # Representative BF16 pointwise boundaries, not the full LTX block.
            return ((x + shift) * scale) / denominator

        common = {
            "compile_threads": 1,
            "triton.cudagraphs": False,
            "max_autotune": False,
            "max_autotune_gemm": False,
        }
        report = {
            "scope": "CPU BF16 add/multiply/divide chain only; no LTX, XPU, or speed claim",
            "torch": torch.__version__,
            "config_path": config.__file__,
            "config_sha256": hashlib.sha256(Path(config.__file__).read_bytes()).hexdigest(),
            "fullgraph": True,
            "dynamic": False,
            "guard_filter": None,
            "rows": [],
        }
        for arm, preserve in (("default_rounding", False), ("preserve_rounding", True)):
            options = {**common, "emulate_precision_casts": preserve,
                       "eager_numerics.division_rounding": preserve}
            compiled = torch.compile(pointwise, backend="inductor", options=options,
                                     fullgraph=True, dynamic=False)
            for shape in ((1, 16, 64), (1, 64, 64)):
                for seed in (17, 42, 123):
                    generator = torch.Generator(device="cpu").manual_seed(seed)
                    values = [torch.randn(shape, generator=generator, device="cpu",
                                          dtype=torch.bfloat16) for _ in range(4)]
                    values[3] = values[3].abs() + 0.25
                    expected = pointwise(*values)
                    actual = compiled(*values)
                    repeat = compiled(*values)
                    exact = torch.equal(expected.view(torch.uint8), actual.view(torch.uint8))
                    replay_exact = torch.equal(actual.view(torch.uint8), repeat.view(torch.uint8))
                    row = {"arm": arm, "shape": list(shape), "seed": seed,
                           "options": options, "exact_eager": exact,
                           "exact_repeat": replay_exact,
                           "finite": bool(torch.isfinite(actual).all()),
                           "unequal_values": int((expected != actual).sum()),
                           "max_abs_diff": float((expected.float() - actual.float()).abs().max())}
                    report["rows"].append(row)
            torch._dynamo.reset()
        report["preserve_rounding_passed"] = all(
            r["exact_eager"] and r["exact_repeat"] and r["finite"]
            for r in report["rows"] if r["arm"] == "preserve_rounding")
        report["default_rounding_mismatch_observed"] = any(
            not r["exact_eager"] for r in report["rows"] if r["arm"] == "default_rounding")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(json.dumps({k: report[k] for k in (
            "scope", "preserve_rounding_passed", "default_rounding_mismatch_observed")}))
        if not report["preserve_rounding_passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
