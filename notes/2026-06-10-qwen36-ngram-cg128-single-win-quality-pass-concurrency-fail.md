# Qwen3.6 INT8 N-Gram CG128: Single-Request Win, Quality Pass, C2 Fail

Date: 2026-06-10

## Context

I retested n-gram speculative decoding on the current accepted Qwen3.6 INT8
runtime, but capped graph capture at 128 to avoid the previous startup hang.

Base runtime:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- runtime dtype: BF16
- quantization: Quark W8A8 INT8
- tensor parallelism: TP4
- max model length: 32K
- `--max-num-batched-tokens 8192`
- `--max-num-seqs 48`
- prefix caching disabled
- XPU PIECEWISE graph capture
- accepted custom-op all-reduce clone settings

Speculative config:

```json
{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_min":2,"prompt_lookup_max":5}
```

Graph cap:

```json
{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":128}
```

## Startup

The CG128 cap fixed the prior large-capture startup hang. The n-gram service
started and captured 19 graph sizes.

## GDN Mixed Decode Patch

The first mixed-traffic run exposed a GDN metadata issue. When an ordinary
one-token decode and a speculative decode landed in the same step, the metadata
builder reclassified the ordinary decode as a prefill. That forced a 1-token
sequence through the FLA chunk prefill kernel and hit an Intel Triton
`PassManager::run failed`.

Patch artifact:

- `patches/vllm-qwen36-gdn-mixed-spec-decode-20260610.patch`

The patch keeps non-spec decodes as decodes when spec decodes are also present.
The model core already has separate recurrent update paths for spec and
non-spec decode and merges them afterward.

Reliability smoke after the patch:

- two concurrent direct completions, one prompt with high n-gram reuse and one
  ordinary technical prompt
- both completed successfully
- no `ERROR`, `Traceback`, `PassManager`, `EngineDead`, or internal-server
  failure appeared in the log for that smoke

## Single-Request Speed

The patched candidate improved the single-request speed gate:

- artifact: `data/qwen36-quark-int8-tp4-ngram5-cg128-gdnmixed-single-20260610.json`
- corrected output tok/s mean: `114.86`
- corrected output tok/s median: `104.26`
- corrected output tok/s min/max: `101.55` / `168.05`
- e2e output tok/s mean: `113.09`
- TTFT mean: `76.15 ms`

For comparison, the same candidate before the GDN metadata patch measured:

- artifact: `data/qwen36-quark-int8-tp4-ngram5-cg128-isolated-single-20260610.json`
- corrected output tok/s mean: `108.83`
- e2e output tok/s mean: `107.31`
- TTFT mean: `75.49 ms`

This is a real single-request decode win over the accepted no-prefix baseline,
but it is still far below the 200 tok/s target.

## Quality

Direct backend quality was not meaningful because it did not use the LAN
frontdoor chat-template override and therefore emitted Qwen thinking text.

Through the same frontdoor behavior used for accepted service traffic
(`enable_thinking=false`), quality passed:

- artifact: `data/qwen36-quark-int8-tp4-ngram5-cg128-gdnmixed-frontdoor-quality-20260610.json`
- `pass_all`: true
- `baseline_match_all`: true
- exact cases, JSON case, repeat case, and 8K long-context case passed

Because n-gram speculative decoding verifies proposals with the target model,
this path should not lower model quality when the implementation is stable.

## Concurrency Reliability Failure

The candidate failed the c2 concurrency gate:

- artifact: `data/qwen36-quark-int8-tp4-ngram5-cg128-gdnmixed-concurrency-fail-20260610.json`
- command attempted c2 and c8 with 512-token prompts and 256-token outputs
- c2 hit HTTP 500 before c8 started
- backend fatal path:
  - `gdn_attention_core_xpu`
  - `gdn_linear_attn._forward_core`
  - `ChunkGatedDeltaRule.forward_native`
  - FLA `chunk_gated_delta_rule`
  - `chunk_gated_delta_rule_fwd_kernel_h_blockdim64`
  - Intel Triton `PassManager::run failed`

The vLLM scheduler dump showed the failure step mixed:

- one new request with a 515-token prefill
- one cached request with two scheduled tokens
- one speculative decode token for the cached request
- two running requests total

So the metadata patch fixed ordinary decode plus spec decode, but the current
runtime is still not safe for prefill plus speculative decode in one step.

## No-Chunked-Prefill Screen

I tried starting the same n-gram candidate with `--no-enable-chunked-prefill` to
avoid mixed prefill/decode batching.

Artifact:

- `data/qwen36-quark-int8-tp4-ngram5-cg128-nochunk-startup-reject-20260610.json`

vLLM rejected the current 32K config because disabling chunked prefill requires
`max_num_batched_tokens >= max_model_len`. The accepted runtime uses
`max_num_batched_tokens=8192`, so a valid no-chunk 32K screen would require
`max_num_batched_tokens=32768` or a smaller context length. That changes memory
and concurrency tradeoffs and needs a separate startup/memory gate.

## Decision

Do not promote n-gram speculative decoding to the accepted production runtime
yet.

Keep it as a research candidate:

- single-request speed improved to 114.86 corrected output tok/s mean
- target-verified quality passed through the frontdoor
- c2 reliability failed in mixed prefill plus speculative decode
- async scheduling is disabled by n-gram speculation, so aggregate throughput
  must be revalidated even after the reliability issue is fixed

Next useful screens:

1. Add a scheduler guard or GDN metadata fallback that prevents prefill plus
   speculative decode from entering the unsafe FLA chunk shape.
2. Test a 32K no-chunked-prefill startup with `max_num_batched_tokens=32768` and
   measure memory/concurrency cost.
3. After reliability passes, sweep `num_speculative_tokens` and
   `prompt_lookup_min/max` for single-request speed.
