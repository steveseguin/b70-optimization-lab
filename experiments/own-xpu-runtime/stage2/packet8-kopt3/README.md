# Packet 8 — decode cost and shape dispatch, round 3

CPU-only preparation for the separate Unsloth UD-IQ3_XXS **quantized compressed
version**. No device executable was run. Earlier packets remain unchanged.
Card-3 exactness and performance are pending; no new winner, model-output
parity, speed record or production runtime is claimed.

[Round-2 receipts](../packet7-kopt2/receipts-card3-20261011/) establish the
~590 GB/s streaming ceiling, quantized GEMV decode bottleneck, useful split4
shapes, and failed two-row wide-load direction. This packet keeps SG32 and
split4 as controls. It does not reopen wide-row staging or run another ceiling
window. The source census identifies the 5.24 MB router as **F32**, despite the
round-2 README's F16 label; its measured ~288–289 GB/s remains useful evidence.

## Decode analysis

[analysis.py](analysis.py) produces [analysis.json](analysis.json). Its per-32
counts are **scalar source operations before compiler CSE/vector lowering**,
not measured executed instructions. They exclude addressing, packed-field byte
assembly in u16/u32, integer negate/select, activation widening, shuffles and
row reductions. Fractional half conversions amortize a whole 256-weight block.
All include 32 activation products and 32 accumulator additions. See the JSON
for shifts, masks, conversions, products, additions, parity and table reads.

| Grid | Dominant current cost | Table reads / 32, old → new | int→FP32 / 32, old → new | FP multiplies / 32, old → new |
| --- | --- | ---: | ---: | ---: |
| IQ2_S | Dependent 10-bit grid lookup and sign handling; decode8 already reuses each octet | 4 → 4 | 68 → 34 | 104 → 68 |
| IQ3_S | Two 9-bit grid lookups/octet, sign handling and repeated subscales | 8 → 8 | 68 → 33 | 100 → 65 |
| IQ3_XXS | Scalar fallback repeats grid fetch, parity and packed scale word per weight | 32 → 8 | 96 → 33 | 160 → 66 |
| Q3_K | Scalar fallback repeatedly extracts six-bit subscales | 0 → 0 | 64 → 34 | 96 → 66 |
| Q6_K | Two bit planes per weight; scales were already partly shared | 0 → 0 | 36 → 34 | 68 → 66 |
| IQ4_NL | Dependent nonlinear level lookup per weight | 32 → 32 | 32 → 32 | 64 → 64 |
| IQ4_XS | Six-bit subscales plus nonlinear lookup | 32 → 32 | 64 → 33 | 96 → 65 |
| Q8_0 | Byte widening and products; little decode work remains | 0 → 0 | 32 → 32 | 64 → 64 |

IQ4_XS's old column is the scalar FORMAT equation, not a prior device kernel.
IQ3_XXS, Q3_K and IQ4_XS are absent from this model's production census. The
first two retain packet-2 synthetic device fixtures; IQ4_XS is CPU format
coverage only and is not added to packet-2 or device admission.

Two format corrections matter: **IQ2_S has 1,024 packed uint64 entries** (eight
8-bit magnitudes each, 8 KiB), not 2,048; **IQ3_S has 512 packed uint32 entries**
(four 8-bit magnitudes each, 2 KiB), not four-bit stored magnitudes. IQ3_XXS is
256×uint32, 1 KiB. IQ4 has sixteen signed-byte levels. These follow the pinned
[FORMAT.md](../../stage1/packet1b/loaders/FORMAT.md) and normative local tables.

### Offline compiler evidence

[inspect_device.py](inspect_device.py) records exact commands, diagnostics,
source hashes and static whole-module opcode counts in
[assembly-receipt.json](assembly-receipt.json). Installed icpx 2026.0.0 rejects
`-fsycl -fsycl-device-only -S` with `IR output is not supported`; adding
`-emit-llvm` also failed during investigation. The supported CPU-only route is:

1. `icpx -fsycl -fsycl-device-only -c -O3 ... kernels.cpp -o build/decode-device.bc`
2. The bundled `llvm-spirv --spirv-ext=+all --spirv-text` converts that bitcode
   to inspectable SPIR-V intermediate assembly. The system `spirv-dis` is too
   old for decoration 5940; the bundled translator handles it.

The receipt verifies subgroup shuffles, shifts, masks, integer conversions,
FP multiplies/adds and no FMA/MAD. These are static module counts, including
branches and reductions, **not Xe machine ISA or instructions per 32 weights**.
IGC JIT dumps would need a device compilation window; none was invoked here.
Register counts, spills, bank conflicts and occupancy remain unmeasured. The
script regenerates the assembly under ignored `build/`; only its compact
receipt is retained after cleanup.

## New named kernels

`decode_const_sg32_v1`, `decode_slm_sg32_v1`,
`decode_const_split4_v1`, `decode_slm_split4_v1` are implemented in
[kernels.cpp](kernels.cpp), with the scalar arithmetic in
[decode.hpp](decode.hpp) and versioned [reference.hpp](reference.hpp).

- Four SG32 subgroups per 128-item work-group, **one row per subgroup**.
  Each 256-weight tile assigns eight contiguous weights to each lane, exactly
  as round 2. No full packed row is copied through SLM.
- One lane widens the block half scale, then broadcasts it. A leader for each
  16/32-weight subblock computes its scale once and broadcasts it. IQ3_XXS
  loads the sign/scale word once per 32 weights and computes parity once per
  octet. Explicit sign bytes and grid indices are read once per octet/quad.
  A block contains multiple subscales and signs; treating these as one scalar
  per 256 weights would decode the wrong model.
- Integer extraction yields signed int16 values (the values fit int8, except
  the container is deliberately wider). One quant→FP32 conversion per weight
  precedes the scale product. Sign multiplication is removed on finite IQ
  paths, preserving signed zero. Exceptional scales use the original scalar
  equation, after all collective calls, to preserve its NaN behavior.
- The constant variant uses the existing compile-time grid arrays. IQ4 levels
  live in subgroup registers and use `select_from_group`; larger codebooks
  use indexed constant reads, shared across each lane's eight outputs. They
  cannot all fit in 32 subgroup registers.
- The SLM variant stages the needed codebook **once per work-group**, then
  synchronizes before any row uses it. Its four typed local allocations
  reserve 11,280 bytes/group in total; only the current matrix's table is
  copied. The constant variant declares only 17 bytes of dummy local storage.
  SLM initialization, barriers and bank conflicts can outweigh lookup savings.
- Eight activation values per lane are prefetched into registers before
  decode. There is no whole-vector SLM copy. Tail lanes still participate in
  every subgroup collective, with safe in-range packed-block addresses.

The per-row arithmetic remains round-2 v1: lane l visits
`begin + 8*l + 256*n`, j=0..7, increasing n; adjacent lane tree at widths
1,2,4,8,16. Split4 uses the same contiguous tile boundaries and a second owned
event for `(p0+p1)+(p2+p3)`, then casts once. Empty partitions are +0.
**FMA contraction stays off.** A true FMA would remove a rounding point and
violate the requested unchanged arithmetic; the implementation uses separate
FP32 multiply and add. Compiler flags also disable fast math and FTZ.
FP32 bits and final BF16/F16 bits are both checked. Full-model parity to the
certified oracle remains a separate gate; round 2's split order already differs
from the original packet-2 order.

## Dispatch and fusion

[dispatch.json](dispatch.json), generated by [dispatch.py](dispatch.py), binds
all **1,224 production tensors**: **933 GEMV**, two existing lookups, and 289
existing control/norm/convolution tensors. Every GEMV matches exactly one of
**25 keys `(type, rows, K, expert-bank-size)`**. Non-GEMV tensors explicitly map
to their existing operation class, never accidentally to a GEMV. Unknown GEMV
keys and duplicate matches fail closed in [dispatch.hpp](dispatch.hpp).

Matched round-2 SG32/split4 event medians select the table. Equivalent keys
across sampled layers use the median of their medians. HC down and attention
output/SSM out select split4; HC up, QKV and expert projections select SG32.
The expert bank/count is important: `ffn_gate_exps` has large K relative to
rows but ten routed slots and measured evidence favors SG32. Unmeasured shapes
(such as the full output head) keep an explicitly unmeasured SG32 fallback.
`multiply_dispatched` executes this table, and the timing window compares the
whole layer's shaped dispatch against all-SG32.

New decode candidates are recorded beside each key, **not promoted without
card-3 timings**. A winner must beat the matched control including both split
passes, pass its exactness gate, and repeat in a fresh device owner/window.
Update the table with the resulting hash-bound evidence; do not select from
these forecasts. The table is operator preparation, not an enabled full-model
runtime default.

`expert_gate_up` submits both projections across all ten selected experts in
**one launch**. `expert_down` submits all ten down projections in **one launch**,
after its input is ready. Read-only activation and route allocations may be
shared by gate/up; any writable alias is rejected. The owner's in-order event
chain preserves intervening activation dependencies. Six small matrices have
one descriptor launch, with mixed raw/quantized types and independent outputs.

Timing measures **2→1 gate/up**, **1→1 down control**, and **6→1 small-family**
launches against the same candidate separately. It never fuses down with
not-yet-computed gate/up. Prepared down/small inputs make this an operator
launch diagnostic: the activation and real small-matrix readiness scheduling
are not implemented in a full layer here. There is no claimed 19→13 complete
model layer; removing six launches would save roughly 0.09–0.10 ms *if* those
inputs were ready together. Whole-sequence timing still excludes nonlinear
and recurrent operators. It reports GEMV operation count and the distinct
native event count, retaining every split pass and inclusive span.

## Predicted GB/s — unmeasured hypotheses

The source issue proxy weights an ordinary operation 1, software half widening
8, a dependent constant-table read 8 and an SLM read 3. These are uncalibrated
planning weights, not clock cycles. Retain the observed 17 µs small-operation
floor per pass; apply 35–70% of the projected instruction saving to the
remaining round-2 time and cap at 590 GB/s. New shuffle/SLM overhead can cause
regressions outside these scenarios. [analysis.json](analysis.json) records
every production test shape and the complete formula.

| Production class / example | Prediction GB/s |
| --- | ---: |
| IQ2_S routed gate/up | 55–61 |
| IQ3_S routed gate/up | 67–77 |
| IQ4_NL routed down | 69–89 |
| Q6_K QKV | 91–94 |
| Q6_K SSM out, split4 | 83–86 |
| Q8_0 HC up | 84–87 |
| Q8_0 HC down, split4 | ~101; little decode-only gain |
| F32 router | ~288; retain measured SG32 |

For otherwise unmeasured formats the JSON also supplies a **separate,
hypothetical 8 MiB, one-launch scenario**, calibrated to the IQ3_S issue proxy:
IQ2_S 68–72, IQ3_S 80–89, IQ3_XXS 72–79, Q3_K ~96, Q6_K ~148,
IQ4_NL 78–111, IQ4_XS 75–106, Q8_0 ~269 GB/s. These are not production-shape
forecasts and are especially weak for Q6/Q8, whose real shapes show much lower
rates. They exist to make the instruction model falsifiable, not to replace
missing measurements. No predicted point belongs in a result/benchmark table.

## CPU validation and coordinator commands

[build-receipt.json](build-receipt.json) records the final CPU tests, fresh
process repeat, compiler commands, dependencies, hashes and scratch cleanup.
Only the CPU executable and Python tests execute; readelf rejects device
libraries on the host executable. SYCL executables are compiled, never run,
even for help. All build/fixture/IR scratch is inside ignored `build/` and
removed by default. Builds use nice19, OMP=2 and two jobs.

CPU coverage: **18 protocol/dispatch tests**, 27 packet-2 hash-matched fixtures,
**551,424 original-format scalar decode comparisons**, **65,536 additional
IQ4_XS values** (616,960 total), **2,832 row comparisons + 200 long-row cases**,
signed zeros, subnormal/extreme/infinite/NaN scales, fresh-process repeat,
read-only sharing and three forbidden writable-alias cases. The 409,600
special-value/XS count is a subset of the decode totals, not additive.

The coordinator exactness gate has **548 cases**: 54 for each of six individual
variants and 112 for each of two grouped variants. Cases change activations,
routes, invalid IDs, row spans and tails; grouped routed fixtures exercise
shared gate/up inputs and the separate down launch. Prepared data is diagnostic
packed-row tiling from the existing local checkpoint, with full-sized expert
banks and ten selected slots; no downloads or checkpoint substitutions.

Timing is refused without the same hash-bound successful exactness receipt.
One warmup and 20 samples are recorded. Both split events **and their inclusive
span/gap** are mandatory. There are nine bounded owner sessions: two kernel
phases for each of four representative layers, then one grouped layer-0 phase.
The phase split keeps each session below the owner's 4,096-event ledger.
Each phase repeats SG32/split4 controls. Fixed order is not balanced; run a
fresh independently admitted repeat before a speed verdict. The reused packet-2
watcher retains fault journal boundaries, graceful stop, postflight and latch.

After this task deletes scratch, the coordinator first rebuilds CPU inputs:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet8-kopt3/validate.py --keep-build
```

Then, in an independently admitted card-3 window, run these **two commands**
once each, in order, with new output directories:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet8-kopt3/tests/device_window.py --authorized-device-window --card 3 --output experiments/own-xpu-runtime/stage2/packet8-kopt3/build/exactness-card3
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet8-kopt3/tests/device_timing.py --authorized-device-window --card 3 --exactness experiments/own-xpu-runtime/stage2/packet8-kopt3/build/exactness-card3/window.json --output experiments/own-xpu-runtime/stage2/packet8-kopt3/build/timing-card3
```

No server, service manager, Docker, device enumeration or device node was used
in preparation. These commands are for the coordinator and do not override
host health/ownership admission.

## Credit and handoff

Implementation extends our packets 2/6/7, the original scalar FORMAT equations
and stage-1 packet-3 owner. Normative codebook data retains its ggml/llama.cpp
MIT attribution. Concept credit at the exact pins in [IDEAS.md](../../IDEAS.md):
llama.cpp/ggml-org and ik_llama.cpp/ikawrakow for block-local unpack reuse;
exllamav3/turboderp for register-prefetch and fixed reduction scheduling;
Intel SYCL/Level Zero are platform dependencies. No external kernel code was
copied. [CPU preparation closeout](CLOSEOUT.md) and [closed directions](DO-NOT-REPEAT.md)
retain limitations and the coordinator's next measurement decision.
