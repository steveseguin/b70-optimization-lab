# Fused QNorm/RoPE/KV-insert record

Date: **2026-07-15**

Status: **promoted; new strict TP4 single-session record**.

## Boundary

The production XPU decode path launched one Triton program for per-head Q
RMSNorm plus Q/KV RoPE, materialized a temporary BF16 `[1,512]` KV row, then
launched a second Triton program to quantize and insert that row into the paged
UE8M0 FP8 cache. This occurs in all 43 layers.

vLLM `3a74a38a3c2e98bd6c409e57e72011933a8148c8` adds a guarded M=1
program selected by `VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT=1`. Its Q branch
retains the existing program arithmetic. Its KV branch keeps the previous BF16
RoPE rounding point inside registers, then performs the same seven per-64 OCP
E4M3 quantizations and writes the cache directly. It removes the temporary and
one graph node without weakening the numerical contract. M>1 remains on the
old path.

## Exact four-card gate

Every B70 passed 40 changing eager inputs and eight changing XPU graph replays
bit-for-bit for both the Q tensor and every cache byte. Replays changed on all
eight epochs, ruling out stale output.

| Card | Existing boundary | Fused | Speedup | Projected saving over 43 layers |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 77.202 us | 37.033 us | 2.085x | 1.727 ms/token |
| 1 | 81.103 us | 39.758 us | 2.040x | 1.778 ms/token |
| 2 | 71.592 us | 35.500 us | 2.017x | 1.552 ms/token |
| 3 | 73.955 us | 36.234 us | 2.041x | 1.622 ms/token |

Raw microgates are
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/fused-qnorm-rope-kv-insert-card{0,1,2,3}-20260715Tfusedqkv1.json`.

## Full-model result

The candidate retained the prior 40 tok/s identity and changed only the new
fusion flag. Six alternating cold requests returned
`1073, 437, 1073, 437, 1073, 437`, all with `cached_tokens=0`. Two strict fixed
12-prompt suites passed every freshness and token-timing gate:

- headline median **40.135724 tok/s**, p10 39.827848, mean 40.152379;
- confirmation median **40.103728 tok/s**, p10 39.807378;
- headline median wall rate 37.968264 tok/s and TTFT 156.901 ms.

Both exceed the prior public 40.020972 tok/s record. The same-commit flag-off
control was 40.094966 tok/s, so the paired uplift is only 0.022-0.102%. Most of
the isolated event saving is hidden or offset inside reusable command-graph
execution, but removing a real node remains a repeatable record gain. This
contrasts with the rejected native dual-RMSNorm substitution, which sped up an
isolated kernel but did not remove a graph boundary and regressed end to end.

LocalMaxxing approved the result as `cmrm601ig1hsmmj017npoivfd`. Evidence is
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/fused-qnorm-rope-kv-insert-candidate-20260715T1040Z`.

## Next boundary

Keep this fusion enabled. The next nonspeculative candidate should eliminate
the preceding WQ_B BF16 output boundary, ideally producing normalized/rotated Q
directly from an Xe2 FP8xBF16 projection epilogue while retaining the direct KV
cache insert. Require raw Q/cache parity, 40 changing inputs, eight graph
replays, and at least 0.50 ms/token projected slowest-rank saving before a
server load.
