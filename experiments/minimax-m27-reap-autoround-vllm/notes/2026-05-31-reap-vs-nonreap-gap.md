# 2026-05-31 REAP Versus Non-REAP Gap

REAP is not much faster than the current non-REAP MiniMax M2.7 AutoRound lane
because it does not materially reduce the per-token active compute on the path we
are using today.

Current facts:

- REAP checkpoint: `MJPansa/MiniMax-M2.7-REAP-172B-A10B-AutoRound-W4A16`
- REAP total routed experts: `192`
- Existing non-REAP MiniMax lane total routed experts: `256`
- Active experts per token remain `8`
- Layer count, hidden size, intermediate size, attention path, TP4 collectives,
  graph boundaries, and decode scheduling remain essentially the same class of
  work.

The smaller expert pool helps storage, download size, and VRAM residency. It does
not divide decode compute by `192 / 256`, because each generated token still
executes the same top-k active expert count and still pays the same attention,
router, allreduce, launch, graph, and synchronization costs.

The second reason is implementation maturity. The non-REAP production path has a
more mature MiniMax logits WS path. REAP required E=192 repairs, and the repaired
MiniMax logits/logits-WS path is not promoted because it is either slower or still
fragile under graph integration:

- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS=1`: `72.44384428157205 output tok/s`
- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`: repaired enough to load in
  some paths, but not stable/fast enough to promote
- promoted REAP path keeps `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=0`

So the current result is mostly measuring the same active MoE and attention
pipeline with a smaller resident model, not a fundamentally cheaper decode path.
The latest REAP best, `89.49922316987691 output tok/s`, is a good fit and
quality-gated result, but it is only a small improvement over the public non-REAP
MiniMax lane and not a clear architectural win yet.

Likely sources of real upside:

- make the E=192 MiniMax logits WS path graph-safe and faster than the
  conservative path
- inspect whether REAP's smaller router/top-k shape can remove memory movement or
  synchronization work rather than only changing resident expert count
- profile decode with per-layer timing to separate MoE, attention, collectives,
  graph replay, and logits costs
- keep cache experiments isolated because fresh-cache and warmed-cache behavior
  are still different enough to hide false positives
- look for deeper fusion around Q/K RMS, attention/KV handoff, MoE output
  allreduce, and final logits rather than relying on simple env sweeps
