# R178: zeroing "new" GDN state pages did not remove the depth-2 phantom, because the hook never saw a GDN page

Date: 2026-09-03 17:42-17:48 EDT, fresh boot 88f0984f (reboot 13:16, preflight clean, postflight clean).
Image: `neural-download/vllm-openai-xpu:qwen38-fp8-mtp2-zero-mamba-pages-r178` (`sha256:40d3645a...`), R156 +
`patches/vllm-qwen38-xpu-zero-mamba-state-pages-r178-20260903.patch`. Prereg:
`data/2026-09-03-qwen38-fp8-r156-mtp2-zero-mamba-pages-r178-prereg.json`.
Results: `/mnt/fast-ai/bench-results/qwen38-fp8-r156-mtp2-zero-mamba-pages-20260903-r178/query-mtp1/`.

## Result

The 64-prompt sequential pass at depth 2 with async scheduling on reproduced the phantom exactly as R165/R167:
row 32 (`cache-c032`, the 33rd request) starts with token 60 (`[60, 271, 3833]`), and it is the only row that
differs from the MTP0 oracle (63/64). The server log confirms the patch was live
(`R178 zeroing Mamba/GDN state pages for 48 layers on new blocks`, both TP ranks).

Prereg decision branch taken: "phantom persists". But the reason is not that the stale content is elsewhere.

## Why R178 could not test its hypothesis

Read from the R178 image (CPU, no device use):

- `vllm/v1/core/single_type_kv_cache_manager.py` line 87: `_record_new_block_ids = needs_kv_cache_zeroing and
  isinstance(kv_cache_spec, AttentionSpec)`. `MambaManager` inherits this, so it never records the block ids it
  allocates. `KVCacheManager.take_new_block_ids()` therefore only ever returns attention page ids.
- `scheduler._get_new_block_ids_to_zero()` forwards that list as `new_block_ids_to_zero`; the R178 worker hook
  `_zero_mamba_pages(block_ids)` was called with attention page ids only. Because the raw KV tensors are shared
  across groups (`kv_cache_tensor.shared_by`; one block id is one page in every layer view), those pages were
  already zeroed by `KVBlockZeroer`, and the page actually assigned to the new request's GDN state was never in the
  list.
- Prefix caching is off on this lane (`enable_prefix_caching: False`), so the Mamba manager runs in its default
  `none` cache mode and delegates allocation to the base class path, which is exactly the path gated by that flag.

So R178 zeroed the wrong pages and the hypothesis (recycled unzeroed GDN state page after a discarded async step)
remains untested by a fix. The R176 probe (kernel-input state sums at prefill of the 33rd request) is the direct
test and runs next; R180 is the corrected fix candidate.

## R180

`docker/Dockerfile.mtp2-zero-mamba-pages-r180` = R178 image + `docker/r180-record-mamba-new-blocks.py`
(`patches/vllm-qwen38-xpu-record-mamba-new-blocks-r180-20260903.patch`): `MambaManager` records new block ids
(`isinstance(kv_cache_spec, (AttentionSpec, MambaSpec))`, plus the align-mode allocation site). Built 17:5x as
`sha256:d3437273...`; contract files unchanged from R156. Prereg
`data/2026-09-03-qwen38-fp8-r156-mtp2-zero-mamba-pages-r180-prereg.json`; runner
`scripts/run-20260903-qwen38-fp8-r180-after-r176.sh` (queued behind the R176 rerun).

## Also on this chain

The first post-reboot R176 attempt aborted at 17:42 on `IMAGE CONTRACT FAIL` for `_xpu_ops.py`: the chain passed
the R156 hash, but the probe image carries its own patched `_xpu_ops.py` (`4a996f86...`, the R176 logging block
only, verified by diff). Fixed in the chain script; rerun queued as
`scripts/run-20260903-qwen38-fp8-r176-rerun-after-chain.sh`.
