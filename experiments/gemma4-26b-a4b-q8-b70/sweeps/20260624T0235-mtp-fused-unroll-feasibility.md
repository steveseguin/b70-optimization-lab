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

## 2026-06-24T0249 status

The local llama.cpp tree at `/home/steve/src/llama.cpp-latest-gemma`
(`c926ad098` base, dirty experimental patch stack) now contains the narrow
proof-of-shape implementation:

- `common/speculative.cpp` parses `LLAMA_MTP_DRAFT_GEMMA4_FUSED_GREEDY=1` and
  routes the safe single-sequence, shared-context, greedy/fast-argmax path
  through `draft_gemma4_fused_greedy_once()`;
- `src/llama-context.{h,cpp}` adds the temporary internal
  `llama_set_mtp_fused_unroll()` API and expands one MTP output into multiple
  output rows for logits and next-N embeddings;
- `src/models/gemma4-assistant.cpp` factors one assistant step and unrolls it
  in one graph using `ggml_argmax(logits)` as the next step token source.

The implementation is intentionally capped at `max_unroll=4` in
`draft_gemma4_fused_greedy_once()`. This is not expected to be the final `>150
tok/s` setting; it is the first build/runtime proof. If n=3/n=4 is correct and
meaningfully faster than the `92.397 tok/s` fresh baseline, the next patch is to
raise the cap toward n=7 and repeat the same fresh-response gate.

Build status: an AOT SYCL build for
`build-sycl-b70-aot-bmg-g31` is in progress. The next validation must use a
fresh binary and run with:

```bash
LLAMA_MTP_DRAFT_GEMMA4_FUSED_GREEDY=1 \
MTP_DRAFT_FAST_ARGMAX=1 MTP_BACKEND_SAMPLING=0 \
MTP_N_MAX=3 MTP_N_MIN=2 MTP_P_MIN=0.12
```

Headline validity still follows the fresh-response rule: use only the first
measured no-cache request as the headline throughput, keep repeated-request
means as supporting evidence, and do not use n-gram/history-warmed repeats as
fresh records.

## 2026-06-24T0255 JIT proof result

Run:

- `data/gemma4-q8-gpu0-mtp-fused-n3-jit-smoke-20260624T025527Z/`
- binary: `/home/steve/src/llama.cpp-latest-gemma/build-sycl-b70-jit/bin/llama-server`
- env: `LLAMA_MTP_DRAFT_GEMMA4_FUSED_GREEDY=1`,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`, no backend draft sampling,
  `MTP_N_MAX=3`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`

Result:

- canary: `32/32` pass;
- fresh measured request: `46.606 tok/s after TTFT`, wall `44.207 tok/s`;
- prompt cache: reported `cached_tokens=1`, so do not use this as a headline
  record; it remains a proof/debug run;
- profile confirms the fused path is active: 579 generated draft tokens with
  284 draft decode calls, versus the scalar shape's one decode per draft token.

Interpretation: functional proof only. JIT SYCL is much slower than the known
AOT path and cannot be used to judge performance. The next useful run is the
same fused n=3 config on the AOT BMG-G31 build. If that still fails to beat the
`92.397 tok/s` AOT baseline, the likely reason is that fused n=3 cuts draft
decode calls but still materializes/scans all logits rows on CPU; the next code
direction is backend-exported sampled IDs for fused rows or raising the unroll
cap toward n=7 after proving AOT behavior.

## 2026-06-24T0305-0320 AOT fused results

The AOT fused implementation was rebuilt and tested at n=3, n=4, and n=7.
All canaries passed, but no fused run beat the scalar fresh-response record.

| Run | Canary | Fresh headline rule | Result |
| --- | --- | --- | --- |
| `data/gemma4-q8-gpu0-mtp-fused-n3-aot-smoke-20260624T030542Z/` | 32/32 | `cached_tokens=1`, not headline | `45.17 tok/s` |
| `data/gemma4-q8-gpu0-mtp-fused-n4-aot-smoke-20260624T030647Z/` | 32/32 | `cached_tokens=1`, not headline | `44.73 tok/s` |
| `data/gemma4-q8-gpu0-mtp-fused-n4-aot-filledlong-smoke-20260624T030827Z/` | 32/32 | `cached_tokens=1`, not headline | `76.71 tok/s` |
| `data/gemma4-q8-gpu0-mtp-fused-n7-aot-filledlong-smoke-20260624T031810Z/` | 32/32 | `cached_tokens=1`, not headline | `90.72 tok/s` |
| `data/gemma4-q8-gpu0-mtp-fused-n7-aot-recordenv-smoke-20260624T031931Z/` | 32/32 | `cached_tokens=0`, headline-valid smoke | `91.54 tok/s` |

Profile interpretation for fused n=7:

- the fused graph reduced draft decode calls substantially (`~130` calls for
  the benchmark request versus scalar's one decode per draft token);
- it still exported full logits rows and next-N hidden rows through the normal
  context output path;
- it remained slower than scalar, so the next useful code experiment is not
  more scalar knob sweeping. It is a logits-transfer reduction: export sampled
  greedy token IDs from the fused graph and consume those IDs in
  `common/speculative.cpp`, avoiding `llama_get_logits_ith()` and the CPU vocab
  scan for each fused draft row.

An unsafe follow-up tried removing exported `h_nextn` rows entirely and crashed
in `ggml_backend_tensor_get_async` with a tensor read out-of-bounds:

- `data/gemma4-q8-gpu2-mtp-fused-n7-nohnext-jit-recordenv-smoke-20260624T032237Z/`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu2-mtp-fused-n7-nohnext-jit-recordenv-smoke-20260624T032237Z.server.log`

That patch was reverted. The current contract still expects exported
`t_h_nextn` rows unless `llama_context::output_reserve()` and the speculative
driver are changed together. Future agents should not repeat the plain
`h_nextn` removal without changing context output accounting.

## 2026-06-24T0327 scalar full confirmation

The fastest one-row scalar lead was rerun with the full chat-canary gate and
eight benchmark rows:

- run:
  `data/gemma4-q8-gpu0-mtp-n7-cleanrebuild-control-full-fresh-20260624T032733Z/`
- canary: **384/384 pass**
- prompt cache: all benchmark rows reported `cached_tokens=0`
- first measured fresh row after TTFT: **94.36621149389549 tok/s**
- wall throughput on that first row: `80.505 tok/s`
- support rows: mean `92.559 tok/s`, median `92.370 tok/s`, min `91.393 tok/s`

Under the fresh-response rule, the headline is the first measured no-cache row,
not the mean and not later repeats. This is a valid fresh single-GPU Q8/MTP n=7
record candidate and supersedes the previous conservative headline
`92.39728860909672 tok/s` from
`data/gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z/`.

The n-gram/history runs remain excluded from fresh-response headline claims.
Their high `200-300+ tok/s` rows are warmed/history-accelerated because the
same benchmark continuation becomes predictable across repeats. They are useful
for warmed/cached throughput notes only, not fresh-response records.

LocalMaxxing submission:

- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-fresh-20260624.queue.json`

## 2026-06-24T0533 verifier backend argmax + verifier-row logits skip

Patch snapshot:

- `patches/gemma4-26b-a4b-q8-b70/llamacpp-mtp-verify-backend-argmax-ids-20260624.patch`
- follow-up in the local llama.cpp tree passes server `spec_i_batch` verifier
  rows into `llama_context` and skips host logits copies for those rows only.

Run:

- `data/gemma4-q8-gpu0-mtp-n7-verify-skiplogits-jit-smoke-20260624T053346Z/`
- JIT binary:
  `/home/steve/src/llama.cpp-latest-gemma/build-sycl-b70-jit/bin/llama-server`
- env: `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`, MTP
  `n=7/n-min=2/p-min=0.12`, backend draft sampling off, fast draft argmax,
  VMM=0, ubatch=512, poll=100, `--ctx-checkpoints 0`.

Result:

- canary: `128/128` pass;
- prompt cache: benchmark rows report `cached_tokens=0`;
- fresh first row: `92.84017448345614 tok/s` after TTFT;
- supporting mean: `92.93551357626149 tok/s` after TTFT.

Decision: **valid loss**, no LocalMaxxing submission. It is below the current
fresh-response record `94.36621149389549 tok/s` from
`gemma4-q8-gpu0-mtp-n7-cleanrebuild-control-full-fresh-20260624T032733Z/`.
The profile confirms target verifier host-logit copies are not the exposed
limiter; the MTP profile remains dominated by assistant draft decode and
draft-side scan/selection. Keep the patch artifact for reference, but do not
promote this path unless a later patch eliminates a larger draft-side transfer.
- submit log:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-fresh-20260624.submit.log`
- result: `HTTP 201`, ID `cmqrjcly601kuqo01rbyub1x6`, status `APPROVED`
- submitted headline: first no-cache row only (`94.36621149389549 tok/s`
  after TTFT, `80.50542700854518 tok/s` wall, `934.1488729987759 ms` TTFT)

## 2026-06-24T0335 current code experiment: fused sampled IDs

New opt-in experiment under construction:

```bash
LLAMA_MTP_DRAFT_GEMMA4_FUSED_GREEDY=1
LLAMA_MTP_DRAFT_GEMMA4_FUSED_SAMPLED_IDS=1
LLAMA_MTP_DRAFT_FAST_ARGMAX=1
```

Intent: keep the fused assistant graph and the existing `h_nextn` export, but
stop exporting/copying full logits rows. The graph already computes
`ggml_argmax(logits)` for each step; this experiment concatenates those token ID
tensors, exposes them through the sampled-token output buffer, and lets
`common_speculative_impl_draft_mtp` read `llama_get_sampled_token_ith()` instead
of scanning vocab logits on CPU.

This is safer than the failed no-`h_nextn` patch because it only changes logits
transport. If it works, expected gain is modest but directly targets the fused
profile's remaining `fast_scan_ms` / logits-copy overhead. If it does not beat
scalar, the next deeper change is proper no-`h_nextn` fused output accounting,
not more n/max/p-min sweeps.

### Result: sampled IDs work, but do not beat scalar

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/llamacpp-mtp-fused-sampledids-20260624.patch`.

| Run | Build | Canary | Fresh rule | First row | Mean |
| --- | --- | --- | --- | --- | --- |
| `data/gemma4-q8-gpu0-mtp-fused-sampledids-n7-jit-smoke-20260624T033545Z/` | JIT | 32/32 | `cached_tokens=0` | `91.923 tok/s` | `91.923 tok/s` |
| `data/gemma4-q8-gpu0-mtp-fused-sampledids-n7-aot-smoke-20260624T034510Z/` | AOT BMG-G31 | 32/32 | `cached_tokens=0` | `91.925 tok/s` | `91.902 tok/s` |

The transport change succeeded technically:

- `fast_logits_ms=0.000`, `fast_scan_ms=0.000`, `vocab_scanned=0`;
- no `llama_get_logits_ith()` CPU vocab scans for fused draft rows;
- canaries stayed green.

It still lost to the scalar full-confirmed fresh record
(`94.366 tok/s`, `384/384` canary). The fused path is therefore bottlenecked by
remaining context-output/hidden-state handoff and fused graph shape overhead,
not by CPU vocab scanning. Keep the patch as a negative result; do not promote
it as a win.

Next useful fused code direction: make the fused assistant path stop exporting
`t_h_nextn` rows safely by changing `llama_context::output_reserve()` and the
speculative driver together. The earlier plain removal crashed because context
output accounting still expected those rows.

## 2026-06-24T0352 fused no-`h_nextn` experiment

New gated experiment:

```bash
LLAMA_MTP_DRAFT_GEMMA4_FUSED_GREEDY=1
LLAMA_MTP_DRAFT_GEMMA4_FUSED_NO_HNEXT=1
LLAMA_MTP_DRAFT_FAST_ARGMAX=1
```

Intent: keep fused internal `h_next` edges between assistant steps, but stop
exporting/copying the concatenated `t_h_nextn` rows. This directly targets the
remaining fused hidden-state handoff. The previous unsafe attempt crashed with
`ggml_backend_tensor_get_async` out-of-bounds because context output accounting
still expected next-N rows; this version also suppresses `embd_nextn` allocation
in `llama_context::output_reserve()` for Gemma4 fused MTP and skips the unused
`llama_get_embeddings_nextn_ith()` call in the fused speculative loop.

JIT smoke:

- run:
  `data/gemma4-q8-gpu0-mtp-fused-nohnext-n7-jit-smoke-20260624T035258Z/`
- canary: **32/32 pass** (`128/128` rows), so the prior out-of-bounds crash is
  fixed
- prompt cache: all benchmark rows reported `cached_tokens=0`
- first measured fresh row: `90.6056373785588 tok/s`
- support rows: mean `91.15961309879506`, max `92.43070453281787`

This is functionally valid but slower than the scalar record
(`94.36621149389549`).

AOT smoke:

- run:
  `data/gemma4-q8-gpu0-mtp-fused-nohnext-n7-aot-smoke-20260624T040258Z/`
- patch artifact:
  `patches/gemma4-26b-a4b-q8-b70/llamacpp-mtp-fused-nohnext-20260624.patch`
- canary: **32/32 pass** (`128/128` rows)
- prompt cache: all benchmark rows reported `cached_tokens=0`
- first measured fresh row: `92.56621266182988 tok/s`
- support rows: mean `91.27152060798966`, max `92.56621266182988`

Decision: archive as safe-but-negative. The patch fixed the prior crash and
removed the unused hidden-row copy path, but it still did not beat the scalar
record. Do not promote without a new reason; if revisited, first carry the
topology bit through graph params / graph reuse identity as noted below.

Second-pass code review note from subagent James: if this path is ever promoted,
do not leave the topology gate as three independent env-var reads forever. Carry
the no-hnext bit through context/graph params and include it in graph reuse
identity (`allow_reuse()`), so toggling the flag cannot reuse a graph with the
wrong output topology.

## 2026-06-24T0407 scalar fresh-response follow-up sweep

After archiving the fused sampled-ID and no-`h_nextn` experiments as negative,
the next four-GPU batch checked whether the scalar `n=7` recipe had an easy
runtime-neighborhood win. All runs used the valid fresh-response rule:
`BENCH_PROMPT_MODE=filled-long`, `cached_tokens=0` on the first benchmark row,
no n-gram/history acceleration, and canaries before benchmark rows.

Baseline to beat:

- `data/gemma4-q8-gpu0-mtp-n7-cleanrebuild-control-full-fresh-20260624T032733Z/`
- first fresh row: `94.36621149389549 tok/s` after TTFT
- canary: `384/384`
- LocalMaxxing: `cmqrjcly601kuqo01rbyub1x6`

Sweep results:

| Run | Change | Canary | First no-cache row | Mean | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-control-freshsweep-20260624T040718Z/` | control repeat | 128/128 | `93.72135082347253` | `92.56450162912316` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-pmin010-freshsweep-20260624T040718Z/` | `MTP_P_MIN=0.10` | 128/128 | `93.40874441916742` | `92.12986630462905` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-pmin014-freshsweep-20260624T040718Z/` | `MTP_P_MIN=0.14` | 128/128 | `91.7277599123917` | `91.65922289173366` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n8-pmin012-freshsweep-20260624T040718Z/` | `MTP_N_MAX=8`, `MTP_P_MIN=0.12` | 128/128 | `62.25127942810437` | `62.41306107570022` | strong loss |

Interpretation:

- The `94.366` promoted row is still the best valid fresh-response result.
- `p-min=0.10` and `p-min=0.14` do not improve the filled-long scalar MTP lane.
- `n=8` remains a bad direction for Gemma 4 Q8 on this host; extra draft depth
  adds serial assistant work faster than it adds accepted fresh tokens.
- The next config-level batch should focus on host/runtime scheduling around
  the scalar `n=7/p-min=0.12` identity (`POLL`, host `THREADS`,
  `MTP_DRAFT_THREADS`, `MTP_DRAFT_THREADS_BATCH`, `UBATCH_SIZE`) and should
  still promote only first no-cache rows after full canary validation.

## 2026-06-24T0430 clean-rebuild scalar control sweep

After the fused negative results, the llama.cpp AOT BMG-G31 server was rebuilt
cleanly with the source reverted away from the sampled-ID and no-`h_nextn`
experiments. This four-GPU batch checked whether the rebuilt binary or nearby
host scheduling settings changed the valid fresh-response scalar `n=7` lane.

All runs used the record-compatible fresh rule:

- `BENCH_PROMPT_MODE=filled-long`, actual prompt length near 512 tokens;
- no n-gram/history acceleration and `--ctx-checkpoints 0`;
- first measured benchmark row only is the fresh-response headline;
- `cached_tokens=0` on the first benchmark row;
- canary suite completed before benchmark measurement.

Baseline to beat remains:

- `data/gemma4-q8-gpu0-mtp-n7-cleanrebuild-control-full-fresh-20260624T032733Z/`
- first fresh row: `94.36621149389549 tok/s` after TTFT
- canary: `384/384`
- LocalMaxxing: `cmqrjcly601kuqo01rbyub1x6`

Sweep results:

| Run | Change | Canary | First no-cache row | Mean | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-exact-control-cleanrebuild-freshsweep2-20260624T0430Z/` | exact control after rebuild | 128/128 | `91.8391403060032` | `91.91578810164542` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-noprofile-cleanrebuild-freshsweep2-20260624T0430Z/` | unset `MTP_DRAFT_PROFILE` | 128/128 | `92.0598261002623` | `92.01875462833068` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-dthreads48-cleanrebuild-freshsweep2-20260624T0430Z/` | `MTP_DRAFT_THREADS=48` | 128/128 | `92.11174915602703` | `92.08071654450323` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-dthreads64-cleanrebuild-freshsweep2-20260624T0430Z/` | `MTP_DRAFT_THREADS=64` | 128/128 | `92.19775062370645` | `92.03959321688123` | valid loss |

Interpretation:

- The promoted `94.366` first-row result remains the best valid fresh-response
  Q8/MTP headline.
- The clean rebuilt AOT binary did not reveal a hidden win; the control and
  nearby draft-thread variants cluster around `91.8-92.2 tok/s`.
- Disabling profile output and increasing draft threads to 48/64 do not improve
  the fresh scalar lane.
- More one-knob scalar sweeps are unlikely to produce a material jump. Future
  record work needs either a deeper code-level reduction in target/draft
  verification cost or a different engine/model packaging path, while keeping
  first no-cache rows separate from warmed/history-accelerated rows.

## 2026-06-24T0455 combined fused sampled-ID + no-`h_nextn` export

The separate fused sampled-ID and no-`h_nextn` experiments each lost when tested
alone, but they remove different host/device export costs. A combined gated patch
was built against the AOT BMG-G31 llama.cpp tree to check whether the interaction
was the missing win.

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/llamacpp-mtp-fused-sampledids-nohnext-combined-20260624.patch`

Run:

- `data/gemma4-q8-gpu0-mtp-fused-sampledids-nohnext-n7-aot-smoke-20260624T045525Z/`

Config:

- record-compatible Q8 main + MTP draft, `MTP_N_MAX=7`, `MTP_N_MIN=2`,
  `MTP_P_MIN=0.12`;
- `MTP_BACKEND_SAMPLING=0`, `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
  `--ctx-checkpoints 0`;
- fused experiment flags:
  `LLAMA_MTP_DRAFT_GEMMA4_FUSED_GREEDY=1`,
  `LLAMA_MTP_DRAFT_GEMMA4_FUSED_SAMPLED_IDS=1`,
  `LLAMA_MTP_DRAFT_GEMMA4_FUSED_NO_HNEXT=1`;
- fresh benchmark rule preserved: `BENCH_PROMPT_MODE=filled-long`,
  first benchmark row only, `cached_tokens=0`.

Result:

- canary: `128/128` pass;
- first no-cache fresh row: `91.67001101978197 tok/s`;
- 2-row support mean: `91.80136920309086 tok/s`.

Decision: **valid loss**. The combined patch is correct under the smoke canary
but does not beat the promoted `94.36621149389549 tok/s` fresh-response record.
Do not spend a full validation run on this lane unless a later patch changes the
cost structure again.

## 2026-06-24T0458 current-bin scalar scheduling sweep

After the combined fused patch lost, a four-replica scalar scheduling sweep
checked whether the newly rebuilt current binary plus small host/runtime changes
could recover the promoted `94.366 tok/s` first-row result. This was a fresh
response sweep only: no n-gram/history acceleration, canaries before benchmark,
`BENCH_PROMPT_MODE=filled-long`, and first benchmark row with `cached_tokens=0`
as the headline.

| Run | Change | Canary | First no-cache row | Mean | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-control-currentbin-schedsweep-20260624T045811Z/` | current-bin control | 256/256 | `91.66956447663866` | `92.56732073043625` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-poll75-currentbin-schedsweep-20260624T045811Z/` | `POLL=75` | 256/256 | `91.81620681259857` | `91.80573228070922` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-threads12-currentbin-schedsweep-20260624T045811Z/` | `THREADS=12` | 256/256 | `93.36440676121182` | `92.3727836470172` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-dtb16-currentbin-schedsweep-20260624T045812Z/` | `MTP_DRAFT_THREADS_BATCH=16` | 256/256 | `92.00404731397906` | `92.1196912626815` | valid loss |

Decision: no scheduling win. `THREADS=12` is the closest current-bin row, but it
still does not beat the promoted `94.36621149389549 tok/s` fresh-response record.
The next worthwhile lane is code-level target verification cost reduction, not
more scalar knob-churn.

## 2026-06-24T0514 verifier backend argmax-ID experiment

Goal: reduce target-verifier host work for strict greedy spec verification by
adding a compact backend `argmax` token-ID output for the target/default context.
This avoids the expensive per-row CPU sampler/candidate path when the verifier
is in deterministic greedy mode. Headline validity rules still require the first
fresh benchmark row only (`cached_tokens=0`); warmed/history rows are not valid
fresh-response claims.

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/llamacpp-mtp-verify-backend-argmax-ids-20260624.patch`

Implementation notes:

- New gated env: `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`.
- Adds `res->t_verify_argmax = ggml_argmax(res->t_logits)` in the default
  context graph and copies it into `sampling.sampled`.
- Keeps normal logits allocated for the default context. The first attempt
  disabled logits globally under this flag and crashed immediately in ordinary
  server sampling (`common_sampler::set_logits()` saw no logits).
- Gates compact verifier IDs off when real backend samplers are present, and
  reorders `sampling.sampled` whenever it exists so compact ID rows follow
  `output_swaps`.
- `git diff --check` passed after the fixes.

Functional smoke:

- `data/gemma4-q8-gpu0-mtp-n7-verify-argmaxids-jit-smoke2-20260624T051454Z/`
- JIT SYCL build, not record-grade AOT timing.
- canary: `128/128` pass.
- first no-cache fresh row: `92.9967871271086 tok/s`;
- 2-row support mean: `93.10770459390474 tok/s`;
- `cached_tokens=0` on the first row.

Decision so far: **functionally valid, timing inconclusive**. The JIT smoke is
below the promoted AOT `94.36621149389549 tok/s` record, but it validates the
runtime path. Next step is an AOT BMG-G31 smoke with the same env before any
promotion/full validation.

AOT smoke:

- `data/gemma4-q8-gpu0-mtp-n7-verify-argmaxids-aot-smoke-20260624T052506Z/`
- canary: `128/128` pass;
- first no-cache fresh row: `93.03958803136896 tok/s`;
- 2-row support mean: `92.96281035679138 tok/s`;
- `cached_tokens=0` on the first row;
- `launcher_identity.llama_spec_verify_backend_argmax_ids=1`.

Decision: **valid loss**. The conservative implementation is correct, but it
keeps full target logits allocated and copied for every default-context output
row so normal server sampling remains safe. That means the main verifier cost
was not removed. Next worthwhile iteration is explicit server-side marking of
spec-verifier-only rows so `llama_context::decode()` can skip host-logit copies
only for rows later consumed by `common_sampler_sample_and_accept_n()`.

## 2026-06-24T0533 verifier-row host-logit skip experiment

Goal: continue the verifier backend argmax-ID lane by letting the server mark
target rows that are consumed only by strict greedy MTP verification. For those
rows, `llama_context::decode()` can skip the host logits copy while still
copying compact backend argmax IDs. This was meant to avoid paying for full
target logits on verifier-only rows without breaking ordinary server sampling.

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/llamacpp-mtp-verify-skiplogits-rows-20260624.patch`

Implementation notes:

- New staging API:
  `llama_set_spec_verify_skip_logits_rows(ctx, rows, n_rows)`.
- Server builds local `batch_view` row IDs from `slot.spec_i_batch - off`.
- Only marks rows when `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`, the slot is
  speculative, draft tokens exist, and the sampler is strict greedy verifier
  mode.
- `get_logits_ith()` now rejects access to rows whose logits were intentionally
  skipped, so accidental use fails loudly.
- JIT SYCL build of `llama-server` completed successfully.

Smoke:

- `data/gemma4-q8-gpu0-mtp-n7-verify-skiplogits-jit-smoke-20260624T053346Z/`
- canary: `128/128` pass;
- first no-cache fresh row: `92.84017448345614 tok/s`;
- 2-row support mean: `92.93551357626149 tok/s`;
- benchmark rows report `cached_tokens=0`.

Decision: **valid loss**. The change is functionally valid but slower than the
promoted AOT record (`94.36621149389549 tok/s`) and does not hit the real
bottleneck. The server profile indicates the hot path is draft-side decode and
scan work, not target verifier host-logit copying. Keep the patch artifact as a
reference, but do not promote this patch.

## 2026-06-24T0539 Level Zero immediate-command-list env sweep

Goal: check whether low-level Level Zero command-list settings move the scalar
MTP record recipe. This used the existing record-grade AOT BMG-G31 binary and
fresh-response validation only: canary before benchmark, `BENCH_PROMPT_MODE=filled-long`,
one benchmark row per replica, `cached_tokens=0`.

| Run | Change | Canary | First no-cache row | Decision |
| --- | --- | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-urimm0-envsweep-20260624T053948Z/` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=0` | 64/64 | `93.47027069219706` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-urimm1-envsweep-20260624T053948Z/` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1` | 64/64 | `93.6108814034219` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-syclpiimm0-envsweep-20260624T053948Z/` | `SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS=0` | 64/64 | `90.604042156637` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-syclpiimm1-envsweep-20260624T053948Z/` | `SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS=1` | 64/64 | `91.56509210296393` | valid loss |

Decision: no record. `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1` was the best of this
sweep, but still below `94.36621149389549 tok/s`. Do not submit to
LocalMaxxing. Next low-risk runtime sweeps should focus on allocation/copy-engine
settings or revisit draft-side decode cost directly.

## 2026-06-24T0605 Level Zero allocation/copy-engine env sweep

Goal: test the remaining low-level Level Zero knobs without using any warmed
history. This used the same scalar MTP record recipe as the immediate-command-list
sweep: AOT BMG-G31 binary, `BENCH_PROMPT_MODE=filled-long`, canary before
benchmark, one fresh benchmark row, and `cached_tokens=0`.

| Run | Change | Canary | First no-cache row | Decision |
| --- | --- | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-relaxedalloc0-envsweep-20260624T0605Z/` | `UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=0` | 64/64 | `92.00433538116685` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-syclcopy0-envsweep-20260624T0605Z/` | `SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE=0` | 64/64 | `93.40668110972861` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-syclcopy1-envsweep-20260624T0605Z/` | `SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE=1` | 64/64 | `91.81562602022211` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-urcopy0-envsweep-20260624T0605Z/` | `UR_L0_USE_COPY_ENGINE=0` | 64/64 | `92.01160667100008` | valid loss |

Decision: no record and no sign that copy/allocation knobs unlock the next
step. Best was `SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE=0` at `93.40668110972861`,
still below the promoted `94.36621149389549 tok/s` fresh-response record. Stop
spending sweep slots on Level Zero runtime knobs unless a later code change
materially changes the runtime profile.

## 2026-06-24T0615 poll-neighborhood rescreen

Goal: rescreen polling around the current `POLL=100` record recipe, with a
same-batch control so GPU/time drift is visible. This again used fresh-response
measurement only: `BENCH_PROMPT_MODE=filled-long`, one benchmark row,
`cached_tokens=0`.

| Run | Change | Canary | First no-cache row | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-poll100-control2-sweep-20260624T0615Z/` | `POLL=100` control | 64/64 | `93.52609888490149` | `79.70299673307724` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-poll125-sweep-20260624T0615Z/` | `POLL=125` | 64/64 | `92.16325423305562` | `78.51296625928768` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-poll150-sweep-20260624T0615Z/` | `POLL=150` | 64/64 | `92.04117864506996` | `78.73125485762982` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-poll200-sweep-20260624T0615Z/` | `POLL=200` | 64/64 | `90.70846681194152` | `77.72705769824374` | valid loss |

Decision: no poll win. Higher poll values monotonically worsened in this batch,
and the `POLL=100` control did not reproduce the promoted high-water mark. Keep
`POLL=100`; do not spend more slots on polling unless another patch changes the
host/device overlap profile.

## 2026-06-24T0625 fused sampled-ID/no-hnext skip-final-hnext patch

Goal: reduce fused Gemma4 assistant graph cost. Even with
`LLAMA_MTP_DRAFT_GEMMA4_FUSED_NO_HNEXT=1`, the fused graph still computed the
final `nextn_proj_post` / `h_nextn` row for the last unrolled draft step, even
though that row is neither fed into a later fused step nor copied to the host.

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/llamacpp-gemma4-fused-skip-final-hnext-20260624.patch`

Implementation note:

- `src/models/gemma4-assistant.cpp` now passes a `need_h_next` flag into the
  fused `build_step()` helper.
- In fused mode with `FUSED_NO_HNEXT=1`, it still computes `h_next` for
  intermediate unroll steps because the next step needs it, but skips it for
  the final step.
- Normal non-fused assistant decode still always produces `h_nextn`.

Smoke:

- `data/gemma4-q8-gpu0-mtp-fused-sampledids-nohnext-skipfinalh-aot-smoke-20260624T0625Z/`
- canary: `128/128` pass;
- first no-cache fresh row: `92.94489494223315 tok/s`;
- wall: `79.60531704958751 tok/s`;
- `cached_tokens=0`.

Profile:

- `fast_scan_ms=0`, `fast_logits_ms=0`, `hidden_get_ms=0`, so the sampled-ID /
  no-hnext path is doing its job.
- Cumulative first benchmark profile still dominated by fused draft decode:
  `draft_decode_ms=3534.797`, `draft_decodes=321`, `draft_decode_tokens=321`.

Decision: **valid loss**. This patch improves over the earlier fused
sampled-ID/no-hnext AOT smoke (`~91.80 -> 92.94 tok/s`) but does not beat the
promoted `94.36621149389549 tok/s` fresh-response record. Do not promote by
itself. The next fused-path target is graph reservation/reuse or reducing the
actual assistant unroll body, because host scan/copy work is already gone in
this lane.

## 2026-06-24T0629 fused MTP reserve/output-cap patch

Goal: test whether the fused Gemma4 MTP path was paying first-fresh-request
setup or reallocation cost because reservation did not match the actual fused
assistant graph shape. A code audit found two issues worth testing:

- `llama_context::graph_reserve()` forced `n_mtp_unroll=1`, while the Gemma4
  assistant fused graph has topology keyed by `n_mtp_unroll` and asserts
  `n_outputs == n_mtp_unroll` for fused decode.
- `tools/server/server-context.cpp` sized the MTP draft context
  `n_outputs_max` as `n_parallel`, which undercounts fused draft rows when
  `--spec-draft-n-max > 1`. The target verification context already uses
  `n_parallel * (1 + common_speculative_n_max(...))`; the MTP draft context
  needs draft rows only: `n_parallel * draft.n_max`.

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/llamacpp-fused-mtp-reserve-outputcap-20260624.patch`

Patch notes:

- This is a **stack patch from the current dirty llama.cpp experiment tree**,
  not a clean upstream-only patch. It includes prior experimental changes in
  the same touched files. Preserve it as the tested state, but isolate before
  promotion.
- `set_mtp_fused_unroll()` now marks the scheduler dirty when the unroll value
  changes.
- `sched_reserve()` adds an explicit fused reserve pass for the exact
  single-token, single-sequence Gemma4 MTP fused shape.
- `graph_reserve()` only enables fused reserve when `n_tokens == 1`,
  `n_seqs == 1`, and `n_outputs == n_mtp_unroll`; prompt-processing and normal
  target decode reservation remain at `n_mtp_unroll=1`.
- Server MTP draft `n_outputs_max` is now based on `draft.n_max` both in the
  pre-fit accounting path and the actual MTP context creation path.

Smoke:

- `data/gemma4-q8-gpu0-mtp-fused-reserve-outputcap-aot-smoke-20260624T062904Z/`
- canary: `64/64` pass;
- first no-cache fresh row: `87.23295680108393 tok/s`;
- wall: `75.52928853887974 tok/s`;
- `cached_tokens=0`.

Profile:

- The server reports graph reuse, but the runtime is still dominated by fused
  draft decode: cumulative first benchmark profile had
  `draft_decode_ms=2982.600`, `draft_decodes=194`, `draft_decode_tokens=194`.
- This suggests reservation/output sizing was not the current limiting cost.
  The assistant unroll body itself remains too expensive.

Decision: **valid loss**. Do not promote. The next path should reduce the
actual fused assistant graph body or change the draft strategy; more reserve
and output-buffer work is unlikely to recover the gap to the
`94.36621149389549 tok/s` fresh-response record, let alone the >150 tok/s goal.

## 2026-06-24T0630 scalar output-cap/current-binary control

Goal: after the fused reserve/output-cap patch, test whether the server-side
MTP draft `n_outputs_max = draft.n_max` change helped the normal scalar draft
path even though the fused path was a loss.

Tested state:

- llama.cpp worktree binary:
  `/home/steve/src/llama.cpp-latest-gemma/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- one B70, GPU0, SYCL AOT BMG build, `GGML_SYCL_ENABLE_VMM=0`,
  `UBATCH_SIZE=512`, `POLL=100`, f16 KV, flash attention off;
- draft-MTP scalar path: no fused Gemma4 env flags;
- `--spec-draft-n-max 7 --spec-draft-n-min 2 --spec-draft-p-min 0.12`,
  backend draft sampling off, draft threads `32/32`, `--ctx-checkpoints 0`;
- filled-long benchmark shape, actual prompt tokens `588`, output tokens `512`.

Smoke:

- `data/gemma4-q8-gpu0-mtp-n7-outputcap-currentbin-scalar-smoke-20260624T063057Z/`
- canary: `64/64` pass;
- first no-cache fresh row: `94.67787818426216 tok/s`;
- `cached_tokens=0`.

Full confirmation:

- `data/gemma4-q8-gpu0-mtp-n7-outputcap-currentbin-scalar-confirm-20260624T063201Z/`
- canary: `384/384` pass;
- all benchmark rows have `cached_tokens=0`;
- first no-cache fresh row: `92.6980937053861 tok/s`;
- supporting repeated-request mean: `92.67492878023255 tok/s`;
- max row: `92.93370535791318 tok/s`.

Decision: **valid loss / not a new record**. The smoke exceeded the prior
record, but the full confirmation regressed below the promoted
`94.36621149389549 tok/s` first-fresh result. Do not submit to LocalMaxxing.
If the output-cap change is isolated later, treat it as a correctness/reserve
cleanup candidate rather than a performance win.

## 2026-06-24T0640 clean record-stack worktree

Problem: `/home/steve/src/llama.cpp-latest-gemma` is now an active dirty
experiment tree with fused Gemma4 MTP, verifier sampled-ID, output-cap, and
reservation changes layered together. The binary path used by the promoted
record was rebuilt later, so the path alone no longer identifies the record
executable.

Action:

- created clean detached worktree:
  `/home/steve/src/llama.cpp-gemma-record-stack` at upstream
  `c926ad09857517978575d6a74d225b463f7417a0`;
- applied the saved pre-fused record-stack patch:
  `patches/gemma4-llamacpp-current-dirty-before-fused-unroll-20260624T023315Z.patch`;
- this patch applies cleanly and touches only:
  - `common/sampling.cpp`;
  - `common/speculative.cpp`;
- configured a separate AOT BMG build directory:
  `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31`.

Purpose: future fresh-response optimization should use this clean worktree as
the reproducible base for the `94.36621149389549 tok/s` record family, then
apply one bounded patch at a time. Keep `/home/steve/src/llama.cpp-latest-gemma`
as the preserved active experiment tree; do not revert it to recover a clean
baseline.

Next targeted code idea from audit: move scalar MTP `h_nextn` access in
`common/speculative.cpp` below rejection/final-token checks. The scalar loop
currently fetches `llama_get_embeddings_nextn_ith()` before logit-gap, p-min,
and `n_max` checks, but the hidden row is only needed when building the next
draft handoff batch. Expected gain is small, but it is correctness-preserving
and directly reduces measured `hidden_get_ms`/handoff work on rejected/final
draft steps.

## 2026-06-24T0655 clean record-stack AOT smoke

Built the clean record-stack worktree at
`/home/steve/src/llama.cpp-gemma-record-stack` with a separate SYCL AOT BMG
build:

- binary:
  `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- source base: upstream `c926ad09857517978575d6a74d225b463f7417a0` plus
  `patches/gemma4-llamacpp-current-dirty-before-fused-unroll-20260624T023315Z.patch`;
- run:
  `data/gemma4-q8-gpu0-mtp-n7-recordstack-clean-aot-smoke-20260624T065550Z/`;
- canary: `256/256` rows pass (`64` repeats x 4 cases);
- fresh measured row: `92.4452168011667 tok/s` after TTFT,
  `79.38277499804373 tok/s` wall;
- actual shape: `588` prompt tokens, `512` completion tokens;
- `cached_tokens=0`.

Decision: valid fresh smoke, but below the promoted
`94.36621149389549 tok/s` record. Use as a credible baseline for clean
worktree patch comparisons, not as a record candidate.

## 2026-06-24T0658 `h_nextn` row deferral patch

Patch:
`patches/gemma4-26b-a4b-q8-b70/gemma4-mtp-hnext-row-defer-loss-20260624T0700.patch`.

Idea: delay `llama_get_embeddings_nextn_ith()` until after logit-gap, p-min,
and `n_max` early exits, because the hidden row is only consumed when building
the next draft handoff batch.

Run:
`data/gemma4-q8-gpu0-mtp-n7-recordstack-hnextdefer-smoke-20260624T065816Z/`.

Result:

- canary: `256/256` rows pass;
- fresh measured row: `92.14998240866272 tok/s` after TTFT,
  `79.07388646875376 tok/s` wall;
- actual shape: `588` prompt tokens, `512` completion tokens;
- `cached_tokens=0`.

Decision: **valid loss** (`92.15` vs clean baseline `92.45`, and both below
the `94.366` record). The patch was reverted in the clean worktree after
preserving the artifact. Do not promote.

## 2026-06-24T0703 verifier h-row direct-copy patch

Patch:
`patches/gemma4-26b-a4b-q8-b70/gemma4-mtp-verify-h-direct-loss-20260624T0705.patch`.

Idea: avoid copying every target verifier h-next row into `verify_h` during
`process()`. Instead, store the target embedding row range and have `accept()`
copy the selected row directly into `pending_h`. The prompt/first-draft path
still copied the last verifier row immediately into `pending_h`.

Run:
`data/gemma4-q8-gpu0-mtp-n7-recordstack-verifydirect-smoke-20260624T070339Z/`.

Result:

- canary: `256/256` rows pass;
- fresh measured row: `92.17476290565298 tok/s` after TTFT,
  `79.13267663434948 tok/s` wall;
- actual shape: `588` prompt tokens, `512` completion tokens;
- `cached_tokens=0`.

Decision: **valid loss**. The buffer-lifetime assumption appears correct
(canaries passed), but removing the bulk copy did not improve throughput and
still trails the clean baseline and the `94.366` record. Reverted in the clean
worktree after preserving the patch artifact. Do not promote.

## 2026-06-24T0707 MTP parameter smokes on 4 GPUs

All runs used the clean record-stack binary, one B70 per run, `64` canary
repeats (`256/256` rows), one fresh measured row, `--ctx-checkpoints 0`, and
`cached_tokens=0`.

First batch:

| Run | GPU | Params | Fresh tok/s | Decision |
| --- | --- | --- | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-p012-clean-sweep-20260624T070724Z/` | 0 | `n_max=7`, `p_min=0.12` | `93.32368040824394` | valid control, below record |
| `data/gemma4-q8-gpu1-mtp-n8-p012-clean-sweep-20260624T070724Z/` | 1 | `n_max=8`, `p_min=0.12` | `62.33599291468352` | valid loss; n8 collapses |
| `data/gemma4-q8-gpu2-mtp-n7-p010-clean-sweep-20260624T070724Z/` | 2 | `n_max=7`, `p_min=0.10` | `91.5251848251785` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-p008-clean-sweep-20260624T070724Z/` | 3 | `n_max=7`, `p_min=0.08` | `91.66186281820815` | valid loss |

Second batch:

| Run | GPU | Params | Fresh tok/s | Decision |
| --- | --- | --- | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-p014-clean-sweep-20260624T071044Z/` | 0 | `n_max=7`, `p_min=0.14` | `91.39518956389144` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-p016-clean-sweep-20260624T071044Z/` | 1 | `n_max=7`, `p_min=0.16` | `91.40650255284862` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n6-p012-clean-sweep-20260624T071044Z/` | 2 | `n_max=6`, `p_min=0.12` | `86.697012211587` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n5-p012-clean-sweep-20260624T071044Z/` | 3 | `n_max=5`, `p_min=0.12` | `81.99225218922254` | valid loss |

Decision: `n_max=7`, `p_min=0.12` remains the best validated scalar MTP
shape. Lower confidence, higher confidence, smaller draft depth, and `n8` all
move away from the promoted `94.36621149389549 tok/s` fresh-response record.

## 2026-06-24T0714 runtime-shape smokes on 4 GPUs

All runs used the clean record-stack binary, `n_max=7`, `p_min=0.12`, one B70
per run, `64` canary repeats (`256/256` rows), one fresh measured row,
`--ctx-checkpoints 0`, and `cached_tokens=0`.

| Run | GPU | Variant | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | --- | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-p012-faon-sweep-20260624T071401Z/` | 0 | flash attention `on` | `90.6878672605743` | `77.6682043212112` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-p012-ub1024-sweep-20260624T071401Z/` | 1 | `ubatch=1024`, `batch=1024` | `91.51021988614615` | `80.57169787982875` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-p012-ub256-sweep-20260624T071401Z/` | 2 | `ubatch=256`, `batch=512` | `91.4810491567663` | `77.08458845350891` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-p012-poll50-sweep-20260624T071401Z/` | 3 | server poll `50` | `91.32676276708477` | `78.15472020018724` | valid loss |

Decision: the promoted runtime shape remains best: flash attention off,
`ubatch=512`, `batch=512`, poll `100`, f16 KV, VMM off. Runtime-shape tweaks
do not explain the remaining gap to >150; the bottleneck is the scalar MTP
draft/verify structure or backend kernel work, not a simple launch knob.

## 2026-06-24T0718 artifact variant sweep: concurrent load hang

Goal: check whether alternate 8-bit/f16 artifacts changed the MTP draft/runtime
frontier without touching source code.

All four runs used the clean record-stack AOT binary, one B70 per process,
`n_max=7`, `p_min=0.12`, `--ctx-checkpoints 0`, f16 KV, `ubatch=512`,
`batch=512`, flash attention off, poll `100`, and `64` canary repeats. The
four processes were launched concurrently:

| Run | GPU | Variant | Outcome |
| --- | --- | --- | --- |
| `data/gemma4-q8-gpu0-mtp-n7-draftf16-sweep-20260624T071835Z/` | 0 | UD-Q8_K_XL target + F16 MTP draft artifact | invalid: server never became ready |
| `data/gemma4-q8-gpu1-mtp-n7-draftbf16-sweep-20260624T071835Z/` | 1 | UD-Q8_K_XL target + BF16 MTP draft artifact | invalid: server never became ready |
| `data/gemma4-q8-gpu2-mtp-n7-draftatomicq8-sweep-20260624T071835Z/` | 2 | UD-Q8_K_XL target + AtomicChat Q8 assistant artifact | invalid: server never became ready; draft memory probe also logged `unknown model architecture: 'gemma4_assistant'` |
| `data/gemma4-q80-gpu3-mtp-n7-q80target-sweep-20260624T071835Z/` | 3 | Q8_0 target + default MTP draft | invalid: server never became ready |

Symptom: after more than 12 minutes all four `/v1/models` endpoints still
returned `503 Loading model`; server logs had not advanced since the early
model-load/tokenizer warnings at `03:18:38`, and each `llama-server` process was
burning about one CPU core. The four processes were terminated and ports
`18300..18303` were freed.

Decision: **invalid / hung**, not a throughput result. This was likely either a
concurrent-load/fitting stall or an artifact compatibility problem. If these
artifacts are revisited, run one at a time with a longer load budget and record
whether the model reaches readiness before running canaries.

## 2026-06-24T0732 one-at-a-time artifact controls

After the four-way artifact sweep hung during model load, the same ideas were
retested one at a time so load contention would not hide the real result. These
runs used the clean record-stack AOT binary, one B70, `n_max=7`, `p_min=0.12`,
`--ctx-checkpoints 0`, f16 KV, `ubatch=512`, `batch=512`, flash attention off,
poll `100`, and one fresh filled-long benchmark row after the canary.

| Run | Variant | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q80-gpu0-mtp-n7-q80target-single-20260624T073244Z/` | Q8_0 target + default MTP draft | 256/256 | `91.25973858216045` | `79.72397371639221` | valid loss |
| `data/gemma4-q8-gpu0-mtp-n7-draftf16-single-20260624T073544Z/` | UD-Q8_K_XL target + F16 MTP draft | 256/256 | `87.39971784113474` | `75.50482492012871` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-draftbf16-single-20260624T073706Z/` | UD-Q8_K_XL target + BF16 MTP draft | 256/256 | `88.99690238975832` | `76.69617329940733` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-draftatomicq8-single-20260624T073730Z/` | UD-Q8_K_XL target + AtomicChat Q8 assistant | n/a | n/a | n/a | invalid: draft load failed with `unknown model architecture: 'gemma4_assistant'` |

Decision: none of these artifacts improves the promoted fresh-response record
(`94.36621149389549 tok/s`). The UD-Q8_K_XL target plus default MTP draft
remains the best validated artifact pairing. The AtomicChat assistant artifact
is not usable with the current llama.cpp Gemma4 assistant loader.

## 2026-06-24T0734 verifier-greedy controls

These runs tested whether target-side verifier sampling was still a hidden
cost after the draft-side cleanups. All used one B70, the default Q8 target and
MTP draft, f16 KV, `--ctx-checkpoints 0`, and
`LLAMA_SPEC_VERIFY_GREEDY_ARGMAX=1`.

| Run | Variant | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu1-mtp-n7-verifiergreedy-sweep-20260624T073400Z/` | `n_max=7` | 256/256 | `91.40003018606407` | `78.06366682464` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n8-verifiergreedy-sweep-20260624T073400Z/` | `n_max=8` | 256/256 | `62.14976284853327` | `55.897142880424845` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n10-verifiergreedy-sweep-20260624T073400Z/` | `n_max=10` | 256/256 | `69.82958101790315` | `61.99247112750145` | valid loss |

Decision: verifier greedy argmax is not the exposed limiter. It does not beat
the normal `n_max=7` scalar lane, and it does not rescue deeper draft settings
(`n=8`, `n=10`). Keep the verifier-greedy patch/logging as a diagnostic only;
the remaining path to `>150 tok/s` needs a larger draft-side structure change
or a different fresh-response speculation strategy, not target sampler tuning.

## 2026-06-24T0742 terminal-logits-only scalar MTP experiment

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/gemma4-mtp-terminal-logits-only-experiment-20260624.patch`.

Idea: on the final scalar draft step, disable MTP `h_nextn` embedding export so
the terminal draft decode only produces logits. This is safe in principle
because there is no next assistant step after `n_max`; if hidden-row export were
the exposed cost, this would reduce the last-step handoff overhead without
changing target verification.

Run:
`data/gemma4-q8-gpu0-mtp-n7-terminal-logits-only-smoke-20260624T074245Z/`.

Result:

- canary: `256/256` rows pass;
- first fresh filled-long row: `93.7899291844928 tok/s` after TTFT,
  `80.16551453112947 tok/s` wall;
- actual shape: `588` prompt tokens, `512` completion tokens;
- prompt-cache rule: `cached_tokens=0`;
- env recorded in summary:
  `LLAMA_MTP_DRAFT_TERMINAL_LOGITS_ONLY=1`;
- profile remained dominated by scalar assistant decode:
  `draft_decode_ms=5537.332`, `fast_scan_ms=356.152`, `hidden_get_ms=9.693`
  cumulative at the end of the run.

Decision: **valid loss**. It does not beat the promoted
`94.36621149389549 tok/s` fresh-response record, and it is nowhere near the
`>150 tok/s` target. The patch was reverted after preserving the artifact. Do
not promote; this confirms that last-step logits/hidden toggling is too small
to matter. The useful path remains a larger draft-side restructuring that
reduces serial assistant decode work or a fresh-response-valid speculation
method that accepts many more tokens per target verification.

## 2026-06-24T0750 research pivot: DFlash parked, draft-only quantization active

Web/local research notes:

- DFlash is a credible next speculation family for Gemma 4 26B-A4B. The
  upstream DFlash repo lists `z-lab/gemma-4-26B-A4B-it-DFlash`, and its README
  says Gemma4 currently needs a temporary vLLM Gemma4 build / CUDA Docker path:
  <https://github.com/z-lab/dflash>.
- The local XPU vLLM environment is `0.20.2rc1.dev13+g9557d9108.d20260620`
  from `/home/steve/src/vllm`, but it has no installed `speculators` package
  and local source search found no `dflash` implementation. DFlash is therefore
  not an immediate XPU smoke without a separate vLLM/speculators integration
  effort.
- The published DFlash direction remains important for future work because
  third-party H100 results report DFlash beating MTP for Gemma 4 26B-A4B MoE,
  while MTP was better for the dense Gemma 4 31B shape:
  <https://jarvislabs.ai/blog/gemma-4-mtp-vs-dflash-benchmark>.

Executable local pivot:

- Keep the final target model at UD-Q8_K_XL (the quality floor).
- Quantize **only the MTP draft** from the F16 MTP artifact. Draft precision
  does not lower final answer quality because the Q8 target still verifies all
  accepted tokens; lower draft precision only changes acceptance and speed.
- Created draft artifacts under
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/`:
  - `gemma-4-26B-A4B-it-Q6_K-MTP.gguf` (`344M`);
  - `gemma-4-26B-A4B-it-Q5_K_M-MTP.gguf` (`329M`);
  - `gemma-4-26B-A4B-it-Q4_K_M-MTP.gguf` (`315M`);
  - `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` (`307M`).

The active sweep launched at `2026-06-24T0752Z` tests these four draft variants
one per B70 with the same Q8 target, `n_max=7`, `p_min=0.12`,
`--ctx-checkpoints 0`, f16 KV, and one fresh filled-long benchmark row.

## 2026-06-24T0752 draft-only quantization smoke results

All runs used the UD-Q8_K_XL target, f16 KV, `n_max=7`, `p_min=0.12`,
`--ctx-checkpoints 0`, `64` canary repeats (`256/256` rows), one fresh
filled-long benchmark row, and `cached_tokens=0`.

| Run | Draft artifact | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-draftq6k-smoke-20260624T075204Z/` | `Q6_K-MTP` | 256/256 | `95.1370994556598` | `80.94003154451562` | promising smoke; full confirmation started |
| `data/gemma4-q8-gpu1-mtp-n7-draftq5km-smoke-20260624T075204Z/` | `Q5_K_M-MTP` | 256/256 | `94.6648291739339` | `80.60452955090534` | promising smoke; full confirmation started |
| `data/gemma4-q8-gpu2-mtp-n7-draftq4km-smoke-20260624T075204Z/` | `Q4_K_M-MTP` | 256/256 | `93.48149498561862` | `79.51136306720339` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-draftq40-smoke-20260624T075204Z/` | `Q4_0-MTP` | 256/256 | `94.26402883748196` | `80.31809173290482` | near record, but below `94.366` |

Profile read:

- Q6_K and Q5_K_M keep essentially the same high acceptance as Q8, but the
  draft-side profile changes enough to recover a small fresh-response gain.
- Q4_K_M loses too much speed/acceptance balance; Q4_0 nearly matches the old
  record but does not beat it in the smoke.

Decision: Q6_K is the first non-warmed fresh-response smoke above the promoted
`94.36621149389549 tok/s` record in this pass. Do not submit or promote from
the smoke. Full Q6_K and Q5_K_M confirmations were launched with `96` canary
repeats (`384/384` rows) and `8` benchmark repeats; headline remains the first
no-cache row only.

### Full confirmation: no promoted record

The full confirmations did **not** reproduce the smoke as a fresh headline
record:

| Run | Draft artifact | Canary | First fresh tok/s | Mean | Max repeated row | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-draftq6k-full-20260624T075456Z/` | `Q6_K-MTP` | 384/384 | `93.59254074121584` | `93.68078781392994` | `95.49508006534309` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-draftq5km-full-20260624T075456Z/` | `Q5_K_M-MTP` | 384/384 | `94.03156035292376` | `94.12601631877907` | `95.0411261284371` | valid loss |

The repeated rows are useful stability/support data, but the headline rule for
this project is the first no-cache fresh request. No LocalMaxxing submission.
Draft-only quantization is still useful because it produced near-record
results and may make nearby `n_max`/`p_min` settings viable, but Q6_K/Q5_K_M at
the baseline `n=7/p=0.12` do not supersede the promoted
`94.36621149389549 tok/s` Q8-draft record.

## 2026-06-24T0759 draft-quant nearby knob smoke

Four follow-up smokes tested whether the promising Q6_K/Q5_K_M draft artifacts
benefit from either a longer draft (`n_max=8`) or a lower probability cutoff
(`p_min=0.10`). All runs used the same UD-Q8_K_XL target, f16 KV,
`--ctx-checkpoints 0`, `64` canary repeats (`256/256` rows), one fresh
filled-long benchmark row, and `cached_tokens=0`.

| Run | Draft / knob | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n8-draftq6k-smoke-20260624T075956Z/` | Q6_K, `n_max=8`, `p_min=0.12` | 256/256 | `63.05046389921442` | `56.53875442780528` | hard loss |
| `data/gemma4-q8-gpu1-mtp-n7-p010-draftq6k-smoke-20260624T075956Z/` | Q6_K, `n_max=7`, `p_min=0.10` | 256/256 | `93.47756312260354` | `79.7022759835586` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n8-draftq5km-smoke-20260624T075956Z/` | Q5_K_M, `n_max=8`, `p_min=0.12` | 256/256 | `63.04342501937956` | `56.54757001808889` | hard loss |
| `data/gemma4-q8-gpu3-mtp-n7-p010-draftq5km-smoke-20260624T075956Z/` | Q5_K_M, `n_max=7`, `p_min=0.10` | 256/256 | `93.35628604599977` | `79.77097403109623` | valid loss |

Profile read:

- `n_max=8` is not viable in the current scalar llama.cpp MTP path. Acceptance
  remains high on repeated canary/bench traffic, but the draft work rises
  (`draft_decode_tokens=4568` and `draft_decode_ms~4.95-5.00s`) without a fresh
  throughput gain; first fresh throughput collapses to ~63 tok/s.
- Lowering `p_min` to `0.10` does not improve the first fresh row and is below
  both the promoted Q8-draft record and the Q6/Q5 full confirmations.

Decision: stop spending runs on longer draft length in this path. The remaining
gap is draft-side overhead, not acceptance. Future work should either reduce the
cost of each draft decode/scan or move to a different fresh-valid speculation
family (for example a DFlash/vLLM lane once Gemma4/XPU support is practical).

## 2026-06-24T0805 scalar runtime backend smoke

After the draft-quant nearby sweep, a four-way runtime interaction smoke checked
whether the record-stack binary had an untested backend combination under the
current fresh-response identity. Baseline held constant: UD-Q8_K_XL target,
default Q8 MTP draft, f16 KV, `n_max=7`, `p_min=0.12`,
`--ctx-checkpoints 0`, `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`,
`POLL=100`, fast draft argmax, backend draft sampling off, one fresh
filled-long benchmark row, and `cached_tokens=0`.

| Run | Change | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-runtime-control-smoke-20260624T080459Z/` | same-batch control | 256/256 | `93.32258478306495` | `79.74668661851673` | valid non-record |
| `data/gemma4-q8-gpu1-mtp-n7-runtime-dnnoff-smoke-20260624T080520Z/` | `GGML_SYCL_DISABLE_DNN=1` | failed row 1 | n/a | n/a | invalid: first JSON canary became `- -_______________________ ...` |
| `data/gemma4-q8-gpu2-mtp-n7-runtime-graphoff-smoke-20260624T080520Z/` | `GGML_SYCL_DISABLE_GRAPH=1` | 256/256 | `91.76354143897511` | `78.76080393275603` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-runtime-faon-smoke-20260624T080521Z/` | `FLASH_ATTN=on` | 256/256 | `90.85436567278931` | `78.00576691913271` | valid loss |

Decision: current backend defaults remain best for the scalar MTP recipe. Do
not repeat DNN-off for promoted Gemma4 Q8 runs unless a future code/driver
change first revalidates canaries; it is a correctness failure, not a speed
variant. Graph-off and FA-on are valid but below the promoted `94.366` record.

## 2026-06-24T0809 quantized-draft retest

Feynman’s result-corpus audit identified only one nearby lane worth retesting:
quantized MTP drafts. The earlier Q6_K smoke had beaten the promoted record but
failed to reproduce at full depth, and Q4_0 had been close. This batch used the
same fresh-response identity as the promoted scalar record: UD-Q8_K_XL target,
f16 target/draft KV, `n_max=7`, `n_min=2`, backend draft sampling off, fast
draft argmax, `--ctx-checkpoints 0`, `VMM=0`, `UBATCH_SIZE=512`, `POLL=100`,
one fresh filled-long benchmark row, and `cached_tokens=0`.

| Run | Draft / knob | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-draftq6k-repeat-smoke-20260624T080932Z/` | Q6_K, `p_min=0.12` repeat | 256/256 | `93.21765023181784` | `79.64751565063813` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-p0125-draftq6k-smoke-20260624T080932Z/` | Q6_K, `p_min=0.125` | 256/256 | `93.39845439114332` | `79.55829461047585` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-p0125-draftq5km-smoke-20260624T080932Z/` | Q5_K_M, `p_min=0.125` | 256/256 | `93.17441795017362` | `79.53353117927875` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-draftq40-repeat-smoke-20260624T080932Z/` | Q4_0, `p_min=0.12` repeat | 256/256 | `94.42328246695452` | `80.16477723413277` | smoke beats record by `0.057`; full confirmation launched |

Decision: Q6_K/Q5_K_M do not reproduce the earlier smoke. Q4_0 is the only
remaining near-term quant-draft candidate, but the margin over the promoted
`94.36621149389549 tok/s` is too narrow for submission from a one-row smoke.
Full Q4_0 confirmation and Q4_0 p-min neighbors were launched at
`2026-06-24T0812Z`.

## 2026-06-24T0812 Q4_0 draft full confirmation: new valid fresh record

The Q4_0 MTP draft smoke reproduced under the full gate and became the new
valid fresh-response record. The target/verifier remains the UD-Q8_K_XL model;
only the MTP draft is Q4_0, so final accepted output quality is still gated by
the Q8 target and the chat canary.

Full run:

- `data/gemma4-q8-gpu0-mtp-n7-draftq40-full-20260624T081218Z/`
- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- recipe: `n_max=7`, `n_min=2`, `p_min=0.12`, backend draft sampling off,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`, f16 KV, `--ctx-checkpoints 0`,
  `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`, `POLL=100`
- canary: **384/384** pass
- headline row: first measured no-cache request only, `cached_tokens=0`
- fresh headline: **95.26352416631231 tok/s** after TTFT
- first-row wall: `81.28549578539435 tok/s`, TTFT `924.2217319842894 ms`
- support rows: mean `95.38558173206405`, median `95.42408428593777`,
  max `95.51641267061656`, min `95.22637213832232`

LocalMaxxing:

- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-fresh-20260624.queue.json`
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-fresh-20260624.submit.log`
- result: `HTTP 201`, ID `cmqrsupdk000jqr01af3eu6vu`, status `APPROVED`

Neighbor smokes from the same launch:

| Run | Q4_0 draft knob | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu1-mtp-n7-p0115-draftq40-smoke-20260624T081218Z/` | `p_min=0.115` | 256/256 | `94.37318807092522` | `80.47623109938299` | valid, only `+0.007` over old record; not worth full confirmation |
| `data/gemma4-q8-gpu2-mtp-n7-p0125-draftq40-smoke-20260624T081218Z/` | `p_min=0.125` | 256/256 | `93.99022306183745` | `79.97033515395458` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-p0130-draftq40-smoke-20260624T081218Z/` | `p_min=0.130` | 256/256 | `94.25528746603686` | `80.32551338213842` | valid loss |

Decision: promote Q4_0 draft at `p_min=0.12` as the current best valid
fresh-response result. Do not promote the neighbor smokes. The real `>150 tok/s`
goal remains unsolved; the evidence still says the next large jump requires a
different fresh-valid speculation family or a deeper reduction in Gemma4
assistant draft decode cost, not more `p_min`/`n_max` neighborhood sweeps.

## 2026-06-24T0821 lower-precision draft smoke

After Q4_0 became the valid record, lower draft quantizations were generated
from the F16 MTP draft and tested to see whether additional draft-side weight
compression could beat Q4_0 without reducing final target quality. The target
model, verifier, KV precision, canary gate, and benchmark identity stayed the
same as the Q4_0 record lane: UD-Q8_K_XL target, f16 KV, `n_max=7`,
`n_min=2`, `p_min=0.12`, backend draft sampling off, fast draft argmax,
`--ctx-checkpoints 0`, `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`,
`POLL=100`, one fresh filled-long benchmark row, and `cached_tokens=0`.

| Run | Draft quant | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-draftq3kl-smoke-20260624T082104Z/` | Q3_K_L | 256/256 | `91.35270617091619` | `78.27044636497399` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-draftq3km-smoke-20260624T082104Z/` | Q3_K_M | 256/256 | `91.52723222815548` | `78.23966536559767` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-draftq3ks-smoke-20260624T082104Z/` | Q3_K_S | 256/256 | `90.13939698418683` | `77.07977644920123` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-draftq2k-smoke-20260624T082104Z/` | Q2_K | 256/256 | `91.19076670344344` | `78.12912125858414` | valid loss |

Decision: lower than Q4_0 is exhausted for this scalar llama.cpp MTP draft
path. The smaller draft files did not translate into faster fresh decode; Q4_0
remains the only quantized-draft win. Do not submit or promote Q3/Q2 results.
Future fresh-valid work should stay centered on the Q4_0 recipe or move to a
source-level reduction in draft decode / verifier coordination overhead.

## 2026-06-24T0827 Q4_0 draft length/thread smoke

With Q4_0 established as the best draft quant, a narrow record-centered smoke
checked whether the draft length or CPU thread split could improve the
fresh-response first row. All runs kept the Q8 target/verifier, Q4_0 MTP draft,
f16 KV, backend draft sampling off, fast draft argmax, `--ctx-checkpoints 0`,
`GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`, `POLL=100`, one fresh filled-long
benchmark row, and `cached_tokens=0`.

| Run | Change | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n6-draftq40-smoke-20260624T082744Z/` | `n_max=6`, threads `32/32` | 256/256 | `89.2722197708782` | `76.76756476352334` | valid loss; shorter draft gives up too much accepted-token depth |
| `data/gemma4-q8-gpu1-mtp-n7-draftq40-dt24-smoke-20260624T082744Z/` | draft threads `24`, batch threads `32` | 256/256 | `94.3582473899406` | `80.34341861546649` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-draftq40-dt40-smoke-20260624T082745Z/` | draft threads `40`, batch threads `32` | 256/256 | `94.16748026410255` | `80.3124366110587` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-draftq40-dtb24-smoke-20260624T082745Z/` | draft threads `32`, batch threads `24` | 256/256 | `94.20168311635278` | `80.3750675777302` | valid loss |

Decision: keep the current Q4_0 record shape: `n_max=7`,
`MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=32`. The `n=6` loss confirms
that the scalar path still benefits from the 7-token draft depth despite its
serial draft-decode cost. Thread neighbors do not recover enough to matter.

## 2026-06-24T0831 Q4_0 no-profile/thread smoke

After the Q4_0 length/thread smoke, a follow-up checked whether the profiling
instrumentation or nearby thread splits were depressing the first fresh row.
All runs kept the Q8 target/verifier, Q4_0 MTP draft, f16 KV, backend draft
sampling off, fast draft argmax, `n_max=7`, `n_min=2`, `p_min=0.12`,
`--ctx-checkpoints 0`, `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`,
`POLL=100`, one fresh filled-long benchmark row, and `cached_tokens=0`.

| Run | Change | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-draftq40-noprofile-smoke-20260624T083105Z/` | disable `MTP_DRAFT_PROFILE` | 256/256 | `94.11862262274629` | `80.17880375606345` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-draftq40-noprofile-dt28-smoke-20260624T083105Z/` | disable profile, draft threads `28`, batch threads `32` | 256/256 | `94.28576098000318` | `80.12900258624215` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-draftq40-noprofile-dt36-smoke-20260624T083105Z/` | disable profile, draft threads `36`, batch threads `32` | 256/256 | `93.9459307525453` | `80.13163455255174` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-draftq40-noprofile-dtb40-smoke-20260624T083105Z/` | disable profile, draft threads `32`, batch threads `40` | 256/256 | `93.75722197864366` | `80.06341216168657` | valid loss |

Decision: keep the record recipe with profiling enabled and draft/batch
threads `32/32`. Disabling the profile counters did not help, and the nearby
thread splits stayed below the `95.26352416631231 tok/s` fresh-response record.
This reinforces that the remaining gap is not ordinary thread-count tuning;
future record attempts need either a better confidence/acceptance policy for
the Q4_0 draft or a source-level reduction in serialized draft decode cost.

## 2026-06-24T0835 Q4_0 fast-top-k / logit-gap smoke

The current record uses `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`, which sets the draft
candidate probability to `1.0` and makes the normal `p_min` threshold mostly
irrelevant. This smoke switched to `LLAMA_MTP_DRAFT_FAST_TOPK=1` to preserve a
small local confidence signal from the draft logits, then screened top-k/gap
settings against one fresh filled-long row. All runs kept the Q8 target/verifier,
Q4_0 MTP draft, f16 KV, backend draft sampling off, `n_max=7`, `n_min=2`,
`p_min=0.12`, `--ctx-checkpoints 0`, `GGML_SYCL_ENABLE_VMM=0`,
`UBATCH_SIZE=512`, `POLL=100`, one benchmark request, and no usable prior
continuation. The measured row is the fresh first request.

| Run | Change | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-q40-topk2-gap0-smoke-20260624T083539Z/` | fast top-k, `top_k=2`, `gap=0.0` | 256/256 | `93.7844457662117` | `79.66662949937839` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-q40-topk2-gap025-smoke-20260624T083539Z/` | fast top-k, `top_k=2`, `gap=0.25` | 256/256 | `93.652038424922` | `79.73284934530619` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-q40-topk2-gap050-smoke-20260624T083539Z/` | fast top-k, `top_k=2`, `gap=0.50` | 256/256 | `93.81988880771189` | `79.9133036675268` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-q40-topk4-gap025-smoke-20260624T083539Z/` | fast top-k, `top_k=4`, `gap=0.25` | 256/256 | `93.41519878165575` | `79.6520036691471` | valid loss |

Decision: reject the fast-top-k confidence branch for the current scalar MTP
recipe. It is valid but slower than both the Q4_0 record
(`95.26352416631231 tok/s`) and the old Q8-draft scalar baseline. Confidence
filtering does not recover enough accepted-token quality to offset the extra
draft-side top-k work. Keep `LLAMA_MTP_DRAFT_FAST_ARGMAX=1` for the promoted
Q4_0 recipe until a source-level design can reduce draft decode cost directly.

## 2026-06-24T0840 Q4_0 context/batch runtime-shape smoke

This screen checked whether the Q4_0 record recipe had a remaining
allocation/runtime-shape sensitivity after the quant/thread/top-k lanes were
exhausted. The identity stayed fresh-response-valid: Q8 target/verifier, Q4_0
MTP draft, f16 KV, backend draft sampling off, fast draft argmax,
`MTP_DRAFT_PROFILE=1`, `n_max=7`, `n_min=2`, `p_min=0.12`,
`--ctx-checkpoints 0`, `GGML_SYCL_ENABLE_VMM=0`, `POLL=100`, flash attention
off, one fresh filled-long benchmark row, and no n-gram/history/cache reuse.

| Run | Change | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-q40-ctx4096-smoke-20260624T084032Z/` | `CTX_SIZE=4096`, batch/ubatch `512/512` | 256/256 | `94.26266948302941` | `80.33290491787001` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-q40-ctx2048-smoke-20260624T084032Z/` | `CTX_SIZE=2048`, batch/ubatch `512/512` | 256/256 | `94.16211342054201` | `79.82809223636212` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-q40-b1024ub512-smoke-20260624T084032Z/` | `BATCH_SIZE=1024`, `UBATCH_SIZE=512`, ctx `8192` | 256/256 | `94.40807367866964` | `80.22882270609028` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-q40-b1024ub1024-smoke-20260624T084032Z/` | `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, ctx `8192` | 256/256 | `93.776368736568` | `82.22027260565834` | valid loss; wall/TTFT improved but headline decode lost |

Decision: keep the promoted Q4_0 runtime shape at `CTX_SIZE=8192`,
`BATCH_SIZE=512`, `UBATCH_SIZE=512`, `POLL=100`, VMM off. Larger batch/ubatch
can improve wall rate and TTFT but does not improve the fresh after-TTFT decode
headline. This closes the remaining small config-level runtime shape around the
Q4_0 record; further gains require source/kernel work or a different
fresh-valid speculation family.

## 2026-06-24T0845 lazy sampler-clone source probe

Schrodinger's source audit found one low-risk generic speculation bookkeeping
probe: avoid cloning the sampler before every speculative verification when the
current target memory mode cannot use a checkpoint restore. The patch is
preserved at:

- `patches/gemma4-26b-a4b-q8-b70/llamacpp-server-lazy-sampler-clone-20260624.patch`

Affected function:

- `/home/steve/src/llama.cpp-gemma-record-stack/tools/server/server-context.cpp`,
  speculative verification loop around `common_sampler_sample_and_accept_n()`.

Fresh-validity rationale: the Q8 target still verifies every draft token and
the accepted token stream is unchanged. The patch only skips creating a rollback
copy of sampler state when rollback cannot use it. No n-gram/history, prefix
reuse, response reuse, or cache reuse is introduced.

The patched build completed after sourcing `/opt/intel/oneapi/setvars.sh
--force`; a plain shell build reached compile but failed final link because the
oneAPI runtime libraries were not on the linker path. The nonfatal UI npm
engine warning is unrelated to the server executable.

| Run | Change | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-q40-lazyclone-smoke-20260624T084529Z/` | lazy sampler clone, GPU0 | 256/256 | `94.19064293704383` | `80.39771016168335` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-q40-lazyclone-smoke-20260624T084529Z/` | lazy sampler clone, GPU1 | 256/256 | `94.71588493240564` | `80.61310695255723` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-q40-lazyclone-smoke-20260624T084529Z/` | lazy sampler clone, GPU2 | 256/256 | `94.61955056891796` | `80.71061680249036` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-q40-lazyclone-smoke-20260624T084529Z/` | lazy sampler clone, GPU3 | 256/256 | `94.51496156614255` | `80.51481570702143` | valid loss |

Decision: reject for promotion and revert the source delta. The change is
correctness-preserving but too small; the best fresh row stayed below the
`95.26352416631231 tok/s` Q4_0 record. This confirms sampler rollback
bookkeeping is not a meaningful lever compared with serialized draft decode.

## 2026-06-24T0853 shared-target masked `h_nextn` source probe

Chandrasekhar's source audit suggested the next low-risk Gemma4-specific
bookkeeping probe: for shared target/draft memory (`is_mem_shared`, Gemma4
assistant), ask the target context to materialize next-N embeddings only for
output rows instead of every raw batch token, then copy only `batch.logits != 0`
rows in `common_speculative_impl_draft_mtp::process()`.

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/llamacpp-mtp-shared-target-nextn-masked-20260624.patch`

Affected source:

- `/home/steve/src/llama.cpp-gemma-record-stack/common/speculative.cpp`

Fresh-validity rationale: the target still verifies the current fresh response
tokens, and speculative `spec_i_batch` indices are raw batch indices for rows
the server already marks as outputs. The patch only avoids materializing/copying
target hidden rows that cannot be consumed by the shared Gemma4 MTP draft path.
It does not use n-gram history, prior continuations, prefix checkpoints, or
response reuse.

Safety notes:

- Non-shared MTP remains dense/unmasked.
- Prompt/prefill split batches with no output row leave the prior pending hidden
  state unchanged; the final prompt output row refreshes it before drafting.
- Speculative verifier batches mark the sampled token and every draft token as
  output rows, so `common_sampler_sample_and_accept_n()` keeps the same raw row
  indices.

The patched build completed with the required oneAPI environment. The nonfatal
UI npm engine warning recurred, but `llama-server` linked successfully. The
four-GPU smoke used the promoted Q4_0 record recipe (`CANARY_REPEATS=256`, one
fresh filled-long benchmark row, `cached_tokens=0` on the measured row).

| Run | Change | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-q40-hnextmasked-smoke-20260624T085333Z/` | shared target masked `h_nextn`, GPU0 | 1024/1024 | `94.34515808347749` | `81.65039361407395` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-q40-hnextmasked-smoke-20260624T085333Z/` | shared target masked `h_nextn`, GPU1 | 1024/1024 | `94.08974502197941` | `81.30354951526054` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-q40-hnextmasked-smoke-20260624T085333Z/` | shared target masked `h_nextn`, GPU2 | 1024/1024 | `94.02298072939736` | `81.3176545020656` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-q40-hnextmasked-smoke-20260624T085333Z/` | shared target masked `h_nextn`, GPU3 | 1024/1024 | `94.15115427742253` | `81.46454762887677` | valid loss |

Decision: reject for promotion and revert the source delta. The patch was
correctness-safe in the server path and did reduce target hidden-row
materialization (`process_tokens` much larger than `verify_rows` in the MTP
profile), but this is not the limiting cost. The best fresh row stayed below the
`95.26352416631231 tok/s` Q4_0 record. This further confirms the remaining
`>150 tok/s` gap is draft-decode shape/kernel work, not target hidden-row copy
bookkeeping.

## 2026-06-24T0907 vLLM DFlash Gemma probe

Fresh-response rule reminder for this lane: DFlash is allowed because the
drafter operates from the current fresh request's target hidden states. It is
not n-gram/history acceleration and does not depend on having previously seen
the benchmark continuation. Prefix caching remains disabled.

Reason for trying: the current llama.cpp MTP lane is capped by a serialized
assistant `llama_decode()` loop and has plateaued around the valid Q4_0 draft
record (`95.26352416631231 tok/s`). The DFlash checkpoint
`z-lab/gemma-4-26B-A4B-it-DFlash` is a parallel drafter for
`google/gemma-4-26B-A4B-it`; if it runs on XPU, it is a more credible route to
`>150 tok/s` than further MTP bookkeeping probes.

Local support audit:

- llama.cpp server does **not** expose DFlash/spec-diffusion for Gemma today.
  Its server spec modes are MTP/EAGLE/ngram families only.
- vLLM has generic DFlash speculative plumbing plus Gemma4 target aux-hidden
  support. The registered draft executor is named Qwen3 (`qwen3_dflash.py`), but
  the Gemma DFlash checkpoint is shaped compatibly enough to load: separate
  `q_proj/k_proj/v_proj`, no embedded tokens, no `lm_head`, and
  `dflash_config.target_layer_ids=[1,6,11,17,22,27]`.
- The DFlash repo README says Gemma4 DFlash needs a vLLM PR and recommends:
  `num_speculative_tokens=15`, target `google/gemma-4-26B-A4B-it`, drafter
  `z-lab/gemma-4-26B-A4B-it-DFlash`.

Downloaded local artifacts:

- target HF snapshot:
  `/mnt/fast-ai/llm-cache/hf/models--google--gemma-4-26B-A4B-it/snapshots/20da991ab4afab98e8f910c4a2e8f4fbefc404ad`
  (`2` safetensor shards, about `48.07 GiB`);
- DFlash drafter:
  `/mnt/fast-ai/llm-cache/hf/hub/models--z-lab--gemma-4-26B-A4B-it-DFlash/snapshots/77d4202772dfe50b2396ec7bac9cfffc7b9e7057`
  (`model.safetensors`, about `0.80 GiB`).

First vLLM/XPU load probe:

- run:
  `data/gemma4-vllm-int8pc-dflash-gpu0-smoke-20260624T090749Z/`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-dflash/servers/gemma4-vllm-int8pc-dflash-gpu0-smoke-20260624T090749Z.server.log`
- target: BF16 HF Gemma4 with vLLM online
  `int8_per_channel_weight_only` (same quality-or-better lane as previous vLLM
  int8pc checks; log still warns only MoE expert weights are quantized);
- spec config: `method=dflash`, `num_speculative_tokens=15`,
  DFlash draft attention backend `flash_attn`;
- `max_model_len=4096`, `max_num_batched_tokens=1024`,
  `gpu_memory_utilization=0.90`, prefix caching disabled.

Outcome: **late load failure, not an architecture failure**. vLLM resolved the
target as `Gemma4ForConditionalGeneration`, resolved the drafter as
`DFlashDraftModel`, loaded both target and drafter, shared target
`embed_tokens`/`lm_head` with the drafter, used aux layers
`(1, 6, 11, 17, 22, 27)`, compiled both the backbone and eagle/DFlash head, then
failed KV allocation:

```text
Available KV cache memory: 0.05 GiB
0.55 GiB KV cache is needed for max seq len 4096
estimated maximum model length is 208
```

Decision: continue the DFlash lane with tighter smoke settings before judging
performance. The next probe is the same identity with
`max_model_len=2048`, `max_num_batched_tokens=768`, and
`gpu_memory_utilization=0.98`.

Second vLLM/XPU DFlash smoke:

- run:
  `data/gemma4-vllm-int8pc-dflash-gpu0-ctx2048-gmu098-smoke-20260624T091041Z/`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-dflash/servers/gemma4-vllm-int8pc-dflash-gpu0-ctx2048-gmu098-smoke-20260624T091041Z.server.log`
- same target/drafter/spec config, but `max_model_len=2048`,
  `max_num_batched_tokens=768`, `gpu_memory_utilization=0.98`;
- prefix caching disabled; one fresh p512/o512 benchmark row.

Outcome:

- canary: **64/64 pass**;
- fresh p512/o512 row: **38.15443892003087 tok/s after TTFT**,
  **36.898668077999695 tok/s wall**, TTFT `0.4567s`;
- server metrics during the benchmark: mean acceptance length about **3.51**,
  draft throughput about `181.5 tok/s`, accepted throughput about
  `30.4 tok/s`, per-position acceptance falling to zero after position 8/9.

Decision: mechanically successful but not competitive. This confirms Gemma4
DFlash can run in local vLLM/XPU despite the Qwen-named executor, but graph-off
vLLM is far below the llama.cpp Q8/MTP fresh record. The only remaining DFlash
speed lever worth a probe is XPU PIECEWISE graph capture for the tiny decode
query shape, while keeping prefill effectively eager via small capture size.

Third vLLM/XPU DFlash smoke, graph enabled:

- run:
  `data/gemma4-vllm-int8pc-dflash-gpu0-ctx2048-graphcap16-smoke-20260624T091431Z/`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-dflash/servers/gemma4-vllm-int8pc-dflash-gpu0-ctx2048-graphcap16-smoke-20260624T091431Z.server.log`
- same target/drafter/spec identity as the second smoke, with
  `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":16}`;
- graph capture did run: the log reports five PIECEWISE capture sizes,
  `0.85 GiB` graph memory, and capture finished in `7s`;
- prefix caching disabled; one fresh p512/o512 benchmark row.

Outcome:

- canary: **64/64 pass**;
- fresh p512/o512 row: **38.26907827338552 tok/s after TTFT**,
  **36.99987402254929 tok/s wall**, TTFT `0.4589s`;
- server metrics during/around the benchmark: mean acceptance length ranged
  roughly `3.37-4.17`, draft throughput up to about `229 tok/s`, and accepted
  throughput about `27-48 tok/s`.

Decision: close the current vLLM DFlash lane as **valid but noncompetitive**.
It is fresh-response-valid and mechanically correct, but graph capture does not
materially improve throughput on this local vLLM/XPU stack. The result remains
far below the llama.cpp Q8-target/Q4_0-draft MTP record
(`95.26352416631231 tok/s`). Further DFlash work would need a vLLM source/PR
optimization, not more runtime flags.

## 2026-06-24T0920 Q4_0 draft depth closeout

After the Q4_0 MTP draft became the current valid fresh-response record, a
four-GPU screen checked whether increasing `n_max` above 7 could recover the
`>150 tok/s` target through longer proposals. All runs used the current
record-compatible identity:

- Q8 target/verifier:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- Q4_0 MTP draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- f16 target/draft KV, `--ctx-checkpoints 0`, VMM off, `UBATCH_SIZE=512`,
  `POLL=100`, flash attention off, backend draft sampling off,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`;
- `BENCH_PROMPT_MODE=filled-long`, one measured p512/o512 row, no
  n-gram/history/cache/prefix acceleration, `cached_tokens=0` on the measured
  row.

| Run | Change | Canary | Fresh tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n8-q40-p012-freshscreen-20260624T092025Z/` | `n_max=8`, `p_min=0.12` | 256/256 | `63.83053305452225` | `57.12108600834848` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n9-q40-p012-freshscreen-20260624T092025Z/` | `n_max=9`, `p_min=0.12` | 256/256 | `68.65300880094985` | `60.99558538900098` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n10-q40-p012-freshscreen-20260624T092025Z/` | `n_max=10`, `p_min=0.12` | 256/256 | `71.62088562649002` | `63.405762493699974` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n8-q40-p010-freshscreen-20260624T092025Z/` | `n_max=8`, `p_min=0.10` | 256/256 | `63.87701568922013` | `57.21757180330594` | valid loss |

Decision: close depth-only tuning for the current scalar MTP recipe. The Q4_0
draft does not change the prior conclusion: above `n=7`, the extra serialized
assistant draft work costs more than any extra accepted fresh tokens. The
current valid fresh-response best remains
`data/gemma4-q8-gpu0-mtp-n7-draftq40-full-20260624T081218Z/` at
`95.26352416631231 tok/s` after TTFT. Further progress requires reducing the
serialized MTP draft-decode shape or a different fresh-valid speculation engine,
not deeper `n_max` sweeps.

## 2026-06-24T0930 direct MTP argmax-ID export

After the fused-unroll losses, the next smallest source-level patch tested a
scalar-loop-only direct greedy argmax ID export for the Gemma4 MTP draft
context. This is deliberately narrower than the prior generic backend argmax
path:

- no backend sampler chain is configured;
- the MTP draft graph attaches `ggml_argmax(logits)` directly to
  `llm_graph_result::t_sampled`;
- `llama_context` copies only that one sampled token ID back to host;
- the stricter variant also stops marking raw logits as graph outputs and stops
  allocating the host raw-logits output buffer when
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`;
- the scalar speculative loop consumes `llama_get_sampled_token_ith()` before
  falling back to the existing CPU fast-argmax path (direct mode stops drafting
  on null rather than scanning stale logits).

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/llamacpp-mtp-direct-argmax-ids-20260624.patch`

Smoke 1, direct sampled ID while still keeping the raw-logits host buffer:

- run:
  `data/gemma4-q8-gpu0-mtp-n7-directargmaxids-smoke-20260624T093003Z/`;
- canary: **256/256 pass**;
- first no-cache p512/o512 row: **94.5178205516173 tok/s** after TTFT,
  `80.76285064165828` wall, `cached_tokens=0`;
- profile confirmed the intended path:
  `fast_logits_ms=0`, `fast_scan_ms=0`, `vocab_scanned=0`,
  `sampler_calls=0`.

Smoke 2, direct sampled ID with raw logits removed from output topology:

- run:
  `data/gemma4-q8-gpu0-mtp-n7-directargmaxids-norawlogits-smoke-20260624T093332Z/`;
- canary: **256/256 pass**;
- first no-cache p512/o512 row: **96.06724620740458 tok/s** after TTFT,
  `81.92843771133595` wall, `cached_tokens=0`.

Full validation of the no-raw-logits variant:

- run:
  `data/gemma4-q8-gpu0-mtp-n7-directargmaxids-norawlogits-full-20260624T093545Z/`;
- canary: **384/384 pass**;
- all eight benchmark rows had `cached_tokens=0`;
- **fresh headline row 0:** `94.36999191392307 tok/s` after TTFT,
  `80.6349320542177` wall, TTFT `0.9241519309871364s`;
- supporting rows: mean `94.68613940299132`, median `94.47859282014346`,
  max `96.18396532938726`;
- final profile still dominated by serialized draft decode:
  `draft_decode_ms=11788.274`, `draft_decodes=9072`, `vocab_scanned=0`.

Decision: **valid loss / useful patch artifact, no LocalMaxxing submission**.
The direct-ID path is correct and removes CPU draft vocab scan/logits transfer,
but it does not beat the current valid fresh-response headline
`95.26352416631231 tok/s` from
`data/gemma4-q8-gpu0-mtp-n7-draftq40-full-20260624T081218Z/`. The later
`96.18 tok/s` row is supporting data only; under the fresh-response rule the
headline is row 0 from the full validation run. This closes draft-side
token-selection micro-optimization as a material route. The remaining exposed
cost is the serialized assistant `llama_decode()` loop / assistant graph body.

## 2026-06-24T1005 direct device `h_nextn` handoff probe

After direct argmax-ID export removed draft-side vocab scan/logit transfer but
failed to beat the Q4_0 record, a narrower device-resident handoff was tested:
copy the target `h_nextn` row directly into the assistant input embedding buffer
for the next draft step, avoiding the host hidden-state read/write path.

Patch artifacts:

- prior direct-ID patch:
  `patches/gemma4-26b-a4b-q8-b70/llamacpp-mtp-direct-argmax-ids-20260624.patch`;
- phase profiler:
  `patches/gemma4-26b-a4b-q8-b70/llamacpp-mtp-decode-phase-profile-20260624.patch`;
- full current research stack including direct-ID, profiling, and device
  handoff:
  `patches/gemma4-26b-a4b-q8-b70/llamacpp-current-directargmax-profile-deviceh-stack-20260624.patch`.

Runs:

| Run | Change | Canary | Fresh tok/s | Wall tok/s | Output SHA | Decision |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `data/gemma4-q8-gpu0-mtp-n7-deviceh-smoke-20260624T100534Z/` | `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`, `LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF=1`, profiling on | 64/64 | `96.12759403073476` | `81.97285111047628` | `d4cf5f90...` | attractive smoke only; not promoted |
| `data/gemma4-q8-gpu0-mtp-n7-deviceh-benchonly-20260624T100911Z/` | same device handoff, benchmark-only fresh row | 0 | `94.34944338398319` | `80.3216362578579` | `d3236ebe...` | valid loss / no canary gate |

Fresh-response validity note: the smoke row had `cached_tokens=0`, but it
followed only a 64-row canary and changed the deterministic output hash to a
comma-separated variant. The bench-only control used no canary and returned the
original output hash, but its fresh row was below the `95.26352416631231 tok/s`
record. Do **not** promote the `96.127` smoke or submit it to LocalMaxxing.

Profile comparison:

- direct-argmax bench-only profile:
  `draft_decode_ms=636.697`, decode phase `total_ms=649.857`,
  `process_ubatch_ms=216.129`, `post_extract_ms=424.359`;
- device-handoff bench-only profile:
  `draft_decode_ms=631.886`, handoff `4.661 ms`, decode phase
  `total_ms=643.975`, `process_ubatch_ms=214.723`,
  `post_extract_ms=419.518`.

Decision: valid loss and useful source artifact. The device handoff saves only
about `6 ms` over a full 512-token generation, far short of a 2x-class lever.
It also has a research-only sharp edge: if a graph rebuild occurs while the
device handoff path is active, the current patch should fail closed rather than
falling back to uploading stale host embeddings. Leave the patch archived, but
do not use `LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF=1` for record attempts until that
fallback is hardened.

## 2026-06-24T1015 code audit conclusion: scalar MTP is structurally capped

A read-only source audit of `common_speculative_impl_draft_mtp::draft()` found
the current scalar MTP hot path still performs one assistant `llama_decode()` per
draft token:

- seed one assistant row;
- call `llama_decode(ctx_dft, batch)` for one step;
- sample or read one draft token;
- prepare one next row;
- loop.

The direct-ID and device-handoff patches remove host-side token-selection and
hidden-state traffic, but they do not change the one-decode-per-draft-token
cadence. This explains why the current family plateaus around the valid Q4_0
record and why deeper `n_max` becomes slower: extra accepted-token opportunity
costs extra serialized assistant graph executions.

Credible path to the `>150 tok/s` fresh-response target:

1. Add a Gemma4-assistant-only direct-greedy unrolled graph path. Inside one
   graph, compute assistant logits for step `k`, run backend `argmax`, feed that
   token id into `model_other->tok_embd` for step `k+1`, feed `h_nextn`, and
   repeat for a fixed unroll length.
2. Extend graph result plumbing to return a vector of sampled token IDs instead
   of the current single `t_sampled` row.
3. Add graph-params/reuse-key support for the unroll length and scale graph node
   limits appropriately.
4. Gate the path narrowly: shared-memory Gemma4 assistant, single sequence,
   deterministic greedy draft only, no grammar/penalties/logit-bias/sampling
   semantics that direct argmax cannot preserve.

This is now the preferred source-level route. Further p-min/thread/runtime
neighborhood sweeps are expected to be small losses unless they accompany the
unrolled assistant graph work.

## 2026-06-24T1022 p-split screen: valid losses, no promotion

After the direct-ID/device-handoff lane failed to beat the Q4_0 draft record,
four parallel `--spec-draft-p-split` probes tested whether splitting the MTP
probability threshold could recover more fresh throughput without changing
quality. Common identity:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- one B70 replica per run, llama.cpp record stack AOT binary;
- `n_max=7`, `n_min=2`, `p_min=0.12`, backend sampling off,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`;
- f16 target/draft KV, `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`,
  `POLL=100`, flash attention off, `--ctx-checkpoints 0`;
- `filled-long` p512/o512 benchmark, one fresh measured row, `cached_tokens=0`;
- 512 chat-canary rows, all passing;
- deterministic output SHA: `d3236ebed08dda8f19a0fec78622967b3622704da06819c98a7e0e63f90d982b`.

| Run | `p_split` | Canary | Fresh tok/s after TTFT | Wall tok/s | TTFT s | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-mtp-n7-q40-psplit005-freshscreen-20260624Tnext/` | `0.05` | 512/512 | `94.75432160286755` | `80.2390197660229` | `0.9774879019823857` | valid loss |
| `data/gemma4-q8-gpu1-mtp-n7-q40-psplit010-freshscreen-20260624Tnext/` | `0.10` | 512/512 | `94.91977999042612` | `80.77585305309783` | `0.9444994060031604` | valid loss |
| `data/gemma4-q8-gpu2-mtp-n7-q40-psplit015-freshscreen-20260624Tnext/` | `0.15` | 512/512 | `94.85955056100765` | `80.59957945287907` | `0.9549371039902326` | valid loss |
| `data/gemma4-q8-gpu3-mtp-n7-q40-psplit020-freshscreen-20260624Tnext/` | `0.20` | 512/512 | `95.01982228111196` | `81.01567694644461` | `0.9314151360013057` | best of screen, still below record |

Conclusion: `p_split` is not the next lever. The best screened value,
`p_split=0.20`, remained below the current fresh-response headline
`95.26352416631231 tok/s` from the Q8 target + Q4_0 draft full validation.
Do not submit or promote these rows.

## 2026-06-24T1030 direct argmax unroll prototype: quality-smoke pass, performance loss

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/llamacpp-direct-argmax-unroll-negative-stack-20260624.patch`

What changed:

- adds `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL`;
- reuses direct argmax ID mode (`LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`) so
  in-graph `ggml_argmax` IDs feed the next assistant token embedding row;
- gates the path to shared-memory Gemma4 MTP, direct greedy draft, single
  sequence, non-chained heads, one-token/one-output graph shape;
- leaves the Q8 target verifier unchanged.

Build:

- rebuilt `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- `bash -n` passed for the harness edits;
- build emitted the known UI npm engine warning but completed `llama-server`.

Harness fix from this pass: `scripts/run-gemma4-26b-first-baseline.sh` and
`scripts/run-gemma4-26b-llamacpp-replica.sh` now record
`LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL` in summaries/logs. These runs were
launched before that metadata fix, so infer the unroll value from the label and
server log.

Common identity: Q8 target/verifier, Q4_0 MTP draft, f16 target/draft KV,
`n_max=7`, `n_min=2`, `p_min=0.12`, backend sampling off, fast argmax,
`--ctx-checkpoints 0`, `UBATCH_SIZE=512`, `POLL=100`, flash attention off,
`filled-long` p512/o512, first measured row only, `cached_tokens=0`.

| Run | Unroll | Canary | Fresh tok/s after TTFT | Wall tok/s | Output SHA | Acceptance / failure | Decision |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| `data/gemma4-q8-gpu0-mtp-n7-q40-directunroll2-smoke-20260624T103229Z/` | 2 | 32/32 | `63.015935308765755` | `56.61442830513479` | `d3236ebe...` | benchmark `340/340` accepted, mean length `3.00` | valid smoke loss |
| `data/gemma4-q8-gpu1-mtp-n7-q40-directunroll3-smoke2-20260624T103350Z/` | 3 | 32/32 | `69.75474433923245` | `61.82607599821259` | `d4cf5f90...` | benchmark `382/385` accepted, mean length `3.96`; comma-style output hash | smoke loss, output style drift |
| `data/gemma4-q8-gpu0-mtp-n7-q40-directunroll4-smoke-20260624T103034Z/` | 4 | 64/64 | `78.70814672038169` | `68.98289626666596` | `d3236ebe...` | benchmark `407/412` accepted, mean length `4.95` | valid smoke loss |
| `data/gemma4-q8-gpu2-mtp-n7-q40-directunroll5-smoke2-20260624T103350Z/` | 5 | 32/32 | `83.38703909237309` | `72.27068802707005` | `d3236ebe...` | benchmark `424/432` accepted, mean length `5.87` | best unroll smoke, still far below record |
| `data/gemma4-q8-gpu3-mtp-n7-q40-directunroll7-smoke2-20260624T103350Z/` | 7 | startup crash | n/a | n/a | n/a | `GGML_ASSERT((int)sched->hash_set.size >= measure_graph->n_nodes + measure_graph->n_leafs)` in `ggml_backend_sched_reserve()` | graph node/leaf budget failure |

Conclusion: direct unroll proves the dataflow is possible, but it is not the
right speed shape. Even with high acceptance, the unrolled assistant graph is
heavier than the scalar draft loop it replaces. Unroll5 accepted nearly all
drafts (`424/432`) and still reached only `83.39 tok/s`, below the current
`95.2635 tok/s` headline and nowhere near `>150 tok/s`.

Do not promote or submit these rows. Before any future promotion attempt, the
unroll gate also needs a production-quality deterministic-greedy predicate
shared with the target sampler path so grammar, penalties, logit bias, or other
non-greedy sampling modes hard-disable the shortcut.

## 2026-06-24T1037 Vulkan Q4_0 draft control: valid loss

Follow-up to the earlier Vulkan backend smoke using the same Q4_0 MTP draft as
the current SYCL record, to rule out "Vulkan plus the better draft file" as a
missed lane.

Common identity:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- target/draft device: `Vulkan0`;
- llama.cpp Vulkan build at `/home/steve/src/llama.cpp-latest-gemma/build-vulkan-b70/bin/llama-server`;
- `n_max=7`, `n_min=2`, `p_min=0.12`, backend sampling off,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`;
- f16 target/draft KV, `UBATCH_SIZE=512`, `POLL=100`, flash attention off,
  `--ctx-checkpoints 0`;
- `filled-long` p512/o512 benchmark, one fresh measured row, `cached_tokens=0`.

Result:

- run: `data/gemma4-q8-vulkan0-mtp-n7-q40-smoke-20260624T103743Z/`;
- canary: `32/32`;
- fresh first row after TTFT: `48.751303749100515 tok/s`;
- wall throughput: `45.088939991341185 tok/s`;
- TTFT: `0.853051357989898 s`;
- output SHA: `d4cf5f90168bd7a276a1bc3072aa2641d8b33eb7a9a269271650586091600f31`
  (comma-style output drift versus the promoted SYCL Q4_0 record).

Decision: rejected. Vulkan remains mechanically viable but far below the SYCL
record (`95.26352416631231 tok/s`) for this model and quality lane. Do not
spend more promotion validation budget on Vulkan unless upstream Battlemage
support changes substantially.

## 2026-06-24T1046 direct IDs + device-handoff full validation: valid loss

Follow-up to the `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1` and
`LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF=1` smokes. This tested whether the small
draft-output transfer shortcut was real at full canary depth.

Common identity:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- one B70 GPU0 replica, llama.cpp record-stack AOT binary;
- `n_max=7`, `n_min=2`, `p_min=0.12`, backend sampling off,
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`,
  `LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF=1`;
- f16 target/draft KV, `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`,
  `POLL=100`, flash attention off, `--ctx-checkpoints 0`;
- `filled-long` p512/o512 benchmark, one fresh measured row, `cached_tokens=0`.

Result:

- run: `data/gemma4-q8-gpu0-mtp-n7-q40-directids-deviceh-full-20260624T104659Z/`;
- canary: `384/384` repeats, `1536/1536` rows, all passing;
- fresh first row after TTFT: `94.04648675008646 tok/s`;
- wall throughput: `80.33770604985402 tok/s`;
- TTFT: `0.9289809039910324 s`;
- output SHA: `d3236ebed08dda8f19a0fec78622967b3622704da06819c98a7e0e63f90d982b`
  (same as the promoted Q8 target + Q4_0 draft record).

Decision: valid loss. The shortcut is quality-safe, but it is slower than the
current headline (`95.26352416631231 tok/s`) and should not be promoted or
submitted. The result reinforces the subagent audit conclusion: the scalar MTP
draft loop is the cap; removing secondary transfers/logit materialization is
not enough to move the headline. Future source work needs to change the draft
execution shape itself.
