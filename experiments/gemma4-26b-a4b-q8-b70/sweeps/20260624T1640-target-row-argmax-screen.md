# 2026-06-24T1640 - target verifier row-argmax screen

Goal: reduce Gemma 4 26B A4B Q8 target verifier overhead without using
history, n-gram continuation, response reuse, prefix reuse, or warmed benchmark
state. This keeps the normal Q8 target verification contract and only changes
how greedy verifier token IDs are extracted.

Patch snapshot:

- `patches/gemma4-26b-a4b-q8-b70/20260624T1640-llamacpp-gemma4-target-row-argmax-screen-current.patch`
- sha256: `0f267bac8e99eed2c4da30d4ba635b8272e68347e7c1dcd58b103222f37f7960`
- scope: `common/sampling.cpp`, `include/llama.h`, `src/llama-cparams.h`,
  `src/llama-context.cpp`, `src/llama-graph.cpp`, `src/llama-graph.h`

## Patch summary

Adds opt-in target-side row argmax IDs:

- `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`
- new target cparam `spec_verify_direct_argmax_ids`
- target verifier graph stores one compact sampled token ID per output row
- sampling consumes sampled IDs directly for greedy verifier rows
- added `llama_get_sampled_token_ith_nosync()` to avoid an extra synchronizing
  accessor after the graph output copy

This is still **not** the fused LM-head argmax path. The backend still computes
the verifier logits internally and then applies row argmax; the win is avoiding
full verifier logits D2H transfer and host-side argmax scans.

## Runs

### Crash: first sampled-token path not updated

`gemma4-q8-gpu0-mtp-n7-targetrowargmax-screen-20260624T163247Z`

Server crash:

```text
common/sampling.cpp:198: GGML_ASSERT(logits != nullptr) failed
get_logits_ith: invalid logits id 38, reason: no logits
```

Cause: normal first-token sampling attempted to read logits after the patch
stopped exporting logits. Fixed by making the sampled-ID read explicit whenever
`LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1` and a sampled ID is available.

### Screen 2: sync accessor

`data/gemma4-q8-gpu0-mtp-n7-targetrowargmax-screen2-20260624T163425Z/`

- canary: `128/128`
- first fresh row: `100.94822992976141 tok/s` after TTFT
- wall throughput: `88.03605131864316 tok/s`
- TTFT: `0.7438925729948096 s`
- prompt/completion: `588/512`
- `cached_tokens=0`

### Screen 3: nosync accessor

`data/gemma4-q8-gpu0-mtp-n7-targetrowargmax-nosync-screen-20260624T163737Z/`

- canary: `128/128`
- first fresh row: `100.9968927292644 tok/s` after TTFT
- wall throughput: `88.12077379167972 tok/s`
- TTFT: `0.7407448249869049 s`
- prompt/completion: `588/512`
- `cached_tokens=0`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-mtp-n7-targetrowargmax-nosync-screen-20260624T163737Z.server.log`

Representative run identity:

```bash
cd /home/steve/qwen36-results-main
PORT=18310 \
GPU_INDEX=0 \
LLAMA_DEVICES=SYCL0 \
ONEAPI_DEVICE_SELECTOR=level_zero:0 \
LLAMA_SERVER=/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server \
LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1 \
MTP_N_MAX=7 MTP_N_MIN=2 MTP_P_MIN=0.12 MTP_BACKEND_SAMPLING=0 \
MTP_DRAFT_FAST_ARGMAX=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7 \
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1 \
MTP_DRAFT_THREADS=32 MTP_DRAFT_THREADS_BATCH=32 \
BATCH_SIZE=1024 UBATCH_SIZE=1024 THREADS=8 POLL=100 \
GGML_SYCL_ENABLE_VMM=0 GGML_SYCL_DISABLE_GRAPH=0 GGML_SYCL_DISABLE_OPT=0 \
MTP_EXTRA_ARGS='--ctx-checkpoints 0' \
BENCH_PROMPT_MODE=filled-long CANARY_REPEATS=32 BENCH_REPEATS=1 \
bash scripts/run-gemma4-26b-mtp-candidate.sh <label>
```

## Validity

The screen result is valid fresh-response evidence:

- single fresh benchmark request;
- `prompt_tokens_details.cached_tokens=0`;
- no n-gram/history acceleration;
- MTP draft is generated from the current request and verified by the Q8 target.

It is **not** promoted as a headline record:

- only a screen run, not the full promoted 384-row canary plus multi-repeat
  support;
- the current promoted Q8 fresh record is `98.617 tok/s`, so this is only a
  small source-level win;
- the actual target remains `>150 tok/s`, and this patch does not materially
  close that gap.

## Decision

Keep the patch as a candidate artifact because it is quality-preserving and
fresh-valid, but do not submit or promote it yet. The result confirms that
plain row argmax is not enough: avoiding host logits extraction buys about
`+2.4 tok/s`, while reaching `>150 tok/s` needs a larger verifier/draft cost
removal.

Next source-level ideas:

1. Fused target verifier LM-head argmax, ideally a multi-row
   `ggml_mul_mat_argmax()` path that never materializes verifier logits.
2. Defer target `h_nextn` extraction until the accepted boundary row is known.
3. Continue using fresh-row-only validity: no warmed continuation averages as
   headline throughput.

## Follow-up: defer target `h_nextn` extraction

Patch snapshot:

- `patches/gemma4-26b-a4b-q8-b70/20260624T1655-llamacpp-gemma4-target-rowargmax-deferh-fusedtarget-crash-current.patch`
- sha256: `0245a68e98b455df9dea059a88d0ecc093785f4160327d25331de99af7c77d19`
- lines: `3228`
- includes the current row-argmax stack, the successful deferred target
  `h_nextn` extraction path, and the default-off fused target LM-head argmax
  prototype described below.

The deferred `h_nextn` path adds:

- `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`;
- `llama_set_mtp_defer_nextn_extract(ctx, bool)`;
- `llama_copy_embeddings_nextn_ith(ctx, i, dst)`;
- verifier-side metadata-only processing until accept-time, then a direct copy
  of the accepted boundary row.

The path is enabled only for the current safe shape:

- memory-shared target/draft setup;
- no chained heads;
- single sequence.

Screen:

`data/gemma4-q8-gpu0-mtp-n7-targetrowargmax-deferh-screen-20260624T164705Z/`

- canary: `128/128`
- first fresh row: `101.19757604826397 tok/s` after TTFT
- wall throughput: `88.18958242937919 tok/s`
- TTFT: `0.7462646670173854 s`
- prompt/completion: `588/512`
- `cached_tokens=0`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-mtp-n7-targetrowargmax-deferh-screen-20260624T164705Z.server.log`

Decision: valid but tiny. It improves over the nosync row-argmax screen by
only about `+0.20 tok/s`, so it is useful cleanup but not a path to `>150 tok/s`
by itself.

Representative command:

```bash
cd /home/steve/qwen36-results-main
PORT=18310 \
GPU_INDEX=0 \
LLAMA_DEVICES=SYCL0 \
ONEAPI_DEVICE_SELECTOR=level_zero:0 \
LLAMA_SERVER=/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server \
LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1 \
LLAMA_MTP_DEFER_TARGET_H_NEXTN=1 \
MTP_N_MAX=7 MTP_N_MIN=2 MTP_P_MIN=0.12 MTP_BACKEND_SAMPLING=0 \
MTP_DRAFT_FAST_ARGMAX=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7 \
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1 \
MTP_DRAFT_THREADS=32 MTP_DRAFT_THREADS_BATCH=32 \
BATCH_SIZE=1024 UBATCH_SIZE=1024 THREADS=8 POLL=100 \
GGML_SYCL_ENABLE_VMM=0 GGML_SYCL_DISABLE_GRAPH=0 GGML_SYCL_DISABLE_OPT=0 \
MTP_EXTRA_ARGS='--ctx-checkpoints 0' \
BENCH_PROMPT_MODE=filled-long CANARY_REPEATS=32 BENCH_REPEATS=1 \
bash scripts/run-gemma4-26b-mtp-candidate.sh <label>
```

## Follow-up: fused target LM-head argmax crash

The default-off prototype `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` tried to
avoid full verifier logits materialization by emitting one sampled token ID per
target verifier row from `ggml_mul_mat_argmax(model.output, row_h)`. This is the
right kind of larger lever, but the current graph wiring is not correct.

Runs:

- `data/gemma4-q8-gpu0-mtp-n7-targetfusedargmax-deferh-screen-20260624T165319Z/`
- `data/gemma4-q8-gpu0-mtp-n7-targetfusedargmax2-deferh-screen-20260624T165509Z/`

Both crashed before canary output. Representative server log:

```text
/home/steve/src/llama.cpp-gemma-record-stack/ggml/src/ggml-backend.cpp:194:
GGML_ASSERT(buffer) failed

#3 ggml_backend_buffer_is_host()
#4 llm_graph_input_out_ids::set_input(llama_ubatch const*)
#5 llm_graph_result::set_inputs(llama_ubatch const*, bool)
#6 llama_context::process_ubatch(...)
```

The likely cause is graph-input lifetime/allocation mismatch: the model graph
still registers `inp_out_ids`, but the fused branch returns before the normal
full-logits output path consumes that input, so the input tensor is not allocated
into a backend buffer and `set_input()` later asserts.

Decision: keep the failed prototype as a patch artifact, but do not promote or
run it as a candidate until the graph input ownership is fixed. The lower-risk
implementation direction is to make the target graph explicitly skip building
or setting `inp_out_ids` when the fused verifier path is active and all tokens
are verifier outputs, or to add a separate graph type/cparam for this verifier
mode instead of trying to branch late inside `gemma4.cpp`.

## Follow-up: fused target crash fixed, still slower

The `inp_out_ids` crash was fixed by skipping `build_inp_out_ids()` when the
fused verifier argmax path is requested and the target verifier graph will not
consume output IDs. This confirms the crash root cause above.

Single-row fused screen:

`data/gemma4-q8-gpu0-mtp-n7-targetfusedargmax3-deferh-screen-20260624T170326Z/`

- canary: `32/32`
- first fresh row: `88.15602712767586 tok/s` after TTFT
- wall throughput: `78.25088075546374 tok/s`
- `cached_tokens=0`

This is valid fresh-response evidence but a clear loss versus row-argmax
(`~101.20 tok/s`) and the promoted full record (`98.62 tok/s`).

## Follow-up: multi-row fused target argmax

Patch snapshot:

- `patches/gemma4-26b-a4b-q8-b70/20260624T172923Z-llamacpp-gemma4-target-fusedargmax-multi-negative-current.patch`
- sha256: `c06990fe134535976eaae56ca3d8b1d6f1ef3bcffac74380313227b8a3c46742`
- lines: `3577`

Patch scope:

- `src/models/gemma4.cpp`: emit one `ggml_mul_mat_argmax(model.output, cur)`
  vector for all verifier rows instead of one op per row;
- `src/llama-context.cpp`: allow `t_sampled_rows[0]` to copy a vector of row
  token IDs;
- `ggml/src/ggml-sycl/ggml-sycl.cpp`: allow `GGML_OP_MUL_MAT_ARGMAX` with
  `src1->ne[1] > 1`, quantize all hidden rows, and route to a multi-row kernel;
- `ggml/src/ggml-sycl/mmvq.cpp/.hpp`: add multi-row Q4_0/Q8_0 argmax kernels
  and per-vector tile reductions.

First screen crashed during scheduler placement:

`data/gemma4-q8-gpu0-mtp-n7-targetfusedargmax-multi-deferh-screen-20260624T171903Z/`

```text
ggml/src/ggml-backend.cpp:1242: GGML_ASSERT(*cur_backend_id != -1) failed
```

Cause: execution support was patched, but SYCL `supports_op()` still rejected
`GGML_OP_MUL_MAT_ARGMAX` where `b->ne[1] != 1`. Fixing the predicate allowed
the graph to load.

Working multi-row screen:

`data/gemma4-q8-gpu0-mtp-n7-targetfusedargmax-multi2-deferh-screen-20260624T172823Z/`

- canary: `32/32`
- first fresh row: `88.26374543490356 tok/s` after TTFT
- wall throughput: `78.26678563909694 tok/s`
- prompt/completion: `588/512`
- `cached_tokens=0`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-mtp-n7-targetfusedargmax-multi2-deferh-screen-20260624T172823Z.server.log`

Decision: valid but negative. Multi-row fusion fixes launch count but does not
recover the lost throughput; the fused LM-head argmax kernel is still much
slower than the row-argmax verifier path. Do **not** promote this lane unless a
future kernel rewrite changes the cost model. The useful lesson is that target
LM-head micro-optimization is not enough for `>150 tok/s`; the next work needs
to increase accepted tokens per target step or change the parallelism strategy
(for example TP/split checks or a better fresh-request draft/verifier plan).
