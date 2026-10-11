# Round 6 — packed expert decode at instruction level

CPU-only preparation for the Unsloth UD-IQ3_XXS **quantized compressed
version**. No GPU executable ran, including help/version; no device node,
server, Docker, systemd unit or port was opened. The new device exactness and
speed results are **pending**, not passed. No candidate is a runtime default.

Experts stay packed. [Packet10's budget](../packet10-kopt5/README.md) permits
dense expansion only. Two corrections from the format and census matter:
IQ2_S has **1,024 × eight-byte entries**, not 2,048 entries; IQ3_S has
**512 × four-byte entries**, requiring two lookups per eight weights.
[FORMAT.md](../../stage1/packet1b/loaders/FORMAT.md) specifies both 256-weight
blocks: 82/110 bytes, F16 block scale, four-bit subscales and explicit signs.
The actual selected experts read **949,760,000 bytes/token**, not 2.4 GB,
within the 4.951 GB planning payload. The ordinary block is 19.712 MB:
IQ2 gate + up and **IQ4_NL down**, not IQ3 down. Packet9's approximately
0.298 ms / 66 GB/s is the control evidence, not a result of this round.

## Native ISA, actually generated and read

[inspect_device.py](inspect_device.py) compiles the **unmodified packet9
Projection kernel** and all four packet11 variants. [assembly-receipt.json](assembly-receipt.json)
records commands, tool/source hashes, compressed-assembly hashes, native opcode
counts and register/spill metadata. Actual dumps and excerpts stay in ignored
`build/` and are removed after validation. Rebuild with `validate.py --keep-build`
to read `build/isa/igc-packet9/*.asm` and `build/isa-evidence/`.

Exact method, all CPU-only, installed icpx 2026.0.0 and ocloc 26.18.1:

1. `icpx -fsycl -fsycl-device-only -S -O3 ...` still rejects `IR output is not supported`; the failed command is retained.
2. `icpx -fsycl -fsycl-device-only -c -O3 -std=c++20 -fno-fast-math -ffp-contract=off -fdenormal-fp-math=ieee -I<owner-src> <kernels.cpp> -o <build/module.bc>`.
3. Bundled `llvm-spirv --spirv-ext=+all,-SPV_INTEL_runtime_aligned,-SPV_KHR_untyped_pointers <module.bc> -o <module.spv>`.
4. `IGC_ShaderDumpEnable=1 IGC_ShowFullVectorsInShaderDumps=1 IGC_DumpToCustomDir=<absolute-build-dir> ocloc compile -spirv_input -file <module.spv> -device bmg-g31 -out_dir <build/aot-dir>`.

The installed IGC rejects those two newer SPIR-V extensions when emitted;
disabling their emission retains typed pointers and the same arithmetic.
The resulting `.asm` says `.platform XE2`. This is real offline BMG-G31 ISA,
**not a capture of the eventual runtime JIT**. The exact device binary remains
the coordinator's correctness gate.

The grids occupy program constant data but are fetched through **UGM/global
memory**, using an indexed 64-bit-address load. They are not an SLM cache or
register table in the baseline. IQ2 emits `load.ugm.d64.a64 (32|M0)`; IQ3 emits
two `load.ugm.d32.a64 (32|M0)`. The dependent index/address/load chain precedes
byte unpacking. Scale broadcasts lower to indirect `r[a0.0]` register reads.
Cache residency and actual load latency cannot be read from the assembly.
No latency was measured. The forecast assumes global-table 40–200 cycles,
SLM 20–40 and shuffle 4–12, all **unverified**, not hardware specifications.

Per **eight weights per lane**, ordinary finite-scale path:

| Work | IQ2_S | IQ3_S |
| --- | ---: | ---: |
| Activation loads | 8 × 16-bit | 8 × 16-bit |
| Index/high/sign loads in native B141 | 3 byte loads | 3 byte + 1 two-byte load |
| Grid lookups | 1 × 64-bit UGM | 2 × 32-bit UGM |
| Block scale load/widen, useful per-lane average | 1/32 | 1/32 |
| Subscale load/extract/convert, useful per-lane average | 1/2 | 1/4 |
| Magnitude byte extracts / signs | 8 / 8 | 8 / 8 |
| Quant integer → FP32 conversions | 8 | 8 |
| Weight-scale multiplications | 8 | 8 |
| Activation products / accumulator adds | 8 / 8 | 8 / 8 |
| Weight/accumulator FMA | **0** | **0** |

Fractional metadata counts are useful lane work, not fractional SIMD issue:
predicated leaders still issue a subgroup instruction. BF16 activation widening
uses shift/bit reinterpretation; F16 activation and block-scale widening use
the exact software half converter, including exceptional branches. Subscale
extraction is already shared per 16/32 weights. It does not justify another
hoisting variant. A true FMA would change the rounding contract and is excluded.
There are 12 scalar MAD instructions per whole kernel in the compiler's
unsigned-division lowering for launch indexing; they do not operate on weights
or dot accumulators. A whole-file search for MAD alone gives a false alarm.

[analysis.json](analysis.json) counts native blocks **B141 + B142** of each
baseline: grid indexing/addressing, lookup and finite signed decode, excluding
activation loads, scales, accumulation, loop and reduction. These blocks run
once for each octet/lane and contain:

| Native operation | IQ2_S | IQ3_S |
| --- | ---: | ---: |
| All instructions in the selected region | 145 | 138 |
| SIMD16 issue equivalents (SIMD32 counts twice) | 225 | 237 |
| Moves, including conversions/repacking | 73 | 58 |
| Shifts + masks | 34 | 31 |
| Signs | 7 selects + 1 predicated negate | 8 selects |
| FP32 scale multiplies | 8 | 8 |

**The largest visible instruction cost is integer unpacking, register
repacking and sign selection**, alongside dependent grid loads. It is not eight
FMAs or repeated F16 conversions. This identifies an instruction-count cost;
without execution counters it does not prove which dependency dominates time.
In IQ2, 64-bit shifts split into SIMD16 halves and many short-integer moves.
The int32 pair candidate directly targets that emitted code.

All inspected kernels use a **128-GRF configuration**; this is allocation mode,
not measured occupancy or peak live registers. The baseline has no reported
GRF scratch spill, but reports predicate stores/loads IQ2 **36/43**, IQ3
**26/33**. The register IQ2 candidate reports **6,016 bytes of scratch spill**
and 2,167 estimated GRF references. Its register intent did not survive register
allocation without spilling. IQ3 register has no reported GRF spill. Pair and
pipeline have no reported GRF spill and predicate stores/loads **2/4** and
**1/2**, respectively. These are offline compiler statistics, not runtime counters.

## Three alternatives and unchanged arithmetic

[kernels.cpp](kernels.cpp) retains packet9's fused gate/up, down and ordered
weighted-sum launches, Arena ownership, bounds, alias checks and invalid-route
behavior. All timing modes use SG32, four rows/workgroup; the actual IQ4 down
kernel and weighted sum remain controls. No expert expansion is stored.

- **`register_grid`:** each SG32 lane holds 32 packed IQ2 entries or 16 IQ3
  entries. Every bank is shuffled uniformly and the destination lane selects
  its requested bank. That requires **64 32-bit shuffles per IQ2 octet**, or
  **32 per IQ3 octet**. Selecting the bank before shuffling is wrong when
  lanes request different banks. Initialization is per row/subgroup, amortized
  over K. The large IQ2 spill makes this a likely negative experiment.
- **`slm_pair`:** stage only the current grid once per workgroup (8 KiB IQ2,
  2 KiB IQ3), then synchronize. Fetch two consecutive 256-weight blocks before
  consuming either. Each lane keeps two `float8` activation groups in private
  registers. An odd last block is handled separately. Stage-copy, barrier and
  bank conflicts count in eventual timing.
- **`packed_pipeline`:** fetch one IQ2 grid or two IQ3 grids into **two uint32
  words**, with signs, shared scale and `sycl::float8` activations. Fetch block
  i+1 before consuming block i; decode the eight bytes with 32-bit shifts,
  then eight separately rounded products/adds. The last block is drained once.
  This is source software pipelining, not a guarantee of a particular load
  latency overlap on hardware.

The finite accumulation body emits **68 instructions** for the pair and
**70** for the pipeline, including eight quant conversions, 15 multiplications
and seven additions; the common successor supplies the final multiply/add.
These smaller regions exclude fetch/setup and must not be compared directly
with baseline B141+B142 as a speedup ratio. Register-grid regions include
1,591 / 391 instructions for IQ2/IQ3, including lowered shuffle/spill traffic.

[decode.hpp](decode.hpp) and [reference.hpp](reference.hpp) preserve packet9's
arithmetic: lane l visits `8*l + 256*n`, each octet in increasing j, then the
adjacent-lane tree at 1,2,4,8,16. Pair/pipeline never accumulate a second block
before the first. Special scales use the original scalar element equation,
preserving NaN/sign behavior. Split4 is tested as a secondary arithmetic
contract, not silently compared with SG32. Exact local arithmetic does not
establish full-model parity to the earlier packet2/model oracle.

## Instruction-based predictions — not measurements

[analysis.py](analysis.py) uses the native finite regions above and records
separate assumptions for the instructions outside those regions, setup,
utilization and latency. **Unverified Xe2 assumptions:** 256 vector engines,
one SIMD16 issue/engine/cycle, 1.5 GHz; SIMD32 costs two issue slots. Forecast:
`256 * 1.5 * packed_block_bytes / issue_slots`, in GB/s, times the explicitly
listed utilization range, capped at the prior ~590 GB/s stream ceiling.
No clock was queried or changed. Spills and startup are especially uncertain.

| Variant | IQ2 slots/block | IQ2 predicted GB/s | IQ3 slots/block | IQ3 predicted GB/s |
| --- | ---: | ---: | ---: | ---: |
| packet9 SG32 control | 353 | 49–76 | 365 | 64–98 |
| register grid | 1,978 | **3–7** | 706 | **27–45** |
| SLM two-block pair | 332 | **52–81** | 308 | **75–117** |
| packed int32 pair pipeline | 304 | **67–93** | 304 | **90–125** |

These are gate/up instruction scenarios, not predicted complete MoE GB/s,
measured points or full-model tok/s. The unchanged IQ4 down, queue gaps and
weighted epilogue limit complete-block gains. Timing records the full block
and all three individual stages to expose that limit. No candidate is selected
from these predictions.

## Validation and two card-3 commands

[build-receipt.json](build-receipt.json) records compiler commands, source,
fixture and binary hashes, CPU dependency checks, fresh-process repeat and
scratch cleanup. **33 Python tests; 27 hash-matched fixtures; 6,291,456 new
packed-value comparisons; 1,080 candidate row comparisons; 104 MockDevice
expert cases** pass. Inherited coverage adds 551,424 decode comparisons,
2,832 row comparisons, 200 long rows and 448 mixture checks. The 409,600
special/XS checks are an overlapping inherited count, not an extra total.

The prepared device gate has **104 cases: 26 per variant**. It checks FP32 and
BF16 bytes, varied table indices/signs/subscales, changed inputs, invalid and
duplicate expert IDs, row tails, K512/K768 pairs and odd tails, infinite/NaN
scales and split4 down. The device results remain unexecuted. Native timing
requires the matching successful exactness receipt and hashes every source,
binary and input. It uses two fresh owners per representative shape, one warmup
and 20 samples per variant, full resident expert banks and all three native
MoE events including queue gaps. Its five layer shapes include ordinary,
PLE, upgraded IQ3, QSA and head controls; at most 4,096 owner events are admitted.
Prepared down inputs omit the SiLU/product dependency, so this remains a GEMV
operator diagnostic, not a full MoE/model quality or performance claim.

After cleanup, recreate CPU build/inputs first (no GPU execution):

```bash
P=experiments/own-xpu-runtime/stage2/packet11-kopt6
nice -n 19 env OMP_NUM_THREADS=2 python3 -B "$P/validate.py" --keep-build
```

Then the coordinator, in the installed oneAPI environment and **after separate
card-3 admission**, runs these two commands once each, in order. They do not
override the host halt recorded in CURRENT.md:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B "$P/tests/device_window.py" --authorized-device-window --card 3 --output "$P/build/card3-exactness"
nice -n 19 env OMP_NUM_THREADS=2 python3 -B "$P/tests/device_timing.py" --authorized-device-window --card 3 --exactness "$P/build/card3-exactness/window.json" --output "$P/build/card3-timing"
```

The inherited cooperative watcher retains faults, refuses retries and latches
unsafe drains. Neither command starts a server. [Closeout](CLOSEOUT.md) and
[negative/pending index](DO-NOT-REPEAT.md) retain this preparation's limits.
Code is our own extension of packets 6–9. Normative grids retain ggml/llama.cpp
format-data attribution and MIT license in FORMAT.md; Intel compilers/SYCL
are platform dependencies. No external runtime kernel was copied.

## Device results — card 3, 2026-10-11 06:1x UTC (boot 13858eef): NEGATIVE

All variants bit-exact, zero kernel fault lines. Fused MoE block (19.7 MB):
experts_sg32 **0.298 ms (66 GB/s)**; register_grid 1.45 ms (13.6 GB/s; the
IQ2 variant spills 6 KB of registers); slm_pair 2.34 ms (8.4 GB/s);
packed_pipeline 2.60 ms (7.6 GB/s). The instruction-count predictions
(67-125 GB/s) were wrong by an order of magnitude for the SLM/pipeline
variants: on this device the subgroup-broadcast and SLM lookup paths cost far
more than the straightforward per-lane decode. Keep experts_sg32. Receipts:
[receipts-card3-20261011/](receipts-card3-20261011/). The expert class stays
at ~66 GB/s; the remaining levers for it are structural (two-card tensor
parallel doubling the streaming rate, and routing-aware placement), not
decode micro-optimisation.
