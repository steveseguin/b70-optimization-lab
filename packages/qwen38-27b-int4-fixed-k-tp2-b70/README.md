# Qwen3.8 27B AutoRound INT4 — fixed-K batch-invariant two-B70 package (candidate)

devan-carlin's AutoRound INT4 tensors of Qwen3.8-27B, served by vLLM XPU on two Intel Arc Pro B70 32 GiB cards through
the plain-GPTQ oneDNN W4A16 path with a rebuilt kernel library, on the FP8 lane's whole-graph deterministic stack.

> **Single request, TP2 (2026-09-05, R222/R227):** MTP0 `36.00 / 34.92 tok/s`, MTP depth 1 `50.83 / 51.12`, depth 4
> `68.62 / 68.23` (two fresh servers each, class-balanced median decode on the strict 12-prompt suite). Every pair
> matched all 12 complete token arrays, and every speculative server matched the MTP0 oracle 12/12 (lossless). The
> same tensors through vLLM's default routing (INC/ARK) give `32.8 tok/s` and cannot be lossless with speculation.

> **Concurrent users (c1-c64 identity ladder, 128 tokens per request, TP2):** MTP0 output byte-identical to a single
> request at every level through 64 (a near-tie prompt differs in some runs, driven by arrival timing); speculative
> depths identical through 16, with c32 >= 30/32 and c64 >= 59/64. Aggregate MTP0 decode at c64: `~998 tok/s`.

> **Matrix (TP2 and TP1, depths 0-4, R239):** running at the time of writing; its table and profiles follow.

## What makes it exact

| layer | problem | fix |
|---|---|---|
| kernel routing | `quant_method: auto-round` selects INC/ARK `woqgemm`: nondeterministic for 32-256 rows, never batch-invariant, 6-10x slower at two rows | relabel the identical tensors as plain `gptq` (`scripts/make-gptq-relabel.py`) -> oneDNN `int4_gemm_w4a16` |
| W4A16 GEMM | oneDNN picks a different K partition per row-count class | rebuilt `_xpu_C` pins a two-tier fixed-K strategy (R221 patch); decode unchanged, prefill GEMMs ~2x |
| FP16 linears (`lm_head`, `mtp.fc`) | oneDNN f16 GEMM changes class above 32 rows | `<=32`-row pieces in an opaque custom op (R224) |
| attention decode | flash-decoding split count follows batch size | `VLLM_BATCH_INVARIANT=1` |
| compiled reductions | Inductor splits reductions by row count | `"split_reductions": false` |

The last known composition dependence is the GDN kernel (launch grouping does not restore single-request
arithmetic); it accounts for the c32/c64 near-tie flips with speculation.

## Commands

See `package.json` (`preflight`, `launch`, `health`, `benchmark`, `stop`). `MTP_DEPTH=0..4` selects the speculative
depth; `TENSOR_PARALLEL_SIZE=1 XPU_DEVICE_MASK=0 GPU_MEMORY_UTILIZATION=0.96` runs one card. The image is
`ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:aaf920b0...` (image id equals the digest); the launcher verifies
the image contract, the rebuilt extension digest and the relabelled model manifest before serving.

Evidence and rationale: [`repro/qwen38-27b-autoround-int4-b70/README.md`](../../repro/qwen38-27b-autoround-int4-b70/README.md)
(fixed-K profile section) and the notes under `experiments/qwen38-27b-b70/notes/2026-09-05-qwen38-int4-*`.
