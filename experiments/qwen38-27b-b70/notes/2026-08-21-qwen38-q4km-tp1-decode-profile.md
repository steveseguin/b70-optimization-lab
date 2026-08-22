# Qwen3.8 Q4_K_M TP1 decode profile and next-rung attribution

Date: 2026-08-21

Status: **diagnostic attribution only; no timing here is promotable.** Taken
with the fork's built-in per-node event profiler (`GGML_SYCL_PROFILE=1`,
barrier cost measured and excluded, 3-graph warmup skip). The profiler
disables the runtime fusion doors, so this is the stock-path decomposition of
the current lane build; the profiled run itself decodes at ~20.3 tok/s and
must never be quoted as a rate.

## Decode step decomposition (n_tokens=1, 296 graphs)

- Host wall 42.56 ms/graph, device span 99.8% of wall, instrument barrier
  cost 113.8 us/graph (0.3%), unattributed 0.
- `MUL_MAT` is 86.5% of node time (36.63 ms, 497 calls/graph, 498.7 GB/s
  blended on the profiler's ideal-traffic model, 610 GB/s roofline note).
- Everything else (~5.7 ms unfused) is the population the three landed
  widenings already fuse: GET_ROWS 1.64, CONCAT 0.66, UNARY 0.56, CPY 0.52,
  GDN 0.44, FA 0.43, ROPE 0.40, GLU 0.39, MUL 0.25, SSM_CONV 0.25 ms.

Largest MUL_MAT roles (per graph):

| Role | Type | Calls | us/call | GB/s | Excess vs 610 GB/s |
|---|---|---:|---:|---:|---:|
| ffn_gate [17408, k=5120] | q4_K | 64 | 98.2 | 511 | ~0.4 ms |
| ffn_out [5120, k=17408] | q4_K | 64 | 98.0 | 512 | ~1.25 ms |
| ffn_up [17408, k=5120] | q4_K | 64 | 91.4 | 549 | ~0 (at kernel ceiling) |
| z [6144, k=5120] | q8_0 | 48 | 87.7 | **381.7** | ~1.6 ms |
| linear_attn_out [5120] | q8_0 | 48 | 67.5 | 496 | ~1.1 ms |
| Qcur_full [12288] | q8_0 | 16 | 125.2 | 534 | ~0.25 ms |
| result_output [248320] | q6_K | 1 | 1741.0 | **599.6** | ~0 (at roofline) |
| qkv-conv in_proj [10240] | q8_0 | 48 x 1 | 102.5 | 543 | ~0.5 ms |

Total mid-size MMVQ excess versus the 610 GB/s roofline is on the order of
5 ms/token — larger than the whole remaining gap to 30 tok/s.

## Findings

1. **`GGML_SYCL_MMVQ_PHASE=1` is a dead lever on B70 for these shapes**: a
   forced-on diagnostic profile left `z` at 381.5 GB/s and every other row
   flat. The door's PVC-only auto-arm is correct; no reason to consider its
   output-order change here. (Two profiled runs, same protocol.)
2. **Standalone shape probes** (test-backend-ops perf additions, committed in
   the lane tree): m>=10240 q8_0 rows stream at ~581 GB/s standalone versus
   ~535-543 in-graph — a ~7% in-graph tax consistent with the per-call
   activation-quant launches that execute inside each MUL_MAT node window.
   Small/mid standalone rows (m<=6144) are L2-contaminated by weight reuse in
   the bench (938-1483 apparent GB/s) and cannot arbitrate the `z` question;
   a cold-weight rotation harness would be needed.
3. **`z` [6144, k=5120] q8_0 at 381.7 GB/s in-graph is the single worst
   large row** (30% below its 10240-row sibling with identical type, k, and
   kernel). Cause not yet identified (not chunk-walk phase). Open.
4. **Quantize launches hide inside MUL_MAT windows**: ~240 activation-Q8
   quantizations per graph remain after dedup (`quantize_launches` /
   `graph_computes`). The Q4_K fused gate/up/SwiGLU path emits f32, so all
   64 `ffn_out` consumers re-quantize; the Q8 lane's producer-side Q8
   emission (`GGML_SYCL_FUSED_SWIGLU_Q8`) never engages on the Q4K route
   (`fused_swiglu=0`).

## Next rungs, ranked

1. Extend the fused Q4_K gate/up/SwiGLU kernel to optionally emit the Q8_1
   activation directly (same quantization arithmetic as the standalone
   quantize kernel, door-gated, exact), killing the 64 largest per-graph
   quant launches. Precedent: the accepted Q8-lane producer doors.
2. Chase the remaining in-graph-vs-standalone streaming tax on big rows
   (quant/dispatch bubbles in the in-order queue).
3. Resolve the `z` 381 GB/s anomaly with a cold-weight standalone harness
   before touching kernel geometry.
4. Clock floor (2650-2800 MHz droop under decode, up to ~4%) stays parked
   pending explicit governance approval.
