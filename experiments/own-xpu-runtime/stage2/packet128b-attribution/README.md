# Packet128b: sampled bundle7 attribution

CPU preparation only. The coordinator owns one lane-B load: twelve fixed
prompts, 64 tokens each, all 768 tokens checked against `iq3-p49-split32-v1`.
Target weights, verifier, arithmetic, bundle7 selection, 24/24 placement,
80,128-row draft prefix and BF16 KV remain unchanged. Diagnostic only.

Packet128 recorded every generated token and measured **42.211 tok/s**, just
**0.728 of 58.0** (0.724 of 58.3). Its overhead gate failed. Its copy timestamps
also broke an analyzer that assumed one non-overlapping clock per rank.
Those observations do not measure this packet's overhead.

This new copy records only generated fixtures **9–16 inclusive** in every
request, across all 48 layers and both ranks, without selecting by hit/miss.
Other tokens bypass the added event-map, label-copy and event-report work.
The runtime's existing event ownership, profiling and draft timing stay intact.
No kernel, queue, synchronization barrier or arithmetic change is introduced.
JSON stays buffered until request boundaries outside decode timing.

The analyzer uses complete prediction cycles **10–16**: rank0's speculative
work/correction is fixture k; rank1's verification/head/draft is fixture k−1.
It requires all 48 layers in each of those 84 cycles and both outcomes in the
sample. Boundary cycles are excluded explicitly; unsampled cycles never enter
averages as zero cost. These sample costs are not whole-suite cost estimates.

## Queue and clock accounting

Every recorded event has a submission-route identity: `compute`, `copy-auto`
or explicitly selected `copy-bcs`. Draft and target kernels share the current
compute queue. Actual snapshot compute kernels keep the compute identity.
The analyzer also accepts separately identified additional queues.

SYCL does not expose the physical engine for automatic copies here. These are
route labels, not a claim that every automatic copy ran on BCS. Each queue's
busy time is an interval union, allowing legitimate overlap. Compute gaps use
only the compute stream, within a sampled fixture with no missing event IDs.
They mean gaps between observed compute kernels, not proven whole-card idle.
Zero-duration copy timestamps are unresolved; they are never treated as free
work or used in compute-idle arithmetic. Host waits remain separate and overlap
GPU work. No timestamps are subtracted across queues or ranks.

The class-balanced rate over each request's 63 decode intervals must reach
**0.90 × 58.0 = 52.2 tok/s** before any ranking is built, including JSON output.
Ratios to both 58.0 and 58.3 are reported. This historical, different-length
comparison is a distortion check, not a matched causal overhead experiment.
Failed gates produce no lever ranking. All 20% reduction scenarios remain
optimistic projections within the observed sample, never measured gains.

## Coordinator handoff

[Proposed B job](../../ops/lane-queue/proposed-p128b-attr-B.txt): exactly one
load and no retry. Expected duration is 4–6 minutes; the worker deadline is
1,440 seconds (4 × 6 minutes), inside the inherited 3,600-second outer watchdog.
No live queue is edited by CPU preparation.

`run_screen.py` runs the analyzer automatically after successful drain and
lease release. A report failure returns a failed job; it does not reload the
model. To rerun only the CPU report after inspecting that failure:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet128b-attribution/analyze.py </dev/null
```

Outputs are `evidence/budget.json` and `BUDGET.md`. **The new device exactness,
throughput, overhead ratio and lever ranking remain pending.**

## CPU gates and reconstruction

All 84 parent symlinks were preserved with `copytree(symlinks=True)` and compared
using `find -type l`; [copy audit](copy-symlinks.json). Parent device output is
not copied into the new evidence directory. Parent source hashes are retained.
Only the engine entry is rebuilt; arithmetic objects are reused by exact hash.
All compilation uses packet94's serial compiler turn and honors whole-host holds.
Root free space must remain ≥25 GB, the build ≤250 MB, and CPU work ≤8 GiB.

The all-window gate covers this view's one registered `attribution-B` window:
real input/oracle/selection checks to both intercepted native argv, full-shape
native startup, a whole 12-request worker rehearsal, and real queue-loop planning
and success/failure completion on a temporary queue copy. Operational state and
native results in rehearsals are explicitly synthetic; no GPU or service runs.
Copied historical eleven-window entrypoints are not registered by this view.

The drain regression includes the old deadline-crossing failure. The getrlimit
gate checks every inherited limit at both actual intercepted rank exec points,
and refuses a finite address-space cap. Resource caps are installed only in
CPU-only main processes; the positive limits probe necessarily retains the
uncapped launch environment and allocates only small CPU snapshots.

From the repository root, prefix each Python command with
`nice -n 19 taskset -c 8-15,24-31 python3 -B`, and close stdin with `/dev/null`:

1. `cpu_prepare.py build_engine.py cpu_gate.py reset_gate.py full_shape.py recorder_gate.py python_gate.py`
2. `seal_view.py --reseal`, then `cpu_prepare.py argument_gate.py`
3. `seal_view.py --reseal`, then `launch_limit_gate.py` directly (not through the capped CPU driver)
4. `cpu_prepare.py queue_gate.py final_check.py`

Use paths under this packet for those scripts. Run `parent_reanalysis.py` only
as a regression on old intrusive data; its inferred route tags and post-hoc
sampling cannot establish the new runtime's overhead.

[Work note](../../../../notes/2026-10-18-own-runtime-packet128b.md),
[preparation closeout](CPU-PREPARATION-CLOSEOUT.md), [retention](RETENTION.md).
