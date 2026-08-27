# Qwen3.8 FP8 strict single-user profile matrix result

## Decision

No official-FP8 TP2 single-user profile qualifies for a public headline.
Every attempt completed the frozen 12-prompt, six-class, 512-token-cap workload
with zero cached tokens and passed the post-suite objective canaries. None of
the six paired controls reproduced all 12 complete token arrays across its two
server lifetimes. Passing the speed workload and small canaries is therefore
not being mistaken for a quality/determinism pass.

The machine-generated source of truth is the
[matrix summary](../data/2026-08-27-qwen38-fp8-strict-profile-matrix-summary.json),
produced by the checked-in
[summarizer](../scripts/summarize-20260827-qwen38-fp8-strict-matrix.py).

## Measured diagnostic results

The rate is the preregistered median of the six prompt-class medians over the
99 intervals between streamed generated-token events 1 through 100. These are
diagnostic observations, not package headlines.

| Exact profile | Attempt A | Attempt B | Complete output agreement | Decision |
| --- | ---: | ---: | ---: | --- |
| W8A16, MTP0, PIECEWISE/XPU Graph | `34.772270` | `34.740755` | `8/12` | withheld |
| W8A16, MTP1, PIECEWISE/XPU Graph | `55.760069` | `55.782147` | `8/12` | withheld; A matched MTP0 A on only `6/12` |
| W8A16, dynamic MTP8 at c1 | `68.049727` | `62.432362` | `8/12` | withheld; A matched MTP0 A on only `9/12` |
| W8A16, MTP0, identical sealed compiled-cache copies | `34.744004` | `34.734494` | `10/12` | withheld |
| W8A16, MTP0, graph/compile off (eager) | `18.808798` | `18.535435` | `10/12` | withheld |
| Stock FP8 dispatch, MTP0, graph/compile off (eager) | `16.607024` | `16.413138` | `8/12` | withheld |

Dynamic MTP's large attempt-to-attempt throughput spread is real for this
varied workload and follows its acceptance behavior; it is another reason not
to reduce that profile to a selected short fixture.

## What the controls establish

- Fresh compilation is not the sole cause: the sealed-cache pair began from
  byte-identical copies and still diverged on two prompts.
- XPU Graph is not required: the W8A16 eager pair still diverged on two
  prompts.
- The lab W8A16 dispatch is not required: the default-off eager pair diverged
  on four prompts.
- Speculation cannot be promoted around the problem: MTP1 and dynamic MTP
  both failed fresh-server equality and exact target-array parity.

The subsequent one-card eager/default-dispatch control also matched only
`8/12` complete outputs at `11.405360`/`11.413057 tok/s`. TP2 and cross-rank
oneCCL are therefore not required either; see the
[TP1 result](2026-08-27-qwen38-fp8-tp1-strict-target-control-result.md).
The remaining diagnosis belongs to the one-rank official-FP8 target/runtime
surface, not to a performance-fixture exception. The experiment does **not** prove
semantic degradation, but it fails the lab's deliberately stricter
no-unadjudicated-output-change rule. No equality threshold was weakened.

## Publication and next work

- Keep the package's single-user cells blank and expose the measured ranges
  only as clearly labeled failed-gate diagnostics.
- Retain the independently qualified MTP0 32K and MTP0/MTP1 short-context
  aggregate results under their exact scopes.
- Do not spend a 32K MTP1 publication run while its short strict target-parity
  gate is failing. That cell is withheld by correctness, not estimated.
- TP1 strict target control is complete and failed `8/12`; do not spend a TP2
  P2P-off run on the disproven cross-rank hypothesis.
- The full AutoRound INT4/MTP5 server remains excluded from this 15 GiB host;
  preserve its existing research result and do not invent the missing cells.

The frozen protocol is in the
[matrix preregistration](2026-08-27-qwen38-fp8-strict-profile-matrix-prereg.md).
