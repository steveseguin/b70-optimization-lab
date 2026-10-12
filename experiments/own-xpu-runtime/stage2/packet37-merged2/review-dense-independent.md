# Independent dense arithmetic review

Reviewed by the K2 integration agent, independently of the dense implementation.
CPU source review only; no device execution or performance claim.

Reviewed `p33_candidates.hpp`, `p33_submit.cpp`, `p33r2.cpp`,
`p33_candidate_cpu.cpp`, `p33_candidate_gates.py`, and their packet28 and
expanded-core references. No unresolved finite-arithmetic defect found.

The dense candidate visits each lane's eight-element tiles in the reference
order. Expanded Q6 uses one FP32 scale per 16 codes and Q8 one per 32 codes;
aligned eight-element tiles cannot cross either scale boundary. Starts not
aligned to 256 retain packet28's general segmentation. F32 and BF16 decode,
multiply, and add in the reference order. No reduction is delegated to an
implementation-defined group sum: lane trees use adjacent additions and
split4 ends with `(p0+p1)+(p2+p3)` before BF16 rounding.

All actual runtime K families are instantiated: 320, 640, 2560, 6144 and
10240. Q6 excludes 320 and 640 because neither is a complete Q6 block; this
is a layout constraint, not an untested admitted kernel. Q8/F32/BF16 cover
all five. Arithmetic variants 6/7 map quantized dense to split1/split4;
0/4 do the same for F32/BF16. The binding path inherits packet28's size,
alignment, alias, shape and variant validation. The additional 32-bit offset
limit is checked before issue. Device split4 scratch uses eight floats per
logical row, and its finalizer reads the four populated first-projection slots.

The gate compares each runtime class at all supported formats, both splits,
lane sums, trees, final rows, BF16 output, odd tails, unaligned intervals and
empty intervals against the reference expanded core. Two host compilers each
run twice in fresh processes. Finite hashes are compared across compilers.
Nonfinite diagnostics retain raw bit mismatches and explicitly remain
unqualified under the inherited packet29 policy; no NaN tolerance is used to
turn those diagnostics into an exactness pass.

The QSA specialization substitutes only validated compile-time shape constants
into the unchanged round2 body. Runtime shapes outside its fixed 128/2048/1
case retain that body's dynamic path. The CPU gate also checks three-token
shape specialization as arithmetic evidence, while K1 exercises the linked
runtime wrapper. Device equivalence, compiler device lowering, and actual K2
measurements remain coordinator gates.

## Final source refresh

Re-reviewed the frozen final files after the host-only OpenMP change and
QSA-only entry-point narrowing. The host loop uses at most two threads only
when there are at least 64 rows. Each row writes its own BF16 result index;
lane arrays, split partials and scalar accumulators are local to that row.
Route status is written outside the parallel loop. Inputs are read-only, and
the inherited alias guards forbid conflicting input/output storage. The
implicit loop barrier completes all row work before the operation returns.
This change does not parallelize a reduction or change device arithmetic.

The packet33 non-GEMV wrapper now instantiates only attention score, softmax
and value. It no longer links unused packet33 copies of GDN or selection.
The remaining generic and fixed QSA kernels preserve the reviewed body.

The fixed QSA specialization requires capacity 128, budget 2048 and exactly
one token. The prepared W windows use context/capacity 256, so they execute
the generic round2-body fallback under `p33.qsa.shape`, not the fixed-128
specialization. K2's fixed-128 QSA timing therefore does not establish a QSA
speedup at the W window's capacity. The whole W run must be measured on its
own; no fixed-shape speed improvement may be inferred for context 256.
This is a specialization coverage limitation, not an arithmetic change.

Final reviewed source hashes:

- `p33_candidates.hpp`: `17f835ea9642d004eebbeb71c4b68dec5e3b795dbf6166c39a08f08307313797`
- `p33_submit.cpp`: `c7bcacd934e0d06639aaecf46625a0c3e1a8fea47dda799d415e5c392f21b84a`
- `p33_submit.hpp`: `b6833e2d825934c64d58d03e5b274e4bd1e87e7bd13082b8ca9caf01e3e302c8`
- `p33r2.cpp`: `4fe740e4accddc2ba4a5f733c16113c564b4a548d53d12f718a73227b80e5a86`
- `p33r2.hpp`: `f7d736727f5c77bd78a2eff8460c1b56e7984ef7bbb21c4cd803507df73c6895`
- `p33_candidate_cpu.cpp`: `648e43a52d503a62af85640c756db9fe95525b7d526a5f8f99c8612f6a6517e0`
- `p33_candidate_gates.py`: `9e392836d79f43cc3da4bab945dbae85c66f172a3b3b480972ec7a209bd05988`
