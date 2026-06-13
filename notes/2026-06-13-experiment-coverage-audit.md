# Experiment Coverage Audit

Date: 2026-06-13

Scope:

- Reviewed tracked notes, recent commit history, and current Qwen result
  artifact names to make sure prior experiments are not lost.
- Focus is decision coverage: what worked, what was rejected, and which older
  wins are worth remembering for the current Qwen3.6 35B-A3B Quark W8A8 INT8
  lane.
- This does not promote any new runtime, model, quantization, or endpoint.

## Current Qwen3.6 Quark W8A8 Coverage

Current accepted lane:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.
- Runtime: vLLM/XPU TP4, 32K context, no prefix cache, PIECEWISE graph,
  clone-safe custom collectives, GDN clone-mode quant reuse, fast `/mnt/fast-ai`
  model/cache roots, P2P enabled, `CCL_ZE_IPC_EXCHANGE` unset/default.
- Speed anchor: roughly `99-101 tok/s` c1 decode, with the exact-model
  Localmaxxing row around `99-100 tok/s`.

Things that worked and should stay remembered:

1. **No-prefix + PIECEWISE graph + custom collectives is the accepted base.**
   Most simple serving flags now measure against that posture. Regressions or
   small gains should not displace it without paired A/B, quality, and repeat
   proof.

2. **Forward-boundary timing changed the search space.**
   Synchronized timing put the dominant steady-state cost inside compiled
   `model_forward`. Logits, sampler, bookkeeping, output formatting, SSE, and
   final-only response handling are not 2x-class levers for c1.

3. **Route replay and W8A8 layer-floor work are useful, but not yet endpoint
   wins.**
   Exact route replay, offset-GEMM, active-offset, quant-out scratch plumbing,
   and hotset experiments are valuable because they expose the layer budget.
   They have not yet removed enough fixed dispatch cost. The non-speculative
   path still points to a resident one-dispatch W8A8 MoE layerlet.

4. **Quant-out scaffold is a real building block.**
   It improved the exact preallocated route replay to about `207 us/layer`, but
   that is still above the roughly `168 us/layer` budget for `>200 tok/s`.
   Keep it as layerlet plumbing, not an endpoint promotion.

5. **Exact SiLU+quant is a small, quality-cleared lead, not a promotion.**
   The exact fused SiLU-Q candidate reached `99.7863 tok/s` and passed parity
   canaries, but the lift was about `0.47%` versus one accepted artifact and
   not enough to promote. If later timing shows activation/quant is a real
   bottleneck, reuse its exactness harness and repeat gate.

Rejected or deprioritized Qwen W8A8 paths already covered:

- TP2 graph32K: slower (`86.8477 tok/s`) than TP4 controls around `99.63`.
- MTP on the current checkpoint: blocked because required weights are absent.
- Local argmax and packed reducer: below accepted decode; logits/sampling not
  the c1 bottleneck.
- N-gram/oracle speculation: not promotable until verifier/KV/input-position
  parity is repaired.
- `--max-num-batched-tokens 512` and `--block-size 256`: effectively flat for
  c1 and worse for aggregate, so keep current `8192` MBT and default block size.
- `VLLM_XPU_ALLREDUCE_ASYNC_WAIT=1`: about `8%` slower.
- Custom allreduce graph-clone-off: tiny/noisy improvement only; keep clone
  guard enabled.
- Small-N INT8 GEMM, FlashAttention split policies, GDN view alias,
  scratchpad-ring shared quant, skip-Python-contiguous, skip redundant casts,
  and one-off output-tail changes: below speed gate or not dominant.
- Hot-expert table-size-only changes and simple rank route skew: not enough;
  route counters were identical across ranks in the latest overlay.

Raw artifact coverage:

- The tree still has many untracked or modified June Qwen logs/traces. Most are
  raw restore logs, request traces, or one-off diagnostic captures. Their
  decisions are represented in the active backlog and data summaries. Do not
  bulk-commit them without a separate artifact-triage pass.

## Older Qwen3.6 27B Q4/FP8 Lessons

These are not current-model results, but they are useful engineering memory.

1. **Three cards can beat four cards for c1 latency.**
   Qwen3.6 27B Q4_0 GGUF quality-cleared TP3 reached `46.194319 tok/s`, while
   equal four-card stayed around `34.929313 tok/s`. A four-card assist split
   improved to `39.204149 tok/s` but still lost to TP3. This supports the
   current Qwen35 TP4-bypass lane: more cards can hurt latency if collectives
   and narrow shards dominate.

2. **Graph/epilogue fusion worked when exactness was controlled.**
   Q4 fused allreduce+residual add, reshape-through-add, fused MMVQ2, and
   narrower `sync_after=2` were quality-preserving gains. The durable lesson is
   to fuse real graph boundaries and prove equivalence, not toggle generic
   communication flags.

3. **Root-residual shortcuts need strict quality proof.**
   The Q4 root-residual plus meta allreduce-add interaction failed stronger
   token/logit checks. A host wait fixed correctness but collapsed throughput.
   Do not accept shortcut ordering changes without strong canaries.

4. **Small recurrent projection fusion was real.**
   The fused beta/alpha augmented Q4 model reached `50.129900 tok/s` with
   root-residual disabled and byte-matched the original model in the safe probe.
   For current Qwen W8A8, this is a reminder to keep GDN/recurrent projection
   fusion on the table if layer timing points there, preferably as a runtime
   rewrite or layerlet, not as a model substitution.

5. **FP8 27B needed default IPC/topology and bounded n-gram settings.**
   The validated FP8 TP4 path used default IPC/topology and n-gram depth 4 with
   lookup `2/4`, landing around `47.674832 tok/s` to a prior `49.581893 tok/s`
   best. Depth 3/6, GPU n-gram, sockets forcing, and lookup widening were
   worse. For current Qwen, speculation still needs exact target verification.

6. **Library precedence mattered.**
   Old FP8 notes explicitly warned not to source oneAPI `setvars.sh` for vLLM
   runtime, because oneAPI library precedence could trigger XCCL instability.
   Keep recording runtime library provenance in future accepted results.

## MiniMax Lessons Now Captured

The dedicated MiniMax transfer note is
`notes/2026-06-13-minimax-m27-transfer-audit-for-qwen36.md`. Key reminders:

- XPU graph and AOT/direct-load cache behavior produced the first large gains.
- Block-size 256 plus MBT512 was a MiniMax win but a direct Qwen W8A8 reject.
- Q/K clean-weight guard repaired graph quality after NUL-token corruption.
- Strict local-argmax and MiniMax-logits paths provided safe results around
  `60-61 tok/s`, while later warm steady-state cache validation reached
  `93.443623 tok/s` only after rejecting a stale fast-but-wrong cache root.
- Structured/regex constrained MiniMax lanes reached about `94 tok/s`, but
  those are task-specific lanes, not general chat decode claims.
- Site-labeled timing, tiny-collective policies, warm-cache repeat gates, and
  MoE-output collective placement are the most useful transfers to Qwen.

Rejected MiniMax paths worth remembering:

- N-gram, DFlash, native MTP, EP4, topology shortcuts, chunked logits gather,
  and no-clone paths repeatedly failed quality, liveness, or repeatability.
- INT4/AutoRound/llm-scaler u4 kernels are not Qwen substitutions. Only their
  dispatch and instrumentation patterns transfer.

## Cross-Cutting Rules To Preserve

1. Promote only after exact model, exact command, cache root, runtime libraries,
   sentinel/canary proof, and repeat metrics are recorded.

2. Separate cold compile, direct-loaded warm cache, and persistent-engine
   steady state. They are different products and should not share one number.

3. Treat sub-`~1 tok/s` deltas as noise unless adjacent control/candidate A/B
   repeats hold up.

4. For current Qwen W8A8, keep the next high-signal work on:
   site-labeled all-rank layer/collective timing, collective-only replay,
   attention/KV placement audit, persistent W8A8 MoE layerlet with output
   collective handling, and oracle `k=1` parity repair.

5. Keep raw logs out of commits unless they become reproducibility artifacts.
   Commit compact JSON/Markdown summaries and source patches instead.
