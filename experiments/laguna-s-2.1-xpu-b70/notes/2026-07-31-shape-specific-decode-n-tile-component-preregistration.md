# Laguna shape-specific decode N-tile component preregistration

Date: 2026-07-31 America/Toronto

Status: **component diagnostic authorized; no endpoint authorized**.

## Question

The earlier width-12 endpoint sweep established that applying generic N32 or
N128 to both grouped-GEMM shapes loses to N64. It did not measure W13 and W2
separately. The exact-mainloop component result now shows that the two shapes
can respond in opposite directions to the same code treatment. A hybrid tile
policy could therefore outperform all three global choices even though both
global alternatives lost.

## Frozen component

Use the ABI-correct `ec507e8b0` DSO at SHA-256
`888d0fd33bf1b355e534b3eda7ea6be2a1d924fc7686f9bdfd2ad0cec6edabf5`.
Keep GRF128 on, exact-mainloop specialization off, scale-vector on, MAD/fold
off, and prefetch distance 6. On one B70, run the identical changed-input
W13 (`M=120,N=2048,K=3072`) and W2 (`M=120,N=3072,K=1024`) corpus at generic
N tiles 32, 64, and 128. Require every raw BF16 output hash to equal N64.

Compare these possible hybrid sums against N64+N64:

- N32 W13 + N64 W2;
- N128 W13 + N64 W2;
- N64 W13 + N32 W2;
- N64 W13 + N128 W2; and
- the best independently selected W13/W2 pair.

Stop unless a bitwise-exact hybrid improves the summed component median by at
least `1.5%`. A pass authorizes source design for shape-specific dispatch, not
an endpoint. No model service, score, reboot, reset, or submission is
authorized here.

## Result and closure

All three tiles were raw-BF16 exact on both shapes. Medians in milliseconds:

| N tile | W13 | W2 |
| ---: | ---: | ---: |
| 32 | 0.368387200 | 0.190762950 |
| 64 | 0.361346500 | **0.179260350** |
| 128 | **0.358837750** | 0.180853350 |

The best hybrid is W13=N128 plus W2=N64: `0.538098100 ms` versus
`0.540606850 ms` for N64+N64, only **0.4662%** faster. It misses the 1.5%
component gate, so no shape-specific source change or endpoint is authorized.
Artifact:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-shape-tile-component-ec507e8-20260731T1055Z`.

This closes the ambiguity left by the earlier global endpoint sweep: N128
does help W13 slightly, but the independently optimal hybrid is far too small
to explain or close the remaining throughput gap.
