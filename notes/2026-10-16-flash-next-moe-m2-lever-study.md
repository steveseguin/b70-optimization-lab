# Flash-Next FP8: exact-preserving M=2 routed-MoE lever study

2026-10-16. Read-only source/evidence study; only this note was created.
No GPU, build, runtime import, model-weight read, privileged command or service
change. CPU commands used `nice -n 19 taskset -c 4-15,20-31`; Python used `-B`.
Three subagents searched evidence, certified source and qualification gates.

**Decision: retain the current routed GEMMs. No direct GEMM change has a
supported positive expected return yet.** The M=2 tile ladder was already
screened; split-K changes the answer; prefetch lost. The single next treatment
I recommend is the existing **row-copy glue patch 01**, with unchanged GEMM
configuration, in one bounded qualification experiment derived from the sealed
replay/census lineage. It is outside the routed GEMM itself and offers a small,
unproven saving. Do not describe it as solving the 14.2 ms GEMM cost. A larger
GEMM project needs the pending M=2 census and compiler evidence first.

The record stays **46.854250 tok/s**. [Today's replay](2026-10-16-flash-next-a367-record-replay.md)
returned all 12 outputs identically at **47.109780 tok/s**; its +0.5% is noise,
not another record. This study neither executes nor authorizes device work.

## What the primary evidence establishes

- [A384–A386](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-13-a384-a386-m2-remainder-decomposed-result.md):
  zeroing the routed GEMMs reduced the M=2 forward from 33.69 to 19.47 ms;
  zeroing the whole MoE block reduced it to 14.80 ms. Thus about **14.2 ms
  GEMMs**, **4.7 ms surround/shared/collectives**. These are subtraction
  diagnostics, not an exhaustive device trace or freely removable budgets.
- **61 versus 566 GB/s is not a matched A367 M=2 comparison.** The
  [September summary](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md)
  (K-loop discussion, lines 465–471) derives about 61
  from an older **M=1 offline graph replay**: 0.211 minus 0.051 ms at different
  K sizes, about 9.8 MB. The [read-only bandwidth probe](../experiments/qwen38-flash-next-fp8-b70/data/20260907-moe-weight-read-bandwidth-probe-card0.log)
  measured 566.2 GB/s strided, 415.6 with two blocks, 415.9 contiguous. This
  weakens the simple weight-layout explanation; it does not measure live M=2
  DRAM saturation or prove a latency cause.
- [A314](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-07-a314-negative-host-placed-selections-cost-nothing.md):
  predicted hot-rank parked hits fell 12.410% → 0.048%; mean speed changed
  −0.021 tok/s, four depth rows stayed exact. Moving which experts are parked
  is closed for speed on that tested identity. Migration is an explanation,
  not measured causality. [A315](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-07-a315-routing-census-and-the-window-problem.md)
  warns that its initial counters mainly measured startup dummy traffic;
  use A316's decode-window method, not those totals as decode routing.
- **The dependent-K-chain diagnosis remains a hypothesis.** The summary first
  proposes it, later questions it after GEMV/prefetch negatives; A314 restores
  it, while A384–A386 calls M=2 bandwidth-bound. These conflicting readings
  do not establish the cause. One CCS does not itself prove that independent
  programs cannot hide latency within that engine.

## Certified dispatch and the actual M=2 configuration

Read source: `/home/steve/src/vllm-flashnext-a367-clean-20261016`, certified
vLLM overlay `6d8724577dabbee5fa0bbc70c4d927c6174c8d8a`, tree
`3e8dfc5937087d186cd4a99a6bf15213be732462`;
[reconstruction evidence](../data/2026-10-16-flash-next-a367-prep/source-reconstruction.json).
Read-only SHA256 checks bind the two principal source files and selected map:

```text
fused_moe.py       c6903b8aa621e7cfd26f2572e384e1f65caa7d47d633b58d2c0cbf8713aee654
triton_moe.py      c0ef7d8b64cb18621a43a78c99e9726a244d2b6dc1db6d9d4c9fb4eb0440cfa6
selected JSON     a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be
```

Source anchors below are relative to that immutable export under
`vllm/model_executor/layers/fused_moe/`:

- `__init__.py:50–63`: explicit `get_config()`/`override_config` overrides the
  file lookup; no such override is selected by the certified launch.
- `fused_moe.py:1106–1179,1487–1507`: filename from **w2's** `(E, _, N)`;
  user `VLLM_TUNED_CONFIG_FOLDER` first, bundled configs second, dynamic
  default last. `VLLM_BATCH_INVARIANT` bypasses the tuned file; preserve the
  certified setting. Map contents are cached; flags/files must be selected
  before capture, never changed under a live graph.
- `experts/triton_moe.py:280–302`: modular `TritonExperts.apply` supplies logical
  shapes **w13=(128,1280,2560), w2=(128,2560,640)**, restoring logical E through
  `_q38_num_experts` for resident-sized placement tensors. The common lookup
  is made with original **M=2**, not W2's expanded 20 rows.
- The [certified folder](../experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32/)
  is the launch's `VLLM_TUNED_CONFIG_FOLDER`. Its filename is exactly:

```text
E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json
```

There are no separate N=1280/N=2560 phase filenames. Keys are
`1,4,8,16,32,64,128`; nearest-key selection at M=2 chooses **1**.
`fused_moe.py:1455–1459,1544–1553` suppresses phase deltas at M != 1 twice.
Consequently both launches receive:

```json
{"BLOCK_SIZE_M":16,"BLOCK_SIZE_N":64,"BLOCK_SIZE_K":128,
 "GROUP_SIZE_M":1,"SPLIT_K":1,"num_warps":8,"num_stages":4}
```

Key 1's nested `W1_CONFIG={"BLOCK_SIZE_N":32}` applies only at M=1. W13 has
A=(2,2560), top_k=10, **20 K iterations**; W2 has A=(20,640), top_k=1,
**five K iterations**, retaining the M=2-selected config. On this XPU quantized path, `SWAP_AB=false` and tensor descriptors are
disabled (`fused_moe/utils.py:655–660`, `fused_moe.py:802–811`). Both use logical
`tl.dot` shape **(16×128) @ (128×64)** with FP32 accumulation.

The historical ~17% placement regression was a missing-map bug, not new
headroom: resident E=110…128 missed E=128, with fixes required at three lookup
sites ([summary, lines 267–288](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md)).
The certified source already repairs it. Future variants must retain logical
shape attributes, placement tables and per-rank selection receipts; a rank-0
“log once” without a warning does not establish that every rank used the map.

**A genuine future M=2 override needs exact-M dispatch.** Adding map key 2
can also change M=3: equal-distance ties follow JSON insertion order, so
placing key 2 before key 4 moves M=3 from key 4 to key 2. Nested W1/W2 overrides remain inert
unless both phase guards change. Do not alter key 1 globally or use a broad
`get_config()` override and call that an M=2-only test.

## Arithmetic boundary: K-order alone is insufficient

The active block-FP8 update in `fused_moe.py:523–575` is, in ascending K:
`acc += (tl.dot(a_k,b_k) * a_scale_k) * b_scale_k`. Each dot starts its own
block partial; scales are applied **inside** the K loop. W2 applies the routed
weight in FP32, then casts to BF16 before the existing expert sum
(`:598–618`). Preserve these operations and every intervening BF16/FP8 store.

| Field or change | Effect on exactness |
| --- | --- |
| BLOCK_SIZE_K | **Arithmetic change:** 128→64 makes two separately scaled/rounded partial adds per original scale block. K traversal remaining ascending does not make this equivalent. Values above 128 are clamped to the block shape at `:851–854`, so requesting 256 does not shorten this loop. |
| Split-K / ordinary stream-K partial sums | **Arithmetic change:** independent partial accumulators plus reduction reassociate the sum, even with a deterministic final reduction. Certified launcher forces SPLIT_K=1; changing the JSON field alone cannot enable it. |
| Dot instruction shape / SWAP_AB | Preserve operand orientation, internal dot reduction and FP32 partial boundaries. A new DPAS/MMA layout can change rounding. The logical dot shape above is known; native instruction shape/sequence is **not established by Python source**. No compiler run or generated-ISA proof was made here. |
| num_warps; BLOCK_SIZE_N/M | No explicit source-level K reassociation, but compiler layout/dot lowering can change. Therefore **candidates**, not exact by construction. BM also changes routing padding; both phases must share it. BM16 is already the historical dot minimum, not two useful rows of arithmetic. |
| GROUP_SIZE_M | Only maps program IDs to independent output tiles (`:388–400`); no source-level per-output arithmetic change. Strongest geometry candidate for preserving arithmetic, but no measured positive result. Check one-owner writes, remote zeros, generated float instructions and bytes. |
| num_stages / load prefetch | Scheduling-only in intent if each original dot/scaled add stays ordered. Compiler reassociation, extra live registers and spills remain risks; existing prefetch regressed. |
| FP8 scale factoring, prescaling weights, replacement activation/quant arithmetic | Changes rounding and/or scale-reduction order; disallowed as an assumed exact shortcut. Preserve block128 max/scale/cast, native SiLU math and BF16 materialization. |

## Candidate value and prior disposition

Expected values below are engineering judgements, **not measured A367 gains**.
A positive timing scenario is not a probability estimate. For scale only,
33.69 forward + 0.89 sampling + 2.22 draft gives about 36.8 ms; saving 1 ms
at unchanged acceptance would imply about +1.3 tok/s near the record. LM-head,
other overhead, M=1 frequency and rank skew make this an optimistic proxy,
not a conversion from a measured full-cycle time.

| Candidate | Evidence / expected return / decision |
| --- | --- |
| M=2 tile config, fixed BK128 | **Low or negative expected return; no sweep recommended.** [A317/A318](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-07-a317-a318-the-w13-tile-never-applied-at-mtp1.md) already reports shared N32/64/128 at 8 warps: 260.0/**200.5**/324.6 µs; 4 warps: 296.1/332.6/819.1. W13 alone also prefers64. These graph-ladder values survive in the note; a matching raw log was not located. The separate [37-arm event sweep](../experiments/qwen38-flash-next-fp8-b70/data/20260906-moe-m2-tile-config-sweep-card0.json) was distorted by event hooks and is not the same evidence. GM-only scheduling remains unmeasured, with little obvious reuse across distinct experts; require a census-supported imbalance before spending a server on it. |
| W13/W2 launch merging | **Unknown gain, high effort/low near-term value.** They are dependent: W13 → BF16 → native fused SiLU/multiply/block quant → W2 → expert sum (`triton_moe.py:382–572`). A merged launch needs exact native arithmetic and cross-tile synchronization, or expensive duplication. One launch removed per 48 layers at the old 2.3 µs replay floor illustrates only 0.11 ms (~0.15 tok/s), not 14.2 ms. No qualified direct-merge result found. |
| Router/align glue | [Existing design](2026-10-16-flash-next-m2-glue-fusion-design.md): patch02 moves integer expert-map lookup into consumers; **0–0.2 ms** planning range (~0–0.26 tok/s), possible regression from repeated loads. New compact aligner/router has unknown return inside only part of 4.7 ms and high sentinel/order risk. Permutation is already GEMM gather/scatter; routed SiLU/quant already fused. Preserve native router softmax/ties and sorted-ID bytes. |
| Row-collective copy coalescing | **Best bounded next screen**, although outside GEMM: patch01 planning **0–0.8 ms** (~0–1.0 tok/s), unmeasured, cheap code change. Preserve both one-row reductions. Views/storage offsets can change CCL behavior; exactness is conditional. Two-row collective arithmetic is excluded by [A378/A379](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-13-a378-a379-row-wise-selector-cost-result.md). |
| Persistent kernel / whole-output stream scheduling | **Unknown, presently low expected return for substantial effort.** Assigning whole output tiles and preserving every sequential block update could be exact; dividing K and combining partials cannot. Persistence alone does not shorten 20/5 dependencies and can reduce occupancy. No retained positive prototype found. A 10–20% GEMM reduction would be 1.4–2.8 ms (~2–4 tok/s), a worthwhile *target*, not an expected result. Demand current graph census plus native-code/register evidence before implementation. |
| Software prefetch / more stages | **Negative evidence; closed as a repeat.** [Summary](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md): hand prefetch M=2 EP-like W13 0.225→0.271 ms; whole-block replay 0.211→0.264 ms. [Retained GEMV log](../experiments/qwen38-flash-next-fp8-b70/data/20260907-moe-gemv-decode-probe-card0.log): depths 1/2/4 = 94.9/104.7/105.7 µs, nonfinite-output bug. These raw numbers supersede the summary's inconsistent 95.0/95.1/95.2; neither supports another prefetch arm. |
| Split-K, swapped dot, GEMV | **Not eligible for this exact line.** A245 split-K4 gained 2.4%, then A259 failed 4K despite passing 2K; split-K8 failed 2K. Earlier neutral split-K arms were inert because launchers stripped their exports. SWAP_AB differed on 22/300 larger offline trials and changed server tokens. GEMV also had invalid values. See [final findings, summary lines375–413,491–557](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md). |
| Repack or change parked identities; repair config lookup | **No remaining measured speed value.** Strided read probe, A314 and already-fixed lookup close these specific mechanisms. Keep logical shapes as a regression guard, not a newly claimed optimization. |

[A327](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-08-a327-the-m1-tile-ladder-has-a-peak-at-64.md)
corrects “anti-predictive”: the **M=1 server** peaks at 64; offline ordering
reversed 16/32/64 but correctly predicted 128's cliff. Offline tuning is
unreliable, not reliably inverted. M=1 server negatives are not M=2 server
measurements; together with the M=2 screen they lower expected value rather
than prove that no future exact GEMM implementation can improve.

## Single next device experiment: row-copy only, GEMM unchanged

Use [patch01](../patches/flash-next-m2-glue-fusion-01-row-copy.patch), SHA256
`9a31076b55f5e6298226c9caa8c2ddf34a0ed479508512ad70be7de089c1c912`.
Select `Q38_M2_GLUE_ROW_COPY=1` in the final worker environment **before import
and capture**. It guards four ranks, BF16 contiguous `(2,2560)`, row threshold 2:
one full clone, then the original row 0 and row 1 all-reduces, replacing two row
clones and two post-copies. Keep patch02/03 off, the exact GEMM config above,
all model/placement/scale bytes, BF16 KV, native exact serial GDN, MTP1,
HC/QSA selectors, CCL twoshots/4096 and capture sizes `[1,2]` unchanged.

Preparation must create a **new separately sealed experiment**, deriving from
[a367-replay](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-replay/README.md)
and the [census sampler/lifecycle](2026-10-16-flash-next-a367-census-build.md),
with a separate candidate source export. Do not modify either sealed packet
or the certified export, repin the unchanged oracle, or run historical host
wrappers. Nothing here creates that packet or asks for approval. Each future server launch needs its own fresh hash-bound admission/window,
with inherited expiry limits; today's replay approval is not a blanket allowance. Retain RAID evidence, short local-ext4 scratch, independent
0.5s sampler/attribution thread, reserve, fault checks, one SIGINT, complete
session exit and 305 s watch; no restart/retry or resident server. The future
**server** retains record nice 0/all CPUs/OMP 1; this study's nice 19/affinity
constraint is not a benchmark treatment.

Preregister a control and candidate on **two fresh servers**, each launched
once and stopped normally, as one bounded experiment. No recapture adapter is
assumed to exist. Control failure blocks the candidate; any device fault
invokes the standing recovery rule, never an automatic retry. Before accepting
the candidate, compare both row reductions as raw bytes on all ranks, including
signed zero/cancellation/NaN payloads and graph replay; verify unchanged CCL
algorithm, row shape/stride and input immutability at row 1's 5120-byte offset.
Then run identical full clients, without tracing in timed passes:

1. **12/12 complete realistic outputs equal to the record**: full token arrays
   and UTF-8 text, prompt hashes, stop reasons, and all unchanged quality gates.
   [Suite](../repro/rapid-model-snapshots-b70/realistic-suite-v1.json) SHA256
   `0ad543d1c1f379a0b6cee88e06236e495c45eee7ba12cfcef062b6e03303e812`;
   [A367 authority](../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json)
   SHA256 `f88da9b4e041255dc36363363bd78756ebcd10418953e1ea7477d63e7b8014dc`.
   Chat, no system message, thinking off, seed 20260609, temperature 0, top_p 1,
   full 512-token cap. Each suite prompt once per attempt, no prompt/KV/response
   reuse, `cached_tokens=0`; never present repeat diagnostics as cold speed.
2. Retain the [A367 client](../experiments/qwen38-flash-next-fp8-b70/tools/run-tp4-mtp1-4352-ple-only-a367-fullgraphdet-w13n32-client.sh)
   battery assertions in the new supervisor, including quality, 16/16 repeats,
   needle and **two repeats each** of exact
   p2048/o128 and p4096/o128 at capacity 4352, cache 0 and `finish_reason=length`.
   Adapt those assertions; do not execute the old wrapper and its historical
   timeout/kill cleanup. Review the candidate source-identity delta explicitly
   while freezing all output oracles. Token-array pins are respectively:

```text
2K afffd2110812762164862b6388f054bb56696ee57b07eadce411a702c40bc714
4K 1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc
```

The [depth fixture](../data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json)
has SHA256 `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`.
Do not substitute the older lineage's 4K `c6193cc6…` or changed packet 4 fixtures.
Token equality is necessary, not proof of every intermediate bit; retain the
byte-level operator gate independently.

**Forecast/risk:** central expectation is near zero, with the prior design's
optimistic 0.8 ms implying roughly +1 tok/s (about 47.9 from the record or 48.2
from today's replay). Regression is possible. This is a low-cost rejection
screen, not a promised several-tok/s campaign. Report whole-cycle and target
forward separately, rank critical path, M=1/M=2 counts, acceptance, TTFT and
full-response wall time, plus the class-balanced 99-interval suite metric.
A flat result inside ~3% short-term drift closes this small lever immediately;
do not extend it into a grid. One control/candidate pair cannot establish
candidate fresh-server determinism or a record: a convincing mechanism and
saving would still require another fresh candidate, matched repeat timing and
the unchanged promotion attestation before any headline. Larger GEMM work
then follows actual M=2 census evidence, not another reading of 61 GB/s.
