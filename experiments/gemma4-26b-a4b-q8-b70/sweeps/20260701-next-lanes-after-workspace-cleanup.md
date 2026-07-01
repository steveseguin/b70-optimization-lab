# 2026-07-01 Next lanes after workspace cleanup

## Context

The active workspace is `/home/steve/llm-optimizations` only. Detached
worktrees are audit/back-reference and should not be used for new experiments.
The active llama.cpp source checkout is
`/home/steve/src/llama.cpp-gemma-record-repro-c926`; before new source edits,
the current dirty record stack was preserved as:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-active-record-stack-before-fastmask-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-active-record-stack-before-fastmask-source.diffstat`

## Best next prompt-processing lane

Read-only source audit points to a gated **global-attention causal fast-mask**
path for long prefill as the next tangible prompt-processing optimization. The
latest long-context profile shows prompt time dominated by global
`FLASH_ATTN_EXT` nodes, not SWA setup. Current DV512/GQA8 FlashAttention still
loads/adds the F16 KQ mask inside the tile loop even when most global causal
long-prefill K blocks are fully valid.

Candidate design:

- keep `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`; do not reopen the failed
  `ncols2=16` branch;
- gate with default-off envs such as
  `LLAMA_EXPERIMENTAL_GLOBAL_FATTN_CAUSAL_FAST_MASK=1` and
  `LLAMA_EXPERIMENTAL_GLOBAL_FATTN_CAUSAL_FAST_MASK_MIN_Q=2048`;
- set the op flag only for global/non-SWA, causal, no-ALiBi, simple
  single-sequence long prefill with large `n_q_per_stream`;
- in the SYCL tile, skip mask loads for fully valid K blocks and keep the
  current mask path for boundary chunks and all unsupported shapes.

Likely hook points from the audit:

- `src/llama-graph.cpp` near attention graph construction and existing SWA
  left-bound gates;
- `ggml/src/ggml.c` near `ggml_flash_attn_ext` op-param setters;
- `ggml/src/ggml-sycl/fattn-common.hpp` launch plumbing;
- `ggml/src/ggml-sycl/fattn-tile.hpp` mask-add path.

Validation plan:

1. Build default-off source patch.
2. Run long-context service A/B on the existing balanced lane:
   `BATCH_SIZE=2048`, `UBATCH_SIZE=1024`, `LLAMA_PREFILL_UBATCH_SIZE=2048`,
   `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`,
   `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`,
   `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`.
3. Use the fixed long-context cases (`lc-12288-early`, `lc-16384-late`,
   `lc-22000-middle`) and keep canaries/cached-token checks.
4. If prefill improves, rerun short-decode guard with the flag enabled to prove
   the long-prefill gate does not perturb the promoted short-decode record lane.

Correctness risk: the mask may encode more than future-token causal masking
(sequence boundaries, cache holes, non-contiguous cells, unusual positions).
This is why the gate must stay conservative and default-off.

## Closed follow-up: global causal fast-mask

The global-attention causal fast-mask patch was built and tested after the
workspace cleanup. It passed canaries and exact long-context gates, but a
GPU-swapped crossover showed no real prefill improvement: control averaged
`1096.304` median prefill tok/s and fast-mask averaged `1096.821` (`+0.047%`,
noise), with AB signs flipping by GPU assignment. Do not promote or keep active.
Evidence:
`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-global-fattn-causal-fastmask-negative.md`.

## Verifier / LM-head lane status

The candidate-bound exact LM-head verifier is not currently a good record-lane
design. Row plumbing is feasible: in the full-bonus MTP verifier shape,
verifier row `r` maps to draft candidate `spec_draft[r]`, and shifted input
token `inp_tokens[r + 1]` is the same candidate. But exact verification still
needs the true target top token on the first mismatch. Current SYCL paths prove
that by scanning full vocab via argmax/top2; there is no existing
candidate-only certificate that proves a candidate beats all 262144 vocab rows
without doing equivalent work.

Low-risk verifier follow-up is diagnostic only:

- add a default-off `LLAMA_SPEC_VERIFY_CANDIDATE_PROOF_PROFILE=1` in
  `common/sampling.cpp`;
- count draft rows tested, rows where `draft[i] == sampled[i]`, first mismatch
  position, full-draft match count, and bonus-row-needed count using existing
  exact sampled IDs;
- do not change sampler state, graph shape, accepted tokens, or runtime
  semantics.

Do not treat target top2/margin as solved: the previous target-top2 diagnostic
recorded zero rows, so any renewed top2 effort must first add graph-build and
copy-path logging.

## Workspace rule for the next experiment

Use the single active workspace and preserve each experiment as a patch + note
+ compact result packet before changing direction. Do not create another linked
worktree unless the user explicitly asks for one.
