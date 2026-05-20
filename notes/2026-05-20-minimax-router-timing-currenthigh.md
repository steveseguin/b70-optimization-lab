# MiniMax M2.7 Current-High Router/MoE Timing

Date: 2026-05-20

## Summary

Ran a diagnostic-only rank-0 synchronized timing pass on the current promoted MiniMax M2.7 AutoRound stack. This was not a throughput submission: the run used eager execution plus explicit timing synchronization to expose decode buckets.

The timing confirms that router materialization is real but not the largest visible decode cost. The earlier all-256 candidate-repair router/top-k kernel is exact but too slow, so the next source-level work should stay inside the existing MiniMax MoE custom-kernel path unless a better optimized router GEMV/top-k kernel is built.

## Artifacts

- Log: `/home/steve/bench-results/minimax-m2.7-router-timing-20260520/vllm-minimax-m27-autoround-tp4-p512n16-20260520T053900Z.log`
- JSON: `/home/steve/bench-results/minimax-m2.7-router-timing-20260520/vllm-minimax-m27-autoround-tp4-p512n16-20260520T053900Z.json`
- Runtime manifest: `/home/steve/bench-results/minimax-m2.7-router-timing-20260520/vllm-minimax-m27-autoround-tp4-p512n16-20260520T053900Z.runtime.json`
- Summary data: `data/minimax-m27-router-timing-currenthigh-20260520.json`

## Rank-0 Timing Buckets

The largest synchronized buckets after the warmup skip were:

- `minimax.moe.experts_total`: `761.638096 ms` total, `1052` calls, `0.723991 ms` average.
- `minimax.attn.qk_norm`: `245.740082 ms` total, `1052` calls, `0.233593 ms` average.
- `minimax.attn.o_proj`: `219.014477 ms` total, `1052` calls, `0.208189 ms` average.
- `all_reduce:(1, 3072):torch.float16`: `174.398713 ms` total, `1936` calls, `0.090082 ms` average.
- `minimax.attn.kv_attention`: `164.463027 ms` total, `1052` calls, `0.156334 ms` average.
- `minimax.moe.router_linear`: `130.100623 ms` total, `1052` calls, `0.123670 ms` average.
- `all_reduce:(1, 2):torch.float32`: `75.310987 ms` total, `928` calls, `0.081154 ms` average.

## Interpretation

The router-linear bucket is worth watching, but the existing exact candidate-repair kernel is not viable. In standalone testing it matched top-k ids and weights, but took roughly `0.52-0.66 ms` for decode token counts where the current router linear measured about `0.02-0.03 ms`.

The next credible math-preserving candidate is therefore narrower: reduce decode-time allocation and dispatch overhead in `moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws` while preserving FP32 route weights, exact top-k, and the promoted output hashes. This should be behind a default-off flag and must pass the full strict quality suite before any throughput result is promoted.
