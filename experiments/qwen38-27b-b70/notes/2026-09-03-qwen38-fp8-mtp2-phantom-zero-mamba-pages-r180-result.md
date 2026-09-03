# R180: zeroing the GDN state pages that are actually allocated does not remove the depth-2 phantom

Date: 2026-09-03 18:10-18:16 EDT, boot 88f0984f (clean). Image `qwen38-fp8-mtp2-zero-mamba-pages-r180`
(`sha256:d3437273...`) = R178 + `patches/vllm-qwen38-xpu-record-mamba-new-blocks-r180-20260903.patch`
(`MambaManager` records its new block ids, so they reach `new_block_ids_to_zero` and the R178 worker hook).
Prereg `data/2026-09-03-qwen38-fp8-r156-mtp2-zero-mamba-pages-r180-prereg.json`. Results:
`/mnt/fast-ai/bench-results/qwen38-fp8-r156-mtp2-zero-mamba-pages-20260903-r180/query-mtp1/`.

## Result

Row 32 (`cache-c032`, 33rd request) again starts `[60, 271, 3833]`; 63/64 vs the MTP0 oracle, identical to R165,
R167, R176 and R178. The hook was live on both ranks (`R178 zeroing Mamba/GDN state pages for 48 layers`), and with
prefix caching off the Mamba manager allocates through the base-class path that now records ids, so every GDN
page handed to a new request was zeroed before its prefill.

Prereg branch taken: "phantom persists -> the stale state page is not the source".

## What is now excluded for the depth-2 phantom

- Sampler / handoff / logits index (R170, R171), device barrier and blocking H2D (R173, R174).
- Stale attention pages (zeroed by `KVBlockZeroer` upstream) and stale GDN conv/ssm pages (R180 zeroes them;
  R176 shows the page reaching request 33 was request 31's anyway, not the discarded step's).

What remains is whatever the async extra step of request 32 leaves that request 33's prefill forward consumes
without going through a KV page: kernel-internal scratch (the lane already has
`patches/vllm-xpu-kernels-qwen38-gdn-scratch-zero-init-20260818.patch` for a GDN scratch defect), the draft
head's buffers, or per-slot runner bookkeeping that feeds the forward's metadata. R181 (probe image, async off)
gives the no-phantom control for a layer-0 input/output comparison before any further fix image.
