# Packet58as: one-card bounded spin wait, CPU preparation

The one-card packet58aj engine now has a private A/B wait switch. The candidate
reimplements the two-card packet56x bounded-spin policy: spin for at most 250 µs,
yield periodically, then sleep for at most 20 µs or the remaining deadline.
It checks asynchronous errors on every iteration and retains completion error
propagation. The original millisecond poll remains the A control; the separate
DMA failure-recovery sleep stays unchanged. Packet58ar and all existing packet
trees are untouched. No GPU, service, settings or live queue changed.

Both compilers pass the wait tests and full miniature byte comparisons against
packet58aj. The two compiler runs cover 120 actual request resets; a separate
CPU probe compiled with the device defines exercises the real launch arguments,
production plan, five view transitions and sixty request resets. All 130
memory-sensor samples are present in that probe. Peak child RSS was 1,144,070,144
bytes; compilation, including the probe and both wait tests, used one shared
compiler turn. These are CPU checks, not device exactness or a speed result.

The analyzer replayed all sixty packet58aj and seventy-two packet58aq requests,
including their cold first views. The complete timing streams are preserved as
byte-identical private snapshots. The largest measured cold phase supports the
600-second operation wait at more than four times its duration. Tests reject
old evidence as a new wait-policy result, wrong tokens, an under-threshold
candidate and excessive drift. Threshold fixtures are labeled synthetic.

The proposal is `proposed-p58as-v5-A.txt`: one fresh whole-host lane-A job.
**No separate smoke:** K1a/K1b and an exact A0 control open the one-load
A0/B0/A1/B1/A2 bracket. Every view keeps resident lookups, the full packet58aj
composition, 21,552,729,600 cache bytes and BF16 KV. All sixty responses must
match `iq3-p49-split32-v1`; both B views must beat every warm A by at least 0.5%,
with at most 3% control drift. A0 is excluded only from speed/drift. Each view
also reports owner-thread CPU time as a percentage of one core. Actual CPU
utilization and device speed remain unmeasured.

Every native flag was checked against --help; actual entry imports and loaders
were checked in the real closed launch environment. Temporary lanequeue planning
and the shared `ops/rehearse_entry.py --report` pass. The shared tool's unranked
one-card preparation warning is covered by the separate real device-define CPU
probe, not hidden. Its generic synthetic smoke-report exercise is not a smoke
launch or prerequisite. The initial argument rehearsal found missing private
admission dependencies; the failed receipts remain, the dependencies were
restored byte-for-byte, and final entry checks pass. Queue pin review also
required private copies of the real-data replay and inherited admission inputs;
those are now included and sealed.

In-run checks cover stream presence/format and exactness only. There is no
wall-clock data-proof cutoff. The CPU stop floor is 27 GB and the device floor
25 GB. Model readers retain idle-class ionice. No fresh-process qualification,
record submission or publication is claimed by this screen.

The private 4 MiB rotary table and measured/admission snapshots are retained
because they are necessary for exact local rebuild and replay; restore their
original bytes from Git. Compiled objects are ignored, hash-bound and restored
from the frozen packet58aj inputs using the packet's restore manifest. This is
a local research packet, not a public deployment recipe.

[Packet and coordinator contract](../experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/README.md),
[final readiness](../experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/READY-FOR-DEVICE.json),
[native delta](../experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/native-delta.patch).
