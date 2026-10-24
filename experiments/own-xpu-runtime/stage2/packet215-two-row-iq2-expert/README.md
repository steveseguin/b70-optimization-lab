# P215: two-row IQ2 gate/up arithmetic

This packet passes a standalone synthetic CPU proof of sharing IQ2 weight
decoding across two routed rows. It does not integrate a paired expert operator
into the Engine or compile or execute a native device kernel. The corrected
candidate passed 100 checks across 17 cases, including all BF16 output and
status/error bytes against the selected control and separate scalar oracle.
The first arithmetic attempt and diagnostic attempt remain retained failures.
The [successful proof](evidence/arithmetic-proof.json) and
[build receipt](evidence/cpu-build.json) bind 53 compiler dependencies and
23 reused GNU Host objects. Its single Host owner closed safely with zero
in-flight work and zero live bytes.

The control is the unchanged selected `p58ag::expert` GNU Host operator:
`Kernel<IQ2_S,2560,64,false,true,0,true>`, with 640 output rows, ten route slots,
512 logical expert entries and the 65,536-entry half conversion table. A
separate `p49dvirtual::host_row<IQ2_S,2560,8>` scalar decoder supplies a second
oracle. The candidate preserves eight accumulation chains per physical lane,
the original local and four-lane reduction trees, exceptional decode handling,
BF16 writes, route statuses and sticky errors. Gate and up outputs retain their
original route slots.

The original candidate and its failed run are retained in
[the first attempt](evidence/cpu-1792805663473210614/receipt.json). The
[diagnostic attempt](evidence/cpu-1792805982161648696/receipt.json) identified
row 1, gate, slot 0, output row 6: candidate BF16 `0x7fc0`, selected/scalar
`0xffc0`, with identical status bytes. The paired row's accumulation compiled
with reversed ADDSS operand priority; recomputed single-input and both controls
retained negative NaN while paired row 1 retained positive NaN. The correction
explicitly preserves the accumulator when both addition operands are quiet
NaNs. Other additions, decoding, trees and counters are unchanged. It does not
canonicalize output or substitute an oracle. This behavior is tied to the
selected GNU Host control; native NaN propagation remains unqualified.

The full-shape disjoint case performed 8,192,000 decoded-tile visits. Five matched
slots reduced this to 6,144,000; ten matched slots reduced it to 4,096,000, with
exact control/oracle output equality. These are counted synthetic decode visits,
not runtime speed measurements. The successful attempt is
[cpu-1792806179719719049](evidence/cpu-1792806179719719049/receipt.json).

The actual matcher greedily pairs the first unmatched opposite slot only when
expert ID, slice, both backing addresses/generations and half-table storage
agree. Duplicate slots remain separate work. `raw_id_overlap`, `tuple_overlap`
and `pair_count` count slot-multiset matches, not distinct common experts.
Backing/slice mismatches take the ordinary independent arithmetic path. Invalid
routes preserve the selected status/NaN behavior; a valid zero-count slice
writes NaN tails with a successful status and performs no decoding.

The candidate's raw CPU interface is internal to the fixture. Its null/count/
geometry checks are not allocation extent, lifetime or alias admission. The
fixture owns complete disjoint active buffers and full pointer tables, with
20 compact synthetic expert backings plus one decoy backing per projection and
deliberately aliased unused table entries.
This is not a production binding or prepared-operation proof.

The fixture covers four full-shape overlap cases and short duplicate, slice,
backing, generation, half-table, invalid-route, zero-count and numerical edge
cases. Isolated exceptional output rows and decoded-tile bit comparisons keep
NaN propagation from masking finite zero/subnormal behavior. All output and
status/error bytes are compared against both independent controls. Instrumented
decode counts record actual candidate visits: one shared visit feeds two
independent input accumulators. They establish arithmetic reuse, not measured
memory traffic, throughput or observed P201 expert overlap. See the separate
[source opportunity](source-opportunity.md) for the conditional value estimate;
its distinct-expert assumption does not apply to duplicate-slot cases.

`build_cpu.py` uses the pinned GNU Host objects and relocates exactly one include
in the frozen selected header; it does not alter that header's arithmetic. Every
compiler dependency must match the admitted source closure before the fixture
can run. Attempts retain source snapshots, compiler output, dependency and
binary hashes, and raw fixture output/failure logs. Generated headers and binary
remain ignored under `build/`. The designated tester alone invokes:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
taskset -c 8-15,24-31 nice -n 19 /home/steve/.venvs/vllm-xpu/bin/python -B \
experiments/own-xpu-runtime/stage2/packet215-two-row-iq2-expert/build_cpu.py --run-host-only
```

The helper enforces a 4 GiB address-space limit, compiler-turn coordination and
a fresh 128 MiB write reservation above the 27 GB root floor. There is one
bounded compile and one bounded synthetic run, with no automatic retry. The
Host backend executes CPU arithmetic with simulated queue/event ownership;
it supplies no native event or device-performance authority. IQ3 layer 2,
down projections, production captures and Engine integration remain outside
this packet.
