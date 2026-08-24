# Ornith 1.5 35B-A3B: shared gate plus residual/RMS fusion

Date: 2026-08-23 EDT

Status: **ACCEPTED — twelfth source feature**

Ornith's Qwen-derived shared-expert branch computes a one-element FP32 gate,
sigmoid, and a broadcast multiply immediately before the already accepted
routed/shared/residual/RMSNorm fusion. An earlier conservative candidate
replaced sigmoid plus multiply with one separate launch and regressed serving.
This candidate instead folds both operations into the existing fusion launch,
removing two launches in each of 40 MoE layers: **80 launches/token**.

The default-off matcher begins only at a named
`shared_expert_gate_sigmoid-*` node and requires the exact six-node chain,
one-use non-output intermediates, FP32 scalar and 2,048-element layouts, and
eligibility for the accepted shared/residual/RMS path. The kernel computes the
stock sigmoid expression and materializes the gated shared output, routed plus
shared output, and residual output through their original FP32 buffers before
the unchanged RMS reduction. This preserves all graph-visible rounding
boundaries.

## Correctness

The four-token smoke run recorded 120 intended hits. The forced canonical
128-token candidate recorded 5,080 hits and produced transcript SHA-256
`2e7965fcdc273f0433df359cff5188ae3585426fd32f28536121d1b5e35dad18`,
identical to the same-frozen-binary flag-off control and the accepted package
record.

## Matched performance

Mirrored depth-zero `tg128`, seven-repetition A/B/B/A:

| Arm | Decode (tok/s) | Within-run standard deviation |
| --- | ---: | ---: |
| Control A | 132.959645 | 1.623436 |
| Candidate A | 134.643526 | 1.666358 |
| Candidate B | 134.484529 | 1.699675 |
| Control B | 132.890786 | 1.948579 |

Control mean was 132.925216 tok/s and candidate mean was 134.564028 tok/s:
**+1.233%**, with both candidates above both controls.

The decisive fresh-server A/B/B/A used the fixed 12-prompt suite, one unique
request per prompt, up to 512 generated tokens, the tokens 1-100 metric, prompt
cache disabled, and a new server process for every arm. All four runs passed
the final gate and reported `cached_tokens=0` for every row.

| Arm | Conventional 99-interval median (tok/s) | Legacy 100-event compatibility median (tok/s) |
| --- | ---: | ---: |
| Control A | 130.810942 | 132.132265 |
| Candidate A | 130.451371 | 131.769061 |
| Candidate B | 132.469090 | 133.807162 |
| Control B | 128.540399 | 129.838787 |

The preferred conventional mean of the two run medians improved
`129.675671 -> 131.460231 tok/s` (**+1.376%**). Across the 24 rows per arm,
the conventional pooled median improved `129.059262 -> 131.780063 tok/s`
(+2.108%) and pooled mean improved `125.334466 -> 127.450520 tok/s`
(+1.688%). Candidate two-run averages beat control two-run averages on
**12/12 prompt IDs**. The originally captured `130.985526 -> 132.788112`
means are retained as legacy compatibility accounting, not the headline.

The complete twelve-feature patch is
`../../../patches/ornith-15-35b-a3b-q4km-b70/llama-cpp-ornith15-twelve-feature-stack-shared-gate-residual-rms-20260823.patch`
(SHA-256 `7b9204f8f44608fc5b1858a15498b3cf9bf52b4f02c27c0f91a1807af5b5d15d`).
The incremental patch is
`../patches/llamacpp-ornith15-shared-gate-residual-rms-positive-20260823.patch`.
Structured results and raw records are under `../data/ornith-gate-resid-*`.

The source now has twelve accepted features and removes 780 decode launches
per token. The directly measured current conventional serving headline is the
mean of the two candidate suite medians: **131.460231 tok/s**. The legacy
compatibility mean remains **132.788112 tok/s**. A separate twelve-feature
0-32K sweep was subsequently measured at all seven displayed depths; no curve
point was scaled or inferred. See
`2026-08-23-ornith35b-twelve-feature-depth-sweep.md`.
