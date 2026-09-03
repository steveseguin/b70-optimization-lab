# A92 preregistration: per-row QSA index update and selection for verifier rows

Date: 2026-09-03, 13:24 EDT
Status: frozen before launch; diagnostic gated on the MTP0 line's hashes

## Why

After A85 (exact recurrent path) the MTP1 residual appears only where the
context exceeds the 2048-token QSA index budget (the 2K fixture from token
12, the 4K fixture throughout). Offline, the Triton block-FP8 MoE and the
dense GEMMs are M-invariant, and the QSA attention kernel is per row with
the same split count for one or two rows. What is not row-exact is the
index side path: in a two-row step, `_compress_qsa_groups_kernel` pools
each row's own group correctly, but `qsa_store_cache_rows` writes both
rows' pooled keys, and two rows in the same compression group (three
steps in four with ratio 4) target the same compressed slot, so the stored
key and the first row's selection can differ from what sequential decode
produces. Selection only matters above the budget, which is exactly where
MTP1 still diverges.

## Design

Overlay commit `2ebbf2a6` adds `VLLM_XPU_QSA_SERIAL_SPEC_INDEXER`
(registered in `envs.py`): for a 2-8-row batch from a single request with
selection active, the indexer compresses, stores and selects one row at a
time, with the request's sequence length rolled back per row, exactly as
each row's own decode step would. Prefill chunks (64 rows) and the draft's
shared-index steps are untouched. A92 is the A85 packet (exact recurrent
path, capture sizes [1, 2], NVMe copy, 12 GB floor) at attempt 92 / port
19764 on that head with the flag exported; same battery and pins as A81/A85.
`tools/rewrite-q38-a85-to-a92-serial-indexer.py`.

A91, the logprob probe of the A85 identity, did not serve: the A85 packet
pins the overlay head A85 ran on and the overlay has since moved, so its
pre-check stopped (`FAIL: vLLM overlay head changed`, no GPU time). It is
superseded by A92's battery; if A92 still diverges, the probe runs on the
A92 identity.

## Reading

- Exact-2K `afffd211...` and exact-4K `c6193cc6...` with the other pins
  unchanged: MTP1 is lossless on this line; the "reached" marker confirms
  the path ran; short and depth rates are the result, and the frozen
  MTP1 client plus a size-2 receipt verifier make it a record pair.
- 2K still `29a2947a...`: the store race was not (all of) it; the probe
  on this identity locates the first differing logit.
- Server error or a changed short/quality output: the per-row path is
  wrong somewhere (the rolled-back sequence length is the first suspect).
