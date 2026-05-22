# 2026-05-22 MiniMax JSON Quality, Context, and Concurrency Sweep

## Goal

Add a practical structured-output quality gate for the current 4x B70
MiniMax-M2.7 AutoRound INT4 fast path, then use it to measure repeatability,
context/prefill sensitivity, and basic concurrent-session behavior without
silently accepting corrupt output.

## Harness

- Added `scripts/run-minimax-json-quality-throughput.py`.
- The harness keeps one vLLM engine alive and runs deterministic JSON tasks:
  - `alpha_names`: ordered JSON list with `name` and first-letter checks.
  - `number_facts`: ordered JSON list with square/cube arithmetic checks.
  - `b70_status`: strict hardware/model status object.
- It records raw candidate pass rate separately from validation-gated delivered
  output. This distinction matters because the fast graph path still produces
  intermittent corrupt candidates.
- Patch snapshot: `patches/minimax-json-quality-throughput-harness-20260522.patch`.
- Condensed data: `data/minimax-m27-json-quality-context-throughput-20260522.json`.

## Promoted Environment Under Test

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Env source: `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`
- Runtime: vLLM `0.20.1-local`, TP4, XPU graph forced with comm and no-op comm
  capture, llm-scaler INT4 MoE path enabled.
- Sampling: greedy (`temperature=0`, `top_p=1`, `top_k=-1`).

## Results

### 4k Max Context, No Padding, Concurrency 1

Run:
`/home/steve/bench-results/minimax-m2.7-json-quality/20260522T112949Z-ctx4096-c1-mbt512-retry3-repeat10/result.json`

- LocalMaxxing: `cmpgv9p9j007qpc01oq5zqhdg`, submitted with conservative
  effective accepted-output `tokSOut=65.588` and `tokSTotal=164.06`.
- Validation-gated delivered output: 30/30 passed.
- Raw candidates: 30/38 passed (`78.95%` candidate pass rate).
- Selected valid-output decode: `87.770 tok/s`.
- Effective accepted-output rate including failed attempts: `65.588 tok/s`.
- Selected valid-output total rate counting prompt tokens: `219.539 tok/s`.
- Repeatability: each task had one normalized JSON hash across all accepted
  runs; `number_facts` had two token hashes that normalized to the same JSON.

Interpretation: the fast path can deliver correct simple JSON tasks above
60 tok/s if a validator retries failed candidates, but raw candidate quality is
not clean enough to call the graph path intrinsically reliable.

### ~2k Prompt Padding, 4k Max Context, Concurrency 1

Run:
`/home/steve/bench-results/minimax-m2.7-json-quality/20260522T114908Z-ctxpad2048-c1-mbt512-retry3-repeat3/result.json`

- Validation-gated delivered output: 9/9 passed.
- Raw candidates: 9/14 passed (`64.29%` candidate pass rate).
- Selected valid-output decode: `83.294 tok/s`.
- Effective accepted-output rate including failed attempts: `38.762 tok/s`.
- Selected valid-output total rate counting prompt tokens: `2571.882 tok/s`.
- Failures included malformed JSON, copied context-pad text, one wrong-model
  substitution, and one NUL/control-character run.

Interpretation: chunked prefill at `max_num_batched_tokens=512` avoids the
large-prefill compile stall and keeps selected decode high, but longer context
increases the number of bad candidates. The retry gate preserved delivered
quality, but the effective rate drops because retries are more frequent.

## Negative Screens

- `sync_cudagraph_replay=1` plus `strong_cudagraph_output=1` did not fix JSON
  corruption and reduced selected valid-output decode to about `59 tok/s`.
  Run: `/home/steve/bench-results/minimax-m2.7-json-quality/20260522T112533Z-ctx4096-c1-mbt512-syncstrong-repeat10/`
- Bad-word bans for known fragments were not sufficient; they shifted failure
  modes and still failed 5/30 raw outputs.
  Run: `/home/steve/bench-results/minimax-m2.7-json-quality/20260522T112133Z-ctx4096-c1-mbt512-badwords-repeat10/`
- Concurrency 2 at 4k max context failed KV reservation before any output:
  available KV cache was about `0.12 GiB`; 2x4096 needed about `0.24 GiB`.
  Run: `/home/steve/bench-results/minimax-m2.7-json-quality/20260522T113333Z-ctx4096-c2-mbt1024-retry3-repeat5/`
- Concurrency 2 with `gpu_memory_utilization=0.95` reached graph capture but
  stalled at 2/3 capture sizes with no outputs.
  Run: `/home/steve/bench-results/minimax-m2.7-json-quality/20260522T114038Z-ctx4096-c2-mbt1024-gmem095-retry3-repeat3/`
- Concurrency 2 at `max_model_len=2048` also stalled after loading with no
  outputs.
  Run: `/home/steve/bench-results/minimax-m2.7-json-quality/20260522T115222Z-ctx2048-c2-mbt512-retry3-repeat3/`
- A single-session long-context run with `max_num_batched_tokens=4096` stalled
  before output; chunked prefill at 512 was usable.
  Run: `/home/steve/bench-results/minimax-m2.7-json-quality/20260522T114504Z-ctxpad3072-c1-mbt4096-gmem095-retry3-repeat3/`

## Current Read

- The current fast path is excellent for selected valid decode speed, but graph
  capture/no-op comm still produces intermittent corruption on less-constrained
  structured tasks.
- A validator/retry layer is currently the safest way to keep delivered quality
  while retaining >60 tok/s effective decode on short structured requests.
- Longer context is usable through chunked prefill, but it worsens raw
  candidate reliability enough that retries become expensive.
- Concurrent sessions are blocked by graph capture/KV scheduling behavior, not
  by a validated throughput limit. This needs a targeted engine fix before
  publishing concurrency throughput.

## Next Steps

1. Add a streaming server-side TTFT harness so prefill latency can be measured
   directly instead of inferred from offline total-token accounting.
2. Investigate the concurrency-2 graph stall. Start with disabling batch-2/4
   graph capture while keeping batch-1 decode graph enabled, or force
   `compile_sizes=[1]` with dynamic fallback for multi-seq prefill.
3. Investigate the NUL/control-output failure in long-context retries; the
   current logit-bias guard did not prevent all-zero token output after decode.
4. Treat validation/retry as a production guardrail for structured output until
   the graph corruption source is fixed.
5. Do not promote LocalMaxxing concurrency/prefill records from the failed c2
   runs. The short JSON-gated result is shareable if clearly labeled as
   validation-gated structured-output throughput, not raw candidate quality.
