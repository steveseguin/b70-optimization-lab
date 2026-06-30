# 2026-06-30 - Gemma Q8 verifier row-shape / accept-prefix audit

Status: documentation + diagnostic only. No source edits were made and no
LocalMaxxing submission is implied.

## Baseline / Current Record

Current valid Gemma 4 26B A4B Q8 one-B70 record remains:

- result:
  `data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json`;
- primary metric: `121.41411987308553 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT across the fixed cold realistic suite;
- model / quality lane: `UD-Q8_K_XL` target/verifier, Q4_0 MTP draft;
- key config: llama.cpp `c926ad098`, `FLASH_ATTN=on`, `CTX_SIZE=32768`,
  `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`;
- validity: fixed realistic suite, each prompt once, `cached_tokens=0`.

## Why This Audit Happened

The latest profile and row-economics results point at verifier/target graph
cost, not draft or sampler host overhead:

- `target_decode_ms ~= 38.5s` vs `draft_ms ~= 2.7s`;
- `sampled_extract_ms ~= 1.66s` is backend output-read/sync boundary, not a
  useful host vector loop;
- row-economics oracle: `3679` current verifier output rows vs `2893` oracle
  rows (`786` saved, `21.365%`) if an exact verifier could stop at the first
  mismatch while preserving full-match bonus rows.

Two read-only subagent audits were run against the current source tree:

1. A smaller candidate: force/preserve multi-row verifier LM-head shape so the
   Q8 output projection sees `ncols=2..4` instead of repeated `ncols=1`.
2. A deeper candidate: implement a new exact accept-prefix verifier LM-head op
   that computes row 0 target top-1, compares on-device to draft token 0, then
   computes later verifier/bonus rows only as needed.

## Diagnostic: Current Verifier Already Uses 4-Output Microbatches

The current SYCL node profile repeatedly reports the hot LM-head node detail as
one-column:

```text
MUL_MAT:node_1775 ... token_embd.weight ... src1{GET_ROWS:result_norm ... ne=[2816,1,1,1]}
```

That detail is misleading. The profiler keys entries by node name and preserves
the first tensor detail it saw. Prompt / one-output graphs often run first, so
the printed detail can say `ne=[...,1,...]` even when later verifier graphs use
the same node key with wider output rows.

To confirm the actual verifier batch shape, a tiny diagnostic run was executed:

```bash
cd /home/steve/qwen36-results-main
LLAMA_BATCH_DEBUG=1 LLAMA_ARG_LOG_VERBOSITY=999 \
GPU_INDEX=0 PORT=18420 \
LABEL=gemma4-q8-gpu0-lmhead-shape-batchdebug-verbose-20260630A \
FLASH_ATTN=on CTX_SIZE=32768 GGML_SYCL_ENABLE_VMM=1 \
BATCH_SIZE=1024 UBATCH_SIZE=1024 THREADS=8 POLL=100 \
CANARY_REPEATS=1 REALISTIC_GATE=0 BENCH_REPEATS=1 PROMPT_TOKENS=32 MAX_TOKENS=12 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Run artifacts:

- `data/gemma4-q8-gpu0-lmhead-shape-batchdebug-verbose-20260630A/summary.json`;
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-lmhead-shape-batchdebug-verbose-20260630A.server.log`.

It was synthetic diagnostic only (`REALISTIC_GATE=0`), but canary passed and
the benchmark row had `cached_tokens=0`.

Relevant split log excerpts:

```text
graph_reserve: reserving a graph for ubatch with n_tokens = 1024, n_seqs = 1, n_outputs = 4
...
ubatch_print:   n_tokens     = 4
ubatch_print:   n_outputs    = 4
slot finish_specu: accepted 2/3 draft tokens
...
ubatch_print:   n_tokens     = 4
ubatch_print:   n_outputs    = 4
slot finish_specu: accepted 3/3 draft tokens
```

Conclusion: the normal full-bonus MTP verifier path already forms 4-token /
4-output verifier microbatches. A simple "coalesce LM-head output rows" patch is
not a real next step unless future profiling proves a specific graph path is
still splitting those verifier rows after `build_inp_out_ids`.

## Subagent Audit Conclusions

### Easy row-shape / host cleanup lanes

Closed or not currently credible:

- simple no-bonus / adaptive-bonus / staged MTP3 / late-head / prefix-tail:
  already tested and negative;
- candidate-vs-max LM-head: exact verification still needs true target top-1 on
  mismatch, so it does not remove the full-vocab max/challenger work;
- sampler-side sync / small host vector cleanup: accept-side sync measured only
  `1.734 ms` total over `896` verifier calls;
- basic LM-head row coalescing: current verifier shape already reaches
  `n_outputs=4`.

### Remaining exact verifier-row path

The only credible bonus-preserving row-output reduction is a new backend op,
roughly:

```text
ggml_mul_mat_argmax_accept_prefix(model.output, hidden_rows, verifier_tokens)
```

Semantics:

1. compute exact target top-1 for verifier row 0;
2. compare on-device with draft token 0;
3. compute row 1 only if row 0 matched;
4. compute row 2 only if rows 0-1 matched;
5. compute the bonus row only if all draft rows matched;
6. on mismatch, still return the exact target top-1 for the first failing row;
7. preserve existing target KV / rollback / bonus semantics.

Likely files:

- `src/models/gemma4.cpp`: guarded branch in the verifier graph before current
  sampled-row output;
- `ggml/include/ggml.h`, `ggml/src/ggml.c`: new op definition;
- `ggml/src/ggml-sycl/ggml-sycl.cpp`, `ggml/src/ggml-sycl/mmvq.cpp`: SYCL Q8_0
  implementation first;
- `src/llama-context.cpp`: sampled-output copying and env/cparam plumbing;
- `common/sampling.cpp`: consume skipped-row / accepted-prefix result without
  falling back to CPU argmax;
- `tools/server/server-context.cpp`: keep standard verifier rows if possible so
  hidden rows, KV, rollback, and bonus alignment remain unchanged.

Risks:

- must match current argmax tie-breaking exactly;
- must be guarded to the narrow greedy no-grammar/no-suppress-token full-output
  MTP shape, initially `n_draft == 3`;
- if the implementation serializes row dot products into multiple launches or
  loses the current efficient Q8 multi-column path, it can easily be neutral or
  negative;
- expected end-to-end upside is modest: row-economics ceiling is 21.365% of
  verifier output rows, not 21% of total decode. A realistic win is probably
  `+2` to `+6 tok/s` if implemented well.

## Decision

Do not spend more GPU time on config roulette or row-shape screens for this
short-record lane. The valid record is already above reliable `>100 tok/s`.
Future short-decode source work should either:

1. implement the exact accept-prefix verifier LM-head op with a strict parity
   mode before benchmarking; or
2. move to a different structurally justified verifier/MoE boundary reduction.

If neither is being actively implemented, pivot to a separate service lane
(prefill / long-context ladder) and rerun the short fixed suite afterward to
prove no regression.
