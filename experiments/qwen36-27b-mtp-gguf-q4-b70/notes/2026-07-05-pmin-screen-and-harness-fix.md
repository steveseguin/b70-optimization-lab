# 2026-07-05 - GGUF MTP p-min screen and cache-off harness fix

Status: **closed no-win / diagnostic only**.

Context:

- Current Qwen27 headline remains the vLLM/XPU webhie AutoRound INT4 +
  runtime INT8 LM-head BF16-scale row at `65.27648650325429 tok/s`.
- The Qwen3.6 27B MTP GGUF/SYCL backend is valid but noncompetitive so far:
  best strict fresh cache-off row was about `30.81 tok/s`; no-spec was about
  `23.67 tok/s`; MTP3 beat MTP4/5 in the first depth screen.
- Community llama.cpp Qwen3.6 MTP reports mention using a nonzero draft
  `p_min` with larger draft depth. This is backend-specific and not evidence
  for vLLM, but it is cheap to test on four B70s and can close the obvious
  GGUF follow-up.

Harness bug fixed before counting results:

- `scripts/bench-qwen36-27b-mtp-gguf-realistic.sh` used
  `REQUEST_EXTRA_JSON="${REQUEST_EXTRA_JSON:-{\"cache_prompt\":false}}"`.
- In Bash parameter expansion, the literal `}` inside the default terminated
  the expansion early, producing malformed JSON:
  `{"cache_prompt":false}}`.
- The failed `*pmin*20260705T225848Z` and `*pmin*rerun*20260705T2300*` runs
  reached `/v1/models` but produced no benchmark rows because
  `bench-openai-realistic-suite.py` rejected that JSON.
- The wrapper now assigns the JSON default with an explicit `if [[ -z ... ]]`
  block. `run-qwen36-27b-mtp-gguf-candidate.sh` passes through an empty value
  and lets the benchmark wrapper own the default.

Screen after the fix:

| Label | GPU | MTP max | MTP min | p-min | Median tok/s | p10 | Mean | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `qwen36-27b-udq4xl-gguf-mtp5-pmin075-nmin1-cacheoff-fixed` | 0 | 5 | 1 | 0.75 | `31.039595329056876` | `29.14419245410815` | `31.202542047195664` | pass, cached-zero |
| `qwen36-27b-udq4xl-gguf-mtp7-pmin075-nmin1-cacheoff-fixed` | 1 | 7 | 1 | 0.75 | `30.990345548588905` | `28.868936803101125` | `30.92116100556002` | pass, cached-zero |
| `qwen36-27b-udq4xl-gguf-mtp7-pmin065-nmin1-cacheoff-fixed` | 2 | 7 | 1 | 0.65 | `31.480049485282322` | `29.491677458193866` | `31.750702282761512` | pass, cached-zero |
| `qwen36-27b-udq4xl-gguf-mtp9-pmin075-nmin2-cacheoff-fixed` | 3 | 9 | 2 | 0.75 | `27.31223039185027` | `24.493309378859628` | `27.712120370095192` | pass, cached-zero |

All rows used the strict fresh Qwen realistic suite with `cache_prompt=false`.
No prompt/KV/history reuse was used, and every completed row reported
`cached_tokens_all_zero=true`.

Primary artifacts:

- `data/qwen36-27b-mtp-gguf-q4-b70-baselines/qwen36-27b-udq4xl-gguf-mtp5-pmin075-nmin1-cacheoff-fixed-20260705T230230Z.json`
- `data/qwen36-27b-mtp-gguf-q4-b70-baselines/qwen36-27b-udq4xl-gguf-mtp7-pmin075-nmin1-cacheoff-fixed-20260705T230230Z.json`
- `data/qwen36-27b-mtp-gguf-q4-b70-baselines/qwen36-27b-udq4xl-gguf-mtp7-pmin065-nmin1-cacheoff-fixed-20260705T230230Z.json`
- `data/qwen36-27b-mtp-gguf-q4-b70-baselines/qwen36-27b-udq4xl-gguf-mtp9-pmin075-nmin2-cacheoff-fixed-20260705T230230Z.json`

Decision:

- Closed no-win for the current Qwen27 B70 record lane.
- The best p-min row (`31.48 tok/s`) is only a small improvement over the
  earlier GGUF best (`30.81 tok/s`) and remains less than half of the vLLM/XPU
  strict record (`65.276 tok/s`).
- Do not spend more Qwen27 record time on llama.cpp/SYCL GGUF depth or p-min
  sweeps unless the backend changes materially. Keep GGUF as a valid
  same-quality-class reference and portability lane, not as the active record
  route.
