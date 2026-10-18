# Packet58y: attribution after overlapped cache maintenance

CPU-only preparation, time box 75 minutes from 18:07 UTC. Main matches origin/main
at initial fetch (38d4ecee4). Unrelated dirty orchestration files are preserved.
No device run, service, live queue, frozen packet or host setting is changed.

## Preregistered decision gate — before any packet58y device data

A next one-card implementation needs a supported projection of **at least +3%**
throughput on the class-balanced 99-interval metric. For a token span T this
requires saving at least T * (1 - 1/1.03), or 2.9126% of its wall time.
Use each prompt's measured spans, then medians within classes and across classes.
A perfect-removal bound below +3% kills that lever for this evidence. A larger
bound only admits further investigation; it is not a measured gain. Unknown
critical-path costs remain unknown and cannot pass the gate by assumption.
No changing arithmetic, weights, BF16 KV, prompt reuse or packet49 oracle.

This is a diagnostic, not a record or promotion. One model load, overlap mode,
all twelve fixed prompts, 128-token cap, every generated token checked against
`iq3-p49-split32-v1`. Cache starts empty and persists as immutable weights only.
First/cold prompt stays in the evidence and aggregate; no warm-up filtering.

Host spans use steady_clock around existing work and existing waits only.
No added per-kernel fences, external profiler, queue profiling or graph-event
profiling. Device durations without valid timestamps are null, never zero.
The existing compute-tail wait includes zero-copy miss kernels: their separate
critical-path duration is unidentifiable without perturbing execution. Record
zero separate miss-wait calls and label their actual stall cost unknown.
Fill copies have no blocking per-token wait in the overlap path; retain their
submissions, pending state, actual published-pointer miss counts and payload
bytes. These are logical payload counts, not measured PCIe traffic.

## Coordinator handoff constraint

New proposal only: proposed-p58y-attrib-A.txt, card 0 / lane A / whole host.
Expected duration at most 900 seconds; watchdog 7200 seconds (8x).
Batch immediately after packet58x smoke and bracket in their SAME whole-host
hold, with lane B paused and drained continuously. Never acquire a standalone
hold for this diagnostic. Preparation plans temporary copies and never queues.
Packet58u measured admission, drain fix, native getrlimit gate, closed launch
environment, lanequeue screen-<job> unit names and recorded oneAPI path remain.

Larger-cache versus miss-path ranking remains pending packet58y device evidence.
The brief's historical 58v figures and 58x +2.2% projection are motivation,
not a replacement for the new split. Prepared analysis will report bounded
levers and explicitly identify costs that cannot be separated.
