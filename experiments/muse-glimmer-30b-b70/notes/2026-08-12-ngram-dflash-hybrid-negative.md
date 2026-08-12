# N-gram plus DFlash hybrid: negative

Date: 2026-08-12

## Decision

Keep DFlash alone. Both target-exact composed n-gram configurations were
slower on the fixed three-class suite. Do not spend more GPU windows on this
lane without new offline evidence.

No drafter training or weight changes were performed.

## Harness correction

The sweep runner previously hard-coded `--spec-type draft-dflash`. Appending a
second `--spec-type` in a config did not override it, so the first attempted
hybrid was actually DFlash-only. That mislabeled result is excluded but kept:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/exact-stack-ngram-hybrid-ab-20260812.jsonl`;
- SHA-256 `5b37061a9b743ce602cc1a6a9839f040750e3b9bb04f2f874b5bf2c545732628`.

`bringup-sweep.py` now accepts one `spec_type` field per arm and emits exactly
one unambiguous argument.

## Corrected results

All arms use the exact kernel stack. `ngram-simple` has priority and DFlash is
the fallback.

| Configuration | Prose | Code | JSON | Mean | Delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| DFlash control for 12x48 | 45.668 | 68.202 | 80.676 | 64.849 | reference |
| ngram 12x48 + DFlash | 44.821 | 64.535 | 75.870 | 61.742 | **-4.79%** |
| DFlash control for 4x15 | 45.914 | 66.747 | 80.930 | 64.530 | reference |
| ngram 4x15 + DFlash | 45.539 | 64.927 | 78.243 | 62.903 | **-2.52%** |

The shorter lookup did not help even though its maximum proposal width equals
the DFlash block width. Acceptance fell in every 4x15 class. The 12x48 path
also lost in all classes and paid for a wider target batch when a long repeat
was proposed.

Corrected raw results:

- 12x48: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/exact-stack-ngram-hybrid-corrected-ab-20260812.jsonl`, SHA-256 `8cfeaaa3db9306d98e21609c2f1a1312985722e234ff81aca111dc100d3c59e4`;
- 4x15: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/exact-stack-ngram4x15-hybrid-ab-20260812.jsonl`, SHA-256 `268b4feced813d59246b4719861d174e596ca30c39f87f4ff758ca2625564cfe`.

Production was restored on the incumbent binary after every window.
