# Native DFlash widths and Xe2 verifier baseline

Date: 2026-07-13 UTC

## Purpose

Native DFlash restored valid long-block speculation once its draft K/V cache
was kept in F16. This experiment moves the verifier work from the old MTP-only
M=4/8 assumptions to the real native DFlash target widths: M=6, M=9, and M=16
for `n_max=5/8/15`.

## End-to-end width timing

Q8 native DFlash, F16 draft KV, FA enabled, graphs off, favorable merge-sort
code prompt, with cycle timing enabled:

| Verifier width | Target verify median | Draft block median | Feature/process median | Request decode | Mean emitted length |
|---:|---:|---:|---:|---:|---:|
| 6 | 58.189 ms | 10.515 ms | 1.056 ms | 76.23 tok/s | 5.57 |
| 9 | 107.626 ms | 66.467 ms | 2.301 ms | 18.23 tok/s | 8.35 |
| 16 | 138.877 ms | 69.085 ms | 2.758 ms | 58.60 tok/s | 12.85 |

The width-9/16 draft path has a second major discontinuity in addition to the
target verifier. Longer blocks cannot win merely through acceptance until both
the target and five-layer DFlash small-M projection paths use the packed Xe2
kernel family.

## Exact-production comparator extension

The experiment-only benchmark hook and comparator were extended to M=6/9/16.
The candidate remains the existing joint-2 DPAS design with eight K splits and
a global partial buffer plus second reduction kernel. It is not yet the desired
single-launch SLM design.

M=6 results, including activation quantization and every candidate submission:

| Shape KxN | Production total | DPAS total | Speedup | Max candidate/production difference | Gate |
|---|---:|---:|---:|---:|---|
| 5120x5120 | 268.043 us | 137.508 us | 1.949x | 0.0335 | pass |
| 5120x17408 | 419.077 us | 230.152 us | 1.821x | 0.0370 | pass |
| 17408x5120 | 355.127 us | 189.345 us | 1.876x | 0.0651 | correctness gate miss |

This is the first candidate to beat the exact production verifier by more than
1.5x on the real native-DFlash width-6 square and up-projection shapes. It is a
material milestone, but runtime integration remains blocked on resolving or
bounding the down-projection numerical difference and replacing the global
partial/reduction sequence.

M=9 is mixed: 2.010x square, 1.385x up, and 1.808x down with the same
approximately 0.066 down-projection difference. M=16 is only 1.08-1.10x; two
DPAS repeat-8 calls and the current global reduction design lose the expected
multi-row advantage. Width 16 needs a different register/SLM ownership mapping.

## Impact on the 100/200 objectives

At favorable DFlash5 mean length 5.57, TP1 needs the width-6 verifier below
about 44.2 ms for 100 tok/s. A projection path that is consistently near the
measured 1.8-1.95x comparator speedup is sufficient in principle, although the
whole verifier will not scale by the projection microkernel ratio alone.

For 200 tok/s, verifier latency must be about 16 ms at the same acceptance, or
longer blocks must retain high acceptance with near-flat M=9/16 execution.
That remains a packed-verifier plus TP3/TP4 objective, not a claim from this
microbenchmark.

## Next action

1. Build one ESIMD workgroup per N tile with K-split workers, SLM partials, one
   barrier, and in-kernel reduction.
2. Resolve the 17408x5120 numerical delta against exact Q4_0/Q8_1 semantics.
3. Pack gate/up only initially: 130 tensors require 6.069946 GiB. The model's
   195 FFN tensors total 9.146423 GiB, but eight down tensors are Q4_1 rather
   than Q4_0 and cannot use this ABI. Eligibility must inspect tensor type.
4. Integrate behind BMG + Q4_0/Q8_1 + M=6 guarded dispatch only after full
   projection correctness and `>=1.5x` total speed hold.

## Single-launch SLM successor

The next prototype eliminates the global partial buffer and second reduction
kernel. One workgroup owns two adjacent N16 tiles; eight ESIMD work-items split
K, stage their partials in SLM, synchronize once, and work-item zero performs
the final reduction and store.

Measured on B70 GPU3:

- M=6 5120x5120: 1.78-2.05x total across stability repeats; pass.
- M=6 5120x17408: 1.834x total; pass.
- M=6 17408x5120: 1.934x speed, but the existing 0.0651 summation-order
  difference remains; the SLM and global-partial candidates have identical
  differences, so SLM did not introduce the discrepancy.
- M=9 5120x5120: 2.153x total; pass.
- M=16 5120x5120: 1.404x; below gate because the two-repeat/register footprint
  still hits a width-16 cliff.

On the first M=6 square run, single-launch SLM reduced the candidate path from
about 103.63 us to 95.72 us and produced a 2.051x exact-production total
speedup. This establishes gate/up-only M=6 as the first guarded integration
target. Down remains disabled until its numerical gate is resolved; width 16
needs a different ownership/register design.

## Guarded runtime pack phase started

The protected llama.cpp source now contains the first disabled-by-default
runtime integration boundary:

- `ggml_tensor_extra_gpu` owns an optional per-device Xe2 M6 packed pointer,
  byte count, and layout identifier;
- cleanup releases the mirror on its owning device;
- `GGML_SYCL_XE2_Q4_M6_FFN=1` enables pack creation;
- `GGML_SYCL_XE2_Q4_M6_PACK_LIMIT=N` deterministically selects the first N
  gate/up tensors (`blk.0.gate`, `blk.0.up`, then layer order), avoiding the
  model-fit context consuming a process-global counter;
- the CPU reference packer creates the winning signed-s4, N16/K32 VNNI layout
  and uploads it before ordinary lazy reorder mutates the source;
- missing packs and all compute still fall through to unchanged production.

A one-tensor smoke test successfully created and retained the exact 50,135,040
byte mirror for `blk.0.ffn_gate.weight`:

`/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/servers/llamacpp-gpu0-port19440-20260713T031502Z.log`

This is pack-lifecycle validation, not a speed result: runtime dispatch still
uses production MMVQ. The next source step is to move the SLM M6 quantizer and
kernel behind a gate/up-only dispatch consuming this pointer, then run
per-layer and end-to-end parity before enabling more than one tensor.

## Runtime M6 integration and zero-scale pack failure

The protected llama.cpp source now has a default-off, exact-shape runtime M6
path for Q4_0 gate/up projections. It includes joint six-row Q8_1 production,
the single-launch SLM DPAS kernel, guarded dispatch, automatic production
fallback, and a one-shot shadow oracle which returns production output while
comparing the candidate.

The first integrated tests were misleadingly catastrophic. One packed tensor
appeared token-exact, but 8/32/64/130-tensor coverage progressively destroyed
DFlash acceptance. A row-level shadow comparison then showed all 104,448
candidate values were exactly zero. This was initially attributed to the JIT
server lacking `spir64_gen -device bmg-g31`; a full BMG AOT rebuild disproved
that diagnosis because its candidate rows were also zero.

Input and sentinel probes found the actual failure:

- the Q8 activation blocks and signed-INT4 packed bytes were nonzero;
- the ESIMD kernel executed and overwrote every destination value;
- every packed FP16 weight scale was zero;
- the source GGUF's first real scale was nonzero (`0x9a26`).

The packer assigned `block_q4_0::d` (a half object in this SYCL build) into a
`ggml_fp16_t` raw-bit array. That performed a numeric half-to-integer
conversion, turning small scales such as `-0.003` into integer zero. Copying
the two FP16 bytes instead preserves the representation. The pack lifecycle
also now rejects truly all-zero memory-fitting placeholders, and can recover
from the immutable production-reordered Q4_0 layout if the ordinary reorder
already occurred.

After the raw-bit fix, the real one-tensor shadow oracle measured:

- maximum absolute difference: `0.000363230705`;
- mean absolute difference: `0.0000438399847`;
- RMS difference: `0.0000557716927`;
- candidate zero count: zero in every row.

This is substantially tighter than the earlier synthetic comparator bound and
clears the real integration correctness gate.

## Full gate/up M6 result

All 130 Q4_0 gate/up tensors were packed (6.069946 GiB). On an identical
128-token merge-sort diagnostic with native DFlash5, F16 draft KV, graph off,
and cold prompt cache, the full path preserved both output hash and draft
acceptance exactly:

| Lane | Decode | Accepted/generated | Output SHA-256 |
|---|---:|---:|---|
| production control | 70.917 tok/s | 102/124 | `e17f8660d5fb42d03c464b3497edd60e4046d1252a9e707382495b150e71db3f` |
| Xe2 M6 gate/up | 73.256 tok/s | 102/124 | same |
| warm production repeat | 73.098 tok/s | 102/124 | same |
| warm Xe2 repeat | 75.808 tok/s | 102/124 | same |

The paired improvements were 3.30% and 3.71%. Cycle evidence reduced the
large target-verifier submission from roughly 57.1 ms to 54.2 ms, removing
about 2.9 ms without changing DFlash economics. These are favorable diagnostic
rows, not LocalMaxxing submissions. A BMG AOT rebuild and the fixed strict cold
realistic suite remain required for promotion.

Partial 2/8/32-tensor JIT lanes were anomalously slow when mixing the new and
ordinary projection paths and are not performance evidence. Full coverage did
not exhibit that cliff. Investigate mixed-path allocator/JIT behavior only if
partial enablement remains operationally useful; it is not on the maximum-
fusion critical path.

## Revised next action

1. Rebuild and validate the BMG AOT server with all 130 gate/up packs.
2. Run the strict realistic cold suite. Submit automatically only if it passes
   correctness and establishes a matching single-session LocalMaxxing record.
3. Extend the packed kernel to square Q/K/V/Z/A projections and the five-layer
   DFlash draft, then solve Q4_1/down semantics. Gate/up alone saves about
   2.9 ms; the current width-6 verifier still needs roughly another 10 ms to
   approach the 100 tok/s cycle target.
4. Persist the native packs to disk keyed by model checksum, tensor identity,
   layout version, and BMG target so repeated AOT experiments avoid the CPU
   repack and loader ambiguity entirely.

## Strict promotion

The corrected BMG-AOT binary reproduced the one-tensor shadow oracle exactly:
maximum absolute difference `0.000363230705`, mean `0.0000438399847`, and no
zero outputs. The fixed 12-prompt realistic cold suite then passed with every
`cached_tokens` count zero:

- AOT median tokens 1-100 after TTFT: `39.249407465376365 tok/s`;
- p10: `33.79043373802919 tok/s`;
- mean: `39.72641447564524 tok/s`;
- median full-output after TTFT: `39.7456899875183 tok/s`;
- median wall full128: `28.697359787051674 tok/s`;
- median TTFT: `1168.4687254019082 ms`.

The supporting JIT strict row measured `40.33759360913713 tok/s`, but the
lower AOT row was conservatively promoted. It improves on the matching native
DFlash baseline of approximately `37.97 tok/s` by 3.38%.

LocalMaxxing approved the AOT record as `cmriq995z0210mj01fl13xmuc`. The first
POST attempt was retained as a rate-limit failure; the retry after the API
reset returned HTTP 201 and `APPROVED`.

## QKV/Q expansion rejected

The real target inventory contains no 5120x5120 projection. The next Q4_0 M=6
families are 48 recurrent `5120x10240` QKV tensors and 17 `5120x12288`
full-attention Q tensors. Exact-production synthetic comparators were strong:
1.751x total for QKV and 2.516x for Q. Runtime pack slots 130-194 and generic
shape dispatch were added experimentally, consuming about 2.2 GiB beyond the
130 gate/up packs.

Real first-layer shadows remained dense but had larger summation differences:

- `blk.0.attn_qkv`: max `0.00626564`, mean `0.000608525`;
- `blk.3.attn_q`: max `0.0100751`, mean `0.00108002`.

A favorable merge-sort diagnostic reached `76.123 tok/s`, but changed the
output/acceptance boundary. The paired fixed realistic cold suites did not
confirm a throughput win:

| JIT lane | Median tok/s | p10 | Mean | Gate |
|---|---:|---:|---:|---|
| gate/up 130 | 39.984 | 34.269 | 40.314 | pass |
| gate/up + QKV/Q 195 | 39.621 | 34.241 | 40.344 | pass |

Therefore the 195-pack expansion is rejected for promotion. Keep the
conservative 130-pack BMG-AOT record as the production lane.

This experiment also exposed and fixed the earlier partial-pack cliff. The
on-demand reordered-weight recovery copied an eligible but pack-limit-excluded
tensor from device to host on every invocation. Checking the deterministic
pack slot before the copy removes that accidental PCIe synchronization. This
fix matters for future family isolation, but does not make QKV/Q a strict win.

The next high-value lanes are now narrower: resolve Q4_0 down-projection
semantics (57 tensors and the existing 0.065 comparator delta), optimize the
sequential Q8_0 DFlash draft cycle, and persist the proven 130 packs to disk for
faster AOT iteration. Do not promote the QKV/Q expansion without new paired
strict evidence.
