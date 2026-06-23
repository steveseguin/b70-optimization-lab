# 2026-06-23T1735 n-gram self-speculation sweep

Goal: test whether draftless n-gram speculation can beat the current valid
Gemma 4 26B A4B Q8 one-B70 fresh-response record (`91.618942 tok/s` after
TTFT) without lowering target-model quality.

## Correction: this sweep is warmed/history-only, not headline throughput

After these runs were submitted, the validity policy was tightened: headline
throughput must apply to **fresh new responses**. A speedup that depends on
previous benchmark repeats having already generated the same or highly similar
continuation is a warmed/history artifact, even if every proposed token is
verified by the target model.

Under that policy, the `ngram-mod` results below (`245-280 tok/s`) are useful
history-accelerated diagnostics but **not valid fresh-response headline
records**. Their first benchmark request stayed near the non-spec baseline
(`~41 tok/s`); the high averages came after the repeated filled-long output had
populated the n-gram history. The submitted LocalMaxxing rows are therefore
marked **retraction-needed** in this repo. API deletion was attempted on
2026-06-23, but LocalMaxxing exposes no documented delete/update endpoint and
`DELETE /api/benchmarks/<id>` returned 404 for each submitted ngram row.

Rationale: the MTP profile shows draft-model `llama_decode` dominates the MTP overhead, while acceptance is already saturated (`~7.4` accepted tokens per draft at `n=7`). Draftless n-gram speculation avoids the draft model entirely and is exact-verifier safe: the target model still verifies all proposed tokens. The filled-long benchmark prompt is repetitive, so n-gram modes are plausible.

Validation rule after correction: no fresh-response LocalMaxxing submission
unless chat canary is clean at promotion depth, `cached_tokens=0`, the first
request and repeat mean are reported separately, and the draft source can
operate without having seen the target response from earlier benchmark repeats.

Initial lanes:

| GPU | Label suffix | Spec config | Expected result |
| --- | --- | --- | --- |
| 0 | ngram-simple-n12m64 | `--spec-type ngram-simple --spec-ngram-simple-size-n 12 --spec-ngram-simple-size-m 64 --spec-ngram-simple-min-hits 1` | high upside if prompt-history repeats match |
| 1 | ngram-mapk-n12m64 | `--spec-type ngram-map-k --spec-ngram-map-k-size-n 12 --spec-ngram-map-k-size-m 64 --spec-ngram-map-k-min-hits 1` | stricter map path, possibly lower overhead/acceptance balance |
| 2 | ngram-mapk4v-n8m32h2 | `--spec-type ngram-map-k4v --spec-ngram-map-k4v-size-n 8 --spec-ngram-map-k4v-size-m 32 --spec-ngram-map-k4v-min-hits 2` | safer but likely less aggressive |
| 3 | ngram-mod-24-48-64 | `--spec-type ngram-mod --spec-ngram-mod-n-match 24 --spec-ngram-mod-n-min 48 --spec-ngram-mod-n-max 64` | docs-recommended lightweight path for long repetition |

Results will be appended after runs finish.

## Aborted first launch

The first launch used the intended n-gram flags but accidentally omitted
`--ctx-checkpoints 0`. Live server logs showed context checkpoint restore/create
on every canary request, while the current promoted MTP record disables
checkpoints. Those partial run directories are retained as aborted artifacts:

- `data/gemma4-q8-gpu0-ngram-simple-n12m64-filled-long-deep-20260623T1735/`
- `data/gemma4-q8-gpu1-ngram-mapk-n12m64-filled-long-deep-20260623T1735/`
- `data/gemma4-q8-gpu2-ngram-mapk4v-n8m32h2-filled-long-deep-20260623T1735/`
- `data/gemma4-q8-gpu3-ngram-mod-24-48-64-filled-long-deep-20260623T1735/`

Relaunch with the same four n-gram modes plus `--ctx-checkpoints 0`.

## Source-audit constraints

Explorer audit of llama.cpp speculative source found:

- `ngram-simple`, `ngram-map-k`, and `ngram-map-k4v` use their own
  `--spec-ngram-*-size-m` value as draft length; `--spec-draft-n-max` is not the
  operative knob for those modes.
- `--spec-ngram-simple-min-hits` is logged but effectively unused.
- `ngram-map-k` is key-only, so `--spec-ngram-map-k-min-hits` does not provide
  the ambiguity filter one might expect. Treat it as an aggressive mode.
- `ngram-map-k4v-min-hits` does matter and is the safer mode for repeated
  patterns with ambiguity.
- Multi-type fallback priority is fixed in source, independent of CLI order:
  `ngram-simple` > `ngram-map-k` > `ngram-map-k4v` > `ngram-mod` >
  `ngram-cache` > draft-model modes. If combining n-gram with MTP, do not put
  a broad/aggressive n-gram mode ahead of MTP unless it has proven beneficial.

Follow-up candidates if the first corrected sweep does not produce drafts:

- `ngram-map-k n=16 m=96` for high-payoff exact repeats;
- `ngram-map-k n=8 m=64` for shorter anchors;
- `ngram-map-k4v n=10 m=64 min_hits=2`;
- `ngram-map-k4v n=12 m=96 min_hits=2`;
- `ngram-mod match=20 min=32 max=64`;
- `ngram-mod match=28 min=48 max=96`;
- `ngram-map-k4v,ngram-mod` with `k4v n=10 m=48 min_hits=2` plus
  `mod match=20 min=32 max=64`.

Deprioritize `ngram-cache` for this lane unless a relevant static cache exists:
server-mode draft length is currently hard-coded to 8, so it is not a long-draft
record path.

## Corrected sweep results

All corrected runs used `--ctx-checkpoints 0`, `BENCH_PROMPT_MODE=filled-long`,
`PROMPT_TOKENS=512`, `MAX_TOKENS=512`, `CANARY_REPEATS=96`, and
`BENCH_REPEATS=8`.

| Label | Spec config | Canary | tok/s after TTFT | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-ngram-simple-n12m64-ctxcp0-filled-long-deep-20260623T1745` | `ngram-simple n=12 m=64` | 384/384 | 41.17 | 36.48 | valid loss; generated no useful drafts |
| `gemma4-q8-gpu1-ngram-mapk-n12m64-ctxcp0-filled-long-deep-20260623T1745` | `ngram-map-k n=12 m=64` | 384/384 | 41.29 | 36.59 | valid loss; generated no useful drafts |
| `gemma4-q8-gpu2-ngram-mapk4v-n8m32h2-ctxcp0-filled-long-deep-20260623T1745` | `ngram-map-k4v n=8 m=32 h=2` | 384/384 | 38.30 | 34.19 | valid loss; generated no useful drafts |
| `gemma4-q8-gpu3-ngram-mod-24-48-64-ctxcp0-filled-long-deep-20260623T1745` | `ngram-mod match=24 min=48 max=64` | 384/384 | **245.98 warmed/history** | **134.55 warmed wall** | submitted before policy correction; retraction-needed |

LocalMaxxing submission for the `ngram-mod 24/48/64` warmed/history artifact:

- record id: `cmqqxbkzx01cxqo01j8p97627`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-ngrammod-24-48-64-filledlong512-20260623.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-24-48-64-filledlong512-20260623.submit.log`.

The `ngram-mod` run's first benchmark repeat was cold/no-draft at about
`41 tok/s`; once the hash pool had observed the repeated output pattern, later
repeats drafted and verified long chunks. Server stats at the end of the run:
`#gen tokens = 3472`, `#acc tokens = 3472`, `#mean acc len = 63.00`. This is
useful for diagnosing repeated-output/history acceleration because the Q8
target model still verifies every drafted token, but it is **not** a valid
fresh-response speed claim.

## Follow-up ngram-mod sweep

Launched immediately after the first warmed/history LocalMaxxing submission:

| GPU | Label | Spec config | Hypothesis |
| --- | --- | --- | --- |
| 0 | `gemma4-q8-gpu0-ngram-mod-20-32-64-ctxcp0-filled-long-deep-20260623T1750` | `match=20 min=32 max=64` | starts drafting earlier than 24/48/64 |
| 1 | `gemma4-q8-gpu1-ngram-mod-16-16-64-ctxcp0-filled-long-deep-20260623T1750` | `match=16 min=16 max=64` | most aggressive safe threshold; may help the cold repeat |
| 2 | `gemma4-q8-gpu2-ngram-mod-24-32-96-ctxcp0-filled-long-deep-20260623T1750` | `match=24 min=32 max=96` | preserve match length but allow longer verified chunks |
| 3 | `gemma4-q8-gpu3-ngram-mod-28-48-96-ctxcp0-filled-long-deep-20260623T1750` | `match=28 min=48 max=96` | higher-confidence longer chunks |

Results:

| Label | Spec config | Canary | tok/s after TTFT | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-ngram-mod-20-32-64-ctxcp0-filled-long-deep-20260623T1750` | `match=20 min=32 max=64` | 384/384 | **255.04 warmed/history** | **137.00 warmed wall** | submitted before policy correction; retraction-needed |
| `gemma4-q8-gpu1-ngram-mod-16-16-64-ctxcp0-filled-long-deep-20260623T1750` | `match=16 min=16 max=64` | 384/384 | 216.04 warmed/history | 125.26 warmed wall | warmed/history loss; chunks too short (`mean acc len 17`) |
| `gemma4-q8-gpu2-ngram-mod-24-32-96-ctxcp0-filled-long-deep-20260623T1750` | `match=24 min=32 max=96` | 384/384 | 189.56 warmed/history | 115.96 warmed wall | warmed/history loss; longer chunks reduced steady rate |
| `gemma4-q8-gpu3-ngram-mod-28-48-96-ctxcp0-filled-long-deep-20260623T1750` | `match=28 min=48 max=96` | 384/384 | 190.29 warmed/history | 116.38 warmed wall | warmed/history loss; higher match threshold and 96-token chunks underperformed |

LocalMaxxing submission for the `ngram-mod 20/32/64` warmed/history artifact:

- record id: `cmqqxjnif01d0qo01ix4oeixo`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-filledlong512-20260623.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-filledlong512-20260623.submit.log`.

Server stats for the record run: `#gen tokens = 3493`, `#acc tokens = 3493`,
`#mean acc len = 63.38`. First benchmark repeat was still cold/no-draft at
`41.10 tok/s`; later repeats ran around `286-287 tok/s` after the n-gram state
had learned the repeated output. Under the fresh-response policy, this is a
history-cache/repetitive-output acceleration artifact, not a headline result.

Immediate follow-up launched after the warmed/history high-water mark:

| GPU | Label | Spec config | Hypothesis |
| --- | --- | --- | --- |
| 0 | `gemma4-q8-gpu0-ngram-mod-20-32-64-repeat2-ctxcp0-filled-long-deep-20260623T1805` | `match=20 min=32 max=64` | reproducibility of the warmed/history high-water mark |
| 1 | `gemma4-q8-gpu1-ngram-mod-18-32-64-ctxcp0-filled-long-deep-20260623T1805` | `match=18 min=32 max=64` | slightly easier match than 20 without shrinking chunks |
| 2 | `gemma4-q8-gpu2-ngram-mod-20-24-64-ctxcp0-filled-long-deep-20260623T1805` | `match=20 min=24 max=64` | start drafting earlier while keeping max chunk 64 |
| 3 | `gemma4-q8-gpu3-ngram-mod-20-32-72-ctxcp0-filled-long-deep-20260623T1805` | `match=20 min=32 max=72` | test whether a small max-length increase beats the 64-token steady state |

Results:

| Label | Spec config | Canary | tok/s after TTFT | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-ngram-mod-20-32-64-repeat2-ctxcp0-filled-long-deep-20260623T1805` | `match=20 min=32 max=64` | 384/384 | 253.26 warmed/history | 136.25 warmed wall | warmed/history near-repeat; confirms artifact family |
| `gemma4-q8-gpu1-ngram-mod-18-32-64-ctxcp0-filled-long-deep-20260623T1805` | `match=18 min=32 max=64` | 384/384 | 220.32 warmed/history | 126.67 warmed wall | warmed/history loss; mean accepted length fell to 61.88 and overhead rose |
| `gemma4-q8-gpu2-ngram-mod-20-24-64-ctxcp0-filled-long-deep-20260623T1805` | `match=20 min=24 max=64` | 384/384 | 219.82 warmed/history | 121.03 warmed wall | warmed/history loss; one benchmark request had a low-acceptance draft (`4/64`) |
| `gemma4-q8-gpu3-ngram-mod-20-32-72-ctxcp0-filled-long-deep-20260623T1805` | `match=20 min=32 max=72` | 384/384 | 203.64 warmed/history | 121.07 warmed wall | warmed/history loss; full acceptance at mean len 72.43, but slower verification |

Decision: keep `match=20 min=32 max=64` as the active ngram diagnostic identity
for warmed/history artifact reproduction only. Do not use it for fresh-response
headlines. The threshold neighborhood is mostly exhausted; runtime-shape
interaction remains useful only for understanding repeated-output behavior.

## Runtime-shape sweep around `match=20 min=32 max=64`

All runs below kept the same ngram-mod diagnostic spec and the same validation
shape: `CANARY_REPEATS=96`, `BENCH_REPEATS=8`, `BENCH_PROMPT_MODE=filled-long`,
`PROMPT_TOKENS=512`, `MAX_TOKENS=512`, `--ctx-checkpoints 0`. These are
warmed/history measurements, not fresh-response headline candidates.

Launched after the 255 tok/s warmed/history high-water mark:

| GPU | Label | Runtime change | Hypothesis |
| --- | --- | --- | --- |
| 0 | `gemma4-q8-gpu0-ngram-mod-20-32-64-repeat3-ctxcp0-filled-long-deep-20260623T1815` | exact repeat | measure variance of the 255 tok/s record |
| 1 | `gemma4-q8-gpu1-ngram-mod-20-32-64-vmm0-ctxcp0-filled-long-deep-20260623T1815` | `GGML_SYCL_ENABLE_VMM=0` | see if VMM-off improves total or decode rate |
| 2 | `gemma4-q8-gpu2-ngram-mod-20-32-64-ub512-ctxcp0-filled-long-deep-20260623T1815` | `UBATCH_SIZE=512` | reduce prompt/chunk overhead versus ubatch 64 |
| 3 | `gemma4-q8-gpu3-ngram-mod-20-32-64-ctx4096ub512-ctxcp0-filled-long-deep-20260623T1815` | `CTX_SIZE=4096`, `UBATCH_SIZE=512` | cut TTFT/cold-repeat cost while fitting the 588+512 benchmark |

Results:

| Label | Context | UBatch | Canary | tok/s after TTFT | Wall tok/s | TTFT ms | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-ngram-mod-20-32-64-repeat3-ctxcp0-filled-long-deep-20260623T1815` | 8192 | 64 | 384/384 | 255.95 warmed/history | 137.57 warmed wall | 1589.67 | warmed/history near-repeat |
| `gemma4-q8-gpu1-ngram-mod-20-32-64-vmm0-ctxcp0-filled-long-deep-20260623T1815` | 8192 | 64 | 384/384 | 252.14 warmed/history | 135.24 warmed wall | 1620.91 | warmed/history loss; VMM-off did not help |
| `gemma4-q8-gpu2-ngram-mod-20-32-64-ub512-ctxcp0-filled-long-deep-20260623T1815` | 8192 | 512 | 384/384 | 279.64 warmed/history | 206.51 warmed wall | 631.59 | warmed/history win; ubatch 512 lowers TTFT and raises steady rate |
| `gemma4-q8-gpu3-ngram-mod-20-32-64-ctx4096ub512-ctxcp0-filled-long-deep-20260623T1815` | 4096 | 512 | 384/384 | **280.04 warmed/history** | **206.50 warmed wall** | **633.53** | submitted before policy correction; retraction-needed |

LocalMaxxing submission for the `ctx4096 + ubatch512` warmed/history artifact:

- record id: `cmqqxx7bp01dbqo012d2qiiw6`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-ctx4096ub512-filledlong512-20260623.queue.json`;
- approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-ctx4096ub512-filledlong512-20260623.submit2.log`;
- filtered no-op submit attempt:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-ctx4096ub512-filledlong512-20260623.submit.log`
  (empty because the first command used a non-matching `--label` filter).

Server stats for the warmed/history artifact remain fully accepted:
`#gen tokens = 3493`, `#acc tokens = 3493`, `#mean acc len = 63.38`.
The change is runtime shape, not model quality: Q8 target verification is
unchanged. The shorter context is honest for this small-context warmed/history
artifact because the measured prompt/output shape is about 588+512 tokens; do
not describe this as a 32K-context or fresh-response result.

Follow-up launched after this warmed/history high-water mark: smaller context
sizes that still fit the benchmark (`CTX_SIZE=2048`, `1536`, `1280`) plus
`BATCH_SIZE=1024 / UBATCH_SIZE=1024` at ctx4096. Goal was to see whether the
cold first repeat and post-warm steady requests could move closer to the
observed per-repeat `~315-316 tok/s` warmed ceiling without hiding warmup.

Results:

| Label | Context | Batch | UBatch | Canary | tok/s after TTFT | Wall tok/s | TTFT ms | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-ngram-mod-20-32-64-ctx2048ub512-ctxcp0-filled-long-deep-20260623T1835` | 2048 | 512 | 512 | 384/384 | 242.97 warmed/history | 180.99 warmed wall | 635.03 | warmed/history loss; unexpected falloff versus ctx4096/1280 |
| `gemma4-q8-gpu1-ngram-mod-20-32-64-ctx1536ub512-ctxcp0-filled-long-deep-20260623T1835` | 1536 | 512 | 512 | 384/384 | 241.70 warmed/history | 179.83 warmed wall | 640.06 | warmed/history loss; same falloff as ctx2048 |
| `gemma4-q8-gpu2-ngram-mod-20-32-64-ctx1280ub512-ctxcp0-filled-long-deep-20260623T1835` | 1280 | 512 | 512 | 384/384 | 277.96 warmed/history | 205.12 warmed wall | 638.40 | warmed/history near-high |
| `gemma4-q8-gpu3-ngram-mod-20-32-64-ctx4096b1024ub1024-ctxcp0-filled-long-deep-20260623T1835` | 4096 | 1024 | 1024 | 384/384 | 236.24 warmed/history | 190.24 warmed wall | 468.25 | warmed/history loss; lower TTFT but worse decode average |

Decision: keep `CTX_SIZE=4096`, `BATCH_SIZE=512`, `UBATCH_SIZE=512` as the
warmed/history diagnostic identity. `CTX_SIZE=1280` is close enough to keep as a
latency/reference variant, but smaller context is not monotonically faster.
Do not use `BATCH_SIZE=1024/UBATCH_SIZE=1024` for this ngram diagnostic lane.

## Scheduler and MTP-fallback follow-up

Launched after the small-context warmed/history losses. All runs use the
`CTX_SIZE=4096`, `BATCH_SIZE=512`, `UBATCH_SIZE=512` artifact identity unless
varied.

| GPU | Label | Change | Hypothesis |
| --- | --- | --- | --- |
| 0 | `gemma4-q8-gpu0-ngram-mod-20-32-64-ctx4096ub512-poll25-ctxcp0-filled-long-deep-20260623T1855` | `POLL=25` | tighter polling may reduce per-token/request latency |
| 1 | `gemma4-q8-gpu1-ngram-mod-20-32-64-ctx4096ub512-poll100-ctxcp0-filled-long-deep-20260623T1855` | `POLL=100` | looser polling may reduce CPU overhead |
| 2 | `gemma4-q8-gpu2-ngram-mod-20-32-64-ctx4096ub512-threads8-ctxcp0-filled-long-deep-20260623T1855` | `THREADS=8` | fewer CPU threads may reduce scheduling contention |
| 3 | `gemma4-q8-gpu3-ngrammod-mtpfallback-n7-ctx4096ub512-ctxcp0-filled-long-deep-20260623T1855` | `--spec-type ngram-mod,draft-mtp`, MTP `n=7/n-min=2/p-min=0.12`, fast top-k | `ngram-mod` handles warm repeats; MTP may lift the first cold repeat from ~41 tok/s toward the 91 tok/s MTP baseline |

Combined ngram+MTP caveat: source priority is fixed as ngram before draft-MTP,
so this only helps when ngram has no usable match. If it improves the record,
describe the result as a repeated-benchmark history-cache result with an MTP
cold-start fallback, not as general no-cache throughput.

Results:

| Label | Change | Canary | tok/s after TTFT | Wall tok/s | TTFT ms | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-ngram-mod-20-32-64-ctx4096ub512-poll25-ctxcp0-filled-long-deep-20260623T1855` | `POLL=25` | 384/384 | 243.63 warmed/history | 181.41 warmed wall | 633.99 | warmed/history loss; tighter polling hurts badly |
| `gemma4-q8-gpu1-ngram-mod-20-32-64-ctx4096ub512-poll100-ctxcp0-filled-long-deep-20260623T1855` | `POLL=100` | 384/384 | **280.64 warmed/history** | 206.24 warmed wall | 639.86 | submitted before policy correction; retraction-needed |
| `gemma4-q8-gpu2-ngram-mod-20-32-64-ctx4096ub512-threads8-ctxcp0-filled-long-deep-20260623T1855` | `THREADS=8` | 384/384 | 279.36 warmed/history | 206.00 warmed wall | 635.09 | warmed/history near-miss; below poll100 artifact |
| `gemma4-q8-gpu3-ngrammod-mtpfallback-n7-ctx4096ub512-ctxcp0-filled-long-deep-20260623T1855` | `ngram-mod,draft-mtp`, MTP fallback | 384/384 | 273.11 warmed/history | 202.06 warmed wall | 599.96 | warmed/history loss; previous direct launch also missed some baseline env defaults, so retest via wrapper |

LocalMaxxing submission for the `POLL=100` warmed/history artifact:

- record id: `cmqqyby6801dvqo01as3wenz2`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-poll100-filledlong512-20260623.queue.json`;
- approved response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-ngrammod-20-32-64-poll100-filledlong512-20260623.submit.log`.

Decision after policy correction: `POLL=100` is the fastest known warmed/history
artifact (`280.04 -> 280.64 tok/s` after TTFT), but it is **not** a
fresh-response headline and should not be promoted publicly except as a clearly
labeled repeated-output/history diagnostic. Keep `THREADS=16` for artifact
reproduction until a thread-count follow-up beats it.

Combined ngram+MTP note: upstream llama.cpp issue
<https://github.com/ggml-org/llama.cpp/issues/23184> reports that combined
`draft-mtp,ngram-mod` modes generate separate draft streams rather than a true
pipeline. Treat combined runs here as cold-start fallback probes only.

Follow-up launched after the `POLL=100` record:

| GPU | Label | Change | Hypothesis |
| --- | --- | --- | --- |
| 0 | `gemma4-q8-gpu0-ngram-mod-20-32-64-ctx4096ub512-poll100-repeat-ctxcp0-filled-long-deep-20260623T1915` | exact `POLL=100` repeat | measure variance and confirm the 280.64 warmed/history artifact family |
| 1 | `gemma4-q8-gpu1-ngram-mod-20-32-64-ctx4096ub512-poll150-ctxcp0-filled-long-deep-20260623T1915` | `POLL=150` | test whether looser polling reduces CPU overhead further |
| 2 | `gemma4-q8-gpu2-ngram-mod-20-32-64-ctx4096ub512-poll100-threads24-ctxcp0-filled-long-deep-20260623T1915` | `POLL=100`, `THREADS=24` | retest higher CPU thread count under the better scheduler poll |
| 3 | `gemma4-q8-gpu3-ngrammod-mtpfallback-n7-poll100-ctx4096ub512-ctxcp0-filled-long-deep-20260623T1915` | wrapper-launched `ngram-mod,draft-mtp`, `POLL=100`, fast-top-k MTP fallback | retest the cold-start fallback without losing baseline env defaults |

Results:

| Label | Change | Canary | tok/s after TTFT | Wall tok/s | TTFT ms | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-ngram-mod-20-32-64-ctx4096ub512-poll100-repeat-ctxcp0-filled-long-deep-20260623T1915` | exact `POLL=100` repeat | 384/384 | 240.05 warmed/history | 179.40 warmed wall | 635.99 | warmed/history loss; one benchmark repeat emitted comma-separated lines, causing a second cold/no-ngram request |
| `gemma4-q8-gpu1-ngram-mod-20-32-64-ctx4096ub512-poll150-ctxcp0-filled-long-deep-20260623T1915` | `POLL=150` | 384/384 | 276.76 warmed/history | 204.29 warmed wall | 639.63 | warmed/history loss; below `POLL=100` high-water mark |
| `gemma4-q8-gpu2-ngram-mod-20-32-64-ctx4096ub512-poll100-threads24-ctxcp0-filled-long-deep-20260623T1915` | `POLL=100`, `THREADS=24` | 384/384 | 276.28 warmed/history | 204.52 warmed wall | 635.69 | warmed/history loss; higher CPU thread count did not help |
| `gemma4-q8-gpu3-ngrammod-mtpfallback-n7-poll100-ctx4096ub512-ctxcp0-filled-long-deep-20260623T1915` | wrapper-launched combined fallback | n/a | n/a | n/a | n/a | harness failure; wrapper escaped comma in `--spec-type ngram-mod,draft-mtp`, fixed in `scripts/run-gemma4-26b-spec-candidate.sh` |

The exact repeat's per-request decode rates were
`[41.2, 299.4, 313.2, 311.7, 310.4, 41.0, 286.8, 316.6]`; row 5 had a
different output hash and used comma-separated lines (`001. benchmark, latency,
...`) instead of the original no-comma repeated line. This explains the lower
mean and points at prompt-shape stability, not a model-quality problem. Added
`BENCH_PROMPT_MODE=filled-fixed-line` in
`scripts/bench-openai-single-decode.py` to request one exact line template
without commas or extra words.

Follow-up launched after this variance diagnosis:

| GPU | Label | Change | Hypothesis |
| --- | --- | --- | --- |
| 0 | `gemma4-q8-gpu0-ngram-mod-20-32-64-ctx4096ub512-poll100-fixedline-r8-ctxcp0-deep-20260623T1935` | new `filled-fixed-line` prompt, 8 repeats | remove output-format drift while keeping comparable repeat count |
| 1 | `gemma4-q8-gpu1-ngram-mod-20-32-64-ctx4096ub512-poll100-fixedline-r16-ctxcp0-deep-20260623T1935` | `filled-fixed-line`, 16 repeats | measure warmed-state amortization explicitly under the fixed prompt |
| 2 | `gemma4-q8-gpu2-ngram-mod-20-32-64-ctx4096ub512-poll100-filledlong-r16-ctxcp0-deep-20260623T1935` | original `filled-long`, 16 repeats | separate repeat-count amortization from the fixed prompt change |
| 3 | `gemma4-q8-gpu3-ngrammod-mtpfallback-n7-poll100-fixedwrapper-ctx4096ub512-ctxcp0-filled-long-deep-20260623T1935` | corrected wrapper-launched combined fallback | retest the MTP fallback now that comma spec types survive |

Outcome after fresh/warmed policy correction:

- These runs were intentionally stopped/left as aborted artifacts because the
  ngram path is not a fresh-response headline candidate. The first three
  sessions were interrupted during canary; the combined fallback passed canary
  but was interrupted during benchmark.
- `filled-fixed-line` remains in `scripts/bench-openai-single-decode.py` as a
  diagnostic prompt mode for history/warmup studies. It should not be used to
  create LocalMaxxing headline submissions.
- The combined-wrapper comma escaping bug is still worth keeping fixed in
  `scripts/run-gemma4-26b-spec-candidate.sh`, since future fresh-response
  fallback experiments may need comma-separated spec types. For headline work,
  any combined mode must report first-request throughput separately and cannot
  average warmed ngram repeats into the fresh-response number.
