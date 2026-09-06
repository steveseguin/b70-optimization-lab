# R220 / R221: a batch-invariant oneDNN W4A16 GEMM for the INT4 lane (2026-09-05)

Directive: the INT4 lane must be lossless for concurrent users on TP1 and TP2 at MTP depths 0-3.
R216/R217 had shown the plain-GPTQ kernel (`_xpu_C.int4_gemm_w4a16`, oneDNN matmul) is repeat-exact and lossless for one
request but computes rows in about five different reduction orders depending on the batch row count, so a request
batched with others gets different FP16 bits and near-tie tokens flip (c64 59/64).

## Mechanism

The FP8 lane solved the same problem in R136-R139 with a oneDNN generator patch (`gen_kernel.cpp`) that pins one
fixed-K strategy string for the exact W8A16 problem. R220 ports that hook to the W4A16 problem family
(`Ta_ext` u4/s4, `Tb_ext` f16) with two plain-environment controls: `QWEN38_GEMM_DUMP=1` prints the selected catalog
entry and derived parameters for every W4A16 problem, and `QWEN38_W4A16_GEMM_STRATEGY="<unrollM> <unrollN> <strategy>"`
pins one strategy for every W4A16 problem with n <= `QWEN38_W4A16_GEMM_MAXN` (1024). Patch
`patches/onednn-qwen38-w4a16-strategy-override-dump-r220-20260905.patch`; build `docker/build-w4a16-strategy-r220-image.sh`
(the R139 flow: vllm-xpu-kernels 1e90ffa6 + r35 + r50, oneDNN 0e2a5bfe + r137a + r137b + r220, sycl-tla cd763790,
built inside the R213b base with oneAPI 2026.1); image r220 36360702, `_xpu_C` 64c4422a.

## What the catalog does (R220 dump, `data/2026-09-05-qwen38-int4-w4a16-natural-strategy-dump-r220-result.json`)

For every INT4 shape the catalog splits K eight ways (`wg 2x1x8`, `wgK=8`) for 1-8 token rows, two ways up to 128 rows
(`wg 4x2x2` / `8x1x2` / `2x2x2`), and not at all above 128 (`wg 4x2`, `8x4`, `wgK=1`), with several tile changes in
between. That is the row-class map: the reduction tree changes with n.

## Screen (`scripts/bench-qwen38-int4-w4a16-strategy-screen.py`, `data/qwen38-int4-w4a16-strategy-screen-r220/`)

All 14 INT4 GEMM shapes of the model at TP1 and TP2, random u4 weights, n = 1..1024 (27 sizes), per candidate one
process: run-to-run identity, row-0 class count across n, prefix exactness, permutation invariance at 200 rows,
zero-padding 168 -> 200, timings.

| candidate | strategy | invariant (14 shapes) | bitwise equal to A | decode (M=1..8) | prefill (M=1024) |
|---|---|---|---|---|---|
| natural | catalog | no (4-8 classes each) | - | reference | reference |
| A | `16 8 at32 am128 aB wg 2x1x8 ikr xaf st vav hi pt sr br sb128 bk0 bm0 nmk sys` (the natural 1-8 entry) | yes | - | = natural | 3-3.5x slower |
| D | natural 9-24 entry (`wg 4x2x2`) | yes | no | +10% big shapes, 2x small shapes | ~2x |
| C | natural 64-128 entry (`wg 2x2x2`) | yes | no | 2-3x slower | ~2x |
| **E** | `16 16 at64+m128@96 am32+m32@160 aB wg 4x2x8 ikr xaf st vav bo pt sr br sb64 bk0 sm sn bm0 sys` (D's tile, A's 8-way K) | yes | **yes, 14/14 shapes, every n** | +10-20% | ~2x |
| E1 | E with unroll 16x32 | yes | yes | slower than E | ~E |
| E2/G | unroll 32 variants | yes | no | pathological (100x) | pathological |
| F | C's tile with `wg 2x2x8` | yes | no | - | - |

Bitwise equality between A and E at every n means the 8-way K partition with the same A-tile/K-loop defines the
reduction order, independent of the M/N tiling. So the two-tier rule "A for n <= 8, E above" is fully batch-invariant at
zero decode cost. E costs about 2x on prefill GEMMs and up to +20% for 32-128-row batches; wider E tiles did not help.

## R221 (final)

`patches/onednn-qwen38-w4a16-fixed-k-two-tier-r221-20260905.patch`: the two-tier rule is the default for every
W4A16 problem with n <= 1024; `QWEN38_W4A16_FIXED_K=0` restores the catalog, `QWEN38_W4A16_GEMM_STRATEGY[_SMALL|_LARGE]`
override, dump retained. Built incrementally in the R220 build root (`docker/rebuild-w4a16-incremental-r221.sh`);
image `neural-download/vllm-openai-xpu:qwen38-int4-w4a16-fixed-k-r221` id 699e2699, `_xpu_C` 271db0d4. Validation
(`r221-default.json`, no environment): all 14 shapes invariant, bitwise equal to A, decode timings equal to the
natural kernel (down_proj 80.7 vs 79.3 us at M=5), prefill about 2x (down_proj 2640 vs 1345 us at M=1024).

The R213b Python determinism pad is unnecessary on this kernel (every n is run-to-run identical) and is switched off
in the R222 wrappers (`VLLM_XPU_W4A16_DETERMINISM_PAD=0`), removing its ~4% dispatch cost.

## Next

R222 matrix on a fresh boot: TP2 then TP1; depth-1 full campaign (G1 MTP0 pair, G2/G3, G5, c1-c64 identity ladders
for MTP1 and MTP0), depths 2 and 3 strict pairs against that oracle plus ladders. Bar: exact at every concurrency for
every depth; the FP8 lane's residual (MTP1+ misses at c32/c64 "not in any censused kernel") may or may not apply here.

## Clean-clone replay (2026-09-06)

`experiments/qwen38-27b-b70/scripts/replay-20260906-w4a16-r220-r221-clean-clone.sh` re-ran the two published build
scripts from fresh blobless clones of the pinned commits (vllm-xpu-kernels 1e90ffa6, oneDNN 0e2a5bfe, sycl-tla cd763790;
the GitHub URLs were redirected with `git url.<mirror>.insteadOf` to local bare mirrors because the WAN was crawling at
~0.5 MB/s, and each script's own `checkout --detach <sha>` still enforced commit identity). Host oneAPI 2026.1 mounted into
the R213b base as before, JOBS=4 (JOBS=8 exhausted the 15 GiB host).

| stage | wall | `_xpu_C` sha256 | image id | identical to shipped |
| --- | --- | --- | --- | --- |
| R220 | 930 s | 64c4422a… | 36360702… | yes (both) |
| R221 incremental | ~1 min | 271db0d4… | 699e2699… | yes (both) |

Two script defects surfaced and were fixed in place: the R220 script's hash pin on the builder helper had gone stale after the
morning's public-closure edit of that helper (defaults only), and the R221 script's `strings | grep -Fq` check aborted under
`set -o pipefail` when `grep -q` closed the pipe early (the last two steps, image build and import smoke, were run by hand
with identical arguments and reproduced the image id; the check now uses `grep -c`). Evidence:
`experiments/qwen38-27b-b70/data/replay-w4a16-r220-r221-clean-clone-20260906T192527Z/` (summary JSON, both stage logs).
