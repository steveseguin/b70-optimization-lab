# One candidate: Q8 attention projection through p33 split 1

The fixed-prompt class profile identified `attention` as a substantial aggregate
of GPU event durations. All 48 matching projections have **Q8_0 weights**, with
BF16 inputs/outputs and N=2560, K=6144. They are not BF16 weight matrices. The
class totals cover the whole request across layers; sums across ranks are not
end-to-end elapsed time or a demonstrated speedup.

This additive candidate selects the existing `p33.dense.segment`, variant 6,
split 1, for exactly those 48 hash-admitted names. Everything else retains the
qualified GSQ dispatch, including the existing full-vocabulary Q6 head, all
expert formats, unfused primitive graph, MTP, request reset and rollback. Both
`--gsq-packed` and `--attention-q8-p33` are required by the new entry point.
There is no dynamic fallback. Wrong shapes, types, missing/duplicate sites,
routes, FP32 side channels or incompatible Matrix bindings refuse.

The control stages four 6,528-byte packed rows into 26,112 bytes of shared local
memory per workgroup and uses one barrier. Existing p33 reads expanded signed
codes and FP32 scales directly, one subgroup per workgroup. Both use consecutive
eight-element segments per lane, stride 256, the ordered weight/input product
and accumulation, adjacent SG32 reduction and final BF16 conversion. Kernel
count remains one per projection. Removing staging and repeated half conversion
is the hypothesis; speed has not been established. Variant 7/split 4 would
change reduction order and is excluded.

Expanded storage includes original metadata: 7,296 bytes/row rather than 6,528,
or 18,677,760 bytes/tensor rather than 16,711,680. Added device storage is exactly
94,371,840 bytes total, 47,185,920 per rank at the admitted 24/24 split. Codes plus
scales read by p33 are 6,912 bytes/row, so this is not a claim of reduced global
weight traffic. The model files and tensor descriptors remain unchanged.

[Preparation](preparation.json) records the exact 48 sites, materialized source
hashes, [patch](overlay.patch), and all 40 original translation-unit dependency
sets. Only object 0 includes the changed entry-owned main and Engine helper.
All 39 other objects and every dependency remain byte-identical; no shared math,
kernel, runtime type or Matrix header changes. The new build recompiles that one
entry with the original strict FP flags and links the 39 pinned objects. Its
source closure still binds the complete control compilation. Native binaries
are never invoked by [build.py](build.py).

The first two preparation attempts refused before compilation or generated-tree
creation: an overly broad label suffix also matched HC labels, then an incorrect
parser anchor refused. Exact helpers and diagnostics remain under `lineage/`.
The final selector uses the explicit 48 labels; the explicit Matrix-binding
strengthening and its earlier preparation are also retained.

[CPU proof](evidence/cpu-proof.json) passed 2,167,843 exact checks: all 65,536
binary16 scale patterns, a synthetic full 2560×6144 matrix compared in FP32 and
BF16, 16 exceptional-scale rows and a changed-code output control. The tested
p33 lane body is extracted byte-for-byte from the selected source; the control
is the original packet6 decoder/lane reduction. No tolerance or NaN waiver is
used. This finite compiler/fixture result does not establish universal native
NaN propagation equivalence.

[Scale census](evidence/scale-census.json) authenticated both held shard
identities and raw header-prefix hashes, then read only the 48 admitted Q8
tensors. Its exact 813,185,168-byte read budget includes headers. All 23,592,960
real scale words were finite: 23,591,732 normal and 1,228 subnormal, with no
positive/negative zeros, infinities or NaNs. Each tensor has a retained digest
from the same bounded read. No complete-model scan or device work occurred.

The pending operational gate is exact baseline tokens and complete target state
on prompt 00, then each remaining arm in the same resident pair if the first
gate passes. Root owns admission and any device execution. Separate-run timing
remains provisional; compilation, CPU arithmetic and scale inspection alone do
not qualify the new full Engine. There is no new microbenchmark framework or
automatic owner restart.

Build commands use helper cores 8–15,24–31, nice 19, two math threads and a 4 GiB
address-space cap, plus the shared compiler coordinator and a 250 MiB write
forecast above the root floor. Failed attempts retain their recipes, logs and
sources. Full `nm` output, when retained, is the exact linked-symbol inventory
for reconstructing offline verification; it is not a model or runtime log.

[Native compilation](evidence/native-build.json) passed on its first attempt:
one new entry with 118 local dependencies, 39 unchanged objects, 416 source pins
and 40 total objects. Binary SHA256 is
`e83469b3a2c1781d6be6241f4c1cd0967379f15ca410c6aed55baf0831b8ac68`.
Offline extraction retains all five generic-format kernel entries and the
linked runtime/MTP symbols. Standalone entry-bitcode post-link reports the same
unresolved `fmaf`/`sqrtf` warnings as the control's isolated entry inspection;
the complete native link succeeded. This is not a native numerical test, and
the build helper never invoked the resulting executable.
