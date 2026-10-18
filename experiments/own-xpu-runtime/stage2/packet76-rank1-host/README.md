# Packet 76: rank 1 event cleanup

CPU-prepared scheduling candidate from frozen packet70 sources. **Device
correctness and speed are unmeasured.** The quality authority remains packet49,
`iq3-p49-split32-v1`, with unchanged weights, kernels, arithmetic and BF16 KV.

[Attribution](ATTRIBUTION.md) accounts for the reported 1.608 ms residual:
1.457 ms of host housekeeping, 0.092 ms of outer setup, 0.001 ms of observed
device gaps after the layers, and 0.057 ms unresolved. The uninstrumented
control has 0.666 ms in the housekeeping bucket. Missing submit timestamps,
layer coverage and usable copy timestamps prevent a complete causal split.
The whole 1.608 ms must not be presented as recoverable production time.

`production` and `ordered` share one binary. `ordered` changes rank1 only:
an explicitly ordered backend proves completion of all tracked work from its
terminal event, instead of polling every event again. The original bounded
tail wait, queue synchronization, asynchronous error propagation, event release,
allocation lifetime and teardown remain. No kernel, transfer or state update
is reordered. No graph, compressed cache, thread, service or extra device
allocation is added. Other backends refuse the new path unless they implement
the ordered-prefix capability. The Device/Backend data layout and Backend
vtable are unchanged; the capability is a separate interface.

The hypothesis is that repeated event queries account for useful time within
host housekeeping. Its individual share was not retained in the old receipts.
New per-half fields `p76_retirement_ms`, `p76_retirement_calls`,
`p76_profiling_ms` and `p76_ordered_retirement` let the screen check this
mechanism. Timing hooks are identical in both selections. Rank1 draft and
target share an owner, so the retirement selection also applies to rank1's
draft drains and result-copy drains; rank0 retains production retirement.

## CPU gates

- GNU host and Intel SYCL device programs compile serially; neither model
  program is run. Unchanged numerical objects are hash-bound to packet70's
  actual packet65 build provenance.
- GNU and Intel each run the tiny mock twice in fresh processes. All 3,072
  output words match. Four drains use 3,072 completion queries in production
  and four in the candidate. Six refusal/error cases pass, including pending
  work, missing ordered capability, graph ownership and capture.
- The full-shape allocation-only mock runs the real setup, bank preparation,
  speculative-image allocation and post-load draft constructor for both
  ranks, both selections, and both 23/25 and 24/24. Every prepared target
  command is issued after post-load allocations to a backend that executes no
  arithmetic. Eight real memory-census admissions pass. Payload reads fail
  explicitly; device pointers are disjoint logical addresses, not RAM
  allocations. [Gate](evidence/fullshape.json).
- 69 tests exercise the original shared admission, refusal and reporting
  code; seven packet tests cover attribution and winner selection, including
  importing the actual worker in the closed launch environment.
- Both selections are sealed. All six shared v4 screen plans and both
  temporary lane-queue plans pass. [Final checks](evidence/final-check.json),
  [queue plans](evidence/queue-plans.json).

## Coordinator screens

Every screen calls the **unchanged shared** `../screen/v4-lanes/screen.py`.
Its full wrapper seal is pinned. No private wrapper or admission bypass is
used. The wrapper admits new lineages at **23/25**, so all controls and
candidates use that placement with rank1 draft. Packet70's selected wide64
experts, draft-HC and batched rollback copy settings are retained. This is a
matched scheduling screen at 23/25, not a measurement at packet70's 24/24
record configuration. The shared wrapper's actual 24/24 refusal is retained
in [evidence](evidence/shared-v4-24-24-refusal.json).

Lane A: fresh production → ordered → fresh production. Lane B: fresh
production → the exact improving lane-A winner → fresh production. There is
one preregistered candidate. B refuses before launching unless all three A
screens pass all 13 packet49 requests and the candidate beats **both** controls
on the class-balanced conventional 99-interval rate. Each screen keeps the
incident64 plus complete twelve-prompt 128-token suite, fault checks, memory
admission, cooperative drain and shared lane locks. There are 90 seconds
between screens and no retry. These are diagnostic screens, never qualifying
512-token results or a final record verdict.

Proposed job lines (not installed in live queues):

- [Lane A](../../ops/lane-queue/proposed-p76-A.txt)
- [Lane B](../../ops/lane-queue/proposed-p76-B.txt)

CPU verification from the repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet76-rank1-host/final_check.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet76-rank1-host/queue_plan.py </dev/null
```

The coordinator supplies the fresh fault review and authorized device window
through the lane queue. No GPU work or service was started during preparation.
The measured build tree is 138,872,656 logical bytes, below 1 GB. Builds enforce
an 8 GiB address-space cap, nice19, the requested CPU set, and serial compiles.

[CPU closeout](CPU-PREPARATION-CLOSEOUT.md) · [Do not repeat](DO-NOT-REPEAT.md) ·
[Artifact retention](RETENTION.md)
