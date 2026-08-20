# Runtime nondeterminism FOUND: oneDNN INT4 GEMM M-band + fix built and op-gated

Date: 2026-08-20
Status: source identified at op level; fix built and gated on this host;
server-side determinism A/B (margin-free, shared cache) is measuring-host
work. THIS UNBLOCKS the determinism gate if the server confirms it.

## The finding

Responding to MARGIN_WAS_MASKING_RUNTIME_NONDETERMINISM_20260820 (~1 argmax
flip per ~3100 tokens, margin-free, shared compile cache, oneDNN aids ON),
this host ran per-op bitwise self-determinism sweeps at production MTP5 TP2
shapes (`scripts/qwen38-op-determinism-bisect.py`, 1000 calls, identical
inputs):

| op | shape | result |
|---|---|---|
| int4_gemm_w4a16 | M=6, [5120x1408] | 0/1000 mismatches |
| int4_gemm_w4a16 | **M=341, [5120x1408]** | **1000/1000 mismatches, max_abs_diff 0.25** |
| int4_gemm_w4a16 | M=6/M=1, [5120x8704] | 0/1000 |
| int8_gemm_w8a8 head | M=6/M=1 | 0/1000 |
| gdn_attention_spec_decode | M=6, persistent, state restored per call | 0/1000 |
| TP allreduce/allgather | 400 collectives, cross-process checksums | bitwise equal |

So: decode-width ops are all deterministic; the oneDNN INT4 GEMM is
nondeterministic **per invocation** in a specific M band. Band mapping
(`data/2026-08-20-int4-gemm-nondeterministic-m-band.json`, production aids
VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER=1 + INPUT_DEPENDENCY=1 ON, still
dirty — the barrier is a stream-ordering aid, not numerics):

- qkv [5120x1408]: dirty M in [129, 448]; clean M<=128, M>=449 (spot-checked
  to 2048)
- down [8704x5120]: dirty M in [129, 248]; clean M>=257
- gate_up [5120x8704]: clean everywhere

Decode GEMMs (verifier M=6, draft M=1) never enter the band. **Prefill
does**: any prompt whose chunked-prefill GEMM lands at 129<=M<512 gets a
raced prefill; the perturbation (max_abs_diff ~0.25 fp16 per layer,
compounding over 64 layers) flips argmax only at near-ties — consistent
with the observed ~4 late-diverging prompts out of 25 and the ~1/3100 flip
rate.

## The fix: determinism pad (built + gated here)

`patches/vllm-xpu-kernels-qwen38-onednn-int4-determinism-pad-20260820.patch`
(int4_gemm_w4a16.h): for 128 < M < 512, pad src to M=512 with zeros, run,
slice back. GEMM rows are independent — proven bitwise: real-row outputs
identical under arbitrary padding content (including x100-magnitude junk),
and padded M=512 execution bitwise-stable over 500 runs.

Default ON; `VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD=0` opts out. Prefill-only
cost; decode widths never take the branch.

**Combined candidate build** (zero-init scratch + determinism pad), staged
at `/home/steve/staged-xpu-detpad-20260820/`:
- `_xpu_C.abi3.so` sha256
  `d756c96082438141b13521541cf94d1de4330a9cab89b727227248226253edce`
- `libgdn_attn_kernels_xe_2.so` bit-identical to pinned manifest
  (`c194e28d…`)

Gate results on the combined build
(`data/2026-08-20-op-determinism-bisect-combined-build.json`):
- M-sweep 10/10 widths clean (256 and 341: 0/200, were 200/200)
- full bisect: every op 0/1000; `any_nondeterministic: false`
- side benefit: padded M=341 GEMM is 155 µs vs 271 µs for the native dirty
  kernel — the deterministic path is also *faster* at this shape
- decode perf untouched: M=6 gate_up 45.7 µs (pinned: 46.2)
- zero-init lever intact: persistent lane 34.2 µs burst, delta 9.0 µs/call
  vs ephemeral (`data/2026-08-20-gdn-scratch-combined-build.json`)

## Caveats / next steps (measuring host)

1. The op-level sweep covers the named candidates only. If a margin-free
   server arm with this build still diverges, the next suspects are the FA
   prefill/decode kernels and batch-composition-dependent paths — the same
   sweep harness extends to them.
2. Other int4 shapes in the model (o_proj [5120x5120], draft head) were not
   band-mapped; the pad rule covers 128<M<512 for ALL int4 GEMMs, so they
   are handled, but their clean/dirty boundaries are unmeasured.
3. Server validation design: margin-free, PERSISTENT_SCRATCH=1, this
   combined build, shared compile cache, two arms, require 25/25 token-ID
   identity. If clean, rerun fresh-compile arms to re-test compilation
   determinism on top.
4. The pad adds one D2D copy + a larger GEMM for in-band prefill chunks
   (e.g. 341->512 rows). Prefill throughput impact is bounded and partly
   offset by the faster clean kernel; measure TTFT on the strict suite.

## Full decode-path audit (2026-08-20, this host)

`data/2026-08-20-decode-path-determinism-audit.json`; sweep scripts under
`scripts/qwen38-det-*.py`. **Every decode-path op is bitwise deterministic
and batch/row-invariant**: int4 GEMM M=1..6 (0 mismatches, row0 M=6 vs M=1
bitwise equal), draft head M=1..6, int8 head M=1..837, FA decode at kv
84..2047 (row-invariant: row 5 packed vs solo bitwise equal), FA prefill at
the divergent prompt lengths, GDN spec op M=6 persistent with state
restore, TP collectives cross-process. Also: all five int4 shape classes
clean at M=48..128.

**The int4 band explains at most 1 of the 4 divergent prompts** (only
holdout--structured-extraction at 187 tokens lands in the band; 49/71-token
prompts are below every measured band; the 837-token prompt is above).
At least one more runtime nondeterminism source exists. Named suspects, in
order: (a) GDN chunk prefill — UNSWEPT, standalone Triton compile fails on
this host (`PassManager::run` in make_ttir); sweep it server-side or fix
the standalone env; (b) the replayssm spec-state ops
(commit_pending/copy_slots/stage_conv) — unswept; (c) cross-request history
dependence (baseline JSON notes the same prompt is identical in a 2-prompt
suite but diverges in the 25-prompt run).
