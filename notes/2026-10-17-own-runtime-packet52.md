# Packet52: free-order GEMV ceiling prepared

Packet52 is built and CPU-checked. No GPU program ran, no model oracle was
started, and no production kernel was integrated. The arithmetic-v3 decision
is pending the coordinator's two exactness and two timing windows. The
packet49 oracle and packet49c units were left untouched.

The [decision rule](../experiments/own-xpu-runtime/stage2/packet52-freeorder/PREREGISTRATION.md)
and [source diagnosis](../experiments/own-xpu-runtime/stage2/packet52-freeorder/DIAGNOSIS.md)
were committed and pushed first, in `e19ffb4d7`, before any build/device
qualification. The rule requires one common set of variants to save at least
120 microseconds per ordinary M1 layer in each fresh timing owner. The sum is
an operator budget, not measured model throughput. No GPU result exists yet;
therefore this is neither a positive nor a negative speed result.

The source census corrected two brief details: production selects ten experts,
and the quoted 96.7/37.2 us QKV/Z values came from unadopted packet48b candidates.
Controls use actual packet49c dispatch: accepted packet48b experts, packet51
HC/attention winners, and unchanged packet45 dense and mixed small-FFN paths.
M2 executes both independent rows serially, matching the current engine.

The diagnosis finds substantial decode work and dependent sums in IQ2, and a
mixture of weight supply and ordered accumulation in QKV. Many total
workgroups do not establish enough independent memory requests per resident
core. IQ4 has shorter chains and many small row groups; HC has a low-to-gate
dependency and uneven row geometry. Attention already has its split and
shared-sigmoid improvements, small FFN includes all four mixed-format members,
and Z has little planning headroom. These are source hypotheses, not hardware
counter measurements. The Little's-law examples explicitly assume latency.

[Five variants](../experiments/own-xpu-runtime/stage2/packet52-freeorder/VARIANTS.md)
test 16 or 8 lanes per row, two or four tile accumulators, deterministic split4,
vector loads and a locally staged IQ2 table. `row32-quad-v8` directly shortens
the K2560 chain from 80 to at most 24 additions without a second launch. The
format/K and arithmetic-order device paths are specialized at compile time.
The split arm includes partial writes and the second stage in timing.
Attention preserves the existing shared injection-factor computation.

CPU evidence:

- GNU host, Intel host and SYCL compile-only builds passed. Existing sealed
  packet45 support objects were verified and reused; the Intel host result is
  cross-compiler coverage of the new packet code, not an independent rebuild
  of all historical runtime support.
- Four fresh bounded processes, two under each host compiler, each passed 35
  cases. All four output receipts are byte-identical. The independent scalar
  mirror is checked against the format-specialized device traversal on CPU,
  including routed pair/status paths, HC/attention epilogues and split partials.
- Two fresh complete-shape M1 host processes each passed 42 comparisons, covering
  all seven production controls and five variants. Their output receipts
  match byte for byte. They took 9.03 and 8.98 seconds with one CPU thread.
- The mocked coordinator/parser suite has 15 tests. It refuses missing cases,
  controls or M2 rows, wrong capture extents, invalid event accounting, stale
  companion bytes and incompatible owners; it checks the exact 120 us threshold
  in both owners and the script-file launch contract.

The first Intel host launch failed before main because `libiomp5.so` was not
on its library search path. The failed CPU-only receipt is retained; compiler
RPATH corrected it. Review also corrected the initial shared mirror traversal,
the small-tuple exactness composition, repeated-control pairing, full-arena
reset overhead, and missing manifest handoff. No GPU or arithmetic failure
was hidden. Finite synthetic BF16 outputs can agree across changed orders;
that is not proof of identical FP32 sums or unchanged model tokens.

The build peaked below 67 MB, well within the 1 GB cap. Cleanup removed 7,677,511
bytes of this packet's regenerable compiler objects and copied initial smoke
receipts into retained evidence before removing their scratch copies. The
final retained build is 59,135,802 bytes. No other packet's build or reserve was
touched. The three binaries, compiler logs, baseline relink proofs, source
closure, CPU receipts and final seal remain available.

[Exact coordinator commands](../experiments/own-xpu-runtime/stage2/packet52-freeorder/WINDOW.md)
use card0 / PCI0000:23:00.0, script files, nice19, approved cores, closed
environment, explicit zombie-tolerant memory sensing and fault supervision.
E1/E2 each contain 252 full-shape comparisons. T1/T2 each contain 44,100 arm
records and 72,450 compute events. Plan 2–5 minutes per E window and 6–12 minutes
per T window, with a 1,140-second cooperative watchdog. These are scheduling
estimates; packet52 device wall time is unmeasured. Four cached input snapshots
and scoped group resets remove repeated 16 MiB scratch/workspace copies.

The [arithmetic-v3 sketch](../experiments/own-xpu-runtime/stage2/packet52-freeorder/ARITHMETIC-V3.md)
identifies the scalar-oracle call paths, explicit class selector, exact orders,
unchanged exceptions and packet53 gates. It budgets about five hours for one
combined two-worker oracle campaign if the measured rule passes. Packet52
launches no oracle job and chooses no winners in advance.

All local execution used low priority and the permitted CPU cores; Python
used `-B`. The initial task pull used `git pull --rebase` on main. Source
changes remain in the new packet and this state/note record. Existing sealed
packets, services, power, memory, swap and cache settings were preserved.

Evidence: [CPU gates](../experiments/own-xpu-runtime/stage2/packet52-freeorder/cpu-gates.json),
[Python gates](../experiments/own-xpu-runtime/stage2/packet52-freeorder/python-gates.json),
[build receipt](../experiments/own-xpu-runtime/stage2/packet52-freeorder/build-receipt.json),
[seal](../experiments/own-xpu-runtime/stage2/packet52-freeorder/seal.json),
[independent review](../experiments/own-xpu-runtime/stage2/packet52-freeorder/REVIEW.md),
[cleanup](../experiments/own-xpu-runtime/stage2/packet52-freeorder/cleanup.json).
