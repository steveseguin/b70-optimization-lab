# MiniMax Post-89 MoE Up Follow-Up Plan

Date: 2026-05-20

## Current State

Promoted MiniMax M2.7 AutoRound remains `89.314195` output tok/s / `119.085594` total tok/s at p512/n1536, ctx2048, batch 1, TP4 on 4x B70. The LocalMaxxing promoted result is `cmpct6t4m007fnw01yjdtlcs4`.

The 2026-05-20 MoE kernel trace shows the llm-scaler work-sharing routed up projection is much heavier than the down projection, but simple tile-size tuning did not improve throughput:

- `VLLM_XPU_MOE_WS_UP_NTILE=1`: raw145 n64 exact pass, `87.718075` output tok/s, rejected.
- `VLLM_XPU_MOE_WS_UP_NTILE=3`: raw145 n64 exact pass, `88.323997` output tok/s, rejected.
- `VLLM_XPU_MOE_WS_UP_NTILE=6`: raw145 n64 exact pass, `80.823931` output tok/s, rejected.

Keep `VLLM_XPU_MOE_WS_UP_NTILE` unset for promoted runs.

## Updated Direction

The next credible >89 tok/s path is not another high-level wrapper or simple tile knob. The remaining work should focus on one of these lower-level changes:

1. MoE up-kernel layout/refactor: reduce repeated activation loads without adding accumulator pressure. The existing `N_TILE=2` default appears near the best register/load balance for the current kernel shape.
2. Router/top-k/up boundary fusion: move more of `router_logits -> top8 -> routed up` into one backend boundary only if exact FP32 biased MiniMax top-k semantics are preserved.
3. Hidden-state collective epilogues: revisit attention `o_proj` or MoE-output allreduce only as a backend-level epilogue/fusion, since Python custom-op wrapping and direct allreduce replacement were quality-clean but slower.
4. Q/K variance collective: only pursue a graph-safe XPU/XCCL-backed path; Level Zero peer-memory polling and global oneCCL algorithm overrides are exhausted for now.

## Promotion Guardrails

A candidate must pass, in order:

- raw145 n64 exact hash before speed screening.
- raw145 n256 exact hash if the speed screen is promising.
- semantic canary suite.
- arithmetic repeat suite.
- extended sixpack.
- at least four p512/n1536 repeats with mean output tok/s above `89.314195` by more than normal noise.

Submit to LocalMaxxing only after the full strict gate passes and the speed improvement is repeatable. Negative or learning-only results should stay GitHub-only.

## Immediate Next Candidate Ideas

- Add richer diagnostic tracing around the MoE up routed kernel to attribute time by shape/forced tile without synchronizing every kernel in promoted runs.
- Prototype a layout-aware up-kernel variant that caches/reuses the activation vector more efficiently across nearby columns while keeping accumulator count at or below the current `N_TILE=2` pressure.
- If MoE up refactor is too invasive, switch back to the hidden-state collective path and inspect whether a lower-level allreduce+epilogue can be implemented without Python scheduling overhead.
