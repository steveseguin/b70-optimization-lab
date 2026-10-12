# Packet36: official one-token draft provider

CPU preparation of packet32's two-rank runtime plus `--draft mtp` on rank1.
No device binary ran. No speed is claimed. Target model, quantization, arithmetic
`iq3-p17-detmath-v2`, kernel sources, dispatch vocabulary and v2 oracle remain
unchanged. This is the quantized compressed Unsloth IQ3 target lane, not the
separate official FP8 target lane.

The provider is **draft-only requantisation of the official draft head; cannot
change output**. Its weights come from Qwen/Qwen3.8-Flash-Next-FP8 revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`. prepare_mtp.py authenticates every
containing safetensors file against packet1's publisher SHA256, requires all 3101
mtp tensors, and records each tensor hash. C++ checks file identity and each
tensor's bytes/hash again before conversion. Missing or changed tensors abort
loading; they are never silently replaced.

## Confirmed-input schedule

Target HALF(p) consumes x_p and emits x_(p+1). Its final four streams are H_p.
DRAFT(p) consumes H_(p-1) and the shared target embedding of **confirmed** x_p,
at cache/RoPE position p-1, and proposes g_(p+1). First row is H0+x1; there is
no artificial initial hidden row. Every shifted prompt row runs the draft
layer. Prompt rows may skip the final mixer/head/argmax when no proposal is
needed; their draft KV/indexer state is still complete.

```text
                              time →
rank1:  B(p-1) → confirms x_p | D(p) → g_(p+1) | B(p) → confirms x_(p+1)
rank0:  A(p,previous guess) ----- keep, or undo + redo A(p,x_p) -----|
                                                                   A(p+1,g_(p+1))
controller: ACCEPT rank1; start DRAFT; resolve rank0; wait DRAFT;
            hand over confirmed A(p); start B(p) and speculative A(p+1).
```

The controller launches DRAFT immediately after rank1 acceptance, before
resolving rank0 speculation. A socket reply publishes the reserved 40-byte
control record at offset 131072. Sequence, predicted position, validity and
vocabulary bounds are checked before its token can become a rank0 guess.
Only target HALF replies enter the emitted-token list.

Induction: rank1 receives only the confirmed target half for each position.
Therefore H_(p-1), x_p and every earlier draft cache row are identical whether
rank0 guessed correctly, guessed wrongly or did not guess. DRAFT is invoked
once in that confirmed order. Rank0 rollback cannot reach draft allocations,
and draft state needs no rollback. CPU cache-byte comparisons substantiate
this for speculation versus suppressed/garbage proposals; target-state tests
also cover provider errors before/after append and a cooperative stall.

Let A and B be rank0/rank1 half wall times, D draft time, and R the rank0 redo.
Ideal steady hit cycle is max(A,B+D). Miss cycle is
max(max(A,B)+R,B+D), plus IPC/accept/handover overhead. The acceptance-weighted
model is a*hit+(1-a)*miss. CPU acceptance is measured below; A/B/D on device are
not measured, so this model supplies no speed prediction. With equal halves
A=B=T/2, redo R=A and D<=A, it reduces to a*(T/2+D)+(1-a)*T.
The measured CPU acceptance is a development-prompt estimate, not a fixed
acceptance guarantee for other requests.

Moving DRAFT until after rank0 resolves adds serial delay: D+max(A,B). Moving
it earlier using an old guessed embedding could overlap the target head but
would make draft cache state speculative on a miss, requiring another rollback
mechanism. This packet implements only the confirmed-input schedule.

## Formats, kernels and memory

Dense official weights remain BF16. Official offset norm parameters become F32
1+w gains, avoiding an additional BF16 rounding. The merge hidden norm spans
all 10240 values, followed by four shared FC-hidden projections and the projected
embedding broadcast. Draft QSA is one full-attention layer, with independent
BF16 KV/raw/pooled indexer cache, shifted token, position p-1 and no PLE.

All 512 FP8 routed experts convert on the host at load time: decode E4M3 bytes
with multiplicative 128x128 BF16 weight_scale_inv blocks, then nearest-even
symmetric int8 max/127 quantization in groups of 16. Each row stores code bytes
followed by one F32 scale per 16 codes. This matches the code/scale prefix read
by the existing expanded dense body; it is a new draft quantizer, not a
lossless GGUF converter. Routed gate/up share input and execute as a pair;
down executes separately for ten routes. No compressed KV is used.

Draft dense/routed/merge operations are compiled by format, K and operation.
The QSA/norm/router/hyper-connection plan reuses target operation bodies with
private draft bindings. Draft activation/mix/combine have compile-time wrappers
using the same scalar arithmetic. Kernel captures are guarded at 1024 bytes.
The head uses the target's own immutable resident weight allocation, dispatch,
logits kernel and argmax, with private output/scratch. Full head is the default;
shortlist mode is unqualified and rejected. Packet31
measured 198/256 accepted tokens with its full FP8/int8 references, versus
171/256 with even its largest 65,536-row shortlist; this is why no shortlist
is enabled. These packet31 counts are reference evidence, not packet36
measurements. See ../packet31-mtp-acceptance/acceptance.json.

The host implementation executes the same lane products, BF16 boundaries,
ordered sums and explicit trees as its proposed device kernels. This is an
implementation contract; **host/device byte parity awaits KD**. Both paths use
no-fast-math and no contraction; the device build additionally keeps IEEE
FP32 denormals and precise division/square root. Target source bytes are bound
in target-source-identity.json. Torch reference differences include dense trees,
HC reassociation, routing-weight rounding, sigmoid boundaries and detmath.

| Rank1 allocation | Bytes |
| --- | ---: |
| Supplied target rank1 allocations | 27,855,798,676 |
| Draft expert int8 codes | 2,516,582,400 |
| Draft expert F32 group16 scales | 629,145,600 |
| Draft dense weights, including F32 norm gains | 181,225,472 |
| Draft BF16 KV and indexer, context 256 | 606,208 |
| Draft scratch, controls and remaining buffers | 17,711,414 |
| Rank1 total | 31,201,069,770 |
| Card capacity | 34,242,297,856 |
| Remaining capacity | 3,041,228,086 |

This allocation plan clears the 1.5 GB margin without moving a target layer or
keeping experts packed. Rank0 is unchanged and both ranks retain the inherited
30GiB arena cap. Driver overhead/device residency remain coordinator evidence.
CPU fixtures stream target layers and hold an extra 839,321,600-byte copy of the
same expanded target head; resident device rank1 shares its head. memory-plan.json
contains the exact arithmetic and measured host allocation census basis.

## CPU agreement and gates

<!-- cpu-results:start -->
| Prompt | Device-arithmetic draft acceptance | Packet31 FP8 acceptance | Agreement with FP8 | Agreement with int8 |
| --- | ---: | ---: | ---: | ---: |
| incident-retrospective | 84.3750% (54/64) | 84.3750% | 98.4375% | 100.0000% |
| code-review | 67.1875% (43/64) | 67.1875% | 98.4375% | 100.0000% |
| customer-email | 81.2500% (52/64) | 81.2500% | 100.0000% | 100.0000% |
| benchmark-analysis | 78.1250% (50/64) | 76.5625% | 98.4375% | 98.4375% |

Pooled acceptance is 199/256 (77.7344%). These are development prompts, not a benchmark suite.
For this prompt mix the cycle model is 0.77734375*max(A,B+D) + 0.22265625*max(max(A,B)+R,B+D). Device A/B/D/R are not measured.

All ten real-model CPU modes passed: 8/8 tokens and 384/384 layer fixtures per mode, across GNU and Intel builds. Full gate counts and binary identities: [CPU results](CPU-RESULTS.md) and [build receipt](build-receipt.json).
<!-- cpu-results:end -->

Final measured results and binary identities are generated into CPU-RESULTS.md
and build-receipt.json. agreement-*.json carries every scored position's target
and draft token, reference agreement and full-vocabulary logit RMS/L2/max-absolute
distance. No output tolerance is applied to target tokens or target fixtures.

The 63-interval decode definition is inherited from packet32: token1 completion
to token64 completion. Per-token receipts include guess/hit/miss, draft wall and
local GPU time, rank1 delay before its half, rank0 wait for a proposal and cycles
classified by the guess that caused the cycle. Draft GPU time is the sum of
profiled compute-event execution durations; copies, uploads and IPC remain in
the wall-time measurement. Rank1 delay and rank0 waiting are controller-observed
wall intervals, with native command timestamps retained in the trace.
Prompt time includes the prompt
draft-cache work. CPU rates, scripts, injected faults and class profiling never
populate the device speed result.

Declared provider errors and cooperative 300-second expiry permanently disable
the provider after drain. Subsequent positions use no guess. A real stuck kernel,
owner failure or hardware fault aborts safely: latch, durable failure before
teardown, one cooperative stop, no retry/hard kill/reset. Loading ranks receive
no process signals. LIFETIME.md and WINDOW.md retain the packet32 owner rules.

## Reproduction and integration

All writes stay in this packet; earlier packets and model files are read-only.
On another host or after restoring model files, run prepare_mtp.py first to
authenticate the local files again; the manifest deliberately binds their local
file identities as well as publisher and tensor hashes.
Use nice 19, idle I/O, OMP=2, inherited affinity and at most two compiler jobs.
Each compiler campaign serializes its real-model modes; at most two campaigns
overlap, and an exclusive lock serializes their official-draft allocations. build.py builds host/sanitizer
programs and compiles device programs; it never executes a device binary.
CPU rebuild and verification from repository root (all output stays here):

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 \
  /home/steve/.venvs/vllm-xpu/bin/python -B \
  experiments/own-xpu-runtime/stage2/packet36-draft/build.py all
```

This needs adequate disk headroom. If packet31's captures were removed,
reference_reproduce.py regenerates only missing target captures beneath this
packet, at two threads, and checks every stream against packet31's hashes.
It also regenerates reference samples and checks their recorded hashes.
The captured inputs already retained here are bound by capture-input-*.json;
KD does not depend on packet31's working directory after capture preparation.
See WINDOW.md for exact coordinator K/KD/W commands, DEADLINES.md for estimates
and watchdogs, INTEGRATE.md for packet34/35 boundaries, and RETENTION.md for the
large tensor manifest and ignored coordinator artifacts. The three independent
reviews are review-wiring.md, review-isolation.md and review-controller.md.

CPU preparation closeout and remaining device gates: [CLOSEOUT.md](CLOSEOUT.md).
