# Review: GDN spec-decode scratch zero-init (vllm-xpu-kernels 0ab8205)

Date: 2026-08-18
Reviewer: second-host agent (read-only review; no build on this 15 GiB host)
Scope: `fix/gdn-scratch-zero-init` @ `0ab8205756b52082399ae1849c0cfb6915f63f04`,
single file `csrc/xpu/gdn_attn/gdn_attn_interface.cpp`.

## What the patch does

All twelve persistent buffers from `get_gdn_spec_decode_scratch` switch from
`torch::empty` to `torch::zeros`/`zeros_like`. Intentional initialisers are
untouched: `has_initial_state = torch::ones`, `exact_query_start_loc =
torch::arange(2)`. No other `torch::empty` remains in that function.
Allocation happens once per shape behind the cache, so the memset is off the
hot path. The claim in the commit message holds for the code as written.

## Verdict

Correct as far as it goes; adopt only after a full strict re-validation. Three
caveats the commit does not state:

1. **The record lane still has the same hazard class.** The approved
   101.922 tok/s MTP5 submission runs with
   `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=0`, i.e. the *non-persistent* branch,
   which still allocates per call with `torch::empty` (verified at lines
   ~1015+ of the patched file). Per-call allocation happened to be
   deterministic across the three record arms — plausibly because the caching
   allocator recycles the same blocks in the same order, or because fresh USM
   segments arrive zero-filled. Either way, the submitted number and the
   fixed-persistent path are *different code paths*; the fix is not a
   like-for-like speedup of the record lane, and adopting it is a new
   measurement, not a re-confirmation.

2. **The actual read-before-write site is still unidentified.** The diagnosis
   proves history dependence (divergence moved 88/30/30 between pairs;
   single-prompt reruns identical), and zeroing removes cross-call residue.
   But if any of the twelve buffers is logically *needed* at five verifier
   rows without being written first, zeros are deterministically wrong rather
   than correct. The quality-vs-own-baseline gate on the fixed build is what
   distinguishes "deterministic and right" from "deterministic and wrong";
   the record lane's 25/25 + quality pass does not transfer.

3. **`exact_query_start_loc = torch::arange(2)`** is sized 2 regardless of
   `num_spec_decodes`. This is pre-existing and untouched, and the call sites
   step one token at a time (`seq_len=1` per step), so [0,1] is the correct
   cu_seqlens for every step. Flagging only because a fixed-size arange next
   to shape-derived buffers reads like a latent bug; it is not one at the
   current call convention.

## Build constraint

Do not build this branch on the 15 GiB second host: the GDN translation unit
peaked at ~14.2 GiB RSS in the BMG-G31 AOT build, which is what froze this
desktop twice on 2026-08-18 during vLLM weight-load staging. Build and
measure on the measuring host (which also needs the disk-space plan noted in
97bb161a5: 4.7 GB free vs 2.3 GB previous build output).

## Adoption gate for the fixed build

1. Full strict 25-prompt suite, three cold arms, pinned compile cache.
2. 25/25 token-ID determinism across all pairs, including a server-restart
   replay.
3. Quality pass against the model's own Qwen3.8 baseline (not Qwen3.6).
4. Performance comparison against 101.922 with scratch disabled; only
   supersede the LocalMaxxing row if the fixed build is strictly better and
   passes 1-3.
