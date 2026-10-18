# Packet93 coordinator handoff

The October 18 reseal uses packet84's restored submission tool. The original
`micro-B` run remains historical: head-transpose qualified at a 0.729 time
ratio; head-plane did not. Its old seal bindings cannot admit the new screens.
This reseal ran CPU checks only. A fresh `micro-B2` qualification is required;
full model-output qualification and engine performance remain pending.

1. Admit [proposed-p93-micro-B2.txt](../../ops/lane-queue/proposed-p93-micro-B2.txt)
   through the ordinary queue coordinator. It holds lane B but opens only
   physical card 2 (`0000:43:00.0`), filtered before device discovery. Its native
   index is 0 after that filter. No live queue was edited by preparation.
2. The diagnostic runs the full 248,320×2,560 target head. Exact FP32,
   BF16 logits and argmax precede timing. Each candidate gets 40 alternating
   production/candidate pairs with per-kernel event timestamps. The timed
   kernels use the actual copied production and candidate operation bodies,
   SG32/WG32 and all ten blocks. Allocation, upload and exactness checks are
   outside event time. Synthetic weights make this diagnostic evidence only.
3. The gate requires candidate median event time ≤85% of production, and the
   same threshold in each alternating order. This explicitly means 15% less
   kernel time, stronger than throughput×1.15. Missing, wrong-shape, inexact,
   nonfinite, incomplete, altered or undrained evidence refuses. The gate
   revalidates hashes and samples before each engine launch. No qualifying
   candidate means no screens; record the negative result and close that arm.
4. Use the B grid then A confirmation by default:
   [B grid](../../ops/lane-queue/proposed-p93-B-grid-B2.txt),
   [A confirm](../../ops/lane-queue/proposed-p93-A-confirm-B2.txt).
   The reverse is also preregistered:
   [A grid](../../ops/lane-queue/proposed-p93-A-grid.txt),
   [B confirm](../../ops/lane-queue/proposed-p93-B-confirm.txt).
   Choose one direction; never enqueue confirmation without its successful
   source grid. The source grid is production / qualifying candidates /
   production. The other lane runs production / exact improving winner /
   production. Outputs include direction and never reuse another direction.
5. The unchanged, hash-pinned shared v4 wrapper owns every engine screen. Its
   first incident prompt is a 64-token exactness smoke before twelve timed
   requests. Every 13-request check must pass; each prompt's acceptance counts
   must remain unchanged. The same candidate must beat both fresh controls
   on both lanes. Fixed 90-second gaps, one start per stage, no retries.

`run_micro.py` requires a coordinator-owned systemd unit, fresh fault review,
lane lease, shared drain permit, observed single-card file descriptors, host
memory admission and root free-space floor. SIGTERM requests a graceful stop
between completed kernels/uploads; no hard kill or automatic restart exists.
A failed/hung owner retains its reservation for coordinator recovery. A clean
micro exit releases its lease before CPU qualification/reporting. Micro output
is `evidence/micro-B2/`; a qualifying `qualification.json` binds its samples,
clean window, build, engine identity and screen seal. A lone micro process is
not a fresh-engine performance verdict.

The three B2 proposal names are fresh queue identities. Do not enqueue the
superseded micro-B proposal or duplicate the older B-grid/A-confirm proposals.
The engine output names are unchanged and must still be unused. Both screen
directions now read only the fresh B2 qualification. [Reseal evidence](RESEAL.md).

CPU-only rechecks from repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet93-packed-head2/final_check.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet93-packed-head2/queue_plan.py </dev/null
```

Plans are explicitly pending and non-runnable evidence. They do not waive the
measured micro gate, device smoke, fault review or matching-lane comparison.
The full-shape mock preserves real allocation/configuration/prepared submission
paths but does not read model payloads or execute device arithmetic. Isolated
wins may shrink inside the engine; neither CPU nor micro gates promote a speed.
