# Qwen3.8 Q8 c2 batch-shape and broader quality audit

Date: 2026-08-16  
Status: **no speed promotion; broader exact-output gate failed**

The accepted target-only Q8 server was tested at concurrency two with four
batch/ubatch shapes. Model bytes, binary, tensor split, F16 KV, two synchronized
256-token requests, cache-off policy, and all optimization doors were fixed.
There was no MTP, DFlash, draft model, or speculative acceptance.

| Batch / ubatch | Prompt pair | Aggregate conventional | Exact to sequential |
| --- | --- | ---: | ---: |
| `1024 / 256` | 0/1 | `55.001916 tok/s` | 1/2 |
| `2048 / 512` | 0/1 | `57.378446 tok/s` | 2/2 |
| `4096 / 1024` | 0/1 | `57.395247 tok/s` | 2/2 |
| `8192 / 2048` | 0/1 | `57.483594 tok/s` | 2/2 |
| `2048 / 512` repeat | 0/1 | `57.395772 tok/s` | 2/2 |
| `8192 / 2048` repeat | 0/1 | `56.309389 tok/s` | 2/2 |
| `2048 / 512` broader gate | 2/3 | `57.285645 tok/s` | **0/2** |

All requests reported `cache_n=0`. The full deep-batch shape did not retain its
apparent high on repeat, and none exceeded the existing `57.398122 tok/s`
narrow c2 capture outside run variance.

More importantly, `2048/512` did not eliminate schedule-dependent greedy
outputs. It passed two repeated prompt-0/1 comparisons, then both prompts in
the disjoint prompt-2/3 pair differed from their same-process sequential
oracles. This confirms that larger routing batches are not a general exactness
repair. Under the lab's strict quality policy, the c2 number remains only a
fixed-prompt service-capacity result; it must not be generalized to arbitrary
requests or replace the exact single-request record.

The reproduction keeps `1024/256` as its published default. Its server launcher
now accepts `QWEN38_C2_BATCH` and `QWEN38_C2_UBATCH` for explicit research
replays, and the capture harness accepts `--prompt-offset` so disjoint fixed
prompt pairs can be audited rather than repeatedly testing one favorable pair.

Structured evidence is in
[`data/2026-08-16-q8-c2-batch-shape-audit.json`](../data/2026-08-16-q8-c2-batch-shape-audit.json).
The hashed raw captures remain under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-c2-batch-sweep`.
