# NEGATIVE: fused resadd/RMSNorm/INT4 gate-up fails its own go/no-go at M=4 TP2

Date: 2026-08-19
Status: measured negative result; candidate closed without building the kernel

The triage note
(2026-08-18-autoround-fused-resadd-rmsnorm-int4-triage.md) requires a median
saving of at least **0.04 ms/layer** at M=4, K=5120, N=17408 before any
integration work. The most the fusion can remove is the separate
residual-add + RMSNorm device time plus the extra pass over x and launches —
the INT4 GEMM stays either way. Measuring exactly that share kills the
candidate before the ESIMD kernel is written.

## Measurement

Script: `experiments/qwen38-27b-b70/scripts/fusion-gonogo-microbench.py`
Data: `experiments/qwen38-27b-b70/data/2026-08-19-fusion-gonogo-microbench.json`

Real layer-0 checkpoint gate/up weights (fixture v1), TP2 rank-0 local
shards, XPU graph capture + 100-replay bursts so numbers are device time in
the production PIECEWISE-graph regime (eager numbers, kept for context, are
launch-bound). The GEMM leg is an fp16 dequantized proxy reading 4x the
production int4 bytes — it overestimates GEMM time but NOT the fusible
share, which is GEMM-independent. (The prebuilt auto_round_kernel wheel
lacks BMG-G31 joint_matrix support on this host, so the production woqgemm
could not be timed here; it does not change the verdict.)

| region | device us/layer |
|---|---|
| graph: add + RMSNorm chain | 24.86 |
| graph: gate_up GEMM (fp16 proxy) | 324.34 |
| graph: full boundary | 356.24 |
| **fusible share (full − GEMM)** | **31.90** |

31.9 µs/layer < 40 µs/layer threshold → **NO-GO**, before accounting for the
fused kernel's own prepass, layout, and dependency costs, which can only
shrink the saving. The true production share is likely smaller still: the
reference RMSNorm here is an unfused fp32 chain, while production runs a
single batch-invariant RMSNorm kernel.

Do not write the M=4 fused ESIMD kernel for this lane. If the shape regime
changes materially (e.g. wider verifier M or a measured multi-kernel
RMSNorm), re-run this script before reconsidering.

## Residual value

The fixture + CPU exactness proofs (fixture v1, 2026-08-18) remain valid and
reusable for any future weight-layout question. The bounded-microbenchmark
method (systemd user scope + XPUGraph bursts on the 15 GiB host, no model
load) is now the established safe way to do kernel-level go/no-go here.
