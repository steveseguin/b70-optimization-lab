# Qwen3.8 Q8 selective 256-GRF MMVQ: negative

Date: 2026-08-16

## Hypothesis

Intel's current compiler exposes the standardized per-kernel
`sycl_ext_intel_grf_size` property. Applying `grf_size<256>` only to the four
hot reordered-Q8 launch families could provide more accumulator space without
the workgroup failures caused by the older global large-GRF option.

The property was applied to the standalone, pair, triple, and recurrent-quad
Q8 MMVQ launches. The candidate was a separate IntelLLVM 2026.1.1 Release/AOT
BMG-G31 build. Its MMVQ object and SYCL library hashes differed from control.

## Result

The candidate launched correctly, unlike the earlier global option. Its real
TP2 p0/n1 smoke preserved the full fusion census, reported
`VERIFY_MISMATCH=0`, and passed the post-process GPU health gate. A
position-balanced A-B-B-A bracket then used p64/n256/r3, equal tensor split,
Q8_0 target weights, F16 KV, FlashAttention, b1024/ub256, direct-Q8 mode 2,
and no speculation.

| Position | Arm | Decode tok/s | Within-process stdev |
| --- | --- | ---: | ---: |
| A1 | accepted control | 36.005708 | 0.048577 |
| B1 | selective GRF256 | 35.402057 | 0.022232 |
| B2 | selective GRF256 | 35.400716 | 0.005362 |
| A2 | accepted control | 36.828693 | 0.037403 |

Control averaged `36.4172005 tok/s`; selective GRF256 averaged
`35.4013865 tok/s`. The candidate regressed decode by `2.789%`. The remarkably
stable candidate measurements make this an unambiguous rejection, not noise.
The likely mechanism is reduced hardware occupancy outweighing any benefit
from the larger register allocation.

No endpoint or semantic-quality suite was spent on a clearly slower candidate.
The property is not in the promoted reproduction.

## Reproduction and retained evidence

- incremental patch: [q8-selective-grf256-negative-20260816.diff](../patches/q8-selective-grf256-negative-20260816.diff)
- structured result: [2026-08-16-q8-selective-grf256-negative.json](../data/2026-08-16-q8-selective-grf256-negative.json)
- local source: `/mnt/fast-ai/src/llama.cpp-q38-q8-selective-grf256`
- local logs: `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-selective-grf256`

Apply the incremental patch only after the accepted Qwen3.8 Q8 full patch.

