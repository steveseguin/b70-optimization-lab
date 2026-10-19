# Full-shape CPU microbenchmark

Implemented, source-bound research harness: `analyze.py`, `cpu.cpp`,
`build_engine.py`. No GGUF or model payload is opened. The active ten experts
occupy full 640×2560 matrices in both streams; the other 502 expert banks are
not read or allocated. Native kernels retain `experts=512`, and invalid routes
are rejected before any address is consumed. This is full operation geometry
with synthetic data, not a real-weight or end-to-end model check.

Reproduce, one command at a time from the repository root:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/analyze.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/build_engine.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/audit.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/test_audit.py </dev/null
```

The build driver serializes through **ops/compile_turn.py**, holds the turn
through the full-shape synthetic reads/execution, enforces 4 GiB address space
and a 27 GB CPU disk floor, and uses no device compiler mode/API. The protected
whole-host timing window gate applies. Before a new run, preserve existing
receipts in a new attempt folder; the listed commands overwrite local generated
CPU evidence. Do not run full-shape preparation while a one-card timing window
owns the host. Resource caps belong to this CPU entry only.

GNU and Intel each use `-O2 -fno-fast-math -ffp-contract=off`, no fast-math/FMA
substitution. The compiler-generated dependency lists bind the actual production
include closure in `evidence/cpu-proof.json`. Comparison uses `memcmp` for FP32
and exact vector equality for BF16, never floating equality or tolerance.

Fixtures 0/1 are finite, with both execution orders. Fixture 2 adds BF16 signed
zeros/subnormals, infinities and NaNs. Weight scales remain finite, as required
by production repack admission; signed zero, subnormal and maximum finite
half-scale patterns are included. No nonfinite-weight admission rule changes.
The raw chain check runs 409,600 FP32 words per fixture, then checks 12,800
BF16 values. A separate call to the **actual native host kernel classes**
compares complete output/status/error with valid and invalid/tail routes.

Timing is a CPU diagnostic alongside quality, not a gate or Xe forecast.
Preserve both failing and passing byte results. The standalone native proof
exits 2 for mismatches; the driver records that research outcome rather than
aborting before the second compiler. Its `passed` field remains false.
`audit.py` succeeds when the closed packet and its pins are consistent; that
audit success must never be reported as CPU candidate qualification.

For a future revision, add a second fresh invocation per compiler and a
same-build device-define CPU preparation-path probe before READY. The current
implementations already fail the first strict check, so no repeat or device
build was spent trying to obtain a passing fixture.
