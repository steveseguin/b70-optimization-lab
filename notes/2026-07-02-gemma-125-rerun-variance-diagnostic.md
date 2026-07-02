# 2026-07-02 Gemma 125 vs 120 Rerun Diagnostic

Question: why did the documented Gemma 4 26B A4B Q8 one-B70 repro rerun at
`120.923 tok/s` instead of the promoted `124.977 tok/s`?

## Runs Compared

Promoted record:

- Summary:
  `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`
- Server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z.server.log`
- Validity: fresh-response, fixed realistic suite, each prompt once,
  `cached_tokens=0`, canary `512/512`.
- Primary metric: `124.97714084813418` median tok/s for generated tokens
  1-100 after TTFT.
- Mean / p10: `122.4743547166875` / `103.83610041293295`.
- Full512 after-TTFT median: `114.87107033590775`.
- TTFT median: `178.6938319564797 ms`.

Rerun:

- Summary:
  `data/gemma4-q8-gpu0-125repro-docpass-20260702T231635Z/summary.json`
- Server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-125repro-docpass-20260702T231635Z.server.log`
- Validity: fresh-response, fixed realistic suite, each prompt once,
  `cached_tokens=0`, canary `512/512`.
- Primary metric: `120.92334534956485` median tok/s for generated tokens
  1-100 after TTFT.
- Mean / p10: `118.86003674156144` / `105.95927439380908`.
- Full512 after-TTFT median: `112.61378328154639`.
- TTFT median: `177.91116051375866 ms`.

## Identity Diff

The important runtime identity matched:

- same target model path and model file size: `27636230944` bytes;
- same `llama-server` path and llama.cpp commit: `c926ad098`;
- same `CTX_SIZE=32768`, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`,
  `UBATCH_SIZE=1024`;
- same Q4_0 MTP draft, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `--ctx-checkpoints 0`;
- same key Gemma/MTP/fused-MoE/final-postnorm env flags.

Observed differences were bookkeeping/runtime placement, not recipe drift:
port/base URL, timestamp, suite path under the current checkout, and newer
launcher identity fields recorded as `<missing>` vs `<unset>`.

Both server logs also showed full prompt re-processing for the benchmark
requests, e.g. `forcing full prompt re-processing due to lack of cache data`.
This rules out cached-prefix reuse as the explanation.

## Per-Prompt Movement

The prompt hashes matched exactly across the 12-prompt suite, but all 12 output
hashes differed between the two runs despite `temperature=0`, `top_p=1`, and
`seed=1`. The speed drop is therefore not the same generated text becoming
uniformly slower; it is different continuation paths causing different MTP
acceptance/timing.

First-100 after-TTFT tok/s by prompt:

| prompt | record | rerun | delta |
| --- | ---: | ---: | ---: |
| incident-retrospective | `127.001` | `117.426` | `-7.54%` |
| code-review | `102.704` | `100.953` | `-1.70%` |
| customer-email | `117.277` | `121.422` | `+3.54%` |
| sql-debugging | `134.764` | `111.701` | `-17.11%` |
| release-plan | `114.027` | `121.152` | `+6.25%` |
| benchmark-analysis | `126.346` | `127.281` | `+0.74%` |
| architecture-tradeoff | `138.859` | `131.264` | `-5.47%` |
| bug-report-synthesis | `131.075` | `108.786` | `-17.00%` |
| technical-guide | `120.345` | `120.694` | `+0.29%` |
| risk-register | `131.283` | `132.086` | `+0.61%` |
| performance-hypotheses | `102.404` | `105.645` | `+3.17%` |
| decision-memo | `123.608` | `127.910` | `+3.48%` |

The suite median is the average of the 6th and 7th sorted values:

- record sorted middle: `(123.608 + 126.346) / 2 = 124.977`;
- rerun sorted middle: `(120.694 + 121.152) / 2 = 120.923`.

So the primary metric moved because two early-window content paths fell by about
`17%`, and the middle-rank prompts shifted downward. It was not a broad engine
slowdown.

Server-side full-run timing was much closer than the 1-100 stream metric:

- full eval median: `114.87 -> 112.63 tok/s` (`~2%` lower);
- mean MTP acceptance: `0.5367 -> 0.5459` (slightly higher on the rerun);
- median MTP acceptance: `0.561 -> 0.543` (lower on the rerun).

This supports the same conclusion: the first-100 streaming window is
content/rank sensitive in this recipe.

## Duplicate-Prompt Diagnostic

Diagnostic artifact:

- `data/gemma4-q8-gpu0-determinism-dupe-20260702T233755Z/summary.json`
- `data/gemma4-q8-gpu0-determinism-dupe-20260702T233755Z/realistic-suite.json`
- Server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-determinism-dupe-20260702T233755Z.server.log`

This run intentionally duplicated two prompts inside one server process. It is
**invalid for promotion** because the fixed-suite uniqueness gate fails
(`prompts_unique=false`), but it is useful for diagnosing stability. It used
the same launcher identity as the 125 repro, `cached_tokens=0`, and
`MAX_TOKENS=256`.

Results:

| prompt | duplicate A hash | duplicate B hash | first-100 tok/s |
| --- | --- | --- | --- |
| sql-debugging | same | same | `111.535`, `111.743` |
| bug-report-synthesis | different | different | `128.229`, `111.801` |

The `bug-report-synthesis` duplicate produced different continuations inside
the same server session at `temperature=0`, `top_p=1`, and `seed=1`. The first
preview changed from `Request-Response Mapping...` to
`Request/Response Lifecycle...`; the faster path was `128.229 tok/s`, the
slower path was `111.801 tok/s`.

This confirms that the active llama.cpp/SYCL/MTP stack is not byte-stable for
long realistic generations even with greedy settings. A different valid
continuation can materially change MTP acceptance and first-window timing.

## Interpretation

The 120 rerun appears to be a valid lower draw from the same recipe, not a lost
optimization, cache-policy change, or launcher regression.

Primary causes:

1. Long realistic Gemma outputs are not byte-deterministic in this stack even
   with `temperature=0`, `top_p=1`, and `seed=1`.
2. MTP acceptance and the `tokens 1-100 after TTFT` metric are content-path
   sensitive; different phrasing can move specific prompts by `10-17%`.
3. The suite median with 12 prompts is rank-sensitive, so a couple of large
   prompt-level moves can lower the headline median by about `4 tok/s`.

Controls that did *not* explain the drop:

- no meaningful launcher/runtime identity drift was found;
- server logs show full prompt re-processing and `cached_tokens=0`;
- TTFT median was essentially unchanged;
- full512 after-TTFT median moved only about `2%`, much less than the primary
  1-100 median.

## Practical Guidance

- Keep `124.977` as a valid high draw of the promoted recipe, but treat the
  recipe as having a same-family support band around roughly `120-125 tok/s`
  unless/until byte-level generation stability improves.
- Do not judge sub-1% or low-single-digit changes from a single MTP realistic
  run. Use the no-spec calibration lane for target-kernel changes, then confirm
  with the realistic MTP gate.
- For future LocalMaxxing/support wording, report the supporting reruns next to
  the headline high so readers understand variance: `124.977` high, `120.923`
  fresh rerun, plus the existing `123.677`, `121.591`, `121.414`, `119.948`,
  `119.264`, and `113.633` same-family support results.
- If we want more reliable >125, the next performance work should reduce
  content sensitivity or improve the lower tail, not chase a tiny broad recipe
  diff. The two prompts to inspect first are `sql-debugging` and
  `bug-report-synthesis`.
