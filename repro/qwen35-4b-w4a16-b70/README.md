# Reproduce Qwen3.5 4B W4A16 with its own MTP head on one or two B70s

> **Certification: `candidate-portable-repro`, not a starter guide.** Model
> revision, container image, launch chain and validation identities are pinned
> and were verified on the lab host on 2026-09-07. The remaining gates are a
> tested Intel driver/Docker installation path, beginner recovery guidance, and
> an independent clean-host replay. See the
> [guide catalog](../guide-catalog.json) and
> [certification standard](../../docs/reproduction-guide-certification.md).

RedHatAI's W4A16 quantization of Alibaba's Qwen3.5-4B (compressed-tensors INT4
weights, FP16 activations), served as published by vLLM XPU on one Intel Arc
Pro B70 through the lab's R293 image (R276 plus the class-consistent FP16 linear, off by default), with the publisher's MTP head as a
lossless speculative draft and full decode-only XPU graph capture. It is the
same stack and launcher as the
[9B W4A16 route](../qwen35-9b-w4a16-b70/README.md); only the weights differ.

## Headline (campaign v1, 2026-09-07, one B70)

- **MTP depth 3 with the draft-only INT4 lm_head: `177.406 / 177.168 tok/s`**
  class-balanced median decode over tokens 1-100 after TTFT on the strict
  12-prompt six-class completions suite, 512-token cap, cache zero, two fresh
  servers with separate empty compile caches. Median TTFT `45 ms`.
- **No speculation: `102.625 / 102.376 tok/s`** on the same suite.
- **Lossless:** G1, G2 and both G3 comparisons matched 12/12 complete token
  arrays; canaries passed on every server.
- LocalMaxxing: `cmtrj2tp3000hps01n3fadg9d`, `177.287 tok/s`.

## Two cards (campaign t1, TP2)

A 4B model is small enough that the second card could plausibly cost more in collective traffic than it returns. It
does not: the second card is worth more to this model than to the 9B.

| measurement | one card | two cards |
| --- | ---: | ---: |
| no speculation | 102.63 / 102.38 | **138.17 / 138.06** |
| MTP depth 3, one user | 177.41 / 177.17 | **240.62 / 227.53** |
| 32 users, no speculation | 1593.9 (32/32) | **2342.9 / 2353.9 (32/32)** |
| 64 users, no speculation | 1725.1 (63/64) | **2752.6 / 2777.7 (62/64, 64/64)** |

All strict gates pass 12/12 on both card counts, and the two-card depth-3 servers returned byte-identical answers on
all 12 prompts. LocalMaxxing `cmtrycz0y002pps011142ifrk` at `236.916 tok/s`, which is the mean of all four two-card
depth-3 servers measured (`240.615`, `227.533`, `240.158`, `239.359`) rather than the better campaign's own pair
(`239.758`): campaign t2 was run because t1's pair was too widely spread to submit, so quoting t2 alone would be
selecting between campaigns.

Two caveats belong with those numbers. The two-card depth-3 pair measured `240.615` and `227.533 tok/s`, a `5.8%`
spread, where the one-card pair of the same lane differed by `0.13%`; two-card speculative decode is markedly noisier
here, so its center is quoted with that spread rather than as a tight figure. And concurrency identity is weaker on
two cards: without speculation the route is exact through 32 users in both passes but scores 62/64 then 64/64 at 64
users, and with depth 3 it is exact only through 16. The 9B on this same kernel is exact at every rung through 64
users on one card and drops to 63/64 on two, so on both models the loss appears when the second card joins. That
points at the cross-card reduction rather than the GEMM.

## Speculative depth (campaigns e4, e5, e6)

Depth 3 was taken from the FP8 route's sweep, not chosen here. Swept on this route it holds, and the
identity column is again the interesting one:

| depth | tok/s | vs MTP0 oracle |
| ---: | ---: | --- |
| 3 | **177.41 / 177.17** | 12/12 |
| 4 | 177.69 / 177.45 | 12/12 |
| 5 | 167.12 / 167.00 | 12/12 |
| 6 | 160.74 / 160.48 | 12/12 |

Depth 4 is within `0.16%` of depth 3, which is inside this lane's noise, so the two are tied rather
than depth 4 being an improvement; 5 and 6 fall away. A cheaper target does not make deeper drafts
pay here - the 4B curve is flat to depth 4 and then drops, where the 9B fell immediately - so no
speed was found and depth 3 stays the operating point, now on this route's own evidence.

Every depth is lossless, matching the 9B. Since depth `d` makes the verify step process `d+1` rows,
this varies the GEMM's row count without varying the number of concurrent users, and on FP8 the same
sweep lost a third of the suite from depth 4 up. That is a fifth independent confirmation that what
FP8 loses is the row-count dependence, not something about speculative decoding.

## Why this route and not the FP8 one

The FP8-dynamic build of the same model **cannot pass the base identity gate on
this stack**. Three independent fresh-server pairs scored 11/12, 9/12 and 11/12:
three of the twelve prompts are tie-prone, each with exactly two valid
continuations, and servers pick between them independently
(`../../experiments/qwen35-4b-b70/notes/2026-09-07-qwen35-4b-fp8-not-repeat-exact.md`).

On this route the same gate passes **12/12**. The difference is the kernel:
vLLM's compressed-tensors path selects `CompressedTensorsWNA16`, which on XPU is
the lab's `wNa16` kernel (`_xpu_C.int4_gemm_w4a16`) with the fixed-K two-tier
strategy, and that kernel does not vary its reduction order. The 9B shows the
same effect in its own way: there the FP8 route is repeat-exact but flips at
concurrency, and the W4A16 route is byte-exact at every rung through 64 users.
Two models, two different symptoms, one cause and one fix.

## Model

Pinned in `manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json`:
`RedHatAI/Qwen3.5-4B-quantized.w4a16` at revision
`7a613872f394578b0b52b683ff4ac47516b4bcaf`, 5.54 GB across three LFS files
including the `model_mtp.safetensors` draft head. The launcher verifies every
LFS file against the manifest before the container starts.

## Launch

```bash
cd /path/to/b70-optimization-lab
MODEL_DIR=/models/Qwen3.5-4B-quantized.w4a16 VLLM_CACHE_DIR=/tmp/qwen35-4b-cache \
  repro/qwen35-4b-w4a16-b70/scripts/run-qwen35-4b-w4a16-server.sh
```

Every variable of the [shared launcher](../qwen35-9b-fp8-b70/README.md#launch)
applies unchanged: `MTP_DEPTH` (default 3), `TENSOR_PARALLEL_SIZE`, `XPU_GRAPH`,
`DRAFT_HEAD_INT4`, `PORT` and the server-shape variables. This wrapper adds
`CLASSPAD` (default `0`; see the R293 section below) and pins the R293 image
(`ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:78bd728d...`), which
with `CLASSPAD=0` is the R276 code path the tables were measured on.

## Validate

Identical to the 9B recipes: the strict suite with canaries, a depth-0 server
for the oracle, `compare-strict-attempt-outputs.py` for the 12/12 gate, and
`bench-openai-concurrency-oracle.py` for the identity ladder. Substitute this
launcher and `qwen35-4b-w4a16-mtp3` as the served model name.

## Many users (campaign v1, one B70, warm pass of two)

| users | no speculation tok/s (exact) | depth 3 + INT4 draft head tok/s (exact) |
| ---: | ---: | ---: |
| 1 | 101.9 (1/1) | 159.2 (1/1) |
| 2 | 193.5 (2/2) | 300.8 (2/2) |
| 4 | 362.3 (4/4) | 537.8 (4/4) |
| 8 | 655.5 (8/8) | 898.0 (8/8) |
| 16 | 1059.3 (16/16) | 1089.9 (16/16) |
| 32 | 1593.9 (32/32) | 1147.4 (30/32) |
| 64 | 1725.1 (63/64) | 1201.0 (55/64) |

128-token completions on the small-context suite, `max-model-len 256`,
`max-num-seqs 64`. Without speculation every rung through 32 users is exact in
both passes; depth 3 is exact through 16 and is the faster choice up to that
point, after which plain decoding wins.

## Long context: 2K to 32K real content (campaign v2)

One slot, unrepeated real content (three requests per depth, median shown), 128 output tokens, cache zero, canaries
before and after; the depth-3 arm ran against a same-configuration MTP0 arm as its oracle.

| active context | no speculation tok/s | depth 3 + INT4 draft head tok/s (exact vs oracle) |
| ---: | ---: | ---: |
| 2,048 | 99.6 | 177.0 (3/3) |
| 4,096 | 98.1 | 188.3 (3/3) |
| 8,192 | 95.7 | 188.8 (3/3) |
| 16,384 | 91.6 | 191.6 (3/3) |
| 24,576 | 87.8 | 161.5 (3/3) |
| 32,768 | 84.4 | 149.9 (3/3) |

All 18 depth-3 answers matched the oracle. This model holds its speed at length better than the 9B, which falls to
89.5 tok/s at 32K against this one's 149.9.

## Many users, faster, still exact: the class-consistent FP16 linear (R293, 2026-09-11)

Every table above was measured with the vocabulary projection (248320 x 2560, 1.2 GB in fp16) and the per-layer
unquantized projections running in `<=32`-row pieces, an R224-era device for keeping the oneDNN f16 GEMM in its
single-row rounding class. Each piece re-reads the weight, so above 32 rows the server paid a tax that grew with the
batch: 41-54% of depth-3 throughput from c32 up, 25-30% of no-speculation throughput above c32, and the reason
"speculation stops paying at 16 users" looked like a property of the model. **R293** keeps the same opaque op but,
with `CLASSPAD=1`, measures the GEMM's row-count classes for each weight shape on first use (rows 1-32, 33-128,
129-320, 321-512 at these shapes, each position-invariant, pad-invariant and deterministic), verifies them, and pads or
splits every call into one canonical class. One weight read per step; rows bit-identical between one user and
sixty-four. Mechanism, census and the R290-R293 history:
[`experiments/qwen35-4b-b70/notes/2026-09-09-the-fp16-linear-chunk-is-a-throughput-tax.md`](../../experiments/qwen35-4b-b70/notes/2026-09-09-the-fp16-linear-chunk-is-a-throughput-tax.md),
[`2026-09-11-r293-class-consistent-fp16-linear-on-the-server.md`](../../experiments/qwen35-4b-b70/notes/2026-09-11-r293-class-consistent-fp16-linear-on-the-server.md);
data `experiments/qwen35-4b-b70/data/2026-09-11-qwen35-4b-r290-classpad-on-the-server.json` (chains 15-16, arms
`r1`-`r10`). The image is R276 plus four pure-Python overlays (`experiments/qwen38-27b-b70/docker/r290..r293-*.py`);
with `CLASSPAD=0`, the default, it runs the R276 code path unchanged and reproduces every number above.

| | `CLASSPAD=0` (R276 path, above) | `CLASSPAD=1` (R293) |
| --- | ---: | ---: |
| strict gates G1/G2/G3, one card and two | 12/12 | **12/12** |
| one card, depth 3 / MTP0, one user (strict) | 177.4 / 102.6 | 168.0 / 96.5 |
| two cards, depth 3 / MTP0, one user (strict) | 240.9 / 138.1 | 225.9 / 127.8 |
| one card, no speculation, c16 / c32 / c64 | 1059 / 1594 / 1725 | 1052 / 1625 / 2164 |
| one card, no speculation, c96 / c128 (`max-num-seqs 128`) | 1779 / 1811 | **2400 / 2520**, both exact |
| one card, depth 3, c16 / c32 / c64 | 1090 / 1147 / 1201 | **1353 / 1608 / 1831** |
| two cards, no speculation, c64 / c128 | 2778 / 3104 | **3317 / 4015**, c128 512/512 |
| two cards, depth 3, c64 | 2021 | **2694** |
| one card, no speculation, c64, 5 ms admission stagger, tie-site suite, twenty passes | 1280/1280 at 1702 | **1280/1280 at 2104**, harness-certified |
| two cards, same | 1280/1280 at 2711 | **1280/1280 at 3164**, harness-certified |

Identity is the same at every rung as with the pieces: no speculation near-exact to 64 users (one card 255/256, two
cards 255/256), depth 3 exact through 16 on one card. On two cards one prompt, `cache-c000`, sits on an exact tie at
token 39 under the R293 arithmetic and diverges once per pass from 2 users up; every other prompt behaves as before.
Depth 2 (`r8`) leads depth 3 above 16 users under R293 (1767 at c32, 2031 at c64) and depth 4 trails it.

**The admission stagger.** `bench-openai-concurrency-oracle.py --launch-stagger-ms 5` releases request *i* 5*i* ms
after a barrier. A batch of constant composition is deterministic on this stack; what flips a tie is the composition
*changing* underneath a request, and a deterministic arrival order makes that change identical on every pass. Without
speculation the result equals the sequential oracle byte for byte at 64 users, on one card and two, for 1% of
throughput. Any client that admits requests in a fixed order gets the same property; it is a serving discipline, not
a kernel change (`experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-staggered-admission-is-exact.json`).

**Serving recommendation.** One image, two modes, both lossless by the gates: `CLASSPAD=0` for the published
single-user headline; `CLASSPAD=1` for any server expected to see more than about eight users, with depth 3 to 16
users, depth 2 to about 48, no speculation above, and the admission stagger where byte-exact output matters. The
5-6% single-user cost of `CLASSPAD=1` is one copy kernel plus a 33-row GEMM per projection per step, the floor of the
design.

```bash
CLASSPAD=1 TENSOR_PARALLEL_SIZE=2 MTP_DEPTH=0 MAX_NUM_SEQS=128 MAX_NUM_BATCHED_TOKENS=1024 \
  MODEL_DIR=/models/Qwen3.5-4B-quantized.w4a16 VLLM_CACHE_DIR=/tmp/qwen35-4b-cache \
  repro/qwen35-4b-w4a16-b70/scripts/run-qwen35-4b-w4a16-server.sh
```

## The draft head only needs a shortlist (R294, 2026-09-12): 191.87 / 191.58

The MTP head drafts three tokens per step, each an argmax over the full 248,320-row vocabulary projection; the 9B
lane measured that projection at 28% of the step even as a draft-only INT4 copy. The draft only proposes. The target
verifies every proposed token with its own full FP16 head, so a draft head that scores only a **shortlist** of rows
cannot change any output: a true argmax outside the list is simply rejected. R294 builds the draft-only INT4 copy from
the shortlisted rows. With the 67,248-row list (the lab's own text united with system documentation and the image's
Python sources; 27% of the vocabulary, 99.5% of this model's suite output), the single-user headline is
**191.87 / 191.58 tok/s** against 177.56 / 177.26 for the same image scoring every row, every gate 12/12, acceptance within noise of
the control. Lists of 32k to 92k rows all land within 1% of it; 16k rows returns only +1% and 8k loses. Under many users with the 92k list (one card, `CLASSPAD=1`): 161.9 at one user, 1400 at 16 (exact), 1888 at 64, against 151.4 / 1353 / 1831 without the shortlist. Curve, lists and builders:
[`experiments/qwen35-4b-b70/notes/2026-09-12-the-draft-head-only-needs-a-shortlist.md`](../../experiments/qwen35-4b-b70/notes/2026-09-12-the-draft-head-only-needs-a-shortlist.md).

The launcher enables it by default (`DRAFT_SHORTLIST`, empty string to score every row); the served image is R294b
(R293 plus the shortlisted head, lists under `/opt/draft-shortlists/`). A deployment with its own traffic can
rebuild the list with `experiments/qwen38-27b-b70/docker/draft-shortlists/build-shortlist-v2.py`; a list that misses
tokens costs acceptance, never correctness. LocalMaxxing `cmtyqbecv0aq9ps01ms6eum7z` at `191.728 tok/s` (approved 2026-09-12).

## Rebased onto stock vLLM XPU v0.29.0, with three upstream fixes (R304, 2026-09-13): 191.37 / 191.41

The served image is now `neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304` (sha256:7cd7bb16): the same
overlay stack on the public v0.29.0 image (vllm-xpu-kernels 0.1.14.1, which also carries upstream GDN fix #544) with
the kernel library rebuilt from public sources, plus three open upstream vLLM fixes applied verbatim: PR #53059
(uniform-decode alias guard), PR #51565 (GDN first-chunk classification) and PR #53542 (active runtime-K width).

Why it matters beyond the version bump: on the previous image every **one-token prompt** and, at depth K, every
**(1+K)-token prompt** came back as a single-character wall (`!!!!...`) on 30 of 30 greedy runs. R304 returns 0 of 30
on every prompt length tested (1 to 6 tokens and long), with and without speculation.

Strict pair on R304 under the recipe contract: G1/G2/G3 12/12, depth 3 **191.37 / 191.41 tok/s**, no speculation 102.4
(the previous image measured 191.87 / 191.58). The 2K-32K exact-depth ladder is 18/18 on both arms; the no-speculation
64-user recipe with the 5 ms admission stagger is 64/64 on seven passes at about 2100 tok/s; a dynamic draft schedule
with a K=1 range runs without the kernel width assertion that killed stock v0.29.0. High concurrency, published ladder settings:
no speculation at 128 users with CLASSPAD=1: 2522 tok/s exact on one card, 3990 exact on two (R293: 2520 / 4015). The launcher pins
`VLLM_USE_V2_MODEL_RUNNER=0`: v0.29.0 defaults XPU to the V2 model runner, whose speculator has no draft INT4 head
(128 instead of 172 tok/s in the single-user harness). Build and provenance:
`experiments/qwen38-27b-b70/docker/rebase-v0290/` and `experiments/qwen38-27b-b70/notes/2026-09-12-rebase-onto-vllm-v0290.md`.

## Known limits

- Depths 1-6 have since been run on one card (all lossless on the strict suite; 2 and 3 tied at the top, 4 level,
  5 and 6 slower); under R293 depth 2 leads above 16 users.
- Two-card concurrency identity without an admission stagger is not qualified above 32 users without
  speculation, or above 16 with it; with the 5 ms stagger it is byte-exact at 64.
- Not yet clean-host tested.
