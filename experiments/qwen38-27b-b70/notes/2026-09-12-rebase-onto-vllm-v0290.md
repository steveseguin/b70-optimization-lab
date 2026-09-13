# Rebase onto vLLM XPU v0.29.0 (R301, 2026-09-12 evening)

The lab's served runtime (R294b) is a stack on `vllm/vllm-openai-xpu` nightly 0.27.2rc1.dev77 with kernels 1e90ffa6.
Stock v0.29.0 (09-09, kernels 0.1.14.1) works on this host and carries kernel fix #544 (GDN speculative conv-state
layout at cache-block boundaries: long MTP generations collapsing into loops), which our pinned kernels predate. This
note records moving the whole stack onto v0.29.0 and proving it lossless and as fast. Artifacts:
`docker/rebase-v0290/` (port diffs, ported files, Dockerfiles, kernel build scripts and log), data
`data/2026-09-12-rebase-v0290-r301-results.json` and `../qwen35-4b-b70/data/2026-09-12-stock-v0290-single-card-baselines.json`.

## What the served image actually is

Inventory from the R294b image itself (its `/workspace/vllm` is a git checkout of the base commit, so `git diff` there
plus a site-packages vs source-tree comparison is the complete overlay list; a marker grep is not, it missed three files):

| layer | content |
| --- | --- |
| base source diff (4 files, 289 lines) | draft-only INT4 lm_head (`vocab_parallel_embedding.py`, `llm_base_proposer.py`), packed-serial-exact Gemma RMSNorm (`layernorm.py`), FA serial spec switches (`flash_attn.py`) |
| site-packages overlays (8 files, ~500 lines) | `_xpu_ops.py` (R156 split-mixed, R228 spec grouping, R276 sync-free), `layers/utils.py` (R224 row-chunk + R290..R293 class-pad), `vocab_parallel_embedding.py` (R294 shortlist), `llm_base_proposer.py` (R256 fallback), `mixed_precision/xpu.py` (R213b pad op), `scaled_mm/xpu.py`, `xpu_communicator.py`, `mamba/gdn/qwen_gdn_linear_attn.py` (state buffers + 7-argument GDN op call) |
| `_xpu_C.abi3.so` | vllm-xpu-kernels 1e90ffa6 + r35 (width, serial-exact paths) + r50 (split serial gates); oneDNN 0e2a5bfe + r137a + r137b + r221 (r221 *replaces* r220; the incremental script reverts r220 first) |

The served configuration keeps every GDN serial-exact gate at 0 (`VLLM_XPU_GDN_NATIVE_SPEC_*_SERIAL_EXACT=0`), so r35
and r50 are dead weight in production; the width contract they addressed is the vLLM side's job (PR #53542, see the
upstream review packet). Upstream kernels 0.1.14.1 pin the *same* oneDNN commit, so the three GEMM patches apply
unchanged. `git apply` refuses r221 on top of r220; GNU `patch` silently rejects it too. Apply r137a, r137b, r221.

## Port

Net diffs (base -> served) were regenerated from the image and applied to v0.29.0: seven of ten files took them with
offsets only; `qwen_gdn_linear_attn.py` needed one hunk by hand (state-buffer registration moved). Kernels: 0.1.14.1
(6d92b1bf; eight commits past 1e90ffa6, one of them #544) built unpatched with the patched oneDNN inside the public
v0.29.0 image's venv (torch 2.13.0+xpu, libsycl.so.9; host oneAPI 2026.1), 13 minutes, by the lab's own builder.
`Dockerfile.r301-v0290-rebase` assembles the candidate from the public digest + ported files + shortlists + the two
libraries; its content hash equals the stage-B1 image the measurements below ran on.

**The trap that cost the first three arms:** v0.29.0 defaults XPU to the V2 model runner ("Using V2 Model Runner").
Its speculator loads the draft with the full FP16 head and never enters the V1 proposer where the INT4 draft head and
the shortlist live. Symptom: everything boots, gates would pass, single user 128 tok/s instead of 172. The serving
recipe must pin `VLLM_USE_V2_MODEL_RUNNER=0` on this image.

## Measured (one card, served configuration, same harness for every row: c1 x2, 128 tokens, small-context suite)

| image | 4B depth 3, one user |
| ---: | ---: |
| stock v0.29.0 (no overlays, no env) | 112, 114 (no spec: 94, 96) |
| stage A2 = v0.29.0 + ported Python, stock kernels, V2 runner | 122, 129 |
| stage B1 = A2 + rebuilt kernels, V2 runner | 128, 128 |
| stage B1, `VLLM_USE_V2_MODEL_RUNNER=0` | **172.1, 172.5** |
| served R294b (0.27.2rc1.dev77) | 170.9, 172.3 |

Stock 9B: 84 (depth 3), 65 (no spec).

Strict pairs on the candidate (the lab's lossless gates; G1 MTP0 a/b, G2 depth-3 a/b, G3 depth-3 vs MTP0):

| lane | G1 | G2 | G3 | depth 3 tok/s | MTP0 tok/s | served R294b |
| --- | --- | --- | --- | ---: | ---: | --- |
| 4B W4A16 | 12/12 | 12/12 | 12/12 + 12/12 | 191.33 / 191.94 | 102.57 / 102.39 | 191.87 / 191.58; 102.6 |
| 9B W4A16 | 12/12 | 12/12 | 12/12 + 12/12 | 124.13 / 124.14 | 64.33 / 64.28 | 124.03 / 124.13; 64.3 |
| 27B INT4 TP2 depth 4 | 12/12 | 12/12 | 12/12 + 12/12 | 117.12 / 117.08 | 50.01 / 50.07 | 117.46 / 117.59; 49.4 |

4B 2K-32K exact-depth ladder on the candidate: **18/18 on both arms** (no-spec oracle, then depth 3 vs it), the same
as the served recipe, so #544 changes nothing this model can see at 32K with 64 accepted-token blocks.

Concurrency-identity recipe on the candidate (4B, one card, CLASSPAD=1): no-spec c64 with the 5 ms stagger **64/64 on
all seven passes** at 2086-2113 tok/s (served R293: 1280/1280 at 2104); depth 3 c64 42-47/64 at ~1840 (served 1831, the
known non-exact regime); no-spec c128 128/128 and 127/128 at 2175 with the engine's ladder defaults.

## R302: the alias guard from the fork review

bosd's PR #47 (merged today) reproduces vLLM #53051 on demand: a fresh prompt of exactly 1+K tokens aliases the
uniform-decode shape, enters the decode graph with stale GDN state indices and degenerates. The upstream guard (PR
#53059) is still open, so neither v0.29.0 nor our lineage has it. R302 = R301 + those two hunks
(`Dockerfile.r302-alias-guard`); the guarded served image `rebase/vllm-xpu:r294b-alias-guard` exists for comparison. The
four-arm test with bosd's harness on the 4B (depth 3) found something else first.

## R303: a one-token prompt breaks the served recipe

bosd's harness sends 30 greedy completions per prompt length. On R294b (served), R301 and R302 alike, the one-token
prompt `Hi` came back as a `!!!!!!` wall on 29 of 30 runs; two tokens and longer were clean. That is not the alias shape
(4 tokens at depth 3, which did not degenerate here once the harness could construct one) but vLLM #51562: a fresh
one-token GDN prefill is classified as a decode step and touches recurrent state it never initialised. The lab's
morning review had confirmed that defect from source and supported upstream PR #51565; it is still open. R303 = R302 +
that PR's `gdn_attn.py` hunks (`Dockerfile.r303-gdn-phase-fix`): `Hi` 0/30, every other length 0/30.

| arm | k=1 `Hi` | k=2 | k=3 | k=4 (alias) | k=5 | k=6 | long |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| R294b served | 30/30 | 0 | 0 | **30/30** | 0 | 0 | 0 |
| R301 / R302 (guard) | 29-30/30 | 0 | 0 | 0 (R302) | 0 | 0 | 0 |
| **R303** | **0/30** | 0 | 0 | 0 | 0 | 0 | 0 |

Round two on the served image also lit the alias: the 4-token prompt `Hello, world!` degenerated 30/30 on R294b (depth 3,
so 1+K = 4), which R302's guard removes. Without speculation the one-token failure is still there on R302 (29/30) and
gone on R303 (0/30), so it does not need MTP. **The published recipe therefore breaks on every one-token prompt and,
at depth K, on every (1+K)-token prompt.** R303 is the shipping candidate; the contract digest set pins its
`gdn_attn.py` too (seventeen files).

The recipe contract now carries a v0.29.0 digest set (sixteen files, keyed on the kernel-head label 6d92b1bf) so R302
launches without `SKIP_IMAGE_CONTRACT`; R301 fails it on `gpu_model_runner.py` by design. The shared launchers pin
`VLLM_USE_V2_MODEL_RUNNER=0` (a no-op on the 0.27.2 lineage).

## Status

Candidate `neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r301` (sha256:5640a86b). Not published, not under
the recipe contract yet (`verify-image-contract.sh` gained `SKIP_IMAGE_CONTRACT=1`, loud, for candidates); the contract
profile needs the new file digests and kernel head `6d92b1bf`. Serving recipes need the V2-runner pin. The 62 MB kernel
libraries are outside git (sha256 in `kernel-artifacts.sha256`; `build-kernels-0.1.14.1-clean-clone.sh` rebuilds them).

## R304 and the fourth lane

R304 = R303 + the `gdn_attn.py` hunks of PR #53542 (active runtime-K width), so a dynamic draft schedule with a K
below the maximum no longer hits the kernel width assertion (9B, schedule 3/1/0: 12 users run, 64 users complete).
Strict pairs under the real contract on R304: 4B 12/12 at 191.37/191.41 (MTP0 102.4), 9B 12/12 at 123.22/123.86
(MTP0 64.3); short prompts 0/30 on every length. The **FP8 27B lane** (R187 profile: whole-graph piecewise compile,
block W8A16, GDN split-mixed, depth 1) needs only oneDNN r137a/r137b from the kernel library, which R304 carries, so it
runs on the same image: G1/G2/G3 12/12, MTP1 54.82/54.83 tok/s, MTP0 33.08/33.08 (published 54.935 / 33.097).
INT4-27B TP2 depth 4 on R304 under the real contract: G1/G2/G3 12/12, 117.04/117.09 tok/s, MTP0 50.11/50.03
(published R299 117.46/117.59, 49.39). One image now serves all four published lanes; it is on GHCR as
`ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16` (tag `r304-v0290-rebase-20260913`).

## 27B ladders on R304 (warm second pass of two, R304c, vs R299 on the 0.27.2 image)

Strict pair R304c: 117.24 / 116.95 depth 4, 50.07 / 50.06 no spec; all gates 12/12.

| users | R304 depth 4 | R299 depth 4 | R304 no spec | R299 no spec |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 113.7 (1/1) | 111.4 (1/1) | 50.2 (1/1) | 50.2 (1/1) |
| 2 | 192.1 (2/2) | 191.3 (2/2) | 95.4 (2/2) | 96.0 (2/2) |
| 4 | 307.9 (3/4) | 304.9 (4/4) | 180.1 (4/4) | 180.1 (4/4) |
| 8 | 435.9 (8/8) | 429.8 (8/8) | 329.8 (8/8) | 330.1 (8/8) |
| 16 | 590.8 (16/16) | 589.0 (16/16) | 539.7 (16/16) | 540.2 (16/16) |
| 32 | 645.4 (31/32) | 650.4 (31/32) | 816.3 (32/32) | 815.0 (32/32) |
| 64 | 596.8 (57/64) | 597.4 (62/64) | 989.3 (64/64) | 987.3 (64/64) |

## Two-card profiles on R304 (TP2, 2026-09-13)

| lane | G1/G2/G3 | depth 3 strict | no spec strict | previous TP2 record |
| --- | --- | ---: | ---: | --- |
| 4B W4A16 | 12/12 | 247.45 / 244.21 | 138.30 / 138.06 | 240.9 (R276-class, no shortlist) |
| 9B W4A16 | 12/12 | 177.24 / 177.32 | 97.53 / 97.53 | 164.7 / 93.6 (R293, no shortlist) |

The c128 rungs in that chain ran with the engine's ladder defaults (max 64 sequences, 512 batched tokens), so they
are not the published c128 configuration (128 sequences, 1024 tokens, capture sizes to 128); a rerun with the
published settings is queued and will replace them here.

## R305/R306: the 9B scheduled-draft profile on the rebase

The 9B "scheduled draft" profile stacks three more overlays (dynamic Mamba allocation, one full decode graph per
scheduled K, draft-state catch-up). Their recorded diffs apply to v0.29.0 with offsets (R305). Strict pairs passed
(12/12, 120.9/121.1 one user), then the c64 ladder server died at graph capture: `spec_state_indices_tensor must be
contiguous`. PR #53542 stages the state indices as a column slice of the `[max_bs, num_spec+1]` buffer, which is not
contiguous when the active width is below the maximum, and the XPU kernel rejects it; the non-graph path never sees
it. R306 gives the builder one contiguous staging buffer per active width, allocated at init. Under the real contract
(a 21-file digest set keyed on the build-lane label): gates 12/12, one user **120.98 / 121.14** (dyn293 on the old
image: 112.4; the shortlist is now active in this profile), c16 992 exact on all four passes (960), c32 1190 (28-31/32),
c64 1631 (62-64/64), no-spec c64 1641: the same concurrency profile, a faster single user. Data:
`experiments/qwen35-9b-b70/data/2026-09-13-qwen35-9b-dynsd-r306.json`.
