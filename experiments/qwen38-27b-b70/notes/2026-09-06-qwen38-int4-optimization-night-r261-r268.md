# Qwen3.8-27B INT4 headline: overnight optimization pass (2026-09-06, R261-R268)

Headline going in: R256 image, TP2, XPU graph capture (FULL_DECODE_ONLY, sizes 1-8), draft-only INT4 head, MTP depth 4,
strict launcher env: **112.36 / 112.33 tok/s** single user, lossless (12/12 vs the MTP0 oracle), identity-qualified through
c8; MTP0 49.8 tok/s, exact c1-c64. Goal: find remaining lossless decode levers, single- and multi-user, then re-publish.

## R261 - graph capture sizes extended to 80 tokens (ladders c1-c64)

Sizes [1..8,10,15,16,20,25,30,32,40,50,60,64,80] (12 decode graphs captured). **No aggregate change at any rung** (MTP4:
c1 106.4 / c2 87.6 / c4 290 / c8 398 / c16 531 / c32 355 / c64 445 tok/s vs R259 106.8 / 86.3 / 219 / 403 / 532 / 359 / 450;
MTP0 within noise, exact c1-c64). Batch size is not what limits multi-user speculative throughput. Observation: in the
single-pass ladder the c2 rung's first request waited 1.02 s for its first token (the other 0.04 s): a first-encounter stall,
so single-pass ladders under-report the steady state (R265 repeats every rung).

## R262 - torch-profiler trace of the headline at c1 (64 tokens)

Rank 1: execute_model 624 ms of a 1030 ms window (25 calls); inside it the eager draft passes (`propose`) 320 ms, i.e. about
half of the worker's step time, 716 `int4_gemm_w4a16` launches and 405 all-reduce calls for 22 decode steps; the verify step
is a captured graph (its kernels are not itemized by the XPU profiler; replay costs ~nothing on the CPU). Rank 0 spends
280 ms inside the ring all-reduce kernel where rank 1 spends 3.5 ms: rank 0 waits for rank 1 at every eager all-reduce.
Between steps the worker idles on the scheduler round trip. **The lane is host-bound**; the levers are capturing the draft
loop and cutting the per-step host path, not bigger decode graphs.

## R263 - vLLM V2 model runner (VLLM_USE_V2_MODEL_RUNNER=1), FP16 draft head

Boots on XPU with TP2; captures the target decode graph (1), the speculator prefill graph (1) and the **fused 4-step draft
loop as one FULL graph** (1). Same prompt as R262: text identical for the first 64 tokens. Three 256-token completions:
78.0 / 78.6 / 78.2 tok/s wall (FP16 head; acceptance 1.61 accepted per step on this technical-prose prompt vs 1.91 for the
V1 INT4-head server on the same prompt). Step time is unchanged versus V1 (~33 ms), so the fused draft graph alone does not
shorten the step; the between-step host path remains. Follow-ups: R266 image ports the draft-only INT4 head to the V2 loader
(`v1/worker/gpu/spec_decode/eagle/utils.py`), R267/R268 test async scheduling on V1 and V2.

## R264 - c2/c8 profile: OOM

The with-stack torch profiler on two workers exceeded the 12g container cgroup during the c2 window (worker OOM-killed at
02:25:06); rerun as R264b without the python stack tracer.

## Image identity of the headline pair (correction to publish)

The container records show the **R257 headline pair (112.36 / 112.33 tok/s) ran the R228 image** (`aaf920b0…`), not R256: its
wrapper sourced `final-int4-config.env` (R228) without overriding the image. Its server log shows the draft-only INT4 head was
prepared through the base (r62) path ("Prepared MTP draft-only INT4 lm_head from the loaded target weight"), so the R256
fallback branch is never taken on this model (the relabelled checkpoint's lm_head is unquantized and already carries
`make_xpu_int4_draft_copy`). R258 (depths 5/6), R259 (ladders) and R260b (depth ladder) ran R256. R256 = R228 + an inert
(for this model) Python fallback; both images execute the same code on this lane and both are public on GHCR. The recipe,
package, matrix and manifest must say so.

## R267 - async scheduling is already on

`--async-scheduling` on the V2 runner (R267b): 77.9 / 78.3 / 78.1 tok/s and 790/490 accepted/drafts, identical to R263
without the flag. In this vLLM the flag defaults to auto and resolves to on for MTP with the multiprocess executor, so every
published run already had it. (R267a on V1 collided with an orphaned ladder server and is re-run as R267a2.)

## R268 - V2 runner + draft-only INT4 head (R266 image)

`docker/r266-v2-draft-int4-head.py` ports the R62/R256 draft-only INT4 head into the V2 loader
(`v1/worker/gpu/spec_decode/eagle/utils.py`); both ranks log "R266: V2 speculator uses a draft-only INT4 lm_head". Same
prompt, three 256-token completions: **97.5 / 98.1 / 98.1 tok/s** (R268a, async flag) and 97.5 / 97.9 / 97.8 (R268b, no
flag) vs 78 with the FP16 head; acceptance 795/485 = 1.64 per step in both, so the INT4 head shortens the fused draft graph
(four FP16 vocabulary projections per step gone) rather than raising acceptance. Outputs are run-to-run identical, identical
to the FP16-head V2 output over 256 tokens, and identical to the V1 headline output over the first 64 tokens. Class-balanced
strict pair vs the MTP0 oracle: R269; ladders: R270.

## R264b - c2 / c8 profiles without the stack tracer

c2 window (2.8 s, rank 0): **1.05 s of Dynamo recompilation (three frames)** on the first two-sequence batch: this is the
c2 stall of the single-pass ladders (TTFT 1.02 s on one request) and it does not recur at c4/c8. A warm-up request at
concurrency 2 after boot, or a second ladder pass (R265b), removes it from measurements. c8 window (1.7 s, 20 steps of
8 x 5 tokens): device kernels 381 ms of 1735 ms (gemm 290 ms), i.e. the cards are busy about a quarter of the time; the CPU
side is dominated by aten::index / copy_ / to (1398 index calls, 6059 copies) in the eager draft passes and sampling. The
multi-user lever is therefore the same as the single-user one: a captured draft loop (V2 runner).

## R265b / R270 - two-pass ladders (V1 headline vs V2 runner)

Warm (second) pass, MTP depth 4, aggregate tok/s and identity:

| c | V1 R265b | V2 R270 | MTP0 (both) |
|---|---|---|---|
| 1 | 107.3 (1/1) | 107.8 (1/1) | 50.1 |
| 2 | 147.6 (2/2) | 149.7 (2/2) | 94.8 |
| 4 | 252.9 (4/4) | 260.7 (3/4) | 179.5 |
| 8 | 405.4 (8/8) | 412.1 (8/8) | 317-319 |
| 16 | 580.4 (16/16) | 588.5 (16/16) | 505-510 |
| 32 | 360.7 (31/32) | 362.7 (31/32) | 839-841 (32/32) |
| 64 | 445.3 (58/64) | 437.8 (62/64) | 999-1001 (64/64) |

The first V1 pass still shows the c2 recompile stall (85.4); V2 has none (150.4 in pass 1). Identity-qualified through c16 in
the warm pass on both runners. **Both collapse between c16 (80 verify tokens) and c32 (160)**: the speculative step at c32
costs ~3x the c16 step while plain decode scales normally. R273 (GDN spec group size 64 / 1 / 16 at c16 and c32) and R274
(c32 profile) probe it.

## R269 - V2 runner + INT4 head, strict pair

**112.70 / 112.96 tok/s**, G2 12/12, G3 12/12 x2 vs the eager MTP0 oracle: lossless and equal to the V1 headline
(112.36 / 112.33). R267a2 (V1) vs R268a (V2) on one prose prompt: 97.1-97.4 vs 97.5-98.1 tok/s, same acceptance
(795/485), identical text. The fused draft-loop graph does not shorten the step; the ~8 ms/step host round trip and the
two-rank all-reduce sync are common to both.

## R272 - per-rank CPU binding (numactl --physcpubind)

Rank 0 on cores 0-3, rank 1 on 4-7 (R272a): 96.9 / 97.3 / 97.5 tok/s; with SMT siblings (R272b): 96.9 / 97.6 / 97.4;
unbound (R267a2): 97.1 / 97.4 / 97.4. No effect; each worker's main thread already spins at ~100% on its own core.

## R273 - GDN speculative group size at c16/c32

Single-pass rungs (they carry the first-encounter recompile at c16). c32 steady state: group 16 (R273a) 352.6, group 64
(R273b) 355.1, group 1 (R273c, per-sequence serial) 288.2 tok/s. Grouping is not the c16->c32 collapse; per-sequence serial
is uniformly slower. MTP0 c32: 32/32 (R273a), 31/32 (R273b, the known near-tie residual).

## R274 - c32 profile (no stack tracer)

Window 6.6 s = 1.08 s Dynamo recompilation on the first 32-sequence batch + 1.0 s mixed prefill step (583 prompt tokens) +
20 uniform decode steps of 32 x 5 = 160 tokens at **162 ms/step** (145.6 ms in the steady step examined). Inside that step
(rank 1): device busy 108 ms of 146 ms wall: `gemm_kernel` 58 ms, `gdn::gated_delta_rule_spec_kernel` 27 ms, all-reduce
12.6 ms; CPU: the eager compiled verify call 134 ms, `vllm::gdn_attention_core_xpu` 42.7 ms over 48 calls (the R228 grouped
branch does a `.tolist()` sync plus a gather/scatter per layer per group), 129 all-reduces. Kernel counts across profiles: at
c8 (R264b) the 40-token verify replays a captured graph, whose kernels the XPU profiler does not itemize; at c32 the 160-token
verify exceeds the captured sizes and runs eagerly, exposing 2256 `gated_delta_rule_spec_kernel` launches at 263 us average.
Two candidate causes remain for the collapse: the eager verify (launch cost and the grouped GDN host path) and the spec
recurrent kernel's own cost at 16-sequence groups. R275 (capture sizes to 320, c16/c32/c64 two-pass ladders) and R274b/c
(c32 profile with group 64; c16 profile) separate them.

## R275 / R275b - graph capture above 16 sequences

R275 (capture sizes to 320, group 16) fails at capture: the grouped GDN branch's `.tolist()` ("wait method cannot be used
for an event associated with a command graph"). R275b (group 64, so the branch is not taken; 18 decode graphs captured to
320 tokens), two-pass c16/c32/c64: **c16 573.9 (16/16), c32 364.4 (32/32), c64 447.3 (60/64)** - no change versus eager
verify (R265b 580 / 361 / 445). MTP0 unchanged (c64 979). So neither the grouped host path nor the eager verify explains the
ladder's c32 pace: the profiled uniform step at c32 is ~110 ms (R274b), which would be ~750 tok/s, while every one of the 32
ladder requests advances at ~12 tok/s (~225 ms per step). The difference is outside the model step (request shape,
streaming, scheduler admission); R278 is an A/B of request shapes on one server.

## R277 - R276 image (sync-free grouped branch): GPU fault

`docker/r276-gdn-spec-group-sync-free.py` (image `qwen38-int4-gdn-spec-group-sync-free-r276`, `_xpu_ops.py`
sha256 6ee6b8db…) launched at 04:45; at 04:47:00 the kernel logged `xe 0000:03:00.0 Fault response: Unsuccessful -EINVAL`
plus a device coredump during the weight load (the same weight-staging fault seen twice on 2026-09-05) and the server hung
until the 45-minute health timeout. The compute/XCCL health check passes afterwards, but this boot carries the fault
signature, so runner-gated campaigns refuse to start; R277b is queued behind a reboot (`boot-20260906-…-r277b-r278-autolaunch.sh`).
