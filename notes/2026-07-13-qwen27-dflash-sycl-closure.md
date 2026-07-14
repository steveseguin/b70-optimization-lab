# Qwen3.6 27B Q4_0 DFlash/SYCL closure

Date: 2026-07-13

Status: **closed as the active optimization lane**. The requested performance
objectives were not reached. Preserve the lane as a measured research packet;
do not resume it with generic configuration sweeps or launch-count-only fusion.

## Objective and final result

The objective was a single active generation at:

- at least `100 tok/s` on one Intel Arc Pro B70; and
- at least `200 tok/s` using up to four B70s, never aggregate throughput.

The final policy-compliant result for the primary one-B70 Q4_0/DFlash lane is:

- `47.818818 tok/s` median for generated tokens 1-100 after TTFT;
- p10 `39.869534`, mean `46.638647`;
- 12 unique cold realistic prompts, `cached_tokens=0` throughout;
- unchanged Q4_0 target with target-verified native DFlash5;
- llama.cpp base `e3546c794` plus the preserved local SYCL stack; and
- LocalMaxxing approval `cmrjbx8bc02g8mj01yzz2v701`.

The matching AOT control was `44.2205 tok/s`, so the final fused Q6_K draft
LM-head/top-1 boundary delivered a real `+8.14%` end-to-end gain. This record is
documented in
[`experiments/qwen27-dflash-sycl-b70/notes/2026-07-13-q6k-m6-fused-top1-production-record.md`](../experiments/qwen27-dflash-sycl-b70/notes/2026-07-13-q6k-m6-fused-top1-production-record.md).

Favorable code prompts reached about `74 tok/s` with high DFlash acceptance,
but the strict mixed suite did not. That workload-specific observation is not
the product result and must not be substituted for it. The separate vLLM
AutoRound TP2 lane reached `95.384868 tok/s`, but it is a different target,
quantization/runtime identity and still missed the requested 200 tok/s
single-session objective.

## What materially worked

1. **The DFlash failure was isolated correctly.** Native DFlash initially
   appeared unusable because Q8_0 draft KV collapsed acceptance. F16 draft KV
   restored `94.3%` acceptance on the controlled favorable prompt while Flash
   Attention remained enabled. The important lesson is to test speculative KV
   precision independently before rejecting the draft model or attention
   implementation.
2. **The hidden MMVQ dispatch fallback was fixed.** Extending direct Q4_0 MMVQ
   coverage through rows 9-17 removed repeated full-weight reads and made the
   remaining target-verifier cost measurable rather than mysterious.
3. **Real target-verifier work moved throughput.** Offline-packed Xe2 width-6
   gate/up and down projections, then GDN snapshot-cache commit, advanced the
   strict DFlash path from `39.249` to `42.641` to `44.255 tok/s`.
4. **A high-value semantic boundary beat generic fusion.** Fusing the Q6_K
   draft vocabulary projection with exact raw-greedy top-1 eliminated full
   logit materialization/readback and produced the final `47.819 tok/s` record.
5. **Hot-loadable AOT modules improved iteration.** The Q6 production kernel
   was reproduced in the small module with exact output and roughly `142x`
   faster rebuild iteration than relinking the complete SYCL backend.
6. **The benchmark discipline held.** Same-window AOT controls, strict cold
   prompts, exact identities, fail-closed dispatches, and LocalMaxxing only
   after the final gate prevented diagnostic numbers from becoming records.

## Why the objectives were missed

The final limitation was not one unexplained `13 ms` framework bucket.
Measured speculative-cycle economics showed several coupled constraints:

- Native DFlash5 spent roughly `58.7 ms` in width-6 target verification,
  `10.0 ms` in draft decode/sampling, `1.0 ms` in feature injection, and up to
  `1.2 ms` in acceptance/commit. Target verification dominated.
- MTP3 emitted only `2.788` tokens/cycle at `59.64%` proposal acceptance. Its
  target verifier was `45.646 ms` of a `56.848 ms` accounted cycle. Removing
  all draft overhead alone would still have reached only about `59 tok/s`.
- DFlash acceptance was strongly workload-dependent. Long accepted runs on
  code did not transfer to the fixed mixed suite.
- Production Q4_0 vector MMVQ was stronger than early microbenchmarks implied.
  Several proposed DPAS kernels looked good only against controls that reread
  weights per row. Against the exact production reordered kernel, critical
  M=4 shapes failed the required speedup.
- Packing faster formats consumed scarce VRAM. The unfinished Q5_K GDN output
  pack needs about `1.516 GiB`; the QKVZAB pack needs about `2.11 GiB`. Both do
  not safely coexist with the model and a 2 GiB reserve.
- Intel BMG AOT device linking remained slow, making full-backend iteration
  expensive even after four-GPU experimental parallelism.

The key engineering mistake to avoid repeating is equating fewer launches with
a faster critical path. Several fusions enlarged kernels, raised register or
transcendental cost, or simply moved work without removing a target weight
read. End-to-end AOT crossover—not launch count—must decide promotion.

## Closed or negative paths

- Persistent executable graph replay achieved deterministic direct reuse but
  did not improve strict no-spec throughput.
- MMVQ plus residual saved about `0.3 ms` and failed the 3% MTP gate.
- GDN output epilogue was neutral; moving sigmoid/softplus raw-gate work into
  GDN regressed strict MTP3 by `6.67%`.
- GDN output-to-Q8 improved only `1.00%`; combining convolution cache regressed
  `1.10%`; QK normalization was neutral.
- Device-resident MTP staging was correct but reached only `50.164 tok/s`.
- Policy sweeps topped out near `50.895 tok/s`; a hindsight per-prompt oracle
  was only `52.245 tok/s`.
- The target Q6 M=6 fused head reduced target decode by about `0.55 ms` and
  improved a short crossover by only `1.6%`, below the promotion gate.
- The down-to-next-RMS/Q8 boundary had a generous ceiling of only `1.403 ms`.
- Global DFlash is rejected for this identity; it remains only a routed,
  workload-specific concept.

## Preserved unfinished work

These items are implementation artifacts, **not measured wins**:

- GDN QKVZAB plus folded gate has exact isolated hot-module evidence and a
  projected `2.328 ms`/48-layer saving. Production matcher/integration compiled
  through host objects and BMG AOT linking but was not run end to end. See the
  [unverified integration handoff](../experiments/qwen27-dflash-sycl-b70/notes/2026-07-13-gdn-qkvzab-production-integration-unverified.md)
  and its scoped patch.
- The Q5_K GDN output DPAS/XMX hot module and offline pack ABI compile. Its
  roofline opportunity is over `4 ms` for all 48 layers, but it has not been
  compared against the real production fixture or integrated. See the
  [compile-only handoff](../experiments/qwen27-dflash-sycl-b70/notes/2026-07-13-xe2-m6-q5k-gdn-output-compile-handoff.md).
- Exact Q4 DFlash target-trace capture passes synthetic/native ABI and
  corruption tests. No real model trace or adapted draft was produced. See the
  [trace closeout](../experiments/qwen27-dflash-sycl-b70/notes/2026-07-13-exact-q4-native-trace-closeout.md).

The protected source remains `/home/steve/src/llama.cpp` at base
`e3546c7948e3af463d0b401e6421d5a4c2faf565`. It is intentionally dirty and
must not be reset or cleaned. At closure, its tracked binary diff SHA-256 was
`bee7b62a0aeda711f4ef9d3ff4b102b87c11908b4b67539960be34a4edfe553f`;
untracked files are listed by its Git status and preserved separately where
needed. The old Qwen benchmark server on localhost port 19443 was stopped; the
public `:8000` service was not touched.

## Transfer to DeepSeek and future lanes

Carry these rules forward:

1. Lock model revision, quantization, graph mode, KV precision, runtime commit,
   suite, and cache identity before comparing speed.
2. Build an exact cycle timeline before choosing kernels. Optimize milliseconds
   per complete emitted-token cycle, not a favorable GEMV roofline.
3. Compare new kernels against the exact production path, including packing,
   activation quantization, reductions, and reuse. A weak control creates a
   false verifier win.
4. Use hot-loadable modules and captured real tensors before production
   integration. Compile only the narrow candidate during search.
5. Rank persistent packs by measured milliseconds saved per GiB and retain a
   device-memory reserve.
6. Treat speculative acceptance as a model-, prompt-, KV-, and width-dependent
   variable. Measure the fixed suite before investing in a broad integration.
7. Preserve raw bit representations when pack formats contain `ggml_fp16_t`;
   numerical conversion of storage objects caused an all-zero kernel failure.
8. Require a meaningful end-to-end gate (normally at least 3%) before paying
   for a full strict suite or expanding a fusion family.

DeepSeek should start with fit and architecture viability, then a strict clean
baseline and cycle decomposition. Do not copy the Qwen fused decoder wholesale:
MoE routing, attention/cache layout, expert residency, and collectives will
change the dominant economics.

## Reopening gate

Reopen this Qwen lane only with one of the following concrete changes:

- a substantially better compatible draft on the fixed mixed suite;
- a target format that materially reduces weights while preserving the desired
  quality class;
- a production-correct small-M verifier expected to save multiple milliseconds
  after packing/quantization overhead; or
- a device-unrolled speculative executor with a measured path below roughly
  `30 ms` per useful cycle.

Do not reopen it for flag sweeps, generic graph experiments, isolated launch
count reductions, or favorable-prompt-only DFlash results.
