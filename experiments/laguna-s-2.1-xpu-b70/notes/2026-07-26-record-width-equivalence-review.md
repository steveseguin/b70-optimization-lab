# Laguna — static review: the record path is unchanged by the width work

Date: 2026-07-26 America/Toronto

Status: **static verification only, no GPU.** Performed while the box is
unusable following the `xe` GuC fault. Approved record remains **94.920039**
tok/s; goal of 102 not met.

## Why this review exists

Fifteen width pins were parameterized behind `VLLM_XPU_LAGUNA_EXACT_MAX_M`
across `linear.py`, `flash_attn.py`, `gpu_model_runner.py`, `laguna.py`, and
`laguna_m8_collectives.py`. Before a scarce post-recovery verification run is
spent, the cheap question is whether any of them can alter the record path at
the default width.

## Result: every width-gated site reduces to its original literal at default 8

Executed with the environment variable unset:

| site | value | expected |
| --- | ---: | ---: |
| `envs.VLLM_XPU_LAGUNA_EXACT_MAX_M` | 8 | 8 |
| `linear.xpu_laguna_exact_max_m()` | 8 | 8 |
| `flash_attn._xpu_exact_spec_max_q()` | 8 | 8 |
| `laguna_m8_collectives._ROWS` | 8 | 8 |
| spec depth (`max_m - 1`) | 7 | 7 |
| `cu_seqlens` length (`max_q + 1`) | 9 | 9 |
| prebuilt width range | `[2..8]` | `[2..8]` |

Each substitution replaces a literal `8`, `9`, or `7` with a helper returning
the environment value, so at the default every predicate, buffer size, and
range is bit-identical to the record source. This is evidence about the
*predicates*, not a claim that the record throughput is unchanged; that still
requires a measured width-8 run after driver recovery.

## Behavioural change found and corrected

One change was not a no-op. Making the collective gather count "learned and
asserted stable" was introduced to get past the 96-slot assertion at width 12,
but it normalized a regression: per-row serialization inflated the topology from
the audited 96 gathers to several hundred, and a learned count accepted that
silently. External review flagged this correctly.

Corrected: at the record width the count is the audited constant again and is
asserted outright, restoring the original guarantee. At other widths it is still
learned, but a count exceeding 1.5x the audited topology now raises, naming
per-row serialization as the usual cause. An explosion can no longer be measured
as if it were legitimate.

Tests after the change: breakable graph 36 passed with 11 expected skips; cycle
attribution 14 passed.

## Still unverified, and why

The three batched-M1 bound fixes — column-parallel, row-parallel, and
replicated — are the intended cure for the 685/684 topology. They are
statically confirmed to be no-ops at width 8 and to admit width 12, but whether
they actually restore a topology near 146/145 is **untested**: the GuC fault
interrupted verification before any width-12 run reached capture.

## Post-recovery order

1. Width 8 at the record commit: startup completes, 146/145 captures, scored
   median near 94.920.
2. Width 8 at current HEAD: same three checks, confirming the parameterization
   is inert in practice as well as in predicate.
3. Width 12: does the topology land near 146/145, and does it stay exact.
4. Only then measure throughput, and only then consider the width-two tree,
   which remains required for 102.
