# Qwen3.8 27B Q8 reordered-weight prefetch

Date: 2026-08-17

Status: **active; claimed on the reference ASRock host**

## Hypothesis

The accepted Q8 reordered row body demand-loads one aligned 16-byte weight
vector per lane and then executes the exact DP4A/FP32 accumulation work for
that iteration. The earlier two-iteration operand-preload experiment moved the
next ordinary load into registers but did not issue a device cache prefetch.
Intel oneAPI 2026.1 exposes an in-kernel prefetch primitive with cache-level
hints, so a bounds-checked prefetch of the next row chunk may overlap B70 HBM
latency without increasing the live DP4A operand set.

The treatment must cover every accepted reordered-Q8 decode family:

- standalone MMVQ, including the down projection and output head;
- fused gate/up pair;
- fused attention Q/V/K triple;
- fused recurrent QKV/Z/alpha/beta quad.

Each lane will prefetch only its next aligned 16-byte weight vector, only when
that next chunk remains within the same row. Actual loads, Q8 scale reads,
DP4A order, FP32 accumulation order, subgroup reduction, tensor split, model,
F16 KV, and target-only execution remain unchanged.

## Gate

Use a default-off runtime door and a same-binary off/on smoke first. Require
the expected dispatch marker on both B70s and `VERIFY_MISMATCH=0`. If the arm
is live and safe, compare candidate-off against the promoted binary to exclude
codegen drift, then use fully position-complemented fresh-process decode
screens. Endpoint and semantic gates are allowed only for a repeatable gain.

The existing transferred PVC note that prefetch was null does not close this
arm: it measured a different architecture and kernel geometry. Do not run this
exact BMG-G31 all-family treatment on another host while the claim is active.
