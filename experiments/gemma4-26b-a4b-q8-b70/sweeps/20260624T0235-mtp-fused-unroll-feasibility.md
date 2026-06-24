# 2026-06-24T0235: Gemma4 MTP fused-unroll feasibility

Goal: identify the next credible fresh-response route toward `>150 tok/s` for
Gemma 4 26B A4B Q8/INT8 on a single B70. The current promoted single-GPU
fresh record is valid but far below the target:

- `data/gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z/`
- first measured request after TTFT: `92.397 tok/s`
- supporting repeat mean: `92.767 tok/s`
- canary: `384/384`
- no n-gram/history/prefix-cache acceleration; all benchmark rows reported
  `cached_tokens=0`

## What is exhausted

The existing llama.cpp Gemma4 draft-MTP path is in:

- `/home/steve/src/llama.cpp-latest-gemma/common/speculative.cpp`
- `common_speculative_impl_draft_mtp::draft()`

For Gemma4 assistant models, `is_mem_shared = llama_get_ctx_other(ctx_dft) ==
ctx_tgt`. The hot path is still host-serialized:

1. build a one-token assistant batch with the previous target token and the
   current `h_nextn` row;
2. call `llama_decode(ctx_dft, batch)`;
3. select a token from that assistant output;
4. read `llama_get_embeddings_nextn_ith(ctx_dft, i_last)` back through the
   regular context output path;
5. copy that h row into the next one-token assistant batch;
6. repeat until `n_max` / confidence stop.

The profiling and follow-up experiments show the bottleneck is this serial
assistant decode loop, not sampler overhead:

- backend draft argmax (`LLAMA_MTP_DRAFT_BACKEND_ARGMAX=1`) made
  `vocab_scanned=0`, `fast_scan_ms=0`, and `fast_logits_ms=0`, but fresh
  throughput regressed to `90-91 tok/s`;
- target verifier greedy argmax was neutral/loss because target verification is
  already batched in `tools/server/server-context.cpp`;
- `n=8+` loses badly because the current design adds more serial assistant
  decodes before target verification can reject bad proposals.

Conclusion: sampler-side micro-optimizations are exhausted. The target
verification side is not the exposed limiter.

## Feasible primitive support

The graph primitive story is better than expected:

- `ggml_argmax()` exists and returns an `I32` token-id tensor
  (`ggml/src/ggml.c`, `GGML_OP_ARGMAX`);
- SYCL implements `GGML_OP_ARGMAX`
  (`ggml/src/ggml-sycl/ggml-sycl.cpp`);
- `ggml_get_rows()` accepts an `I32` row-index tensor and SYCL supports
  `GGML_OP_GET_ROWS`;
- the Gemma4 assistant graph already has access to the target model token
  embedding matrix through `cparams.ctx_other`:
  `model_other->tok_embd` in `src/models/gemma4-assistant.cpp`.

So an in-graph sequence like:

```text
assistant_step(token_i, h_i) -> logits_i, h_{i+1}
token_{i+1} = argmax(logits_i)
embd_{i+1} = get_rows(target_tok_embd, token_{i+1})
assistant_step(token_{i+1}, h_{i+1}) -> ...
```

is conceptually expressible in ggml/SYCL for greedy-only decoding.

## Why the existing backend sampler is insufficient

llama.cpp backend sampling already uses `ggml_argmax()` for the greedy sampler:

- `src/llama-sampler.cpp`
- `llama_sampler_greedy_backend_apply()`

But `llm_graph_context::build_sampling()` only attaches sampled token tensors as
graph outputs. `llama_context` later copies them back to host buffers
(`sampling.sampled`) after graph execution. That cannot feed the sampled token
into the next assistant step in the same backend graph, which is why the
backend-argmax experiment removed CPU vocab scans without changing the serial
shape.

## Required source-level change

The credible `>150 tok/s` route is a Gemma4-specific fused greedy assistant
unroll:

1. Add a new opt-in graph/API path for:
   - Gemma4 assistant only;
   - shared target context (`is_mem_shared`);
   - single sequence;
   - greedy-equivalent draft sampling;
   - no grammar/logprobs/penalties;
   - bounded `n_max` (start with 2 or 3 before trying 7).
2. In `src/models/gemma4-assistant.cpp`, factor one assistant block into a
   helper that can be called repeatedly while building one graph.
3. After each assistant step, use `ggml_argmax(logits)` and
   `ggml_get_rows(target_tok_embd, sampled_token)` to build the next input.
4. Expose all sampled token IDs and all `h_nextn` rows from this graph to the
   speculative driver. This likely needs a new internal API or new fields on
   `llm_graph_result`; the current `t_sampled` map is one-output-row oriented.
5. In `common/speculative.cpp`, route only the safe greedy single-sequence
   Gemma4 path through the fused API; preserve the current host loop as the
   fallback.
6. Keep target verification and accept/rollback unchanged. Final output remains
   target-model verified.

## Implementation risks

- The graph result/output allocation path currently assumes the number of
  output rows follows the batch outputs. A fused draft graph needs to return
  multiple token IDs and h rows from a one-token input.
- Unrolled graphs may increase compile time and temporary memory. Start with
  depth 2/3 as a proof of shape before attempting depth 7.
- Greedy-only gating must be strict. Do not silently apply this to stochastic
  sampling, grammar, penalties, multi-sequence, or backend paths that cannot
  preserve exact draft behavior.
- If assistant matmul dominates rather than launch/host scheduling, speedup may
  be modest (`+15-35%`). If launch/scheduling/logit materialization dominates,
  `130-160 tok/s` fresh is plausible.

## Decision

Do not spend more time on small MTP knobs, vLLM INT8 online quantization, Vulkan,
backend argmax, or target verifier argmax for this model. They are documented
negative controls. The next real engineering step is the fused greedy assistant
unroll, preferably first as a narrow proof-of-shape patch with depth 2/3 and a
smoke canary before any promotion run.
