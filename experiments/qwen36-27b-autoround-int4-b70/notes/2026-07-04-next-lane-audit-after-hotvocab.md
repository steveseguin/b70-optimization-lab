# Qwen27 Next-Lane Audit After Hot-Vocab Closure

Date: 2026-07-04

## Context

The draft hot-vocab top-1 screen is closed negative:

```text
experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-draft-hot-vocab-top1-no-win.md
```

Current valid record remains the `webhie/Qwen3.6-27B-int4-AutoRound` runtime
INT8 LM-head BF16-scale recipe at `65.27648650325429 tok/s`, with same-window
support/control rows around `65.6-65.8 tok/s`.

## Audit Result

Two independent read-only audits were run after the hot-vocab closure.

### Native LM-head / verifier primitive

The current runtime INT8 LM-head still materializes dense logits:

- `vllm/model_executor/layers/vocab_parallel_embedding.py` quantizes hidden
  states and calls `_xpu_C.int8_gemm_w8a8`;
- `vllm-xpu-kernels/csrc/xpu/onednn/onednn_matmul.cpp` and
  `csrc/xpu/onednn/int8_gemm_w8a8.h` bind a dense `DNNL_ARG_DST` output;
- `LogitsProcessor.get_top_tokens()` still calls the LM-head quant method and
  only then reduces dense logits;
- `gpu_model_runner.py` and `rejection_sampler.py` already have the useful
  consumer path for precomputed exact top-token IDs.

No existing oneDNN/vLLM-XPU primitive provides an argmax/top-k/candidate-max
matmul epilogue. Existing sampler/top-k kernels consume dense logits after
materialization. Existing grouped-GEMM Xe2/XMX code is useful as a template but
not directly reusable as the public op because it is expert-shaped and writes
dense output.

Credible next kernel experiment:

```text
int8_lm_head_candidate_max_w8a8(
  A_int8, A_scale_fp32, B_int8_t, B_scale_bf16_or_fp32,
  candidate_ids_i64_or_i32, out_dtype, org_vocab_size
) -> top_ids_i64, top_vals_fp32, candidate_vals_fp32, candidate_is_max_bool
```

Benchmark first on rows `1,2,3,4`, hidden `5120`, vocab `248320`, BF16 scales,
against `per_token_quant_int8_xpu + int8_gemm_w8a8 + argmax`. Stop unless the
prototype is exact and clearly faster, roughly `<2.3 ms` or `>1.10x` over
dense. Near parity will not survive endpoint overhead.

Likely blocker: cross-workgroup reduction across `248320` vocab columns without
a second reduction launch. The previous exact full-vocab compact top-1 kernel
already lost (`2.66-2.68 ms` compact versus `2.57-2.61 ms` dense for rows
`1-4`), so a candidate-max variant must be materially better than that, not
just a rewrap.

### Dynamic depth / partial speculative group

The generic metadata and rejection sampler mostly understand per-request
`num_draft_tokens`, but the XPU Qwen/GDN verifier path still assumes rectangular
full groups of `self.num_spec + 1` rows. Partial draft groups can schedule
`k + 1` verifier rows while GDN graph/spec code still sizes/indexes as full
MTP3.

Risk points:

- `vllm/v1/attention/backends/gdn_attn.py`;
- `gpu_model_runner.py` dummy spec metadata and graph-capture paths;
- `vllm/_xpu_ops.py` GDN spec loops;
- `model_executor/layers/mamba/gdn_linear_attn.py` native/fallback GDN loops.

The observed XPU indexing assert from the previous dynamic-depth prototype is
consistent with `query_start + spec_pos` / `spec_token_indx` indexing a full
rectangular group while the actual verifier group is shorter.

Minimal safe path would require partial-group eager fallback or per-depth graph
keys plus GDN metadata/loop masking. That is high correctness risk and likely
slow. It is useful for debugging but unlikely to beat fixed MTP3 unless the
native/GDN path remains fast for partial groups.

## Decision

Do not spend the next work block on partial-group dynamic depth. It is a deep
GDN graph-state engineering task with poor near-term record odds.

Continue with a microbench-first native LM-head/verifier primitive only if the
kernel worktree can be kept clean and the first prototype has a clear stop
criterion:

- exactness versus dense logits;
- rows `1-4` Qwen27 shape;
- `<2.3 ms` or `>1.10x` faster than dense baseline;
- no endpoint integration until the microbench wins.

If the native kernel prototype cannot beat dense oneDNN in microbench, the next
near-term Qwen27 path is not more config screening. It is a better
target-matched drafter trained from a larger/diverse non-final corpus, with
held-out acceptance and quality checks before endpoint validation.
