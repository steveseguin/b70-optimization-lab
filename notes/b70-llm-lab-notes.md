# Intel Arc Pro B70 LLM Lab Notes

Date: 2026-05-04

This note is the current public/reproducible summary for the B70 optimization work. The active technical plan is `plans/q4_0-gguf-b70-optimization-plan.md`; submitted benchmark IDs and exact payloads are recorded in `notes/localmaxxing-submissions-2026-05-04.md` and `data/localmaxxing-payloads-20260504.json.gz.b64`.

## 2026-06-11 Qwen3.6 35B Quark W8A8 INT8 Addendum

Current high-fidelity Qwen3.6 target:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.
- Runtime: vLLM/XPU TP4 on 4x Arc Pro B70, 32K context, Quark W8A8 INT8,
  graph-safe custom collectives, no prefix caching.
- Accepted public result: `99.428 tok/s` corrected decode and `98.163 tok/s`
  e2e output for p512/n512/c1/r4, submitted to Localmaxxing as
  `cmq8yhxvo001ipb0149aoa79o`.
- Quality gate passed before submission: exact canaries, JSON
  schema/semantics, copy phrase, 8K long-context needle, repeat stability, and
  baseline hash parity.

Current Qwen3.6 INT8 direction:

1. Keep this accepted TP4 service as the reliability baseline.
2. Do not spend time on Qwen3.5, 4-bit fallback, or quality-lowering routes for
   the production-quality path.
3. Prioritize verifier-preserving speculation using Qwen3.6 assets, persistent
   MoE/fused-activation coverage for the actual Quark W8A8 path, and
   shape-exact collective/MoE microbenches.
4. Track bigger ideas in
   `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`,
   especially the "Bigger Bets To Track" and
   "Public Follow-Up And Bolder Ideas" sections. The current highest-upside
   path is verifier-preserving speculation: MTP/DFlash-style draft tokens are
   allowed only if the current Quark INT8 model remains the final verifier.
5. Add real-router-distribution capture for Qwen3.6 MoE and feed those
   histograms into `vllm-xpu-kernels` grouped-GEMM microbenches before more
   small-M W8A8 kernel tuning. Stage-filtered decode capture and exact-ID
   capture now exist; next step is route replay in the MoE microbench, then
   hot-expert packing or layer-specific policy.
6. Direct vLLM chat quality needs
   `chat_template_kwargs={"enable_thinking": false}` for deterministic canary
   comparisons. The no-thinking post-restore smoke passed; the plain direct
   endpoint is the wrong quality mode because it can emit thinking content.
7. Route replay is now implemented in
   `scripts/bench-qwen36-int8-moe-kernels.py`. Rows=16 real route replay is much
   faster than synthetic uniform routing because fewer experts are active, but
   rows=1 hot-expert packing is layer-dependent. Do not use a blind global
   expert remap; collect more layer/prompt-class route windows first.
8. The current Qwen3.6 backlog is now split into immediate experiments,
   medium engineering branches, and moonshots under "Things To Try After Route
   Replay" in
   `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`. Highest
   priority remains route-window scans plus prompt-class route capture; highest
   upside remains verifier-preserving MTP/EAGLE/self-speculation; highest
   durable kernel work remains persistent MoE and exact-shape grouped-GEMM
   repros for `vllm-xpu-kernels`.
9. Multi-window route replay now exists through `--route-start-indices`. The
   first layer 8/20 scan rejects a blind global hot-expert remap: hot-packing
   helped layer 8 rows=16 and layer 20 rows=1, but hurt layer 8 rows=1 and
   layer 20 rows=16. Treat expert layout as layer/window/prompt-class specific
   until broader captures prove otherwise.
10. Route heatmap analysis now ranks all-layer decode locality. Current first
    targets for broader route-window or single-layer replay are layers `9`, `8`,
    `21`, `14`, and `20`. Layer `9` is the best next new layer because it has
    the strongest all-layer locality signal and was not part of the initial
    exact-ID route replay.
11. Routecapture6 added exact-ID routes for heatmap-selected layers `9`, `14`,
    and `21`. Hot-pack remap still is not a broad win: layer `9` helped rows=1
    but hurt rows=16, layer `14` hurt both, and layer `21` hurt rows=1 but
    helped rows=16 slightly. Treat these route streams as parity/performance
    repros for persistent MoE or grouped-GEMM scheduling rather than evidence
    for a simple global physical remap.
12. After the oracle k=1 parent-state trace, the next speculative branch should
    avoid a scheduler-only fake COW fix. Track the expanded work queue in
    `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md` under
    "Additional Bigger Bets After Parent-State Trace": worker-state tracing,
    transactional scratch verification, KV page-table COW, a sidecar proposer
    protocol, lower-context latency lanes, route-aware COW/MoE capture, and
    upstreamable `vllm-xpu-kernels` repros.
13. After the worker-state trace, the latest backlog is under "Bigger Bolder
    Ideas After Worker Trace And Fresh Public Scan" in the same Qwen3.6 note.
    The highest-upside items are now: no-bonus/post-reconcile COW diagnostics,
    scratch KV page-table verification, verifier-preserving DFlash/MTP sidecar,
    speculative-window pipeline-parallel latency lane, hybrid EP/TP memory
    model, real-route grouped-GEMM autotuning, persistent MoE layerlet kernels,
    tile-native 8-bit repack cache, isolated newer `vllm-xpu-kernels` bakeoff,
    and strict 8-bit engine bakeoff. None of these relax the no-Qwen3.5,
    no-4-bit, no-quality-loss constraint.
14. The no-bonus diagnostic is now recorded under "No-Bonus Diagnostic Result".
    CPU accounting passed, graph-enabled runtime hit `UR_RESULT_ERROR_DEVICE_LOST`
    during capture, and no-XPU-graph runtime showed the verifier-bonus mismatch
    class disappears while replacement-after-reject mismatches remain. Next COW
    work should target rejected-draft/replacement-token state isolation rather
    than only bonus-token emission.
15. Added "Additional Bigger Bets After No-Bonus Runtime" to the Qwen3.6 note. The
    next near-term items are reject/replacement scratch KV, graph-capture
    failure reduction, prompt-class speculation accept maps, MTP-1, DFlash
    sidecar target verification, and a single-user static graph lane. Larger
    bets now tracked are hybrid expert/tensor parallelism, replicated-attention
    plus sharded experts, persistent MoE layerlet kernels, B70-native packed
    INT8 caches, shape-exact tiny collectives, route-aware expert packing,
    current `vllm-xpu-kernels` bakeoff, strict 8-bit engine bakeoff, controlled
    driver/kernel/OS bakeoff, and public upstream repro packages. All of these
    keep the no-Qwen3.5, no-4-bit, target-verifier quality constraint.
16. Added "Bolder Ideas Added After User Backlog Prompt" to the Qwen3.6 note.
    New no-quality-loss ideas now tracked include TP2/TP3 capacity relaunches,
    hybrid expert-parallel simulation, a static single-request decode appliance,
    target-trace-trained proposer adapters, pipelined proposer/verifier work,
    transactional KV/page-table rollback, persistent MoE layerlet kernels,
    load-time tile-native INT8 repack caches, exact collective-elimination
    proofs, prefill/decode disaggregation, capacity-gated mirror serving, and
    upstream-ready shape repro packages. The note also records fresh public
    signals from Localmaxxing, `vllm-xpu-kernels`, Intel XPU container notes,
    B70 TP2 instability reports, and speculative-decoding design discussion.
17. Added an incremental request-window worker trace patch for the remaining
    Qwen3.6 speculative `replacement_after_reject` mismatch:
    `patches/vllm-qwen36-cow-worker-request-window-trace-20260612.patch`.
    The new env-gated trace records token windows, corrected positions,
    token ids at those positions, block-table tails, and slot mappings for
    each active request on `after_prepare_positions`. This is intended to
    decide whether the next repair should target scratch KV/page-table COW or
    persistent `token_ids_cpu` rollback/replacement commit.
18. Ran the new request-window diagnostic as
    `qwen36-quark-int8-tp4-oracle1-nobonus-windowtrace-nograph-20260612b`.
    The trace shows `64` request windows, `16` nonzero speculative windows,
    `7` accepted drafts, and `9` rejected drafts. The remaining drift is now
    attributable to suppressed full-accept bonus tokens being retained in
    persistent token state and then re-emitted on the next reject row. The next
    repair target is token-state commit/rollback, not KV block-table tails.
19. Added a second-tier Qwen3.6 W8A8 backlog with larger quality-preserving
    bets: transactional speculation as a milestone, Intel persistent-MoE kernel
    stack A/B, a one-request static engine lane, route-window persistent MoE
    layerlet replay, expert-parallel simulation, host-stack spare-disk A/B,
    target-trace-trained drafter, pipelined verifier/proposer, collective
    topology profiling, tile-native W8A8 repack cache, upstream repro bundles,
    and a dual-lane production architecture.
20. Added "Cache-Filter No-Bonus Negative And Backlog Refresh" to the Qwen3.6
    note. The cache-filter diagnostic shows that suppressing the full-accept
    bonus in worker cache while scheduler no-bonus accounting also rolls it
    back is a negative result: it moves drift earlier and repeats the last
    committed token. The next implementation target is a consistent
    transaction model, starting with cache-filter plus kept computed count or a
    verifier-owned bonus escrow. New bolder ideas are now tracked around a
    transactional speculation subsystem, verifier-owned commit protocol,
    static single-request executor, GPU-resident proposer state, persistent-MoE
    layerlet work, EP/TP route simulation, W8A8 tile repack cache,
    collective-elimination roofline, target-trace-trained drafter, spare-root
    Intel stack bakeoff, upstream bug/perf packets, and production promotion
    lanes.
21. Added `patches/vllm-qwen36-spec-cachefilter-optin-20260612.patch` and
    applied the same cleanup to the local vLLM checkout. The negative
    cache-filter path is no longer tied to
    `VLLM_XPU_SPEC_DECODE_DISABLE_FULL_ACCEPT_BONUS`; it now requires the
    explicit diagnostic env
    `VLLM_XPU_SPEC_DECODE_FILTER_SUPPRESSED_BONUS_CACHE=1`. This keeps future
    no-bonus traces from silently enabling the rejected worker-cache behavior.
22. Added "Bonus Recompute Diagnostics And Bigger Bets" to the Qwen3.6 note.
    The keep-computed cache-filter diagnostic removed the duplicate-token
    failure but skipped the suppressed bonus; the recompute diagnostic improved
    one natural prompt to first diff at index `25` but still failed repetitive
    parity; and the full-bonus no-graph/eager control diverged despite `100%`
    accepted drafts. Next work is now a no-spec no-graph/eager baseline control
    plus first-diff logit/KV tracing, not speed benchmarking. Larger tracked
    ideas now include a speculative verifier differential debugger, two-phase
    verifier commit protocol, bonus-token escrow as the bridge to MTP/DFlash,
    a no-spec static latency lane, real-route persistent MoE repros, strict
    8-bit engine bakeoff, graph/eager parity audit, host-stack A/B, and an
    upstreamable oracle `k=1` full-bonus failure packet.
23. Added "Runtime-Mode Parity Controls And Larger Bets" to the Qwen3.6 note.
    The old oracle default baseline was stale/mixed for at least the natural
    prompt, so `scripts/launch-qwen36-quark-int8-oracle-trace.sh` now defaults
    to the fresh accepted graph baseline
    `data/qwen36-quark-int8-tp4-accepted-restored-current-oracle-baseline-20260612i.json`.
    No-spec no-graph/eager and no-spec graph-off compile-on controls diverged
    from the accepted graph token stream, so no-graph speculative diagnostics
    are no longer sufficient proof of a speculative verifier bug. The next
    speed-safe work is graph/eager parity, graph-enabled oracle tracing, and
    measured latency decomposition before more speculation benchmarks.
24. Added "Accepted Graph COW Trace, Cache Provenance, and V6 Ideas" to the
    Qwen3.6 note. Default-off COW parent/worker trace env passthroughs now
    exist in `scripts/launch-qwen36-quark-int8-accepted.sh`. Production-cache
    accepted graph tracing preserved the accepted 32-token branch, while a
    fresh graph cache root drifted to the no-graph/refill token branch at the
    known `repetitive_kernel_notes` index `14` sentinel. Cache root and graph
    artifact provenance are now mandatory quality metadata before speed claims.
    New larger ideas include a cache-certified graph registry, resident-state
    verifier service, graph/eager upstream repro packet, certified static
    decode lane, speculation transaction log, route-aware COW/MoE capture, and
    a promotion matrix that separates quality branch, speed branch, and
    stability branch.
25. Added `scripts/check-qwen36-accepted-provenance.py` and "Accepted
    Provenance Guard And FULL_DECODE_ONLY Negative" to the Qwen3.6 note. The
    guard checks served model id, accepted cache-root evidence in the launch
    log, two 32-token sentinel completions, and known graph/refill drift token
    positions before speed claims. `FULL_DECODE_ONLY` was tested on an isolated
    cache root and rejected at startup with
    `sycl_ext_oneapi_work_group_scratch_memory` unavailable under SYCL Graph.
    Restored PIECEWISE accepted backend passed the guard and measured
    `99.463 tok/s` after first text at p512/o512/c1.
26. Added `notes/2026-06-12-qwen36-next-bigger-bets.md` as the focused backlog
    for the next Qwen3.6 35B Quark W8A8 INT8 push. It records the current
    `~100 tok/s` quality baseline, folds in public B70/XPU/persistent-MoE
    signals, and ranks immediate no-quality-loss experiments: real-path
    preallocated MoE scratch reuse, route-exact persistent-MoE layerlets,
    route-window kernel fixtures, low-overhead latency decomposition,
    block-size/metadata-copy screens, strict 8-bit engine bakeoff, and material
    Localmaxxing submission thresholds. Bigger bets now tracked there include a
    B70-native persistent MoE kernel, resident-state transactional verifier,
    static one-request latency appliance, hybrid TP/EP simulation, tile-native
    W8A8 repack cache, GPU-resident metadata updates, cache artifact
    certification, target-trace-trained proposer, production dual-lane routing,
    and an upstreamable Qwen3.6 XPU perf packet.
27. Added vLLM histogram-delta capture to
    `scripts/measure-openai-endpoint-metrics.py` and recorded a direct-backend
    live c1 p512/o512 decode-budget artifact at
    `data/qwen36-quark-int8-tp4-live-c1-p512o512-metrics-hist-20260612q.json`.
    The accepted backend measured `99.875 tok/s` corrected after first chunk,
    `98.613 tok/s` e2e output, `74.163 ms` vLLM TTFT, `69.128 ms` prefill,
    and `5116.930 ms` decode for 512 generated tokens, or `9.994 ms/token`.
    Queue time was effectively zero (`0.0069 ms`). This makes the next speed
    requirement concrete: `>200 tok/s` needs roughly `<=5 ms/token` steady
    decode, so the main work has to cut decode-path kernels/collectives/graph
    fences or use exact target-verified speculation; frontdoor and queue work
    cannot close the gap for c1.
28. Ran a synchronized decode timing profile as a risky attribution diagnostic.
    The timing backend hit Level Zero `UR_RESULT_ERROR_DEVICE_LOST` in
    `block_table.copy_to_gpu(num_reqs)` and then
    `UR_RESULT_ERROR_OUT_OF_RESOURCES` while filling
    `num_accepted_tokens.gpu`, so broad synchronized timing is no longer a
    default profiling recipe. The partial summary is still useful:
    `moe_forward_shared.custom_op` dominated with `4837.535 ms` total across
    `1248` calls, followed by `xpu_moe.gemm2_w8a8` at `1672.690 ms` and
    `xpu_moe.gemm1_w8a8` at `1476.398 ms`; the largest dense allreduce bucket
    was much smaller at `122.319 ms`. Normal accepted service was restored,
    provenance guard passed, and p512/o128 sanity measured `100.234 tok/s`
    corrected after first text chunk. New tracked bets are selective/no-sync
    timing, MoE flight recording, persistent exact W8A8 expert workers,
    expert-parallel simulation, GPU-resident scheduler metadata, offline kernel
    replay, layer-specific tile-native W8A8 repack, a certified static c1 lane,
    BF16 differential quality checks, and a separate host-stack reliability
    lane. Detailed artifacts and next actions are in
    `notes/2026-06-12-qwen36-next-bigger-bets.md`.
29. Added selective XPU decode timing controls in
    `patches/vllm-qwen36-selective-xpu-decode-timing-20260612.patch` and the
    live vLLM helper. New envs allow label include/exclude filtering and
    separate sync include/exclude filtering; the accepted launch script strips
    these unless `VLLM_XPU_DECODE_TIMING_ALLOW=1`. A no-sync label profile
    stayed stable at `100.669 tok/s` corrected p512/o128 and showed no-sync
    step timing is useful for host/graph-enqueue visibility but cannot rank
    live MoE replay kernels under the accepted graph. A model-forward-only
    synchronized profile avoided device loss and measured steady active decode
    `gpu_model_runner.model_forward` at `8.438 ms/token` mean, with profiled
    decode at `10.162 ms/token`. The restored accepted backend passed
    provenance guard and measured `100.196 tok/s` corrected p512/o128. Current
    budget: the graph model forward is the dominant c1 wall, so the next real
    speed target is graph-aware W8A8 MoE replay/kernel work or exact
    target-verified speculation, not frontdoor or queue cleanup.
30. Added `scripts/qwen36-moe-flight-recorder.py`, a CPU-only route JSONL
    analyzer for graph-aware MoE planning. The routecapture5 exact-ID flight
    record covers layers `8` and `20`: layer `8` top-16 experts cover `54.8%`
    of assignments and top-32 cover `75.5%`; layer `20` top-16 cover `53.4%`
    and top-32 cover `72.9%`. Median active experts per 16-token route window
    are `44` and `46`, while full top-k tuple repeat share is only `6.25%`.
    This argues for layer/window-specific tile-native W8A8 packing, persistent
    expert scheduling, or hot-expert replication simulations, not whole-route
    memoization or global remap. Artifacts:
    `data/qwen36-quark-int8-tp4-routecapture5-flight-record-20260612w.json`
    and `.md`.
31. Added `scripts/qwen36-moe-hotset-plan.py` and broader routecapture6 plus
    prompt-class flight records. Routecapture6 exact-ID layers `9`, `14`, and
    `21` show top-32 hotset coverage from `64.5%` to `72.2%`, with top-64 from
    `86.4%` to `91.6%`. Prompt-class layers `8`, `9`, `14`, `20`, and `21`
    show broader top-32 coverage from `57.8%` to `62.8%`, with top-64 from
    `78.6%` to `83.0%`. The hotset memory estimate is favorable: one layer
    top-32 costs about `24.3 MiB/rank`; all-layer top-32 costs about
    `971 MiB/rank`; all-layer top-64 costs about `1.9 GiB/rank`. The next
    exact speed target is now a layer-gated hotset fast path: persistent W8A8
    MoE layerlets or tile-native W8A8 repack with cold-expert exact fallback,
    using model-forward-only sync timing as the live regression gate. The
    detailed backlog and larger ideas are in
    `notes/2026-06-12-qwen36-next-bigger-bets.md`.
32. Added `scripts/qwen36-moe-hotset-manifest.py` and a concrete layer `9` /
    layer `20` manifest from raw route JSONLs. Source-normalized top-64 is now
    the first hotset target: layer `9` top-64 covers `88.7%` mean / `75.0%`
    worst-source, while layer `20` top-64 covers `91.0%` mean / `78.4%`
    worst-source. Top-32 remains a subtest but misses the worst-source
    threshold (`52.0%` for layer `9`, `56.9%` for layer `20`). The manifest
    also validates fixed replay starts for exact-ID and prompt-class stress
    windows, so the next kernel step is a top-64 hotset fast path with exact
    cold fallback, starting on layer `9`.
33. Extended `scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py` with
    hotset split dry-run support. Layer `9` top-64 exact-ID windows put
    `75.0%` to `93.8%` of rows into the hotset, leaving only `5` to `22` active
    cold experts; prompt-class math stress windows still keep `69.5%` to
    `83.6%` of rows hot. Layer `20` is similar on exact windows and mostly
    strong on repetitive stress, except one `62.5%` hot window. This makes
    top-64 hotsets a real target, but a naive two-launch hot/cold GEMM can lose
    to launch overhead. The next useful implementation should be persistent or
    fused around the cold fallback, not just two independent grouped GEMMs.
34. Added a follow-up backlog to
    `notes/2026-06-12-qwen36-next-bigger-bets.md` after the hotset split
    results. Immediate next items are a CPU-safe hotset split floor model,
    layer `9` top-64 GPU microbench during a deliberate backend stop,
    grouped-GEMM policy sweeps on captured route windows, a tile-native hotset
    repack cache, and a strict quality gate before endpoint promotion. Larger
    ideas now tracked include persistent hotset layerlets, fused hot expert
    gate/up/SwiGLU/down, adaptive per-request hotsets, MoE-only TP/EP hybrid
    routing, a static c1 latency lane, device-resident scheduler metadata,
    resident-state verifier speculation, exact-weight backend bakeoffs, an
    upstreamable hotset repro packet, and reliability soak as part of every
    speed claim.
35. Added `scripts/qwen36-hotset-split-floor-model.py` and generated
    `data/qwen36-quark-int8-tp4-hotset-split-floor-model-20260612aa.{json,md}`.
    The CPU-only break-even model shows every selected top-64 hotset split
    window still has cold fallback, so a simple split adds `2` launches per
    two-GEMM MoE layer window. Under a `200 us` full-window / `10 us` launch
    scenario, split body work must be at least `1.11x` faster to break even.
    Full-cold split is deprioritized because it uses `1.25x` table slots plus
    extra launches. Compact-cold split remains worth one maintenance-window
    microbench: layer `9` routecapture6 exact windows shrink table slots to
    `0.29x` mean / `0.34x` max with `75.0%` / `87.0%` min/mean hot coverage.
    The production direction is still persistent/fused cold fallback.

## 2026-05-10 MiniMax AutoRound Addendum

MiniMax M2.7 AutoRound INT4 is now the main four-card optimization target. The
aspiration target has been raised to `60 tok/s` output at p512/n1536 on 4x B70,
with `75+ tok/s` reserved for verified speculative/MTP or deeper fusion that
preserves target logits.

Current quality-conservative anchor:

- `37.552538` output tok/s / `50.070051` total tok/s at p512/n1536, TP4,
  FP16, llm-scaler raw-u4 decode MoE path, Q/K TP variance allreduce enabled,
  no speculation, no expert dropping, and no power-limit change. LocalMaxxing:
  `cmozow03v005wlo01q81bnspx`.

Recent negative follow-ups:

- DFlash from fast NVMe loads/compiles target and drafter but stalls before
  producing a p64/n32 benchmark result.
- Source-tree and installed-runtime RMS provider swaps are below the accepted
  MiniMax reference.
- Installed-runtime post-attention fused-add RMS warmed to `35.077` output
  tok/s at p512/n512, and delayed `o_proj` allreduce plus fused-add RMS warmed
  to `35.804`. Both are negative versus the accepted `39.611` p512/n512
  reference and were not submitted to LocalMaxxing.
- A Python-level custom op wrapping output-projection allreduce plus
  `_C.fused_add_rms_norm` compiled after moving registration out of the forward
  path, but warmed to only `32.611` output tok/s at p512/n512. This rules out
  Python custom-op wrapping as the practical fusion layer.
- Current clean p512/n1536 MiniMax refresh is `37.17` output tok/s /
  `49.558` total tok/s with 17,216 GPU KV-cache tokens. The active AOT graph
  shows 187 TP allreduce boundaries per generated-token graph: 62 Q/K
  variance, 62 output-projection hidden, 62 MoE hidden, and one vocab-embedding
  allreduce. This confirms the next speed path is reducing/fusing collective
  boundaries, especially hidden-state allreduce plus residual/RMSNorm, rather
  than more standalone MoE matvec work.

Current direction:

- Stop spending time on standalone RMS provider swaps or simply moving the same
  allreduce call.
- Build an XPU-specific allreduce plus residual/RMSNorm or MoE/projection
  epilogue fusion path, with p512/n512 and p512/n1536 validation after each
  change.
- Keep all negative/diagnostic flags unset for real benchmarks unless a run is
  explicitly labeled as an experiment.

## Hardware And Constraints

- Host: Ubuntu 24.04.4 LTS, kernel 6.17.0-22-generic during the latest runs.
- CPU: AMD EPYC 9015.
- GPUs: 4x Intel Arc Pro B70 32GB, exposed through Level Zero selectors `0-3`.
- Power-limit / overclocking changes are intentionally out of scope. The current work is software-only.
- Single-card tests should isolate one device with `ONEAPI_DEVICE_SELECTOR=level_zero:N`.
- llama.cpp multi-GPU device syntax is slash-separated, for example `-dev SYCL0/SYCL1/SYCL2`.

## Current Best Results

Quality-preserving Q4_0 GGUF path, llama.cpp/SYCL:

- 1x B70 baseline: about `24.7 tok/s` decode.
- 2x B70 async-copy tensor split: `37.690 tok/s`, LocalMaxxing `cmoqkcqpv0006la04l5mtlj2q`.
- 2x B70 single-kernel allreduce: `39.849 tok/s`, LocalMaxxing `cmoqp6jpq0004lb04241n9ns3`.
- 2x B70 Q8 activation-cache validation, 512 prompt / 512 output: `40.487 tok/s`, LocalMaxxing `cmormylxz000fib04wodwo1ng`.
- 3x B70 single-kernel allreduce, selector/root order `2,1,3`: `41.737 tok/s`, LocalMaxxing `cmoqqed6s0007jv049wnizwle`.
- 3x B70 Q8 activation-cache short run, 512 prompt / 256 output: `42.432 tok/s`, LocalMaxxing `cmordq9t5000dl404x309pj48`.
- 3x B70 Q8 activation-cache validation, 512 prompt / 512 output: `41.659 tok/s`, LocalMaxxing `cmorn71e2000kib0415vo51vj`.
- 3x B70 current quality-cleared no-root Q4_0 stack with experimental flat fused Qwen35 `ssm_ba` GGUF, 512 prompt / 512 output: `50.130 tok/s`, LocalMaxxing `cmov6p4r7007tqr01yi8ug4un`.
- 3x B70 root-residual performance ceiling with `--poll 25`, 512 prompt / 512 output: `50.922 tok/s`, LocalMaxxing `cmouxjqao000npn01hxqn68td`, now marked suspect because later token/logit probing found the root-residual plus meta allreduce-add pair can diverge.
- 3x B70 final-rebuild root-residual rerun with flat fused `ssm_ba` GGUF: `50.687 tok/s` decode and `80.879 tok/s` total. Default-prompt root checks passed, but a two-token prompt follow-up timed out, so this is documented but not submitted/promoted.
- 4x B70 Q4_0 remains negative-scaling: `31.482 tok/s` without Q8 cache and `31.913 tok/s` with Q8 cache; LocalMaxxing `cmor2e5r00004jl04o99d26p8` and `cmornec37000okw040zl9563z`.

FP8 path, vLLM/XPU:

- Official `Qwen/Qwen3.6-27B-FP8` runs, but current XPU block-FP8/requant path is slow: TP2 512-output upper-bound `20.106 tok/s`, LocalMaxxing `cmorb75xb001ckz0489eqc9se`.
- Static `vrfai/Qwen3.6-27B-FP8` with patched XPU FlashAttention2 reaches `41.503 tok/s` on TP4 for 512 prompt / 512 output, LocalMaxxing `cmork3n3k000ujo04y73lbr1j`.
- TP4 also fits Qwen3.6 full configured context (`262144`) and reports `1,206,355` GPU KV-cache tokens.
- PP2 x TP2 is valid as a capacity fallback but slower for one sequence: `22.721 tok/s`, LocalMaxxing `cmormmlz0000bky04wpu4oc01`.
- FP8 KV cache is not a speed path and is quality-risky without proper scaling: `28.036 tok/s`, LocalMaxxing `cmornlh8g000vkw04yb57ukvl`.

MiniMax M2.7 UD-IQ4_XS path:

- First useful four-B70 MiniMax baseline: `13.754 tok/s` for `p0/n64` with `ik_llama.cpp` process-per-GPU RPC workers, SYCL/Level Zero, layer split, runtime repack, CPU KV, fused MoE off, fused MMAD off, and local SYCL `MULTI_ADD`. LocalMaxxing `cmovvoo6f00f5p1017yeb7kxd`.
- Current MiniMax best: `16.384 tok/s` for `p0/n64/r3` after the corrected RPC device map and `-nkvo 0`, with conservative SYCL `MOE_FUSED_UP_GATE`, fused MoE, merged gate/up experts (`-muge 1`), and experimental SYCL `MUL_MULTI_ADD`. LocalMaxxing `cmowft2hr000oo3019is4snoq`.
- Direct single-process SYCL MiniMax is blocked on a regular SYCL model-buffer allocation during `llm_load_tensors`. Even an uneven split plus `-b 512` fails on a 19.028 GB allocation on GPU0 despite full reported VRAM. The process-per-GPU RPC layout remains the valid path until regular model buffers can be chunked or routed through the split/pool allocator.
- Layer placement is only a small/noisy lever: one-repeat `p0/n64` sweep topped out at `16.358 tok/s` with `-ts 0.8/1.05/1.05/1.1`, below the existing `16.384 tok/s` three-repeat best.
- Quality-correct MiniMax graph mode now executes with forced real reductions at nonlinear boundaries, but it is diagnostic only: `GGML_MINIMAX_NO_DEFER_REDUCE=1` plus `GGML_RPC_REDUCE_MIRROR=1` reached only `2.034 tok/s` for a one-token smoke. The earlier faster branch-fused graph path remains unpromoted because deferred reductions can cross RMSNorm/router/MoE and change the math.
- Layer-mode follow-up screens were negative: `-t` sweep topped out at `16.307 tok/s`, `-fa 1` aborts on unsupported `FLASH_ATTN_EXT`, disabling fused MMAD/MoE is slower at p0/n64, oneDNN enabled is slower at `15.590 tok/s`, same-type contiguous copy memcpy is neutral, and an 8-expert `MUL_MULTI_ADD` unroll regressed to `13.823 tok/s` and was removed.
- CPY tracing shows MiniMax repeats three copy shapes per layer: f32-to-f32 row-strided, contiguous f32-to-f16, and `ne0=1` strided f32-to-f16. A default-off standalone shape-specific copy fast path regressed to `12.732 tok/s`, so the next copy-related attempt should fuse producer kernels into KV/cache writes instead of replacing `CPY` with separate kernels.
- Fused RMSNorm is no longer an unsupported-op blocker in the local SYCL RPC worker. The f32 fused RMSNorm implementation runs, but p0/n64/r1 reached `16.308 tok/s`, below the current `16.384 tok/s` best.

INT4 AutoRound path:

- `Lorbus/Qwen3.6-27B-int4-AutoRound` produced strong vLLM/XPU speed results, including `45.2 tok/s` on 1x B70 and `49.1 tok/s` on 2x B70.
- These results are recorded on LocalMaxxing but are not counted as Q4_0 GGUF success because the quantization changes model fidelity.
- `Lasimeri/MiniMax-M2.7-int4-AutoRound` is now the main 4x B70 MiniMax path. Strict-quality promoted public decode is `89.314 tok/s` on LocalMaxxing (`cmpct6t4m007fnw01yjdtlcs4`), with warm in-process p512/n1536 controls in the `92.4` to `92.8 tok/s` range.
- MiniMax vLLM quality guardrails now require exact token hashes for raw145 n64/n256, semantic canaries, arithmetic repeat, and extended sixpack before any candidate speed result is promoted. Warm-only results are not submitted to LocalMaxxing unless the same stack has passed strict quality.
- Recent exact router custom-op attempts are quality-clean but not speed wins: the non-WS router custom-op was neutral, and the stricter router+WS custom-op screened at `92.278 tok/s` versus a matched `92.415 tok/s` control, so it was rejected.
- Retesting vLLM `fuse_minimax_qk_norm` with the XPU helper module on the current promoted stack was also not a speed win: warm p512/n1536 mean was `92.244 tok/s`, below same-family controls. It was rejected before full strict promotion and was not submitted to LocalMaxxing.
- A new JSON task harness shows the fast graph path still has intermittent raw candidate corruption on practical structured output. With validation/retry, 4k max-context/no-padding JSON tasks delivered `30/30` valid outputs at `87.770 tok/s` selected decode and `65.588 tok/s` effective accepted-output rate including retries; this conservative effective result is on LocalMaxxing as `cmpgv9p9j007qpc01oq5zqhdg`. With ~2k prompt padding, delivered output stayed valid, with repeat controls at `83.294` and `83.151 tok/s` selected decode. The newer `83.151 tok/s` 2k-context run is on LocalMaxxing as `cmpgx0yrb009fpc0183xjri4j`; it had selected total-token accounting of `2567.477 tok/s`, but conservative submitted effective accepted-output was `54.898 tok/s` because raw candidate pass rate was only `66.67%`. Concurrency 2 is not usable yet: c2 can have enough KV at `gpu_memory_utilization=0.95`, but graph mode stalls during a fused INT4/RMS Triton launch and no-graph generation dies with Torch XPU `Indexing.h:622` assertions. A 1024-token prefill chunk also hit Intel `ocloc`/IGC internal compiler errors, so keep `max_num_batched_tokens=512` for current reliable context tests. Detailed note: `notes/2026-05-22-minimax-json-quality-context-concurrency.md`.
- The structured HTML fast lane is back above 90 tok/s with zero accepted quality failures after tightening the skeleton suffix regex to forbid apostrophe-only generated word chunks. Repeat30 result: `30/30` accepted, `0` rejects, `100%` first-attempt pass rate, `94.406 tok/s` effective accepted output, `94.692 tok/s` post-first. Artifact: `/home/steve/bench-results/minimax-m2.7-quality-ramp/20260522T212009Z-promoted-structured-skeleton-regex2-repeat30/result.json`. Structured JSON schema cross-check also passed `9/9` with `0` rejects at `87.956 tok/s` effective output and stable parsed JSON hashes. Detailed note: `notes/2026-05-22-minimax-structured-fast-lane-regex2.md`.

## Important Implementation Artifacts

llama.cpp Q4_0/SYCL work:

- Combined diff: `patches/llama-cpp-db44417-b70-sycl-combined.diff.gz.b64`.
- Decode/apply guide: `patches/llama-cpp-db44417-b70-sycl-combined-diff.md`.
- Key runtime flags for the best Q4_0 runs:
  - `GGML_SYCL_ASYNC_CPY_TENSOR=1`
  - `GGML_SYCL_COMM_ALLREDUCE=1`
  - `GGML_SYCL_COMM_SINGLE_KERNEL=1`
  - `GGML_SYCL_Q8_CACHE=1`
- Benchmark harnesses:
  - `scripts/bench-qwen36-q4_0-gguf-sycl-matrix.sh`
  - `scripts/bench-qwen36-q4_0-gguf-vulkan-matrix.sh`

vLLM/XPU FP8 work:

- XPU FA2 singleton scale patch: `patches/vllm-xpu-fa2-compressed-tensors-scalar-scales.patch`.
- Qwen3.5/Qwen3.6 language-only vision skip patch: `patches/vllm-qwen35-language-model-only-skip-vision.patch`.
- Qwen3.6 MoE route-capture diagnostic patch:
  `patches/vllm-qwen36-moe-route-capture-20260611.patch`.
- Qwen3.6 Quark W8A8 route-capture wrapper and summarizer:
  `scripts/launch-qwen36-quark-int8-route-capture.sh` and
  `scripts/summarize-qwen36-moe-route-capture.py`.
- Qwen3.6 route-capture lower-hook patch:
  `patches/vllm-qwen36-moe-route-capture-lower-hooks-20260611.patch`.
- FP8 result notes: `notes/2026-05-04-qwen36-fp8-b70-fa2.md` and `notes/2026-05-04-qwen36-fp8-full-context-topologies.md`.
- FP8 topology data: `data/qwen36-fp8-b70-topology-screens-20260504.json`.

## Current Diagnosis

- Single-card Q4_0 is not limited by flash attention, ubatch, graph capture, oneDNN, AOT alone, or a missing reordered MMVQ path.
- Reordered Q4_0 MMVQ is required; disabling it drops single-card speed to about `15 tok/s`.
- Multi-card Q4_0 improves through async tensor copies, direct allreduce, Q8 activation caching, graph fusions, fused small projections, and safe allreduce+ADD scheduling. Root-residual fused allreduce+ADD is a promising performance ceiling but is not quality-cleared until its ordering hazard with meta allreduce-add is fixed. Four-card scaling still regresses because each token pays many small 20 KiB reductions and narrower row shards lose matvec efficiency.
- Timing hooks show synchronized allreduce cost rises sharply with GPU count: roughly `1.718 ms/token` on 2 GPUs, `5.732 ms/token` on 3 GPUs, and `10.605 ms/token` on 4 GPUs for the same reduction pattern.
- Four-GPU root/order/topology sweeps are not enough; the next useful work is reducing the number of reductions or fusing delayed reductions through safe graph regions.
- MiniMax M2.7 has two very different tracks. The GGUF/RPC path remains capped around `16.384 tok/s`, but the AutoRound vLLM/XPU path is quality-cleared at `89.314 tok/s` public decode and `92+ tok/s` warm in-process decode. Current site-labeled timing shows no single trivial CPU callback left: MoE expert time dominates, while MoE output all-reduce, attention output all-reduce, and Q/K variance all-reduce each contribute comparable per-layer decode costs.

## Current Next Steps

1. Keep Q4_0 single-card profiling focused on reordered MMVQ and activation quantization launch overhead.
2. Prototype fewer/fused Meta allreduces for Q4_0 multi-GPU; do not spend more time on simple root-copy or pairwise allreduce topology variants.
3. Use 3x B70 Q4_0 no-root fused beta/alpha at `50.130 tok/s` as the current quality-cleared speed point; treat root-residual `50.922 tok/s` as a performance ceiling until the correctness hazard is fixed.
4. Use static FP8 TP4 with patched XPU FA2 as the best high-fidelity four-card path for now.
5. Keep PP2 x TP2 as a capacity fallback for larger models, not a speed path for Qwen3.6 27B.
6. Mine Intel `llm-scaler` for reduce-scatter/all-gather, fused output-kernel, Gated DeltaNet, and speculative/MTP ideas, but do not assume it will run directly on Arc/B70.
7. For MiniMax GGUF, keep the process-per-GPU RPC layout only as the capacity baseline; direct SYCL still needs chunked regular model-buffer allocation before it is usable.
8. For MiniMax AutoRound/vLLM, target lower-level MoE expert/router fusion or multi-boundary reduction scheduling. Do not spend more time on pure Python-boundary router moves unless they include a new fused kernel and pass the full strict quality gate.
9. For MiniMax AutoRound usability, debug c2 before advertising concurrency: first reproduce the no-graph `Indexing.h:622` failure with a smaller two-request prompt, then inspect whether scheduler slot/candidate indexing or a custom INT4 shape assumption is feeding an invalid XPU index. Keep the 512-token prefill chunk until the `ocloc` internal compiler error for 1024-token chunking is avoided or an existing safe cache artifact is reused.
10. For Qwen3.6 Quark W8A8 INT8, route capture now works below the generic
    router abstraction. Routecapture4 produced a decode-only
    `quark_int8_apply` summary with `10,080` records across `40` layers and
    `80,640` assignments. Routecapture5 added exact `topk_ids` for layers `8`
    and `20`; use the rank0 artifact for replay because TP ranks record
    duplicate logical routes.
11. For Qwen3.6 performance, prioritize large no-quality-loss levers:
    route-replay MoE microbenches, hot-expert physical packing, layer-specific
    grouped-GEMM policy, newest Intel XPU kernel-stack comparison,
    verifier-preserving MTP/DFlash-style speculation, shape-exact collective
    replacement, and a static one-user latency lane.
12. Do not promote `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1` based only on isolated
    MoE microbench wins. The endpoint screen already rejected it for current
    production because decode speed did not improve and KV headroom dropped.
13. Fresh Qwen3.6 Quark W8A8 verifier probes show that accepted graph
    continuous decode and token-replay/refill verification can follow different
    state trajectories. The strongest example is `repetitive_kernel_notes` at
    output position `14`: accepted graph decode selects token `4752`
    (`" unique"`) as top-1, while prompt-logprob/refill ranks it hundreds to
    thousands of places behind token `6126` (`"PU"`). External re-prefill
    sidecars are therefore diagnostics only. The next quality-preserving speed
    path is resident-state verification: in-engine copy-on-write request/KV/GDN
    state fork, transactional speculation logs, route-aware persistent MoE
    layerlets, shape-exact tiny collective work, and a strict 8-bit engine
    bakeoff. Detailed addendum and artifacts are in
    `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`.
14. Qwen3.6 Quark W8A8 direct offline `LLM.generate` with the accepted
    PIECEWISE graph cache reached `98.564 tok/s` mean output speed for
    p512/o512/r3, essentially matching the accepted endpoint. This rules out
    OpenAI serving/frontdoor overhead as the main c1 bottleneck. The offline
    probe also exposed a stability hazard: two accepted-backend restores reached
    `/health` and then crashed on first completion with
    `UR_RESULT_ERROR_DEVICE_LOST` in XPU metadata-copy paths. The next backlog
    is now resident-state COW verification, structured guard failure artifacts,
    real-route grouped-GEMM/MoE kernel work, scheduler metadata-copy removal,
    exact expert physical packing, TP/EP hybrid experiments, block-size `64`
    screens, and a full oneAPI/PyTorch/Triton/vLLM kernel-stack bakeoff. Detailed
    artifacts and external leads are in
    `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`.
15. Recovery tooling now covers the post-device-lost path. The accepted
    provenance guard writes structured failure JSON when the backend is down,
    and `scripts/qwen36-xpu-recovery-snapshot.sh` captures XPU process,
    health, stats, optional vLLM cleanup, and optional per-device torch copy
    smoke artifacts. After the offline-probe `UR_RESULT_ERROR_DEVICE_LOST`
    event, the four-XPU copy smoke passed, the accepted backend relaunched to
    `/health` in `62 s`, the provenance guard passed all exact sentinels, and a
    p512/o512 c1 sanity run measured `99.728 tok/s` corrected after-first and
    `98.212 tok/s` e2e. This restores the quality baseline but does not change
    the speed diagnosis: >200 tok/s still needs resident-state speculation or a
    real MoE/kernel breakthrough.
16. The Qwen3.6 Quark W8A8 layer `9` top-64 compact hot/cold split closed as a
    negative GPU result. The floor model justified one maintenance-window
    screen, but real XPU grouped-GEMM timing showed exact full-table mean
    `213.852 us` versus compact split mean `407.192 us`, or `1.928x` slower.
    Even `93.75%` hot-coverage windows were `1.525x` to `2.420x` slower, so the
    table shrink does not overcome launch and tiny-shape overhead. Do not spend
    more endpoint downtime on two-launch full-cold, compact-cold, prompt-class,
    or different top-N split variants. Keep hotsets only as one-launch or
    persistent-kernel ideas: in-kernel cold queue, tile-native hotset repack
    inside one grouped-GEMM path, small-shape grouped-GEMM policy work, and
    route-conditioned EP/TP simulation. The accepted endpoint restored cleanly
    afterward; provenance sentinels passed and a repetitive p512/o256 sanity run
    measured `99.157 tok/s` corrected after first text chunk with
    `10.047 ms/generated token` decode.
