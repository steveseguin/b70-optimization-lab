# Exact CPU expert arithmetic, packet 46

This is an original AVX2 implementation of the existing arithmetic-v2 expert
body. It reads the lab's code and synthetic fixture definitions; it reads no
Strata code or model weights. It is a standalone CPU prerequisite, not an
integrated CPU-miss runtime. The live CPU reports **AMD Threadripper PRO 5955WX,
AVX2 and FMA, no AVX-512** in `/proc/cpuinfo`.

The reference is packet45's read-only `p28/expert.hpp`, `p33_candidates.hpp`,
`p39_fused.hpp` and `p42_expert.hpp`, together with the unchanged format tables
and packet17 deterministic math. Compilation records the complete local-header
closure. The gate compares both p28 and p42 gate/up lane arithmetic; packed-code
loads in p42 change representation only. Down uses p33's selected lookup
arithmetic. No expert GEMV here uses split-four: current gate/up and down use
**split=1**. A future split-four specialization must separately preserve
`(p0+p1)+(p2+p3)`; this candidate cannot stand in for one.

## Storage and decode

The release called IQ3_XXS contains **IQ2_S gate/up in 47 layers, IQ3_S gate/up in
layer 2, and IQ4_NL down**. There are no IQ3_XXS expert tensors in this scope.
An ordinary expert is 1,971,200 bytes; a layer-2 expert is 2,329,600 bytes.
Gate and up each have 640 rows of 2,560 values, with 820 or 1,100 bytes/row.
Down has 2,560 rows of 640 values at 360 bytes/row. Original packed bytes are
retained; no expanded expert copy or changed quantization is substituted.

For a value at `k`, read the original little-endian FP16 block scale `d` and
widen it exactly with `iq3::half`. Indices below are block-local, zero-based.
All float expressions are FP32 and preserve their explicit parentheses.

| Format | Block | Scale and code |
| --- | --- | --- |
| IQ2_S | 256 values / 82 B | For `i=k%256`, `q=i/8`: index `b[2+q] \| (((b[66+q/4] >> (2*(q%4))) & 3) << 8)`, signs `b[34+q]`; scale **`(d*(0.5f+float((b[74+i/32] >> (4*((i/16)%2))) & 15)))*0.25f`**. Read eight magnitudes from the existing 1,024-entry, eight-byte codebook. |
| IQ3_S | 256 values / 110 B | For `i=k%256`, two adjacent four-value indices start at `q=i/4`: `b[2+q] \| (((b[66+q/8] >> (q%8)) & 1) << 8)`. Signs `b[74+i/8]`; scale **`d*float(1+2*((b[106+i/64] >> (4*((i/32)%2))) & 15))`**. Read the existing 512-entry, four-byte codebook. |
| IQ4_NL | 32 values / 18 B | For `i=k%32`, code **`(b[2+i%16] >> (4*(i/16))) & 15`**; level table `[-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113]`; value **`d*float(level)`**. |

For finite admitted IQ2/IQ3 scales, apply the integer sign to the magnitude,
then `value=scale*float(signed_magnitude)`, matching the selected GPU kernel.
The scalar format oracle's exceptional magnitude-then-sign path must not be
algebraically replaced; this candidate instead marks nonfinite scales unsupported
at immutable-weight admission. That is not exceptional-output parity.

## Accumulation and boundaries

For every output row, initialize 32 logical lanes to positive FP32 zero. Lane
`l` processes `k=256*tile+8*l`, with increasing tiles and `j=0..7` within a tile:

```
input   = bit_cast<float>(uint32_t(bf16_input[k+j]) << 16)
product = value[k+j] * input       // FP32 multiply, rounded
sum[l]  = sum[l] + product        // separate FP32 addition, rounded
```

Down's final K=640 tile has only lanes 0..15. Lanes 16..31 do not execute
an extra addition, including addition of +0. Reduce in the unchanged adjacent
tree: widths 1, 2, 4, 8, 16; for each width update `sum[i] += sum[i+width]`
at `i=0,2*width,...`. Round the final FP32 gate and up separately to BF16 with
`iq3::bf16_bits`. Widen both; calculate the existing `ng::silu(gate)*up` using
packet17 deterministic exp and its explicitly requested FMA operations; round
that product to BF16. This is the down input. Down uses the same lane rule,
tree and final BF16 rounding. Return the complete 2,560-value down result;
the future GPU merge must retain the original ten-slot route order.

AVX2 vectors hold eight **independent logical lanes**. Each multiply/add is
explicitly `_mm256_mul_ps` / `_mm256_add_ps`; the input-only transpose changes
addresses, not values. There is no horizontal vector reduction, BLAS call,
FMA contraction in GEMV, reassociation, host expf or changed BF16 cast site.
Compiler flags disable fast math and contraction. `-mfma` permits only the
explicitly requested FMAs already present in deterministic math.

Require round-to-nearest with gradual underflow (`FTZ=0`, `DAZ=0`) on every
worker. Do not change the host's FP environment or power/memory settings to
make a test pass. Signed-zero and subnormal lane fixtures are strict raw-bit
checks. Runtime input/weight shape and immutable ownership are prerequisites.

## Exactness and exceptional boundaries

The CPU gate uses complete existing G4 fixture experts 0, 37 and 333 for both
gate/up formats. A jump-ahead LCG takes exact slices of the existing synthetic
bank, using seed `0x39c0ffee`, multiplier 1,664,525, increment 1,013,904,223,
scale bytes `00 24`, and peer bytes XOR `35` followed by restoration of scales.
No actual checkpoint bytes or additional model files are opened. Three changing
inputs rotate the existing 17-value G4 input. Compare every gate, up, activation
and down BF16 value; sampled rows also compare every FP32 lane and reduction
against packet45's current CPU oracle. Two fresh processes must have identical
test JSON and raw-output digest. No NaN payload tolerance is allowed.
The original packet28 `weights(T,2560,1,1,salt)` fixtures at salts 1 and 91
also compare all lanes and trees: their first ten FP16 scales cover signed zero,
smallest/largest half subnormals, smallest normals and finite maxima.
Thirty derived down-row cases combine those same ten finite scale values with
normal, signed-zero and BF16-subnormal input patterns. Every FP32 lane, tree
result and BF16 output is compared, including K=640's final partial tile.

The standalone candidate rejects nonfinite inputs and scales, and rejects
nonfinite results before publication. A sticky error or inactive request cannot
write caller output; invalid finite computation cannot publish partial output.
These tests establish **candidate guard behavior**, not equivalence to the
device's exceptional status/output behavior. `nonfinite_oracle_qualified=false`
is always reported. Nonfinite/control/route parity against a device window,
real-weight admission, cross-device FP32 behavior, ownership and mailbox
integration remain required before this can become an engine path.

## Throughput meaning

The bounded sustained benchmark uses **144 distinct synthetic expert slices**:
141 IQ2_S/IQ4_NL and three IQ3_S/IQ4_NL, preserving the 47:1 layer mix. Its
284,928,000-byte packed working set exceeds the CPU's 64 MiB aggregate L3.
Expert bytes remain original packed bytes; no output or activation is reused.
Every sweep changes inputs and reads all experts. One initialization sweep is
excluded; all measured sweeps include input transposition, complete gate/up,
deterministic SiLU, down, finite-result guards, output hash and OpenMP dispatch.

Report decimal **GB/s of packed expert bytes processed**, not measured DRAM
bandwidth; codebook/input/output traffic is additional. Report complete experts/s,
sample elapsed times, batches, median and p10 from five samples of at least two
seconds in each of two fresh processes. Percentiles use the actual sample at
nearest rank `ceil(p*N)`, with no interpolation; p10 of five samples is the
minimum. Only cores 4–15,20–31 and nice 19 are allowed. All 24 workers must pass
the FP-environment and allowed-affinity guards. Capture each worker's affinity
mask, and require it unchanged before each measured sweep. Inherited OpenMP
affinity settings cannot silently widen workers beyond the admitted CPU set.

The benchmark exposes enough independent expert jobs to use all workers.
Actual layer misses are at most ten and are dependent on each layer's GPU input;
this test does **not** establish those tail latencies or CPU/GPU overlap. A low
aggregate result can disprove a CPU-miss speed assumption for this implementation;
a high result cannot by itself prove the one-card engine can reach it. All-hit,
all-miss and mixed-slot scheduling remain future work. CPU testing uses host
elapsed time; the separate GPU layer window uses GPU event timing.
