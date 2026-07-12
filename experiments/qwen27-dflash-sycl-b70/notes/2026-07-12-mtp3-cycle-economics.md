# 2026-07-12 MTP3 cycle economics

## Result

An opt-in, server-only diagnostic measured the complete validated AOT
production fusion stack on the 12-prompt strict realistic suite.  The run
passed the strict gate, all requests reported `cached_tokens=0`, and the normal
headline calculation was `51.694 tok/s`.  The diagnostic added phase logging
but did not add device events or kernel barriers.

Across 538 speculative cycles:

- verifier widths were `{4: 537, 3: 1}`; there were no width-2 cycles;
- accepted-draft counts were `{0: 100, 1: 121, 2: 110, 3: 207}`;
- `962 / 1613 = 59.64%` draft candidates were accepted;
- 1500 tokens were emitted, or `2.7881` emitted tokens per cycle.

The single width-3 verifier was an end-of-request truncation.  MTP3 is
therefore effectively always an M=4 target verification workload; it does not
normally obtain cheaper M=2/M=3 target calls after an early draft mismatch.

## Exact phase reconciliation

Median phase intervals were:

| phase | median | share of accounted median |
| --- | ---: | ---: |
| target M=4 verification | `45.646 ms` | `80.3%` |
| three-pass draft preparation | `9.700 ms` | `17.1%` |
| target-to-MTP state processing | `0.936 ms` | `1.6%` |
| sampling and acceptance | `0.621 ms` | `1.1%` |
| rollback/sequence trim and result commit | `0.009 ms` | `<0.1%` |
| phase sum | `56.848 ms` | `100%` |
| accept-to-accept wall interval | `56.861 ms` | — |
| residual | `0.016 ms` | — |

The fresh draft measurement is an exact blocking wall interval for all three
MTP draft decodes.  The prior native-event diagnostic splits its four repeated
55-node state/draft graphs into one `0.70-0.73 ms` state graph followed by
three `2.97-3.07 ms` draft graphs.  The fresh `9.700 ms` aggregate is consistent
with that direct-device split.  Native-event evidence is retained at:

`/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/mtp3-native-cycle-verbose-20260712T164945Z/`

The important correction is that rollback, sampler coordination, and result
commit are not a multi-millisecond mystery bucket.  Together they are about
`0.63 ms`; target verification itself dominates the cycle.

## Prompt dependence

Acceptance varied materially across the realistic suite:

| prompt | acceptance | emitted/cycle |
| --- | ---: | ---: |
| incident-retrospective | `70.8%` | `3.125` |
| code-review | `54.2%` | `2.625` |
| customer-email | `62.1%` | `2.864` |
| sql-debugging | `63.6%` | `2.907` |
| release-plan | `60.6%` | `2.818` |
| benchmark-analysis | `51.7%` | `2.551` |
| architecture-tradeoff | `62.8%` | `2.884` |
| bug-report-synthesis | `55.3%` | `2.660` |
| technical-guide | `63.6%` | `2.907` |
| risk-register | `56.4%` | `2.681` |
| performance-hypotheses | `50.3%` | `2.510` |
| decision-memo | `69.1%` | `3.073` |

This acceptance range changes emitted tokens per cycle but does not change the
target verifier cost: almost every cycle still verifies four rows.

## 68 and 100 tok/s budgets

At the measured `2.7881` emitted tokens per cycle:

- `68 tok/s` permits `41.002 ms/cycle`, requiring a `15.85 ms` (`27.9%`)
  reduction from the measured phase sum;
- `100 tok/s` permits `27.881 ms/cycle`, requiring a `28.97 ms` (`51.0%`)
  reduction.

Keeping all non-target work unchanged gives the target verifier these hard
budgets:

- at 68 tok/s, at most about `29.80 ms`, a `34.7%` target reduction;
- at 100 tok/s, at most about `16.68 ms`, a `63.4%` target reduction.

Even deleting the entire current draft cost would leave approximately
`47.15 ms/cycle`, only about `59.1 tok/s`.  Draft optimization alone therefore
cannot reach 68 tok/s.  The dominant actionable stage is the M=4 target
verifier: it needs a materially faster multi-row projection path and/or fusion
that removes work inside that 45.6 ms call.  The next target should be
`<30 ms` verification for 68 tok/s and ultimately approximately `16-17 ms`
with the current non-target costs for 100 tok/s.

## Artifacts

- structured summary:
  `data/qwen27-mtp-cycle-economics-20260712T203856Z/cycle-economics.json`;
- strict result and raw server log:
  `/mnt/fast-ai/bench-results/qwen27-dflash-sycl-b70/mtp-cycle-economics-20260712T203856Z/`;
- reusable parser:
  `scripts/summarize-qwen27-mtp-cycle-economics.py`.

The source diagnostic is gated by `LLAMA_MTP_CYCLE_TIMING=1`.  It records
draft preparation, target decode width/time, speculative state processing,
accepted/emitted counts, and acceptance/commit time.  It is inert by default.
