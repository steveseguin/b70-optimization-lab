# Packet 107: ordinary layer specialisation

CPU preparation only. GDN layer 4 is **closed by an Intel raw-byte mismatch**.
QSA layer 3 is the remaining device candidate. No performance has been measured.
The first experiment deliberately stops short of a whole-runtime integration.

The sources are copied from packet97; unchanged compiled operators are linked
read-only from its frozen build. The parent link is reproduced byte-for-byte
before reusing its objects. `source-origin.json` pins the source snapshot;
no changing parent orchestration output is pinned. The local `selection.json`
is route-fast, rec-both-plus, exp-halfcache, wide HC, production HC norm;
head/host/draft settings do not participate in these two isolated target layers.
The arithmetic remains `iq3-p49-split32-v1`.

`layer_bench.cpp` composes complete real-shape layers, with the remaining
production operators unchanged. `specialised_layers.hpp` fixes head counts,
head routing, BF16 strides, capacities and 128/160/4096 launch extents. Selected
expert IDs and selected QSA token indices remain changing inputs. Synthetic
packed weights use the real mixed formats and the production half-cache/plane
repacking. They are not model payloads and this is not a model benchmark.

GDN prepares 16 Q/K head pairs and 48 gates once, then feeds the existing
four-row recurrence geometry. Full finite-layer output and state checks pass
on GNU. Both GNU operator repeats also pass exceptional cases. Intel finite
cases pass, but its NaN test changes output `0x7fc1` to `0x7fc0`; state bytes
match. Restoring the four-row CPU loop and then using strict FP exceptions did
not repair it. The latter failed source and byte evidence are retained in
`evidence/gdn-closed`. No tolerance, payload repair, or fallback is adopted.
The device entry explicitly refuses GDN. See [closeout](gdn-closeout.md).

QSA shares each 32-token BF16 K/V tile among four query heads in a 512-thread
workgroup. Its 32 KiB local K/V buffer replaces four sets of global reads.
Each head keeps its four score subgroups, FP32 tree, split maxima, denominator,
value tree and BF16/gate boundary. Admission and the upper combine are the
unchanged production functions. There is no descriptor interpreter, serial
whole-layer workgroup, duplicated norm, graph replay, or new host wait.

The CPU full-layer harness compares every producer output and all production
mutable allocations after each of four consecutive tokens (126–129), including
all recurrent, convolution, KV, pooled-index, routing and scratch bytes. Streams
change; state persists. Four distinct expert sets occur in each layer. Intel
host builds compile the harness/candidates with Intel and reuse frozen GNU
objects for unchanged operators; separate Intel leaf tests compile both the
changed candidate and its production arithmetic directly. CPU parity is not
device parity. The added GDN-only private preparation buffer is not production
state and is excluded from production allocation equality.

The proposed lane-B file contains two fresh process jobs, each restricted to
physical card 2 by the existing coordinator wrapper. Each first checks four
consecutive complete QSA layers, then compares 50 AB/BA pairs at each occupied
length 128 and 4096 (10 warm-up pairs, 40 measured). The two arms start every
pair from the same changing input/state snapshot. All production mutable bytes
are compared outside timing. Event execution sums are the metric; uploads,
readback, comparison and host enqueue are excluded. This cannot establish an
engine tok/s win. There is no retry, server, or live-queue edit.

Integration requires at least 80 µs median paired saving in **each** fresh
process at 128 tokens; 160 µs is the upper target. The 4096-token results are a
separate context diagnostic. Below threshold, close this QSA arm. A passing
micro still needs unchanged full-model oracle and fresh model screens.

Build/run commands and final evidence are recorded in the
[work note](../../../../notes/2026-10-18-own-runtime-packet107.md).

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md) records the bounded
outcome and the remaining gates. [Static access counts](evidence/code-cost.json)
are estimates, not device performance. `evidence/cpu-leaf.json` intentionally
has aggregate `passed=false` because GDN is closed; device admission checks
QSA's explicit passing field and the complete-layer receipt.
