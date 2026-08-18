# Qwen3.8 AutoRound: fused residual/RMSNorm/INT4 gate-up triage

Date: 2026-08-18  
Status: source-reviewed candidate; not built or benchmarked in this lane

## Candidate

The Qwen3.6 ledger left one structural candidate unfinished: fuse the repeated

```text
residual add -> post-attention RMSNorm -> dense gate_up W4A16
```

boundary. The source lead is Intel `llm-scaler` commit
[`db05b45831a5a534b74510797832dcf9b3c7e7ab`](https://github.com/intel/llm-scaler/commit/db05b45831a5a534b74510797832dcf9b3c7e7ab),
`resadd_norm_gemv_int4.h`.

That commit is important for correctness, not just speed. Its original fused
kernel let one workgroup update the residual while later workgroups still read
it. At large output width this changed `h + r_old` into `h + (h + r_old)` for
some rows. The fix uses a single-workgroup residual/RMSNorm prepass followed by
a pure GEMV-from-normalized-input kernel whenever `N > 512`.

The historical Qwen3.6 plan required at least `0.04 ms/layer` saved before
integration. Across 64 layers that threshold is material, so the mechanism is
worth retaining for Qwen3.8 AutoRound rather than rediscovering it.

## Why the Intel kernel is not directly usable

The current Qwen3.8 TP2/MTP3 hot verifier has local gate-up shape approximately
`M=4, K=5120, N=17408`. Intel's repaired path is a one-row GEMV:

- it accepts one hidden/residual row and emits one output row;
- it assumes FP16 scale storage;
- it expects output-major packed weights and output-major group scales;
- its tests use a CPU Q4_0-style packer, not the checkpoint's complete
  AutoRound load/repack path;
- its large-`N` repair deliberately becomes two kernel submissions.

The AutoRound path physically repacks qweight output-major before exposing a
transposed view to oneDNN, so the packed weight bytes may be reusable after an
exact nibble/zero-point proof. The checkpoint's gate/up scales are FP16 with
shape `[K/group, N]`; the ESIMD kernel expects the physical equivalent of
`[N, K/group]`. A separate immutable prepacked scale buffer is therefore
required; silently reinterpreting the current tensor is invalid.

Calling the one-row kernel four times is not presumed faster than the current
oneDNN M=4 GEMM. The candidate must first become a real M=4 implementation or
win a representative four-call microbenchmark. No endpoint build is justified
before that test.

## Required proof order

1. Reconstruct the pinned Qwen3.8 AutoRound runtime and preserve the accepted
   path unchanged as the control.
2. Extract one real layer's post-load qweight, qzeros, scales, RMSNorm weight,
   hidden rows, and residual rows. Prove the candidate's unpacking, zero point,
   scale dtype/layout, residual update, normalized output, and GEMM output
   against the existing oneDNN path. Random-weight relative-error tests are not
   sufficient.
3. Microbenchmark exactly `M=4, K=5120, N=17408` after warmup. Include all
   prepass, launch, layout, and dependency costs. Stop unless the median saves
   at least `0.04 ms/layer` in both run orders.
4. Run at least 512 replays with alternating input buffers under the same graph
   capture mode. Require stable complete outputs, unchanged residuals versus
   the accepted arithmetic policy, no NaNs, and no Xe reset/fault.
5. Integrate behind one default-off environment gate and a shape/dtype/layout
   fail-closed check. Never route other layers or checkpoints by inference.
6. Run same-binary control/candidate pairs, the 25 cold prompts with both
   all-25 and selection-12 metrics, cache-zero checks, a matching B replicate,
   and the new Qwen3.8 target-only quality oracle.

## Safety and classification

This note records an untested idea, not a result or a performance claim. The
15 GiB replay host must not compile the AOT extension while a model is loaded
and must not run this candidate until the reference host supplies a measured
low-RAM procedure. The built-in TP2 profiler and unsafe remote-write prototype
remain prohibited.

Do not substitute Intel's original pre-fix kernel or use its `N <= 512`
all-workgroups-resident assumption at Qwen's large `N`. Do not weaken weights,
KV precision, the deterministic sampler, target verification, or quality gates
to make this candidate appear faster.
