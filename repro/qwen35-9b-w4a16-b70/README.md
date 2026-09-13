# Reproduce Qwen3.5 9B W4A16 with its own MTP head on one B70

> **Certification: `candidate-portable-repro`, not a starter guide.** Model
> revision, container image, launch chain and validation identities are pinned
> and were verified on the lab host on 2026-09-07. The remaining gates are a
> tested Intel driver/Docker installation path, beginner recovery guidance, and
> an independent clean-host replay. See the
> [guide catalog](../guide-catalog.json) and
> [certification standard](../../docs/reproduction-guide-certification.md).

RedHatAI's W4A16 quantization of Alibaba's Qwen3.5-9B (compressed-tensors INT4
weights, FP16 activations), served as published by vLLM XPU on one Intel Arc
Pro B70 through the lab's R276 image, with the publisher's MTP head as a
lossless speculative draft and full decode-only XPU graph capture. It is the
same stack, launcher and workload as the
[FP8 route](../qwen35-9b-fp8-b70/README.md) for the same model, so the two are
directly comparable.

## Headline (campaign w1, 2026-09-07, one B70)

- **MTP depth 3 with the draft-only INT4 lm_head: `113.627 / 112.904 tok/s`**
  class-balanced median decode over tokens 1-100 after TTFT on the strict
  12-prompt six-class completions suite, 512-token cap, cache zero, two fresh
  servers with separate empty compile caches. Median TTFT `68 ms`.
- **No speculation: `64.332 / 64.338 tok/s`** on the same suite.
- **Lossless:** G1 12/12 (the two MTP0 servers), G2 12/12 (the two depth-3
  servers), G3 12/12 twice (each depth-3 server against the MTP0 oracle);
  canaries passed on every server.
- LocalMaxxing: `cmtrhoyl1000cps01o43bhl72`, `113.265 tok/s`.
- ML Bottleneck's tuned-run target for `qwen3.5_9b` INT4 on one B70 is
  `99.12 tok/s`, physical ceiling `153.05`; the headline is 1.14x the target
  and 74% of the ceiling.

## Why this route also serves many users losslessly

vLLM's compressed-tensors path selects `CompressedTensorsWNA16`, which on XPU
is the lab's `wNa16` kernel (`_xpu_C.int4_gemm_w4a16`) carrying the fixed-K
two-tier W4A16 strategy built for the Qwen3.8 INT4 lane. That kernel does not
change its reduction order with the number of decode rows. The consequence is
visible in the identity ladders: without speculation this route is byte-exact
against a single request at **every rung through 64 users, in both passes**,
where the FP8 route on the same model, weights of the same publisher and the
same launcher flips a near-tie token from 16 users up.

| users | W4A16 tok/s (exact) | FP8 tok/s (exact) |
| ---: | ---: | ---: |
| 1 | 64.2 (1/1) | 50.1 (1/1) |
| 2 | 124.0 (2/2) | 97.2 (2/2) |
| 4 | 236.2 (4/4) | 187.5 (4/4) |
| 8 | 437.7 (8/8) | 355.0 (8/8) |
| 16 | 746.7 (16/16) | 634.7 (15/16) |
| 32 | 1184.0 (32/32) | 1055.2 (31/32) |
| 64 | **1268.4 (64/64)** | 1253.8 (59/64) |

No speculation, 128-token completions on the small-context suite, warm pass of
two, `max-model-len 256`, `max-num-seqs 64`. What separates the two columns is
the kernel, not the model or the workload: same model, same publisher, same
launcher, different matmul.

One qualification, measured on 2026-09-08. The GEMM is row-count invariant by
construction, but it is not the only reduction on this path: the RMSNorm this
route runs is *not* row-count invariant, and gives about 2-3% of rows a
last-bit difference once the batch reaches 16
(`experiments/qwen35-9b-b70/notes/2026-09-08-the-rmsnorm-is-also-row-count-dependent.md`).
So the right reading of the left-hand column is that this route is exact in the
regimes measured, not that its kernel makes it exact everywhere. A last-bit
perturbation only changes a token when it lands on a near-tie, which is why the
ladder loses the occasional request at high concurrency rather than diverging.

### Speculative depth (campaigns d4, d5, d6)

Depth 3 was originally taken from the FP8 route's sweep. Swept here it holds, and the identity
column is the interesting one:

| depth | W4A16 tok/s | W4A16 vs MTP0 oracle | FP8 tok/s | FP8 vs MTP0 oracle |
| ---: | ---: | --- | ---: | --- |
| 3 | **113.63 / 112.90** | 12/12 | 98.25 / 98.03 | 12/12 |
| 4 | 108.45 / 108.24 | **12/12** | 98.42 / 98.55 | 8/12 |
| 5 | 104.91 / 104.85 | **12/12** | 91.30 / 91.29 | 8/12 |
| 6 | 99.27 / 99.32 | **12/12** | 88.60 / 88.68 | 8/12 |

Every depth is lossless on this route; on FP8 only depth 3 was. A verify step at depth `d` processes
`d+1` rows, so depth varies the GEMM's row count without varying the number of concurrent users.
That makes this an independent test of the same kernel property the concurrency ladders measure, and
it says FP8's loss of identity above depth 3 was never a property of speculative decoding - it was
the row-count dependence its GEMM has and this one does not.

### Past 64 users (campaign x1)

64 was the top of the ladder, not a measured ceiling, so campaign x1 ran the
same ladder to 128 users with graph capture sizes raised to match (an
uncaptured decode shape falls back to eager, which is a different execution
path and would have confounded the answer).

| users | no speculation tok/s (exact, pass 1 / pass 2) |
| ---: | --- |
| 64 | 1272.7 / 1272.0 (64/64, 64/64) |
| 96 | 1308.5 / 1308.3 (96/96, **95/96**) |
| 128 | 1323.7 / 1322.3 (128/128, 128/128) |

The ceiling is not clean. One request out of 448 across the two top rungs
diverged, at 96 users in the second pass, while 128 users matched twice. So
64 remains the highest concurrency qualified in both passes, and 96 and 128 are
reported as near-exact rather than folded into the claim. Aggregate decode has
almost stopped scaling by then: the last doubling of users buys about 4%.

The W4A16 determinism pad (`VLLM_XPU_W4A16_DETERMINISM_PAD`) is off in the
published configuration and should stay off. Measured on this model (campaign
w2): without speculation it is inert, because 64 users is 64 decode rows and
the pad only engages above 128, and the route is already exact there. With
depth 3 the verify step submits up to 256 rows, the pad engages, costs 13% at
64 users (683.7 against 789.2 tok/s) and changes nothing about identity
(62/64 against 61/64). The residual speculative flips above 16 users are
therefore not GEMM row-tier effects.

With MTP depth 3 the same ladder is exact through 16 users in both passes
(`750.8 tok/s`), 32/32 in the warm pass at `827.3` and 31/32 cold, and 61/64 at
`789.2`: the speculative verify step still walks through row counts the fixed-K
tiers do not cover.

## Model

Pinned in `manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json`:
`RedHatAI/Qwen3.5-9B-quantized.w4a16` at revision
`a398088c4228b0ae0c8c78df88fd1e4bf445f068`, three LFS files
(`model.safetensors` 10,952,xxx,xxx B, `model_mtp.safetensors` 486,582,848 B,
`tokenizer.json`) plus the small config files, 11.46 GB total. Download it the
same way as the FP8 route and keep the filenames; the launcher verifies every
LFS file against the manifest before the container starts.

## Launch

```bash
cd /path/to/b70-optimization-lab
MODEL_DIR=/models/Qwen3.5-9B-quantized.w4a16 VLLM_CACHE_DIR=/tmp/qwen35-w4a16-cache \
  repro/qwen35-9b-w4a16-b70/scripts/run-qwen35-9b-w4a16-server.sh
```

Every variable of the [FP8 launcher](../qwen35-9b-fp8-b70/README.md#launch)
applies unchanged: `MTP_DEPTH` (default 3), `TENSOR_PARALLEL_SIZE`,
`XPU_GRAPH`, `DRAFT_HEAD_INT4`, `PORT`, and the server-shape variables. The
image, kernel digests and determinism environment are identical, so the two
routes differ only in the weights on disk.

## Validate

Identical to the FP8 recipe: the strict suite with canaries, a depth-0 server
for the oracle, `compare-strict-attempt-outputs.py` for the 12/12 gate, and
`bench-openai-concurrency-oracle.py` for the identity ladder. See
[that section](../qwen35-9b-fp8-b70/README.md#validate) for the exact commands;
substitute this launcher and `qwen35-9b-w4a16-mtp3` as the served model name.

## Two cards (campaign w3, TP2)

Same launcher with `TENSOR_PARALLEL_SIZE=2`.

| measurement | one card | two cards |
| --- | ---: | ---: |
| no speculation, one user | 64.33 / 64.34 | 97.59 / 97.54 |
| MTP depth 3, one user | 113.63 / 112.90 | **172.27 / 172.32** |
| no speculation, exact ladder ceiling | 64 users, 1268.4 tok/s | 32 users, 1836.9 tok/s |
| depth 3, exact ladder ceiling | 16 users, 750.8 tok/s | 16 users, 1174.6 tok/s |

All strict gates pass 12/12 on both card counts. LocalMaxxing `cmtrn9hoy001ops01qzd4axry` at `172.296 tok/s`.

One difference is worth stating plainly: on one card this kernel is byte-exact at every rung through 64 users, and on
two cards 64 users drops to 63/64 in both passes while 32 users stays perfect. The kernel removes the variation that
comes from the number of decode rows; it cannot remove the variation that comes from summing partial results across two
cards. If byte-identical output at the largest batch matters more than aggregate throughput, one card is the safer
shape.

## Long context: 2K to 32K real content (campaign w4, one B70)

One slot, unrepeated real content (technical prose, Python, structured documents; three requests per depth, median
shown), 128 output tokens, cache zero, canaries before and after; the depth-3 arm ran against a same-configuration
MTP0 arm as its oracle.

| active context | no speculation tok/s | depth 3 + INT4 draft head tok/s (exact vs oracle) |
| ---: | ---: | ---: |
| 2,048 | 64.0 | 116.7 (3/3) |
| 4,096 | 63.0 | 145.7 (3/3) |
| 8,192 | 62.0 | 118.7 (3/3) |
| 16,384 | 60.1 | 153.5 (3/3) |
| 24,576 | 58.4 | 134.5 (3/3) |
| 32,768 | 56.9 | 89.5 (3/3) |

All 18 depth-3 answers matched the oracle. The FP8 route of the same model runs 49.6 to 45.5 without speculation and
105.9 to 86.8 with it, so INT4 leads at every depth and by the widest margin at short context.

## Many users, faster, still exact: the class-consistent FP16 linear (R293, 2026-09-11)

Every static-server table above ran the vocabulary projection (248320 x 4096, 2 GB in fp16) and the per-layer
unquantized projections in `<=32`-row pieces, an R224-era device for keeping the oneDNN f16 GEMM in its single-row
rounding class. Each piece re-reads the weight, which is why the depth-3 column was flat from 16 users (747, 827, 787
tok/s at c16/c32/c64). **R293** keeps the same opaque op but, with `CLASSPAD=1`, measures the GEMM's row-count
classes per weight shape on first use, verifies them, and pads or splits every call into one canonical class: one
weight read per step, rows bit-identical between one user and sixty-four. Found and characterised on the 4B lane
([`experiments/qwen35-4b-b70/notes/2026-09-11-r293-class-consistent-fp16-linear-on-the-server.md`](../../experiments/qwen35-4b-b70/notes/2026-09-11-r293-class-consistent-fp16-linear-on-the-server.md));
measured here by campaigns `s1`-`s7`
([`experiments/qwen35-9b-b70/notes/2026-09-11-r293-on-the-9b.md`](../../experiments/qwen35-9b-b70/notes/2026-09-11-r293-on-the-9b.md),
data `experiments/qwen35-9b-b70/data/2026-09-11-qwen35-9b-r293-classpad.json`). The image is R276 plus four
pure-Python overlays; with `CLASSPAD=0`, the default, it runs the R276 code path unchanged.

| | `CLASSPAD=0` (R276 path, above) | `CLASSPAD=1` (R293) |
| --- | ---: | ---: |
| strict gates G1/G2/G3, one card and two | 12/12 | **12/12** |
| one card, depth 3 / MTP0, one user (strict) | 113.6 / 64.3 | 112.4 / 61.7 |
| two cards, depth 3 / MTP0, one user (strict) | 172.3 / 97.6 | 164.7 / 93.6 |
| one card, no speculation, c32 / c64 / c128 | 1184 / 1268 / 1324 | 1209 / **1644 / 1955**, c64 and c128 exact |
| one card, depth 3, c16 / c32 / c64 | 747 / 827 / 787 | **942 / 1228 / 1225** |
| two cards, no speculation, c32 / c64 / c128 | 1845 / 2093 / - | 1856 / **2614 / 3227**, c128 512/512 |
| two cards, depth 3, c16 / c32 / c64 | 1175 / 1356 / 1465 | **1419 / 1857 / 2165** |
| two cards, no speculation, c64, 5 ms admission stagger, tie-site suite, twenty passes | 1257/1280 unstaggered | **1280/1280 at 2557**, harness-certified |

Identity is R224's at every rung within the four-pass resolution: no speculation exact to 24 users and at 64 on one
card (127/128 at 32), to 32 on two (255/256 at 64); depth 3 exact through 16 on one card. The staggered-admission
recipe from the 4B lane (`bench-openai-concurrency-oracle.py --launch-stagger-ms 5`: request *i* released 5*i* ms after
a barrier, so the batch composition every request sees is the same on every pass) had never been run on this model;
it is byte-exact here too. Single user costs 1-4%, less than on the 4B, because this model's per-layer projections are
a smaller share of its step.

**Serving recommendation for the static servers.** `CLASSPAD=0` for the published single-user headline;
`CLASSPAD=1` for more than about eight users, depth 3 to about 32 users on one card, no speculation above, the
admission stagger where byte-exact output matters. The scheduled-draft server in the next section is a separate route
built on the R276 digest and has not been combined with R293.

## The draft head only needs a shortlist (R294, 2026-09-12): 124.03 / 124.13

The MTP head drafts three tokens per step, each an argmax over the full 248,320-row vocabulary projection; the 9B
lane measured that projection at 28% of the step even as a draft-only INT4 copy. The draft only proposes. The target
verifies every proposed token with its own full FP16 head, so a draft head that scores only a **shortlist** of rows
cannot change any output: a true argmax outside the list is simply rejected. R294 builds the draft-only INT4 copy from
the shortlisted rows. With the 67,248-row list (the lab's own text united with system documentation and the image's
Python sources; 27% of the vocabulary, 99.5% of this model's suite output), the single-user headline is
**124.03 / 124.13 tok/s** against 113.48 / 113.49 for the same image scoring every row, every gate 12/12, acceptance within noise of
the control. The 32k list reads the same 124.0 / 124.1 with lower acceptance; the 92k list 122.2 / 122.2 with the control's acceptance. Curve, lists and builders:
[`experiments/qwen35-4b-b70/notes/2026-09-12-the-draft-head-only-needs-a-shortlist.md`](../../experiments/qwen35-4b-b70/notes/2026-09-12-the-draft-head-only-needs-a-shortlist.md).

The launcher enables it by default (`DRAFT_SHORTLIST`, empty string to score every row); the served image is R294b
(R293 plus the shortlisted head, lists under `/opt/draft-shortlists/`). A deployment with its own traffic can
rebuild the list with `experiments/qwen38-27b-b70/docker/draft-shortlists/build-shortlist-v2.py`; a list that misses
tokens costs acceptance, never correctness. LocalMaxxing `cmtyqbel70aqcps01zrvj4kjp` at `124.084 tok/s` (approved 2026-09-12).

## One server for every batch size (campaigns cudynm1 / cudynm1r, 2026-09-11)

Speculation on this route is a latency lever, not a throughput lever: depth 3 is
worth +72% at one user and costs a third of aggregate throughput at 64, and it is
the only setting that is *not* exact at 32 and 64 users. vLLM in R276 carries
`num_speculative_tokens_per_batch_size`, a per-batch-size draft schedule, so one
server can hold both ends - but running it well needs three pure-Python overlays
on R276, all in [`docker/`](docker/), each a COPY-only Dockerfile on the previous:

- `r276-dynamic-mamba-alloc`: the scheduler reserves GDN/Mamba state for the
  largest draft depth still possible for the batch instead of the static
  maximum (the 27B lane's August patch, applied to R276 without fuzz). Without
  it the no-draft rungs run 6-18% under the no-speculation server.
- `r276-dynsd-fullgraph`: keeps `FULL_DECODE_ONLY` and captures one full decode
  graph per query length the schedule can produce (the dispatcher keys differ
  in request count, so a graph for 8x4 tokens is never replayed for 16x2). vLLM's
  own fallback rewrites the mode to PIECEWISE, which on this lane means either
  no graphs at all (`splitting_ops: []`, 77.6 tok/s at one user) or, with the
  default splitting ops, a 4K-context near-tie site where the 1-row oracle and
  the 4-row verify pick different tokens - 4 of 4 piecewise runs, 0 of 5
  full-graph runs. Static configurations are unchanged by construction.
- `r276-dynsd-catchup`: on a pure-decode step that schedules no drafts, vLLM
  still runs the draft layer's forward so its KV stays current for when the
  batch shrinks - 5-6% of every step at 32-128 users. The overlay skips that
  forward, keeps the skipped positions' target hidden states and next tokens in
  a per-request ring (256 positions), and replays them through the draft layer
  as a prefill-shaped catch-up the next time that request is asked for drafts.
  Steps with prefill tokens are never skipped. Drafts are proposals and the
  target verifies every token, so nothing this changes can reach the output.

Schedule `[[1,8,3],[9,16,1],[17,64,0]]`: depth 3 through 8 concurrent users,
depth 1 through 16, no speculation above. Two runs on one boot, each its own
strict pair, its own MTP0 oracle pair, and its own c1-c64 identity ladders:

| users | scheduled server (cudynm1 / cudynm1r, warm pass) | exact | before catch-up (fgdynm1) | static depth 3 | no speculation |
| ---: | ---: | --- | ---: | ---: | ---: |
| 1 | **110.7 / 110.6** (strict pairs 110.69/110.60, 110.65/110.60) | 12/12 x 2 | 110.7 | 110.7 | 64.2 |
| 8 | **623 / 622** | 8/8 | 623 | ~596 | 432 |
| 16 | 851 / 850 | 16/16 | 852 / 883 | ~667 | 725 |
| 32 | **1113 / 1109** | 32/32 in all four passes | 1090 | ~878 | 1148 |
| 64 | **1184 / 1183** | 63/64 + 64/64; 64/64 + 64/64 | 1150 | ~909 | 1206 |

- **Identity claim, two-run rule:** the deepest rung exact in both passes of
  both runs is **32 users**; aggregate rates are published through that rung.
  At 64 the scheduled server is in the same near-exact band as the
  no-speculation server itself (this route's RMSNorm qualification above), where
  static depth-3 speculation loses 2-3 requests in 64.
- **Context:** the 2K-32K real-content ladder on the scheduled server is
  **18/18 exact** against its own MTP0 oracle, with the same decode figures as
  the static run in the section above (111.4 / 139.0 / 113.9 / 147.8 / 128.9 /
  86.7 tok/s at 2K...32K).
- **What it costs.** At 32-64 users the scheduled server is 2-3% under plain
  no-speculation (it was 5% before the catch-up overlay): the draft layer still
  runs on the mixed prefill steps while a rung fills, so every prompt's draft
  KV is written, and each request pays one catch-up pass when the batch shrinks
  past a threshold. The cold first pass a fresh server runs reads low whatever
  the rung (459 at 16 users, 916-953 at 32); quote warm passes.
- **Past 64 users:** the schedule carries "no drafts" forward above its last
  range; at 128 users the full-graph server without catch-up measured 1197
  against the no-speculation server's 1254 (both 127/128 exact).
- Result files: `experiments/qwen35-9b-b70/data/qwen35-9b-w4a16-tp1-mtp3-dynamic-catchup-20260911-cudynm1-strict-result.json`
  and `...-cudynm1r-strict-result.json` (the full-graph-only runs are
  `...-dynamic-fullgraph-20260910-fgdynm1[r]-strict-result.json`); every ladder
  in `experiments/qwen35-9b-b70/data/2026-09-10-qwen35-9b-w4a16-dynamic-schedule-ladders.json`;
  campaign note
  `experiments/qwen35-9b-b70/notes/2026-09-10-one-server-for-every-batch-size.md`.

Build the overlays once (COPY-only Dockerfiles, seconds each, base = the public
R276 digest) and launch:

```bash
cd /path/to/b70-optimization-lab
docker build -f repro/qwen35-9b-w4a16-b70/docker/r276-dynamic-mamba-alloc.Dockerfile \
  -t neural-download/vllm-openai-xpu:qwen38-int4-r276-dynamic-mamba-alloc repro/qwen35-9b-w4a16-b70/docker
docker build -f repro/qwen35-9b-w4a16-b70/docker/r276-dynsd-fullgraph.Dockerfile \
  -t neural-download/vllm-openai-xpu:qwen38-int4-r276-dynsd-fullgraph repro/qwen35-9b-w4a16-b70/docker
docker build -f repro/qwen35-9b-w4a16-b70/docker/r276-dynsd-catchup.Dockerfile \
  -t neural-download/vllm-openai-xpu:qwen38-int4-r276-dynsd-catchup repro/qwen35-9b-w4a16-b70/docker
MODEL_DIR=/models/Qwen3.5-9B-quantized.w4a16 VLLM_CACHE_DIR=/tmp/qwen35-w4a16-dyn-cache \
  repro/qwen35-9b-w4a16-b70/scripts/run-qwen35-9b-w4a16-dynamic-server.sh
```

**Combined with R293 (2026-09-11 evening, this host).** The same three overlays build unchanged on the R293 image
(`docker/r293-*.Dockerfile`; nothing overlaps) and the launcher's content pins accept the result. Run against the
R276 build on the same host the same evening, both as full runs with four-pass ladders: gates 12/12 on both; one user
113.5 -> 112.4; 16 users 943 -> 960, exact on both; 32 users 1153 -> 1192; **64 users 1243 -> 1631**, within 0.6%
of the no-speculation R293 server, so the schedule's handover to no drafts no longer costs anything. Identity at 32
and 64 users is the same or better on R293 (120/128 and 255/256 against 115/128 and 249/256). Note that on this host
the R276 scheduled server read 115/128 at 32 users where the four-card host recorded 32/32 in four passes, so the
two-run-rule rung here is 16 users on either image; recorded as a host difference in
`experiments/qwen35-9b-b70/notes/2026-09-11-r293-on-the-9b.md`. Launch the combination with
`IMAGE=neural-download/vllm-openai-xpu:qwen38-int4-r293-dynsd-catchup CLASSPAD=1` in front of the dynamic launcher
after building the `r293-*` Dockerfiles.

A locally built overlay's image ID is not portable, so the launcher pins the
overlay by content: it verifies the SHA-256 of all six overlaid files inside
the image before starting, and the shared launcher's image contract still
verifies the R276 kernels and pinned files underneath. `SPEC_SCHEDULE` and
`MTP_DEPTH` (the schedule's largest depth) change the policy; `MAX_NUM_SEQS`
defaults to 64 to cover it; `IMAGE=neural-download/vllm-openai-xpu:qwen38-int4-r276-dynsd-fullgraph`
runs the configuration without the catch-up overlay. Validate exactly as above,
plus the identity ladder with `--require-output-identity` at every rung you
intend to serve.

## Rebased onto stock vLLM XPU v0.29.0, with three upstream fixes (R304, 2026-09-13): 123.22 / 123.86

The served image is now `neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304` (sha256:7cd7bb16): the same
overlay stack on the public v0.29.0 image (vllm-xpu-kernels 0.1.14.1, which also carries upstream GDN fix #544) with
the kernel library rebuilt from public sources, plus three open upstream vLLM fixes applied verbatim: PR #53059
(uniform-decode alias guard), PR #51565 (GDN first-chunk classification) and PR #53542 (active runtime-K width).

Why it matters beyond the version bump: on the previous image every **one-token prompt** and, at depth K, every
**(1+K)-token prompt** came back as a single-character wall (`!!!!...`) on 30 of 30 greedy runs. R304 returns 0 of 30
on every prompt length tested (1 to 6 tokens and long), with and without speculation.

Strict pair on R304 under the recipe contract: G1/G2/G3 12/12, depth 3 **123.22 / 123.86 tok/s**, no speculation 64.3
(the previous image measured 124.03 / 124.13). The 2K-32K exact-depth ladder is 18/18 on both arms; the no-speculation
64-user recipe with the 5 ms admission stagger is 64/64 on seven passes at about 2100 tok/s; a dynamic draft schedule
with a K=1 range runs without the kernel width assertion that killed stock v0.29.0. The launcher pins
`VLLM_USE_V2_MODEL_RUNNER=0`: v0.29.0 defaults XPU to the V2 model runner, whose speculator has no draft INT4 head
(128 instead of 172 tok/s in the single-user harness). Build and provenance:
`experiments/qwen38-27b-b70/docker/rebase-v0290/` and `experiments/qwen38-27b-b70/notes/2026-09-12-rebase-onto-vllm-v0290.md`.

## The scheduled-draft server on the rebase (R306, 2026-09-13): 120.98 / 121.14 one user, c16 992 exact

The three scheduled-draft overlays apply to the v0.29.0 rebase (R305) with one fix on top: upstream PR #53542 stages
the GDN state indices as a column slice of its maximum-width buffer, which is not contiguous for a scheduled K below
the maximum, and the XPU kernel rejects it at graph capture; R306 keeps one contiguous staging buffer per active
width. Image `neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r306-dynsd`
(`ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:f124c6fb`), now the dynamic launcher's default; launch with
`CLASSPAD=1` as measured. Under the recipe contract: G1/G2/G3 12/12, one user **120.98 / 121.14 tok/s** (dyn293:
112.4, the shortlist is now active in this profile), 16 users 992 tok/s exact on all four passes (960), 32 users 1190
(28-31/32), 64 users 1631 (62-64/64; no speculation 1641). Data:
`experiments/qwen35-9b-b70/data/2026-09-13-qwen35-9b-dynsd-r306.json`.

## Known limits

- Depth 3 is confirmed on this route's own evidence (campaigns d4/d5/d6),
  not inherited: throughput falls monotonically with depth and no depth above 3
  is faster. See the depth table below.
- Graph-off and 2K-32K context rows exist for the FP8 route only.
- Two-card concurrency identity without an admission stagger is weaker than one-card: exact through 32
  users, and about one request lost at 64 (with the 5 ms stagger, 1280/1280 over twenty passes under R293). That last figure is intermittent -
  six control passes across three campaigns read four at 63/64 and two at
  64/64 - so treat it as a rate, not a fixed score, and do not compare
  interventions against it with two passes
  (`experiments/qwen35-9b-b70/notes/2026-09-08-the-two-card-c64-identity-metric-is-intermittent.md`).
- Not yet clean-host tested.
