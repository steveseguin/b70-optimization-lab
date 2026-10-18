# Packet141: measure the transfer gap

Started 2026-10-18 18:07 UTC. CPU-only preparation; no device launch or queue
change is authorized here. Deadline for sealed proposal: 19:07 UTC; two-hour box.

## Preregistered decision, before any packet141 device data

For each class, sum its kernel events within a half, then aggregate matched
repeats. If every class's cold in-order / warm-micro ratio is <=1.15, close this
body lever: kernel-bound under this diagnostic, retaining the 59–60 working
band. If any class has ratio >=1.30 and cold cost >=0.5 ms per half, recommend
layout/allocation/order testing for that class only. Otherwise report and close.
This is a diagnostic decision, not a model speed prediction or record change.
Incomplete coverage, route mismatch, output mismatch or invalid event clocks
make the result inconclusive, never a kill-gate pass.

Use packet136 bundle8 unchanged arithmetic, packet49's bound oracle and
packet138's incident-retrospective capture. One lane-B load; real rank0 half,
24 layers. A short model window reconstructs real temporal state, with every
emitted token checked against packet49. The three arms use identical state and
prepared kernel calls. No graph capture, profiler, cache precision change or
host cache drop. Cold means a device-local eviction sweep before the half;
report this as a controlled cache condition, not proof of a specific L2/L3
occupancy. Pre-touch reads only the relevant weights immediately before their
consumer and is excluded from kernel time but reported separately.

Sources reviewed: packet110, 112, 115–117, 119, 128b, 134 and 140 negative
indexes; packet135 is represented by its CPU analysis (no packet135 directory).
Packet110's floor is representative scaling; packet128b failed overhead.
Neither supplies a matched packet141 baseline. The current record is unchanged.

Limits: 4 GiB CPU preparation, nice19, CPUs8–15/24–31, python -B, stdin closed;
compiler turns through ops/compile_turn.py; root >=25 GB, build <=300 MB,
device output <=200 MB. No services, GPU, sudo, host settings or live queues.

## CPU preparation and review

The full-size allocation rehearsal passed on both ranks. The selected half is
530 kernels over 24 layers, with 778,473,844 bytes of mutable state. All 15
Python safety/provenance/protocol checks passed. Both real native exec paths
were intercepted before execution and passed closed-environment and limit checks.

Review added normal engine enqueue/finish bookkeeping to all measured arms and
one uninstrumented cold control half per block. Observer overhead above 10%,
or a between-kernel gap >=0.5 ms and >10% of span, makes the kernel-bound
conclusion inconclusive. These checks only withhold the preregistered verdict.
Natural is a no-extra-eviction control after state restoration; it cannot prove
physical L2/L3 occupancy. Warm per-site output restores are excluded from event
times and can affect residency; complete-half hashes must still match exactly.
No speed result is inferred from this CPU preparation.

Both native builds now pass. Final CPU seal and temporary lane-B queue plan
pass. Physical build files total 62,013,917 bytes, with more than 32 GB root free.
The read-only follow-up review found no blocker in the corrected enqueue and
control paths. Inherited whitespace was preserved with frozen bytes; no existing
packet or live queue was edited. Device timing, exact-state equality and cache
sensitivity remain pending. Ready marker follows this preparation commit as the
last write of the milestone; the analysis reader is prepared afterwards.

Deadline exception: at 19:09 UTC the final build, seal and temporary queue plan
were complete, but the readiness marker had not been written. The 19:07 UTC
proposal deadline was missed while the final host link waited for the protected
whole-host compiler hold. That hold was left untouched. This is a timing miss,
not a device failure. The two-hour work box still applies.


## Packet141b — early rank exit repaired on CPU, October 18

The first probe never ran a model step. Both ranks saved `Level Zero GPU index`
in their receipts, although their logs showed only the allocation plan. Their
argv already contained `--authorized-device-window`. The device compile used
`-fsycl` without `OWN_RT_HOST_ONLY`; the host-only p141 diagnostic exception
was not the cause. The rank catch wrote files but printed nothing unless saving
those files also failed.

The exact closed environment could not load the Level Zero adapter: its Intel
`libumf.so.1` dependency was missing. CPU `dlopen` reproduced that error without
calling any device API. The original device binary parsed both real rank argv
and reached the existing-output guard; only the priority argument was adjusted
from 0 to 19 for that CPU check. Original logs, launch records, receipts,
ownership/drain evidence and the failed output tree are retained unchanged.
No new kernel fault was reported in the supplied failure; the existing count
of two was unchanged.

The device binary now explicitly needs an unmodified packet-local copy of Intel
UMF 1.1.0, with its license and notices. Rank exceptions also print immediately
to stderr. The new CPU gate runs the real device parser with both original argv
plus a safe exit flag; it shares the constructor's exact selection checks,
loads both Level Zero adapters and returns before model, IPC or device APIs.
Traces show no GPU or model-file opens. Six bad argument cases refuse, and two
missing-IPC tests prove that both native ranks write their exception into the
captured logs. The gate never claims successful GPU enumeration or computation.

One compile turn rebuilt the two entry objects and linked both binaries; peak
compiler child RSS was 731,516 KiB. Production kernel objects, numerical flags,
selection, model bytes and `iq3-p49-split32-v1` are unchanged. The prior full-size
allocation receipt is reused; no model, GGUF, or full-size allocation run was
performed. All commands used nice19, CPUs8–15/24–31, Python -B, closed stdin and
a 4-GiB CPU cap. No GPU, service, live queue, sudo or host setting was touched.

`analyze.py` is complete. It checks finished/released evidence, hashes, exact
47+8 oracle tokens, full site/event coverage, routes, state equality, controls
and clocks. It sums complete samples before medians and applies the registered
<=1.15 close / >=1.30 with >=0.5 ms class-followup gates. Invalid cache sensitivity,
observer overhead or issue gaps withhold the verdict. Pre-touch bytes and time
remain separate. Thirteen synthetic tests cover boundaries, summation, malformed
or altered evidence, equality and timing controls; all pass alongside the 15
existing probe tests. Synthetic values are not measurements.

The new queue pin guard also rejected inherited mutable source paths. Exact
compiled source bytes are now snapshotted under this packet; original commands
remain provenance, and parent objects use canonical immutable ELF paths. Three
small input links are now local copies with unchanged hashes. The selected
unchanged oracle result is explicitly included in the oracle binding. The
proposal is sealed through a packet-local snapshot, with no mutable ops pin.
Old build/seal/readiness metadata is retained as byte-verified gzip history.
This does not rebuild or modify any other packet or shared wrapper.

The fresh proposal is `packet141b-probe-B`, service
`screen-packet141b-probe-B.service`, output `evidence/probe-B-repair141b/`.
Temporary queue planning passes; it is not queued. The last readiness write
binds the repaired seal, native gate and queue plan. The coordinator's device
attempt must still reach the first timed sequence and pass all exact-output
checks; this CPU repair supplies no timing result or new model speed claim.

Repair evidence: `stage2/packet141-transfer-gap/evidence/repair141b/`.
Original attempt: `stage2/packet141-transfer-gap/evidence/probe-B/`.
