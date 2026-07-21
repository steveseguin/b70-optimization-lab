# B70 bandwidth recovery and M=1 binding-constraint investigation

Date: **2026-07-20**

## Numbers first

### Part 1: true achievable bandwidth

| Question | Result |
|---|---:|
| Intel rating | `608 GB/s/card`, 256-bit GDDR6, effective `19.0 Gb/s/pin` (`2375 MHz` base-clock equivalent) |
| Previous probe | `527 GB/s/card` |
| New 4 GiB incompressible streaming-read probe, one card | `584.863 GB/s` median, `603.703 GB/s` best (5 s) |
| New probe, all four cards for 65 s | `576.473-582.829 GB/s` medians; `603.826 GB/s` best event |
| True sustained achievable bandwidth | **`579.045 GB/s/card`** mean event median (`575.062 GB/s/card` wall), 95.2% of rating |
| Recoverable part of `527 -> 608` | **`52.045 GB/s` sustained**, 64.3% of the gap, by kernel geometry; bursts recover `76.826 GB/s` (94.8%) |
| Remaining sustained-to-rated gap | about `28.955 GB/s/card` (`4.8%`); no clock/power/ECC lever was identified |
| Corrected weight-stream roofline | **`150.99 tok/s`** from the measured `2316.18 GB/s` four-card event-median aggregate, up from `137.55 tok/s`; absolute 2432 GB/s rated ceiling `158.54 tok/s` |

The old `527 GB/s` number was partly a microbenchmark-kernel limit, not the
memory limit. The winning standalone/default-off kernel uses one 4 GiB
allocation initialized with per-address SplitMix64 data to defeat transparent
memory compression, 16-byte vector loads, four independent accumulators,
WG128, four workgroups per compute unit, and a checksum write. On the 65-second
all-card run, wall rates were `573.017-577.377 GB/s`; event medians were
`582.829/576.473/577.806/579.072 GB/s`. Short best events on every card were
`603.738-603.826 GB/s`. A uniform-fill version can falsely report more than
`1.4 TB/s` and is explicitly rejected as a compression artifact.

### Part 2: the two decode kernels

| Kernel | Arithmetic intensity | Direct EU active/stall/idle | Memory delivery | Binding constraint | Exact-safe untried lever | Expected result |
|---|---:|---:|---:|---|---|---:|
| Routed MXFP4 N64, M=1 | `3.765 FLOP/B` useful; `7.588 element-op/B` including scale/unpack/exponent work | synthetic sustained-chain `45/15/40%` | in-model `288.7 GB/s`, **49.9% of 579.045** | **occupancy/latency-bound**; layout is a secondary hypothesis | K32xN64 tile-major weight prepack with colocated group-major E8M0 scale sidecars | conditional `2.45-2.72 ms/token`, saving **`0.77-1.03 ms/token`** if 370-410 GB/s is reached |
| Shared-down FP8 512->4096, M=1 | `2.014 FLOP/B` including block scaling | E8M0 rotating-weight proxy `12/5/83%` | in-model `150.3 GB/s`, **26.0% of 579.045** | **occupancy/latency-bound** | fixed-shape native-FP8 oneDNN JIT N-tile/workgroup specialization | conditional `0.225-0.301 ms/token`, saving **`0.299-0.375 ms/token`** if 300-400 GB/s is reached |

The highest-upside untried hypothesis is the **MXFP4 K32xN64 tile-major prepack
with colocated E8M0 scales**. It is distinct from the rejected GRF, prefetch,
N32/N128 and dense-oneDNN layout screens, and it has the largest plausible
exact-safe saving.

## ECC: inferred off locally, controller/inline, toggleable elsewhere

Intel lists the B70 as 32 GB GDDR6, 256-bit, 608 GB/s, with ECC support. Intel
also documents that an ECC-enabled B70 reports 28 GB, that disabling ECC in
Intel Graphics Software restores 32 GB, and that the setting persists across
systems. The local cards report `34,242,297,856` allocatable-state bytes
(`32656 MiB`), i.e. the full nominal 32 GiB class. That strongly indicates
**ECC is disabled on all four cards**, but direct confirmation is unavailable
because the ECC query is unsupported. ECC is not the source of the old
527 GB/s result under this evidence.

The implementation is not unavoidable GDDR6 on-die ECC: Micron's GDDR6/GDDR7
comparison explicitly lists on-die ECC as absent for GDDR6 and present for
GDDR7. A controller/inline mode is therefore the supported inference; Intel
does not publish the exact ECC code. The observed capacity
reservation is `4/32 = 12.5%`. Intel does not publish a B70-specific bandwidth
penalty. If parity traffic shares the same DRAM interface, approximately 12.5%
less useful sequential payload (about `532 GB/s` from a 608 GB/s raw stream) is
only a rough order-of-magnitude inference, not a bound or measurement; capacity
reservation does not determine the DRAM coding traffic.

The installed Linux stack cannot query or change the mode:

- `xpu-smi config` reports current/pending ECC as `N/A`;
- read-only Level Zero `zesDeviceEccAvailable`, `zesDeviceEccConfigurable` and
  `zesDeviceGetEccState` all return `ZE_RESULT_ERROR_UNSUPPORTED_FEATURE`;
- the supported path found is Intel Graphics Software on Windows. IGCL defines
  ECC state/control APIs, but IGCL is not installed here.

No setting was changed. Turning ECC off in a supported environment trades the
controller's memory error detection/correction for capacity/performance and
raises silent-corruption risk. On this host it offers **zero additional
bandwidth**, because capacity evidence indicates ECC is already off.

Sources:

- Intel B70 product specification: <https://www.intel.com/content/www/us/en/products/sku/245797/intel-arc-pro-b70-graphics/specifications.html>
- Intel 28 GB/ECC toggle support article: <https://www.intel.com/content/www/us/en/support/articles/000102907/graphics.html>
- Micron GDDR6/GDDR7 RAS comparison: <https://www.micron.com/content/dam/micron/global/public/products/product-flyer/gddr7-product-brief.pdf>
- IGCL ECC and VRAM-frequency interfaces: <https://intel.github.io/drivers.gpu.control-library/Control/api.html>

## Clock, power, temperature and throttling

The 608 GB/s rating implies `608e9 * 8 / 256 = 19.0 Gb/s/pin`, or a nominal
GDDR6 base-clock equivalent of `2375 MHz`. The current Linux Level Zero driver enumerates only GPU
and media frequency domains; it exposes no instantaneous memory-clock domain.
IGCL has `vramCurrentClockFrequency` and `vramCurrentEffectiveFrequency`, but
that runtime is absent. Therefore there is no direct instantaneous GDDR clock
readout on this installation.

The performance result still decides the rated-versus-reduced question. The
`603.826 GB/s` best event requires at least `18.870 Gb/s/pin` before protocol
overhead and is within 0.7% of the 19.0 Gb/s rating. Even the sustained
`579.045 GB/s` mean requires `18.095 Gb/s/pin`. The burst result is physically
incompatible with a materially reduced memory clock, though the direct
instantaneous clock remains unavailable. GPU core frequency held `2800 MHz`
during load.

The incompressible 65-second all-card load, followed by a warmed 15-second
privileged read-only throttle capture, found:

| Card | Average/max power | Max core / VRAM temp | Throttle samples |
|---:|---:|---:|---:|
| 0 | `174.89 / 191.28 W` | `68 / 82 C` | `15/15 Not Throttled` |
| 1 | `183.38 / 195.76 W` | `77 / 100 C` | `15/15 Not Throttled` |
| 2 | `177.67 / 192.74 W` | `74 / 90 C` | `15/15 Not Throttled` |
| 3 | `182.48 / 194.80 W` | `74 / 94 C` | `15/15 Not Throttled` |

All cards remained below the `230 W` cap. The warmest VRAM sensor reached
100 C but produced no thermal/power throttle flag; all 15 warmed samples per
card were `Not Throttled`. The stream loop measured about 3% EU active with
roughly 90% EU stall, the expected signature of a bandwidth/latency load.

`xpu-smi`'s B70 DRAM counters are not quantitatively trustworthy across cards:
two cards reported roughly 109-110% bandwidth while two reported 71-74% for
identical `~577-583 GB/s` loops. Timed logical bytes are the bandwidth
authority; the
explicit throttle reason, power, temperature and EU-state ratios are retained
as telemetry evidence.

## Routed MXFP4 N64: occupancy/latency bound

Per local expert pair (GEMM1 plus GEMM2):

- packed MXFP4 weights: `12,582,912 B`;
- E8M0 scales: `786,432 B`;
- total weight+scale stream: `13,369,344 B`;
- useful GEMM arithmetic: `50,331,648 FLOP`, or `3.765 FLOP/B`;
- scale application: `25,165,824` BF16 multiplies, yielding
  `75,497,472` scale-inclusive numeric ops or `5.647 op/B`;
- separate representation work: `25,165,824` MXFP4 element expansions and
  `786,432` exponent-build operations.

Counting useful GEMM FLOPs, scale multiplies, unpack/conversions and exponent
construction gives `101,449,728` element operations, or `7.588 op/B`.
Activation and output traffic are excluded from these weight+scale intensities.

The roofline residual model infers only `1.087 useful TFLOP/s` or `1.630 TOP/s`
including scale multiplication; these are not direct expert-count or DRAM
measurements. A synthetic sustained chain with zero weights and a rotating
three-local route measured aggregate 1 Hz EU active/stall/idle `45/15/40%`
across GEMM1, activation, GEMM2 and gather. It is a qualitative chain proxy,
not per-kernel ALU attribution. The xpu-smi memory counter is invalid for this
block-2D path (0-2% while the timed loop moved hundreds of logical GB/s), so
the trustworthy memory measure is the in-model logical `288.7 GB/s`, now
49.9% of the corrected 579.045 GB/s sustained roof.

The route-count response is the strongest classification evidence: isolated
logical bandwidth rises from `369.56` to `410.75`, `427.75`, and
`441.74 GB/s` as local experts rise from 2 to 3, 4, and 6. More independent
streams hide latency. Ordinary occupancy knobs do not solve it: GRF128 nearly
doubles time, N32/N128 fail, and prefetch-distance 3 saves only
`0.026 ms/token`.

The highest-upside untried, exactness-preserving design candidate is a load-time K32xN64 tile-major representation
that places each workgroup's packed weights and 64 E8M0 scale bytes together.
It preserves nibble values, scale values, BF16 scaling, K32 DPAS order, FP32
accumulation and BF16 rounding by reconstructing the identical CUTE B fragment
and avoiding a duplicate persistent weight copy. It is not qualified until
changing-input eager and fixed-address graph bitwise gates pass. If it moves
the profile family from 288.7 to
370-410 GB/s changes `3.485 ms/token` to `2.719-2.454 ms/token`, saving
`0.766-1.031 ms/token`. This is a conditional, low-confidence scenario rather
than a forecast. The corrected 579.045 GB/s sustained hard floor is
`1.738 ms/token`, not a forecast.

## Dense shared-down FP8: occupancy/latency bound

For one M=1, N=4096, K=512 call, the lower-bound traffic is `2,106,000 B`:
`2,097,152 B` weight, `128 B` weight scales, `512 B` activation, `16 B`
activation scales and `8192 B` output. GEMM work is `4,194,304 FLOP`; block
scaling adds about 45-49k FLOP, for approximately `2.014 FLOP/B`.

In-model performance is `0.304 TFLOP/s` including scales and `150.3 GB/s`.
The rotating-43-weight telemetry loop uses the production E8M0 scale dtype and
measured median EU active/stall/idle `12/5/83%`. Its timed logical rate was
`85.18 GB/s`; rotation intentionally defeats cache reuse and counter sampling
adds overhead, so it is a qualitative aggregate EU proxy rather than an exact
in-model per-kernel bandwidth measurement. Most EUs are idle, not busy
dequantizing. M=8 is decisive: it performs eight times the GEMM math
in slightly less profiled device time per call, reaching about 2.724 TFLOP/s. That rules
out compute or dequant as the M=1 binding limit.

The existing `[N,K]` checkpoint layout is contiguous along K, oneDNN detects
the NT view, and its primitive/JIT is already cached. Explicit contiguous and
padded `[K,N]` prepack variants were exact for shared-down but slower. The
software FP8-to-FP16 ESIMD path was 2.35x slower and bit-inexact. Therefore
neither generic prepack nor software dequant is the next lever.

The remaining exactness-preserving design candidate is a fixed M1/N4096/K512 native-FP8 oneDNN JIT
specialization with a narrower N tile and more independent N workgroups,
while retaining each output's K reduction order, 128-K scale boundaries, FP32
accumulation and BF16 rounding. A different JIT tile can still change the
generated accumulation grouping, so it requires changing-input eager and
fixed-address graph bitwise gates and likely private oneDNN JIT work; the
public wrapper has no N-tile knob. If it reaches 300-400 GB/s, it would change this family
from `0.600219` to `0.300610-0.225458 ms/token`, saving
`0.299609-0.374761 ms/token`. This is a conditional target range, not a
forecast. It is smaller than the MXFP4 hypothesis and
probably insufficient alone for the 0.50 ms integration gate.

## Evidence and safety

- structured summary:
  `../data/b70-bandwidth-recovery-investigation-20260720.json`;
- default-off stream source: `../scripts/b70-stream-bandwidth.cpp`;
- read-only Sysman source: `../scripts/b70-sysman-readonly.cpp`;
- telemetry capture: `../scripts/capture-b70-bandwidth-telemetry.py`;
- sustained kernel counter loop: `../scripts/sustain-m1-kernel-for-telemetry.py`;
- raw evidence:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/b70-bandwidth-investigation-20260720T2300Z`;
- prior endpoint/profile authority:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-m1-roofline-profile-20260719T140812Z`.

No service/model was loaded, no ECC/power/clock setting was changed, no reboot
was performed, and no LocalMaxxing action was made. A broad read-only `rg`
command inadvertently matched and displayed held-out prompt content while
searching for the old roofline number; no held-out file was modified, copied,
or used in any benchmark or conclusion. This was outside the intended audit
scope and is recorded explicitly rather than silently omitted.
