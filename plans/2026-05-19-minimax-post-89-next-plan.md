# MiniMax M2.7 Post-89 tok/s Plan

Date: 2026-05-19

## Current Promoted Baseline

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70, TP4, vLLM/XPU
- Current promoted result: `89.314195` output tok/s and `119.085594` total tok/s at p512/n1536, ctx2048, batch 1.
- Quality baseline: exact raw145 n64/n256 token hashes, semantic suite, 16-repeat arithmetic, and extended sixpack all match promoted references.
- LocalMaxxing result: `cmpct6t4m007fnw01yjdtlcs4`

## Promotion Policy

Only promote or submit a new result when all of these are true:

- Exact-token and semantic quality gates pass.
- The run is repeatable across at least four benchmark repeats.
- The mean output tok/s is above `89.314195` by more than normal run noise.
- No sampling, routing, quantization, or precision shortcut changes quality semantics.

Negative, quality-failed, or merely noisy results stay local/GitHub-only.

## Immediate Candidates

1. Current-high stack plus `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`.
   - Rationale: communication-only knob, no model math change.
   - Risk: previous CCL topology override screens were negative on older stacks.
   - Status: rejected. Strict quality passed, but mean output fell to `89.037858` tok/s and oneCCL/PMI teardown noise appeared. Keep this env unset.

2. Current-high stack plus `VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS=1`.
   - Rationale: avoid redundant Python/framework tensor copies when the MoE input and router logits are already contiguous.
   - Risk: an older related screen was slightly negative, but it was not the exact current full-forward stack.
   - Status: rejected. Strict quality passed, but mean output was `89.141961` tok/s and shutdown logs showed intermittent `Bad address` noise.

3. Attention `o_proj` custom-op boundary.
   - Rationale: rank-0 sync timing showed FP16 hidden-state allreduce/projection boundaries as the visible synchronized cost.
   - Status: rejected. Strict quality passed, but mean output was `89.100464` tok/s, `0.24%` below the promoted mean. Broad Python custom-op wrapping alone is not enough.

4. Site-labeled allreduce timing.
   - Rationale: the previous timing run grouped collectives only by shape and dtype. The next run should label Q/K variance, attention `o_proj`, MoE output, and any delayed/final hidden-state allreduces so the next fusion target is selected by evidence.
   - Status: completed. MoE output labels were captured, while attention/RowParallel labels did not survive the compiled graph path. The remaining unlabeled FP16 hidden-state shapes/counts match the attention `o_proj` collective family. The largest visible buckets were Q/K variance FP32 `(1, 2)`, attention-shaped FP16 hidden `(1, 3072)`/`(2, 3072)`, and MoE-output FP16 hidden `(1, 3072)`/`(2, 3072)`.

5. MoE output direct-allreduce inside the custom-op boundary.
   - Rationale: MoE-output FP16 hidden-state allreduce remained visible in the site-labeled timing run.
   - Status: rejected. Exact raw145 and semantic quality passed, arithmetic n64/r8 passed, and extended sixpack passed, but four p512/n1536 repeats averaged `88.843823` output tok/s / `118.458431` total tok/s. This is `0.470372` output tok/s below the current promoted mean. The active runtime hook was reverted and the result was not submitted to LocalMaxxing.

6. Q/K RMS variance allreduce+scale custom op.
   - Rationale: the site-labeled timing run showed the FP32 `(1, 2)` Q/K variance collective as the largest visible synchronized bucket. This candidate preserved the exact promoted ordering by performing allreduce first and then multiplying by `1 / tp_world` inside a single custom-op boundary.
   - Status: rejected. Exact raw145 n64/n256, semantic suite, 16-repeat arithmetic, and extended sixpack all passed, but four p512/n1536 repeats averaged `88.558751` output tok/s / `118.078334` total tok/s. This is `0.755445` output tok/s below the current promoted mean. It also produced intermittent `Bad address (src/pipe.cpp:367)` shutdown noise. The active runtime hook was reverted and the result was not submitted to LocalMaxxing.

7. Targeted RowParallel attention `o_proj` in-place allreduce.
   - Rationale: the remaining visible FP16 hidden-state allreduce family matches attention `o_proj`, and the previous broad attention custom-op wrapper was quality-safe but slower. This tried a narrower math-preserving in-place path only for `*.o_proj` RowParallelLinear outputs on XPU FP16/BF16 tensors up to 6144 elements.
   - Status: rejected. Exact raw145 n64/n256, semantic suite, 16-repeat arithmetic, and extended sixpack all passed, but four p512/n1536 repeats averaged `88.852415` output tok/s / `118.469886` total tok/s. This is `0.461781` output tok/s below the current promoted mean. It also produced intermittent `Bad address (src/pipe.cpp:367)` shutdown noise during quality teardown. The active runtime hook was reverted and the result was not submitted to LocalMaxxing.

8. Size-ranged oneCCL `CCL_ALLREDUCE` algorithm selection.
   - Rationale: Intel oneCCL supports size-ranged algorithm selection, so this screened whether tiny TP collectives could benefit from `recursive_doubling` without changing model math.
   - Candidate: `CCL_ALLREDUCE='recursive_doubling:0-8192;ring:8193-max'` on top of the current promoted graph-enabled stack.
   - Status: rejected before quality. oneCCL accepted the env var, but XPU graph capture failed with `sched algorithms do not support sycl_graph recording, please use sycl_algorithms`. The strict runner reported `quality_failed_raw145_n64`, but no tokens were generated; classify this as runtime/graph incompatibility, not a quality regression. Keep `CCL_ALLREDUCE` unset for promoted graph-enabled runs unless a future oneCCL/XPU stack provides a graph-compatible SYCL algorithm path.

9. oneCCL topo copy-engine pipeline toggles.
   - Rationale: keep the default graph-compatible `topo` allreduce path, but test whether disabling reduce-scatter/allgatherv monolithic pipeline kernels changes copy-engine overlap or slow-tail behavior without changing model math.
   - Candidate: unset `CCL_ALLREDUCE`, set `CCL_REDUCE_SCATTER_MONOLITHIC_PIPELINE_KERNEL=0`, and set `CCL_ALLGATHERV_MONOLITHIC_PIPELINE_KERNEL=0`.
   - Status: rejected. Exact raw145 n64/n256, semantic suite, 16-repeat arithmetic, and extended sixpack all passed, but four p512/n1536 repeats averaged `88.749571` output tok/s / `118.332762` total tok/s versus the promoted `89.314195` / `119.085594`. One repeat fell to `87.099748` output tok/s, so this was both slower and noisier. Keep these oneCCL topo pipeline envs unset for promoted graph-enabled runs.

10. Q/K clean-weight guard CPU-callback reduction by raising `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS`.
   - Rationale: reduce CPU sanity checks/callbacks in the Q/K clean-weight guard for prefill-sized prompts while preserving the clean-weight mechanism.
   - Candidate: current promoted stack with `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS=1024`.
   - Status: rejected before benchmarking. raw145 n64 exact passed, but raw145 n256 exact failed: expected `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`, observed `ff27d99c39789c365fcb83d140aad8d168bf0735846015e231ad95bcc5f1ab43`. The output was deterministic and non-degenerate but shifted into a repeated Greek-token continuation. Keep the promoted `min_tokens=2`; the n64 canary alone is not sufficient for this guard.

11. Current-high retest of `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=2`.
   - Rationale: the earlier max2 screen was lower than max4, but a current-high isolated cache retest was useful because max2 is close to max4 and could have been cache/runtime-noise sensitive.
   - Status: rejected. Full strict quality passed, including raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Four p512/n1536 repeats averaged `89.242091` output tok/s / `118.989455` total tok/s. This is only `0.072104` output tok/s below the promoted mean, but still below it. Keep `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4`; no LocalMaxxing submission.

12. Index-based MiniMax MoE full-forward custom-op.
   - Rationale: remove byte-string `LayerName` resolution and dict lookup inside the current promoted MoE full-forward custom-op boundary without changing model math.
   - Candidate: current promoted stack plus `VLLM_MINIMAX_MOE_FULL_FORWARD_INDEX_CUSTOM_OP=1`.
   - Status: rejected. Full strict quality passed, including raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Four p512/n1536 repeats averaged `88.648258` output tok/s / `118.197678` total tok/s, about `0.75%` below the promoted mean. Leave `VLLM_MINIMAX_MOE_FULL_FORWARD_INDEX_CUSTOM_OP` unset; no LocalMaxxing submission.

13. Q/K RMS post-allreduce apply custom-op boundary.
   - Rationale: preserve the proven Q/K ordering while wrapping the post-allreduce scale plus existing XPU apply helper in a narrower custom-op boundary.
   - Candidate: current promoted stack plus `VLLM_MINIMAX_QK_RMS_POST_AR_APPLY_CUSTOM_OP=1`.
   - Status: neutral / rejected. Full strict quality passed, including raw145 n64/n256 exact hashes, semantic suite, arithmetic-repeat n64/r8, and extended sixpack. Four p512/n1536 repeats averaged `89.328078` output tok/s / `119.104104` total tok/s versus the promoted `89.314195` / `119.085594`, a negligible `+0.0155%` delta inside run noise. The candidate also introduced repeated `ocloc` 245 / IGC floating-point-exception messages during graph capture. Leave `VLLM_MINIMAX_QK_RMS_POST_AR_APPLY_CUSTOM_OP` unset; no LocalMaxxing submission.

14. XPU FlashAttention no-contiguous cleanup.
   - Rationale: upstream vLLM removed forced `q/k/v.contiguous()` calls before XPU FlashAttention, so this tested whether those wrapper copies were still costing the MiniMax TP4 stack.
   - Candidate: current promoted stack with the upstream `vllm/_xpu_ops.py` FlashAttention hunk from `be0dcc29d` / PR #40356.
   - Status: rejected as a speed candidate. Full strict quality passed, including raw145 n64/n256 exact hashes, semantic suite, arithmetic-repeat n64/r8, and extended sixpack. Four p512/n1536 repeats averaged `88.890310` output tok/s / `118.520414` total tok/s versus the promoted `89.314195` / `119.085594`, about `0.47%` slower. One repeat printed the known `Bad address (src/pipe.cpp:367)` shutdown noise after writing JSON. Do not submit to LocalMaxxing. This narrows the remaining bottleneck away from the immediate XPU FlashAttention contiguous wrapper path.

15. Recheck XPU Level Zero IPC peer-polling path for Q/K variance allreduce.
   - Rationale: the CUDA MiniMax kernel fuses Q/K variance exchange and RMS apply through peer-visible Lamport workspaces, so the closest XPU analogue is a peer IPC mailbox path.
   - Candidate: standalone `minimax_qk_rms_xpu_ipc` recheck on the current 4x B70 setup, plus a new system-scope `sycl::atomic_ref` sequence-counter probe and an XCCL tiny allreduce comparison.
   - Status: rejected as a vLLM integration path. Level Zero peer access, remote fills, and forked IPC handles all validated across all 4x4 source/destination pairs, but cross-device atomics are not advertised. XCCL `[1, 2]` FP32 allreduce measured `0.061791 ms/iter`; the two-kernel mailbox path with a CPU barrier validated at `0.290768 ms/iter`; the same path without a barrier failed validation; single-kernel sequence/counter polling remained around `417 ms/iter`; and the atomic-counter variant failed validation. Keep the IPC prototype as evidence only. Do not pursue SYCL peer-memory polling again unless a new Level Zero event/barrier or oneCCL fused primitive can validate without CPU barriers.

16. Current-high `MAX_BATCHED_TOKENS=640` scheduling screen.
   - Rationale: retest a small chunked-prefill boundary change on the current promoted post-89 stack, since older MBT sweeps happened before the full-forward MoE custom-op and MoE-output allreduce-inside-custom-op changes.
   - Candidate: promoted stack plus `MAX_BATCHED_TOKENS=640`, isolated compile cache, full strict quality gates, and four p512/n1536 repeats.
   - Status: rejected. Full strict quality passed, including raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Four repeats averaged `88.835750` output tok/s / `118.447666` total tok/s, below the promoted `89.314195` / `119.085594`. Keep `MAX_BATCHED_TOKENS=512` for promoted p512/n1536 MiniMax runs; no LocalMaxxing submission.

17. Router-linear plus MoE fusion using existing all-256 candidate repair.
   - Rationale: reduce CPU/framework boundaries by moving more MiniMax router
     and MoE logic into the llm-scaler custom-op path.
   - Candidate: reuse the existing exact `minimax_m2_candidate_repair_topk`
     kernel with all 256 experts as the candidate set.
   - Status: rejected before full-model integration. The kernel is exact, but a
     standalone XPU microbench showed it is much slower than the current router
     linear: for 1/2/4 decode tokens, current `linear(x.float(), w)` measured
     `0.032211` / `0.022275` / `0.022450 ms`, while all-256 candidate repair
     measured `0.609194` / `0.523925` / `0.656969 ms`. Top-k ids matched and
     max weight diff stayed within `7.45e-08`, so this is a performance
     rejection, not a quality rejection. Do not implement naive all-expert
     candidate repair in the hot path.

18. MiniMax WS decode-buffer reuse.
   - Rationale: reduce allocator/framework churn inside the current llm-scaler
     MiniMax logits WS MoE decode path without changing model math.
   - Candidate: reuse only the routed intermediate scratch buffer via
     `VLLM_XPU_MINIMAX_WS_REUSE_DECODE_BUFFERS=1` /
     `VLLM_XPU_MINIMAX_WS_REUSE_INTERMEDIATES=1`; leave top-k scratch reuse
     behind a separate diagnostic-only flag.
   - Status: rejected as a speed candidate. The intermediate-only form passed
     full strict quality, including raw145 n64/n256 exact hashes, semantic
     suite, 16-repeat arithmetic, and extended sixpack. Four p512/n1536 repeats
     averaged `88.900355` output tok/s / `118.533807` total tok/s versus the
     promoted `89.314195` / `119.085594`. The earlier combined top-k plus
     intermediate reuse attempt failed raw145 n64 and produced corrupted output,
     so `VLLM_XPU_MINIMAX_WS_REUSE_TOPK_BUFFERS` must remain diagnostic-only.
     Allocator scratch reuse is not a meaningful current bottleneck; no
     LocalMaxxing submission.

19. Cache llm-scaler MiniMax logits WS op on each MoE layer.
   - Rationale: avoid repeated Python import/op resolution in the MiniMax MoE
     monolithic decode path without changing model math.
   - Candidate: current promoted stack plus
     `VLLM_XPU_LLM_SCALER_MOE_CACHE_MINIMAX_LOGITS_OP=1`.
   - Status: rejected as a speed candidate. Full strict quality passed,
     including raw145 n64/n256 exact hashes, semantic suite, 16-repeat
     arithmetic, and extended sixpack. Four corrected p512/n1536 repeats
     averaged `88.150576` output tok/s / `117.534102` total tok/s versus the
     promoted `89.314195` / `119.085594`, and below today's post-repro control
     mean of `88.495999` / `117.994666`. Keep the flag unset. An earlier
     throughput attempt for this candidate was invalid because the benchmark
     env was sourced but not exported, causing the wrapper to fall back to
     `MAX_BATCHED_TOKENS=1024`; ignore that directory for comparisons.

20. Source rebuild sanity and non-WS recovery after a failed llm-scaler
    full-shared tile experiment.
   - Rationale: before more lower-level fusion work, verify the llm-scaler
     extension can still be rebuilt and imported cleanly.
   - Status: blocked for promoted-path source work. Rebuilt `moe_int4_ops`
     shared objects segfault during import inside `libsycl.so.8`
     `ProgramManager::addImage(...)`, before vLLM code runs. Disabling the
     new candidate, trying `-fsycl-device-code-split=off`, and disabling
     unused candidate-repair/WS sections did not produce an importable rebuilt
     binary. Restoring the importable `20260512T064555Z` binary recovered a
     quality-clean non-WS MiniMax logits fallback, but that binary lacks
     `moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws`. The fallback passed
     raw145 n64/n256 exact hashes, semantic suite, and arithmetic-repeat r8,
     but averaged only `75.767918` output tok/s / `101.023891` total tok/s.
     This is a recovery result, not a LocalMaxxing submission. See
     `notes/2026-05-20-minimax-llm-scaler-rebuild-import-segfault-and-nonws-recovery.md`.

21. Source-rebuilt WS extension recovery.
   - Rationale: unblock further lower-level source optimization by proving that
     the promoted llm-scaler WS extension can be rebuilt from source and
     imported cleanly.
   - Status: completed. The promoted patch is rooted at the
     `vllm/custom-esimd-kernels-vllm` extension subdirectory; applying it from
     the llm-scaler repo root without
     `--directory=vllm/custom-esimd-kernels-vllm` was the reproducibility
     mistake. An isolated rebuild from commit
     `4bfc0070090cc54afdb2d46b8e57882359141568` with the correct patch prefix
     produced a WS-capable `moe_int4_ops` shared object with SHA256
     `30b19be4456abab814f3378561204d575e4e8c01f848634a059d72ff3b23db66`.
     Strict quality passed, including raw145 n64/n256 exact hashes,
     semantic-suite n64/r2, arithmetic-repeat n64/r16, and extended-sixpack
     n64/r2. Four p512/n1536 repeats averaged `87.964466` output tok/s /
     `117.285955` total tok/s, with output repeats `88.823285`,
     `88.889003`, `86.989162`, and `87.156415`. This restores a source-built
     promoted path but does not beat the LocalMaxxing-promoted `89.314195`
     tok/s result, so it was not submitted as a new result. See
     `data/minimax-m27-ws-source-rebuild-recovery-20260520.json`.

22. Router-linear inside llm-scaler MiniMax MoE custom-op boundary.
   - Rationale: reduce CPU/framework scheduling boundaries by moving the
     MiniMax FP32 router linear projection into the existing llm-scaler
     MiniMax logits WS MoE path, while preserving exact router logits and the
     same downstream MoE work-sharing implementation.
   - Status: rejected as a speed candidate. The candidate passed exact raw145
     n64 and n256 token-hash gates, and an eager path-proof run confirmed the
     new router custom-op selected during decode on all four XPUs. Four warm
     p512/n1536 repeats averaged `92.831898` output tok/s / `123.775864`
     total tok/s versus the restored promoted active control at `92.854798`
     output tok/s / `123.806397` total tok/s. The `-0.025%` output delta is
     neutral to slightly negative. Do not promote and do not submit to
     LocalMaxxing. See
     `notes/2026-05-21-minimax-router-customop-neutral.md` and
     `data/minimax-m27-router-customop-neutral-20260521.json`.

## Source-Level Work Queue

- Audit remaining decode-time CPU/framework boundaries in `minimax_m2.py`, `moe_wna16.py`, and `xpu_communicator.py`.
- Prioritize a lower-level fusion or scheduling candidate around one of the three proven collective families: Q/K variance FP32, attention `o_proj` FP16 hidden-state allreduce, or MoE-output FP16 hidden-state allreduce.
- Do not spend more time on broad Python custom-op wrappers unless the wrapper changes a lower-level compiled/collective boundary.
- Do not force non-`topo` `CCL_ALLREDUCE` in graph-enabled runs; the scheduled algorithm path is not compatible with current `sycl_graph` capture.
- Prefer math-preserving changes that remove import/call/copy overhead or custom-op graph breaks.
- Preserve exact operation ordering around residual add, RMSNorm, router logits, expert selection, and final allreduce unless a canary explicitly proves equivalence.
- For any new patch, save a patch note and strict run summary before considering LocalMaxxing.

## Current Next Step

Implement the next math-preserving candidate against a real collective boundary. Preferred order:

1. A narrow Q/K variance collective path that reduces the `(1, 2)` FP32 dependency without changing the exact Q/K RMSNorm formula.
2. A lower-level attention `o_proj` scheduling/fusion candidate, since Python custom-op wrapping was quality-safe but slower.
3. A true MoE-output epilogue/allreduce fusion candidate, since direct Python-level allreduce replacement was quality-safe but slower.

The simple Q/K custom-op boundary and the targeted RowParallel `o_proj` in-place hook did not help, so future work needs to be lower-level than Python conditional/custom-op wrapping. The next useful candidates should either fuse a proven collective with its adjacent kernel at the backend level, or reduce CPU/framework scheduling boundaries without adding Python branches to the hot path.

The size-ranged `CCL_ALLREDUCE` screen also failed before quality under graph capture. That removes high-level oneCCL algorithm selection from the current near-term path; the remaining credible route to another large gain is lower-level XPU/SYCL fusion or graph scheduling around the known collective families while preserving the default graph-compatible communication backend.

The oneCCL topo copy-engine toggles were quality-clean but slower. High-level communication environment changes have now produced regressions or graph incompatibilities; the next pass should move back into source-level scheduling/fusion where the candidate can remove a real hot-path boundary instead of changing oneCCL's global heuristics.

The clean-weight guard threshold screen shows that removing CPU callbacks around Q/K weight sanity can change longer greedy output even when the first 64 generated tokens match. Future CPU-callback reductions need an equivalent clean-weight guarantee rather than simply bypassing the guard.

The current-high max2 retest is close but still negative. The guard-size tuning path is now effectively exhausted: max1, max2, max3, and max512 are all below max4 under strict quality. The next candidate should be source-level and should remove a real compiled/backend boundary, not just adjust Python guard thresholds.

The index-based MoE full-forward custom-op also shows that shaving name lookup
inside the already-promoted Python custom-op wrapper is not enough. The next
source-level candidate should target a real tensor/collective boundary, with
Q/K variance plus apply remaining the lowest-risk option and lower-level
attention `o_proj` reduce fusion remaining higher risk.

The Q/K post-allreduce apply custom-op confirms the same pattern on the Q/K
side: wrapping existing kernels can be quality-clean, but it does not move
throughput beyond noise and can create worse Intel compiler behavior. Future
Q/K work should avoid another Python wrapper and instead target a lower-level
XPU/SYCL fusion or compiler scheduling change that removes a real kernel or
collective boundary.

The XPU FlashAttention no-contiguous cleanup is also quality-clean but slower
on this workload. That removes another shallow wrapper-copy hypothesis. The
next credible path is still a deeper XPU/SYCL implementation around the
MiniMax-specific Q/K allreduce+RMS or hidden-state allreduce epilogue, not more
high-level Python or wrapper-only edits.

The Level Zero IPC recheck confirms that peer buffers themselves are usable, but
the CUDA-style in-kernel Lamport polling design does not translate cleanly to
this B70/XPU stack. XCCL is still the correct tiny-collective primitive today.
Future Q/K fusion work must either extend/fuse around XCCL, use a validated
Level Zero synchronization primitive, or move to a different hot path.

The current-high MBT640 screen confirms that scheduling-boundary tuning is not
the next speed source for batch-1 p512/n1536 MiniMax. Quality remains exact, but
decode is slower than the promoted stack. Move back to source-level work that
removes a real remaining boundary: the most credible next target is fusing the
FP32 router-linear step into the existing llm-scaler MiniMax logits WS MoE path,
behind a default-off flag and strict top-k/quality audits.

The first router-fusion implementation candidate is now rejected: exact
all-256 candidate repair is correct but much slower than the current router
linear. Router work should only continue if a focused full-model timing run
shows router materialization is still meaningful, and the implementation should
use either a proper optimized full-router GEMV/top-k kernel or a narrower
`router_logits -> top8 -> MoE` boundary fusion.

The MiniMax WS decode-buffer reuse screen is quality-clean for intermediate
scratch only, but slower than the promoted stack. Top-k scratch reuse is
unsafe under graph-captured layers without a deeper lifetime/aliasing repair.
Future allocator work should be deprioritized unless timing evidence changes;
the next credible improvement path is still lower-level fusion/scheduling in
one of the remaining kernel/collective families, not additional scratch-buffer
reuse.

The cached-MiniMax-op screen also failed to improve throughput despite exact
quality. This closes another shallow CPU/framework-reduction idea. The next
candidate should be lower-level: either a backend-level fused Q/K
allreduce+RMS apply path, a real attention/MoE hidden-state allreduce epilogue
fusion, or a better optimized router/top-k/MoE boundary kernel than the
rejected all-256 candidate repair path.

The source rebuild sanity check is now resolved for the promoted WS path. Future
source optimization can proceed from the isolated rebuilt extension state, but
the current validation mean is slightly below the earlier promoted mean. The
next work should first explain or reduce that variance, then continue into
lower-level source candidates. The highest-value next steps are:

1. Add a one-process warm-repeat benchmark mode so quality and throughput
   repeats do not reload 112 GiB of weights and repeatedly stress process
   teardown. This should improve repeatability of the measurement itself without
   changing model math.
2. Capture per-token decode timing around the restored WS path to separate the
   lower `86.99`/`87.16` repeats from normal noise, CCL slow-tail behavior,
   graph replay behavior, or thermal/driver scheduling variance.
3. Resume source-level fusion work from the rebuilt WS state, focusing on real
   kernel/collective boundaries rather than Python wrapper reductions:
   Q/K variance allreduce+RMS, attention `o_proj` hidden allreduce, and
   MoE-output epilogue/allreduce remain the credible targets.

2026-05-21 update: the current-stack Q/K compiler-pass retest is quality-clean
but not a performance win. It passed fresh-cache strict quality, including exact
raw145 n64/n256 token hashes, 8x arithmetic repeat, and extended six-pack, but
process-level p512/n1536 averaged only `88.50` output tok/s. Logs also report
`minimax_allreduce_rms_qk op not found`, so the requested compiler pass is
disabled rather than using a real fused backend op. The useful outcome is a
strict-harness hardening: fresh cache roots are now the default and promoted
Q/K helper flags are passed into the quality checker. Do not submit this result
to LocalMaxxing; move next to implementing the missing backend op or another
true lower-level fusion.
