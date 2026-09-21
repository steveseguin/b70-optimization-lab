# The 24 fps capacity budget: every stage is the problem (2026-09-21)

## Measured stage demands per clip (f87 endure receipts, run dir 87)

| Stage | Worker(s) | Card(s) | Demand (s/clip) | Evidence |
| --- | --- | --- | --- | --- |
| sample | 2 | xpu:0 + xpu:1 | 2.52 card-s; interval 1.63 | emitted_phases, campaign wall |
| encode | **1** | xpu:2 + xpu:3 | **1.70 (3.40/pair), contention-inflated** | f84 receipts (graph-capture-84 note); f87 median 3.15/pair |
| decode (incl. MP4 save) | **1** | xpu:3 | **1.60 median job** | pipeline-decode receipts, n=81 |

The 1.70 figure is measured WHILE decode co-runs on xpu:3 (the 84 note
attributes the f83c->f84 encode swing to device contention); the shard
design's isolated estimate is ~0.85 s/clip. xpu:3 is the overloaded card:
it carries the decode AND half the encode. Packet 91's decode replica
relieves the encode cap at the same time.

24 fps = every stage ≤ **1.042 s/clip** sustained. All THREE stages sit at
1.6-1.7 today - the pipeline is deliberately balanced, and every stage is
individually over budget. Encode at 1.70 is in fact the hardest cap: the
endure only sustains 1.63 because encode runs ahead of a finite prompt
list (backlog grows ~0.07 s/clip, invisible at 120 prompts, fatal
sustained).

## First-order findings

1. **Every stage is over budget; encode is the hardest cap.** All three
   stages sit at 1.6-1.7 s/clip (deliberate pipeline balancing). Encode at
   1.70 s/clip with one worker caps sustained throughput at 14.7 fps no
   matter what the sampler does; decode at 1.60 binds below that. The
   decode job includes the lossy MP4 preview write
   (pipeline_decode_node.decode_clip -> save_preview_guarded).
2. **The sampler's packing loss is ~0.7 s/pair** (packet 90 note). Perfect
   packing on the current split bounds the sampler at ~1.33 s/clip - still
   above 1.042. Kernel-time reduction is unavoidable, not optional.
3. **Total GPU work inequality.** sampler 2.52 + encode 1.70 + decode ~1.2
   ≈ 5.4 GPU-s/clip over 4 cards averages 1.35 > 1.042. Reaching 24 fps
   needs BOTH spreading AND cutting ~1.0-1.4 s/clip of work. Cut list, all
   proven-or-spec'd lossless: adaLN fusion 0.05 (packet 89, built), glue
   capture 0.09, oracle capture 0.05, and the 0.84 s/clip non-GEMM pool
   (norms/small kernels; fusion sweep + attention backends). The encoder
   (a 14.3 GiB GEMM stack, already graph-captured) needs its own kernel
   pass or a second co-running worker.

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
of sampler on each card. Blocked twice over: xpu:3 carries decode (1.60)
+ encode share, xpu:2 carries encode share - 1.70 s/clip of encode across
the two cards. Viable only if encode AND decode both shrink or move.
Keep as a contingency; do NOT build before 90's measurement lands.

## Encode levers (packet 92 candidates)

a. **Second encode worker co-running on xpu:2/xpu:3** (the sampler's own
   proven pattern: two clips' encodes in flight on the same two cards).
   Capacity 1.70 -> ~1.0-1.2 at the observed co-run efficiency. The
   encoder is already sharded+graphed; a second worker needs its own
   static buffers (memory: xpu:2 at 21.6, xpu:3 at 16.6 of 32.6 - fits).
   Cross-thread determinism already proven by the sampler's pool keying.
b. Encoder kernel pass (same fusion/backends toolbox as the sampler's
   non-GEMM pool) - measure its phase profile first; the encoder's load
   path is the crash-prone one, so iterate carefully.

## Sequence (with the encode cap explicit)

1. Reboot -> packet 89 campaign (fusion proof + endure profile).
2. Packet 90: busy windows -> packing attribution -> targeted fix.
3. Packet 91: decode capacity (probe cross-card VAE equality; save-offload
   measurement rides 90's build).
4. Packet 92: encode capacity (second worker, then kernel pass).
5. Then the sampler work-cut list and, if needed, the 4-way shard.
