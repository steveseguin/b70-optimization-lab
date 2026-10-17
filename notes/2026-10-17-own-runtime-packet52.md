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

## Device results — free-order ceiling closed negative

<!-- campaign-closeout -->

### Question and identity

The coordinator ran the sealed packet52 synthetic, production-matched
operator fixture on B70 card 0 (`0000:23:00.0`), E1/E2/T1/T2 under `p52-b`.
This tested five changed arithmetic orders in seven classes, M=1 and two
serial M=1 rows for M=2, with ten distinct changing routed experts. It was
an operator budget experiment, not a full-model speed or quality result.

### Outcome

Both exactness owners passed all 252 comparisons against each variant's own
CPU mirror. Both timing owners completed. The common selection saved
**10.4675 and 10.4160 microseconds per ordinary M=1 layer**, far below the
preregistered **120 microseconds**. `arithmetic_v3_proceeds=false`.
No arithmetic-v3 oracle or production integration follows this packet.
The initial CPU-preparation account above is historical; its pending device
statements are superseded by these results.

### What worked

The selected gains were expsdown `row8-dual-v8` (3.020/2.8645 us),
small FFN `row16-v8` (4.8435/4.8435 us), and GDN Z `row8-dual-v8`
(2.604/2.708 us). These small changed-order gains do not meet the decision bar.
All observations, including regressions, follow; positive means saved time.
Paired medians are the registered metric, so subtraction of the two separate
arm medians need not give the same value.

| Class | Candidate | T1 saved us | T2 saved us |
| --- | --- | ---: | ---: |
| expsgate | row16-v8 | -18.541 | -18.333 |
| expsgate | row8-dual-v8 | -18.907 | -18.802 |
| expsgate | split4-row16-v8 | -21.458 | -21.562 |
| expsgate | row16-dual-local | -32.812 | -32.813 |
| expsgate | row32-quad-v8 | -18.750 | -18.750 |
| gdn.qkv | row16-v8 | -6.355 | -5.834 |
| gdn.qkv | row8-dual-v8 | -4.270 | -4.166 |
| gdn.qkv | split4-row16-v8 | -13.489 | -13.750 |
| gdn.qkv | row16-dual-local | -3.959 | -4.167 |
| gdn.qkv | row32-quad-v8 | -4.688 | -4.740 |
| expsdown | row16-v8 | -5.468 | -5.625 |
| expsdown | row8-dual-v8 | 3.020 | 2.864 |
| expsdown | split4-row16-v8 | -62.291 | -62.292 |
| expsdown | row16-dual-local | -4.479 | -4.480 |
| expsdown | row32-quad-v8 | -22.396 | -22.448 |
| attention | row16-v8 | -4.374 | -4.687 |
| attention | row8-dual-v8 | -23.437 | -23.698 |
| attention | split4-row16-v8 | -5.731 | -5.730 |
| attention | row16-dual-local | -9.062 | -9.218 |
| attention | row32-quad-v8 | -19.687 | -19.688 |
| hc.low_gate | row16-v8 | -60.416 | -60.364 |
| hc.low_gate | row8-dual-v8 | -94.685 | -94.583 |
| hc.low_gate | split4-row16-v8 | -49.793 | -49.794 |
| hc.low_gate | row16-dual-local | -68.230 | -68.230 |
| hc.low_gate | row32-quad-v8 | -48.437 | -48.334 |
| small.ffn.q6 | row16-v8 | 4.844 | 4.844 |
| small.ffn.q6 | row8-dual-v8 | 1.250 | 1.250 |
| small.ffn.q6 | split4-row16-v8 | 0.937 | 0.939 |
| small.ffn.q6 | row16-dual-local | 4.374 | 4.375 |
| small.ffn.q6 | row32-quad-v8 | 4.270 | 4.272 |
| gdn.z | row16-v8 | -4.114 | -3.802 |
| gdn.z | row8-dual-v8 | 2.604 | 2.708 |
| gdn.z | split4-row16-v8 | -8.959 | -9.061 |
| gdn.z | row16-dual-local | -4.896 | -4.896 |
| gdn.z | row32-quad-v8 | -4.584 | -4.688 |

### What failed or remains uncertain

Every expsgate, QKV, attention and HC low/gate variant was slower than its
production control. Expsgate lost about 18–33 us, worst with
`row16-dual-local`. Source inspection suggests that staging the 8 KB codebook
in every one of 6,400 short workgroups dominated; this is a hypothesis, not
a measured attribution to table fill or SLM bank conflicts.

The first `p52-a-e1` wrapper failed when a native child had dropped RssAnon
inside `exit_mm()` while its task state still read R. It was not a kernel
arithmetic failure. Fix commit `b9745a557` accepts the kernel PF_EXITING bit
alongside Z/X and continues to reject a live task missing its memory fields.
The failed receipt is preserved; the four `p52-b` windows used the fix.

E1/E2 took 33.79/34.04 seconds wall time; T1/T2 took 29.99/29.76 seconds,
including their wrapper work. Earlier minute estimates were conservative,
not measured durations. Control medians vary by pair: for example the first
small-FFN pairing is about 25 us while later pairings are about 18 us. The
full receipts preserve this variation; no single fastest control was chosen.

### Evidence and patches

[Compact two-owner summary](../experiments/own-xpu-runtime/stage2/packet52-freeorder/evidence-copy/p52-b-summary.json)
retains every class, candidate and M value. The adjacent evidence-copy folders
contain original window/receipt JSON and T summaries, including the failed
first window. Raw iterations stay at `packet52-freeorder/evidence/p52-b-*`;
the roughly 10 MB iteration files were not copied into Git. The original
sealed source, variant manifest and CPU evidence remain unchanged.

### When to revisit

Do not repeat this free-order grid or start arithmetic v3 on these results.
Packet53 instead tests expert-only scheduling and logical-lane packing while
keeping each production sum and adjacent tree exactly unchanged. Persistent
workgroups can amortize codebook staging; CPU proof and fresh device equality
must precede its two-owner 30 us timing decision. Dense-class free-order work
needs a new mechanism with evidence of meaningful headroom.
