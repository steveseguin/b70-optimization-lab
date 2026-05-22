# 2026-05-22 MiniMax JSON C2 Context Follow-up

## Context

Goal: improve usable MiniMax-M2.7 AutoRound INT4 throughput without lowering
output quality. This follow-up focuses on concurrency, context length, and the
JSON/content validation gate rather than raw unconstrained decode.

Common launch properties:

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Engine: vLLM `0.20.1-local`, XPU/Level Zero, llm-scaler INT4 MoE path
- Hardware: 4x Intel Arc Pro B70 32GB
- TP: 4
- `max_num_batched_tokens=512`
- `gpu_memory_utilization=0.95`
- `compile_sizes=[1]`
- `cudagraph_mode=NONE`
- Prefix caching and chunked prefill enabled
- Temperature 0, top-p 1, top-k -1
- Control-character logit bias disabled for c2 because it triggered XPU
  `Indexing.h:622` assertions; the validator still rejects control characters.

## Harness Fix

Fixed the concurrency retry semantics in
`scripts/run-minimax-json-quality-throughput.py`: for concurrent requests, the
retry loop now stops only after every concurrency slot has a passing candidate.
Previously it stopped when any slot passed. The old behavior did not mark a
bad run as passing, but it underused retries and made c2 quality recovery harder
to measure.

## Results

### C2, 4k max context, no pad

Run:
`/home/steve/bench-results/minimax-m2.7-json-quality/20260522T131732Z-ctx4096-c2-mbt512-nograph-compile1-allowctrl-retry3-repeat3-fixedretry/`

- Passed: yes
- Raw measured candidates: 18/18
- Wall accepted output throughput: `63.449 tok/s`
- Per-request accepted output throughput: `31.725 tok/s`
- Prompt+output total throughput: `78.037 tok/s`
- Notes: no retry was needed in this repeat3 run.

### C2, 4k max context, 2k prompt padding

Run:
`/home/steve/bench-results/minimax-m2.7-json-quality/20260522T132050Z-ctxpad2048-c2-mbt512-nograph-compile1-allowctrl-retry3-repeat2/`

- Passed delivered quality: yes
- Raw measured candidates: 12/14
- Failure class: `wrong_model` x2, both `MiniMax-M2.6` instead of the requested
  `MiniMax-M2.7`
- Retry-adjusted wall accepted output throughput: `55.765 tok/s`
- Selected valid wall output throughput: `64.606 tok/s`
- Prompt+output total throughput with retries: `1006.366 tok/s`
- Notes: quality can be maintained with validation/retry, but raw candidate
  reliability worsens at this prompt length.

### C1, 8k max context, 6k prompt padding

Run:
`/home/steve/bench-results/minimax-m2.7-json-quality/20260522T132411Z-ctxpad6144-c1-mbt512-nograph-compile1-allowctrl-retry3-repeat2/`

- Passed: yes
- Raw measured candidates: 6/6
- Output throughput: `36.918 tok/s`
- Prompt+output total throughput: `3201.433 tok/s`
- Notes: long-context single-session quality held cleanly, but decode drops
  with the larger active context.

### C2, 8k max context, 6k prompt padding

Cold repeat2, no warmup:
`/home/steve/bench-results/minimax-m2.7-json-quality/20260522T133314Z-ctxpad6144-c2-mbt512-nograph-compile1-allowctrl-retry3-repeat2-confirm/`

- Passed: yes
- Raw measured candidates: 12/12
- Wall output throughput: `49.588 tok/s`
- Prompt+output total throughput: `2150.092 tok/s`

Warm repeat2, one warmup wave excluded:
`/home/steve/bench-results/minimax-m2.7-json-quality/20260522T133612Z-ctxpad6144-c2-mbt512-nograph-compile1-allowctrl-retry3-warm1-repeat2-confirm/`

- Passed: yes
- Raw measured candidates: 12/12
- Warm wall output throughput: `64.062 tok/s`
- Per-request accepted output throughput: `32.031 tok/s`
- Prompt+output total throughput: `2777.685 tok/s`
- Warmup wave itself: `41.547 tok/s` wall output
- LocalMaxxing: `cmpgyxotu00aspc016gg8azvf`
- Notes: this is the best quality-clean context/concurrency result from this
  follow-up and is suitable for LocalMaxxing if labeled as batch/concurrency 2.

Max-seqs 4 repeat2, one warmup wave excluded:
`/home/steve/bench-results/minimax-m2.7-json-quality/20260522T141839Z-ctxpad6144-c2-mbt512-maxseq4-nograph-compile1-allowctrl-retry3-warm1-repeat2/`

- Passed: yes
- Raw measured candidates: 12/12
- Wall output throughput: `63.693 tok/s`
- Per-request accepted output throughput: `31.847 tok/s`
- Prompt+output total throughput: `2761.671 tok/s`
- Notes: increasing `max_num_seqs` from 2 to 4 is quality-clean and does not
  materially change offline c2 throughput. It is useful as a serving scheduler
  probe, not a decode-speed improvement.

### Rejected: C2, 8k, 6k pad, `max_num_batched_tokens=1024`

Run:
`/home/steve/bench-results/minimax-m2.7-json-quality/20260522T140910Z-ctxpad6144-c2-mbt1024-nograph-compile1-allowctrl-retry3-warm1-repeat2/`

- Passed: no
- Raw measured candidates: 0/36
- Failure classes: `control_characters` x36, `json_decode_error` x36,
  `not_single_json_value_text` x36
- Invalid-output throughput: `31.703 tok/s`, not promotable
- Init elapsed: `292.081 s`
- Notes: this run also exposed an Intel compiler failure during warmup:
  `ocloc` returned 245 and IGC reported `Internal Compiler Error: Floating
  point exception` while compiling a Triton reduction kernel. vLLM recovered
  enough to run, but every measured answer contained NUL/control output. Keep
  `max_num_batched_tokens=512` for this stack until the compiler/quality issue
  is understood.

## Interpretation

- The no-graph c2 path is now viable when control-token logit bias is disabled
  and validation remains strict.
- `compile_sizes=[1]` remains the best policy. Compiling exact size 2 passed
  quality but fell to `33.706 tok/s` wall throughput.
- XPU graph capture remains a negative path for c2. Capturing only size 1
  avoided a hard failure but delivered only `36.162 tok/s` wall throughput.
- Long context increases the value of warm service operation. Cold first-wave
  c2 at 8k was `49.588 tok/s`; warm measured c2 was `64.062 tok/s`.
- Validation/retry is still required for honest quality gates. The 2k prompt
  padding run showed `wrong_model` raw failures even though delivered output
  recovered.

## Serving TTFT Probe

To separate offline validated throughput from online serving latency, I ran
`vllm bench serve` against a real OpenAI-compatible server with the same 8k/c2
no-graph settings:

Run:
`/home/steve/bench-results/minimax-m2.7-serve-context/vllm-minimax-m27-autoround-serve-tp4-p6144n128-np2-20260522T135833Z.json`

- Prompt shape: two simultaneous random 6144-token prompts, 128 output tokens
  each, two warmup requests, `temperature=0`, `ignore_eos=true`
- Completed: 2/2
- Output throughput: `35.478 tok/s`
- Total token throughput: `1738.409 tok/s`
- Mean/median TTFT: `1963.456 ms`
- Mean TPOT: `40.136 ms`
- Median ITL: `29.059 ms`
- P99 ITL: `272.861 ms`
- Mean end-to-end latency: `7060.769 ms`
- LocalMaxxing: `cmpgzog7400bfpc01camuplq8`

Interpretation: the serving/API path is much slower than the offline JSON
quality harness at the same context/concurrency setting. The first request had
TTFT `0.295 s`, while the second simultaneous request had TTFT `3.632 s`, so
the current scheduler/prefill path is not handling c2 long-prefill admission as
efficiently as the offline harness. This is now a concrete optimization target.

### Serving max-seqs 4 probe

Run:
`/home/steve/bench-results/minimax-m2.7-serve-context/vllm-minimax-m27-autoround-serve-tp4-p6144n128-np2-20260522T142150Z.json`

- Related offline quality gate:
  `/home/steve/bench-results/minimax-m2.7-json-quality/20260522T141839Z-ctxpad6144-c2-mbt512-maxseq4-nograph-compile1-allowctrl-retry3-warm1-repeat2/result.json`
- Completed: 2/2
- Output throughput: `36.032 tok/s`
- Total token throughput: `1765.558 tok/s`
- Mean/median TTFT: `3267.023 ms`
- Mean TPOT: `30.120 ms`
- Median ITL: `29.635 ms`
- Mean end-to-end latency: `7092.221 ms`

Interpretation: `max_num_seqs=4` is quality-clean offline but not a serving
win for this c2 long-prefill shape. Output throughput improved only about
`1.6%` over the maxseq2 serving probe, while mean TTFT worsened by about
`1.3 s`. Do not promote this as an optimization; keep it as a scheduler
boundary data point.

## Next Steps

1. Add per-wave TTFT/prefill timing from the online serving path; the offline
   total-token accounting is useful, but not a true TTFT measurement.
2. Investigate the control-character logit-bias `Indexing.h:622` failure so c2
   can use stricter sampling constraints without crashing.
3. Add an optional exact-output prompt variant that avoids brittle model-name
   memorization failures while still checking JSON validity, ordering, and math.
4. Investigate the `max_num_batched_tokens=1024` IGC/`ocloc` crash and NUL
   output path. This looks like a driver/compiler boundary, not a safe prefill
   optimization.
5. Re-test c2 with a long-lived server and LAN client, since repeated offline
   runs spend about 75 seconds reloading the checkpoint each time.
