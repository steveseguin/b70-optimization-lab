# Independent GEMV review

Reviewer: packet27 nongemv subagent, independent of GEMV implementation.
Source-only CPU review; no device ran. Exact file hashes are in `review-gemv.json`.

The new GEMV kernel arithmetic and output ownership passed source review. The
FP32 input preparation widens BF16 by a bit shift and bitcast. Its consumers keep
the original product sequence and reduction tree. The prepared buffer is ordered
before use and invalidated when a writer touches its source or a token begins.

The packed64 IQ4 path uses the same eight code bytes for lower/upper nibble lanes.
Owner `lane & ~2` shares those bytes with the matching lane in the upper half of
each 32-value quantization block. Scale multiplication, nibble selection and each
lane's product order stay unchanged. Expanded paths preserve signed code values
and scales. Loads use byte vectors, so packed row alignment need not be eight.

The rows2sg path emulates 32 virtual lanes in each 16-lane half subgroup. Two
private accumulators retain their original left-to-right products. Widths 1,2,4,8
reduce the two virtual halves separately; their root addition is exactly width16
of the old adjacent tree. Skipping an empty third tile removes no arithmetic.
Inactive halves do no subgroup operations inside their private decode branch;
all physical lanes still participate in the following shuffle reductions.

Split partial slots and output rows have unique writers. Workgroup barriers are
unconditional across active and padded rows. Route status is written once by the
row-zero leader per slot. The binding validator rejects conflicting outputs,
missing extents, wrong formats, or unsupported geometry before submitting.

No new descriptor interpreter is present: type/candidate selection occurs on the
host, template arguments specialize device arithmetic, and the by-value binding
set supplies pointers and geometry only.

One integration finding outside GEMV arithmetic was sent to the main-file owner:
folded route+gather was forced to packet26 implementation 1, preventing its new
round2 dispatch. The owner fixed it: folded route now reads the explicit route+gather fusion choice; round2 maps to implementation 2.

Native identity, performance, and fresh-owner tests remain pending coordinator
windows; this review does not claim measured speed or establish device parity.

## Final CPU scheduling and receipt review

The final review also covers `gemv_timing.cpp`, the CPU-only OpenMP additions,
and the FP32-cache memory accounting. Updated hashes are in the JSON receipt.

The two-thread GEMV loop assigns whole rows. Route/status writes precede the
parallel region, all inputs are read-only, and each `(slot,row,projection)` output
has a unique writer. Each parallel region joins before processing the next slot.
The complete arithmetic tree stays within one thread. The two-thread GDN loop
similarly owns one whole 128-value state slice per row; token recurrence stays
serial inside that row. No thread writes shared guard/status inside either loop.
Both pragmas are confined to CPU code. The GDN scheduling delta was authored by
the GEMV agent and independently reviewed here; the rest of GDN has a separate
independent review by the small-GEMV agent.

The fixture backend pairs 64-byte aligned allocation and deallocation correctly.
K1 reads and checks each output. K2 reads outputs on its first and last repetition;
its receipt explicitly records that boundary. Intermediate repetitions are timed,
not individually byte-checked. The FP32 preparation event remains in the measured
sequence and its stage count, so preparation cost is included. This review does
not extend finite GEMV qualification to nonfinite scales or activations.

The plan now accounts for 174,080 FP32 elements, or 696,320 bytes, on each card,
matching the actual prepared-input allocation. No new numerical, write-race or
interpreter defect was found in these final changes. Retained rebuilt CPU gates
remain the execution evidence; no device executable was run for this review.

## Routed half-table candidate

Independently reviewed the final `p25.half_table` registration, preparation,
consumer addressing, guards and K1/K2 integration. The temporary table stores
only the FP16 block scales converted through the same `iq3::half` routine. It
does not stage decoded weights. IQ2/IQ3 scale expressions keep their parentheses,
then multiply the same signed grid integers and input values in the original
lane order and reduction tree.

The table is `[projection][route slot][output row][quantization block]`. Both
preparation and GEMV map route slots through the same validated expert ID and
row offset. Paired gate/up consumes two disjoint projection slices. The model
workload needs 512,000 bytes, within the existing 4 MiB workspace. Repeated expert
IDs still have distinct slot slices. Invalid rows write zero table entries
without accessing invalid source rows; the GEMV retains its original invalid-row
and status behavior.

Each preparation item writes one float. The owner orders that event before the
GEMV consumer and orders later workspace reuse after the consumer. The CPU
preparation distributes independent indices over at most two threads and joins
before consumption. Extent and alias guards run before either kernel; K1/K2
exercise missing, undersized and aliased workspace rejection. The preparation
is included in the two-event candidate timing.

A work-in-progress pointer issue was identified during review: an unpaired call
formed an unused pointer into a nonexistent second projection. The author had
independently fixed it, and final host/device call sites now form the peer table
pointer only when paired. No remaining arithmetic, race or interpreter defect
was found. Fresh device-owner exactness and card timing remain required.
