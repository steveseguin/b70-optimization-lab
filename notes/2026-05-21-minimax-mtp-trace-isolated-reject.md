# MiniMax M2.7: MTP Feasibility and Isolated Trace Rejection

Date: 2026-05-21

## Scope

This pass checked whether speculative/MTP work was a safe next optimization
path and tried to add lower-level llm-scaler tracing around the MiniMax W4A16
top-k path.

The quality policy remains strict:

- raw145 n64 exact token hash:
  `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact token hash:
  `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite hash:
  `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- repeated arithmetic r8 hash:
  `261779104d5abf1642713bfc560ca8d2d6c0f16edbcc929c8b0819b5a760dd7c`

## MTP / Speculative Decode Check

Checkpoint:

`/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`

The config advertises MTP metadata:

- `use_mtp: true`
- `num_mtp_modules: 3`
- `mtp_transformer_layers: 1`
- `num_hidden_layers: 62`

However, the checkpoint index does not contain matching MTP/draft tensors:

- no keys matching `mtp`, `multi`, `nextn`, `draft`, `spec`, or `predict`
- no layer keys beyond the normal 62 decoder layers

The bundled `modeling_minimax_m2.py` also does not implement a MiniMax MTP
forward path. vLLM has MTP/Eagle implementations for other model families and
has a registry entry for `Eagle3MiniMaxM2ForCausalLM`, but this AutoRound
checkpoint does not include the required draft/MTP weights.

Decision: do not implement MTP or speculative decode against this checkpoint
unless real MiniMax M2.7 draft/MTP weights are available. Synthesizing a draft
path would put quality at risk and would not satisfy the exact-token gates.

## Isolated Trace Attempt

Isolated source path:

`/mnt/fast-ai/src/llm-scaler-promoted-rebuild-20260520T120230Z/vllm/custom-esimd-kernels-vllm`

The attempted instrumentation changed the MiniMax top-k helper to go through
the existing `submit_kernel(...)` trace wrapper. It built and imported, but it
was not quality-safe:

- trace-enabled eager raw145 n64 generated 64 token id `0` values
- graph/no-trace validation after the same source rebuild also generated 64
  token id `0` values
- both runs failed with `degenerate or corrupt generated output`

Relevant artifacts:

- `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/minimax-trace-eager-topk-raw145-n64-20260521T1830Z.json`
- `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/minimax-topk-trace-wrapper-normal-raw145-n64-20260521T1834Z.json`
- `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/build-moe-int4-u4-oneapi2025-20260521T184022Z.log`

The trace patch was reverted, but the isolated source/cache combination still
failed the NUL guard. Treat that isolated fork as unsafe until it is recloned or
diffed against the promoted source and revalidated from a clean build/cache.

## Promoted Path Sanity

Promoted runtime path:

`/home/steve/src/llm-scaler/vllm/custom-esimd-kernels-vllm/python`

Promoted env:

`/home/steve/llm-optimizations-publish/repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`

After unsetting `LLM_SCALER_KERNELS` and returning to the promoted path, raw145
n64 passed with the expected token hash and zero NUL/control output:

`/home/steve/bench-results/minimax-m2.7-post-repro-optimization/minimax-promoted-path-raw145-n64-20260521T1849Z.json`

The strict post-experiment control also passed:

- raw145 n64 exact token hash matched
- raw145 n256 exact token hash matched
- semantic suite passed
- arithmetic repeat r8 passed

Benchmark result:

- output tok/s: 88.210663
- total tok/s: 117.614218
- prompt/output: p512/n1536
- TP4, 4x Intel Arc Pro B70, block 256, max model len 2048

Summary artifact:

`/home/steve/bench-results/minimax-m2.7-post-repro-optimization/minimax-promoted-path-post-isolated-reject-strict-tp4-ctx2048-mbt512-bs256-20260521T185149Z-summary.json`

Decision: no LocalMaxxing submission. The run is quality-clean and useful as a
control, but it is below the accepted 93.443623 output tok/s result.

## Next Work

Do not continue experiments from the rejected isolated fork. The next safe
optimization path is:

1. Start from the promoted source path or a fresh copy of it.
2. Before source edits, run raw145 n64/n256 on the exact source/cache to prove
   the baseline is clean.
3. Add instrumentation that does not synchronize inside generation or alter
   MiniMax top-k submission semantics.
4. Prefer synthetic microbenchmarks for llm-scaler custom ops before routing a
   new kernel through full generation.
5. Only run p512/n1536 throughput after exact-token quality gates pass.

The most promising remaining performance work is still reducing decode-time
framework/collective overhead, but any fusion must be staged behind exact-token
quality checks because the known failure modes can look fast while silently
producing corrupt token id `0` output.
