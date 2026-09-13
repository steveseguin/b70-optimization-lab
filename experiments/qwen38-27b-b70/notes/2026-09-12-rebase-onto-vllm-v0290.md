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
| 27B INT4 TP2 depth 4 | pending | | | | | 117.46 / 117.59; 49.4 |

4B 2K-32K exact-depth ladder on the candidate: **18/18 on both arms** (no-spec oracle, then depth 3 vs it), the same
as the served recipe, so #544 changes nothing this model can see at 32K with 64 accepted-token blocks.

Pending on the same image, queued: the 27B strict pair (both cards) and the concurrency-identity recipe (no-spec c64 with the 5 ms stagger on CLASSPAD=1;
served: 1280/1280 at 2104 tok/s).

## Status

Candidate `neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r301` (sha256:5640a86b). Not published, not under
the recipe contract yet (`verify-image-contract.sh` gained `SKIP_IMAGE_CONTRACT=1`, loud, for candidates); the contract
profile needs the new file digests and kernel head `6d92b1bf`. Serving recipes need the V2-runner pin. The 62 MB kernel
libraries are outside git (sha256 in `kernel-artifacts.sha256`; `build-kernels-0.1.14.1-clean-clone.sh` rebuilds them).
