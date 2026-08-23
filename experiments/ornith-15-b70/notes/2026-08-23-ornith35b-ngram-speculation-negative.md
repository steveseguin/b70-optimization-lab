# Ornith 1.5 35B-A3B: no-model n-gram speculation is negative

Date: 2026-08-23 EDT

Status: **CLOSED NEGATIVE — keep the public recipe target-only**

After the remaining small launch fusions proved server-neutral, llama.cpp's
target-verified n-gram speculation was screened as a separately labelled
assisted mode. It uses no draft model, but it still proposes multiple tokens
and makes the target verify them in batches. It must therefore earn its cost
through acceptance; its throughput is not interchangeable with the target-only
anchor.

On the exact published six-fusion library
`3887af763ac560ca277dd224ded611b083798dd27f149b7caf886c831460f637`,
the fresh realistic suite measured:

| Arm | Configuration | Median tok/s | Delta |
| --- | --- | ---: | ---: |
| target only | `--spec-type none` | **113.000242** | — |
| n-gram default | `ngram-simple`, N=12, M=48 | **96.423720** | **-14.67%** |

Both complete runs passed all freshness/finality gates. The n-gram server
reported only 22 accepted tokens from 336 generated draft tokens across the
seven requests where it logged a proposal (6.55% reported acceptance). The
48-token verification blocks therefore cost far more than they saved.

A bounded shorter profile (`N=4`, `M=8`) was also attempted. It reported the
first response generation at 79.86 tok/s, then failed to finalize the HTTP
stream/task or begin request two while remaining GPU-active. The process was
terminated after 3m44s. That arm is a server-hang negative, not performance
evidence.

Do not enable generic n-gram speculation in the Ornith guide. A future assisted
lane needs either a genuinely fast compatible draft model or a workload-specific
static corpus with measured acceptance. It must remain separately labelled and
pass the same fresh-suite and correctness gates.

Structured conclusion and complete-run JSON are under
`../data/2026-08-23-ornith35b-ngram-*`; the default and hang logs preserve the
reported acceptance and failure evidence.
