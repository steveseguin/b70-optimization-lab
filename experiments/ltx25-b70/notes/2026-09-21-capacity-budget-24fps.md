# The 24 fps capacity budget: every stage is the problem (2026-09-21)

## Measured stage demands per clip (f87 endure receipts, run dir 87)

| Stage | Worker(s) | Card(s) | Demand (s/clip) | Evidence |
| --- | --- | --- | --- | --- |
| sample | 2 | xpu:0 + xpu:1 | 2.52 card-s; interval 1.63 | emitted_phases, campaign wall |
| decode (incl. MP4 save) | **1** | xpu:3 | **1.60 median job** | pipeline-decode receipts, n=81 |
| encode | 1 | xpu:2 + xpu:3 | ~0.85 (design estimate) | shard design; receipts contaminated by pipeline waits |

24 fps = every stage ≤ **1.042 s/clip** sustained.

## First-order findings

1. **Decode is co-limiting today.** One decode worker at 1.60 s/clip against
   the sampler's 1.63 interval. ANY sampler gain below 1.6 makes decode the
   binding stage. The job includes the lossy MP4 preview write
   (pipeline_decode_node.decode_clip -> save_preview_guarded).
2. **The sampler's packing loss is ~0.7 s/pair** (packet 90 note). Perfect
   packing on the current split bounds the sampler at ~1.33 s/clip - still
   above 1.042. Kernel-time reduction is unavoidable, not optional.
3. **Total GPU work inequality.** sampler 2.52 + decode ~1.2 + encode ~0.85
   ≈ 4.5 GPU-s/clip over 4 cards averages 1.13 > 1.042. Reaching 24 fps
   needs BOTH spreading AND cutting ~0.6-0.9 s/clip of work. Cut list, all
   proven-or-spec'd lossless: adaLN fusion 0.05 (packet 89, built), glue
   capture 0.09, oracle capture 0.05, and the 0.84 s/clip non-GEMM pool
   (norms/small kernels; fusion sweep + attention backends).

## Decode levers (packet 91 candidates, after 89/90)

a. **Second decode worker, VAE replica on xpu:2.** VAE state is small
   (CausalDiffusionVAE 1.37 GiB + AudioVAE 0.34) and xpu:2 has ~11 GiB
   headroom (21.45 of 32.6 reserved, f87 receipt). Capacity -> 0.8 s/clip.
   Lossless in construction (each clip decoded once, by an identical twin).
   **Gating question: cross-card VAE bitwise equality** - the exactness
   harness compares against references decoded on xpu:3; a clip decoded on
   xpu:2 must be byte-identical. One probe run answers it (GPU-gated).
b. **Move the MP4 save off the decode worker** (async writer thread). The
   preview is diagnostic-only; the exactness gate never reads it. Host-side
   change, zero numerics risk. Share of the 1.60 s unknown - measure first
   (one timer split in decode_clip, rides packet 90's instrumentation).
c. Decode kernel work (the old decoder-axis candidates) - only if (a)+(b)
   insufficient.

## Structural option: 4-way sampler block shard

Whole-block placement is exactness-safe (the 2-way shard proves placement
changes nothing; the column-parallel "4-way 9/20 exact" verdict applies to
INTRA-layer splits, not block placement). 12/12/12/12 would put 0.63 s/clip
of sampler on each card. Blocked today: xpu:3 already carries decode (1.60)
+ encode share, xpu:2 carries encode. Viable only after decode moves
(b above, or replica absorbs it). Uneven splits are a preparer flag.
Keep as packet 92 contingency; do NOT build before 90's measurement lands.

## Sequence (unchanged, now with the decode gate explicit)

1. Reboot -> packet 89 campaign (fusion proof + endure profile).
2. Packet 90: busy windows -> packing attribution -> targeted fix.
3. Packet 91: decode capacity (probe cross-card VAE equality; save-offload
   measurement rides 90's build).
4. Then the work-cut list and, if needed, the 4-way shard.
