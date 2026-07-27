# Laguna — the XCCL startup hang is a GPU driver fault, not a code regression

> **RETRACTED CAUSAL CLAIM — HISTORICAL NOTE ONLY.** The later audit proved
> that post-recovery “0/4” summaries came from a wrapper that never launched
> the Python probe. Module-reload, FLR, GPU-fault, and shared-memory conclusions
> drawn from those non-runs were unfounded; host health was unknown at that
> point. Later corrected TP4 work completed successfully and the lane closed at
> the qualified 102.971-legacy / 101.942-conventional result. Read the
> [probe correction](2026-07-26-xccl-probe-harness-correction.md) and
> [current resume](../RESUME.md). The original text is preserved below so the
> mistake remains auditable.

Date: 2026-07-26 America/Toronto

Status: **environment fault. All measurement is suspended until the box is
recovered.** Approved record remains **94.920039** tok/s. Goal of 102 not met.

## What happened

Every run after roughly 03:00 froze during startup immediately after XCCL
topology recognition: the server log stopped at 58-59 lines, workers spun near
full CPU, the health endpoint never listened, and the leg's startup timeout
fired. This affected width 12 and then width 8 alike.

I suspected my own changes and reverted two of them in turn — the in-forward
diagnostic probes, then the lazy per-slot collective buffers. Neither restored
startup.

The decisive test was to check out the **approved record commit**
`ef334233deabeaeedb607056a2db1c90edb3887c` and run the same width-8
configuration. **It hung identically**, at 59 lines. That exonerates every code
change in this session as the cause.

`dmesg` shows the real cause:

```
xe 0000:47:00.0: [drm] Tile0: GT0: Timedout job: seqno=74707, lrc_seqno=74707,
                       guc_id=0, flags=0x73 in no process [-1]
xe 0000:47:00.0: [drm] Tile0: GT0: Kernel-submitted job timed out
WARNING: drivers/gpu/drm/xe/xe_guc_submit.c:1580 at guc_exec_queue_timedout_job
xe 0000:47:00.0: [drm] Tile0: GT0: reset done
```

Card 3 (`0000:47:00.0`) hit a kernel-submitted job timeout, a GuC submission
warning, and a GT reset. `xpu-smi health` still reports power and frequency OK
and all four cards idle at 43 MiB, so the fault is in the submission/GuC state
rather than a hard device failure.

## Probable cause, and it is mine

Over this session I repeatedly `kill -9`'d TP4 worker groups mid-run to recover
from failed experiments. Killing a four-rank XCCL job while collectives are in
flight can leave GuC execution queues wedged, which matches the observed
timeout-and-reset signature and the fact that the failures began only after a
long series of hard kills.

Cleaner recovery — stopping the service through the leg's own `stop_service`
path and waiting for it — should have been used instead of `kill -9` wherever
possible.

## Consequence for the evidence

Every run from the first hang onward measured a faulted environment, not the
code under test. Specifically:

- No conclusion should be drawn from those runs about the batched-M1 bound
  fixes, the collective preallocation revert, or the diagnostic probe removal.
- The earlier substantive results stand, because they predate the fault: M=12
  bitwise exactness on the full suite, the depth-11 speculation counters
  (+6.9% emitted per cycle), and the 685/684 versus 146/145 topology
  measurement.

## Required before any further measurement

1. Recover the `xe` driver state on card 3. A module reload
   (`modprobe -r xe && modprobe xe`) or a host reboot is the usual remedy; this
   is an operator decision and was not taken unilaterally.
2. Re-verify with a width-8 run at the record commit that startup completes,
   the audited 146/145 topology captures, and the scored median is near
   94.920 before trusting any width-12 result.
3. Only then resume the M=12 work.

## Standing next steps once recovered

1. Confirm the batched-M1 bound fixes actually restore a topology near 146/145
   at width 12; that is the untested hypothesis this fault interrupted.
2. Measure width 12 and compare against the record.
3. The width-two tree remains required for 102, since +6.9% on 94.920 projects
   only about 101.5 even at unchanged cycle time.
