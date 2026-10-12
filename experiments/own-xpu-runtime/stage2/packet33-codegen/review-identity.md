# Independent candidate identity review

Source review finds no finite-arithmetic ordering defect in the six candidate
families. Requested CPU coverage fixes have been applied and independently re-read.
Status is **finite source and CPU gates reviewed; device gates pending**. Source
hashes, candidate reasoning and findings are in `review-identity.json`.

The two expert-down lookup replacements enumerate exactly the same sixteen
signed values. They preserve half conversion, scale multiplication, BF16 input
expansion, separate product and addition, lane/tile order and tree32. The gate
candidate calls the unchanged paired private-decode body with restrict
annotations. Read-only aliasing is not itself a restrict violation; inherited
validation rejects writable binding aliases. The dense candidate is equivalent
for admitted ranges: K2560 split boundaries are multiples of256 and every
8-element lane tile stays within one scale group. Its split finish retains
`(p0+p1)+(p2+p3)`.

The generated route change batches four identical comparisons before checking
whether rank reached Top. Winning ranks necessarily scan all entries and match
exactly; only losing ranks can overshoot, and those entries do not write.
Tie-by-ID comparison is unchanged. The generated QSA literalization is guarded
by exact capacity128/budget2048/tokens1 and invokes the unchanged round2
arithmetic body. No new floating point operation, reduction order or barrier
was introduced.

The submitted row offset is restricted to a total weight extent <=UINT32_MAX
before dispatch. Validated routes bound expert/row indices, so intermediate
32-bit row arithmetic is safe. Invalid routes preserve canonical NaN output and
per-slot status. All new lambdas and the three generated round2 lambdas use
the existing capture-size guard. Generated GEMV timing retains the runtime's
own incumbent submission,200 measured repetitions, and rotated banks.

Resolved gate findings:

- Added actual K2560 expert specializations and final tree/BF16 checks.
- Added actual K2560 dense specializations, nonzero aligned ranges, split4
  partial/final tree and BF16 checks. Scales vary by group to detect incorrect
  scale indexing, including signed, normal and subnormal finite scales.
- Added all generated route stages: 12 fixtures compare output probabilities,
  IDs, gate/down tuples and status, including ties, inactive and invalid inputs.
  The host source is extracted from the actual generated device source and an
  assertion checks that the rank substitution is its only core change.

NaN policy is explicit: nonfinite mismatches are recorded, never relabeled
as equal, and remain unqualified, as in packet29. A finite `passed` result
must not be described as all-bit-pattern identity. Historical QSA stored bytes
remain a diagnostic when they differ from recomputation by the frozen current
reference core. The SYCL wrapper itself is source-reviewed; its prepared
on-card equality checks have not run.

The final CPU receipt has 3442552 required checks per process, zero required failures,
four fresh processes across GNU and Intel host compilers, matching repeat
receipts and matching required finite output fingerprints. Nonfinite diagnostic
failures are retained separately and do not count as qualified successes.

Iteration1 review: explicit vec8 loads read the same bytes without overread.
`k=lane*8+256*t` gives code starts at block offset2 or10 and final byte<=17.
The `K%8==0` guard makes all active input tiles complete; odd lengths retain
bounds-checked scalar loads. Installed SYCL `vector.hpp` loads through
element pointers, so no stronger alignment promise was introduced. The
C++20 int8 conversion gives the same signed table values. Floating point
operation and reduction order are unchanged. Four fresh CPU gate processes
pass after this edit. The device-only vector load branch is independently
source-reviewed and offline compiled; CPU gates execute its scalar fallback.

Timing review fixes are closed by inspecting regenerated source: read-only
RoPE/fixture paths resolve correctly, QSA and route failures name the actual
implementations, and excluded candidate failures make the overall receipt
false and return nonzero. Cooperative signal handling only sets a flag; it
throws between completed repetitions, then uses failure-before-teardown
reporting. This review did not execute the device timing executable.

Final extraction review caught three discarded IGC compile attempts being
counted alongside final code. The extractor now compares each dumped GEN
`.dat` against the offline ELF `.text` section: all330 selected kernels match
exactly, followed only by zero padding; the three rejected attempts remain
recorded separately. The generic native fixture is12241 static instructions,
not the30863 sum of two compile attempts. This proves offline artifact
selection, not equality with untraced device JIT code.

Payload extraction now separates cross-thread arguments from per-thread local
IDs. The table labels64-bit typed instructions precisely and avoids assigning
the expert-down reduction or conversion behavior to unrelated kernels.
Unestablished dynamic per-weight counts remain unknown. The prefix before a
first branch is not launch latency, and the generic runtime-op activation
fixture does not identify an isolated tiny-kernel fixed cost. Scratch, private
allocation and register spill metadata remain distinct: the final generic
fixture allocates32768 scratch bytes and reports21504 private bytes despite
having no GRF spill-size annotation.

The final summarizer requires200 exact repetitions and the declared stage
counts, rejects extra arms/repetitions, and includes qsa.k split4. That path
uses one incumbent event and two candidate events, as verified in the actual
original and new submission functions. K0 metadata now distinguishes device
access/compilation from kernel execution. No device executable was run during
this review.

The final table now separates unrounded GRF spill bytes, allocated scratch
bytes per hardware SIMD thread and `execution_env.private_size` bytes per
hardware SIMD thread. These sizes are not additive. Per-lane global-private
buffers remain explicitly marked `is_simt_thread` in the extracted metadata:
for R5,184 bytes/lane ×32 lanes =5888 private bytes/hardware thread. A row
containing multiple kernels reports the maximum allocation, not the sum.
