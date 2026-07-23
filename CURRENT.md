# Current Workspace State

Last reviewed: **2026-07-22**

## Authority And Update Rule

This is the sole cross-repository authority for the loaded service, active
optimization lane, protected work, and immediate next actions. Result packets
own promoted evidence; lane handoffs own detailed resume context; `notes/` owns
chronology. Do not append experiment history here.

Always verify the actual endpoint, relevant processes, and Git status before an
operational change. A runnable recipe or installed service unit does not prove
that its model is currently loaded.

## Live Service

No process was listening on the public LAN `:8000` endpoint when the Qwen lane
was closed on 2026-07-13. The last configured role was the temporary Gemma 4
26B A4B Q8 coding-agent service. Its restore, validation, and stop procedure is
in [`docs/gemma4-26b-q8-service-runbook.md`](docs/gemma4-26b-q8-service-runbook.md).
Confirm the endpoint and process state before relying on this observation.

No DeepSeek service is currently running. The promoted DSpark7 sharded target-
argmax record service was stopped cleanly after three strict suites and the
final exact canary. Its evidence is
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-sharded-target-argmax-candidate-20260718T2100Z`.
The DeepSeek lane is paused/closed at this record. Its durable publication is
the [result packet](results/deepseek-v4-flash-k160-b70/README.md),
[standalone repro](repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md),
and [frontier closeout](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md).
Do not interpret the older bounded-next-work detail retained below as an active
instruction; another configuration is being started separately and is outside
this closeout.
The exact public-record source identity is vLLM `264c7f2f7`, XPU kernels
`313156737`, and oneCCL `48fda4f0e`. Restore it with target PIECEWISE, draft
breakable PIECEWISE,
`DSPARK_SPEC_TOKENS=7`, `VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE=1`,
`VLLM_XPU_GREEDY_FUSED_REJECTION=1`,
`VLLM_XPU_GREEDY_SHARDED_TARGET_ARGMAX=1`,
`VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS=1`, and
`VLLM_XPU_DSPARK_PERSISTENT_MARKOV=1`, and
`VLLM_XPU_DSPARK_REPLICATED_MARKOV_W1=1`, plus
`VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M=8`,
`VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M=8`, and
`VLLM_XPU_MXFP4_SMALL_M_N=128`, and
`VLLM_XPU_V4_ROUTER_NORM_MAX_M=8`; the draft queries M=7 while
target verification remains M=8. The preceding QNorm/route-portfolio source remains
historical evidence at vLLM `4a6fd8747` and XPU kernels `18a44f440`.
The complete manager-facing resume is
[`experiments/deepseek-v4-flash-reap-xpu-b70/ORCHESTRATOR_HANDOFF.md`](experiments/deepseek-v4-flash-reap-xpu-b70/ORCHESTRATOR_HANDOFF.md).
Current Option-4 development HEADs are vLLM `67044c25d`, XPU kernels
`5a1e9fa46`, and
oneCCL `48fda4f0e`; later experiments are default-off and do not replace the
public-record identity. The latest fixed-M8 MHC+RMS fusion was rejected on card
0 as inexact and slower before model load. The immediate bounded lane is the
M7/M8 shared+routed activation portfolio, followed by exact DPAS W2 inside the
incumbent captured collective Markov path. The strategic lane remains the
fixed-address Intel decoder transaction.
Option-4 M1 attention Phase 1 now has a clean 344/344 two-bucket oracle packet
and a passing 43-layer raw command-list component gate, but its guarded TP4
endpoint is a Phase-2 no-go: the candidate regresses by 0.181654 ms/token and
fails cross-run exact-token identity. The selector remains default-off and no
LocalMaxxing submission was made. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-20-option4-phase1-m1-attention-debug-to-done.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-20-option4-phase1-m1-attention-debug-to-done.md).
The restorable nonspeculative direct M=1 routed-MoE record recipe is at
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-direct-moe-wideepoch-candidate-20260715T2220Z`:
vLLM `a681dbb2b`, XPU kernels `6522849b0`, and exact-version oneCCL
`48fda4f0e`. `VLLM_XPU_V4_M1_ROUTER_NORM=1` and
`VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE=1` are active; speculation is disabled.
The sustained exact gate passes 70/70, including the old rollover failure
positions 28 and 58.
The runtime is force-preloaded from
`/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f` and routes only
SYCL all-reduces larger than 131,072 bytes to the safe path. Its Arc ring uses
a 24-bit collective readiness epoch plus a 7-bit communicator tag instead of
the rollover-prone 11-bit sequence. All four worker maps were verified. The
rejected native dual RMSNorm remains off.
The host reboot auto-started the two Gemma service units and occupied the B70s;
both units were stopped before DeepSeek testing and remain stopped.
The authorized 2026-07-15 host reboot recovered all four B70s: discovery,
per-device allocation/compute, runtime status, and a four-rank exact XCCL gate
pass, all four external links report Gen4 x16, and ASPM is `default`. The
external `/mnt/usb-models` volume did not automount, but the active K160 model
is on `/mnt/fast-ai` and the record launcher maps oneCCL from the DeepSeek
virtual environment first.

The unauthenticated LAN front door is intentional for this private network. Do
not silently add authentication or change its exposure policy.

## Laguna S 2.1 Bring-Up

The active bring-up lane is Poolside Laguna S 2.1 INT4 on four B70s. The
target and DFlash attention set is now enumerated. The DFlash paged-decode
tuple `16,128,64,false,false,false` was rebuilt with oneAPI 2025.3 at kernel
commit `c615c38fb79d4035118c05675565dbf7e2443a90`; the expanded seven-case
changed-input oracle passed independently on all four B70s. The tokenizer's
secondary processor probe remains repaired at vLLM commit
`e0e56c7e81780ae413c5e22549dcb208d65440aa`. Explicit native BF16 KV cache
writes were repaired at vLLM commit
`6bf7d6b83cb20c335b5e9a8ffda95d646338bbf5`.

The earlier target-only TP4+EP4 path was not bitwise repeatable: identical cold
q=1 requests could change token 0 because M-dependent INT4 projections, atomic
MoE remap, and XCCL reduction order moved BF16 values by one ULP. The first
exact repair at vLLM `d26fe57b3` serialized target work as M=1 rows. The current
batched-exact path at vLLM `cb616c670` plus XPU kernels `6fc06b08c` retains M=1
numerical lanes inside batched BF16 projections, uses one paged-decode verifier
pass, fixed-rank fused sums, and deterministic direct M8 MoE.

DFlash now works with the quantization-matched
`poolside/Laguna-S-2.1-DFlash-INT4` draft. The originally supplied plain BF16
draft remains incompatible with the INT4 target's Hadamard-rotated auxiliary
states and accepted zero tokens even after the kernel fix. With the matched
draft, the cold BF16-KV gate accepted `953/1,953` proposals (48.797%), mean
accepted draft length 3.4158, and per-position survival
`[83.871,67.025,50.896,43.369,37.276,30.824,28.315]%`.

The prior 31.774278 tok/s 128-token staged row was blocked after its full-512
extension passed only 12/13: a 512-token response contaminated the following
request at output token 0. Input tracing located the first bad tensor at the
next request's layer-0 embedding/residual boundary, before KV, attention, MoE,
or decoder reductions. DFlash-only `--no-async-scheduling` serializes that
request boundary while retaining batched q=8 verification. Two independent
fresh DFlash starts now match the canonical q=1 teacher **13/13 + 13/13** and
each other **13/13**, with all 26 requests cache-zero; long-then-next is 2/2
on both starts and the 863-token rollover prompt is 1/1 on both. Exact medians
are 33.103677 and **33.085825 tok/s**; the lower second-start value was
submitted and approved.
Acceptance is 4,642/12,040 = 38.5548%. This is a valid first Laguna record
under the max-512 contract and is APPROVED as LocalMaxxing
`cmrw7cn1k006jnz01gq2z981v`.

The default-off fused-W1 plus route-parallel-W2 follow-up is the current
approved public record. At vLLM `6a570e70b` plus kernels `20cfa3aef`, it retained
the exact fused W1+SiLU launch reduction while restoring the incumbent
route-parallel INT4 W2 and fixed-order gather. Both fresh-start suites passed
teacher exactness **13/13 + 13/13**, cross-start exactness **13/13**, cache-zero
**13/13 + 13/13**, long-then-next **2/2 + 2/2**, and rollover **1/1 + 1/1**.
Fresh-start medians were **33.303424** and **33.267564 tok/s**; the lower start
beats the prior 33.085825 row by 0.181739 tok/s (+0.5493%). LocalMaxxing
approved the lower result as `cmrwlyxez00f4nz01zefturuv`; its queue is
`data/localmaxxing-laguna-s-2.1-int4-b70-dflash-fused-w1-route-w2-33.268tok-20260722.queue.json`
and the prior `cmrw7cn1k006jnz01gq2z981v` row is superseded.

Resume from
[`experiments/laguna-s-2.1-xpu-b70/notes/2026-07-22-dflash-depth-sweep-and-profile-decomposition.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-22-dflash-depth-sweep-and-profile-decomposition.md).
Candidate B at the same vLLM commit plus XPU kernels `210a6eb60` changes only
W1/W2 workgroup enumeration to cycle across the 80 routed rows at each N tile.
The four-card gate is bitwise exact **64/64** and reduces the mean routed
component **0.561952 -> 0.538143 ms/layer**. Two fresh full suites are teacher
exact **13/13 + 13/13**, cross-start exact **13/13**, cache-zero
**13/13 + 13/13**, long-then-next **2/2 + 2/2**, and rollover **1/1 + 1/1**.
Fresh-start medians are **33.438927** and **33.546439 tok/s**; the lower start
beats the approved 33.267564 record by 0.171363 tok/s (+0.5151%). LocalMaxxing
approved it as `cmrwot89400gqnz014oodtlbp`; the payload is
`data/localmaxxing-laguna-s-2.1-int4-b70-dflash-m8-route-interleave-33.439tok-20260722.queue.json`
and the prior `cmrwlyxez00f4nz01zefturuv` row is superseded.
Remote-route zeroing remained exact and removed 95 fill launches/cycle, but
regressed to 32.590900 tok/s. The deterministic graph pass fixed the M=8 qkv
shape guard and added an exactness-complete AOT cache identity. A default-off
per-layer probe then localized successive compiled/eager differences in Q/K
RMSNorm, gate softplus, local attention output BMM, and fused residual-add +
post-attention RMSNorm; rank 2 also retains a one-ULP qkv INT4 GEMM difference.
The correct full contract passed only 0/13 at 30.992062 tok/s, so no second
start, DFlash measurement, payload, or submission was allowed. The graph path
remains experimental and unpromoted. The guarded persistent/fused direct-M8
expert transaction at vLLM `9164595cd` plus kernels `d0b5b1539` is bitwise
exact across its four-card component gate and both full fresh-start suites, but
it is also unpromoted: fresh-start medians were 33.008027 and 33.908219 tok/s,
so the lower reproducible result did not beat 33.085825. Its 282 -> 94 routed
launch reduction serialized W2 expert slots and raised routed-MoE device time
9.077583 -> 10.388394 ms/cycle. Preserve it default-off. The exact depth sweep
over 4-10 left depth 7 best: depths 5/6/7 were 13/13 exact but slower than the
record, depth 4 was 12/13, and depths 8-10 left the exact M<=8 target path,
matched 0/13, and regressed to 4.94-6.11 tok/s. The old 13.409 ms/cycle
`other_noncollective` bucket was a classifier artifact containing W1 and W2;
the true residual is 3.591 ms/cycle. Its next single named kernel lever is
TopKGating at 0.560 ms/cycle. The larger target family is BF16 attention QKV+O
at 2.919 ms/cycle; the draft-side family is dense MLP at 0.637 ms/cycle. The
default-off native-M8 BF16 attention MM experiment at vLLM `b52d6a592` passed
the four-card bitwise gate 896/896 and both fresh exact suites, but its
32.298869/32.171000 tok/s medians regressed from the approved record. Resume
from the [exact negative note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-22-bf16-attention-m8-mm-negative.md);
the follow-up default-off exact M=8 Q/K RMSNorm + RoPE fusion at vLLM
`d503073ec` plus kernels `9525343e7` passed its four-card component gate
256/256 and reduced isolated launches 144 -> 48 per target cycle. Both fresh
full suites were teacher exact 13/13, cross-start exact 13/13, cache-zero
13/13 + 13/13, long-then-next 2/2 + 2/2, and rollover 1/1 + 1/1. Its medians
were 34.233360 and 33.190702 tok/s, so the lower start missed the approved
record by 0.248228 tok/s (-0.7423%); no payload was staged. Resume from the
[fusion negative note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-22-exact-m8-qknorm-rope-fusion-negative.md).
The preregistered A-B-B-A follow-up corrected the earlier interpretation:
fusion beat both adjacent controls in headline throughput, cycle time, and
11-12/13 prompt rows, but the per-position DFlash acceptance histograms
differed and the candidate's lower 33.302984 tok/s start still missed the
record by 0.4065%. All four starts remained teacher exact 13/13, cross-leg
exact 13/13, and cache-zero. It is strong directional evidence but failed the
frozen promotion gates; no fifth run, payload, or submission was allowed.
Resume from the [crossover result note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-22-qknorm-rope-crossover-result.md).
The Laguna-only XPU auxiliary-stream gate for the complete shared-expert MLP
was bitwise exact on all four cards but a decisive performance negative:
overlapped pairs were 10.03-10.77% slower on every B70. The preregistered gate
therefore stopped the lane before any endpoint. The failed candidate is
preserved at vLLM `3d1222281` and explicitly reverted at `f239a1014`; the
current source tree again matches `d503073ec`. Resume from the
[negative result](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-22-shared-expert-xpu-stream-negative.md).
The exact BF16-input/FP32-sigmoid M=8 router specialization at vLLM
`689ee3643` plus kernels `af6811818` passed its four-card component gate and
removed about 0.45-0.48 ms per 47-layer isolated cycle. In the frozen cold
endpoint phase it remained teacher exact 13/13 and cache-zero on both starts,
won 10/13 paired rows, improved the paired median 0.7138%, and saved 1.0301 ms
per target cycle. However, the official candidate headline was
32.310122 versus the adjacent control's 32.969012 tok/s (-1.9985%), so the
preregistered early-stop rule forbade B2/A2 and no payload was staged. Resume
from the [phase-1 result](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-m8-bf16-router-topk-preregistration.md).
Select the next lever from the independent occupancy and exact-fusion audits;
do not stack this router candidate into another endpoint trial unless a future
preregistered design explicitly isolates its contribution. Do not revisit
route buffer fills or progressively serialize the whole model into opaque
graph islands. Preserve the exact approved base at vLLM `cb616c670` plus
kernels `6fc06b08cd10a9e9e7d15e62e1afcf06e7ab6c73`. Current experiment heads are
vLLM `689ee3643f320e4a10c621ddd829620bc2f5b3b3` and kernels
`af6811818ef797aa86aef51bda15ae9c49040f7b`. Also preserve the DeepSeek
option-4 branch and all `preserve/*` tags. All Laguna model, cache,
temp, log, and run artifacts remain on the external Corsair drive; do not write
them to `/mnt/fast-ai`. Postflight on 2026-07-23 left no Laguna endpoint or
worker running; all four B70s are free.

## Optimization Transition

The Qwen3.6 27B Q4_0/DFlash optimization lane was closed on 2026-07-13. Its
`>=100 tok/s` TP1 and `>=200 tok/s` multi-B70 single-session objectives were
not reached. The final strict one-B70 record is `47.818818 tok/s`, approved by
LocalMaxxing as `cmrjbx8bc02g8mj01yzz2v701`. The authoritative closeout is
[`notes/2026-07-13-qwen27-dflash-sycl-closure.md`](notes/2026-07-13-qwen27-dflash-sycl-closure.md).

The investment-gated DeepSeek V4 Flash vLLM/XPU lane ran from 2026-07-13
through its 2026-07-21 closeout for one active generation on four B70s. It is
now paused. The frozen source was
`deepseek-ai/DeepSeek-V4-Flash` revision
`60d8d70770c6776ff598c94bb586a859a38244f1`. The first runnable candidate is
the uniform-K160 `0xSero/DeepSeek-V4-Flash-180B` smoke checkpoint at revision
`7c360e1cd4a5168099dbc54d16d929bf6df04990`. It is a 96.026 GiB standard
safetensors artifact with 160 experts in every layer, so explicit TP4 expert
parallelism assigns 40 experts per rank without heterogeneous loader surgery.
It is not yet the quality-certified final model: its hash layers are pruned,
its calibration is not reproducible, and its published ranking is not true
REAP. A later
official-source teacher and hash-preserved nested pack remain the quality path.

The controlling plan is
[`plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md`](plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md),
with the current handoff at
[`experiments/deepseek-v4-flash-reap-xpu-b70/HANDOFF.md`](experiments/deepseek-v4-flash-reap-xpu-b70/HANDOFF.md).
The user explicitly authorized the frozen K160 download on 2026-07-13. It is
now complete, cryptographically verified, and promoted to
`/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/current-k160`. The official-source
transfer was started, then paused without a completed weight shard so the
runnable K160 could take priority; it remains resumable later for teacher
evidence. The nonspeculative lane has crossed 40 tok/s, so speculation is now
permitted as a separate measured lane. It must retain exact target verification
and must not be mixed with the base record. The archived Qwen detail below
remains resume evidence, not an instruction to continue experimenting.

The promoted nonspeculative runtime is now vLLM `a681dbb2b` plus XPU kernels
`6522849b0` and the exact-version oneCCL 2021.17.2 size-routed, wide-epoch
runtime at `48fda4f0e`.
Persistent graph replay, native mHC, context-bounded sparse work, and direct
paged FP8 attention all pass. The current strict TP4+EP single-session record
uses split QK/LSE plus 8-by-64 tiled PV, a mutation-declared TP-only in-place
all-reduce for the 87 contiguous BF16 `[1,4096]` decode reductions, selective
W8A16 for four high-value projection families, and an exact clamp-at-10
SwiGLU plus per-128 E4M3FN quant producer for the W8A8 shared-down path. Exact
router normalization and direct M=1 routed-MoE gather raise the trustworthy
nonspeculative record to **43.766673/43.698550 tok/s** median with
`43.226357/43.186344` p10. Two further rollover suites reach
43.694210/43.667908. The same-build direct-off control is
41.991191/42.155092, so direct fusion removes 0.84-0.97 ms/token. All 48 strict
rows are cached-zero and 70 independent exact captures pass. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-direct-routed-moe-wideepoch-record.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-direct-routed-moe-wideepoch-record.md),
and LocalMaxxing approved `cmrmnp7h81nntmj01lfenydgj`. The preceding
41.733256 native-router row `cmrmjd3io1nn1mj013stqoe4b` remains superseded
speed evidence. The older
`40.1357239` LocalMaxxing row `cmrm601ig1hsmmj017npoivfd` remains historical
speed evidence, but consecutive changed-prompt testing later proved its
unmodified large-SYCL-allreduce identity was not repeatability-safe. Evidence
for the repair and promoted identity is
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-kv-repeatability-and-oneccl-allreduce-routing.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-kv-repeatability-and-oneccl-allreduce-routing.md).
The corrected `40.170350` row `cmrmebmzg1nm0mj01k30nv6vw` remains the
superseded repeatability-repair authority.
The current target-verified speed record is DSpark7 with target PIECEWISE,
private breakable draft PIECEWISE at exact M=7, a persistent sharded W2
transaction, W1-only replication, exact M=8 strided-batch compressors,
selective M=8 W8A16, MXFP4 N128, exact native M=8 router normalization, and a
guarded sharded target-argmax/native target-token rejection transaction:
**80.820052 tok/s** median with `71.669556` p10. Independent strict suite
medians are 80.820052 / 76.900178 / 78.287226 tok/s;
36/36 realistic requests are fresh and cache-zero, and four six-case exact
suites pass before, between, and after the performance suites. The unchanged
K160 target verifies all accepted tokens at M=8. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-sharded-target-argmax-record.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-sharded-target-argmax-record.md).
LocalMaxxing approved `cmrquta9905w3lg013m5vxoqx`. The preceding M=8 router
record remains approved as `cmrqp2uoa05ublg01lh6yluj8`. The preceding W8A16/N128
record remains superseded evidence at 78.288267 tok/s,
`cmrqlp9je05thlg01q4igkk0x`; the compressor record remains at 71.506808 tok/s,
`cmrql07qs05t4lg01p86jjybx`. The preceding W1-only
replication record remains superseded evidence at 67.501117 tok/s,
`cmrqjhpmz05snlg01ujiehc0u`; the persistent Markov record remains at 66.479103,
`cmrqiovsv05s6lg012d8v5nz8`. The preceding exact
QNorm-M2 + route-direct MTP1 record remains superseded evidence at 63.851301
tok/s, `cmrocpuhq029hlg01g3yzglko`.
The record's exact follow-up cycle attribution is complete. The eager Markov
sampler is the largest draft-side scope at about 10.50 ms/cycle. Isolating it
in a separate reusable graph preserves exact output but not its 83 kernels or
14/15 collective breaks and falls to 62.460903 tok/s; combining sampler and
model replay corrupts output. A fused three-stage context-WKV projection cuts
its local scope from 1.914 to 1.303 ms and passes 18/18 ordered exact canaries,
but two strict medians are only 64.269762/64.244449 tok/s. Both candidates are
default-off and no LocalMax submission was made. Evidence and the next
device-resident sampler/acceptance/commit boundary are in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-dspark-cycle-profile-and-fusion-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-dspark-cycle-profile-and-fusion-closure.md).
The ordered continuation plan is
[`plans/2026-07-16-deepseek-v4-flash-b70-100-200-tps-roadmap.md`](plans/2026-07-16-deepseek-v4-flash-b70-100-200-tps-roadmap.md).
It preserves the current record while pursuing four explicit options:
high-value target fusion, TP4 communication/cycle restructuring, deeper
target-verified speculation, and a fixed-geometry Intel SYCL/Level Zero
decoder. The fixed-M2 finite event chain is now closed before model load. It is
exact in two 40-epoch eager runs, with rank skew, and in fixed-address graph
replay, but its 5.60-5.70 ms eager saving falls to only 0.109546 ms/cycle once
the ordinary comparator is also captured. The production graph had already
removed the Python/c10d submission cost. The active path is now the Option-4
fixed-geometry decoder shell and cached real-model parity/replay corpus,
followed by exact M=4/M=8 verifier economics and held-out deeper-speculation
evaluation. The first shell artifact is complete: a 150 MiB content-addressed
real M=2 corpus captures 87 TP4 reductions and 85 MHC boundaries per rank, and
the no-model four-B70 worker passes 70/70 full fixed-address replays at a
4.209382 ms slowest-rank median. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-m2-real-cycle-corpus-and-replay.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-m2-real-cycle-corpus-and-replay.md).
The first M-width decoder-shell extension now passes its component gate while
retaining proven segmented M=2 collectives: fixed M=4 MHC saves 1.423781
ms/cycle and fixed M=8 saves 4.311293 ms/cycle, with 16 changed eager schedules
and 70/70 graph replays exact on all four cards. A single wide `[4,4096]` BF16
collective is blocked by repeatable oneCCL corruption, so its faster timing is
excluded. This is not an endpoint record or an acceptance result. Next is
guarded integration against true sequential verifier tensors, complete-cycle
economics, and the frozen held-out predictor gate. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-m4-m8-fixed-mhc-component-gate.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-m4-m8-fixed-mhc-component-gate.md).
The fresh post-portfolio eager diagnostic now attributes **17.8497 ms/cycle**
to noncollective device work versus 19.4779 ms before the promoted portfolio,
a measured 1.6283 ms reduction. Dense GEMMs remain 6.5639 ms and compact
routed MXFP4 remains the largest open kernel family at 3.9424 ms. oneCCL and
host durations remain profiler-distorted and excluded. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-mtp1-postportfolio-eager-cycle-profile.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-mtp1-postportfolio-eager-cycle-profile.md).
The subgroup-split/SLM producer is now closed by an incremental upper bound
before implementation. Its best possible all-remote comparison is only about
0.123 ms/cycle above the already-promoted route-direct path, and all-remote has
no local gate/up arithmetic for subgroup splitting to accelerate. No source,
build, service, or GPU experiment was made. The fixed-M2 producer/allreduce/
consumer upper bound then passed twice and exposed two missing device edges:
the Arc LL ring discarded incoming producer dependencies, and native MHC
needed a one-BF16 graph-visible completion witness. The guarded finite chain
passed exact eager and graph correctness, but failed its graph performance
gate at only 0.109546 ms/cycle saved. It is closed before service and is not a
speed result. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-tp4-m2-event-chain-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-tp4-m2-event-chain-closure.md),
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-tp4-m2-producer-allreduce-consumer-upper-bound.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-tp4-m2-producer-allreduce-consumer-upper-bound.md) and
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-mtp1-sg-split-incremental-upper-bound-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-mtp1-sg-split-incremental-upper-bound-closure.md).
The exact M=2 MXFP4 N32/N128 follow-up is closed without promotion. N32
regresses. N128 saves 0.247-0.283 ms per 43 routed layers in the four-card
microgate, but two strict suites reach 62.649706/63.628477 tok/s while
same-binary N64 controls span 61.205692-63.101865. The isolated improvement is
inside observed service variance and does not robustly beat the record; keep
N64 and do not submit the single above-record row. The profile's 6.580 ms dense
bucket is also decomposed into already optimized or closed families. The next
noncollective candidate must be an architectural M=2 grouped-MXFP4 change with
a measured four-card ceiling of at least 0.50 ms/cycle. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-mxfp4-policy-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-mxfp4-policy-closure.md).
The integration gate now permits a predeclared portfolio of compatible exact
micro-wins whose conservative, non-overlapping lower bounds sum to at least
`0.50 ms/cycle`; it no longer requires every component to clear that threshold
alone. The first same-binary B-A-B portfolio combined M=2 QNorm/RoPE/direct-KV
with N128 MXFP4. It was exact and directionally positive: its two strict
medians averaged 62.606843 tok/s versus 61.895036 for the control, a
`+0.711806 tok/s` crossover. Both bundle rows remained below the 63.349928
record, so M=1/N64 stays promoted and no LocalMaxxing submission was made.
Ten post-confirmation exact suites passed 10/10, all cached-zero. Do not rerun
this two-item bundle without another compatible component that materially
raises its conservative ceiling. Evidence and the admission policy are in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-subgate-portfolio-policy.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-subgate-portfolio-policy.md).
The first attempted third portfolio component is closed before service. The
old `0.470 ms` M=2 gather/shared-add estimate overlapped the unpromoted compact
scheduler and could not be added to N128. A new isolated four-card gate passes
140/140 changed graph cases per B70, including shared-buffer aliasing, but the
actual conservative incremental projections are only `+0.0038`, `+0.00007`,
`-0.0049`, and `-0.0007 ms/cycle`. Preserve XPU `5d1a72e` and vLLM
`eb4e39b4d` as default-off exact infrastructure; do not service-test it. The
frozen inventory now has no further exact, non-overlapping component with a
defensible `>=0.25 ms/cycle` incremental ceiling. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-isolated-gather-shared-add-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-isolated-gather-shared-add-closure.md).
The first architectural scheduler screen is also closed before service. A
route-compact M=2 Xe2 scheduler is exact on 84/84 changed-input card-0 cases,
but its worst valid all-remote EP route projects only 0.262 ms saved per 43
layers against the 0.50 ms gate. Favorable routes project 0.459-0.830 ms, so
the result is route-dependent and must not be promoted from an average. The
next screen must jointly remove M=2 remap, scheduling, and permuted-gather
traffic while preserving grouped expert reuse. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-compact-scheduler-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-compact-scheduler-closure.md).
The combined fixed-M2 route-direct boundary is now closed as well. An audit
invalidated the first misordered upper-bound graphs before integration; the
corrected remap -> GEMM1 -> clamped SwiGLU -> GEMM2 -> gather gate passes all
84 changed-input cases bitwise exactly. Its best 12-lane/generic-gather variant
saves 0.546-0.942 ms across 43 layers when local work exists, but only 0.414 ms
for the valid all-remote EP case, below the frozen 0.50 ms minimum. Four-lane
GEMM scheduling, direct gather, and 2/4/12-lane routed activations are preserved
losses. No service load or LocalMaxxing submission occurred. The next bounded
screen must remove a launch, led by source-direct GEMM1 folding the route map
into its first N tile. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-route-direct-boundary-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-route-direct-boundary-closure.md).
The first launch-removing follow-up is also closed before service. Fusing the
exact clamped SwiGLU calculation into GEMM2's A loader passes all 84
changed-input cases bitwise, but the GEMM2 output-N grid recomputes the same
activation for every N tile. It regresses every route with local work, with a
worst projection of `-9.133 ms` over 43 layers. Signed XPU experiment commit
`cfb0155` is preserved; do not integrate it. A deletion-only remap upper bound
is also marginal and unstable (`0.5002/0.4774 ms`). The next bounded audit is
paired gate/up production in the GEMM1 epilogue so each activated value is
formed once. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-fused-swiglu-gemm2-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-fused-swiglu-gemm2-closure.md).
That paired producer is now closed too. It passes `84/84` cases bitwise, but
the dual B payload and dual FP32 accumulator working set loses up to
`2.655 ms/43 layers` at GRF256 and `4.502 ms/43 layers` at GRF128. The
compiler reports no spill for the paired kernel, so lower occupancy and live
payload are the architectural limit. Single-workgroup and SLM-premapped remap
variants are also exact but top out at only `0.403-0.430 ms` fail-closed.
Preserve signed XPU commits `33e3ce4`, `5ea7608`, and `c069ed8`; do not service
test them. The next bounded producer design must split gate/up ownership across
subgroups and exchange rounded BF16 fragments through SLM, retaining the same
`0.50 ms` every-route gate. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-remap-and-paired-gemm1-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-remap-and-paired-gemm1-closure.md).
The exact gather/shared-output-add widening is also below the real gate. Its
real route-direct chain saves `0.535 ms/43 layers` for six-local work but only
`0.448 ms` on all-remote; an empty-routed fast path raises all-remote to
`0.470 ms` while leaving six-local at a noise-fragile `0.501 ms`. With that
fast path, literal remap deletion plus fused gather/add passes twice at
`0.538/0.527 ms`, leaving only `0.638-0.894 us/layer` for an implementation.
The upstream unique-route router is exact over 40 changing eager and 32 graph
epochs, but its best local-memory/subgroup-ballot emitter costs
`3.132 us/layer` (`0.125 ms/cycle`). The WG32/local-barrier shell costs only
`0.076 us/layer`, proving stable table construction is the blocker. Netting the
best exact emitter against the two deletion ceilings leaves only
`0.413/0.402 ms/cycle`, below the `0.50 ms` gate before downstream consumption.
Preserve signed XPU commits `820ecc5`, `4e2ce07`, `e7685b1`, `9360422`,
`579db66`, `c71bd3e`, `fdc4765`, and `70e3824`; no service test occurred. No
measured noncollective M=2 source boundary now clears the integration gate.
Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-gather-shared-add-gate.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-gather-shared-add-gate.md).
The preceding native M=2 MHC record remains approved LocalMaxxing evidence at
60.264242 tok/s, ID `cmrmvjbok1np3mj01p9il8486`.
The follow-up M=2 QNorm/KV fusion, exact M=2 in-place all-reduce, and MTP draft
local-argmax reduction are preserved exact candidates but did not independently
confirm above the record. They remain disabled; do not stack them without a new
complete-cycle performance reason. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-post-record-fusion-sweep.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-post-record-fusion-sweep.md).
Future deeper speculation must follow the freeze-before-reveal held-out policy
in [`experiments/deepseek-v4-flash-reap-xpu-b70/quality/spec-eval-contract-v1.json`](experiments/deepseek-v4-flash-reap-xpu-b70/quality/spec-eval-contract-v1.json);
the repeatedly used public 12-prompt suite is now a continuity screen, not
sufficient promotion evidence by itself.
The preceding target-verified record is row-exact attached MTP1 with a
strided-batch FP32 compressor and selective M=2 W8A16 verification:
**55.524496 tok/s** median with `52.029542` p10; independent support is
54.708889 tok/s. Twenty ordered exact captures pass, including ten after both
strict suites, and measured acceptance is 77.96%. LocalMaxxing approved
`cmrmgacdq1nmimj01i4sfqytp`. Both real compressor shapes pass 40/40 changing
eager and graph-replay comparisons on every B70. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp1-batched-compressor-record.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp1-batched-compressor-record.md).
The uncorrected
50.74/50.10 MTP1 screen is
invalid because a later replay leaked prompt text after `437`; the repair is
`VLLM_XPU_V4_COMPRESSOR_M2_ROW_EXACT=1`. Evidence and failure detail are in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp1-rowexact-record.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp1-rowexact-record.md).
The M=2 W8A16 record mechanism and four-card gates are in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp1-w8a16-m2-record.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp1-w8a16-m2-record.md).
MTP2 reuse is closed without a speed result: its initial M=3 exact gate passes,
but second-position acceptance is only about 0.5-2.2% and a realistic request
deadlocks the engine. Do not test larger repeated-single-layer widths. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp2-reuse-deadlock-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp2-reuse-deadlock-closure.md).
The gain comes from changing split FP8 QK from four 16-head/8-warp programs to
sixteen 4-head/16-warp programs; complete attention microbenchmarks improve
22-42% across short and 128-token C4/C128 shapes. The preceding 34.0671207
tok/s shared-expert-fusion result remains the matching control.
The previous 30.295 and 33.887 rows are invalid: generic scale prepacking also
transposed DeepSeek's special `wo_a` BMM scales, while its BF16 cache interpreted
them as canonical. Correcting that layout changed 77% of the first 96 greedy
tokens versus the invalid path. Corrected W8A16 is fast (`34.015` and `33.924`
tok/s) but the all-W8A16 path is rejected as a quality side lane: it matches
only 83.3% of early W8A8 greedy tokens and corrupts the frozen long
math-invariant case that W8A8 solves correctly. The promoted selective path
keeps shared-down W8A8 and passes that invariant. A later scheduler audit found
that the earlier MXFP4 N32 replay failure and N128 output changes came from an
in-kernel global-counter reset racing other workgroups. An ordered queue reset
makes both geometries bitwise exact over 40 changed graph epochs, but fixed N32
saves only 1.05 us per complete MoE layer and fixed N128 is 0.3% slower than
N64. The fix was diagnosed and explicitly reverted; keep N64. The
register-resident M=1 MHC post/pre
plus RMSNorm candidate is now closed before a server run: it introduced small
changed-state reduction drift and regressed `20.326 -> 22.427 us`, a projected
`0.179 ms/token` loss across 85 boundaries. Under the promoted selective W8A16
mix, fused FP8 output for the K4096 projections would also be unused. The
active work is therefore the ordered 87-collective producer/consumer boundary.
The prior general MHC/RMS fusion and oneCCL twoshots lanes remain preserved
losses.
The post-reboot 87-call oneCCL recording-path gate is closed. Forced recording
added only `0.051506 ms` against the mean of two exact controls, about one tenth
of the `0.50 ms` integration gate. Sequence/update-to-ring fusion is therefore
rejected; communication work must overlap or shorten the ring/consumer
critical path. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-oneccl-recording-sequence-upper-bound.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-oneccl-recording-sequence-upper-bound.md).
The first two-stream hardware upper bound passes twice, hiding `0.642` and
`0.612 ms` only when the independent MHC stream is submitted before the ring.
The next source experiment is a test-only persistent consumer waiting on
epoch-tagged per-wire readiness, with a `<=1 us` marker-tax gate and
`>=6 us/boundary` slowest-rank savings gate. The cheaper LL-threshold-8192 path
saved only `0.169 ms/87`, and ARC LL256 corrupted every sequential-replay
epoch, so neither proceeds. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-tp4-consumer-overlap-feasibility.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-tp4-consumer-overlap-feasibility.md).
Subsequent cheap gates are closed. LL workgroup geometry saved at most
`0.360 ms/87` against mean controls; exact two-round recursive doubling was
`0.0656 ms/87` slower than paired ring controls. Round-robin expert ownership
reached the intended interleaved map but failed the first changed-input replay
(`1369 -> 361 -> 1369` versus `1073 -> 437 -> 1073`), exposing a remaining
contiguous-expert assumption in packed MXFP4 state. A profiler trace confirms
87 collectives but cannot measure cross-device arrival skew because profiling
distorts and serializes the events. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-late-tp4-collective-and-placement-gates.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-late-tp4-collective-and-placement-gates.md).
The ring-readiness prerequisite passes. The default-off marker route is
bitwise exact over 24 changing epochs and adds at most `0.446 us` per boundary
against the faster paired control, below its `1 us` gate. The dependent
second-queue resident MHC consumer is rejected: its polling workgroup prevents
the ring queue from advancing, while a low-priority queue makes no progress.
The next microgate is a compact 256-thread version of the preserved in-ring
MHC post/pre boundary; require exact state and `>=6 us/boundary` savings before
a model server run. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-ring-readiness-marker-gate.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-ring-readiness-marker-gate.md).
Failure detail is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-resident-mhc-consumer-forward-progress-failure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-resident-mhc-consumer-forward-progress-failure.md).
The following compact in-ring post/pre screen is also closed. Although its
256-thread isolated boundary was bitwise exact and more than 2x faster than the
honest promoted reference, 256- and 512-thread full-model graph runs produced
nondeterministic arithmetic. Exact 87-position, alias, multi-replay, rank-skew,
and dependent-producer probes all passed; stable double buffers and an explicit
producer barrier did not repair the model. No speed suite was run. A future
retry requires captured real-model intermediate tensors. The fresh record-lane
noncollective timeline is now complete. A corrected seven-token eager trace
attributes about 6.582 ms/token to dense GEMMs, 3.479 ms/token to MXFP4 MoE,
2.890 ms/token to the MHC kernel, and 1.452 ms/token to tuned split attention.
Do not add the enclosing `mhc_post_pre_m1_out` operator duration; that
double-counted the same device work in the earlier roughly 4 ms estimate.
Exact auxiliary-stream overlap, generic C4 projection fusion, approximate
Triton compressor GEMV, MHC geometry, and fixed MXFP4 N32/N128 have all failed
their hardware or full-model gates. The same-hour paired control remains
40.023086 tok/s. The next server-scale candidate must first demonstrate at
least 0.50 ms/token on an exact real-model producer/consumer gate, most likely
an exact heterogeneous attention prologue or a different large boundary. The
former compact-ring prerequisite is now complete: one real M=1 token captured
692 tensors (571,072,236 bytes; aggregate SHA-256
`6f8b7b9e7a1c78cc7a2005e2d92d292a80811405725dc43e190526e1be5a59eb`),
including all 87 reductions, all 85 MHC post/pre calls, the final post, and 42
real alias boundaries. The compact candidate is bitwise exact against that
corpus in eager mode and over eight graph replays. Full-model observers then
isolated the former corruption to a missing post-kernel graph-visible
completion edge in the direct oneCCL hook: one BF16 post-kernel read makes six
alternating requests exact. The repaired path is nevertheless closed because
it reaches only 34.708355 tok/s, 13.28% below the record, and changes all 12
strict-suite hashes. Do not retune or reintegrate this boundary. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-compact-ring-mhc-post-pre-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-compact-ring-mhc-post-pre-closure.md)
and
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-record-lane-noncollective-gates.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-record-lane-noncollective-gates.md)
and
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-real-mhc-capture-and-graph-fence-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-real-mhc-capture-and-graph-fence-closure.md).
The subsequent TP4 rank-arrival probe is measurement-closed. Its same-device
elapsed-clock design avoided invalid raw cross-GPU timestamp comparisons and
completed exact all-reduce gates, but every LL256 marker sample timed out,
including self, and some clock calibrations exceeded the 2% validity gate. No
full-model run, skew claim, speed claim, or LocalMax submission followed. Both
runtime patches are preserved in experiment/revert history and production
source is restored. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-tp4-rank-arrival-trace-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-tp4-rank-arrival-trace-closure.md).
The next exact noncollective candidate is also closed. A native M=1 dual
Q1024/KV512 RMSNorm operator matches Triton's reduction order and passes
160/160 changing eager cases plus 32/32 changing graph replays across four
B70s. Although isolated timing projected 0.893-1.290 ms/token saved, paired
full-model testing regressed: 39.9928 and 39.9174 tok/s with the flag on versus
40.0950 for the same-commit flag-off control. Keep vLLM `d8d7cf198` and XPU
kernels `ef307a8` as default-off evidence; do not substitute a standalone
graph node again. The next candidate must remove the WQ_B producer boundary
with Q normalization/RoPE/KV insertion and clear an exact real-model gate.
See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-native-dual-rmsnorm-graph-loss.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-native-dual-rmsnorm-graph-loss.md).
The following producer/consumer fusion succeeds. One M=1 Triton program now
performs Q RMSNorm/RoPE and direct UE8M0 FP8 KV-cache insertion while retaining
the old BF16 KV rounding point internally. It removes one graph node and the
temporary KV row. Four-card gates pass 160/160 changed eager cases and 32/32
graph replays bit-for-bit; the isolated boundary is 2.02-2.08x faster. Two
strict suites reach 40.1357/40.1037 tok/s, both above the old public record,
and LocalMaxxing approved `cmrm601ig1hsmmj017npoivfd`. Keep this fusion on and
continue into the preceding WQ_B projection epilogue. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-fused-qnorm-rope-kv-insert-record.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-fused-qnorm-rope-kv-insert-record.md).
The attempted WQ_B extension is now closed before model integration. A padded
M16 DPAS proof was 8.13x slower than oneDNN. A true-M1 subgroup proof reaches
23.559-23.700 us across the four B70s, but it is not bitwise exact and its fast
geometry spreads each 512-wide head across workgroups. The topology capable of
head-wide in-kernel normalization already costs 53.330-53.644 us for projection
alone, so it cannot clear the 11.63 us/layer complete-boundary gate. Preserve
XPU-kernel commit `de979b9` as a benchmark proof and do not connect it to the
model. The next bounded lane is the attached one-layer MTP, kept separate from
the 40.135724 tok/s nonspeculative record. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-wqb-m1-producer-fusion-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-wqb-m1-producer-fusion-closure.md).
TP2+DP2+EP4 has been recovered for correctness, localizing its stall to a
oneCCL fast-SYCL switch cycle between disjoint TP and crossed DP communicators.
All safe fallbacks are performance-closed: the best fresh screen is only
`2.495917 tok/s`, so this topology must not displace the TP4 lane without a
communicator-scoped fast-SYCL or dedicated fused DPEP transport. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-14-tp2-dp2-dpep-recovery.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-14-tp2-dp2-dpep-recovery.md).
The 40 tok/s base gate is now cleared. Speculation may proceed only as a
separate exact target-verified lane. Detailed history is in the lane handoff and
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-14-xpu-graph-recovery-and-tp4-profile.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-14-xpu-graph-recovery-and-tp4-profile.md).

### Archived Qwen3.6 27B lane detail

- [Controlling requirements and execution plan](plans/2026-07-12-qwen27-tp1-max-speed-requirements-and-execution.md)
- [Archived experiment workspace](experiments/qwen27-dflash-sycl-b70/README.md)
- [Initial Q4_0 and speculation diagnostic](experiments/qwen27-dflash-sycl-b70/notes/2026-07-12-initial-dflash-mtp-benchmark.md)
- [Current MMVQ dispatch-fix result](experiments/qwen27-dflash-sycl-b70/notes/2026-07-12-mmvq-dispatch-fix.md)
- [Native DFlash draft-KV correctness isolation and first >68 result](notes/2026-07-13-qwen36-native-dflash-sycl-fa-isolation.md)
- [Prior promoted vLLM result packet](results/qwen36-27b-autoround-int4-b70/README.md)

The target product is one B70. The intended route combines persistent cached
development workers, B70-native offline weight packs, full useful device
replay/fusion, true multi-row Xe2 verification, and the fastest measured
target-verified MTP/DFlash policy. The main engineering target is a strict
quality-valid result above `100 tok/s` on the fixed realistic suite, with
higher workload-specific code throughput where DFlash acceptance supports it.

Phase 0 implementation now has direct MMVQ rows 1-17 correctness at 34/34,
strict graph-off medians of `25.783 tok/s` no-spec and `47.244 tok/s` MTP3,
and four independent MTP3 calibration medians of `47.976-49.708 tok/s` with
all cold/cached-zero gates passing. Mixed-suite DFlash5 is closed as a global
policy at `11.505 tok/s`; preserve long DFlash for targeted code/adaptive work.
The guarded persistent executable-graph cache now achieves exact direct replay
(381/384 hits) and deterministic output parity, but strict no-spec throughput
was unchanged (`25.848` cache versus `25.854 tok/s` graph off), so graph remains
off by default. Native event timing locates steady M=1 work at about `37.0 ms`
(`12.2-12.5 ms` host submission) and MTP3 at roughly a `42.5-45.8 ms` target
verifier plus about `9.7 ms` of draft/state graphs. Standalone MMVQ+residual
fusion hits 128 pairs/pass and saves about `0.3 ms`, but failed the 3% MTP gate.
The first block-scaled Xe2 DPAS verifier layout is closed at only `1.11x` M=4
and `1.09x` M=8 versus vector, below its `1.5x` integration gate.

The larger guarded fusion stack now reaches `50.390 tok/s` strict MTP3 versus
`48.796 tok/s` without direct GDN cache commit (`+3.27%`) across an eight-run
four-card crossover.  RMS/Q8 sharing and repaired SwiGLU/Q8 are retained behind
flags.  Two further 48-layer boundaries are closed as losses: the matched GDN
output epilogue was neutral (`25.89` versus `25.93-25.94 tok/s` M=1), while
moving sigmoid/softplus raw-gate work into GDN regressed strict MTP3 by `6.67%`
(`46.321` versus `49.632 tok/s`).  Both remain default off.  These results show
that launch-count reduction alone is insufficient when fusion enlarges the GDN
kernel or adds transcendental work to its critical path.

Direct GDN epilogue-to-Q8 output projection, direct SSM convolution cache
commit, and fused SSM convolution/QK normalization are also implemented behind
default-off flags and confirmed to match the real graph. The output-Q8 path was
only `+1.00%` in the AOT eight-run crossover (`49.978` versus `49.486 tok/s`),
below promotion threshold. Combining it with convolution cache regressed AOT
MTP3 by `1.10%` (`49.418` versus `49.969 tok/s`), and QK normalization was
neutral. Preserve these implementations and results, but do not enable them in
the production stack. JIT had overstated these gains, so AOT crossover remains
mandatory before interpreting future fusion wins.

A second Xe2 joint-N verifier briefly appeared to clear the verifier gate, but
independent review found its repeated-vector control reread weights per row,
unlike production reordered MMVQ. The corrected exact-production comparator,
including activation quantization and joint reduction, measured only `1.407x`
and `1.374x` on two critical M=4 shapes; a `1.662x` down-projection case missed
correctness. M=8 square passed at `1.925x`, but is not the MTP3 floor. Runtime
integration is therefore closed; no verifier-v2 dispatch flag was added.

Fresh strict MTP3 cycle accounting measures `2.788` emitted tokens per cycle
at `59.64%` proposal acceptance. The M=4 target verifier is `45.646 ms`
(`80.3%`), aggregate draft preparation `9.700 ms` (`17.1%`), and everything
else only `1.566 ms`, for `56.848 ms` accounted. At current acceptance, 68
tok/s requires a `41.00 ms` cycle and 100 tok/s a `27.88 ms` cycle; even
deleting all draft cost reaches only about `59.1 tok/s`. Per-op device timing
attributes `5.43 ms` of the M=4 penalty to projections, but an explicit Xe2
SIMD4 DP4A variant was only `1.004-1.012x` versus the exact compiler-optimized
production kernel. Crossing 68 now requires materially higher accepted tokens
per cycle (roughly `>=3.1`) as well as device-resident MTP staging; generic
launch fusion and another multi-column loop rewrite are closed.

Focused policy validation (`p_min 0.025-0.80` plus MTP2) produced no rescue:
best strict throughput was `50.895 tok/s`, and even a hindsight per-prompt
oracle across policies was only `52.245 tok/s` median. Existing intrinsic-MTP
adapter experiments are tied to a different HF/vLLM checkpoint, lack a safe
GGUF merge path, and their best offline acceptance gain is far below what is
required. Under the fixed single-B70 Q4_0 model and mixed strict suite, the
`>68 tok/s` objective is now blocked by the combination of Q4 weight bandwidth,
M=4 verifier time, and MTP3's four-token ceiling. Meaningful continuation
requires at least one scope change: a compatible substantially better draft,
lower-bit/reduced-weight target, or a context-owned device-unrolled MTP engine
plus verifier below `29.8 ms`; current safe optimizations cannot meet 68.

The context-owned device-resident MTP3 phase-one path is now implemented and
correct: persistent candidate/`h_nextn` staging, ordered same-device input
copies, a fixed three-step submission loop, and a poisoned-host parity/lifetime
test all pass. A SYCL top-k leading scratch entry initially collapsed
acceptance; selecting the exact production-equivalent candidate restored normal
acceptance. The strict cold suite nevertheless measured only `50.164 tok/s`
median with all gates passing, so host-boundary removal alone is closed as a
speed lane. The serialized draft graphs still execute and the `45.646 ms` M=4
target verifier remains the dominant blocker.

Native DFlash is no longer rejected based on the earlier near-zero-acceptance
result. The failure was caused by using Q8_0 for the native DFlash draft KV
cache, not by DFlash weights, Q4 quantization, or flash attention itself. The
missing controlled run—FA enabled with F16 draft KV—restored `100/106`
acceptance (`94.3%`) and `73.47 tok/s`. The earlier Q8_0 draft-KV run managed
only `7/470`, so quantized draft KV is prohibited until its numerical/backend
failure is fixed. A focused 12-case D=128/GQA4/iSWA/sparse-mask backend test
found Q8-K SYCL/CPU parity (NMSE below `6.6e-6`, no argmax mismatches over 960
rows), so current evidence favors DFlash model sensitivity to Q8 K-cache
quantization rather than a generic FA kernel error. The existing Q4_K_M draft likewise recovered to
`104/115` acceptance and `74.01 tok/s`, proving that the original Q4 result was
not ordinary quantization damage. This is the first valid local lane above the
68 tok/s milestone, but it is workload-specific rather than a production
promotion: native Q8 DFlash5 reached only `40.203 tok/s` median on the strict
12-prompt mixed suite.

Complete native DFlash timing now accounts for the mixed-workload cycle. At
`n_max=5`, steady state is about `58.7 ms` target width-6 verification,
`10.0 ms` DFlash block decode/sampling, `1.0 ms` feature injection, and
`0.3-1.2 ms` acceptance/commit: roughly `70-71 ms` total. The measured primary
blocker is therefore the generic small-M target verifier. The next decisive
work is an offline-packed Xe2 DPAS/XMX verifier plus projection fusion; generic
configuration sweeps and another global DFlash rejection are closed.

The production Xe2 width-6 verifier now covers 130 Q4_0 gate/up tensors plus 57
Q4_0 down tensors. Same-layer gate/up shares one activation quantization and
one dual-matrix ESIMD submission; down consumes canonical Q8_1 metadata, which
reduced its real shadow error to `1.01e-7`. The guarded BMG-native mirrors
preserve target-verifier semantics while materially reducing small-M cost. The
initial integrated kernel returned all zeros because the host packer
numerically converted a half-precision scale object into the raw
`ggml_fp16_t` storage type; copying the two representation bytes fixed the
scales and reduced the real one-tensor shadow error to `0.00036323` maximum.
The first corrected BMG-AOT strict suite passed at `39.249 tok/s`, versus the
matching FA-on, target-KV8, draft-KV-F16 baseline of `37.967 tok/s` (`+3.38%`), and was
approved by LocalMaxxing as `cmriq995z0210mj01fl13xmuc`. The joint gate/up plus
down BMG-AOT successor passed at `42.641 tok/s` (`+8.64%` over that row),
with JIT support at `45.484 tok/s`. Stacking the exact GDN snapshot-cache
commit fusion then raised the strict BMG-AOT record to `44.255 tok/s`, another
`3.79%`, approved as `cmrj8s2sy02a4mj01f18hanvc`. The next independent
boundary fused the Q6_K draft vocabulary head and exact top-1 into one M=6
device operation. Its strict confirmation reached **`47.819 tok/s`**, versus
an exact AOT control of `44.221 tok/s` (`+8.14%`), and LocalMaxxing approved it
as `cmrjbx8bc02g8mj01yzz2v701`. The compact path has guarded graph identity,
lowest-ID tie semantics, and an ordinary-logit rollback/redecode path after a
read failure. Do not compare these
identities with the older `40.203 tok/s` row, which used FA off and F16 target
and draft KV. An experimental 65-tensor QKV/Q expansion was rejected after its
paired strict result failed to improve throughput and introduced larger
summation drift. The next high-value measured boundary is target-side M=6
vocabulary verification: return six exact masked greedy IDs without copying
the full `6 x 248320` logits tensor to the host, then replace its vector head
with the offline-packed Xe2 verifier if the compact boundary clears its gate.

The separate promoted two-B70 vLLM result remains durable reference evidence:
graph-safe FlashAttention plus ReplaySSM transactions reached **95.384868
tok/s median**, passed exact/repeat128/baseline-parity/1K gates, and was
approved by LocalMaxxing as `cmrh35ct50092mj01h7jgydqj`. It is not the active
target configuration.

### Protected Qwen research state

The following main-repository paths contain the committed Qwen experiment
packet and must remain discoverable even though the lane is closed:

- `experiments/qwen27-dflash-sycl-b70/`;
- `notes/2026-07-12-b70-qwen27-prior-art-research.md`;
- `patches/qwen36-27b-autoround-int4-b70/llamacpp-sycl-mmvq-ncols17-q4_0-20260712.patch`;
- `plans/2026-07-12-qwen27-dflash-sycl-single-b70-plan.md`;
- `plans/2026-07-12-qwen27-tp1-max-speed-requirements-and-execution.md`.

`/home/steve/src/llama.cpp` is also protected at base `e3546c794`. It contains
the broader Qwen verifier/fusion/speculation stack plus uncommitted trace and
QKVZAB integration work across multiple files. Its closure-time tracked binary
diff SHA-256 and scoped snapshots are recorded in the
[closure note](notes/2026-07-13-qwen27-dflash-sycl-closure.md). Preserve it,
inspect Git status before building, and do not reset or clean the tree for a
new model lane. Treat the external vLLM, XPU-kernel, oneCCL, build, cache, and
result trees as mutable research state as well.

## Paused And Bookmarked Lanes

- [DeepSeek V4 Flash uniform-K160 closed frontier](results/deepseek-v4-flash-k160-b70/README.md)
- [Gemma 4 26B A4B Q8](results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
- [MiniMax M2.7 INT4](results/minimax-m27-int4-autoround-b70/README.md)
- [Qwen3.6 35B Quark INT8](results/qwen36-35b-quark-int8-b70/README.md)
- [Qwen3.6 27B AutoRound INT4 TP2 result](results/qwen36-27b-autoround-int4-b70/HANDOFF.md)
- [All model effort packets](docs/model-effort-index.md)

These are reproducible or resumable lanes, not claims about the currently
loaded service.

## Immediate Manager Actions

1. Keep the DeepSeek lane paused. Restore the record only from the standalone
   repro and reopen research only under the explicit frontier-closeout gates.
2. Preserve the exact DeepSeek vLLM, XPU-kernel, oneCCL, patch, and result
   identities. Do not relabel later default-off experiments as the record.
3. Leave the newly started configuration and its active setup work untouched;
   it is outside this DeepSeek publication closeout.
4. Preserve `/home/steve/src/llama.cpp` as dirty Qwen research state until its
   patch snapshots are independently reviewed. Do not reset or clean it for a
   different model bring-up.
5. Continue to publish only verified new matching LocalMaxxing records after
   the cold realistic gate, complete identity capture, and correctness pass.

The detailed state formerly accumulated in this file remains available in Git
at commit `95b4ca413` (`git show 95b4ca413:CURRENT.md`).
