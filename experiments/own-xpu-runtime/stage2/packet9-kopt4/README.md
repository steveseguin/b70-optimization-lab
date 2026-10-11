# Round 4 — routed experts and whole-layer GEMV timing

CPU preparation only. New expert kernels and both SYCL executables compile;
CPU exactness and harness checks pass. This repair ran no device binary. Card-3
exactness, speed, target-model parity and performance promotion remain pending.
Earlier packets are unchanged. This is our own code over the lab's packet2
owner/math, packet6/7 kernels and packet8 decode, with Intel SYCL dependencies.

## What the actual census and receipts say

The task description and round-3 prose contain discrepancies. The pinned
[census](../../../qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json),
[packet3 contract](../packet3/README.md) and
[round-3 raw receipt](../packet8-kopt3/receipts-card3-20261011/timing.json)
determine the implementation:

- **48 total MoE layers = 36 GDN + 12 QSA**, each with 512 experts and top 10.
- GGUF dimensions are fastest-first. Ordinary gate **and** up each have
  **640 output rows, K=2560, IQ2_S**; each reads **5,248,000 selected bytes**.
  Some layers use IQ3_S gate/up, reading 7,040,000 bytes each.
- Ordinary down has **2560 output rows, K=640, IQ4_NL**, reading **9,216,000
  selected bytes**. IQ3_S K=640 would not even be a whole 256-element block.
  The ordinary MoE block therefore reads **19,712,000 bytes**, not 14.5 MB.
  The upgraded gate/up block reads 23,296,000 bytes. Reporting GB/s over
  14.5 MB would omit one projection. All byte numerators come from the census.
- Total selected expert bytes are **949,760,000/token**, not 2.4 GB, within
  the packet3 **4,951,240,940-byte/token** payload estimate.
- Earlier routed GEMVs already batch ten experts into one projection launch:
  three projection launches, not thirty. The round-3 `groups` session actually
  contains six fused records: constant gate/up **0.1829165 ms**, constant down
  **0.2040105 ms**; SLM gate/up **0.256719 ms**, SLM down **0.178229 ms**.
  Kernel-only sessions have empty `summary.fused`. Those isolated stage times
  are not a measured complete MoE block, and differ from the ~0.136 ms best
  unfused down control. This packet times all three stages as a sequence.

[analysis.json](analysis.json) retains the raw receipt hash and corrections.
These corrections change planning, not prior measurement artifacts.

## Launches and arithmetic

[kernels.cpp](kernels.cpp) specializes the three actual expert formats. A
single three-dimensional launch indexes `(projection, selected slot, row
block)` for gate/up. Both descriptors share one device activation vector and
one device route table; IDs never return to the host. Weights stay packed.
The status/output/diagnostic allocations are separate, with checked bounds
and forbidden writable aliases. Invalid IDs, invalid spans and inactive row
tails produce canonical NaNs and route status, never out-of-bounds reads.

The candidate splits each small gate/up row's K across four SG32 subgroups in
one 128-work-item group. Each subgroup reduces with the fixed adjacent-pair
lane tree. Four FP32 partials enter **16 bytes of local memory**, synchronize,
and reduce `(p0+p1)+(p2+p3)` in that same group. There is no global scratch
reduction launch. The exact order is packet7/8's split4 order and is mirrored
in [reference.hpp](reference.hpp); contraction, fast math and FTZ remain off.
The unsplit control uses four rows per work-group and the original SG32 tree.

Down is one ten-slot launch, with a distinct BF16 input per slot. The actual
K=640 / 2560-row shape uses SG32: split4 would leave one of its four parts
empty. The API and device gate also test split4 down at K=2560, covering the
small-row geometry mentioned in the request without silently transposing the
checkpoint. Split4 is an arithmetic identity of its own; CPU equality to its
oracle does not prove parity to the original packet2/complete-model arithmetic.

A third launch reads the **rounded BF16 down results**, multiplies FP32
routing weights, and accumulates selected slots 0 through 9 in order before
one final BF16 rounding. It follows packet3's routed contribution contract.
The shared expert and its gated addition remain separate layer operations;
there is no floating atomic or reassociation. Device tests check both FP32
and BF16 results, including the mixture.

| Launch | SG32 control groups | Split4 candidate groups | Work-items/group |
| --- | ---: | ---: | ---: |
| Gate + up, ten × 640 rows × two projections | 3,200 | **12,800** | 128 |
| Down, ten × 2560 rows | **6,400** | **6,400** (SG32) | 128 |
| Ordered weighted sum, 2560 outputs | **20** | **20** | 128 |

The general formula is `matrices × slots × ceil(rows × splits / 4)`.
The alternative 640-row split4 down has 6,400 groups. Against the previously
recorded 256 compute units / 32 subslices, the candidate exposes 50 gate/up
and 25 down groups per compute unit (400 and 200 per subslice), queued over
multiple waves. Even the old control has thousands of groups: too few groups
is **not an established diagnosis**. Occupancy, register pressure and achieved
bandwidth remain unmeasured; split4 may regress. It is worth testing the
shorter per-subgroup K chain and eliminated global reduction pass directly.

## Timing and projection

[dispatch.json](dispatch.json) and its generated [header](dispatch.hpp) cover
all 1,224 tensors and 25 GEMV shape keys. Dense dispatch selects the smallest
median from round2/3 shape evidence (median of available session medians),
retaining evidence hashes and all candidates. This is diagnostic selection,
not a newly qualified production default. Unmeasured keys, including the
full output head, use explicitly unmeasured SG32 fallback.

`device_timing.py` refuses timing unless the successful packet9 exactness
receipt matches every prepared source, binary, fixture and plan hash. It runs
five shapes **twice in fresh owners**: ordinary GDN, PLE GDN, upgraded GDN,
QSA and the full 248,320-row head plus final HC mixer. Each session is bounded
at 120 seconds, watches fault signatures, stops cooperatively, and latches
failures without retry. Allocations, ownership and teardown are checked.
The largest planned session uses fewer than 1,900 of the owner's 4,096 events.

Each session records one warmup and 20 samples for both expert modes:

- The three expert launches issued back to back, with **nonempty fused
  summaries required**: stage ms, whole-block ms, GB/s over all three packed
  matrices, kernel sums and queue gaps.
- The complete layer GEMV subsequence using the dense dispatch table and new
  expert block on **one in-order queue**. Every native split pass and inclusive
  queue gap counts. Ordinary GDN has **30 native launches**, PLE GDN 33,
  upgraded GDN 28, QSA **33**, and head/final-HC 4.
- Host submit/wait time separately from device timestamps. No per-stage wait
  occurs inside a timed sequence. Status readback is outside the timed region.

**These are GEMV-only diagnostics, not dependency-correct full layers.** Fixed
packed-row tiles and prepared BF16 inputs omit nonlinear/state computations.
In particular down receives a prepared product activation; it is **not** wired
to uncomputed SiLU(gate)×up. The weighted epilogue does consume the newly
computed down output. No server, KV cache, token, prompt or model answer is
timed, and warmed diagnostics cannot become a performance headline.

The resulting receipt reports ordinary GDN and QSA ms and launch counts, then
projects a sequential two-card layer split. It uses 34 ordinary GDNs, one PLE
GDN, one upgraded GDN, 12 QSA, measured full head/final HC, and the optimistic
3,540-byte embedding/PLE-lookup floor at 590 GB/s. The layer representatives
are proxies, not a claim that every unsampled layer has identical timing.
Actual host-backed lookup latency is unmeasured. A separate row provides the
requested **48 GDN + 12 QSA hypothetical**, explicitly not this checkpoint.
Neither projection doubles bandwidth for two sequential cards. Non-GEMV
operations, KV/state and transfers are excluded.

Every projection appears beside **28.49 tok/s (35.10 ms/token)** and the actual
checkpoint's **590 GB/s payload floor: 8.392 ms/token, 119.16 tok/s reciprocal
ceiling**. These are comparisons and optimistic calculations, not new measured
decode rates. The hypothetical 60-layer scenario does not reuse the 48-layer
payload floor as its own byte count.

## Unmeasured prediction and acceptance

A deliberately falsifiable scenario assumes **100–160 GB/s** expert payload
throughput and adds three conservative 17 µs launch allowances. This is an
uncalibrated target, not an inferred speedup:

| Block | Payload | Predicted time | 590 GB/s byte floor |
| --- | ---: | ---: | ---: |
| Ordinary IQ2_S gate/up + IQ4_NL down | 19.712 MB | **0.174–0.248 ms** | 0.0334 ms |
| Upgraded IQ3_S gate/up + IQ4_NL down | 23.296 MB | **0.197–0.284 ms** | 0.0395 ms |

The measured card-3 block may be slower than either scenario. Require exact
operator output and two fresh-owner timing results before deciding the next
lever. A full-model lossless gate and realistic suite are still required for
any headline. See [closeout](CLOSEOUT.md) and [negative index](DO-NOT-REPEAT.md).

## October 11 allocation and failure-classification repair

The coordinator's **04:40:09 UTC** card-3 attempt stopped in `experts_sg32`
with `duplicate allocation label`, **zero completed cases**, no kernel fault
lines and clean teardown. Each matrix reused the pinned `packed-stage`,
`x-stage` and `route-stage` labels; readback labels also repeated. The previous
CPU tests only exercised arithmetic, so they missed this allocation path.

[The shared expert case](tests/expert_case.hpp) now scopes every allocation by
case and every matrix buffer by projection index (0 gate, 1 up, 2 down).
[MockDevice coverage](tests/mock_experts.hpp) runs that same case setup and
copy/readback path on ordinary CPU memory with reference operations. The
Arena still rejects duplicate live labels. Kernel arithmetic is unchanged.

The native receipt distinguishes an actual byte mismatch (`failure_kind:
exactness`) from an infrastructure exception. `checks` counts completed
cases, so an actual mismatch in the first case can still have `checks: 0`.
The packet-local watcher and exactness harness now record:

- Infrastructure abort: `outcome: aborted`, `error: aborted: <error>`, no
  fault latch for a clean native abort. The run stays failed and cannot admit timing.
- Byte mismatch: `outcome: exactness_failed`, with a latch even in the first case.
- Kernel-journal fault: `outcome: kernel_fault`, with the matching `fault_lines`
  saved in the latch, including faults during postflight or without native JSON.

Deadlines, interrupted windows, lost journal visibility and unsafe teardown
retain their safety latches. There is no automatic retry. Nine new Python
checks cover these boundaries and success through both variants, mocking the
child and journal; none launches a device process.

The original coordinator tree and archived false latch were moved intact to
`archive-20261011-0440/build/`. All 214 original files were rehashed after the
move; `archive-inventory.json` records their hashes, and the pre-repair build
receipt is retained there. This is preserved evidence, not validation scratch.
The fresh `validate.py` run passed and removed only its new `build/` scratch.
Device exactness and timing remain pending after this repair.

## CPU checks and coordinator commands

[build-receipt.json](build-receipt.json) records **31 Python tests**, **27
hash-matched fixtures**, **616,960 scalar decode comparisons** (551,424 regular
plus 65,536 IQ4_XS), **3,032 row comparisons**, **448 ordered mixture checks**,
and an identical fresh CPU process repeat. The special-value subset is not
added twice. Both SYCL targets compile; neither was invoked during this repair. The host
executable is checked with `readelf` for absence of device libraries.

The prepared device gate contains **28 expert-block cases**: 14 per mode,
covering three formats, BF16/F16 inputs, different gate/up weights, nontrivial
slot activations, route order, bank 511, duplicate IDs, invalid IDs, row spans,
tails, both reduction orders and weighted mixtures. Every projection's FP32
and rounded BF16 output and every route status is compared with the CPU
reference. The same case setup now runs all 28 cases end to end through `MockDevice`,
including allocation, upload, three reference operations, byte comparisons,
release and clean teardown. This catches Arena refusals before a device window;
it does not execute or qualify the SYCL kernels.

Build/test on CPU (no device runtime execution):

```bash
P=experiments/own-xpu-runtime/stage2/packet9-kopt4
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$P/validate.py"
```

The default removes its own ignored `build/` scratch. Before the coordinator's
window, rerun this CPU command with `--keep-build` to recreate hash-bound inputs
and binaries. From the repository root, with `P` set as above, the **two card-3
commands** are:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$P/tests/device_window.py" --authorized-device-window --card 3 --output "$P/build/card3-exactness"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$P/tests/device_timing.py" --authorized-device-window --card 3 --exactness "$P/build/card3-exactness/window.json" --output "$P/build/card3-timing"
```

Only the coordinator runs these after card-3 admission. They never restart a
server or retry a failed owner. Preserve device receipts and fault evidence
before deleting any coordinator build tree. No power, memory, driver, service
or resident workload changes are part of this packet.
