# Full187 joint gate/up plus down independent audit

Date: 2026-07-13 UTC

## Audit outcome

The promoted full187 AOT row is a valid matching-identity improvement over the
prior gate/up-only AOT row. The retained server log proves one B70, one active
generation, Q4_0 target, Q8_0 target KV, native Q8 DFlash5 with F16 draft KV,
flash attention on, graphs off, and all fusion flags other than the guarded Xe2
M=6 path off. It packed and dispatched all 187 intended mirrors: 130 gate/up
and 57 Q4_0 down tensors. The fixed 12-prompt cold gate passed with every cache
count zero.

The promoted AOT result is `42.6410014044 tok/s` median tokens 1-100 after
TTFT, `37.0118154027` p10, and `42.9565985106` mean. The JIT support row is
`45.4843644309`, `36.9368191904`, and `43.1351360212` respectively. The
headline median difference must not be interpreted as an AOT kernel
regression: p10 and mean are essentially equal, and the exact cycle accounting
below shows AOT is slightly faster per speculative cycle. Different
accumulation order changed some greedy branches and therefore acceptance and
the discrete number of cycles used by individual prompts.

## Exact current cycle economics

The AOT server log provides per-request target-generation time, cumulative
DFlash cycle counts, accepted-token counts, and cumulative draft duration.
Differencing all 12 requests gives:

- 556 speculative cycles and 963 accepted draft tokens;
- `2.732014` emitted tokens per speculative cycle from `1 + accepted/cycles`;
- `35,895.000 ms` aggregate target-generation time;
- `64.559353 ms` weighted end-to-end cycle time;
- `9.348189 ms` weighted DFlash draft generation/sampling time;
- `55.211164 ms` weighted remainder for target verification, feature/state
  work, acceptance/commit, host coordination, and untimed gaps;
- per-request median cycle `64.466 ms`, median draft `9.352 ms`, and median
  remainder `55.001 ms`.

The analogous JIT totals are 552 cycles, 966 accepted tokens, `2.750000`
emitted/cycle, `65.556558 ms` weighted cycle, and `9.461382 ms` draft. The JIT
first request contains a cold outlier; the per-request median cycle is about
`64.85 ms`. AOT is therefore about 0.6% faster at the median cycle boundary.

These totals are exact host/cycle evidence, but the latest full187 run did not
enable `GGML_SYCL_CYCLE_TIMING`; the `55.21 ms` remainder must not be relabeled
as an exact target-device time. The immediately preceding synchronized
gate/up-only trace measured about `54.2 ms` for the target graph, roughly
`0.39 ms` and `0.27 ms` for the two small state/feature graphs, and about
`7.9 ms` for the draft graph. A fresh full187 cycle-timed AOT run is required
to measure how much of the new strict win is target-device time versus changed
acceptance and host gaps.

At current mixed-suite acceptance, 100 tok/s requires a `27.32 ms` cycle, a
`37.24 ms` reduction. Even perfect DFlash5 acceptance is only six emitted
tokens per cycle, which caps the current `64.56 ms` cycle at `92.9 tok/s`.
Thus at least `4.56 ms` must be removed even under perfect acceptance, and the
strict 100 tok/s objective needs both materially better mixed-prompt acceptance
and a much faster target verifier. The Q6_K fused top-1 boundary can be useful,
but its expected roughly 1-2 ms draft/sampler saving cannot reach 100 alone.

## Highest-value safe next boundaries

The safest already-measured independent boundary is the DFlash Q6_K M=6
LM-head plus top-1 candidate. It crossed the `<2.5 ms` experiment gate, but it
must first pass the captured-production-activation comparator. Integrating it
before exact row-1..5 token parity would risk silently changing the draft.

The highest-value next target-side fusion is a DPAS-aware
`SwiGLU -> canonical Q8_1 -> down projection` boundary for the 57 eligible
layers, followed by a down-output residual epilogue. The runtime currently
materializes SwiGLU F32, runs canonical Q8 quantization, writes/reads a
row-major canonical temporary, repacks to the Xe2 SoA, then runs down DPAS.
The existing repaired SwiGLU/Q8 kernel already preserves the required F32
rounding point. A dedicated candidate can produce exact canonical half
`(d,sum)`, compute `qsum`, and write the Xe2 SoA/correction directly in one
kernel. This removes the skipped GLU materialization plus the canonical
temporary and repack launch without changing the successful projection
kernel. Gate it on a real all-layer shadow and a cycle-timed AOT crossover;
do not infer a gain from launch count alone.

After that boundary, revisit shared-input attention projection groups only
with canonical quantization and paired strict evidence. The prior QKV/Q
expansion is not a valid shortcut: despite strong isolated ratios, its strict
result was neutral/slower and it introduced larger summation drift.

## Correctness and performance risks found

1. **Current quality evidence is numerical, not exact-output parity.** The real
   down shadow is excellent (`1.01e-7` maximum for `blk.8`), and the earlier
   gate/up shadow was bounded, but the same-build joint gate/up control and
   candidate matched only 6/12 full output hashes. Full187 changed more paths.
   This is consistent with legal floating-point accumulation-order drift, but
   the cold freshness gate alone is not a semantic-quality gate. Add
   representative early/middle/late all-layer shadows and a small semantic or
   exact-case regression before treating the kernel as generally safe.

2. **Joint gate/up is invisible to logical op timing.** The graph loop takes
   the joint shortcut before constructing `sycl_op_timer`, so
   `GGML_SYCL_OP_TIMING=1` omits these paired projections. Cycle timing remains
   valid. Any future full187 op timeline needs an explicit joint-pair timer or
   it will undercount the optimized work.

3. **The matcher is intentionally model-specific but under-guarded for reuse.**
   It validates names, main dimensions, contiguity, shared input, and BMG, but
   does not explicitly require the second node's compute flag or all higher
   dimensions to equal one. Pack slots for gate/up also have no explicit
   upper-layer bound; a same-shaped model above layer 64 could collide with
   down slots. These are not active failures for this exact graph, but should
   be hardened before making the path portable.

4. **Lazy pack creation is not concurrency-safe.** The pointer check and pack
   publication are not atomic. This record uses `n_parallel=1` and all 187
   packs were built during model loading, so it is unaffected. A persistent or
   concurrent worker must load/publish packs once under a lock or before any
   request threads start.

5. **The path and graph replay are mutually exclusive.** Both single and joint
   dispatch reject `GGML_SYCL_ENABLE_GRAPH=1`. Accidentally enabling graphs
   therefore retains the roughly 8.73 GiB mirror allocation but silently falls
   back to production projection. Keep this in run identity and log an explicit
   disabled reason before graph experiments resume.

6. **Memory headroom is now a design constraint.** The 187 mirrors total
   `9,375,252,480` bytes (about 8.73 GiB), in addition to the 14.62 GiB target,
   1.75 GiB draft, recurrent state, KV, and compute buffers. The proposed
   expanded Q6_K pack adds about 1.36 GB. It fits the promoted 4K recipe, but
   longer context and future pack families need an explicit memory budget and
   should replace raw representations where possible rather than duplicate
   them indefinitely.

## Evidence and audited source identity

- AOT JSON:
  `data/qwen36-27b-mtp-gguf-q4-b70-baselines/xe2-m6-hybridquant-full187-joint-aot-realistic128-20260713T1305Z.json`
- JIT JSON:
  `data/qwen36-27b-mtp-gguf-q4-b70-baselines/xe2-m6-hybridquant-full187-joint-jit-realistic128-20260713T1252Z.json`
- AOT server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/servers/xe2-m6-aot-hybridquant-full187-joint-gpu3-20260713.log`
- JIT server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/servers/xe2-m6-jit-hybridquant-full187-joint-gpu3-20260713.log`
- source HEAD: `e3546c7948e3af463d0b401e6421d5a4c2faf565` (protected dirty tree);
- audited file SHA-256 values at review time:
  `mmvq.cpp=0392261c...`, `mmvq.hpp=88457dd5...`,
  `ggml-sycl.cpp=fc55e6d4...`, `common.cpp=a4032720...`, and
  `common.hpp=39899ad1...`.

No protected source was changed by this audit.
