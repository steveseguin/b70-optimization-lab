# Qwen3.8 FP8 TP2 W8A16 MTP2-reuse screen result

Serially reusing Qwen3.8-27B-FP8's one publisher MTP layer for two draft
tokens is a strong single-user result and a poor high-concurrency trade. It
measured **`83.646518 tok/s`** after TTFT on the first declared cache-zero
40-token-prompt/128-token-output response: `+35.57%` over native MTP1 and
`+138.91%` over MTP0 on the same W8A16 target identity.

This is not native two-layer MTP. The checkpoint declares one MTP layer and
contains only `mtp.layers.0`; vLLM runs that layer twice. The runtime warning
that this can lower acceptance is borne out under varied concurrent prompts:
the logged average draft acceptance was about 61–67%, while the repeated
single-user fixture accepted both draft positions at 100%.

## Frozen results

| mode | one user after TTFT | c64 aggregate | qualification |
| --- | ---: | ---: | --- |
| native MTP1, MBT512 | 61.699580 | 1,091.642460 (median of 3) | selected candidate profile |
| MTP2 one-layer reuse, MBT512 | **83.646518** | 737.190110 (1 sample) | research screen |
| MTP2 one-layer reuse, MBT768 | not measured | 712.790232 (1 sample) | scheduler follow-up negative |

Both MTP2 services passed 7/7 sequential semantic cases and 8/8 repeat
stability. Both c64 batches returned all 8,192 token IDs, reported zero cached
prompt tokens, and passed cross-task output isolation. Their greedy outputs
matched their sequential oracles on 57/64 and 58/64 requests respectively,
consistent with the already documented batch-shape dependence.

MBT768 missed the frozen 900 tok/s continuation hurdle and regressed 3.31%
from MBT512. MBT1024 therefore did not run. The MTP2-reuse route closes as an
explicit interactive research profile; it does not replace native MTP1, does
not preserve the aggregate objective, and is not a candidate-package default.
It has no 32K measurement, replicated concurrency result, or concurrent
semantic canary.

The exact structured result is
[`2026-08-26-qwen38-fp8-block-w8a16-mtp2-reuse-summary.json`](../data/2026-08-26-qwen38-fp8-block-w8a16-mtp2-reuse-summary.json).
All reported values are directly measured; none is interpolated or
extrapolated.
